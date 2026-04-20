import json
import re
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
from src.integrations.open_notebook.service import OpenNotebookAskRequest
from src.integrations.open_notebook.stub import AskResult, RetrievedEvidence
from src.utils.tw_check import to_traditional


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
    # regex fallback 無法提取 reason 時，應使用原始使用者輸入
    assert req.reason == "fake input"


def test_requirement_agent_regex_fallback_with_reason(mock_llm):
    """Test regex fallback preserves reason when extractable."""
    agent = RequirementAgent(mock_llm)

    mock_llm.generate.return_value = '''
    "doc_type": "函", "sender": "教育局", "receiver": "各學校",
    "subject": "校園安全", "reason": "為強化校園安全管理"
    '''

    req = agent.analyze("some input")
    assert req.doc_type == "函"
    assert req.reason == "為強化校園安全管理"


def test_requirement_agent_failure(mock_llm):
    """Test fallback requirement when JSON parsing fails completely."""
    agent = RequirementAgent(mock_llm)
    mock_llm.generate.return_value = "I don't know what you want."

    # 不再拋出 ValueError，改為回傳 fallback 需求
    user_text = "fake input for testing with important details about 環保局"
    result = agent.analyze(user_text)
    assert result.doc_type == "函"
    assert result.sender == "（未指定）"
    assert result.receiver == "（未指定）"
    assert "fake input" in result.subject
    # fallback 應保留完整使用者輸入作為 reason，供 WriterAgent 使用
    assert result.reason == user_text


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


def test_template_engine_apply_template_uses_canonical_reference_heading():
    """TemplateEngine 應將參考來源統一成 canonical heading。"""
    engine = TemplateEngine()
    req = PublicDocRequirement(
        doc_type="函",
        sender="測試機關",
        receiver="測試單位",
        subject="測試主旨",
    )
    sections = {
        "subject": "測試主旨",
        "explanation": "依據行政程序法辦理[^1]。",
        "provisions": "",
        "attachments": "",
        "references": "[^1]: [Level A] 行政程序法 | URL: https://law.moj.gov.tw/a",
    }

    result = engine.apply_template(req, sections)

    assert "### 參考來源 (AI 引用追蹤)" in result
    assert "**參考來源**：" not in result


def test_template_engine_apply_template_normalizes_legacy_reference_heading():
    """舊格式 heading 輸入應被正規化，不得重複輸出。"""
    engine = TemplateEngine()
    req = PublicDocRequirement(
        doc_type="函",
        sender="測試機關",
        receiver="測試單位",
        subject="測試主旨",
    )
    sections = {
        "subject": "測試主旨",
        "explanation": "依據行政程序法辦理[^1]。",
        "provisions": "",
        "attachments": "",
        "references": "**參考來源**：\n[^1]: [Level A] 行政程序法",
    }

    result = engine.apply_template(req, sections)

    assert result.count("### 參考來源 (AI 引用追蹤)") == 1
    assert "**參考來源**：" not in result


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


def test_writer_postprocess_adds_inline_citation_and_prunes_unused_refs(mock_llm):
    """有來源但無正文引用時，Writer 應補正文引用且只輸出實際使用的參考來源。"""
    kb_mock = MagicMock()
    kb_mock.search_hybrid.return_value = [
        {
            "id": "src-1",
            "content": "法規內容A",
            "metadata": {
                "title": "行政程序法",
                "source_level": "A",
                "source_url": "https://law.moj.gov.tw/a",
                "source": "law",
                "content_hash": "aaaaaaaaaaaaaaaa",
            },
            "distance": 0.2,
        },
        {
            "id": "src-2",
            "content": "法規內容B",
            "metadata": {
                "title": "中央法規標準法",
                "source_level": "A",
                "source_url": "https://law.moj.gov.tw/b",
                "source": "law",
                "content_hash": "bbbbbbbbbbbbbbbb",
            },
            "distance": 0.3,
        },
    ]

    writer = WriterAgent(mock_llm, kb_mock)
    mock_llm.generate.return_value = "### 主旨\n測試\n\n### 說明\n一、依據行政程序法規定辦理。"

    req = PublicDocRequirement(
        doc_type="函", sender="測試機關", receiver="測試單位", subject="測試主旨"
    )
    draft = writer.write_draft(req)

    # 正文引用應自動補上
    assert re.search(r"依據[^\n]{0,30}\[\^1\]", draft)
    # 只保留實際使用到的來源定義
    assert "[^1]:" in draft
    assert "[^2]:" not in draft


def test_writer_postprocess_removes_inline_footnote_definition(mock_llm):
    """正文中的 [^n]: 定義應被移除，改由文末參考來源統一管理。"""
    kb_mock = MagicMock()
    kb_mock.search_hybrid.return_value = [
        {
            "id": "src-1",
            "content": "法規內容A",
            "metadata": {
                "title": "行政程序法",
                "source_level": "A",
                "source_url": "https://law.moj.gov.tw/a",
                "source": "law",
                "content_hash": "aaaaaaaaaaaaaaaa",
            },
            "distance": 0.2,
        },
    ]

    writer = WriterAgent(mock_llm, kb_mock)
    mock_llm.generate.return_value = (
        "### 主旨\n測試\n\n### 說明\n一、依據行政程序法辦理[^9]。\n"
        "[^9]: 這是模型自行產生的定義，應被移除。"
    )

    req = PublicDocRequirement(
        doc_type="函", sender="測試機關", receiver="測試單位", subject="測試主旨"
    )
    draft = writer.write_draft(req)

    assert "[^9]:" not in draft
    assert "這是模型自行產生的定義" not in draft
    assert "### 參考來源 (AI 引用追蹤)" in draft
    assert "[^1]: [Level A] 行政程序法" in draft


def test_writer_open_notebook_path_uses_retrieved_evidence_for_reference_tracking(mock_llm, monkeypatch):
    """open-notebook writer path 應沿用實際 retrieval evidence，而非原 request docs。"""
    kb_mock = MagicMock()
    kb_mock.search_hybrid.return_value = [
        {
            "id": "src-1",
            "content": "法規內容A",
            "metadata": {
                "title": "原始 KB 範例",
                "source_level": "A",
                "source_url": "https://example.test/request-doc",
                "source": "law",
                "meta_id": "doc-1",
                "content_hash": "aaaaaaaaaaaaaaaa",
            },
            "distance": 0.2,
        },
    ]

    class FakeService:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def ask(self, request: OpenNotebookAskRequest) -> AskResult:
            return AskResult(
                answer_text="### 主旨\n測試\n\n### 說明\n一、依據行政程序法辦理[^1]。",
                evidence=[
                    RetrievedEvidence(
                        title="實際檢索證據",
                        snippet="依據行政程序法辦理。",
                        source_url="https://example.test/retrieved-doc",
                        rank=1,
                    )
                ],
                diagnostics={"adapter": "smoke"},
            )

    monkeypatch.setenv("GOV_AI_OPEN_NOTEBOOK_MODE", "smoke")
    monkeypatch.setattr("src.agents.writer.OpenNotebookService", FakeService)
    writer = WriterAgent(mock_llm, kb_mock)

    req = PublicDocRequirement(
        doc_type="函", sender="測試機關", receiver="測試單位", subject="測試主旨"
    )
    draft = writer.write_draft(req)

    assert "實際檢索證據" in draft
    assert "https://example.test/retrieved-doc" in draft
    assert "https://example.test/request-doc" not in draft
    assert writer._last_sources_list[0]["evidence_snippet"] == "依據行政程序法辦理。"


def test_writer_postprocess_strips_manual_reference_heading(mock_llm):
    """模型自行輸出的「參考來源」標題應移除，避免和系統重建段落重複。"""
    kb_mock = MagicMock()
    kb_mock.search_hybrid.return_value = [
        {
            "id": "src-1",
            "content": "法規內容A",
            "metadata": {
                "title": "行政程序法",
                "source_level": "A",
                "source_url": "https://law.moj.gov.tw/a",
                "source": "law",
                "content_hash": "aaaaaaaaaaaaaaaa",
            },
            "distance": 0.2,
        },
    ]

    writer = WriterAgent(mock_llm, kb_mock)
    mock_llm.generate.return_value = (
        "### 主旨\n測試\n\n### 說明\n一、依據行政程序法辦理[^1]。\n\n"
        "**參考來源**：\n[^1]: 這是模型自行輸出的定義。"
    )

    req = PublicDocRequirement(
        doc_type="函", sender="測試機關", receiver="測試單位", subject="測試主旨"
    )
    draft = writer.write_draft(req)

    assert "**參考來源**：" not in draft
    assert draft.count("### 參考來源 (AI 引用追蹤)") == 1
    assert "[^1]: 這是模型自行輸出的定義" not in draft


def test_writer_postprocess_sanitizes_placeholder_law_and_copy_units(mock_llm):
    """無法規來源時應降風險處理占位法條與副本占位機關。"""
    kb_mock = MagicMock()
    kb_mock.search_hybrid.return_value = [
        {
            "id": "src-1",
            "content": "範例內容",
            "metadata": {
                "title": "召開採購評選委員會議通知",
                "source_level": "A",
                "source_url": "https://example.test/source",
                "source": "example",
                "content_hash": "aaaaaaaaaaaaaaaa",
            },
            "distance": 0.2,
        },
    ]

    writer = WriterAgent(mock_llm, kb_mock)
    mock_llm.generate.return_value = (
        "### 主旨\n本部會議訂於115年5月6日召開，請各委員撥冗準時出席，請查照。\n\n"
        "### 說明\n一、依據○○法第○條規定辦理。\n\n"
        "### 辦法\n一、請依限辦理。\n\n"
        "正本：數位政府推動委員會各委員\n"
        "副本：○○司（處）、○○署等相關單位"
    )

    req = PublicDocRequirement(
        doc_type="函", sender="測試機關", receiver="測試單位", subject="測試主旨"
    )
    draft = writer.write_draft(req)

    assert "撥冗" not in draft
    assert "○○法" not in draft
    assert "第○條" not in draft
    assert (
        re.search(r"依本部行政作業流程辦理", draft)
        or re.search(r"為利業務推動與跨單位協調，特通知辦理本案\[\^1\]", draft)
    )
    assert "○○司（處）" not in draft
    assert "○○署" not in draft
    assert "相關司（處）" in draft


def test_writer_postprocess_adjusts_issue_date_before_meeting():
    """會議通知若出現時序衝突，發文日期應回調到會議日前。"""
    draft = (
        "**發文日期**：中華民國115年4月9日\n"
        "**主旨**：本部會議訂於114年3月5日召開，請各委員準時出席，請查照。"
    )
    normalized = WriterAgent._normalize_issue_date_before_meeting(draft)

    issue_match = re.search(r"\*\*發文日期\*\*：中華民國(\d+)年(\d+)月(\d+)日", normalized)
    meeting_match = re.search(r"訂於(\d+)年(\d+)月(\d+)日", normalized)
    assert issue_match is not None
    assert meeting_match is not None

    issue_tuple = tuple(int(issue_match.group(i)) for i in (1, 2, 3))
    meeting_tuple = tuple(int(meeting_match.group(i)) for i in (1, 2, 3))
    assert issue_tuple < meeting_tuple


def test_writer_postprocess_aligns_doc_number_year_after_date_adjustment():
    """發文日期回調時，發文字號年度也應同步更新。"""
    draft = (
        "**發文日期**：中華民國115年4月10日\n"
        "**發文字號**：數位發字第1150410001號\n"
        "**主旨**：本部會議訂於114年3月5日召開。"
    )
    normalized = WriterAgent._normalize_issue_date_before_meeting(draft)

    assert "**發文日期**：中華民國114年2月26日" in normalized
    assert "**發文字號**：數位發字第1140410001號" in normalized


def test_writer_postprocess_stabilizes_meeting_notice_fields():
    """會議通知缺少地點/附件時，應自動補齊並修正主旨語氣。"""
    draft = (
        "函\n\n"
        "**主旨**：檢送第5次會議通知，請查照並出席。\n\n"
        "**說明**：\n一、會議通知內容。"
    )
    normalized = WriterAgent._stabilize_meeting_notice_fields(draft)

    assert "請查照並準時出席" in normalized
    assert "會議地點：本部第一會議室。" in normalized
    assert "附件：會議通知及議程資料（隨函附送）" in normalized


def test_to_traditional_meeting_notice_common_chars():
    """會議通知常見簡體混用字應可轉成繁體。"""
    text = "预定讨論数位政府議题，开會当日請携带資料并於15分钟前报到，拨冗出席。"
    converted = to_traditional(text)
    assert "預定" in converted
    assert "討論" in converted
    assert "數位政府議題" in converted
    assert "開會當日" in converted
    assert "攜帶資料併於15分鐘前報到" in converted
    assert "撥冗出席" in converted


def test_writer_reference_title_normalized_for_meeting_context():
    """會議文稿若引用明顯不相關來源，應輸出中性追蹤標題。"""
    draft = "本案係第5次會議通知，請查照[^1]。"
    sources = [{
        "index": 1,
        "title": "函復國家賠償請求案",
        "source_level": "A",
        "source_url": "",
        "content_hash": "",
    }]
    lines = WriterAgent._build_reference_lines(draft, sources)

    assert len(lines) == 1
    assert "會議通知行政範本" in lines[0]
    assert "函復國家賠償請求案" not in lines[0]


def test_writer_reference_title_kept_for_non_meeting_context():
    """非會議情境下不應強制改寫來源標題。"""
    draft = "請各縣市政府依規定配合辦理淨零推動事項[^1]。"
    sources = [{
        "index": 1,
        "title": "函復國家賠償請求案",
        "source_level": "A",
        "source_url": "",
        "content_hash": "",
    }]
    lines = WriterAgent._build_reference_lines(draft, sources)

    assert len(lines) == 1
    assert "函復國家賠償請求案" in lines[0]
    assert "會議通知行政範本" not in lines[0]


def test_writer_stabilize_meeting_agenda_fills_missing_items():
    """議程僅有開頭時，應補齊討論事項與臨時動議。"""
    draft = "函\n\n**說明**：\n五、本次會議議程如下：\n（一）報告事項："
    normalized = WriterAgent._stabilize_meeting_agenda(draft)

    assert "（二）討論事項：" in normalized
    assert "（三）臨時動議。" in normalized


def test_writer_normalize_explanation_numbering_resequences():
    """說明段主項跳號時，應重排為連續編號。"""
    draft = "函\n\n**說明**：\n一、第一項。\n三、第三項。\n**辦法**：\n一、辦法。"
    normalized = WriterAgent._normalize_explanation_numbering(draft)

    assert "**說明**：\n一、第一項。\n二、第三項。" in normalized


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
    assert "flag as" in prompt_text


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


# ==================== ConsistencyChecker Enhanced Tests ====================

def test_consistency_checker_prompt_contains_detailed_checks(mock_llm):
    """測試 ConsistencyChecker 的 prompt 包含詳細的一致性檢查項目。"""
    checker = ConsistencyChecker(mock_llm)
    mock_llm.generate.return_value = '{"issues": [], "score": 0.95}'

    checker.check("### 主旨\n測試主旨\n### 說明\n測試說明")

    call_args = mock_llm.generate.call_args
    prompt_text = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
    # 驗證 prompt 包含核心檢查項目
    assert "Subject–Body Contradiction" in prompt_text
    assert "Numeric Inconsistency" in prompt_text
    assert "Date Contradiction" in prompt_text
    assert "Named Entity Mismatch" in prompt_text
    assert "Attachment Reference Mismatch" in prompt_text


def test_consistency_checker_prompt_has_severity_guidelines(mock_llm):
    """測試 ConsistencyChecker 的 prompt 包含嚴重度指引。"""
    checker = ConsistencyChecker(mock_llm)
    mock_llm.generate.return_value = '{"issues": [], "score": 0.95}'

    checker.check("### 主旨\n測試")

    call_args = mock_llm.generate.call_args
    prompt_text = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
    assert "Severity Guidelines" in prompt_text
    assert "What NOT to Flag" in prompt_text


def test_consistency_checker_prompt_has_examples(mock_llm):
    """測試 ConsistencyChecker 的 prompt 包含具體範例。"""
    checker = ConsistencyChecker(mock_llm)
    mock_llm.generate.return_value = '{"issues": [], "score": 0.95}'

    checker.check("### 主旨\n測試")

    call_args = mock_llm.generate.call_args
    prompt_text = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
    # 包含公文領域的具體範例
    assert "同意補助" in prompt_text
    assert "補助新臺幣" in prompt_text


def test_consistency_checker_detects_contradiction(mock_llm):
    """測試 ConsistencyChecker 能偵測主旨與說明矛盾。"""
    checker = ConsistencyChecker(mock_llm)
    mock_llm.generate.return_value = json.dumps({
        "issues": [{
            "severity": "error",
            "location": "主旨 vs 說明",
            "description": "主旨表示「同意補助」，但說明指出「不符合補助資格」",
            "suggestion": "統一主旨與說明的立場"
        }],
        "score": 0.3,
    })

    result = checker.check(
        "### 主旨\n同意補助新臺幣50萬元\n### 說明\n一、經審查不符合補助資格"
    )
    assert len(result.issues) == 1
    assert result.issues[0].severity == "error"
    assert result.issues[0].category == "consistency"


def test_consistency_checker_detects_numeric_mismatch(mock_llm):
    """測試 ConsistencyChecker 能偵測數字不一致。"""
    checker = ConsistencyChecker(mock_llm)
    mock_llm.generate.return_value = json.dumps({
        "issues": [{
            "severity": "error",
            "location": "主旨 vs 辦法",
            "description": "金額不一致：主旨為50萬元，辦法為30萬元",
            "suggestion": "請確認正確金額並統一"
        }],
        "score": 0.4,
    })

    result = checker.check(
        "### 主旨\n補助新臺幣50萬元\n### 辦法\n核定金額30萬元"
    )
    assert len(result.issues) == 1
    assert result.issues[0].severity == "error"


def test_consistency_checker_scope_delineation(mock_llm):
    """測試 ConsistencyChecker 的 prompt 明確劃分不檢查的範圍。"""
    checker = ConsistencyChecker(mock_llm)
    mock_llm.generate.return_value = '{"issues": [], "score": 0.95}'

    checker.check("### 主旨\n測試")

    call_args = mock_llm.generate.call_args
    prompt_text = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
    # 明確排除其他 Agent 的職責
    assert "Format Auditor" in prompt_text
    assert "Style Checker" in prompt_text
    assert "Fact Checker" in prompt_text
    assert "Compliance Checker" in prompt_text


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
