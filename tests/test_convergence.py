"""分層收斂迭代機制的單元測試。"""
from unittest.mock import MagicMock, patch

from src.core.review_models import (
    IssueTracker,
    IterationState,
    ReviewIssue,
    ReviewResult,
)
from src.core.constants import CONVERGENCE_STALE_ROUNDS


# ============================================================
# IssueTracker 測試
# ============================================================

class TestIssueTracker:

    def _make_issue(self, desc: str = "測試問題", sev: str = "error") -> ReviewIssue:
        return ReviewIssue(
            category="format", severity=sev, location="主旨",
            description=desc, suggestion="修正建議",
        )

    def test_record_attempt_increments(self):
        tracker = IssueTracker()
        issue = self._make_issue()
        tracker.record_attempt("Format Auditor", issue)
        tracker.record_attempt("Format Auditor", issue)
        assert not tracker.is_unfixable("Format Auditor", issue)

    def test_marks_unfixable_after_max_attempts(self):
        tracker = IssueTracker(max_attempts=3)
        issue = self._make_issue()
        for _ in range(3):
            tracker.record_attempt("Format Auditor", issue)
        assert tracker.is_unfixable("Format Auditor", issue)

    def test_different_issues_tracked_separately(self):
        tracker = IssueTracker(max_attempts=2)
        issue_a = self._make_issue("問題 A")
        issue_b = self._make_issue("問題 B")
        tracker.record_attempt("Agent", issue_a)
        tracker.record_attempt("Agent", issue_a)
        assert tracker.is_unfixable("Agent", issue_a)
        assert not tracker.is_unfixable("Agent", issue_b)

    def test_mark_resolved_removes_from_tracker(self):
        tracker = IssueTracker(max_attempts=2)
        issue = self._make_issue()
        tracker.record_attempt("Agent", issue)
        tracker.record_attempt("Agent", issue)
        assert tracker.is_unfixable("Agent", issue)
        tracker.mark_resolved("Agent", issue)
        assert not tracker.is_unfixable("Agent", issue)

    def test_get_fixable_issues_excludes_unfixable(self):
        tracker = IssueTracker(max_attempts=1)
        issue_fix = self._make_issue("可修")
        issue_unfix = self._make_issue("不可修")
        tracker.record_attempt("A", issue_unfix)  # 1 次就 unfixable

        results = [
            ReviewResult(agent_name="A", issues=[issue_fix, issue_unfix], score=0.5),
        ]
        fixable = tracker.get_fixable_issues(results, "error")
        assert len(fixable) == 1
        assert fixable[0][1].description == "可修"

    def test_get_fixable_issues_filters_by_severity(self):
        tracker = IssueTracker()
        error_issue = self._make_issue("錯誤", "error")
        warn_issue = self._make_issue("警告", "warning")
        results = [
            ReviewResult(agent_name="A", issues=[error_issue, warn_issue], score=0.5),
        ]
        fixable = tracker.get_fixable_issues(results, "warning")
        assert len(fixable) == 1
        assert fixable[0][1].severity == "warning"

    def test_get_fixable_issues_filters_error_only(self):
        """篩選 error 時不應回傳 warning。"""
        tracker = IssueTracker()
        error_issue = self._make_issue("錯誤", "error")
        warn_issue = self._make_issue("警告", "warning")
        results = [
            ReviewResult(agent_name="A", issues=[error_issue, warn_issue], score=0.5),
        ]
        fixable = tracker.get_fixable_issues(results, "error")
        assert len(fixable) == 1
        assert fixable[0][1].severity == "error"

    def test_unfixable_count(self):
        tracker = IssueTracker(max_attempts=1)
        issue1 = self._make_issue("問題 1")
        issue2 = self._make_issue("問題 2")
        tracker.record_attempt("A", issue1)
        tracker.record_attempt("B", issue2)
        assert tracker.unfixable_count == 2


# ============================================================
# IterationState 測試
# ============================================================

class TestIterationState:

    def test_initial_state(self):
        state = IterationState("draft text")
        assert state.current_phase == "error"
        assert state.round_number == 0
        assert state.phase_round == 0
        assert state.best_score == -1.0
        assert not state.is_final_phase

    def test_record_round_increments(self):
        state = IterationState("draft")
        state.record_round(0.5, "High")
        assert state.round_number == 1
        assert state.phase_round == 1
        # record_round 不再更新 best_score，由 update_best_draft 維護
        assert state.best_score == -1.0

    def test_record_round_tracks_phase_best_for_stale(self):
        """record_round 使用 _phase_best_score 追蹤 stale，不影響全域 best_score。"""
        state = IterationState("draft")
        state.record_round(0.5, "High")
        state.record_round(0.8, "Moderate")
        assert state._phase_best_score == 0.8
        state.record_round(0.6, "Moderate")  # 下降
        assert state._phase_best_score == 0.8  # Phase best 不降
        # 全域 best_score 不受 record_round 影響
        assert state.best_score == -1.0

    def test_is_stale_after_no_improvement(self):
        state = IterationState("draft")
        state.record_round(0.8, "Moderate")
        assert not state.is_stale
        # 連續 CONVERGENCE_STALE_ROUNDS - 1 輪無改善：尚未 stale
        for _ in range(CONVERGENCE_STALE_ROUNDS - 1):
            state.record_round(0.7, "Moderate")
        if CONVERGENCE_STALE_ROUNDS > 1:
            assert not state.is_stale
        # 再一輪無改善：觸發 stale
        state.record_round(0.6, "Moderate")
        assert state.is_stale

    def test_is_stale_uses_constant(self):
        state = IterationState("draft")
        state.record_round(0.8, "Moderate")
        for _ in range(CONVERGENCE_STALE_ROUNDS):
            state.record_round(0.5, "Moderate")
        assert state.is_stale

    def test_advance_phase(self):
        state = IterationState("draft", phases=("error", "warning", "info"))
        assert state.current_phase == "error"
        assert state.advance_phase()
        assert state.current_phase == "warning"
        assert state.phase_round == 0  # phase_round 重置
        assert state.advance_phase()
        assert state.current_phase == "info"
        assert not state.advance_phase()  # 最後一個 Phase

    def test_advance_phase_resets_stale(self):
        state = IterationState("draft")
        state.record_round(0.8, "X")
        state.record_round(0.5, "X")
        state.record_round(0.4, "X")
        assert state.is_stale
        state.advance_phase()
        assert not state.is_stale

    def test_advance_phase_resets_phase_best_score(self):
        """Phase 轉換後，新 Phase 的 stale 基準應獨立於上一 Phase。"""
        state = IterationState("draft", phases=("error", "warning"))
        state.record_round(0.9, "X")  # Phase 內最佳 0.9
        state.advance_phase()
        # 新 Phase：0.5 < 0.9 在舊 phase_best 下會立即 stale，但重置後不會
        state.record_round(0.5, "X")
        assert not state.is_stale  # 新 Phase 第一輪不應 stale

    def test_best_score_only_updated_by_update_best_draft(self):
        """best_score 應由 update_best_draft 維護，不受 record_round 影響。"""
        state = IterationState("draft v0")
        state.record_round(0.8, "X")
        assert state.best_score == -1.0  # record_round 不更新 best_score
        state.update_best_draft("draft v1", 0.85)
        assert state.best_score == 0.85
        assert state.best_draft == "draft v1"
        state.record_round(0.9, "X")
        assert state.best_score == 0.85  # 仍由 update_best_draft 管理

    def test_is_final_phase(self):
        state = IterationState("draft", phases=("error",))
        assert state.is_final_phase

    def test_update_best_draft(self):
        state = IterationState("draft v0")
        state.record_round(0.5, "X")
        state.update_best_draft("draft v1", 0.7)
        assert state.best_draft == "draft v1"
        state.update_best_draft("draft v2", 0.3)  # 更差
        assert state.best_draft == "draft v1"

    def test_history_includes_phase(self):
        state = IterationState("draft")
        state.record_round(0.5, "High")
        assert state.history[0]["phase"] == "error"
        assert state.history[0]["phase_round"] == 1

    def test_two_phase_convergence(self):
        """跳過 info 的兩 Phase 流程。"""
        state = IterationState("draft", phases=("error", "warning"))
        assert state.current_phase == "error"
        state.advance_phase()
        assert state.current_phase == "warning"
        assert state.is_final_phase
        assert not state.advance_phase()


# ============================================================
# EditorInChief convergence 模式測試
# ============================================================

class TestEditorConvergenceMode:

    def _make_review_result(self, agent: str, issues: list[ReviewIssue], score: float = 0.8):
        return ReviewResult(agent_name=agent, issues=issues, score=score)

    def _make_issue(self, sev: str = "error"):
        return ReviewIssue(
            category="format", severity=sev, location="主旨",
            description="測試問題", suggestion="修正",
        )

    @patch("src.agents.editor.EditorInChief._execute_review")
    @patch("src.agents.editor.EditorInChief._execute_targeted_review")
    @patch("src.agents.editor.EditorInChief._layered_refine")
    def test_convergence_completes_when_no_issues(self, mock_refine, mock_targeted, mock_review):
        """無問題時應直接完成。"""
        mock_review.return_value = (
            [self._make_review_result("Format Auditor", [], 1.0)],
            [],
        )

        from src.agents.editor import EditorInChief
        editor = EditorInChief.__new__(EditorInChief)
        editor.llm = MagicMock()
        editor.format_auditor = MagicMock()
        editor.style_checker = MagicMock()
        editor.fact_checker = MagicMock()
        editor.consistency_checker = MagicMock()
        editor.compliance_checker = MagicMock()

        draft, report = editor._convergence_review("test draft", "函", ("error", "warning"))
        assert report.rounds_used >= 1
        mock_refine.assert_not_called()

    @patch("src.agents.editor.EditorInChief._execute_review")
    @patch("src.agents.editor.EditorInChief._execute_targeted_review")
    @patch("src.agents.editor.EditorInChief._layered_refine")
    def test_convergence_advances_phase(self, mock_refine, mock_targeted, mock_review):
        """error Phase 無問題後應進入 warning Phase。"""
        self._make_issue("error")
        warn_issue = self._make_issue("warning")

        # 第 1 輪：只有 warning，沒有 error → 應跳到 warning Phase
        mock_review.return_value = (
            [self._make_review_result("Style Checker", [warn_issue], 0.7)],
            [],
        )
        # 第 2 輪 targeted：warning 修好了
        mock_targeted.return_value = (
            [self._make_review_result("Style Checker", [], 0.95)],
            [],
        )
        mock_refine.return_value = "refined draft"

        from src.agents.editor import EditorInChief
        editor = EditorInChief.__new__(EditorInChief)
        editor.llm = MagicMock()
        editor.format_auditor = MagicMock()
        editor.style_checker = MagicMock()
        editor.fact_checker = MagicMock()
        editor.consistency_checker = MagicMock()
        editor.compliance_checker = MagicMock()

        draft, report = editor._convergence_review("test draft", "函", ("error", "warning"))
        assert report.rounds_used >= 2

    @patch("src.agents.editor.EditorInChief._execute_review")
    def test_convergence_stops_when_all_agents_fail(self, mock_review):
        """全部 Agent 失敗時應停止。"""
        mock_review.return_value = (
            [ReviewResult(agent_name="A", issues=[], score=0.0, confidence=0.0)],
            [],
        )

        from src.agents.editor import EditorInChief
        editor = EditorInChief.__new__(EditorInChief)
        editor.llm = MagicMock()
        editor.format_auditor = MagicMock()
        editor.style_checker = MagicMock()
        editor.fact_checker = MagicMock()
        editor.consistency_checker = MagicMock()
        editor.compliance_checker = MagicMock()

        draft, report = editor._convergence_review("test", "函", ("error",))
        assert report.rounds_used <= 2

    @patch("src.agents.editor.EditorInChief._execute_review")
    @patch("src.agents.editor.EditorInChief._execute_targeted_review")
    @patch("src.agents.editor.EditorInChief._layered_refine")
    def test_convergence_stale_advances_phase(self, mock_refine, mock_targeted, mock_review):
        """連續無改善時應強制推進 Phase。"""
        issue = self._make_issue("error")

        # 每輪都回傳相同分數
        mock_review.return_value = (
            [self._make_review_result("Format Auditor", [issue], 0.5)],
            [],
        )
        mock_targeted.return_value = (
            [self._make_review_result("Format Auditor", [issue], 0.5)],
            [],
        )
        mock_refine.return_value = "same draft"

        from src.agents.editor import EditorInChief
        editor = EditorInChief.__new__(EditorInChief)
        editor.llm = MagicMock()
        editor.format_auditor = MagicMock()
        editor.style_checker = MagicMock()
        editor.fact_checker = MagicMock()
        editor.consistency_checker = MagicMock()
        editor.compliance_checker = MagicMock()

        draft, report = editor._convergence_review("test", "函", ("error", "warning"))
        # 應在 error Phase 卡住後進入 warning Phase
        assert report.rounds_used >= 2


class TestShowRounds:
    """show_rounds=True 時應呼叫 _print_round_draft。"""

    def _make_review_result(self, agent: str, issues: list, score: float = 0.8):
        return ReviewResult(agent_name=agent, issues=issues, score=score)

    def _make_issue(self, sev: str = "error"):
        return ReviewIssue(
            category="format", severity=sev, location="主旨",
            description="測試問題", suggestion="修正",
        )

    @patch("src.agents.editor.EditorInChief._print_round_draft")
    @patch("src.agents.editor.EditorInChief._execute_review")
    @patch("src.agents.editor.EditorInChief._execute_targeted_review")
    @patch("src.agents.editor.EditorInChief._layered_refine")
    def test_convergence_show_rounds_calls_print(
        self, mock_refine, mock_targeted, mock_review, mock_print_round,
    ):
        """show_rounds=True 時，修正成功後應呼叫 _print_round_draft。"""
        issue = self._make_issue("error")
        # 第 1 輪：有 error
        mock_review.return_value = (
            [self._make_review_result("Format Auditor", [issue], 0.5)],
            [],
        )
        # targeted 驗證：修正後分數上升，無問題
        mock_targeted.return_value = (
            [self._make_review_result("Format Auditor", [], 0.95)],
            [],
        )
        mock_refine.return_value = "refined draft"

        from src.agents.editor import EditorInChief
        editor = EditorInChief.__new__(EditorInChief)
        editor.llm = MagicMock()
        editor.format_auditor = MagicMock()
        editor.style_checker = MagicMock()
        editor.fact_checker = MagicMock()
        editor.consistency_checker = MagicMock()
        editor.compliance_checker = MagicMock()

        editor._convergence_review("test draft", "函", ("error",), show_rounds=True)
        mock_print_round.assert_called()

    @patch("src.agents.editor.EditorInChief._print_round_draft")
    @patch("src.agents.editor.EditorInChief._execute_review")
    @patch("src.agents.editor.EditorInChief._execute_targeted_review")
    @patch("src.agents.editor.EditorInChief._layered_refine")
    def test_convergence_no_show_rounds_no_print(
        self, mock_refine, mock_targeted, mock_review, mock_print_round,
    ):
        """show_rounds=False（預設）時不應呼叫 _print_round_draft。"""
        issue = self._make_issue("error")
        mock_review.return_value = (
            [self._make_review_result("Format Auditor", [issue], 0.5)],
            [],
        )
        mock_targeted.return_value = (
            [self._make_review_result("Format Auditor", [], 0.95)],
            [],
        )
        mock_refine.return_value = "refined draft"

        from src.agents.editor import EditorInChief
        editor = EditorInChief.__new__(EditorInChief)
        editor.llm = MagicMock()
        editor.format_auditor = MagicMock()
        editor.style_checker = MagicMock()
        editor.fact_checker = MagicMock()
        editor.consistency_checker = MagicMock()
        editor.compliance_checker = MagicMock()

        editor._convergence_review("test draft", "函", ("error",), show_rounds=False)
        mock_print_round.assert_not_called()

    @patch("src.agents.editor.EditorInChief._print_round_draft")
    @patch("src.agents.editor.EditorInChief._execute_review")
    @patch("src.agents.editor.EditorInChief._auto_refine")
    def test_iterative_show_rounds_calls_print(
        self, mock_refine, mock_review, mock_print_round,
    ):
        """_iterative_review 中 show_rounds=True 時應呼叫 _print_round_draft。"""
        issue = self._make_issue("error")
        # 第 1 輪：分數差，觸發修正
        results_bad = [self._make_review_result("Format Auditor", [issue], 0.4)]
        # 第 2 輪：分數好，停止
        results_good = [self._make_review_result("Format Auditor", [], 1.0)]

        mock_review.side_effect = [
            (results_bad, []),
            (results_good, []),
        ]
        mock_refine.return_value = "refined draft"

        from src.agents.editor import EditorInChief
        editor = EditorInChief.__new__(EditorInChief)
        editor.llm = MagicMock()
        editor.format_auditor = MagicMock()
        editor.style_checker = MagicMock()
        editor.fact_checker = MagicMock()
        editor.consistency_checker = MagicMock()
        editor.compliance_checker = MagicMock()

        editor._iterative_review("test draft", "函", 3, show_rounds=True)
        mock_print_round.assert_called()


class TestEditorTargetedReview:

    def test_no_rerun_when_no_issues(self):
        """上一輪沒有指定 phase 的問題時，應直接回傳舊結果。"""
        from src.agents.editor import EditorInChief

        editor = EditorInChief.__new__(EditorInChief)
        editor.format_auditor = MagicMock()
        editor.style_checker = MagicMock()
        editor.fact_checker = MagicMock()
        editor.consistency_checker = MagicMock()
        editor.compliance_checker = MagicMock()

        prev = [ReviewResult(agent_name="Format Auditor", issues=[], score=0.9)]
        results, timed_out = editor._execute_targeted_review("draft", "函", prev, "error")
        assert results == prev
        assert timed_out == []
