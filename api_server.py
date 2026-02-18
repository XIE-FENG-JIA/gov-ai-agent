#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FastAPI Server for Gov AI Agent - n8n Integration
=================================================

啟動方式：
    uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload

n8n 呼叫方式：
    HTTP Request Node -> http://localhost:8000/api/v1/{endpoint}
"""

import asyncio
import logging
import os
import time
import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from src.core.config import ConfigManager
from src.core.llm import get_llm_factory
from src.core.models import PublicDocRequirement
from src.core.review_models import ReviewResult
from src.core.constants import (
    CATEGORY_WEIGHTS,
    WARNING_WEIGHT_FACTOR,
    API_MAX_WORKERS,
    API_VERSION,
    SESSION_ID_LENGTH,
    MAX_DRAFT_LENGTH,
    MAX_FEEDBACK_LENGTH,
    assess_risk_level,
)
from src.knowledge.manager import KnowledgeBaseManager
from src.agents.editor import EditorInChief
from src.agents.requirement import RequirementAgent
from src.agents.writer import WriterAgent
from src.agents.template import TemplateEngine
from src.agents.style_checker import StyleChecker
from src.agents.fact_checker import FactChecker
from src.agents.consistency_checker import ConsistencyChecker
from src.agents.compliance_checker import ComplianceChecker
from src.agents.auditor import FormatAuditor
from src.agents.review_parser import format_audit_to_review_result
from src.document.exporter import DocxExporter

logger = logging.getLogger(__name__)

# ============================================================
# Rate Limiting（簡易滑動視窗限流器）
# ============================================================

# 預設限流設定（可透過環境變數覆蓋）
_RATE_LIMIT_RPM = int(os.environ.get("RATE_LIMIT_RPM", "30"))  # 每分鐘請求上限
_RATE_LIMIT_WINDOW = 60  # 滑動視窗秒數


class _RateLimiter:
    """基於 IP 的簡易滑動視窗限流器。"""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window = window_seconds
        self._requests: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(self, client_ip: str) -> bool:
        """檢查該 IP 是否允許請求；同時清理過期紀錄。"""
        now = time.monotonic()
        timestamps = self._requests[client_ip]
        # 清理過期的時間戳
        self._requests[client_ip] = [
            t for t in timestamps if now - t < self.window
        ]
        if len(self._requests[client_ip]) >= self.max_requests:
            return False
        self._requests[client_ip].append(now)
        return True


_rate_limiter = _RateLimiter(_RATE_LIMIT_RPM, _RATE_LIMIT_WINDOW)


def _sanitize_error(exc: Exception) -> str:
    """
    清理例外訊息，避免洩漏內部實作細節（檔案路徑、堆疊追蹤等）。

    僅保留安全的錯誤類型描述，不回傳原始例外字串。
    """
    exc_type = type(exc).__name__
    # 允許向用戶顯示的安全錯誤類型
    _SAFE_ERROR_TYPES = {
        "ValueError": "輸入資料不符合預期格式，請檢查請求參數。",
        "ValidationError": "請求資料驗證失敗，請檢查欄位格式。",
        "TypeError": "請求參數類型錯誤，請檢查資料格式。",
        "KeyError": "請求資料缺少必要欄位。",
        "TimeoutError": "操作逾時，請稍後再試。",
    }
    return _SAFE_ERROR_TYPES.get(exc_type, "伺服器內部錯誤，請稍後再試或聯繫管理員。")

# ============================================================
# CORS 允許來源設定（安全性：避免使用萬用字元 "*"）
# ============================================================
_ALLOWED_ORIGINS: List[str] = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5678,http://localhost:3000,http://localhost:8080",
    ).split(",")
    if origin.strip()
]

# 僅允許 API 實際需要的 HTTP 標頭（避免使用萬用字元 "*"）
_ALLOWED_HEADERS: List[str] = [
    "Content-Type",
    "Accept",
    "Authorization",
    "X-Request-ID",
]

# 有效的審查 Agent 名稱
_VALID_AGENT_NAMES = frozenset(["format", "style", "fact", "consistency", "compliance"])

# ============================================================
# App Initialization
# ============================================================

# 全域實例（在 lifespan 中初始化）
_config: Optional[Dict[str, Any]] = None
_llm: Optional[Any] = None
_kb: Optional[KnowledgeBaseManager] = None
_executor = ThreadPoolExecutor(max_workers=API_MAX_WORKERS)


def get_config() -> Dict[str, Any]:
    """取得全域設定，延遲初始化。"""
    global _config
    if _config is None:
        try:
            _config = ConfigManager().config
        except Exception as e:
            logger.error("設定檔載入失敗: %s，使用預設設定", e)
            _config = {
                "llm": {"provider": "ollama", "model": "mistral"},
                "knowledge_base": {"path": "./kb_data"},
            }
    return _config


def get_llm():
    """取得 LLM provider 實例，延遲初始化。"""
    global _llm
    if _llm is None:
        config = get_config()
        llm_config = config.get("llm", {"provider": "ollama", "model": "mistral"})
        _llm = get_llm_factory(llm_config, full_config=config)
    return _llm


def get_kb() -> KnowledgeBaseManager:
    """取得知識庫管理器實例，延遲初始化（不可用時回傳降級實例）。"""
    global _kb
    if _kb is None:
        kb_path = get_config().get("knowledge_base", {}).get("path", "./kb_data")
        _kb = KnowledgeBaseManager(kb_path, get_llm())
    return _kb


@asynccontextmanager
async def lifespan(app: FastAPI):
    """在啟動時初始化共享資源，關閉時清理。"""
    logger.info("正在初始化 API 資源...")
    get_config()
    get_llm()
    get_kb()
    logger.info("API 資源就緒。")
    yield
    _executor.shutdown(wait=False)
    logger.info("API 已關閉。")


app = FastAPI(
    title="公文 AI Agent API",
    description=(
        "n8n 整合用的公文 AI Agent REST API。\n\n"
        "提供公文需求分析、草稿撰寫、多 Agent 審查、自動修正等功能。\n\n"
        "## 端點分類\n"
        "- **健康檢查**: 伺服器狀態查詢\n"
        "- **需求分析**: 自然語言轉結構化需求\n"
        "- **草稿撰寫**: 依需求產生公文草稿\n"
        "- **審查**: 格式、文風、事實、一致性、合規性審查\n"
        "- **修改**: 依審查意見修正草稿\n"
        "- **完整流程**: 一鍵完成需求→撰寫→審查→修改→輸出"
    ),
    version=API_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "健康檢查", "description": "伺服器狀態與健康檢查端點"},
        {"name": "需求分析", "description": "將自然語言轉換為結構化公文需求"},
        {"name": "草稿撰寫", "description": "根據結構化需求撰寫公文草稿"},
        {"name": "審查", "description": "各類審查 Agent（格式、文風、事實、一致性、合規）"},
        {"name": "修改", "description": "依審查意見修正草稿"},
        {"name": "完整流程", "description": "一鍵完成需求分析→撰寫→審查→修改→輸出"},
    ],
)

# CORS 設定（使用環境變數控制允許來源，標頭限定為實際需要的項目）
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=_ALLOWED_HEADERS,
)


# ============================================================
# 安全中介層：Rate Limiting + 安全標頭
# ============================================================


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    """
    為所有回應添加安全標頭，並對 POST 端點進行限流。

    安全標頭：
    - X-Content-Type-Options: 防止 MIME 嗅探
    - X-Frame-Options: 防止 clickjacking
    - Cache-Control: 防止快取敏感資料
    - Content-Security-Policy: 限制資源載入
    """
    # Rate limiting（僅針對非健康檢查的 POST 請求）
    if request.method == "POST":
        client_ip = request.client.host if request.client else "unknown"
        if not _rate_limiter.is_allowed(client_ip):
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "請求過於頻繁，請稍後再試。",
                    "retry_after_seconds": _RATE_LIMIT_WINDOW,
                },
            )

    response = await call_next(request)

    # 安全標頭
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Content-Security-Policy"] = "default-src 'none'"
    response.headers["X-API-Version"] = API_VERSION

    return response


# ============================================================
# Request/Response Models
# ============================================================

class RequirementRequest(BaseModel):
    """需求分析請求

    將用戶的自然語言描述轉換為結構化的公文需求。
    """

    user_input: str = Field(
        ...,
        description="用戶的自然語言需求描述",
        min_length=5,
        max_length=5000,
        json_schema_extra={
            "examples": ["幫我寫一份函，台北市環保局發給各學校，關於加強資源回收"]
        },
    )


class RequirementResponse(BaseModel):
    """需求分析回應"""

    success: bool
    requirement: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class WriterRequest(BaseModel):
    """草稿撰寫請求

    根據結構化需求（來自 requirement agent）撰寫公文草稿。
    """

    requirement: Dict[str, Any] = Field(
        ...,
        description="結構化的公文需求（來自 requirement agent）",
        json_schema_extra={
            "examples": [
                {
                    "doc_type": "函",
                    "sender": "臺北市政府環境保護局",
                    "receiver": "臺北市各級學校",
                    "subject": "函轉有關加強校園資源回收工作一案",
                }
            ]
        },
    )

    @field_validator("requirement")
    @classmethod
    def validate_requirement_fields(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """確保 requirement 包含最低必要欄位。"""
        required_keys = {"doc_type", "sender", "receiver", "subject"}
        missing = required_keys - set(v.keys())
        if missing:
            raise ValueError(
                f"requirement 缺少必要欄位: {', '.join(sorted(missing))}"
            )
        # 驗證必要欄位不為空字串
        for key in required_keys:
            val = v.get(key)
            if not val or (isinstance(val, str) and not val.strip()):
                raise ValueError(f"requirement 欄位 '{key}' 不可為空。")
        return v


class WriterResponse(BaseModel):
    """草稿撰寫回應"""

    success: bool
    draft: Optional[str] = None
    formatted_draft: Optional[str] = None
    error: Optional[str] = None


class ReviewRequest(BaseModel):
    """審查請求

    提交公文草稿進行單一 Agent 審查。
    """

    draft: str = Field(
        ..., description="要審查的公文草稿", min_length=10, max_length=50000
    )
    doc_type: Literal["函", "公告", "簽", "書函", "令", "開會通知單", "通知"] = Field(
        "函", description="公文類型"
    )


class SingleAgentReviewResponse(BaseModel):
    """單一 Agent 審查結果"""

    agent_name: str
    score: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    issues: List[Dict[str, Any]]
    has_errors: bool


class ReviewResponse(BaseModel):
    """審查回應"""

    success: bool
    agent_name: str
    result: Optional[SingleAgentReviewResponse] = None
    error: Optional[str] = None


class MeetingRequest(BaseModel):
    """開會（完整流程）請求

    一鍵完成：需求分析 -> 撰寫 -> 審查 -> 修改 -> 輸出。
    """

    user_input: str = Field(
        ..., description="用戶需求", min_length=5, max_length=5000
    )
    max_rounds: int = Field(3, description="最大修改輪數", ge=1, le=5)
    skip_review: bool = Field(False, description="是否跳過審查")
    output_docx: bool = Field(True, description="是否輸出 docx 檔案")
    output_filename: Optional[str] = Field(
        None,
        description="輸出檔名（不含路徑，僅允許 .docx 副檔名）",
        max_length=200,
    )

    @field_validator("output_filename")
    @classmethod
    def validate_output_filename(cls, v: Optional[str]) -> Optional[str]:
        """防止路徑遍歷與不合法的檔名。"""
        if v is None:
            return v
        # 禁止路徑分隔符號
        if "/" in v or "\\" in v or ".." in v:
            raise ValueError("檔名不可包含路徑分隔符號或 '..'。")
        return v


class MeetingResponse(BaseModel):
    """開會回應"""

    success: bool
    session_id: str
    requirement: Optional[Dict[str, Any]] = None
    final_draft: Optional[str] = None
    qa_report: Optional[Dict[str, Any]] = None
    output_path: Optional[str] = None
    rounds_used: int = 0
    error: Optional[str] = None


class ParallelReviewRequest(BaseModel):
    """並行審查請求（n8n Split 後用）

    同時執行多個審查 Agent，彙整結果。
    """

    draft: str = Field(
        ...,
        description="要審查的公文草稿",
        min_length=10,
        max_length=50000,
    )
    doc_type: Literal["函", "公告", "簽", "書函", "令", "開會通知單", "通知"] = Field(
        "函", description="公文類型"
    )
    agents: List[str] = Field(
        ["format", "style", "fact", "consistency", "compliance"],
        description="要執行的 Agent 列表（可用值：format, style, fact, consistency, compliance）",
    )

    @field_validator("agents")
    @classmethod
    def validate_agent_names(cls, v: List[str]) -> List[str]:
        """確保所有 Agent 名稱有效且列表不為空。"""
        if not v:
            raise ValueError("agents 列表不可為空。")
        if len(v) > 5:
            raise ValueError("agents 列表最多 5 個。")
        invalid = set(v) - _VALID_AGENT_NAMES
        if invalid:
            raise ValueError(
                f"無效的 Agent 名稱: {', '.join(sorted(invalid))}。"
                f"有效名稱: {', '.join(sorted(_VALID_AGENT_NAMES))}"
            )
        return list(dict.fromkeys(v))  # 去重但保持順序


class ParallelReviewResponse(BaseModel):
    """並行審查回應"""

    success: bool
    results: Dict[str, SingleAgentReviewResponse]
    aggregated_score: float = Field(..., ge=0.0, le=1.0)
    risk_summary: str
    error: Optional[str] = None


class RefineRequest(BaseModel):
    """修改請求

    根據審查意見修改公文草稿。
    """

    draft: str = Field(
        ...,
        description="要修改的公文草稿",
        min_length=10,
        max_length=50000,
    )
    feedback: List[Dict[str, Any]] = Field(
        ...,
        description="來自審查的問題列表",
        max_length=20,
    )


class RefineResponse(BaseModel):
    """修改回應"""

    success: bool
    refined_draft: Optional[str] = None
    error: Optional[str] = None


# ============================================================
# Helper Functions
# ============================================================

def review_result_to_dict(result: ReviewResult) -> SingleAgentReviewResponse:
    """將 ReviewResult 轉換為 API 回應格式。"""
    return SingleAgentReviewResponse(
        agent_name=result.agent_name,
        score=result.score,
        confidence=result.confidence,
        issues=[
            {
                "category": i.category,
                "severity": i.severity,
                "risk_level": i.risk_level,
                "location": i.location,
                "description": i.description,
                "suggestion": i.suggestion,
            }
            for i in result.issues
        ],
        has_errors=result.has_errors,
    )


def _sanitize_output_filename(filename: Optional[str], session_id: str) -> str:
    """清理並驗證輸出檔名，防止路徑遍歷攻擊。"""
    if not filename:
        return f"output_{session_id}.docx"
    basename = os.path.basename(filename)
    if not basename or basename.startswith("."):
        return f"output_{session_id}.docx"
    if not basename.endswith(".docx"):
        basename += ".docx"
    return basename


async def _run_in_executor(func: Any) -> Any:
    """將同步的阻塞函式包裝為在執行緒池中非同步執行，避免阻塞事件迴圈。"""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, func)


# ============================================================
# API Endpoints
# ============================================================

@app.get("/", tags=["健康檢查"])
async def root() -> Dict[str, str]:
    """基本健康檢查

    回傳伺服器狀態、API 版本號及時間戳記。
    """
    return {
        "status": "healthy",
        "service": "公文 AI Agent API",
        "version": API_VERSION,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/v1/health", tags=["健康檢查"])
async def health_check() -> Dict[str, str]:
    """詳細健康檢查

    回傳 LLM 提供者與模型資訊（不洩漏檔案路徑等敏感資訊）。
    """
    config = get_config()
    llm_config = config.get("llm", {})
    return {
        "status": "healthy",
        "llm_provider": llm_config.get("provider", "unknown"),
        "llm_model": llm_config.get("model", "unknown"),
        "kb_status": "available" if _kb is not None else "initializing",
    }


# ------------------------------------------------------------
# 1. Requirement Agent
# ------------------------------------------------------------

@app.post(
    "/api/v1/agent/requirement",
    response_model=RequirementResponse,
    tags=["需求分析"],
)
async def analyze_requirement(request: RequirementRequest) -> RequirementResponse:
    """需求分析 Agent

    將用戶的自然語言描述轉換為結構化的公文需求（doc_type, sender, receiver 等）。
    """
    try:
        agent = RequirementAgent(get_llm())
        # 在執行緒池中執行阻塞的 LLM 呼叫，避免阻塞事件迴圈
        requirement = await _run_in_executor(
            lambda: agent.analyze(request.user_input)
        )
        return RequirementResponse(
            success=True,
            requirement=requirement.model_dump(),
        )
    except Exception as e:
        logger.exception("需求分析失敗")
        return RequirementResponse(success=False, error=_sanitize_error(e))


# ------------------------------------------------------------
# 2. Writer Agent
# ------------------------------------------------------------

@app.post(
    "/api/v1/agent/writer",
    response_model=WriterResponse,
    tags=["草稿撰寫"],
)
async def write_draft(request: WriterRequest) -> WriterResponse:
    """撰寫 Agent

    根據結構化需求（來自 requirement agent）撰寫公文草稿，
    並套用標準模板格式。
    """
    try:
        requirement = PublicDocRequirement(**request.requirement)
        writer = WriterAgent(get_llm(), get_kb())

        # 將整個撰寫 + 模板套用流程放入執行緒池，
        # 避免模板解析（CPU 運算）阻塞事件迴圈
        def _write_and_format():
            raw = writer.write_draft(requirement)
            engine = TemplateEngine()
            sections = engine.parse_draft(raw)
            formatted = engine.apply_template(requirement, sections)
            return raw, formatted

        raw_draft, formatted_draft = await _run_in_executor(_write_and_format)

        return WriterResponse(
            success=True,
            draft=raw_draft,
            formatted_draft=formatted_draft,
        )
    except Exception as e:
        logger.exception("草稿撰寫失敗")
        return WriterResponse(success=False, error=_sanitize_error(e))


# ------------------------------------------------------------
# 3. Individual Review Agents
# ------------------------------------------------------------

@app.post(
    "/api/v1/agent/review/format",
    response_model=ReviewResponse,
    tags=["審查"],
)
async def review_format(request: ReviewRequest) -> ReviewResponse:
    """格式審查 Agent

    檢查公文是否符合標準格式規範（主旨、說明、辦法等段落結構）。
    """
    try:
        auditor = FormatAuditor(get_llm(), get_kb())
        # 在執行緒池中執行阻塞的 LLM 呼叫
        fmt_raw = await _run_in_executor(
            lambda: auditor.audit(request.draft, request.doc_type)
        )
        result = format_audit_to_review_result(fmt_raw)

        return ReviewResponse(
            success=True,
            agent_name="format",
            result=review_result_to_dict(result),
        )
    except Exception as e:
        logger.exception("格式審查失敗")
        return ReviewResponse(
            success=False, agent_name="format", error=_sanitize_error(e)
        )


@app.post(
    "/api/v1/agent/review/style",
    response_model=ReviewResponse,
    tags=["審查"],
)
async def review_style(request: ReviewRequest) -> ReviewResponse:
    """文風審查 Agent

    檢查公文用語是否正式、語氣是否得體。
    """
    try:
        checker = StyleChecker(get_llm())
        result = await _run_in_executor(lambda: checker.check(request.draft))
        return ReviewResponse(
            success=True,
            agent_name="style",
            result=review_result_to_dict(result),
        )
    except Exception as e:
        logger.exception("文風審查失敗")
        return ReviewResponse(
            success=False, agent_name="style", error=_sanitize_error(e)
        )


@app.post(
    "/api/v1/agent/review/fact",
    response_model=ReviewResponse,
    tags=["審查"],
)
async def review_fact(request: ReviewRequest) -> ReviewResponse:
    """事實審查 Agent

    檢查公文中的事實陳述、日期、法規引用是否正確。
    """
    try:
        checker = FactChecker(get_llm())
        result = await _run_in_executor(lambda: checker.check(request.draft))
        return ReviewResponse(
            success=True,
            agent_name="fact",
            result=review_result_to_dict(result),
        )
    except Exception as e:
        logger.exception("事實審查失敗")
        return ReviewResponse(
            success=False, agent_name="fact", error=_sanitize_error(e)
        )


@app.post(
    "/api/v1/agent/review/consistency",
    response_model=ReviewResponse,
    tags=["審查"],
)
async def review_consistency(request: ReviewRequest) -> ReviewResponse:
    """一致性審查 Agent

    檢查公文內部邏輯是否一致、前後文是否矛盾。
    """
    try:
        checker = ConsistencyChecker(get_llm())
        result = await _run_in_executor(lambda: checker.check(request.draft))
        return ReviewResponse(
            success=True,
            agent_name="consistency",
            result=review_result_to_dict(result),
        )
    except Exception as e:
        logger.exception("一致性審查失敗")
        return ReviewResponse(
            success=False, agent_name="consistency", error=_sanitize_error(e)
        )


@app.post(
    "/api/v1/agent/review/compliance",
    response_model=ReviewResponse,
    tags=["審查"],
)
async def review_compliance(request: ReviewRequest) -> ReviewResponse:
    """政策合規審查 Agent

    檢查公文內容是否符合相關法規與政策要求。
    """
    try:
        checker = ComplianceChecker(get_llm(), get_kb())
        result = await _run_in_executor(lambda: checker.check(request.draft))
        return ReviewResponse(
            success=True,
            agent_name="compliance",
            result=review_result_to_dict(result),
        )
    except Exception as e:
        logger.exception("合規審查失敗")
        return ReviewResponse(
            success=False, agent_name="compliance", error=_sanitize_error(e)
        )


# ------------------------------------------------------------
# 4. Parallel Review (All Agents)
# ------------------------------------------------------------

@app.post(
    "/api/v1/agent/review/parallel",
    response_model=ParallelReviewResponse,
    tags=["審查"],
)
async def parallel_review(
    request: ParallelReviewRequest,
) -> ParallelReviewResponse:
    """並行審查

    同時執行多個審查 Agent（格式、文風、事實、一致性、合規），
    彙整加權分數與風險等級。
    """
    try:
        results: Dict[str, SingleAgentReviewResponse] = {}
        llm = get_llm()
        kb = get_kb()

        # 各 Agent 執行函式映射
        agent_map = {
            "format": lambda: _run_format_audit(request.draft, request.doc_type, llm, kb),
            "style": lambda: StyleChecker(llm).check(request.draft),
            "fact": lambda: FactChecker(llm).check(request.draft),
            "consistency": lambda: ConsistencyChecker(llm).check(request.draft),
            "compliance": lambda: ComplianceChecker(llm, kb).check(request.draft),
        }

        # 使用 asyncio + 執行緒池並行執行
        loop = asyncio.get_running_loop()
        tasks: List[asyncio.Future] = []
        agent_names: List[str] = []

        for agent_name in request.agents:
            if agent_name in agent_map:
                agent_names.append(agent_name)
                tasks.append(
                    loop.run_in_executor(_executor, agent_map[agent_name])
                )

        review_results = await asyncio.gather(*tasks, return_exceptions=True)

        # 處理結果並計算加權分數
        weighted_score = 0.0
        total_weight = 0.0
        weighted_error_score = 0.0
        weighted_warning_score = 0.0

        for i, result in enumerate(review_results):
            agent_name = agent_names[i]

            if isinstance(result, Exception):
                # 僅記錄到伺服器日誌，不向用戶洩漏例外細節
                logger.error("Agent %s 執行失敗: %s", agent_name, result)
                results[agent_name] = SingleAgentReviewResponse(
                    agent_name=agent_name,
                    score=0.0,
                    confidence=0.0,
                    issues=[
                        {
                            "category": agent_name,
                            "severity": "error",
                            "risk_level": "high",
                            "location": "Agent 執行",
                            "description": f"{agent_name} Agent 執行失敗，請稍後再試。",
                            "suggestion": None,
                        }
                    ],
                    has_errors=True,
                )
            else:
                results[agent_name] = review_result_to_dict(result)

                # 使用共用常數計算加權分數
                weight = CATEGORY_WEIGHTS.get(agent_name, 1.0)
                weighted_score += result.score * weight * result.confidence
                total_weight += weight * result.confidence

                for issue in result.issues:
                    if issue.severity == "error":
                        weighted_error_score += weight
                    elif issue.severity == "warning":
                        weighted_warning_score += weight * WARNING_WEIGHT_FACTOR

        avg_score = weighted_score / total_weight if total_weight > 0 else 0.0

        # 使用共用函式判定風險等級（與 EditorInChief 一致）
        risk = assess_risk_level(
            weighted_error_score, weighted_warning_score, avg_score
        )

        return ParallelReviewResponse(
            success=True,
            results=results,
            aggregated_score=round(avg_score, 3),
            risk_summary=risk,
        )

    except Exception as e:
        logger.exception("並行審查失敗")
        return ParallelReviewResponse(
            success=False,
            results={},
            aggregated_score=0.0,
            risk_summary="Critical",
            error=_sanitize_error(e),
        )


def _run_format_audit(draft: str, doc_type: str, llm: Any, kb: Optional[KnowledgeBaseManager]) -> ReviewResult:
    """輔助函式：執行格式審查並轉換為 ReviewResult。"""
    auditor = FormatAuditor(llm, kb)
    fmt_raw = auditor.audit(draft, doc_type)
    return format_audit_to_review_result(fmt_raw)


# ------------------------------------------------------------
# 5. Editor (Refine)
# ------------------------------------------------------------

@app.post(
    "/api/v1/agent/refine",
    response_model=RefineResponse,
    tags=["修改"],
)
async def refine_draft(request: RefineRequest) -> RefineResponse:
    """Editor Agent

    根據審查 Agent 回傳的問題列表，自動修正公文草稿。
    """
    try:
        llm = get_llm()

        # 彙整回饋意見
        feedback_str = ""
        for item in request.feedback:
            agent = item.get("agent_name", "Unknown")
            for issue in item.get("issues", []):
                severity = issue.get("severity", "info").upper()
                desc = issue.get("description", "")
                suggestion = issue.get("suggestion", "")
                feedback_str += f"- [{agent}] {severity}: {desc}"
                if suggestion:
                    feedback_str += f" (Fix: {suggestion})"
                feedback_str += "\n"

        if not feedback_str:
            return RefineResponse(success=True, refined_draft=request.draft)

        # 截斷過長的回饋和草稿
        if len(feedback_str) > MAX_FEEDBACK_LENGTH:
            feedback_str = feedback_str[:MAX_FEEDBACK_LENGTH] + "\n...(回饋已截斷)"
        draft_for_prompt = request.draft
        if len(draft_for_prompt) > MAX_DRAFT_LENGTH:
            draft_for_prompt = draft_for_prompt[:MAX_DRAFT_LENGTH] + "\n...(草稿已截斷)"

        prompt = f"""You are the Editor-in-Chief.
Refine the following government document draft based on the feedback from review agents.

# Draft
{draft_for_prompt}

# Feedback to Address
{feedback_str}

# Instruction
Rewrite the draft to fix these issues while maintaining the standard format.
Return ONLY the new draft markdown.
"""

        # 在執行緒池中執行阻塞的 LLM 呼叫
        refined = await _run_in_executor(lambda: llm.generate(prompt))

        # 若 LLM 回傳空值，保留原始草稿
        if not refined or not refined.strip() or refined.startswith("Error"):
            return RefineResponse(success=True, refined_draft=request.draft)

        return RefineResponse(success=True, refined_draft=refined)

    except Exception as e:
        logger.exception("草稿修改失敗")
        return RefineResponse(success=False, error=_sanitize_error(e))


# ------------------------------------------------------------
# 6. Full Meeting (Orchestrated Flow)
# ------------------------------------------------------------

@app.post(
    "/api/v1/meeting",
    response_model=MeetingResponse,
    tags=["完整流程"],
)
async def run_meeting(request: MeetingRequest) -> MeetingResponse:
    """完整開會流程

    一鍵執行：需求分析 -> 撰寫 -> 審查 -> 修改 -> 輸出 DOCX。
    """
    session_id = str(uuid.uuid4())[:SESSION_ID_LENGTH]

    try:
        llm = get_llm()
        kb = get_kb()

        # 整個流程包含大量阻塞 LLM 呼叫，放入執行緒池執行
        def _meeting_workflow():
            # 步驟 1: 需求分析
            req_agent = RequirementAgent(llm)
            requirement = req_agent.analyze(request.user_input)

            # 步驟 2: 撰寫草稿
            writer = WriterAgent(llm, kb)
            raw_draft = writer.write_draft(requirement)

            # 步驟 3: 套用模板
            template_engine = TemplateEngine()
            sections = template_engine.parse_draft(raw_draft)
            formatted_draft = template_engine.apply_template(requirement, sections)

            final_draft = formatted_draft
            qa_report = None
            rounds_used = 0

            # 步驟 4: 審查迴圈
            if not request.skip_review:
                editor = EditorInChief(llm, kb)
                for round_num in range(request.max_rounds):
                    rounds_used = round_num + 1
                    final_draft, qa_report = editor.review_and_refine(
                        final_draft, requirement.doc_type
                    )
                    if qa_report.risk_summary in ["Safe", "Low"]:
                        break

            # 步驟 5: 匯出
            output_filename = None
            if request.output_docx:
                exporter = DocxExporter()
                filename = _sanitize_output_filename(
                    request.output_filename, session_id
                )
                exporter.export(
                    final_draft,
                    filename,
                    qa_report=qa_report.audit_log if qa_report else None,
                )
                # 僅回傳檔名，不回傳完整的伺服器檔案路徑（避免洩漏目錄結構）
                output_filename = filename

            return requirement, final_draft, qa_report, output_filename, rounds_used

        requirement, final_draft, qa_report, output_filename, rounds_used = (
            await _run_in_executor(_meeting_workflow)
        )

        return MeetingResponse(
            success=True,
            session_id=session_id,
            requirement=requirement.model_dump(),
            final_draft=final_draft,
            qa_report=qa_report.model_dump() if qa_report else None,
            output_path=output_filename,
            rounds_used=rounds_used,
        )

    except Exception as e:
        logger.exception("開會流程失敗")
        return MeetingResponse(
            success=False,
            session_id=session_id,
            error=_sanitize_error(e),
        )


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
