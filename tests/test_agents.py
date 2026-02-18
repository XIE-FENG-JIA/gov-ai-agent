import pytest

from src.agents.requirement import RequirementAgent
from src.agents.template import TemplateEngine, clean_markdown_artifacts, renumber_provisions
from src.agents.auditor import FormatAuditor
from src.agents.style_checker import StyleChecker
from src.agents.fact_checker import FactChecker
from src.agents.consistency_checker import ConsistencyChecker
from src.agents.compliance_checker import ComplianceChecker
from src.agents.org_memory import OrganizationalMemory
from src.core.models import PublicDocRequirement


# ==================== RequirementAgent ====================

def test_requirement_agent(mock_llm):
    """Test requirement analysis parsing from code block."""
    agent = RequirementAgent(mock_llm)

    mock_llm.generate.return_value = '''
    ```json
    {
        "doc_type": "函",
        "urgency": "速件",
        "sender": "Test Agency",
        "receiver": "Test Receiver",
        "subject": "Test Subject"
    }
    ```
    '''

    req = agent.analyze("fake input")
    assert req.doc_type == "函"
    assert req.urgency == "速件"


def test_requirement_agent_raw_json(mock_llm):
    """Test parsing raw JSON without code block."""
    agent = RequirementAgent(mock_llm)

    mock_llm.generate.return_value = '''{
        "doc_type": "公告",
        "sender": "環保局",
        "receiver": "各學校",
        "subject": "回收公告"
    }'''

    req = agent.analyze("fake input")
    assert req.doc_type == "公告"
    assert req.sender == "環保局"


def test_requirement_agent_regex_fallback(mock_llm):
    """Test regex fallback when JSON is malformed."""
    agent = RequirementAgent(mock_llm)

    # Malformed JSON but has extractable fields
    mock_llm.generate.return_value = '''Here is the result:
    "doc_type": "簽", "sender": "市府", "receiver": "局長", "subject": "簽呈測試", extra garbage...
    '''

    req = agent.analyze("fake input")
    assert req.doc_type == "簽"
    assert req.subject == "簽呈測試"


def test_requirement_agent_failure(mock_llm):
    """Test that ValueError is raised for completely unparseable output."""
    agent = RequirementAgent(mock_llm)
    mock_llm.generate.return_value = "I don't know what you want."

    with pytest.raises(ValueError, match="LLM 未回傳有效的 JSON"):
        agent.analyze("fake input")


# ==================== TemplateEngine ====================

def test_template_engine():
    """Test markdown parsing and template application."""
    engine = TemplateEngine()

    raw_draft = """
### 主旨
Test Subject

### 說明
Test Explanation

### 辦法
Test Provisions
    """

    sections = engine.parse_draft(raw_draft)
    assert sections["subject"] == "Test Subject"
    assert sections["explanation"] == "Test Explanation"
    assert sections["provisions"] == "Test Provisions"


def test_template_engine_with_basis():
    """Test that 依據 section merges into explanation."""
    engine = TemplateEngine()

    raw_draft = """
### 主旨
公告主旨

### 依據
某法規第三條

### 說明
具體說明內容
    """

    sections = engine.parse_draft(raw_draft)
    assert "依據" in sections["explanation"]
    assert "某法規第三條" in sections["explanation"]
    assert "具體說明內容" in sections["explanation"]


def test_template_engine_apply_template():
    """Test full template application with Jinja2."""
    engine = TemplateEngine()
    req = PublicDocRequirement(
        doc_type="函",
        sender="測試機關",
        receiver="測試單位",
        subject="測試主旨",
    )
    sections = {"subject": "測試主旨", "explanation": "測試說明", "provisions": "", "attachments": "", "references": ""}
    result = engine.apply_template(req, sections)

    assert "測試機關" in result
    assert "測試單位" in result
    assert "測試主旨" in result


def test_clean_markdown_artifacts():
    """Test markdown artifact removal."""
    text = "```json\n{}\n```\n# Title\n**bold** _italic_ [link](http://x)"
    cleaned = clean_markdown_artifacts(text)
    assert "```" not in cleaned
    assert "**" not in cleaned
    assert "_italic_" not in cleaned
    assert "[link]" not in cleaned
    assert "bold" in cleaned
    assert "italic" in cleaned


def test_renumber_provisions():
    """Test provision renumbering."""
    text = "1. 第一項\n2. 第二項\n(1) 子項目"
    result = renumber_provisions(text)
    assert "一、" in result
    assert "二、" in result
    assert "（一）" in result


def test_renumber_provisions_empty():
    """Test renumber with empty/None input."""
    assert renumber_provisions("") == ""
    assert renumber_provisions(None) == ""


# ==================== Auditor ====================

def test_auditor(mock_llm):
    """Test format auditing logic."""
    auditor = FormatAuditor(mock_llm)

    mock_llm.generate.return_value = '{"errors": ["缺少『主旨』欄位"], "warnings": []}'

    draft = "### 說明\nSome text"
    result = auditor.audit(draft, "函")
    assert "缺少『主旨』欄位" in result["errors"]


def test_auditor_empty_response(mock_llm):
    """Test auditor handles empty LLM response."""
    auditor = FormatAuditor(mock_llm)
    mock_llm.generate.return_value = ""

    result = auditor.audit("### 主旨\nTest", "函")
    assert isinstance(result["errors"], list)
    assert isinstance(result["warnings"], list)


def test_auditor_invalid_json(mock_llm):
    """Test auditor handles non-JSON response gracefully."""
    auditor = FormatAuditor(mock_llm)
    mock_llm.generate.return_value = "This is not JSON at all."

    result = auditor.audit("### 主旨\nTest", "函")
    # Should have a warning about parse failure
    assert len(result["warnings"]) > 0


# ==================== Review Agents ====================

def test_style_checker(mock_llm):
    """Test style checker with valid JSON response."""
    checker = StyleChecker(mock_llm)
    mock_llm.generate.return_value = '{"issues": [], "score": 0.95}'

    result = checker.check("### 主旨\n正式公文內容")
    assert result.agent_name == "Style Checker"
    assert result.score == 0.95
    assert len(result.issues) == 0


def test_style_checker_empty_response(mock_llm):
    """Test style checker with empty response."""
    checker = StyleChecker(mock_llm)
    mock_llm.generate.return_value = ""

    result = checker.check("test")
    assert result.score == 0.8  # Default fallback


def test_fact_checker(mock_llm):
    """Test fact checker."""
    checker = FactChecker(mock_llm)
    mock_llm.generate.return_value = '{"issues": [{"severity": "warning", "location": "依據", "description": "法規可能過期", "suggestion": "確認最新版本"}], "score": 0.7}'

    result = checker.check("依據廢棄物清理法辦理")
    assert result.agent_name == "Fact Checker"
    assert len(result.issues) == 1
    assert result.issues[0].category == "fact"


def test_consistency_checker(mock_llm):
    """Test consistency checker."""
    checker = ConsistencyChecker(mock_llm)
    mock_llm.generate.return_value = '{"issues": [], "score": 0.9}'

    result = checker.check("### 主旨\n測試\n### 說明\n測試說明")
    assert result.agent_name == "Consistency Checker"
    assert result.score == 0.9


def test_compliance_checker(mock_llm):
    """Test compliance checker with no KB."""
    checker = ComplianceChecker(mock_llm)
    mock_llm.generate.return_value = '{"issues": [], "score": 0.9, "confidence": 0.8}'

    result = checker.check("### 主旨\n測試公文")
    assert result.agent_name == "Compliance Checker"
    assert result.confidence == 0.8


# ==================== OrganizationalMemory ====================

def test_org_memory(tmp_path):
    """Test organizational memory CRUD."""
    storage = tmp_path / "prefs.json"
    mem = OrganizationalMemory(str(storage))

    # Get default profile
    profile = mem.get_agency_profile("測試機關")
    assert profile["formal_level"] == "standard"

    # Update preference
    mem.update_preference("測試機關", "formal_level", "formal")
    profile = mem.get_agency_profile("測試機關")
    assert profile["formal_level"] == "formal"

    # Writing hints
    hints = mem.get_writing_hints("測試機關")
    assert "正式" in hints


def test_org_memory_export(tmp_path):
    """Test memory export report."""
    storage = tmp_path / "prefs.json"
    mem = OrganizationalMemory(str(storage))
    mem.update_preference("機關A", "usage_count", 5)

    report = mem.export_report()
    assert "機關A" in report
    assert "使用次數" in report
