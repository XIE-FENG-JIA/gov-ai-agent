"""
API response models.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class RequirementResponse(BaseModel):
    """需求分析回應。"""

    success: bool
    requirement: dict[str, Any] | None = None
    error: str | None = None
    error_code: str | None = None


class WriterResponse(BaseModel):
    """草稿撰寫回應。"""

    success: bool
    draft: str | None = None
    formatted_draft: str | None = None
    error: str | None = None
    error_code: str | None = None


class SingleAgentReviewResponse(BaseModel):
    """單一 Agent 審查結果。"""

    agent_name: str
    score: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    issues: list[dict[str, Any]]
    has_errors: bool


class ReviewResponse(BaseModel):
    """審查回應。"""

    success: bool
    agent_name: str
    result: SingleAgentReviewResponse | None = None
    error: str | None = None
    error_code: str | None = None


class MeetingResponse(BaseModel):
    """開會回應。"""

    success: bool
    session_id: str
    requirement: dict[str, Any] | None = None
    final_draft: str | None = None
    qa_report: dict[str, Any] | None = None
    output_path: str | None = None
    rounds_used: int = 0
    error: str | None = None
    error_code: str | None = None


class ParallelReviewResponse(BaseModel):
    """並行審查回應。"""

    success: bool
    results: dict[str, SingleAgentReviewResponse]
    aggregated_score: float = Field(..., ge=0.0, le=1.0)
    risk_summary: Literal["Critical", "High", "Moderate", "Low", "Safe"]
    error: str | None = None
    error_code: str | None = None


class RefineResponse(BaseModel):
    """修改回應。"""

    success: bool
    refined_draft: str | None = None
    error: str | None = None
    error_code: str | None = None


class BatchItemResult(BaseModel):
    """批次處理中單一項目的結果。"""

    status: Literal["success", "error"] = Field(..., description="該項目的處理狀態")
    duration_ms: float = Field(0.0, description="該項目的處理時間（毫秒）")
    error_message: str | None = Field(None, description="錯誤訊息（僅在 status=error 時有值）")
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
    """批次處理回應。"""

    results: list[BatchItemResult]
    progress: dict[str, int] = Field(default_factory=dict, description="處理進度（completed, total）")
    total_duration_ms: float = Field(0.0, description="整體處理時間（毫秒）")
    summary: dict[str, Any] = Field(default_factory=dict, description="處理摘要（total, success, failed）")


class KBSearchResponse(BaseModel):
    """知識庫搜尋回應。"""

    success: bool
    results: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None
    error_code: str | None = None

