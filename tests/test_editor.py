from unittest.mock import MagicMock

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
            issues=[ReviewIssue(category="format", severity="error", risk_level="high", location="文件結構", description="缺少主旨")],
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
            issues=[ReviewIssue(category="format", severity="error", risk_level="high", location="文件結構", description="格式問題", suggestion="修正格式")],
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
