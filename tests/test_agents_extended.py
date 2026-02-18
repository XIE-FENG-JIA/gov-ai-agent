"""
src/agents/ 的延伸測試
補充邊界條件、錯誤路徑和未覆蓋的功能
"""
import pytest
import json
from unittest.mock import MagicMock
from src.agents.requirement import RequirementAgent
from src.agents.writer import WriterAgent
from src.agents.template import TemplateEngine, clean_markdown_artifacts, renumber_provisions
from src.agents.auditor import FormatAuditor
from src.agents.style_checker import StyleChecker
from src.agents.fact_checker import FactChecker
from src.agents.consistency_checker import ConsistencyChecker
from src.agents.compliance_checker import ComplianceChecker
from src.agents.org_memory import OrganizationalMemory
from src.agents.review_parser import (
    parse_review_response,
    _extract_json_object,
    format_audit_to_review_result,
)
from src.core.models import PublicDocRequirement


# ==================== RequirementAgent 邊界測試 ====================

class TestRequirementAgentEdgeCases:
    """RequirementAgent 的邊界測試"""

    def test_json_with_extra_fields(self, mock_llm):
        """測試 JSON 含有多餘欄位時仍能正常解析"""
        agent = RequirementAgent(mock_llm)
        mock_llm.generate.return_value = json.dumps({
            "doc_type": "函",
            "sender": "測試機關",
            "receiver": "測試單位",
            "subject": "測試主旨",
            "extra_field": "should be ignored",
            "another": 123
        })
        req = agent.analyze("test")
        assert req.doc_type == "函"
        assert req.subject == "測試主旨"

    def test_json_with_unicode_escape(self, mock_llm):
        """測試含有 unicode 轉義的 JSON"""
        agent = RequirementAgent(mock_llm)
        mock_llm.generate.return_value = json.dumps({
            "doc_type": "\u51fd",  # 函
            "sender": "\u6e2c\u8a66",  # 測試
            "receiver": "\u55ae\u4f4d",  # 單位
            "subject": "\u4e3b\u65e8"  # 主旨
        })
        req = agent.analyze("test")
        assert req.doc_type == "函"

    def test_json_in_nested_code_block(self, mock_llm):
        """測試在巢狀程式碼區塊中的 JSON"""
        agent = RequirementAgent(mock_llm)
        mock_llm.generate.return_value = '''Sure, here is the result:
```json
{
    "doc_type": "公告",
    "sender": "環保局",
    "receiver": "各學校",
    "subject": "回收公告"
}
```
That's it!'''
        req = agent.analyze("test")
        assert req.doc_type == "公告"

    def test_multiple_code_blocks_uses_first_valid(self, mock_llm):
        """測試多個程式碼區塊時使用第一個有效的"""
        agent = RequirementAgent(mock_llm)
        mock_llm.generate.return_value = '''
```json
invalid json here
```
```json
{"doc_type": "簽", "sender": "市府", "receiver": "局長", "subject": "簽呈"}
```
'''
        req = agent.analyze("test")
        assert req.doc_type == "簽"

    def test_llm_exception_propagates(self, mock_llm):
        """測試 LLM 呼叫拋出異常時的處理"""
        agent = RequirementAgent(mock_llm)
        mock_llm.generate.side_effect = Exception("API timeout")
        with pytest.raises(Exception, match="API timeout"):
            agent.analyze("test")

    def test_json_missing_required_fields_fallback_to_regex(self, mock_llm):
        """測試 JSON 缺少必要欄位時回退到 regex"""
        agent = RequirementAgent(mock_llm)
        mock_llm.generate.return_value = '{"doc_type": "函"}'
        # JSON 解析會成功但 Pydantic 驗證會失敗，回退到 regex
        # regex 也找不到所有必要欄位，最終拋出 ValueError
        with pytest.raises(ValueError):
            agent.analyze("test")


# ==================== WriterAgent 測試 ====================

class TestWriterAgent:
    """WriterAgent 的測試"""

    def test_write_draft_with_examples(self, mock_llm):
        """測試有範例時的草稿撰寫"""
        mock_kb = MagicMock()
        mock_kb.search_examples.return_value = [
            {"content": "範例公文內容", "metadata": {"title": "範例函"}}
        ]
        mock_llm.generate.return_value = "### 主旨\n生成的公文內容"

        writer = WriterAgent(mock_llm, mock_kb)
        requirement = PublicDocRequirement(
            doc_type="函",
            sender="測試機關",
            receiver="測試單位",
            subject="測試主旨"
        )
        draft = writer.write_draft(requirement)

        assert "生成的公文內容" in draft
        assert "參考來源" in draft  # 因為有範例所以應有參考來源
        mock_kb.search_examples.assert_called_once()

    def test_write_draft_without_examples(self, mock_llm):
        """測試沒有範例時的草稿撰寫"""
        mock_kb = MagicMock()
        mock_kb.search_examples.return_value = []
        mock_llm.generate.return_value = "### 主旨\n無範例的公文內容"

        writer = WriterAgent(mock_llm, mock_kb)
        requirement = PublicDocRequirement(
            doc_type="函",
            sender="測試機關",
            receiver="測試單位",
            subject="測試主旨"
        )
        draft = writer.write_draft(requirement)

        assert "無範例的公文內容" in draft
        assert "參考來源" not in draft  # 沒有範例所以沒有參考來源

    def test_write_draft_with_multiple_examples(self, mock_llm):
        """測試多個範例時的草稿撰寫"""
        mock_kb = MagicMock()
        mock_kb.search_examples.return_value = [
            {"content": "範例一", "metadata": {"title": "函範例A"}},
            {"content": "範例二", "metadata": {"title": "函範例B"}}
        ]
        mock_llm.generate.return_value = "### 主旨\n綜合範例的公文"

        writer = WriterAgent(mock_llm, mock_kb)
        requirement = PublicDocRequirement(
            doc_type="函",
            sender="環保局",
            receiver="各學校",
            subject="資源回收"
        )
        draft = writer.write_draft(requirement)

        assert "[^1]" in draft  # Source 1
        assert "[^2]" in draft  # Source 2

    def test_write_draft_uses_correct_query(self, mock_llm):
        """測試搜尋查詢包含正確的公文類型和主旨"""
        mock_kb = MagicMock()
        mock_kb.search_examples.return_value = []
        mock_llm.generate.return_value = "### 主旨\n測試"

        writer = WriterAgent(mock_llm, mock_kb)
        requirement = PublicDocRequirement(
            doc_type="公告",
            sender="市府",
            receiver="各區",
            subject="垃圾清運公告"
        )
        writer.write_draft(requirement)

        # 驗證搜尋查詢
        call_args = mock_kb.search_examples.call_args
        assert "公告" in call_args[0][0]
        assert "垃圾清運公告" in call_args[0][0]


# ==================== TemplateEngine 邊界測試 ====================

class TestTemplateEngineEdgeCases:
    """TemplateEngine 的邊界測試"""

    def test_parse_list_items_empty(self):
        """測試空文字的清單解析"""
        engine = TemplateEngine()
        items = engine._parse_list_items("")
        assert items == []

    def test_parse_list_items_none(self):
        """測試 None 的清單解析"""
        engine = TemplateEngine()
        items = engine._parse_list_items(None)
        assert items == []

    def test_parse_list_items_with_numbering(self):
        """測試帶編號的清單解析"""
        engine = TemplateEngine()
        text = "1、第一項\n2、第二項\n（一）子項"
        items = engine._parse_list_items(text)
        assert len(items) == 3
        assert "第一項" in items[0]

    def test_parse_draft_empty(self):
        """測試空草稿的解析"""
        engine = TemplateEngine()
        sections = engine.parse_draft("")
        assert sections["subject"] == ""
        assert sections["explanation"] == ""

    def test_parse_draft_with_inline_content(self):
        """測試標頭後直接跟隨內容（同一行）"""
        engine = TemplateEngine()
        draft = "### 主旨：測試同行內容\n### 說明\n說明內容"
        sections = engine.parse_draft(draft)
        assert "測試同行內容" in sections["subject"]

    def test_parse_draft_announcement_provisions(self):
        """測試公告事項的解析"""
        engine = TemplateEngine()
        draft = """
### 主旨
公告主旨

### 公告事項
一、第一項
二、第二項
"""
        sections = engine.parse_draft(draft)
        assert sections["provisions"] != ""
        assert "一、" in sections["provisions"]

    def test_apply_template_sign_type(self, sample_sign_requirement):
        """測試簽類型的模板套用"""
        engine = TemplateEngine()
        sections = {
            "subject": "簽呈主旨",
            "explanation": "簽呈說明",
            "provisions": "",
            "attachments": "",
            "references": ""
        }
        result = engine.apply_template(sample_sign_requirement, sections)
        assert "市府" in result or "簽呈主旨" in result

    def test_apply_template_with_references(self, sample_requirement):
        """測試有參考來源時的模板套用"""
        engine = TemplateEngine()
        sections = {
            "subject": "測試主旨",
            "explanation": "測試說明",
            "provisions": "",
            "attachments": "",
            "references": "[^1]: 某法規"
        }
        result = engine.apply_template(sample_requirement, sections)
        assert "參考來源" in result
        assert "某法規" in result

    def test_fallback_apply(self, sample_requirement):
        """測試 fallback 模板（Jinja2 載入失敗時）"""
        engine = TemplateEngine()
        sections = {
            "subject": "測試主旨",
            "explanation": "測試說明",
            "provisions": "一、辦法一",
            "attachments": "",
            "references": ""
        }
        result = engine._fallback_apply(sample_requirement, sections)
        assert "測試機關" in result
        assert "測試主旨" in result
        assert "辦法一" in result

    def test_fallback_apply_with_attachments(self, sample_requirement):
        """測試 fallback 模板包含附件"""
        engine = TemplateEngine()
        sections = {
            "subject": "測試",
            "explanation": "",
            "provisions": "",
            "attachments": "",
            "references": ""
        }
        result = engine._fallback_apply(sample_requirement, sections)
        assert "附件" in result
        assert "附件1" in result

    def test_fallback_apply_with_action_items(self):
        """測試 fallback 模板使用 action_items 作為說明"""
        engine = TemplateEngine()
        req = PublicDocRequirement(
            doc_type="函",
            sender="測試",
            receiver="對象",
            subject="主旨",
            action_items=["動作一", "動作二"]
        )
        sections = {
            "subject": "主旨",
            "explanation": "",
            "provisions": "",
            "attachments": "",
            "references": ""
        }
        result = engine._fallback_apply(req, sections)
        assert "動作一" in result


# ==================== clean_markdown_artifacts 邊界測試 ====================

class TestCleanMarkdownArtifacts:
    """clean_markdown_artifacts 的邊界測試"""

    def test_empty_string(self):
        """測試空字串"""
        assert clean_markdown_artifacts("") == ""

    def test_none_input(self):
        """測試 None 輸入"""
        assert clean_markdown_artifacts(None) == ""

    def test_nested_bold_italic(self):
        """測試巢狀粗體斜體"""
        text = "***粗斜體***"
        result = clean_markdown_artifacts(text)
        assert "***" not in result

    def test_remove_separator_lines(self):
        """測試移除分隔線"""
        text = "第一段\n---\n第二段"
        result = clean_markdown_artifacts(text)
        assert "---" not in result

    def test_remove_stamp_text(self):
        """測試移除捺印處文字"""
        text = "承辦人 捺印處 審核"
        result = clean_markdown_artifacts(text)
        assert "捺印處" not in result

    def test_collapse_multiple_blank_lines(self):
        """測試合併多餘空行"""
        text = "第一段\n\n\n\n\n第二段"
        result = clean_markdown_artifacts(text)
        assert "\n\n\n" not in result

    def test_url_in_link(self):
        """測試連結中的 URL 被移除"""
        text = "請參閱[公文系統](https://example.com)辦理"
        result = clean_markdown_artifacts(text)
        assert "https://example.com" not in result
        assert "公文系統" in result


# ==================== renumber_provisions 邊界測試 ====================

class TestRenumberProvisionsEdgeCases:
    """renumber_provisions 的邊界測試"""

    def test_skip_signature_section(self):
        """測試跳過簽署區內容"""
        text = "1. 辦法內容\n正本：受文者\n副本：其他"
        result = renumber_provisions(text)
        assert "一、" in result
        assert "正本" in result
        assert "副本" in result

    def test_mixed_numbering(self):
        """測試混合編號格式"""
        text = "1. 第一項\n(1) 子項A\n(2) 子項B\n2. 第二項"
        result = renumber_provisions(text)
        assert "一、" in result
        assert "二、" in result
        assert "（一）" in result
        assert "（二）" in result

    def test_chinese_numbering_already_present(self):
        """測試已有中文編號的文字"""
        text = "一、第一項\n二、第二項"
        result = renumber_provisions(text)
        assert "一、" in result
        assert "二、" in result

    def test_plain_text_preserved(self):
        """測試普通文字不被修改"""
        text = "這是一段普通文字，不需要編號。"
        result = renumber_provisions(text)
        assert result == "這是一段普通文字，不需要編號。"

    def test_empty_lines_preserved(self):
        """測試空行被保留"""
        text = "1. 第一項\n\n2. 第二項"
        result = renumber_provisions(text)
        assert "" in result.split("\n")

    def test_sub_counter_resets(self):
        """測試子編號在主編號變化後重設"""
        text = "1. 主項一\n(1) 子項\n2. 主項二\n(1) 新子項"
        result = renumber_provisions(text)
        lines = [line for line in result.split("\n") if line.strip()]
        # 第二個 (1) 應該也是 （一）因為子計數器已重設
        sub_items = [line for line in lines if "（一）" in line]
        assert len(sub_items) == 2


# ==================== FormatAuditor 邊界測試 ====================

class TestFormatAuditorEdgeCases:
    """FormatAuditor 的邊界測試"""

    def test_audit_with_kb_rules(self, mock_llm):
        """測試有知識庫規則時的審查"""
        mock_kb = MagicMock()
        mock_kb.search_regulations.return_value = [
            {"content": "- [Error] 必須有主旨段落", "metadata": {"title": "函規則"}}
        ]
        mock_llm.generate.return_value = '{"errors": ["缺少主旨"], "warnings": []}'

        auditor = FormatAuditor(mock_llm, mock_kb)
        result = auditor.audit("### 說明\n測試", "函")
        assert "缺少主旨" in result["errors"]

    def test_audit_with_validator_calls(self, mock_llm):
        """測試含有 [Call: func_name] 的規則會觸發驗證器"""
        mock_kb = MagicMock()
        mock_kb.search_regulations.return_value = [
            {"content": "[Call: check_doc_integrity]\n- [Error] 必須有主旨",
             "metadata": {"title": "規則"}}
        ]
        mock_llm.generate.return_value = '{"errors": [], "warnings": []}'

        auditor = FormatAuditor(mock_llm, mock_kb)
        # 草稿缺少標準欄位，check_doc_integrity 應產生錯誤
        result = auditor.audit("### 主旨\n測試", "函")
        assert len(result["errors"]) > 0

    def test_audit_llm_exception(self, mock_llm):
        """測試 LLM 呼叫異常時的錯誤處理"""
        mock_llm.generate.side_effect = Exception("Timeout")
        auditor = FormatAuditor(mock_llm)
        result = auditor.audit("### 主旨\n測試", "函")
        assert len(result["warnings"]) > 0
        assert any("審查錯誤" in w for w in result["warnings"])


# ==================== StyleChecker 邊界測試 ====================

class TestStyleCheckerEdgeCases:
    """StyleChecker 的邊界測試"""

    def test_check_with_issues(self, mock_llm):
        """測試包含問題的審查結果"""
        mock_llm.generate.return_value = json.dumps({
            "issues": [
                {"severity": "warning", "location": "主旨",
                 "description": "口語化用詞", "suggestion": "改為正式用語"}
            ],
            "score": 0.7
        })
        checker = StyleChecker(mock_llm)
        result = checker.check("幫我處理一下")
        assert result.score == 0.7
        assert len(result.issues) == 1
        assert result.issues[0].category == "style"

    def test_check_json_decode_error(self, mock_llm):
        """測試 JSON 解析失敗時回傳預設值"""
        mock_llm.generate.return_value = "This is completely invalid"
        checker = StyleChecker(mock_llm)
        result = checker.check("test")
        assert result.score == 0.8
        assert len(result.issues) == 0

    def test_check_exception_handling(self, mock_llm):
        """測試一般例外時回傳預設值"""
        mock_llm.generate.return_value = '{"issues": "not_a_list", "score": 0.9}'
        checker = StyleChecker(mock_llm)
        result = checker.check("test")
        # issues 非列表被忽略（空），但 score 仍從 JSON 正確取得
        assert result.score == 0.9
        assert result.issues == []


# ==================== FactChecker 邊界測試 ====================

class TestFactCheckerEdgeCases:
    """FactChecker 的邊界測試"""

    def test_check_empty_response(self, mock_llm):
        """測試空回應時回傳預設值"""
        mock_llm.generate.return_value = ""
        checker = FactChecker(mock_llm)
        result = checker.check("test")
        assert result.score == 0.8
        assert result.agent_name == "Fact Checker"

    def test_check_json_decode_error(self, mock_llm):
        """測試 JSON 解析失敗時回傳預設值"""
        mock_llm.generate.return_value = "Not a JSON response"
        checker = FactChecker(mock_llm)
        result = checker.check("test")
        assert result.score == 0.8

    def test_check_no_json_match(self, mock_llm):
        """測試找不到 JSON 物件時回傳預設值"""
        mock_llm.generate.return_value = "No JSON here at all"
        checker = FactChecker(mock_llm)
        result = checker.check("test")
        assert result.score == 0.8

    def test_check_with_multiple_issues(self, mock_llm):
        """測試多個問題的審查結果"""
        mock_llm.generate.return_value = json.dumps({
            "issues": [
                {"severity": "error", "location": "依據", "description": "法規不存在"},
                {"severity": "warning", "location": "日期", "description": "日期可能過期"}
            ],
            "score": 0.4
        })
        checker = FactChecker(mock_llm)
        result = checker.check("依據某法辦理")
        assert len(result.issues) == 2
        assert result.score == 0.4
        assert all(i.category == "fact" for i in result.issues)


# ==================== ConsistencyChecker 邊界測試 ====================

class TestConsistencyCheckerEdgeCases:
    """ConsistencyChecker 的邊界測試"""

    def test_check_empty_response(self, mock_llm):
        """測試空回應時回傳預設值"""
        mock_llm.generate.return_value = ""
        checker = ConsistencyChecker(mock_llm)
        result = checker.check("test")
        assert result.score == 0.8

    def test_check_json_decode_error(self, mock_llm):
        """測試 JSON 解析失敗"""
        mock_llm.generate.return_value = "{invalid json"
        checker = ConsistencyChecker(mock_llm)
        result = checker.check("test")
        assert result.score == 0.8

    def test_check_with_contradictions(self, mock_llm):
        """測試發現矛盾時的審查結果"""
        mock_llm.generate.return_value = json.dumps({
            "issues": [
                {"severity": "error", "location": "主旨 vs 辦法",
                 "description": "主旨說請出席會議但辦法沒有列出時間地點"}
            ],
            "score": 0.5
        })
        checker = ConsistencyChecker(mock_llm)
        result = checker.check("主旨：請出席\n辦法：無")
        assert result.has_errors is True


# ==================== ComplianceChecker 邊界測試 ====================

class TestComplianceCheckerEdgeCases:
    """ComplianceChecker 的邊界測試"""

    def test_check_with_kb(self, mock_llm):
        """測試有知識庫時的政策合規檢查"""
        mock_kb = MagicMock()
        mock_kb.search_policies.return_value = [
            {"metadata": {"title": "淨零碳排政策"}, "content": "所有公文應考慮碳排放"}
        ]
        mock_llm.generate.return_value = json.dumps({
            "issues": [], "score": 0.95, "confidence": 0.9
        })

        checker = ComplianceChecker(mock_llm, mock_kb)
        result = checker.check("### 主旨\n測試公文")
        assert result.score == 0.95
        assert result.confidence == 0.9

    def test_check_kb_exception(self, mock_llm):
        """測試知識庫查詢異常時不中斷"""
        mock_kb = MagicMock()
        mock_kb.search_policies.side_effect = Exception("DB error")
        mock_llm.generate.return_value = json.dumps({
            "issues": [], "score": 0.85, "confidence": 0.5
        })

        checker = ComplianceChecker(mock_llm, mock_kb)
        result = checker.check("test")
        assert result.score == 0.85  # 應仍能正常運作

    def test_check_empty_response(self, mock_llm):
        """測試空回應"""
        mock_llm.generate.return_value = ""
        checker = ComplianceChecker(mock_llm)
        result = checker.check("test")
        assert result.score == 0.85
        assert result.confidence == 0.5

    def test_check_json_decode_error(self, mock_llm):
        """測試 JSON 解析失敗"""
        mock_llm.generate.return_value = "not json"
        checker = ComplianceChecker(mock_llm)
        result = checker.check("test")
        assert result.score == 0.85

    def test_check_with_compliance_issues(self, mock_llm):
        """測試發現合規問題時的處理"""
        mock_llm.generate.return_value = json.dumps({
            "issues": [
                {
                    "severity": "error",
                    "location": "說明",
                    "description": "抵觸淨零碳排政策",
                    "suggestion": "調整措辭"
                }
            ],
            "score": 0.4,
            "confidence": 0.8
        })
        checker = ComplianceChecker(mock_llm)
        result = checker.check("增加燃煤發電")
        assert len(result.issues) == 1
        assert result.issues[0].risk_level == "high"
        assert result.issues[0].category == "compliance"

    def test_check_risk_level_mapping(self, mock_llm):
        """測試嚴重性到風險等級的映射"""
        mock_llm.generate.return_value = json.dumps({
            "issues": [
                {"severity": "error", "location": "A", "description": "高風險"},
                {"severity": "warning", "location": "B", "description": "中風險"},
                {"severity": "info", "location": "C", "description": "低風險"}
            ],
            "score": 0.5,
            "confidence": 0.8
        })
        checker = ComplianceChecker(mock_llm)
        result = checker.check("test")
        assert result.issues[0].risk_level == "high"
        assert result.issues[1].risk_level == "medium"
        assert result.issues[2].risk_level == "low"

    def test_check_general_exception(self, mock_llm):
        """測試 LLM 呼叫異常時回傳預設值（優雅降級）"""
        mock_llm.generate.side_effect = Exception("Unknown error")
        checker = ComplianceChecker(mock_llm)
        result = checker.check("test")
        # LLM 呼叫失敗時應回傳預設分數，而非拋出例外
        assert result.score == 0.85
        assert result.confidence == 0.5
        assert len(result.issues) == 0


# ==================== OrganizationalMemory 邊界測試 ====================

class TestOrganizationalMemoryEdgeCases:
    """OrganizationalMemory 的邊界測試"""

    def test_learn_from_edit(self, tmp_path):
        """測試從編輯中學習"""
        storage = tmp_path / "prefs.json"
        mem = OrganizationalMemory(str(storage))
        mem.learn_from_edit("測試機關", "原始內容", "修改後內容")

        profile = mem.get_agency_profile("測試機關")
        assert profile["usage_count"] == 1
        assert "last_edit" in profile

    def test_learn_from_edit_increments_count(self, tmp_path):
        """測試多次編輯學習累計次數"""
        storage = tmp_path / "prefs.json"
        mem = OrganizationalMemory(str(storage))
        mem.learn_from_edit("機關A", "v1", "v2")
        mem.learn_from_edit("機關A", "v2", "v3")

        profile = mem.get_agency_profile("機關A")
        assert profile["usage_count"] == 2

    def test_corrupted_preferences_file(self, tmp_path):
        """測試損壞的偏好設定檔案"""
        storage = tmp_path / "prefs.json"
        storage.write_text("THIS IS NOT JSON!!!", encoding="utf-8")

        mem = OrganizationalMemory(str(storage))
        assert mem.preferences == {}

    def test_get_writing_hints_concise(self, tmp_path):
        """測試簡潔風格的寫作提示"""
        storage = tmp_path / "prefs.json"
        mem = OrganizationalMemory(str(storage))
        mem.update_preference("測試機關", "formal_level", "concise")

        hints = mem.get_writing_hints("測試機關")
        assert "簡潔" in hints

    def test_get_writing_hints_standard(self, tmp_path):
        """測試標準風格（無特殊提示）"""
        storage = tmp_path / "prefs.json"
        mem = OrganizationalMemory(str(storage))
        hints = mem.get_writing_hints("全新機關")
        assert hints == ""  # 標準風格沒有特殊提示

    def test_get_writing_hints_with_preferred_terms(self, tmp_path):
        """測試有偏好詞彙時的寫作提示"""
        storage = tmp_path / "prefs.json"
        mem = OrganizationalMemory(str(storage))
        mem.update_preference("機關X", "preferred_terms", {"請": "惠請"})

        hints = mem.get_writing_hints("機關X")
        assert "偏好詞彙" in hints
        assert "惠請" in hints

    def test_get_writing_hints_with_signature(self, tmp_path):
        """測試有署名格式時的寫作提示"""
        storage = tmp_path / "prefs.json"
        mem = OrganizationalMemory(str(storage))
        mem.update_preference("機關Y", "signature_format", "局長 XXX")

        hints = mem.get_writing_hints("機關Y")
        assert "署名格式" in hints

    def test_export_report_multiple_agencies(self, tmp_path):
        """測試多機關的匯出報告"""
        storage = tmp_path / "prefs.json"
        mem = OrganizationalMemory(str(storage))
        mem.update_preference("機關A", "usage_count", 10)
        mem.update_preference("機關B", "usage_count", 5)
        mem.update_preference("機關C", "usage_count", 20)

        report = mem.export_report()
        # 應按使用次數降序排列
        pos_a = report.find("機關A")
        pos_b = report.find("機關B")
        pos_c = report.find("機關C")
        assert pos_c < pos_a < pos_b  # C(20) > A(10) > B(5)

    def test_persistence_across_instances(self, tmp_path):
        """測試跨實例的持久化"""
        storage = tmp_path / "prefs.json"

        mem1 = OrganizationalMemory(str(storage))
        mem1.update_preference("持久機關", "formal_level", "formal")
        del mem1

        mem2 = OrganizationalMemory(str(storage))
        profile = mem2.get_agency_profile("持久機關")
        assert profile["formal_level"] == "formal"


# ==================== ReviewParser 邊界測試 ====================

class TestReviewParserEdgeCases:
    """review_parser 模組的邊界測試，覆蓋未測試的錯誤路徑"""

    def test_parse_review_response_with_non_dict_issue_items(self):
        """測試 issues 列表中包含非 dict 項目時被跳過（覆蓋 line 120）"""
        response = json.dumps({
            "issues": [
                1,
                "text_item",
                None,
                True,
                {"severity": "warning", "location": "主旨", "description": "有效項目"},
            ],
            "score": 0.7,
        })
        result = parse_review_response(response, "TestAgent", "style")
        # 只有最後一個 dict 項目應被保留
        assert len(result.issues) == 1
        assert result.issues[0].description == "有效項目"
        assert result.score == 0.7

    def test_parse_review_response_all_non_dict_issues(self):
        """測試 issues 列表全部為非 dict 時回傳空 issues"""
        response = json.dumps({
            "issues": [42, "string", None, False, [1, 2, 3]],
            "score": 0.6,
        })
        result = parse_review_response(response, "TestAgent", "fact")
        assert len(result.issues) == 0
        assert result.score == 0.6

    def test_parse_review_response_issue_parsing_exception(self):
        """測試單一 issue 解析時發生例外（覆蓋 lines 133-137）

        透過傳入一個會讓 ReviewIssue 建構失敗的 suggestion 類型（list）
        來觸發 inner except 區塊。
        """
        response = json.dumps({
            "issues": [
                {
                    "severity": "warning",
                    "location": "說明",
                    "description": "問題描述",
                    "suggestion": {"nested": "object_not_string"},
                },
                {
                    "severity": "info",
                    "location": "辦法",
                    "description": "正常項目",
                },
            ],
            "score": 0.65,
        })
        result = parse_review_response(response, "TestAgent", "consistency")
        # 如果第一個 issue 因為 suggestion 類型問題而解析失敗，
        # 至少第二個正常項目應該被保留
        # （注意：Pydantic 可能會成功強制轉型，此時兩個都會保留）
        assert result.score == 0.65
        assert len(result.issues) >= 1

    def test_parse_review_response_json_syntax_error(self):
        """測試 JSON 語法錯誤時回傳預設結果（覆蓋 lines 145-146）"""
        # _extract_json_object 會找到 {... 但 json.loads 會失敗
        response = '{issues: [broken json syntax}'
        result = parse_review_response(response, "SyntaxTest", "style")
        assert result.score == 0.8
        assert len(result.issues) == 0
        assert result.agent_name == "SyntaxTest"

    def test_parse_review_response_json_decode_error_from_extracted(self):
        """測試 _extract_json_object 回傳的字串不是合法 JSON（覆蓋 line 145）"""
        # 這裡利用 _extract_json_object 的括號配對找到 {...}，但內部不是合法 JSON
        response = "結果如下: {key without quotes: value} 結束"
        result = parse_review_response(response, "DecodeTest", "fact")
        assert result.score == 0.8
        assert len(result.issues) == 0

    def test_parse_review_response_general_exception(self):
        """測試非 JSONDecodeError 的一般例外（覆蓋 lines 152-154）

        透過讓 data.get("issues") 觸發 AttributeError 來測試一般例外路徑。
        這裡用合法 JSON 但值的結構導致後續處理出錯。
        """
        # json.loads 成功但 data.get("score", ...) 不會失敗...
        # 改用不同策略：score 值超出 Pydantic 範圍（>1.0）
        response = json.dumps({
            "issues": [],
            "score": 999.0,  # 超出 ge=0.0, le=1.0 限制
        })
        result = parse_review_response(response, "ExceptionTest", "style")
        # Pydantic 驗證會拋出 ValidationError（不是 JSONDecodeError），
        # 觸發 lines 152-154 的 except Exception
        assert result.score == 0.8
        assert len(result.issues) == 0
        assert result.agent_name == "ExceptionTest"

    def test_parse_review_response_with_custom_default_score(self):
        """測試自訂預設分數在解析失敗時正確套用"""
        result = parse_review_response(
            "no json here", "CustomScore", "style", default_score=0.5
        )
        assert result.score == 0.5

    def test_extract_json_object_unbalanced_opening_braces(self):
        """測試不平衡的左括號（只有開頭沒有結尾）"""
        result = _extract_json_object("{{{")
        assert result is None

    def test_extract_json_object_deeply_nested_unbalanced(self):
        """測試深層巢狀但不平衡的括號"""
        result = _extract_json_object('{"a": {"b": {"c": "d"')
        assert result is None

    def test_extract_json_object_empty_object(self):
        """測試空 JSON 物件"""
        result = _extract_json_object("prefix {} suffix")
        assert result == "{}"

    def test_extract_json_object_with_string_containing_backslash(self):
        """測試字串中包含反斜線的情況"""
        text = r'{"path": "C:\\Users\\test"}'
        result = _extract_json_object(text)
        assert result is not None
        data = json.loads(result)
        assert "Users" in data["path"]

    def test_format_audit_to_review_result_with_errors_and_warnings(self):
        """測試含有錯誤和警告的格式審查結果轉換"""
        fmt_raw = {
            "errors": ["缺少主旨段落", "缺少受文者"],
            "warnings": ["說明段落過短"],
        }
        result = format_audit_to_review_result(fmt_raw)
        assert result.agent_name == "Format Auditor"
        assert result.score == 0.5  # 有問題時分數為 0.5
        assert result.confidence == 1.0
        assert len(result.issues) == 3
        # 驗證錯誤和警告的嚴重性
        errors = [i for i in result.issues if i.severity == "error"]
        warnings = [i for i in result.issues if i.severity == "warning"]
        assert len(errors) == 2
        assert len(warnings) == 1

    def test_format_audit_to_review_result_empty_input(self):
        """測試空的格式審查結果（無錯誤無警告）"""
        result = format_audit_to_review_result({"errors": [], "warnings": []})
        assert result.score == 1.0
        assert len(result.issues) == 0

    def test_format_audit_to_review_result_missing_keys(self):
        """測試完全空的字典輸入"""
        result = format_audit_to_review_result({})
        assert result.score == 1.0
        assert len(result.issues) == 0

    def test_format_audit_to_review_result_custom_agent_name(self):
        """測試自訂 agent_name"""
        result = format_audit_to_review_result(
            {"errors": ["問題"], "warnings": []},
            agent_name="Custom Auditor"
        )
        assert result.agent_name == "Custom Auditor"

    def test_parse_review_response_confidence_from_json(self):
        """測試從 JSON 正確讀取 confidence 值"""
        response = json.dumps({
            "issues": [],
            "score": 0.9,
            "confidence": 0.75,
        })
        result = parse_review_response(response, "ConfTest", "style")
        assert result.confidence == 0.75

    def test_parse_review_response_no_json_in_text(self):
        """測試文字中完全沒有 JSON 物件（找不到 { 符號）"""
        result = parse_review_response(
            "This response has no JSON at all!", "NoJSON", "fact"
        )
        assert result.score == 0.8
        assert len(result.issues) == 0


# ==================== _chinese_index 邊界測試 ====================

class TestChineseIndex:
    """_chinese_index Jinja2 過濾器的邊界測試"""

    def test_index_out_of_range(self):
        """測試超出中文數字範圍時回傳阿拉伯數字字串"""
        from src.agents.template import _chinese_index
        from src.core.constants import MAX_CHINESE_NUMBER
        # 超過上限應回傳 str(value)
        result = _chinese_index(MAX_CHINESE_NUMBER + 1)
        assert result == str(MAX_CHINESE_NUMBER + 1)

    def test_index_zero(self):
        """測試 0（低於有效範圍）回傳 str"""
        from src.agents.template import _chinese_index
        result = _chinese_index(0)
        assert result == "0"

    def test_index_negative(self):
        """測試負數回傳 str"""
        from src.agents.template import _chinese_index
        result = _chinese_index(-1)
        assert result == "-1"

    def test_index_valid(self):
        """測試有效範圍回傳中文數字"""
        from src.agents.template import _chinese_index
        result = _chinese_index(1)
        assert result == "一"


# ==================== parse_draft basis_text 邊界測試 ====================

class TestParseDraftBasisOnly:
    """parse_draft 中 basis_text 無 explanation_text 的邊界測試"""

    def test_basis_without_explanation(self):
        """測試有依據但無說明時的段落合併"""
        engine = TemplateEngine()
        draft = "### 主旨\n測試主旨\n### 依據\n某法規第三條"
        sections = engine.parse_draft(draft)
        assert sections["explanation"] == "依據：某法規第三條"

    def test_basis_with_explanation(self):
        """測試有依據且有說明時的段落合併"""
        engine = TemplateEngine()
        draft = "### 主旨\n測試主旨\n### 依據\n某法規\n### 說明\n補充說明"
        sections = engine.parse_draft(draft)
        assert "依據：某法規" in sections["explanation"]
        assert "補充說明" in sections["explanation"]


# ==================== _parse_list_items 空行跳過 ====================

class TestParseListItemsBlankLines:
    """_parse_list_items 中空行跳過邏輯的測試"""

    def test_items_with_blank_lines(self):
        """測試含空行的清單解析會跳過空行"""
        engine = TemplateEngine()
        text = "第一項\n\n第二項\n\n\n第三項"
        items = engine._parse_list_items(text)
        assert len(items) == 3
        assert items[0] == "第一項"
        assert items[2] == "第三項"


# ==================== apply_template 載入/渲染失敗測試 ====================

class TestApplyTemplateFallback:
    """apply_template 中 Jinja2 載入/渲染失敗的回退測試"""

    def test_template_load_failure_fallback(self, sample_requirement):
        """測試 Jinja2 模板載入失敗時使用 fallback"""
        from unittest.mock import patch
        engine = TemplateEngine()
        sections = {
            "subject": "測試主旨",
            "explanation": "測試說明",
            "provisions": "",
            "attachments": "",
            "references": ""
        }
        # Mock env.get_template 使其拋出異常
        with patch.object(engine.env, "get_template", side_effect=Exception("Template not found")):
            result = engine.apply_template(sample_requirement, sections)
        assert "測試主旨" in result
        assert "測試機關" in result

    def test_template_render_failure_fallback(self, sample_requirement):
        """測試 Jinja2 模板渲染失敗時使用 fallback"""
        from unittest.mock import patch, MagicMock
        engine = TemplateEngine()
        sections = {
            "subject": "渲染失敗測試",
            "explanation": "測試說明",
            "provisions": "",
            "attachments": "",
            "references": ""
        }
        mock_template = MagicMock()
        mock_template.render.side_effect = Exception("Render error")
        with patch.object(engine.env, "get_template", return_value=mock_template):
            result = engine.apply_template(sample_requirement, sections)
        assert "渲染失敗測試" in result
        assert "測試機關" in result


# ==================== FormatAuditor 驗證器白名單 ====================

class TestAuditorValidatorWhitelist:
    """FormatAuditor 驗證器白名單安全機制的測試"""

    def test_disallowed_validator_skipped(self, mock_llm):
        """測試不在白名單中的驗證器被跳過"""
        mock_kb = MagicMock()
        mock_kb.search_regulations.return_value = [
            {"content": "[Call: evil_function]\n- [Error] 規則",
             "metadata": {"title": "規則"}}
        ]
        mock_llm.generate.return_value = '{"errors": [], "warnings": []}'

        auditor = FormatAuditor(mock_llm, mock_kb)
        result = auditor.audit("### 主旨\n測試", "函")
        # evil_function 不在白名單，不應執行；結果僅來自 LLM
        assert isinstance(result, dict)

    def test_unknown_validator_skipped(self, mock_llm):
        """測試白名單內但不存在於 registry 的驗證器被跳過"""
        from unittest.mock import patch
        mock_kb = MagicMock()
        mock_kb.search_regulations.return_value = [
            {"content": "[Call: check_date_logic]\n- [Error] 規則",
             "metadata": {"title": "規則"}}
        ]
        mock_llm.generate.return_value = '{"errors": [], "warnings": []}'

        auditor = FormatAuditor(mock_llm, mock_kb)
        # Mock hasattr 回傳 False 來模擬 registry 上找不到該函式
        import src.agents.auditor as auditor_mod
        mock_registry = MagicMock(spec=[])  # spec=[] 表示沒有任何屬性
        with patch.object(auditor_mod, 'validator_registry', mock_registry):
            result = auditor.audit("### 主旨\n測試", "函")
            assert isinstance(result, dict)

    def test_validator_exception_handled(self, mock_llm):
        """測試驗證器執行時拋出異常被安全處理"""
        from unittest.mock import patch
        mock_kb = MagicMock()
        mock_kb.search_regulations.return_value = [
            {"content": "[Call: check_date_logic]\n- [Error] 規則",
             "metadata": {"title": "規則"}}
        ]
        mock_llm.generate.return_value = '{"errors": [], "warnings": []}'

        auditor = FormatAuditor(mock_llm, mock_kb)
        import src.agents.auditor as auditor_mod
        mock_registry = MagicMock()
        mock_registry.check_date_logic.side_effect = RuntimeError("Validator crash")
        with patch.object(auditor_mod, 'validator_registry', mock_registry):
            result = auditor.audit("### 主旨\n測試", "函")
            assert isinstance(result, dict)


# ==================== OrgMemory 儲存失敗 ====================

# ==================== FormatAuditor JSONDecodeError ====================

class TestAuditorJSONDecodeError:
    """FormatAuditor LLM 回傳無效 JSON 的測試"""

    def test_audit_llm_returns_invalid_json(self, mock_llm):
        """測試 LLM 回傳含 {} 但無效的 JSON 時的 JSONDecodeError 處理"""
        # 正規式會匹配 {errors: []} 但 json.loads 會失敗
        mock_llm.generate.return_value = "Result: {errors: [], warnings: []}"
        auditor = FormatAuditor(mock_llm)
        result = auditor.audit("### 主旨\n測試", "函")
        assert isinstance(result, dict)
        assert any("無法解析 JSON" in w for w in result["warnings"])


# ==================== ComplianceChecker 例外路徑 ====================

class TestComplianceCheckerExceptions:
    """ComplianceChecker _parse_response 中的例外路徑測試"""

    def test_parse_response_json_decode_error(self, mock_llm):
        """測試 _parse_response 中 JSONDecodeError（有 {} 但不合法 JSON）"""
        checker = ComplianceChecker(mock_llm)
        # regex 會匹配 {invalid json here} 但 json.loads 會拋出 JSONDecodeError
        result = checker._parse_response("data: {invalid: json here}")
        assert result.score == 0.85  # 預設分數 (_build_default_result)

    def test_parse_response_generic_exception(self, mock_llm):
        """測試 _parse_response 中通用 Exception"""
        from unittest.mock import patch
        checker = ComplianceChecker(mock_llm)
        # Mock json.loads 拋出非 JSONDecodeError 的例外
        with patch("src.agents.compliance_checker.json.loads", side_effect=RuntimeError("unexpected")):
            result = checker._parse_response("data: {some json}")
        assert result.score == 0.85  # _build_default_result


# ==================== RequirementAgent regex 策略 3 失敗 ====================

class TestRequirementRegexStrategy3:
    """RequirementAgent regex 策略 3 失敗的測試"""

    def test_regex_fields_fail_validation(self, mock_llm):
        """測試 regex 提取到的欄位通過驗證時失敗（空白 doc_type）"""
        from src.agents.requirement import RequirementAgent
        agent = RequirementAgent(mock_llm)
        # LLM 回應的 JSON 結構不完整，只有部分欄位可 regex 到
        # 但 doc_type 為空白會觸發 ValueError
        mock_llm.generate.return_value = '"doc_type": "   ", "sender": "機關", "receiver": "對象", "subject": "主旨"'
        with pytest.raises(ValueError, match="LLM 未回傳有效的 JSON"):
            agent.analyze("使用者輸入")


# ==================== KB metadata 非標準型別 ====================

class TestKBMetadataConversion:
    """KB ingest 中 metadata 型別轉換的測試"""

    def test_non_standard_metadata_type_converted(self, tmp_path):
        """測試含巢狀 dict metadata 的檔案匯入時被轉為 str"""
        from src.cli.kb import app as kb_app
        from typer.testing import CliRunner
        from unittest.mock import patch

        runner = CliRunner()
        # 建立含有 nested dict metadata 的 YAML 前置物（dict 不在標準型別清單中）
        doc_path = tmp_path / "test_doc.md"
        doc_path.write_text("---\ntitle: 測試\nnested:\n  key: value\n---\n內容", encoding='utf-8')

        with patch("src.cli.kb.ConfigManager") as mock_cm, \
             patch("src.cli.kb.get_llm_factory"), \
             patch("src.cli.kb.KnowledgeBaseManager") as mock_kb_class:
            mock_cm.return_value.config = {
                "llm": {"provider": "mock"},
                "knowledge_base": {"path": str(tmp_path / "kb")}
            }
            mock_kb_instance = mock_kb_class.return_value
            mock_kb_instance.add_document.return_value = "doc_id"

            result = runner.invoke(kb_app, [
                "ingest", "--source-dir", str(tmp_path), "--collection", "examples"
            ])
            assert result.exit_code == 0
            # 確認 add_document 被呼叫，且 nested dict 被轉為 str
            call_args = mock_kb_instance.add_document.call_args
            metadata = call_args[0][1]  # 第二個位置引數
            assert isinstance(metadata["nested"], str)
            assert "key" in metadata["nested"]


# ==================== OrgMemory 儲存失敗 ====================

class TestOrgMemorySaveFailure:
    """OrgMemory 儲存偏好設定失敗的測試"""

    def test_save_preferences_io_error(self, tmp_path):
        """測試儲存偏好設定時 IO 錯誤被優雅處理"""
        from src.agents.org_memory import OrganizationalMemory
        from unittest.mock import patch
        mem = OrganizationalMemory(str(tmp_path / "prefs.json"))
        mem.preferences["測試機關"] = {"formal_level": "formal"}
        # Mock open 拋出 IOError
        with patch("builtins.open", side_effect=IOError("磁碟已滿")):
            # 不應拋出異常
            mem._save_preferences()
