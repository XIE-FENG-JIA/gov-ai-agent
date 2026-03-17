"""
API Request/Response Pydantic 模型定義
=====================================

所有 API 端點的請求與回應資料模型集中定義於此。
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from src.core.models import DocTypeLiteral
from src.core.constants import MAX_USER_INPUT_LENGTH

# 有效的審查 Agent 名稱
_VALID_AGENT_NAMES = frozenset(["format", "style", "fact", "consistency", "compliance"])


# ============================================================
# 需求分析
# ============================================================

class RequirementRequest(BaseModel):
    """需求分析請求

    將用戶的自然語言描述轉換為結構化的公文需求。
    """

    user_input: str = Field(
        ...,
        description="用戶的自然語言需求描述",
        min_length=5,
        max_length=MAX_USER_INPUT_LENGTH,
        json_schema_extra={
            "examples": ["幫我寫一份函，台北市環保局發給各學校，關於加強資源回收"]
        },
    )

    @field_validator("user_input")
    @classmethod
    def validate_user_input_not_blank(cls, v: str) -> str:
        """攔截僅含空白字元的輸入（min_length 不檢查空白）。"""
        if not v.strip():
            raise ValueError("user_input 不可僅含空白字元。")
        return v


class RequirementResponse(BaseModel):
    """需求分析回應"""

    success: bool
    requirement: dict[str, Any] | None = None
    error: str | None = None
    error_code: str | None = None


# ============================================================
# 草稿撰寫
# ============================================================

class WriterRequest(BaseModel):
    """草稿撰寫請求

    根據結構化需求（來自 requirement agent）撰寫公文草稿。
    """

    requirement: dict[str, Any] = Field(
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
    def validate_requirement_fields(cls, v: dict[str, Any]) -> dict[str, Any]:
        """確保 requirement 包含最低必要欄位。"""
        required_keys = {"doc_type", "sender", "receiver", "subject"}
        missing = required_keys - set(v.keys())
        if missing:
            raise ValueError(
                f"requirement 缺少必要欄位: {', '.join(sorted(missing))}"
            )
        # 驗證必要欄位不為空字串
        _MAX_FIELD_LEN = 500
        for key in required_keys:
            val = v.get(key)
            if not val or (isinstance(val, str) and not val.strip()):
                raise ValueError(f"requirement 欄位 '{key}' 不可為空。")
            if isinstance(val, str) and len(val) > _MAX_FIELD_LEN:
                raise ValueError(
                    f"requirement 欄位 '{key}' 超過長度限制（{_MAX_FIELD_LEN} 字元）。"
                )
        return v


class WriterResponse(BaseModel):
    """草稿撰寫回應"""

    success: bool
    draft: str | None = None
    formatted_draft: str | None = None
    error: str | None = None
    error_code: str | None = None


# ============================================================
# 審查
# ============================================================

class ReviewRequest(BaseModel):
    """審查請求

    提交公文草稿進行單一 Agent 審查。
    """

    draft: str = Field(
        ..., description="要審查的公文草稿", min_length=10, max_length=50000
    )
    doc_type: DocTypeLiteral = Field(
        "函", description="公文類型"
    )

    @field_validator("draft")
    @classmethod
    def validate_draft_not_blank(cls, v: str) -> str:
        """攔截僅含空白字元的草稿。"""
        if not v.strip():
            raise ValueError("draft 不可僅含空白字元。")
        return v


class SingleAgentReviewResponse(BaseModel):
    """單一 Agent 審查結果"""

    agent_name: str
    score: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    issues: list[dict[str, Any]]
    has_errors: bool


class ReviewResponse(BaseModel):
    """審查回應"""

    success: bool
    agent_name: str
    result: SingleAgentReviewResponse | None = None
    error: str | None = None
    error_code: str | None = None


# ============================================================
# 完整流程（Meeting）
# ============================================================

class MeetingRequest(BaseModel):
    """開會（完整流程）請求

    一鍵完成：需求分析 -> 撰寫 -> 審查 -> 修改 -> 輸出。
    """

    user_input: str = Field(
        ..., description="用戶需求", min_length=5, max_length=MAX_USER_INPUT_LENGTH
    )
    max_rounds: int = Field(3, description="最大修改輪數（經典模式）", ge=1, le=5)
    skip_review: bool = Field(False, description="是否跳過審查")
    convergence: bool = Field(False, description="啟用分層收斂迭代（零錯誤制）")
    skip_info: bool = Field(False, description="分層收斂模式下跳過 info 層級")
    output_docx: bool = Field(True, description="是否輸出 docx 檔案")
    output_filename: str | None = Field(
        None,
        description="輸出檔名（不含路徑，僅允許 .docx 副檔名）",
        max_length=200,
    )

    @field_validator("user_input")
    @classmethod
    def validate_user_input_not_blank(cls, v: str) -> str:
        """攔截僅含空白字元的輸入。"""
        if not v.strip():
            raise ValueError("user_input 不可僅含空白字元。")
        return v

    @field_validator("output_filename")
    @classmethod
    def validate_output_filename(cls, v: str | None) -> str | None:
        """防止路徑遍歷、不合法字元與 Windows 保留名稱。"""
        if v is None:
            return v
        # 禁止空白字串
        if not v.strip():
            raise ValueError("檔名不可為空白。")
        # 禁止路徑分隔符號
        if "/" in v or "\\" in v or ".." in v:
            raise ValueError("檔名不可包含路徑分隔符號或 '..'。")
        # 禁止 Windows 非法字元
        _ILLEGAL_CHARS = '<>:"|?*'
        for ch in _ILLEGAL_CHARS:
            if ch in v:
                raise ValueError(
                    f"檔名不可包含非法字元: {_ILLEGAL_CHARS}"
                )
        # 禁止控制字元（ASCII 0-31）
        if any(ord(c) < 32 for c in v):
            raise ValueError("檔名不可包含控制字元。")
        # 禁止 Windows 保留名稱（不分大小寫）
        _RESERVED_NAMES = frozenset({
            "CON", "PRN", "AUX", "NUL",
            *(f"COM{i}" for i in range(1, 10)),
            *(f"LPT{i}" for i in range(1, 10)),
        })
        stem = v.rsplit(".", 1)[0].upper()
        if stem in _RESERVED_NAMES:
            raise ValueError(
                f"檔名不可使用 Windows 保留名稱: {stem}"
            )
        return v


class MeetingResponse(BaseModel):
    """開會回應"""

    success: bool
    session_id: str
    requirement: dict[str, Any] | None = None
    final_draft: str | None = None
    qa_report: dict[str, Any] | None = None
    output_path: str | None = None
    rounds_used: int = 0
    error: str | None = None
    error_code: str | None = None


# ============================================================
# 並行審查
# ============================================================

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
    doc_type: DocTypeLiteral = Field(
        "函", description="公文類型"
    )
    agents: list[str] = Field(
        ["format", "style", "fact", "consistency", "compliance"],
        description="要執行的 Agent 列表（可用值：format, style, fact, consistency, compliance）",
    )

    @field_validator("draft")
    @classmethod
    def validate_draft_not_blank(cls, v: str) -> str:
        """攔截僅含空白字元的草稿。"""
        if not v.strip():
            raise ValueError("draft 不可僅含空白字元。")
        return v

    @field_validator("agents")
    @classmethod
    def validate_agent_names(cls, v: list[str]) -> list[str]:
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
    results: dict[str, SingleAgentReviewResponse]
    aggregated_score: float = Field(..., ge=0.0, le=1.0)
    risk_summary: Literal["Critical", "High", "Moderate", "Low", "Safe"]
    error: str | None = None
    error_code: str | None = None


# ============================================================
# 修改（Refine）
# ============================================================

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
    feedback: list[dict[str, Any]] = Field(
        ...,
        description="來自審查的問題列表",
        max_length=20,
    )

    @field_validator("draft")
    @classmethod
    def validate_draft_not_blank(cls, v: str) -> str:
        """攔截僅含空白字元的草稿。"""
        if not v.strip():
            raise ValueError("draft 不可僅含空白字元。")
        return v

    @field_validator("feedback")
    @classmethod
    def validate_feedback(cls, v: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """確保 feedback 列表不為空，且每項至少有基本結構。"""
        if not v:
            raise ValueError("feedback 列表不可為空。")
        for i, item in enumerate(v):
            if "issues" not in item and "agent_name" not in item:
                raise ValueError(
                    f"feedback[{i}] 至少需要 'agent_name' 或 'issues' 欄位。"
                )
            if "issues" in item:
                issues = item["issues"]
                if not isinstance(issues, list):
                    raise ValueError(
                        f"feedback[{i}].issues 必須為列表。"
                    )
                for j, issue in enumerate(issues):
                    if not isinstance(issue, dict):
                        raise ValueError(
                            f"feedback[{i}].issues[{j}] 必須為字典。"
                        )
        return v


class RefineResponse(BaseModel):
    """修改回應"""

    success: bool
    refined_draft: str | None = None
    error: str | None = None
    error_code: str | None = None


# ============================================================
# 批次處理
# ============================================================

class BatchRequest(BaseModel):
    """批次處理請求"""

    items: list[MeetingRequest] = Field(
        ..., description="批次處理的多筆公文需求", min_length=1, max_length=50
    )


class BatchItemResult(BaseModel):
    """批次處理中單一項目的結果（含進度追蹤欄位）"""

    status: Literal["success", "error"] = Field(
        ..., description="該項目的處理狀態"
    )
    duration_ms: float = Field(
        0.0, description="該項目的處理時間（毫秒）"
    )
    error_message: str | None = Field(
        None, description="錯誤訊息（僅在 status=error 時有值）"
    )
    # 嵌入原有的 MeetingResponse 欄位
    session_id: str = ""
    success: bool = False
    requirement: dict[str, Any] | None = None
    final_draft: str | None = None
    qa_report: dict[str, Any] | None = None
    output_path: str | None = None
    rounds_used: int = 0
    error: str | None = None
    error_code: str | None = None


class BatchResponse(BaseModel):
    """批次處理回應（含進度追蹤）"""

    results: list[BatchItemResult]
    progress: dict[str, int] = Field(
        default_factory=dict,
        description="處理進度（completed, total）",
    )
    total_duration_ms: float = Field(
        0.0, description="整體處理時間（毫秒）"
    )
    summary: dict[str, Any] = Field(
        default_factory=dict,
        description="處理摘要（total, success, failed）",
    )


# ============================================================
# 知識庫搜尋
# ============================================================

class KBSearchRequest(BaseModel):
    """知識庫搜尋請求"""

    query: str = Field(
        ..., description="搜尋查詢", min_length=2, max_length=500
    )
    n_results: int = Field(5, description="回傳結果數", ge=1, le=50)
    source_level: Literal["A", "B"] | None = Field(None, description="來源等級篩選（A 或 B）")
    doc_type: str | None = Field(None, description="公文類型篩選")


class KBSearchResponse(BaseModel):
    """知識庫搜尋回應"""

    success: bool
    results: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None
    error_code: str | None = None
