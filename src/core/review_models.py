from __future__ import annotations

import hashlib
from pydantic import BaseModel, Field
from typing import Literal

from src.core.constants import CONVERGENCE_MAX_FIX_ATTEMPTS, CONVERGENCE_STALE_ROUNDS

class ReviewIssue(BaseModel):
    """審查 Agent 發現的單一問題。"""
    category: Literal["format", "style", "fact", "consistency", "compliance"]
    severity: Literal["error", "warning", "info"]
    risk_level: Literal["high", "medium", "low"] = "low"
    location: str = Field(..., description="問題所在位置")
    description: str = Field(..., description="問題描述")
    suggestion: str | None = Field(None, description="建議修正方式")

class ReviewResult(BaseModel):
    """單一審查 Agent 的輸出結果。"""
    agent_name: str
    issues: list[ReviewIssue]
    score: float = Field(..., ge=0.0, le=1.0, description="品質分數（0-1）")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Agent 對自身審查的信心度")

    @property
    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)

def _issue_id(agent_name: str, issue: "ReviewIssue") -> str:
    """產生穩定的 issue 識別碼，用於追蹤同一問題的修正歷程。"""
    raw = f"{agent_name}|{issue.category}|{issue.location}|{issue.description}"
    return hashlib.md5(raw.encode()).hexdigest()


class IssueTracker:
    """追蹤每個 issue 的修正嘗試次數，判斷是否標記為 unfixable。"""

    def __init__(self, max_attempts: int = CONVERGENCE_MAX_FIX_ATTEMPTS) -> None:
        self.max_attempts = max_attempts
        self._attempts: dict[str, int] = {}
        self._unfixable: set[str] = set()

    def record_attempt(self, agent_name: str, issue: "ReviewIssue") -> None:
        iid = _issue_id(agent_name, issue)
        self._attempts[iid] = self._attempts.get(iid, 0) + 1
        if self._attempts[iid] >= self.max_attempts:
            self._unfixable.add(iid)

    def is_unfixable(self, agent_name: str, issue: "ReviewIssue") -> bool:
        return _issue_id(agent_name, issue) in self._unfixable

    def mark_resolved(self, agent_name: str, issue: "ReviewIssue") -> None:
        iid = _issue_id(agent_name, issue)
        self._attempts.pop(iid, None)
        self._unfixable.discard(iid)

    def get_fixable_issues(
        self, results: list["ReviewResult"], severity: str,
    ) -> list[tuple[str, "ReviewIssue"]]:
        """篩出指定嚴重度且非 unfixable 的 issues，回傳 (agent_name, issue) 清單。"""
        out: list[tuple[str, "ReviewIssue"]] = []
        for res in results:
            for issue in res.issues:
                if issue.severity == severity and not self.is_unfixable(res.agent_name, issue):
                    out.append((res.agent_name, issue))
        return out

    @property
    def unfixable_count(self) -> int:
        return len(self._unfixable)


class IterationState:
    """管理分層收斂迭代的狀態。"""

    def __init__(self, draft: str, phases: tuple[str, ...] = ("error", "warning", "info")) -> None:
        self.phases = phases
        self._phase_idx = 0
        self.round_number = 0
        self.phase_round = 0
        self.best_draft = draft
        self.best_score = -1.0  # 全域最佳分數（由 update_best_draft 維護，用於回滾保護）
        self._phase_best_score = -1.0  # Phase 內最佳分數（由 record_round 維護，用於 stale 檢測）
        self.issue_tracker = IssueTracker()
        self.history: list[dict] = []
        self._stale_count = 0

    @property
    def current_phase(self) -> str:
        return self.phases[self._phase_idx]

    @property
    def is_final_phase(self) -> bool:
        return self._phase_idx >= len(self.phases) - 1

    def advance_phase(self) -> bool:
        """進入下一 Phase。回傳 False 表示已無更多 Phase。"""
        if self.is_final_phase:
            return False
        self._phase_idx += 1
        self.phase_round = 0
        self._stale_count = 0
        self._phase_best_score = -1.0  # 新 Phase 重置 stale 基準
        return True

    def record_round(self, score: float, risk: str) -> None:
        self.round_number += 1
        self.phase_round += 1
        self.history.append({
            "round": self.round_number,
            "phase": self.current_phase,
            "phase_round": self.phase_round,
            "score": score,
            "risk": risk,
        })
        # Stale 檢測使用 Phase 內最佳分數，不受 update_best_draft 干擾
        if score > self._phase_best_score:
            self._phase_best_score = score
            self._stale_count = 0
        else:
            self._stale_count += 1

    def update_best_draft(self, draft: str, score: float) -> None:
        if score >= self.best_score:
            self.best_draft = draft
            self.best_score = score

    @property
    def is_stale(self) -> bool:
        return self._stale_count >= CONVERGENCE_STALE_ROUNDS


class QAReport(BaseModel):
    """完整的品質保證報告。"""
    overall_score: float = Field(..., ge=0.0, le=1.0, description="加權總分（0-1）")
    risk_summary: Literal["Critical", "High", "Moderate", "Low", "Safe"]
    agent_results: list[ReviewResult]
    audit_log: str  # Markdown 格式的詳細審計日誌
    rounds_used: int = Field(1, ge=1, description="實際執行的審查輪數")
    iteration_history: list[dict] = Field(
        default_factory=list,
        description="每輪的 score/risk 歷史，格式：[{round, score, risk}]",
    )
