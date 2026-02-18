from pydantic import BaseModel, Field
from typing import List, Optional, Literal

# 從 constants 模組匯入權重（保持向後相容的再匯出）
from src.core.constants import CATEGORY_WEIGHTS  # noqa: F401

class ReviewIssue(BaseModel):
    """審查 Agent 發現的單一問題。"""
    category: Literal["format", "style", "fact", "consistency", "compliance"]
    severity: Literal["error", "warning", "info"]
    risk_level: Literal["high", "medium", "low"] = "low"
    location: str = Field(..., description="問題所在位置")
    description: str = Field(..., description="問題描述")
    suggestion: Optional[str] = Field(None, description="建議修正方式")

class ReviewResult(BaseModel):
    """單一審查 Agent 的輸出結果。"""
    agent_name: str
    issues: List[ReviewIssue]
    score: float = Field(..., ge=0.0, le=1.0, description="品質分數（0-1）")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Agent 對自身審查的信心度")

    @property
    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)

class QAReport(BaseModel):
    """完整的品質保證報告。"""
    overall_score: float = Field(..., ge=0.0, le=1.0, description="加權總分（0-1）")
    risk_summary: Literal["Critical", "High", "Moderate", "Low", "Safe"]
    agent_results: List[ReviewResult]
    audit_log: str  # Markdown 格式的詳細審計日誌
