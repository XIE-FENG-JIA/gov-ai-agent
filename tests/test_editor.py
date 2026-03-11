from unittest.mock import MagicMock, patch

from src.agents.editor import EditorInChief
from src.core.review_models import QAReport, ReviewIssue, ReviewResult


def test_editor_review_safe(mock_llm):
    """Test editor with all agents returning clean results."""
    # Mock all LLM responses to return clean JSON
    mock_llm.generate.return_value = '{"issues": [], "score": 0.95}'

    editor = EditorInChief(mock_llm)
    draft = "### 主旨\n測試主旨\n### 說明\n測試說明"

    final_draft, qa_report = editor.review_and_refine(draft, "函")

    assert isinstance(qa_report, QAReport)
    assert qa_report.overall_score > 0
    assert qa_report.risk_summary in ["Critical", "High", "Moderate", "Low", "Safe"]


def test_editor_category_detection():
    """Test _get_agent_category method."""
    editor = EditorInChief(MagicMock())

    assert editor._get_agent_category("Format Auditor") == "format"
    assert editor._get_agent_category("Style Checker") == "style"
    assert editor._get_agent_category("Fact Checker") == "fact"
    assert editor._get_agent_category("Consistency Checker") == "consistency"
    assert editor._get_agent_category("Compliance Checker") == "compliance"
    assert editor._get_agent_category("Unknown Agent") == "style"  # Default


def test_editor_qa_report_generation():
    """Test QA report generation with mixed results."""
    editor = EditorInChief(MagicMock())

    results = [
        ReviewResult(
            agent_name="Format Auditor",
            issues=[ReviewIssue(
                category="format", severity="error", risk_level="high",
                location="文件結構", description="缺少主旨",
            )],
            score=0.5,
            confidence=1.0,
        ),
        ReviewResult(
            agent_name="Style Checker",
            issues=[],
            score=0.95,
            confidence=0.9,
        ),
    ]

    report = editor._generate_qa_report(results)
    assert report.overall_score < 1.0
    assert report.risk_summary in ["Critical", "High", "Moderate"]
    assert "Format Auditor" in report.audit_log
    assert "缺少主旨" in report.audit_log


def test_editor_auto_refine(mock_llm):
    """Test auto-refine with feedback."""
    mock_llm.generate.return_value = "### 主旨\n已修正的主旨\n### 說明\n已修正的說明"

    editor = EditorInChief(mock_llm)
    results = [
        ReviewResult(
            agent_name="Format Auditor",
            issues=[ReviewIssue(
                category="format", severity="error", risk_level="high",
                location="文件結構", description="格式問題", suggestion="修正格式",
            )],
            score=0.5,
        ),
    ]

    refined = editor._auto_refine("### 主旨\n原始內容", results)
    assert "已修正" in refined


def test_editor_auto_refine_no_feedback(mock_llm):
    """Test auto-refine with no issues returns original draft."""
    editor = EditorInChief(mock_llm)
    results = [ReviewResult(agent_name="Test", issues=[], score=1.0)]

    original = "### 主旨\n原始內容"
    refined = editor._auto_refine(original, results)
    assert refined == original


def test_editor_build_audit_log_with_suggestion():
    """測試審計日誌中 issue 有 suggestion 時的顯示"""
    editor = EditorInChief(MagicMock())
    results = [
        ReviewResult(
            agent_name="Format Auditor",
            issues=[ReviewIssue(
                category="format", severity="error", risk_level="high",
                location="主旨", description="缺少主旨",
                suggestion="請補上主旨段落"
            )],
            score=0.5,
        ),
    ]
    log = editor._build_audit_log(results, 0.5, "High", 1.0, 0.0)
    assert "*建議*：請補上主旨段落" in log


def test_editor_auto_refine_long_feedback(mock_llm):
    """測試回饋超過 MAX_FEEDBACK_LENGTH 時被截斷"""
    mock_llm.generate.return_value = "### 主旨\n已修正"

    editor = EditorInChief(mock_llm)
    # 建立超長回饋（大量 issue）
    issues = []
    for i in range(500):
        issues.append(ReviewIssue(
            category="format", severity="error", risk_level="high",
            location=f"位置{i}", description=f"問題描述{i}" * 10
        ))
    results = [ReviewResult(agent_name="Test", issues=issues, score=0.1)]
    editor._auto_refine("### 主旨\n測試", results)
    # 應成功呼叫 LLM（回饋被截斷但不崩潰）
    assert mock_llm.generate.called


def test_editor_auto_refine_long_draft(mock_llm):
    """測試草稿超過 MAX_DRAFT_LENGTH 時被截斷"""
    from src.core.constants import MAX_DRAFT_LENGTH
    mock_llm.generate.return_value = "### 主旨\n已修正"

    editor = EditorInChief(mock_llm)
    long_draft = "### 主旨\n" + "A" * (MAX_DRAFT_LENGTH + 100)
    results = [ReviewResult(
        agent_name="Test",
        issues=[ReviewIssue(
            category="format", severity="error", risk_level="high",
            location="主旨", description="問題"
        )],
        score=0.5,
    )]
    editor._auto_refine(long_draft, results)
    # 應成功呼叫 LLM（草稿被截斷但不崩潰）
    assert mock_llm.generate.called


def test_editor_parallel_agent_exception_handling(mock_llm):
    """測試並行審查中單一 agent 拋出例外時的容錯處理"""
    from src.core.constants import DEFAULT_FAILED_SCORE, DEFAULT_FAILED_CONFIDENCE
    # 設定正常的 LLM 回應（格式審查用）
    mock_llm.generate.return_value = '{"errors": [], "warnings": []}'

    editor = EditorInChief(mock_llm)
    # 讓其中一個 checker 的 check 方法拋出例外
    editor.style_checker.check = MagicMock(side_effect=RuntimeError("unexpected failure"))

    draft = "### 主旨\n測試主旨\n### 說明\n測試說明"
    final_draft, qa_report = editor.review_and_refine(draft, "函")

    # 應該產生完整的 QA 報告（包含失敗的 agent）
    assert isinstance(qa_report, QAReport)
    # 找到失敗的 agent 結果
    failed_results = [r for r in qa_report.agent_results if r.agent_name == "Style Checker"]
    assert len(failed_results) == 1
    assert failed_results[0].score == DEFAULT_FAILED_SCORE
    assert failed_results[0].confidence == DEFAULT_FAILED_CONFIDENCE


def test_auto_refine_no_issues_returns_original(mock_llm):
    """Bug 1: 低分但無 issues 時 _auto_refine 應返回原始草稿且不呼叫 LLM"""
    editor = EditorInChief(mock_llm)
    # 構造低分但無 issues 的結果
    results = [
        ReviewResult(
            agent_name="Style Checker",
            issues=[],
            score=0.7,
            confidence=1.0,
        ),
        ReviewResult(
            agent_name="Fact Checker",
            issues=[],
            score=0.6,
            confidence=1.0,
        ),
    ]
    original_draft = "### 主旨\n原始草稿內容"
    refined = editor._auto_refine(original_draft, results)
    # 無 issues → 無回饋 → 應返回原始草稿
    assert refined == original_draft
    # 不應呼叫 LLM（因為沒有具體修改建議）
    mock_llm.generate.assert_not_called()


def test_editor_print_report_long_description():
    """測試 _print_report 中超長描述被截斷"""
    long_desc = "A" * 100  # 超過 max_desc_length (75)
    report = QAReport(
        overall_score=0.5,
        risk_summary="High",
        agent_results=[
            ReviewResult(
                agent_name="Test",
                issues=[ReviewIssue(
                    category="format", severity="error", risk_level="high",
                    location="位置", description=long_desc
                )],
                score=0.5,
            ),
        ],
        audit_log="test",
    )
    # 不應拋出異常（static method）
    EditorInChief._print_report(report)


# ==================== 分段審查測試 ====================


class TestSegmentedReview:
    """超長草稿分段審查測試"""

    def test_split_draft_short(self):
        """短草稿不應分段"""
        segments = EditorInChief._split_draft("短草稿")
        assert len(segments) == 1
        assert segments[0] == "短草稿"

    def test_split_draft_long(self):
        """超長草稿應被分段"""
        long_draft = "A" * 30000
        segments = EditorInChief._split_draft(long_draft)
        assert len(segments) > 1
        # 合併後應等於原始草稿
        assert "".join(segments) == long_draft

    def test_split_draft_prefers_newline_boundary(self):
        """分段應優先在換行處切割"""
        # 建構包含換行的長草稿
        lines = ["第" + str(i) + "行內容" * 100 + "\n" for i in range(200)]
        long_draft = "".join(lines)
        segments = EditorInChief._split_draft(long_draft)
        # 每段（除最後一段）應以換行結尾
        for seg in segments[:-1]:
            assert seg.endswith("\n")

    def test_segmented_review_triggers_for_long_draft(self, mock_llm):
        """超過 15000 字的草稿應觸發分段審查"""
        mock_llm.generate.return_value = '{"errors": [], "warnings": []}'
        editor = EditorInChief(mock_llm)

        long_draft = "### 主旨\n測試主旨\n### 說明\n" + "測試內容。" * 3000
        assert len(long_draft) > EditorInChief._SEGMENT_THRESHOLD

        final_draft, report = editor.review_and_refine(long_draft, "函")
        assert isinstance(report, QAReport)
        # 分段審查的 agent 名稱應包含段落標記
        segment_agents = [r for r in report.agent_results if "段" in r.agent_name]
        assert len(segment_agents) > 0

    def test_segmented_review_preserves_return_type(self, mock_llm):
        """分段審查回傳類型應與普通審查相同"""
        mock_llm.generate.return_value = '{"errors": [], "warnings": []}'
        editor = EditorInChief(mock_llm)

        long_draft = "### 主旨\n" + "A" * 20000
        result = editor.review_and_refine(long_draft, "函")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], QAReport)

    def test_normal_draft_does_not_segment(self, mock_llm):
        """正常長度草稿不應分段"""
        mock_llm.generate.return_value = '{"errors": [], "warnings": []}'
        editor = EditorInChief(mock_llm)

        short_draft = "### 主旨\n測試\n### 說明\n短內容"
        _, report = editor.review_and_refine(short_draft, "函")
        # 不應有段落標記
        segment_agents = [r for r in report.agent_results if "段" in r.agent_name]
        assert len(segment_agents) == 0


# ==================== 逾時保留部分結果測試 ====================


class TestTimeoutPartialResults:
    """並行審查逾時時保留部分結果的測試"""

    def test_timeout_preserves_completed_results(self, mock_llm):
        """逾時時應保留已完成 Agent 的結果"""
        import threading
        mock_llm.generate.return_value = '{"errors": [], "warnings": []}'

        editor = EditorInChief(mock_llm)

        # 用 Event.wait 模擬慢 Agent，搭配短 timeout 來加速測試
        block = threading.Event()
        editor.fact_checker.check = MagicMock(
            side_effect=lambda d: (block.wait(10) or ReviewResult(
                agent_name="Fact Checker", issues=[], score=1.0
            ))
        )

        # 暫時縮短並行逾時為 1 秒
        import src.core.constants as _c
        orig = _c.PARALLEL_REVIEW_TIMEOUT
        _c.PARALLEL_REVIEW_TIMEOUT = 1
        try:
            draft = "### 主旨\n測試\n### 說明\n測試內容"
            _, report = editor.review_and_refine(draft, "函")
        finally:
            _c.PARALLEL_REVIEW_TIMEOUT = orig
            block.set()  # 釋放阻塞的執行緒

        # 應有結果（包括已完成和逾時的）
        assert isinstance(report, QAReport)
        assert len(report.agent_results) >= 1

    def test_audit_log_includes_timeout_annotation(self):
        """逾時的 Agent 應在審計日誌中被標註"""
        editor = EditorInChief(MagicMock())
        results = [
            ReviewResult(agent_name="Format Auditor", issues=[], score=1.0),
        ]
        timed_out = ["Style Checker", "Fact Checker"]
        report = editor._generate_qa_report(results, timed_out)

        assert "逾時未完成的 Agent" in report.audit_log
        assert "Style Checker" in report.audit_log
        assert "Fact Checker" in report.audit_log

    def test_audit_log_no_timeout_section_when_none(self):
        """無逾時時審計日誌不應包含逾時區段"""
        editor = EditorInChief(MagicMock())
        results = [
            ReviewResult(agent_name="Format Auditor", issues=[], score=1.0),
        ]
        report = editor._generate_qa_report(results, [])
        assert "逾時未完成的 Agent" not in report.audit_log

    def test_generate_qa_report_backward_compatible(self):
        """_generate_qa_report 不傳 timed_out_agents 時應向後相容"""
        editor = EditorInChief(MagicMock())
        results = [
            ReviewResult(agent_name="Format Auditor", issues=[], score=0.9),
        ]
        # 不傳第二個參數（向後相容）
        report = editor._generate_qa_report(results)
        assert isinstance(report, QAReport)
        assert "逾時未完成的 Agent" not in report.audit_log


# ==================== 迭代審查測試 ====================


class TestIterativeReview:
    """迭代審查機制測試"""

    def _make_safe_results(self):
        """產生全部通過的審查結果列表"""
        return [
            ReviewResult(agent_name="Format Auditor", issues=[], score=0.98, confidence=1.0),
            ReviewResult(agent_name="Style Checker", issues=[], score=0.95, confidence=0.9),
            ReviewResult(agent_name="Fact Checker", issues=[], score=0.95, confidence=0.9),
            ReviewResult(agent_name="Consistency Checker", issues=[], score=0.95, confidence=0.9),
            ReviewResult(agent_name="Compliance Checker", issues=[], score=0.95, confidence=0.9),
        ]

    def _make_high_risk_results(self):
        """產生高風險的審查結果列表"""
        return [
            ReviewResult(
                agent_name="Format Auditor",
                issues=[ReviewIssue(
                    category="format", severity="error", risk_level="high",
                    location="全文", description="缺少必要欄位",
                )],
                score=0.4, confidence=1.0,
            ),
            ReviewResult(agent_name="Style Checker", issues=[], score=0.8, confidence=0.9),
            ReviewResult(agent_name="Fact Checker", issues=[], score=0.8, confidence=0.9),
            ReviewResult(agent_name="Consistency Checker", issues=[], score=0.8, confidence=0.9),
            ReviewResult(agent_name="Compliance Checker", issues=[], score=0.8, confidence=0.9),
        ]

    def _make_all_failed_results(self):
        """產生全部失敗的審查結果"""
        return [
            ReviewResult(agent_name="Format Auditor", issues=[], score=0.0, confidence=0.0),
            ReviewResult(agent_name="Style Checker", issues=[], score=0.0, confidence=0.0),
            ReviewResult(agent_name="Fact Checker", issues=[], score=0.0, confidence=0.0),
            ReviewResult(agent_name="Consistency Checker", issues=[], score=0.0, confidence=0.0),
            ReviewResult(agent_name="Compliance Checker", issues=[], score=0.0, confidence=0.0),
        ]

    def test_single_round_safe(self, mock_llm):
        """Safe 風險時不迭代，第 1 輪即停止"""
        editor = EditorInChief(mock_llm)
        safe_results = self._make_safe_results()

        with patch.object(editor, '_execute_review', return_value=(safe_results, [])):
            final_draft, report = editor.review_and_refine("### 主旨\n測試", "函")

        assert report.risk_summary in ["Safe", "Low"]
        assert report.rounds_used == 1
        assert len(report.iteration_history) == 1
        assert report.iteration_history[0]["round"] == 1

    def test_two_rounds_convergence(self, mock_llm):
        """第 1 輪 High → 修正 → 第 2 輪 Safe → 停止"""
        editor = EditorInChief(mock_llm)
        high_results = self._make_high_risk_results()
        safe_results = self._make_safe_results()
        call_count = [0]

        def mock_execute_review(draft, doc_type):
            call_count[0] += 1
            if call_count[0] == 1:
                return high_results, []
            return safe_results, []

        with patch.object(editor, '_execute_review', side_effect=mock_execute_review), \
             patch.object(editor, '_auto_refine', return_value="### 主旨\n已修正"):
            final_draft, report = editor.review_and_refine("### 主旨\n測試", "函", max_rounds=3)

        assert report.rounds_used == 2
        assert len(report.iteration_history) == 2
        assert report.iteration_history[0]["risk"] in ["Critical", "High", "Moderate"]
        assert report.iteration_history[1]["risk"] in ["Safe", "Low"]

    def test_max_rounds_cap(self, mock_llm):
        """持續 High 且分數持續改善時在 max_rounds 停止"""
        editor = EditorInChief(mock_llm)
        call_count = [0]

        def mock_execute_review(draft, doc_type):
            call_count[0] += 1
            # 每輪分數略微改善，但風險始終 High
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
                ReviewResult(agent_name="Style Checker", issues=[], score=improving_score + 0.1, confidence=0.9),
                ReviewResult(agent_name="Fact Checker", issues=[], score=improving_score + 0.1, confidence=0.9),
                ReviewResult(agent_name="Consistency Checker", issues=[], score=improving_score + 0.1, confidence=0.9),
                ReviewResult(agent_name="Compliance Checker", issues=[], score=improving_score + 0.1, confidence=0.9),
            ], []

        with patch.object(editor, '_execute_review', side_effect=mock_execute_review), \
             patch.object(editor, '_auto_refine', return_value="### 主旨\n修正中"):
            final_draft, report = editor.review_and_refine("### 主旨\n測試", "函", max_rounds=3)

        assert report.rounds_used == 3
        assert len(report.iteration_history) == 3

    def test_score_no_improvement_stops(self, mock_llm):
        """分數未改善時停止迭代"""
        editor = EditorInChief(mock_llm)
        call_count = [0]

        def mock_execute_review(draft, doc_type):
            call_count[0] += 1
            # 第 1 輪和第 2 輪分數相同
            return [
                ReviewResult(
                    agent_name="Format Auditor",
                    issues=[ReviewIssue(
                        category="format", severity="error", risk_level="high",
                        location="全文", description="問題",
                    )],
                    score=0.5, confidence=1.0,
                ),
                ReviewResult(agent_name="Style Checker", issues=[], score=0.7, confidence=0.9),
                ReviewResult(agent_name="Fact Checker", issues=[], score=0.7, confidence=0.9),
                ReviewResult(agent_name="Consistency Checker", issues=[], score=0.7, confidence=0.9),
                ReviewResult(agent_name="Compliance Checker", issues=[], score=0.7, confidence=0.9),
            ], []

        with patch.object(editor, '_execute_review', side_effect=mock_execute_review), \
             patch.object(editor, '_auto_refine', return_value="### 主旨\n修正中"):
            final_draft, report = editor.review_and_refine("### 主旨\n測試", "函", max_rounds=5)

        # 第 2 輪分數 == 第 1 輪，應停止
        assert report.rounds_used == 2
        assert len(report.iteration_history) == 2

    def test_all_agents_failed_stops(self, mock_llm):
        """所有 Agent confidence=0 且 Critical 時停止"""
        editor = EditorInChief(mock_llm)
        failed_results = self._make_all_failed_results()

        with patch.object(editor, '_execute_review', return_value=(failed_results, [])):
            final_draft, report = editor.review_and_refine("### 主旨\n測試", "函", max_rounds=3)

        assert report.rounds_used == 1
        assert report.risk_summary == "Critical"

    def test_rounds_used_in_report(self, mock_llm):
        """QAReport.rounds_used 正確記錄輪數"""
        editor = EditorInChief(mock_llm)
        safe_results = self._make_safe_results()

        with patch.object(editor, '_execute_review', return_value=(safe_results, [])):
            _, report = editor.review_and_refine("### 主旨\n測試", "函")

        assert report.rounds_used == 1
        assert isinstance(report.rounds_used, int)

    def test_iteration_history_in_report(self, mock_llm):
        """QAReport.iteration_history 記錄每輪 score/risk"""
        editor = EditorInChief(mock_llm)
        high_results = self._make_high_risk_results()
        safe_results = self._make_safe_results()
        call_count = [0]

        def mock_execute_review(draft, doc_type):
            call_count[0] += 1
            if call_count[0] == 1:
                return high_results, []
            return safe_results, []

        with patch.object(editor, '_execute_review', side_effect=mock_execute_review), \
             patch.object(editor, '_auto_refine', return_value="### 主旨\n已修正"):
            _, report = editor.review_and_refine("### 主旨\n測試", "函", max_rounds=3)

        assert len(report.iteration_history) == 2
        assert report.iteration_history[0]["round"] == 1
        assert report.iteration_history[1]["round"] == 2
        assert "score" in report.iteration_history[0]
        assert "risk" in report.iteration_history[0]

    def test_custom_max_rounds(self, mock_llm):
        """自訂 max_rounds 參數生效"""
        editor = EditorInChief(mock_llm)
        call_count = [0]

        def mock_execute_review(draft, doc_type):
            call_count[0] += 1
            improving_score = 0.3 + call_count[0] * 0.1
            return [
                ReviewResult(
                    agent_name="Format Auditor",
                    issues=[ReviewIssue(
                        category="format", severity="error", risk_level="high",
                        location="全文", description="問題",
                    )],
                    score=improving_score, confidence=1.0,
                ),
                ReviewResult(agent_name="Style Checker", issues=[], score=improving_score + 0.1, confidence=0.9),
                ReviewResult(agent_name="Fact Checker", issues=[], score=improving_score + 0.1, confidence=0.9),
                ReviewResult(agent_name="Consistency Checker", issues=[], score=improving_score + 0.1, confidence=0.9),
                ReviewResult(agent_name="Compliance Checker", issues=[], score=improving_score + 0.1, confidence=0.9),
            ], []

        with patch.object(editor, '_execute_review', side_effect=mock_execute_review), \
             patch.object(editor, '_auto_refine', return_value="### 主旨\n修正中"):
            _, report = editor.review_and_refine("### 主旨\n測試", "函", max_rounds=2)

        assert report.rounds_used <= 2

    def test_backward_compatible_default(self, mock_llm):
        """不傳 max_rounds 時預設 3 輪"""
        editor = EditorInChief(mock_llm)
        safe_results = self._make_safe_results()

        with patch.object(editor, '_execute_review', return_value=(safe_results, [])):
            # 不傳 max_rounds
            _, report = editor.review_and_refine("### 主旨\n測試", "函")

        assert isinstance(report, QAReport)
        assert report.rounds_used >= 1

    def test_segmented_review_not_iterative(self, mock_llm):
        """超長草稿分段審查不迭代（維持現行行為）"""
        mock_llm.generate.return_value = '{"errors": [], "warnings": []}'
        editor = EditorInChief(mock_llm)

        long_draft = "### 主旨\n測試主旨\n### 說明\n" + "測試內容。" * 3000
        assert len(long_draft) > EditorInChief._SEGMENT_THRESHOLD

        final_draft, report = editor.review_and_refine(long_draft, "函", max_rounds=3)
        # 分段審查不使用迭代，rounds_used 維持預設值 1
        assert report.rounds_used == 1
        assert report.iteration_history == []

    def test_audit_log_includes_iteration_history(self, mock_llm):
        """審計日誌中包含迭代歷程"""
        editor = EditorInChief(mock_llm)
        results = [
            ReviewResult(agent_name="Format Auditor", issues=[], score=0.9, confidence=1.0),
        ]
        iteration_history = [
            {"round": 1, "score": 0.6, "risk": "High"},
            {"round": 2, "score": 0.9, "risk": "Safe"},
        ]
        log = editor._build_audit_log(
            results, 0.9, "Safe", 0.0, 0.0,
            iteration_history=iteration_history,
        )
        assert "迭代審查歷程" in log
        assert "第 1 輪" in log
        assert "第 2 輪" in log
        assert "score=0.60" in log
        assert "risk=High" in log
