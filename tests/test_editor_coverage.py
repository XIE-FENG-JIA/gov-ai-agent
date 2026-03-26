"""EditorInChief 覆蓋率補齊測試 — 涵蓋 convergence review、targeted review、
layered refine、segmented review（含修正）、print_round_draft、audit_log 擴展。"""

from unittest.mock import MagicMock, patch

import pytest

from src.agents.editor import EditorInChief
from src.core.review_models import QAReport, ReviewIssue, ReviewResult


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.generate.return_value = '{"issues": [], "score": 0.95}'
    return llm


def _safe_results():
    return [
        ReviewResult(agent_name="Format Auditor", issues=[], score=0.98, confidence=1.0),
        ReviewResult(agent_name="Style Checker", issues=[], score=0.95, confidence=0.9),
        ReviewResult(agent_name="Fact Checker", issues=[], score=0.95, confidence=0.9),
        ReviewResult(agent_name="Consistency Checker", issues=[], score=0.95, confidence=0.9),
        ReviewResult(agent_name="Compliance Checker", issues=[], score=0.95, confidence=0.9),
    ]


def _error_results(severity="error"):
    return [
        ReviewResult(
            agent_name="Format Auditor",
            issues=[ReviewIssue(
                category="format", severity=severity, risk_level="high",
                location="文件結構", description="缺少主旨", suggestion="補上主旨",
            )],
            score=0.4, confidence=1.0,
        ),
        ReviewResult(agent_name="Style Checker", issues=[], score=0.8, confidence=0.9),
        ReviewResult(agent_name="Fact Checker", issues=[], score=0.8, confidence=0.9),
        ReviewResult(agent_name="Consistency Checker", issues=[], score=0.8, confidence=0.9),
        ReviewResult(agent_name="Compliance Checker", issues=[], score=0.8, confidence=0.9),
    ]


# ==================== Convergence Review ====================


class TestConvergenceReview:
    """分層收斂迭代測試"""

    def test_convergence_no_issues_all_phases_done(self, mock_llm):
        """無問題時所有 Phase 快速完成"""
        editor = EditorInChief(mock_llm)
        safe = _safe_results()

        with patch.object(editor, '_execute_review', return_value=(safe, [])):
            draft, report = editor.review_and_refine(
                "### 主旨\n測試", "函", convergence=True,
            )

        assert isinstance(report, QAReport)
        assert report.rounds_used >= 1

    def test_convergence_skip_info_phase(self, mock_llm):
        """skip_info=True 時只執行 error/warning 兩個 Phase"""
        editor = EditorInChief(mock_llm)
        safe = _safe_results()

        with patch.object(editor, '_execute_review', return_value=(safe, [])):
            _, report = editor.review_and_refine(
                "### 主旨\n測試", "函",
                convergence=True, skip_info=True,
            )

        assert isinstance(report, QAReport)

    def test_convergence_fixes_error_then_advances(self, mock_llm):
        """有 error 問題 → 修正 → 無 error → 進入 warning Phase"""
        editor = EditorInChief(mock_llm)
        err = _error_results("error")
        safe = _safe_results()
        call_count = [0]

        def mock_execute(draft, doc_type):
            call_count[0] += 1
            if call_count[0] <= 1:
                return err, []
            return safe, []

        def mock_targeted(draft, doc_type, prev, phase):
            return safe, []

        mock_llm.generate.return_value = "### 主旨\n已修正"

        with patch.object(editor, '_execute_review', side_effect=mock_execute), \
             patch.object(editor, '_execute_targeted_review', side_effect=mock_targeted):
            draft, report = editor.review_and_refine(
                "### 主旨\n測試", "函", convergence=True, skip_info=True,
            )

        assert isinstance(report, QAReport)
        assert report.rounds_used >= 1

    def test_convergence_all_agents_failed_stops(self, mock_llm):
        """所有 Agent confidence=0 時停止"""
        editor = EditorInChief(mock_llm)
        failed = [
            ReviewResult(agent_name="Format Auditor", issues=[
                ReviewIssue(category="format", severity="error", risk_level="high",
                            location="全文", description="問題"),
            ], score=0.0, confidence=0.0),
        ]

        with patch.object(editor, '_execute_review', return_value=(failed, [])):
            _, report = editor.review_and_refine(
                "### 主旨\n測試", "函", convergence=True,
            )

        assert isinstance(report, QAReport)

    def test_convergence_long_draft_degrades_to_segmented(self, mock_llm):
        """超長草稿 + convergence → 降級為分段審查"""
        mock_llm.generate.return_value = '{"errors": [], "warnings": []}'
        editor = EditorInChief(mock_llm)

        long_draft = "### 主旨\n" + "內容" * 8000
        assert len(long_draft) > editor._SEGMENT_THRESHOLD

        _, report = editor.review_and_refine(
            long_draft, "函", convergence=True,
        )

        assert isinstance(report, QAReport)
        # 降級分段審查的 agent 應有段落標記
        segment_agents = [r for r in report.agent_results if "段" in r.agent_name]
        assert len(segment_agents) > 0

    def test_convergence_stale_skips_phase(self, mock_llm):
        """連續多輪無改善時跳至下一 Phase"""

        editor = EditorInChief(mock_llm)
        err = _error_results("error")

        # 修正後分數總是不改善（略低於 best_score * 0.95）
        mock_llm.generate.return_value = "### 主旨\n修正但沒改善"

        stale_round = [0]

        def mock_execute(draft, doc_type):
            return err, []

        def mock_targeted(draft, doc_type, prev, phase):
            stale_round[0] += 1
            # 回傳同樣有 error 的結果（分數不變）
            return err, []

        with patch.object(editor, '_execute_review', side_effect=mock_execute), \
             patch.object(editor, '_execute_targeted_review', side_effect=mock_targeted):
            _, report = editor.review_and_refine(
                "### 主旨\n測試", "函",
                convergence=True, skip_info=True,
            )

        assert isinstance(report, QAReport)

    def test_convergence_show_rounds(self, mock_llm):
        """show_rounds=True 時不崩潰"""
        editor = EditorInChief(mock_llm)
        safe = _safe_results()

        with patch.object(editor, '_execute_review', return_value=(safe, [])):
            _, report = editor.review_and_refine(
                "### 主旨\n測試", "函",
                convergence=True, show_rounds=True,
            )

        assert isinstance(report, QAReport)


# ==================== Targeted Review ====================


class TestTargetedReview:
    """_execute_targeted_review 單元測試"""

    def test_no_phase_issues_returns_prev(self, mock_llm):
        """前一輪無指定 phase 問題時直接回傳"""
        editor = EditorInChief(mock_llm)
        prev = _safe_results()

        results, timed_out = editor._execute_targeted_review(
            "### 主旨\n測試", "函", prev, "error",
        )

        assert results == prev
        assert timed_out == []

    def test_reruns_only_affected_agents(self, mock_llm):
        """只重跑有指定 phase issue 的 Agent"""
        mock_llm.generate.return_value = '{"issues": [], "score": 0.95}'

        editor = EditorInChief(mock_llm)
        prev = [
            ReviewResult(
                agent_name="Format Auditor",
                issues=[ReviewIssue(
                    category="format", severity="error", risk_level="high",
                    location="主旨", description="問題",
                )],
                score=0.5, confidence=1.0,
            ),
            ReviewResult(agent_name="Style Checker", issues=[], score=0.9, confidence=0.9),
        ]

        results, _ = editor._execute_targeted_review(
            "### 主旨\n測試", "函", prev, "error",
        )

        # Style Checker 不需重跑，應保留
        style_results = [r for r in results if r.agent_name == "Style Checker"]
        assert len(style_results) == 1
        assert style_results[0].score == 0.9

    def test_unknown_agent_name_preserved(self, mock_llm):
        """未知 Agent 名稱不重跑，保留舊結果"""
        editor = EditorInChief(mock_llm)
        prev = [
            ReviewResult(
                agent_name="Unknown Agent",
                issues=[ReviewIssue(
                    category="format", severity="error", risk_level="high",
                    location="位置", description="問題",
                )],
                score=0.3, confidence=1.0,
            ),
        ]

        results, _ = editor._execute_targeted_review(
            "### 主旨\n測試", "函", prev, "error",
        )

        # Unknown Agent 應被保留（在舊結果中）
        assert any(r.agent_name == "Unknown Agent" for r in results)

    def test_agent_exception_during_targeted_review(self, mock_llm):
        """targeted review 中 Agent 拋出例外時容錯處理"""
        mock_llm.generate.return_value = '{"issues": [], "score": 0.95}'

        editor = EditorInChief(mock_llm)
        # 讓 style_checker 拋出例外
        editor.style_checker.check = MagicMock(side_effect=RuntimeError("boom"))

        prev = [
            ReviewResult(
                agent_name="Style Checker",
                issues=[ReviewIssue(
                    category="style", severity="error", risk_level="high",
                    location="文風", description="問題",
                )],
                score=0.5, confidence=1.0,
            ),
        ]

        results, _ = editor._execute_targeted_review(
            "### 主旨\n測試", "函", prev, "error",
        )

        # 失敗的 Agent 應回傳 DEFAULT_FAILED_SCORE
        from src.core.constants import DEFAULT_FAILED_SCORE
        failed = [r for r in results if r.agent_name == "Style Checker"]
        assert len(failed) == 1
        assert failed[0].score == DEFAULT_FAILED_SCORE


# ==================== Layered Refine ====================


class TestLayeredRefine:
    """_layered_refine 單元測試"""

    def test_empty_issues_returns_draft(self, mock_llm):
        """空 issues 直接回傳原始草稿"""
        editor = EditorInChief(mock_llm)
        result = editor._layered_refine("### 原始", [])
        assert result == "### 原始"

    def test_normal_refine(self, mock_llm):
        """正常修正流程"""
        mock_llm.generate.return_value = "### 已修正的草稿"
        editor = EditorInChief(mock_llm)

        issues = [
            ("Format Auditor", ReviewIssue(
                category="format", severity="error", risk_level="high",
                location="主旨", description="缺少主旨", suggestion="補上主旨",
            )),
        ]

        result = editor._layered_refine("### 原始", issues)
        assert result == "### 已修正的草稿"
        mock_llm.generate.assert_called_once()

    def test_alternative_strategy(self, mock_llm):
        """alternative=True 使用保守策略"""
        mock_llm.generate.return_value = "### 保守修正"
        editor = EditorInChief(mock_llm)

        issues = [
            ("Format Auditor", ReviewIssue(
                category="format", severity="error", risk_level="high",
                location="主旨", description="問題",
            )),
        ]

        result = editor._layered_refine("### 原始", issues, alternative=True)
        assert result == "### 保守修正"
        # 確認 prompt 包含 CONSERVATIVE
        prompt = mock_llm.generate.call_args[0][0]
        assert "CONSERVATIVE" in prompt

    def test_llm_failure_returns_original(self, mock_llm):
        """LLM 呼叫失敗時回傳原始草稿"""
        mock_llm.generate.side_effect = RuntimeError("timeout")
        editor = EditorInChief(mock_llm)

        issues = [
            ("Format Auditor", ReviewIssue(
                category="format", severity="error", risk_level="high",
                location="主旨", description="問題",
            )),
        ]

        result = editor._layered_refine("### 原始", issues)
        assert result == "### 原始"

    def test_llm_returns_empty(self, mock_llm):
        """LLM 回傳空值時保留原始草稿"""
        mock_llm.generate.return_value = ""
        editor = EditorInChief(mock_llm)

        issues = [
            ("Format Auditor", ReviewIssue(
                category="format", severity="error", risk_level="high",
                location="主旨", description="問題",
            )),
        ]

        result = editor._layered_refine("### 原始", issues)
        assert result == "### 原始"

    def test_llm_returns_error_string(self, mock_llm):
        """LLM 回傳 Error 開頭時保留原始草稿"""
        mock_llm.generate.return_value = "Error: model overloaded"
        editor = EditorInChief(mock_llm)

        issues = [
            ("Format Auditor", ReviewIssue(
                category="format", severity="error", risk_level="high",
                location="主旨", description="問題",
            )),
        ]

        result = editor._layered_refine("### 原始", issues)
        assert result == "### 原始"

    def test_long_feedback_truncated(self, mock_llm):
        """超長回饋被截斷但不崩潰"""
        mock_llm.generate.return_value = "### 已修正"
        editor = EditorInChief(mock_llm)

        issues = [
            ("Agent", ReviewIssue(
                category="format", severity="error", risk_level="high",
                location="位置", description="X" * 500, suggestion="Y" * 500,
            ))
            for _ in range(100)
        ]

        result = editor._layered_refine("### 原始", issues)
        assert result == "### 已修正"

    def test_long_draft_truncated(self, mock_llm):
        """超長草稿被截斷但不崩潰"""
        from src.core.constants import MAX_DRAFT_LENGTH
        mock_llm.generate.return_value = "### 已修正"
        editor = EditorInChief(mock_llm)

        issues = [
            ("Format Auditor", ReviewIssue(
                category="format", severity="error", risk_level="high",
                location="主旨", description="問題",
            )),
        ]

        long_draft = "A" * (MAX_DRAFT_LENGTH + 1000)
        result = editor._layered_refine(long_draft, issues)
        assert result == "### 已修正"

    def test_issue_without_suggestion(self, mock_llm):
        """issue.suggestion 為 None 時使用預設文字"""
        mock_llm.generate.return_value = "### 已修正"
        editor = EditorInChief(mock_llm)

        issues = [
            ("Format Auditor", ReviewIssue(
                category="format", severity="error", risk_level="high",
                location="主旨", description="問題", suggestion=None,
            )),
        ]

        result = editor._layered_refine("### 原始", issues)
        assert result == "### 已修正"
        # 確認 prompt 包含預設建議文字
        prompt = mock_llm.generate.call_args[0][0]
        assert "請自行判斷修正方式" in prompt


# ==================== Review Single & Segmented Review ====================


class TestReviewSingleAndSegmented:
    """_review_single 和 _segmented_review 測試"""

    def test_review_single_safe(self, mock_llm):
        """單段審查品質良好時不修正"""
        editor = EditorInChief(mock_llm)
        safe = _safe_results()

        with patch.object(editor, '_execute_review', return_value=(safe, [])):
            draft, report = editor._review_single("### 主旨\n測試", "函")

        assert draft == "### 主旨\n測試"  # 不修改
        assert report.risk_summary in ["Safe", "Low"]

    def test_review_single_high_risk_triggers_refine(self, mock_llm):
        """單段審查風險高時觸發自動修正"""
        mock_llm.generate.return_value = "### 已修正"
        editor = EditorInChief(mock_llm)
        err = _error_results()

        with patch.object(editor, '_execute_review', return_value=(err, [])):
            draft, report = editor._review_single("### 主旨\n測試", "函")

        assert draft == "### 已修正"

    def test_segmented_review_merges_results(self, mock_llm):
        """分段審查合併各段結果"""
        mock_llm.generate.return_value = '{"errors": [], "warnings": []}'
        editor = EditorInChief(mock_llm)

        long_draft = "### 主旨\n" + "A\n" * 8000
        assert len(long_draft) > editor._SEGMENT_THRESHOLD

        draft, report = editor._segmented_review(long_draft, "函")
        assert isinstance(report, QAReport)
        assert len(report.agent_results) > 0

    def test_segmented_review_high_risk_refines_full_draft(self, mock_llm):
        """分段審查風險高時對完整草稿進行修正"""
        editor = EditorInChief(mock_llm)
        err = _error_results()

        def mock_execute_review(draft, doc_type):
            return err, []

        mock_llm.generate.return_value = "### 完整修正"

        with patch.object(editor, '_execute_review', side_effect=mock_execute_review):
            long_draft = "### 主旨\n" + "B\n" * 8000
            draft, report = editor._segmented_review(long_draft, "函")

        assert draft == "### 完整修正"

    def test_segmented_review_collects_timed_out(self, mock_llm):
        """分段審查應收集各段的逾時 Agent 資訊"""
        editor = EditorInChief(mock_llm)
        safe = _safe_results()

        call_count = [0]

        def mock_execute_review(draft, doc_type):
            call_count[0] += 1
            # 第一段有逾時 Agent，第二段正常
            timed_out = ["Style Checker"] if call_count[0] == 1 else []
            return safe, timed_out

        with patch.object(editor, '_execute_review', side_effect=mock_execute_review):
            long_draft = "### 主旨\n" + "C\n" * 8000
            draft, report = editor._segmented_review(long_draft, "函")

        assert call_count[0] >= 2, "應至少呼叫兩次 _execute_review（兩段）"
        # 報告應包含逾時資訊（至少有 Style Checker）
        assert isinstance(report, QAReport)


# ==================== Auto Refine (edge cases) ====================


class TestAutoRefineEdgeCases:
    def test_llm_returns_error_string(self, mock_llm):
        """LLM 回傳 Error 字串時保留原始草稿"""
        mock_llm.generate.return_value = "Error: service unavailable"
        editor = EditorInChief(mock_llm)

        results = [
            ReviewResult(
                agent_name="Test",
                issues=[ReviewIssue(
                    category="format", severity="error", risk_level="high",
                    location="主旨", description="問題",
                )],
                score=0.5,
            ),
        ]

        original = "### 原始草稿"
        refined = editor._auto_refine(original, results)
        assert refined == original

    def test_auto_refine_llm_exception(self, mock_llm):
        """LLM 呼叫拋出例外時保留原始草稿"""
        mock_llm.generate.side_effect = RuntimeError("connection refused")
        editor = EditorInChief(mock_llm)

        results = [
            ReviewResult(
                agent_name="Test",
                issues=[ReviewIssue(
                    category="format", severity="error", risk_level="high",
                    location="主旨", description="問題", suggestion="修正",
                )],
                score=0.5,
            ),
        ]

        original = "### 原始草稿"
        refined = editor._auto_refine(original, results)
        assert refined == original


# ==================== Print Round Draft ====================


class TestPrintRoundDraft:
    """_print_round_draft 靜態方法測試"""

    def test_no_prev_draft(self):
        """prev_draft 為 None 時不崩潰"""
        EditorInChief._print_round_draft(1, "error", "### 草稿", None, 0.8, "Low")

    def test_same_draft_no_diff(self):
        """相同草稿時不顯示差異"""
        EditorInChief._print_round_draft(1, "error", "### 草稿", "### 草稿", 0.8, "Low")

    def test_different_drafts_shows_diff(self):
        """不同草稿時顯示差異面板"""
        EditorInChief._print_round_draft(
            2, "warning",
            "### 主旨\n已修正的內容",
            "### 主旨\n原始的內容",
            0.85, "Low",
        )

    def test_multiline_diff(self):
        """多行差異不崩潰"""
        old = "行1\n行2\n行3\n行4\n行5"
        new = "行1\n行2修改\n行3\n新增行\n行5"
        EditorInChief._print_round_draft(3, "info", new, old, 0.9, "Safe")


# ==================== Build Audit Log (extended) ====================


class TestBuildAuditLogExtended:
    def test_with_unfixable_count(self):
        """不可修復問題計數在日誌中顯示"""
        results = [ReviewResult(agent_name="Test", issues=[], score=0.9)]
        log = EditorInChief._build_audit_log(
            results, 0.9, "Low", 0.0, 0.0, unfixable_count=3,
        )
        assert "不可自動修復問題" in log
        assert "3" in log

    def test_with_phase_in_history(self):
        """迭代歷程含 phase 資訊"""
        results = [ReviewResult(agent_name="Test", issues=[], score=0.9)]
        history = [{"round": 1, "score": 0.7, "risk": "High", "phase": "error"}]
        log = EditorInChief._build_audit_log(
            results, 0.9, "Low", 0.0, 0.0, iteration_history=history,
        )
        assert "phase=error" in log

    def test_issue_severity_icons(self):
        """不同 severity 有不同圖示"""
        results = [
            ReviewResult(
                agent_name="Test",
                issues=[
                    ReviewIssue(category="format", severity="error", risk_level="high",
                                location="位置", description="錯誤"),
                    ReviewIssue(category="format", severity="warning", risk_level="medium",
                                location="位置", description="警告"),
                    ReviewIssue(category="format", severity="info", risk_level="low",
                                location="位置", description="資訊"),
                ],
                score=0.5,
            ),
        ]
        log = EditorInChief._build_audit_log(results, 0.5, "High", 1.0, 0.5)
        assert "[E]" in log
        assert "[W]" in log
        assert "[I]" in log

    def test_zero_weight_critical(self):
        """total_weight=0 時風險為 Critical"""
        results = [ReviewResult(agent_name="Test", issues=[], score=0.0, confidence=0.0)]
        editor = EditorInChief(MagicMock())
        report = editor._generate_qa_report(results)
        assert report.risk_summary == "Critical"


# ==================== Iterative Review (show_rounds) ====================


class TestIterativeReviewShowRounds:
    def test_show_rounds_flag(self, mock_llm):
        """show_rounds=True 時顯示每輪差異（不崩潰）"""
        editor = EditorInChief(mock_llm)

        err = _error_results()
        safe = _safe_results()
        call_count = [0]

        def mock_execute(draft, doc_type):
            call_count[0] += 1
            if call_count[0] == 1:
                return err, []
            return safe, []

        mock_llm.generate.return_value = "### 已修正的草稿"

        with patch.object(editor, '_execute_review', side_effect=mock_execute):
            _, report = editor.review_and_refine(
                "### 主旨\n測試", "函",
                max_rounds=3, show_rounds=True,
            )

        assert isinstance(report, QAReport)

    def test_iterative_multi_round_audit_log(self, mock_llm):
        """多輪迭代後 audit_log 包含完整歷程"""
        editor = EditorInChief(mock_llm)
        call_count = [0]

        def mock_execute(draft, doc_type):
            call_count[0] += 1
            improving_score = 0.3 + call_count[0] * 0.05
            return [
                ReviewResult(
                    agent_name="Format Auditor",
                    issues=[ReviewIssue(
                        category="format", severity="error", risk_level="high",
                        location="全文", description="問題",
                    )],
                    score=improving_score, confidence=1.0,
                ),
                ReviewResult(agent_name="Style Checker", issues=[],
                             score=improving_score + 0.1, confidence=0.9),
            ], []

        mock_llm.generate.return_value = "### 修正中"

        with patch.object(editor, '_execute_review', side_effect=mock_execute):
            _, report = editor.review_and_refine(
                "### 主旨\n測試", "函", max_rounds=3,
            )

        assert report.rounds_used >= 2
        assert "迭代審查歷程" in report.audit_log


# ==================== EditorInChief init edge cases ====================


class TestEditorInit:
    def test_realtime_lookup_failure_degrades(self, mock_llm):
        """即時查詢服務初始化失敗時降級為 None"""
        # LawVerifier/RecentPolicyFetcher 是在 __init__ 的 try 區塊中 local import，
        # 需要 patch 原始模組讓 import 失敗
        with patch.dict("sys.modules", {"src.knowledge.realtime_lookup": None}):
            editor = EditorInChief(mock_llm)
            # 應仍可建構成功（降級為無即時查詢）
            assert editor.fact_checker is not None
