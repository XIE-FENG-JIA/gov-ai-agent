import json
from unittest.mock import MagicMock

from src.agents.requirement import RequirementAgent
from src.agents.template import TemplateEngine, clean_markdown_artifacts, renumber_provisions
from src.agents.auditor import FormatAuditor
from src.agents.style_checker import StyleChecker
from src.agents.fact_checker import FactChecker
from src.agents.consistency_checker import ConsistencyChecker
from src.agents.compliance_checker import ComplianceChecker
from src.agents.writer import WriterAgent
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
    """Test fallback requirement when JSON parsing fails completely."""
    agent = RequirementAgent(mock_llm)
    mock_llm.generate.return_value = "I don't know what you want."

    # 不再拋出 ValueError，改為回傳 fallback 需求
    result = agent.analyze("fake input for testing")
    assert result.doc_type == "函"
    assert result.sender == "（未指定）"
    assert result.receiver == "（未指定）"
    assert "fake input" in result.subject


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
    mock_llm.generate.return_value = json.dumps({
        "issues": [{"severity": "warning", "location": "依據",
                     "description": "法規可能過期", "suggestion": "確認最新版本"}],
        "score": 0.7,
    })

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


# ==================== Writer Anti-Hallucination Tests ====================

def test_writer_prompt_contains_anti_hallucination_rules(mock_llm):
    """測試 WriterAgent 的 prompt 包含反幻覺規則。"""
    kb_mock = MagicMock()
    kb_mock.search_hybrid.return_value = []

    writer = WriterAgent(mock_llm, kb_mock)
    mock_llm.generate.return_value = "### 主旨\n測試主旨\n\n### 說明\n測試說明"

    req = PublicDocRequirement(
        doc_type="函", sender="測試機關", receiver="測試單位", subject="測試主旨"
    )
    writer.write_draft(req)

    # 驗證 LLM 被呼叫時的 prompt 包含反幻覺關鍵詞
    call_args = mock_llm.generate.call_args
    prompt_text = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
    assert "NEVER fabricate regulation names" in prompt_text
    assert "Anti-Hallucination Rules" in prompt_text


def test_writer_skeleton_mode_no_examples(mock_llm):
    """測試無範例時 Writer 進入骨架模式，草稿包含明確警告。"""
    kb_mock = MagicMock()
    kb_mock.search_hybrid.return_value = []

    writer = WriterAgent(mock_llm, kb_mock)
    mock_llm.generate.return_value = "### 主旨\n測試\n\n### 說明\n依據某法辦理"

    req = PublicDocRequirement(
        doc_type="函", sender="測試機關", receiver="測試單位", subject="測試主旨"
    )
    draft = writer.write_draft(req)

    # 骨架模式應包含提醒訊息
    assert "骨架模式" in draft
    assert "待補依據" in draft
    assert "請勿直接使用本草稿作為正式公文" in draft


def test_writer_no_examples_prompt_forbids_citations(mock_llm):
    """測試無範例時 prompt 明確禁止使用引用標記。"""
    kb_mock = MagicMock()
    kb_mock.search_hybrid.return_value = []

    writer = WriterAgent(mock_llm, kb_mock)
    mock_llm.generate.return_value = "### 主旨\n測試"

    req = PublicDocRequirement(
        doc_type="函", sender="測試機關", receiver="測試單位", subject="測試"
    )
    writer.write_draft(req)

    call_args = mock_llm.generate.call_args
    prompt_text = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
    # 無範例時 prompt 中應告知不要使用引用標記
    assert "不要使用任何 [^i] 引用標記" in prompt_text


# ==================== FactChecker Enhanced Tests ====================

def test_fact_checker_unverified_citation(mock_llm):
    """測試 FactChecker 對未驗證引用的處理。"""
    checker = FactChecker(mock_llm)
    # 模擬 LLM 回傳包含未驗證引用警告的結果
    mock_llm.generate.return_value = json.dumps({
        "issues": [{
            "severity": "warning",
            "location": "說明第一項",
            "description": "未驗證引用：該法規名稱未在知識庫來源中找到對應記錄",
            "suggestion": "請確認「廢棄物清理法第二十八條」是否正確引用"
        }],
        "score": 0.6,
    })

    result = checker.check("依據廢棄物清理法第二十八條辦理")
    assert result.agent_name == "Fact Checker"
    assert len(result.issues) == 1
    assert "未驗證引用" in result.issues[0].description


def test_fact_checker_prompt_contains_skepticism_stance(mock_llm):
    """測試 FactChecker 的 prompt 包含預設懷疑立場。"""
    checker = FactChecker(mock_llm)
    mock_llm.generate.return_value = '{"issues": [], "score": 0.9}'

    checker.check("### 主旨\n測試公文")

    call_args = mock_llm.generate.call_args
    prompt_text = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
    assert "Default Stance" in prompt_text
    assert "ALWAYS flag as" in prompt_text


def test_fact_checker_prompt_checks_hallucination_patterns(mock_llm):
    """測試 FactChecker 的 prompt 包含常見幻覺模式檢查。"""
    checker = FactChecker(mock_llm)
    mock_llm.generate.return_value = '{"issues": [], "score": 0.9}'

    checker.check("### 主旨\n測試")

    call_args = mock_llm.generate.call_args
    prompt_text = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
    assert "hallucination patterns" in prompt_text
    assert "未驗證引用" in prompt_text


# ==================== ComplianceChecker Enhanced Tests ====================

def test_compliance_checker_no_policy_limited_mode(mock_llm):
    """測試無政策文件時 ComplianceChecker 進入限定檢查模式。"""
    checker = ComplianceChecker(mock_llm, kb_manager=None)
    mock_llm.generate.return_value = json.dumps({
        "issues": [{
            "severity": "warning",
            "location": "說明",
            "description": "使用過時術語「殘障」，建議改為「身心障礙」（缺乏政策文件佐證）",
            "suggestion": "將「殘障」改為「身心障礙」"
        }],
        "score": 0.85,
        "confidence": 0.3,
    })

    result = checker.check("### 主旨\n關於殘障人士福利")
    assert result.agent_name == "Compliance Checker"
    assert len(result.issues) == 1


def test_compliance_checker_no_policy_prompt_forbids_guessing(mock_llm):
    """測試無政策文件時 prompt 明確禁止猜測政策要求。"""
    checker = ComplianceChecker(mock_llm, kb_manager=None)
    mock_llm.generate.return_value = '{"issues": [], "score": 0.9, "confidence": 0.3}'

    checker.check("### 主旨\n測試公文")

    call_args = mock_llm.generate.call_args
    prompt_text = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
    assert "Limited Mode" in prompt_text
    assert "Do NOT guess" in prompt_text
    assert "fabricate policy violations" in prompt_text


def test_compliance_checker_with_policy_uses_full_checks(mock_llm):
    """測試有政策文件時使用完整檢查模式。"""
    kb_mock = MagicMock()
    kb_mock.search_policies.return_value = [{
        "metadata": {"title": "測試政策"},
        "content": "測試政策內容",
    }]
    checker = ComplianceChecker(mock_llm, kb_manager=kb_mock)
    mock_llm.generate.return_value = '{"issues": [], "score": 0.95, "confidence": 0.9}'

    checker.check("### 主旨\n測試公文")

    call_args = mock_llm.generate.call_args
    prompt_text = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
    # 完整模式不應包含 Limited Mode
    assert "Limited Mode" not in prompt_text
    assert "Policy Alignment" in prompt_text


# ==================== StyleChecker Enhanced Tests ====================

def test_style_checker_official_title_check(mock_llm):
    """測試 StyleChecker 檢查官職銜稱格式。"""
    checker = StyleChecker(mock_llm)
    mock_llm.generate.return_value = json.dumps({
        "issues": [{
            "severity": "warning",
            "location": "受文者",
            "description": "官職銜稱格式不完整：「王副局」應為「王副局長」",
            "suggestion": "改為「王副局長」"
        }],
        "score": 0.85,
    })

    result = checker.check("### 主旨\n請王副局核示")
    assert len(result.issues) == 1
    assert result.issues[0].category == "style"


def test_style_checker_prompt_contains_title_rules(mock_llm):
    """測試 StyleChecker 的 prompt 包含官職銜稱檢查規則。"""
    checker = StyleChecker(mock_llm)
    mock_llm.generate.return_value = '{"issues": [], "score": 0.95}'

    checker.check("### 主旨\n測試公文")

    call_args = mock_llm.generate.call_args
    prompt_text = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
    assert "Official Title Format" in prompt_text
    assert "主任秘書" in prompt_text
    assert "副局長" in prompt_text


def test_style_checker_prompt_contains_agency_name_rules(mock_llm):
    """測試 StyleChecker 的 prompt 包含機關名稱一致性檢查規則。"""
    checker = StyleChecker(mock_llm)
    mock_llm.generate.return_value = '{"issues": [], "score": 0.95}'

    checker.check("### 主旨\n測試公文")

    call_args = mock_llm.generate.call_args
    prompt_text = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
    assert "Agency Name Consistency" in prompt_text
    assert "全銜" in prompt_text
    assert "簡稱" in prompt_text


def test_style_checker_agency_name_inconsistency(mock_llm):
    """測試 StyleChecker 偵測機關名稱不一致。"""
    checker = StyleChecker(mock_llm)
    mock_llm.generate.return_value = json.dumps({
        "issues": [{
            "severity": "warning",
            "location": "全文",
            "description": "機關簡稱不一致：同時使用「環保局」和「環境局」指稱同一機關",
            "suggestion": "統一使用「環保局」或正式全銜「環境保護局」"
        }],
        "score": 0.8,
    })

    result = checker.check("臺北市政府環境保護局（下稱環保局）...環境局辦理...")
    assert len(result.issues) == 1
    assert result.issues[0].severity == "warning"
