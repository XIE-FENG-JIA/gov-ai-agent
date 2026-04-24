"""
API request models.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from src.core.constants import MAX_USER_INPUT_LENGTH
from src.core.models import DocTypeLiteral

_VALID_AGENT_NAMES = frozenset(["format", "style", "fact", "consistency", "compliance"])


class RequirementRequest(BaseModel):
    """需求分析請求。"""

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
    def validate_user_input_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("user_input 不可僅含空白字元。")
        return value


class WriterRequest(BaseModel):
    """草稿撰寫請求。"""

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
    def validate_requirement_fields(cls, value: dict[str, Any]) -> dict[str, Any]:
        required_keys = {"doc_type", "sender", "receiver", "subject"}
        missing = required_keys - set(value.keys())
        if missing:
            raise ValueError(f"requirement 缺少必要欄位: {', '.join(sorted(missing))}")

        max_field_len = 500
        for key in required_keys:
            field_value = value.get(key)
            if not field_value or (isinstance(field_value, str) and not field_value.strip()):
                raise ValueError(f"requirement 欄位 '{key}' 不可為空。")
            if isinstance(field_value, str) and len(field_value) > max_field_len:
                raise ValueError(f"requirement 欄位 '{key}' 超過長度限制（{max_field_len} 字元）。")
        return value


class ReviewRequest(BaseModel):
    """審查請求。"""

    draft: str = Field(..., description="要審查的公文草稿", min_length=10, max_length=50000)
    doc_type: DocTypeLiteral = Field("函", description="公文類型")

    @field_validator("draft")
    @classmethod
    def validate_draft_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("draft 不可僅含空白字元。")
        return value


class MeetingRequest(BaseModel):
    """開會（完整流程）請求。"""

    user_input: str = Field(..., description="用戶需求", min_length=5, max_length=MAX_USER_INPUT_LENGTH)
    max_rounds: int = Field(3, description="最大修改輪數（經典模式）", ge=1, le=5)
    skip_review: bool = Field(False, description="是否跳過審查")
    convergence: bool = Field(False, description="啟用分層收斂迭代（零錯誤制）")
    skip_info: bool = Field(False, description="分層收斂模式下跳過 info 層級")
    ralph_loop: bool = Field(False, description="啟用 Ralph Loop 極限品質模式（強制 convergence，持續迭代追求滿分）")
    ralph_max_cycles: int = Field(2, description="Ralph Loop 最大循環次數", ge=1, le=20)
    ralph_target_score: float = Field(1.0, description="Ralph Loop 目標分數（建議 1.0）", ge=0.0, le=1.0)
    output_docx: bool = Field(True, description="是否輸出 docx 檔案")
    output_filename: str | None = Field(
        None,
        description="輸出檔名（不含路徑，僅允許 .docx 副檔名）",
        max_length=200,
    )
    use_graph: bool = Field(True, description="使用 LangGraph 流程圖執行（True=新路徑, False=傳統路徑）")

    @field_validator("user_input")
    @classmethod
    def validate_user_input_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("user_input 不可僅含空白字元。")
        return value

    @field_validator("output_filename")
    @classmethod
    def validate_output_filename(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not value.strip():
            raise ValueError("檔名不可為空白。")
        if "/" in value or "\\" in value or ".." in value:
            raise ValueError("檔名不可包含路徑分隔符號或 '..'。")

        illegal_chars = '<>:"|?*'
        for char in illegal_chars:
            if char in value:
                raise ValueError(f"檔名不可包含非法字元: {illegal_chars}")
        if any(ord(char) < 32 for char in value):
            raise ValueError("檔名不可包含控制字元。")

        reserved_names = frozenset(
            {
                "CON",
                "PRN",
                "AUX",
                "NUL",
                *(f"COM{i}" for i in range(1, 10)),
                *(f"LPT{i}" for i in range(1, 10)),
            }
        )
        stem = value.rsplit(".", 1)[0].upper()
        if stem in reserved_names:
            raise ValueError(f"檔名不可使用 Windows 保留名稱: {stem}")
        return value


class ParallelReviewRequest(BaseModel):
    """並行審查請求。"""

    draft: str = Field(..., description="要審查的公文草稿", min_length=10, max_length=50000)
    doc_type: DocTypeLiteral = Field("函", description="公文類型")
    agents: list[str] = Field(
        ["format", "style", "fact", "consistency", "compliance"],
        description="要執行的 Agent 列表（可用值：format, style, fact, consistency, compliance）",
    )

    @field_validator("draft")
    @classmethod
    def validate_parallel_draft_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("draft 不可僅含空白字元。")
        return value

    @field_validator("agents")
    @classmethod
    def validate_agent_names(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("agents 列表不可為空。")
        if len(value) > 5:
            raise ValueError("agents 列表最多 5 個。")
        invalid = set(value) - _VALID_AGENT_NAMES
        if invalid:
            raise ValueError(
                f"無效的 Agent 名稱: {', '.join(sorted(invalid))}。"
                f"有效名稱: {', '.join(sorted(_VALID_AGENT_NAMES))}"
            )
        return list(dict.fromkeys(value))


class RefineRequest(BaseModel):
    """修改請求。"""

    draft: str = Field(..., description="要修改的公文草稿", min_length=10, max_length=50000)
    feedback: list[dict[str, Any]] = Field(..., description="來自審查的問題列表", max_length=20)

    @field_validator("draft")
    @classmethod
    def validate_refine_draft_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("draft 不可僅含空白字元。")
        return value

    @field_validator("feedback")
    @classmethod
    def validate_feedback(cls, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not value:
            raise ValueError("feedback 列表不可為空。")
        for index, item in enumerate(value):
            if "issues" not in item and "agent_name" not in item:
                raise ValueError(f"feedback[{index}] 至少需要 'agent_name' 或 'issues' 欄位。")
            if "issues" in item:
                issues = item["issues"]
                if not isinstance(issues, list):
                    raise ValueError(f"feedback[{index}].issues 必須為列表。")
                for issue_index, issue in enumerate(issues):
                    if not isinstance(issue, dict):
                        raise ValueError(f"feedback[{index}].issues[{issue_index}] 必須為字典。")
        return value


class BatchRequest(BaseModel):
    """批次處理請求。"""

    items: list[MeetingRequest] = Field(..., description="批次處理的多筆公文需求", min_length=1, max_length=50)


class KBSearchRequest(BaseModel):
    """知識庫搜尋請求。"""

    query: str = Field(..., description="搜尋查詢", min_length=2, max_length=500)
    n_results: int = Field(5, description="回傳結果數", ge=1, le=50)
    source_level: Literal["A", "B"] | None = Field(None, description="來源等級篩選（A 或 B）")
    doc_type: str | None = Field(None, description="公文類型篩選")

