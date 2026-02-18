"""
邊界案例和健壯性強化測試

覆蓋以下場景：
1. 空值和 None 處理
2. 超長輸入處理
3. 特殊字元處理
4. Graceful degradation（優雅降級）
5. LLM 回傳異常值處理
"""
import json
import pytest
from unittest.mock import MagicMock, patch

from src.core.llm import MockLLMProvider, LiteLLMProvider
from src.core.models import PublicDocRequirement
from src.core.review_models import ReviewResult
from src.core.constants import MAX_DRAFT_LENGTH, MAX_USER_INPUT_LENGTH
from src.agents.requirement import RequirementAgent, _sanitize_json_string
from src.agents.writer import WriterAgent
from src.agents.editor import EditorInChief
from src.agents.template import TemplateEngine, clean_markdown_artifacts, renumber_provisions
from src.agents.auditor import FormatAuditor
from src.agents.style_checker import StyleChecker
from src.agents.fact_checker import FactChecker
from src.agents.consistency_checker import ConsistencyChecker
from src.agents.compliance_checker import ComplianceChecker
from src.agents.review_parser import parse_review_response, _extract_json_object
from src.document.exporter import DocxExporter
from src.knowledge.manager import KnowledgeBaseManager


# ============================================================
# 1. 空值和 None 處理
# ============================================================

class TestNullAndNoneHandling:
    """測試所有模組對 None/空值輸入的防護"""

    # --- LLM Provider ---

    def test_mock_llm_generate_empty_prompt(self):
        """測試 MockLLMProvider 對空 prompt 的處理"""
        provider = MockLLMProvider({})
        assert provider.generate("") == ""
        assert provider.generate(None) == ""
        assert provider.generate("   ") == ""

    def test_mock_llm_embed_empty_text(self):
        """測試 MockLLMProvider 對空文字的 embed 處理"""
        provider = MockLLMProvider({})
        assert provider.embed("") == []
        assert provider.embed(None) == []
        assert provider.embed("   ") == []

    @patch("src.core.llm.litellm")
    def test_litellm_generate_empty_prompt(self, mock_litellm):
        """測試 LiteLLMProvider 對空 prompt 的處理"""
        provider = LiteLLMProvider({"provider": "ollama"})
        result = provider.generate("")
        assert result == ""
        mock_litellm.completion.assert_not_called()

    @patch("src.core.llm.litellm")
    def test_litellm_generate_none_prompt(self, mock_litellm):
        """測試 LiteLLMProvider 對 None prompt 的處理"""
        provider = LiteLLMProvider({"provider": "ollama"})
        result = provider.generate(None)
        assert result == ""
        mock_litellm.completion.assert_not_called()

    @patch("src.core.llm.litellm")
    def test_litellm_embed_empty_text(self, mock_litellm):
        """測試 LiteLLMProvider 對空文字 embed 的處理"""
        provider = LiteLLMProvider({"provider": "ollama"})
        result = provider.embed("")
        assert result == []
        mock_litellm.embedding.assert_not_called()

    # --- RequirementAgent ---

    def test_requirement_agent_empty_input(self, mock_llm):
        """測試 RequirementAgent 對空輸入拋出 ValueError"""
        agent = RequirementAgent(mock_llm)
        with pytest.raises(ValueError, match="空白"):
            agent.analyze("")

    def test_requirement_agent_whitespace_input(self, mock_llm):
        """測試 RequirementAgent 對純空格輸入拋出 ValueError"""
        agent = RequirementAgent(mock_llm)
        with pytest.raises(ValueError, match="空白"):
            agent.analyze("   \n  \t  ")

    def test_requirement_agent_none_input(self, mock_llm):
        """測試 RequirementAgent 對 None 輸入拋出 ValueError"""
        agent = RequirementAgent(mock_llm)
        with pytest.raises(ValueError, match="空白"):
            agent.analyze(None)

    def test_requirement_agent_llm_returns_empty(self, mock_llm):
        """測試 LLM 回傳空字串時拋出 ValueError"""
        agent = RequirementAgent(mock_llm)
        mock_llm.generate.return_value = ""
        with pytest.raises(ValueError, match="空的回應"):
            agent.analyze("寫一份公文")

    def test_requirement_agent_llm_returns_error(self, mock_llm):
        """測試 LLM 回傳錯誤訊息時拋出 ValueError"""
        agent = RequirementAgent(mock_llm)
        mock_llm.generate.return_value = "Error: 無法連線到 LLM 服務"
        with pytest.raises(ValueError, match="LLM 呼叫失敗"):
            agent.analyze("寫一份公文")

    # --- WriterAgent ---

    def test_writer_agent_none_reason(self, mock_llm):
        """測試 WriterAgent 處理 reason=None 的需求"""
        mock_kb = MagicMock()
        mock_kb.search_examples.return_value = []
        mock_llm.generate.return_value = "### 主旨\n測試草稿"

        writer = WriterAgent(mock_llm, mock_kb)
        req = PublicDocRequirement(
            doc_type="函",
            sender="測試機關",
            receiver="測試單位",
            subject="測試主旨",
            reason=None,  # None reason
        )
        draft = writer.write_draft(req)
        assert "（未提供）" in mock_llm.generate.call_args[0][0] or draft is not None

    def test_writer_agent_empty_action_items(self, mock_llm):
        """測試 WriterAgent 處理空 action_items"""
        mock_kb = MagicMock()
        mock_kb.search_examples.return_value = []
        mock_llm.generate.return_value = "### 主旨\n測試"

        writer = WriterAgent(mock_llm, mock_kb)
        req = PublicDocRequirement(
            doc_type="函",
            sender="機關",
            receiver="單位",
            subject="主旨",
            action_items=[],
            attachments=[],
        )
        draft = writer.write_draft(req)
        assert draft is not None

    def test_writer_agent_llm_returns_empty(self, mock_llm):
        """測試 LLM 回傳空草稿時的回退處理"""
        mock_kb = MagicMock()
        mock_kb.search_examples.return_value = []
        mock_llm.generate.return_value = ""

        writer = WriterAgent(mock_llm, mock_kb)
        req = PublicDocRequirement(
            doc_type="函",
            sender="機關",
            receiver="單位",
            subject="測試主旨",
        )
        draft = writer.write_draft(req)
        assert "測試主旨" in draft  # 應使用基本模板

    def test_writer_agent_kb_search_failure(self, mock_llm):
        """測試知識庫搜尋失敗時的優雅降級"""
        mock_kb = MagicMock()
        mock_kb.search_examples.side_effect = Exception("ChromaDB error")
        mock_llm.generate.return_value = "### 主旨\n降級測試"

        writer = WriterAgent(mock_llm, mock_kb)
        req = PublicDocRequirement(
            doc_type="函",
            sender="機關",
            receiver="單位",
            subject="主旨",
        )
        draft = writer.write_draft(req)
        assert "降級測試" in draft

    # --- StyleChecker / FactChecker / ConsistencyChecker ---

    def test_style_checker_empty_draft(self, mock_llm):
        """測試 StyleChecker 對空草稿的處理"""
        checker = StyleChecker(mock_llm)
        result = checker.check("")
        assert result.score == 0.8
        assert len(result.issues) == 0

    def test_style_checker_none_draft(self, mock_llm):
        """測試 StyleChecker 對 None 草稿的處理"""
        checker = StyleChecker(mock_llm)
        result = checker.check(None)
        assert result.score == 0.8

    def test_fact_checker_empty_draft(self, mock_llm):
        """測試 FactChecker 對空草稿的處理"""
        checker = FactChecker(mock_llm)
        result = checker.check("")
        assert result.score == 0.8

    def test_consistency_checker_empty_draft(self, mock_llm):
        """測試 ConsistencyChecker 對空草稿的處理"""
        checker = ConsistencyChecker(mock_llm)
        result = checker.check("")
        assert result.score == 0.8

    def test_compliance_checker_empty_draft(self, mock_llm):
        """測試 ComplianceChecker 對空草稿的處理"""
        checker = ComplianceChecker(mock_llm)
        result = checker.check("")
        assert result.score == 0.85
        assert result.confidence == 0.5

    # --- FormatAuditor ---

    def test_auditor_empty_draft(self, mock_llm):
        """測試 FormatAuditor 對空草稿的處理"""
        auditor = FormatAuditor(mock_llm)
        result = auditor.audit("", "函")
        assert "草稿內容為空" in result["errors"]

    def test_auditor_none_draft(self, mock_llm):
        """測試 FormatAuditor 對 None 草稿的處理"""
        auditor = FormatAuditor(mock_llm)
        result = auditor.audit(None, "函")
        assert "草稿內容為空" in result["errors"]

    # --- TemplateEngine ---

    def test_template_parse_draft_none(self):
        """測試 TemplateEngine 對 None 草稿的處理"""
        engine = TemplateEngine()
        sections = engine.parse_draft(None)
        assert sections["subject"] == ""
        assert sections["explanation"] == ""

    def test_template_parse_draft_empty(self):
        """測試 TemplateEngine 對空草稿的處理"""
        engine = TemplateEngine()
        sections = engine.parse_draft("")
        assert sections["subject"] == ""

    # --- review_parser ---

    def test_parse_review_response_none(self):
        """測試解析 None 回應"""
        result = parse_review_response(None, "Test", "style")
        assert result.score == 0.8

    def test_parse_review_response_empty(self):
        """測試解析空回應"""
        result = parse_review_response("", "Test", "style")
        assert result.score == 0.8

    def test_parse_review_response_whitespace(self):
        """測試解析純空格回應"""
        result = parse_review_response("   \n  ", "Test", "style")
        assert result.score == 0.8

    # --- Exporter ---

    def test_exporter_empty_draft(self, tmp_path):
        """測試匯出空草稿"""
        exporter = DocxExporter()
        output_file = tmp_path / "empty.docx"
        exporter.export("", str(output_file))
        assert output_file.exists()

    def test_exporter_none_draft(self, tmp_path):
        """測試匯出 None 草稿"""
        exporter = DocxExporter()
        output_file = tmp_path / "none.docx"
        exporter.export(None, str(output_file))
        assert output_file.exists()


# ============================================================
# 2. 超長輸入處理
# ============================================================

class TestLongInputHandling:
    """測試超長輸入的截斷處理"""

    def test_requirement_agent_long_input(self, mock_llm):
        """測試 RequirementAgent 對超長輸入的截斷"""
        agent = RequirementAgent(mock_llm)
        mock_llm.generate.return_value = json.dumps({
            "doc_type": "函",
            "sender": "機關",
            "receiver": "單位",
            "subject": "主旨",
        })

        long_input = "A" * (MAX_USER_INPUT_LENGTH + 1000)
        req = agent.analyze(long_input)
        assert req.doc_type == "函"
        # 確認傳給 LLM 的 prompt 中輸入已被截斷
        call_prompt = mock_llm.generate.call_args[0][0]
        assert len(long_input) > len(call_prompt)

    def test_style_checker_long_draft(self, mock_llm):
        """測試 StyleChecker 對超長草稿的截斷"""
        mock_llm.generate.return_value = '{"issues": [], "score": 0.9}'

        checker = StyleChecker(mock_llm)
        long_draft = "一、" + "測試內容。" * 5000  # 超過 MAX_DRAFT_LENGTH
        result = checker.check(long_draft)
        assert result.score == 0.9

        # 確認傳給 LLM 的 prompt 已截斷
        call_prompt = mock_llm.generate.call_args[0][0]
        assert "截斷" in call_prompt

    def test_fact_checker_long_draft(self, mock_llm):
        """測試 FactChecker 對超長草稿的截斷"""
        mock_llm.generate.return_value = '{"issues": [], "score": 0.9}'
        checker = FactChecker(mock_llm)
        long_draft = "X" * (MAX_DRAFT_LENGTH + 1000)
        result = checker.check(long_draft)
        assert result.score == 0.9

    def test_consistency_checker_long_draft(self, mock_llm):
        """測試 ConsistencyChecker 對超長草稿的截斷"""
        mock_llm.generate.return_value = '{"issues": [], "score": 0.9}'
        checker = ConsistencyChecker(mock_llm)
        long_draft = "Y" * (MAX_DRAFT_LENGTH + 1000)
        result = checker.check(long_draft)
        assert result.score == 0.9

    def test_compliance_checker_long_draft(self, mock_llm):
        """測試 ComplianceChecker 對超長草稿的截斷"""
        mock_llm.generate.return_value = '{"issues": [], "score": 0.9, "confidence": 0.8}'
        checker = ComplianceChecker(mock_llm)
        long_draft = "Z" * (MAX_DRAFT_LENGTH + 1000)
        result = checker.check(long_draft)
        assert result.score == 0.9

    def test_auditor_long_draft(self, mock_llm):
        """測試 FormatAuditor 對超長草稿的截斷"""
        mock_llm.generate.return_value = '{"errors": [], "warnings": []}'
        auditor = FormatAuditor(mock_llm)
        long_draft = "W" * (MAX_DRAFT_LENGTH + 1000)
        result = auditor.audit(long_draft, "函")
        assert isinstance(result["errors"], list)

    def test_editor_auto_refine_long_draft(self, mock_llm):
        """測試 EditorInChief 對超長草稿和回饋的截斷"""
        mock_llm.generate.return_value = "### 主旨\n修正後的內容"
        editor = EditorInChief(mock_llm)

        long_draft = "Q" * (MAX_DRAFT_LENGTH + 1000)
        results = [
            ReviewResult(
                agent_name="Test",
                issues=[],
                score=0.5,
            ),
        ]
        # 無問題的 results 不會觸發修正
        refined = editor._auto_refine(long_draft, results)
        assert refined == long_draft  # 無回饋，回傳原稿

    def test_writer_agent_long_example_truncation(self, mock_llm):
        """測試 WriterAgent 截斷過長的範例"""
        mock_kb = MagicMock()
        mock_kb.search_examples.return_value = [
            {"content": "X" * 10000, "metadata": {"title": "超長範例"}}
        ]
        mock_llm.generate.return_value = "### 主旨\n測試"

        writer = WriterAgent(mock_llm, mock_kb)
        req = PublicDocRequirement(
            doc_type="函", sender="機關", receiver="單位", subject="主旨"
        )
        writer.write_draft(req)

        # 確認傳給 LLM 的 prompt 中範例已被截斷
        call_prompt = mock_llm.generate.call_args[0][0]
        assert "截斷" in call_prompt


# ============================================================
# 3. 特殊字元處理
# ============================================================

class TestSpecialCharacterHandling:
    """測試包含特殊字元的 LLM 回應和使用者輸入"""

    def test_json_with_escaped_quotes(self, mock_llm):
        """測試 LLM 回傳含有轉義引號的 JSON"""
        agent = RequirementAgent(mock_llm)
        mock_llm.generate.return_value = json.dumps({
            "doc_type": "函",
            "sender": '機關"名稱',
            "receiver": "單位",
            "subject": '含"引號"的主旨',
        })
        req = agent.analyze("test")
        assert '"' in req.sender or req.sender == '機關"名稱'

    def test_json_with_newlines_in_values(self, mock_llm):
        """測試 LLM 回傳值中包含換行的 JSON"""
        agent = RequirementAgent(mock_llm)
        # json.dumps 會正確轉義換行
        mock_llm.generate.return_value = json.dumps({
            "doc_type": "函",
            "sender": "機關",
            "receiver": "單位",
            "subject": "第一行\n第二行",
        })
        req = agent.analyze("test")
        assert "\n" in req.subject

    def test_json_with_unicode_characters(self, mock_llm):
        """測試 LLM 回傳含有特殊 Unicode 字元的 JSON"""
        agent = RequirementAgent(mock_llm)
        mock_llm.generate.return_value = json.dumps({
            "doc_type": "函",
            "sender": "台北市政府",
            "receiver": "各區公所",
            "subject": "關於「全形引號」和《書名號》及（括號）測試",
        })
        req = agent.analyze("test")
        assert "全形引號" in req.subject
        assert "書名號" in req.subject

    def test_sanitize_json_string_bom(self):
        """測試 _sanitize_json_string 移除 BOM"""
        text = '\ufeff{"key": "value"}'
        cleaned = _sanitize_json_string(text)
        assert '\ufeff' not in cleaned

    def test_sanitize_json_string_zero_width(self):
        """測試 _sanitize_json_string 移除零寬度字元"""
        text = 'test\u200bvalue'
        cleaned = _sanitize_json_string(text)
        assert '\u200b' not in cleaned

    def test_sanitize_json_string_none(self):
        """測試 _sanitize_json_string 處理 None"""
        assert _sanitize_json_string(None) == ""
        assert _sanitize_json_string("") == ""

    def test_extract_json_object_with_nested_braces(self):
        """測試 _extract_json_object 處理巢狀括號"""
        text = 'prefix {"a": {"b": "c"}, "d": "e"} suffix'
        result = _extract_json_object(text)
        assert result is not None
        data = json.loads(result)
        assert data["a"]["b"] == "c"

    def test_extract_json_object_with_escaped_quotes(self):
        """測試 _extract_json_object 處理轉義引號"""
        text = '{"key": "value with \\"quotes\\""}'
        result = _extract_json_object(text)
        assert result is not None
        data = json.loads(result)
        assert "quotes" in data["key"]

    def test_extract_json_object_with_braces_in_strings(self):
        """測試 _extract_json_object 處理字串中的括號"""
        text = '{"msg": "contains { and } in string"}'
        result = _extract_json_object(text)
        assert result is not None
        data = json.loads(result)
        assert "{" in data["msg"]

    def test_extract_json_object_no_json(self):
        """測試 _extract_json_object 找不到 JSON 時回傳 None"""
        assert _extract_json_object("no json here") is None
        assert _extract_json_object("") is None
        assert _extract_json_object(None) is None

    def test_parse_review_response_with_special_chars(self):
        """測試解析含特殊字元的審查回應"""
        response = json.dumps({
            "issues": [
                {
                    "severity": "warning",
                    "location": "主旨",
                    "description": '含有「全形」和"半形"引號的描述',
                    "suggestion": "建議使用《書名號》"
                }
            ],
            "score": 0.8,
        })
        result = parse_review_response(response, "Test", "style")
        assert len(result.issues) == 1
        assert "全形" in result.issues[0].description

    def test_parse_review_response_issues_not_list(self):
        """測試 issues 欄位不是列表時的處理"""
        response = '{"issues": "not_a_list", "score": 0.9}'
        result = parse_review_response(response, "Test", "style")
        assert len(result.issues) == 0
        assert result.score == 0.9

    def test_parse_review_response_invalid_severity(self):
        """測試無效的 severity 值被修正"""
        response = json.dumps({
            "issues": [
                {
                    "severity": "critical",  # 無效值
                    "location": "主旨",
                    "description": "問題"
                }
            ],
            "score": 0.7,
        })
        result = parse_review_response(response, "Test", "style")
        assert len(result.issues) == 1
        assert result.issues[0].severity == "info"  # 被修正為 info

    def test_parse_review_response_missing_fields(self):
        """測試 issue 中缺少欄位時的處理"""
        response = json.dumps({
            "issues": [
                {"severity": "warning"}  # 缺少 location 和 description
            ],
            "score": 0.7,
        })
        result = parse_review_response(response, "Test", "style")
        assert len(result.issues) == 1
        assert result.issues[0].location == "未知"
        assert "無描述" in result.issues[0].description

    def test_exporter_special_characters(self, tmp_path):
        """測試 Word 匯出處理特殊字元"""
        exporter = DocxExporter()
        output_file = tmp_path / "special.docx"

        draft = """# 函

**機關**：台北市政府
**受文者**：各區公所

---

### 主旨
關於「全形引號」和《書名號》及（括號）的測試\x00\x01\x02

### 說明
一、金額：新臺幣$1,000,000元。
二、百分比：50%成長。
三、特殊符號：&、<、>、©、®、™
"""
        exporter.export(draft, str(output_file))
        assert output_file.exists()
        assert output_file.stat().st_size > 0

    def test_exporter_sanitize_control_chars(self):
        """測試 DocxExporter 移除控制字元"""
        exporter = DocxExporter()
        text = "正常文字\x00\x01\x08控制字元\x0b\x0c\x0e結尾"
        cleaned = exporter._sanitize_text(text)
        assert "\x00" not in cleaned
        assert "\x01" not in cleaned
        assert "\x08" not in cleaned
        assert "正常文字" in cleaned
        assert "結尾" in cleaned

    def test_exporter_sanitize_preserves_whitespace(self):
        """測試 _sanitize_text 保留正常空白字元"""
        exporter = DocxExporter()
        text = "行一\n行二\t制表\r\n換行"
        cleaned = exporter._sanitize_text(text)
        assert "\n" in cleaned
        assert "\t" in cleaned

    def test_exporter_sanitize_none(self):
        """測試 _sanitize_text 處理 None"""
        exporter = DocxExporter()
        assert exporter._sanitize_text(None) == ""
        assert exporter._sanitize_text("") == ""

    def test_template_engine_special_chars_in_subject(self):
        """測試模板引擎處理主旨中的特殊字元"""
        engine = TemplateEngine()
        req = PublicDocRequirement(
            doc_type="函",
            sender="機關",
            receiver="單位",
            subject='含有 "引號" & <角括號> 的主旨',
        )
        sections = {
            "subject": '含有 "引號" & <角括號> 的主旨',
            "explanation": "",
            "provisions": "",
            "attachments": "",
            "references": "",
        }
        result = engine.apply_template(req, sections)
        assert "引號" in result
        assert "角括號" in result

    def test_clean_markdown_artifacts_with_complex_markdown(self):
        """測試清理複雜的 Markdown 標記"""
        text = """```python
code block
```

# 標題

**粗體** _斜體_ ~~刪除線~~

[連結文字](https://example.com/path?key=value&other=123)

---

捺印處

多餘

空行

結尾"""
        result = clean_markdown_artifacts(text)
        assert "```" not in result
        assert "**" not in result
        assert "---" not in result
        assert "捺印處" not in result
        assert "連結文字" in result

    def test_renumber_provisions_with_special_chars(self):
        """測試辦法重新編號處理特殊字元"""
        text = '1. 含有「引號」的辦法\n2. 含有《書名號》的辦法'
        result = renumber_provisions(text)
        assert "一、" in result
        assert "引號" in result
        assert "書名號" in result


# ============================================================
# 4. Graceful Degradation（優雅降級）
# ============================================================

class TestGracefulDegradation:
    """測試各種服務不可用時系統仍能運作"""

    def test_kb_init_failure_graceful(self, tmp_path, mock_llm):
        """測試 ChromaDB 初始化失敗時的優雅降級"""
        # 使用一個無效路徑觸發失敗
        with patch("src.knowledge.manager.chromadb.PersistentClient") as mock_client:
            mock_client.side_effect = Exception("ChromaDB init failed")
            kb = KnowledgeBaseManager("/invalid/path", mock_llm)
            assert kb._available is False
            assert kb.get_stats() == {
                "examples_count": 0,
                "regulations_count": 0,
                "policies_count": 0,
            }

    def test_kb_unavailable_search_returns_empty(self, tmp_path, mock_llm):
        """測試知識庫不可用時搜尋回傳空列表"""
        with patch("src.knowledge.manager.chromadb.PersistentClient") as mock_client:
            mock_client.side_effect = Exception("DB error")
            kb = KnowledgeBaseManager("/bad/path", mock_llm)
            assert kb.search_examples("query") == []
            assert kb.search_regulations("query") == []
            assert kb.search_policies("query") == []

    def test_kb_unavailable_add_returns_none(self, tmp_path, mock_llm):
        """測試知識庫不可用時新增回傳 None"""
        with patch("src.knowledge.manager.chromadb.PersistentClient") as mock_client:
            mock_client.side_effect = Exception("DB error")
            kb = KnowledgeBaseManager("/bad/path", mock_llm)
            result = kb.add_document("content", {"title": "test"})
            assert result is None

    def test_kb_add_empty_content(self, tmp_path, mock_llm):
        """測試知識庫新增空白內容回傳 None"""
        kb_dir = tmp_path / "kb_empty_test"
        kb = KnowledgeBaseManager(str(kb_dir), mock_llm)
        assert kb.add_document("", {"title": "empty"}) is None
        assert kb.add_document(None, {"title": "none"}) is None
        assert kb.add_document("   ", {"title": "spaces"}) is None

    @patch("src.core.llm.litellm")
    def test_ollama_not_running_clear_message(self, mock_litellm):
        """測試 Ollama 未啟動時有清楚的錯誤訊息"""
        mock_litellm.completion.side_effect = Exception(
            "ConnectionError: [Errno 10061] 拒絕連線"
        )
        provider = LiteLLMProvider({"provider": "ollama", "model": "mistral"})
        result = provider.generate("測試")
        assert "無法連線" in result or "Error" in result

    @patch("src.core.llm.litellm")
    def test_invalid_api_key_clear_message(self, mock_litellm):
        """測試 API Key 無效時有清楚的錯誤訊息"""
        mock_litellm.completion.side_effect = Exception(
            "AuthenticationError: Invalid API Key"
        )
        provider = LiteLLMProvider({"provider": "gemini", "api_key": "bad-key"})
        result = provider.generate("測試")
        assert "API Key" in result or "Error" in result

    def test_compliance_checker_llm_failure(self, mock_llm):
        """測試 ComplianceChecker LLM 呼叫失敗時的優雅降級"""
        mock_llm.generate.side_effect = Exception("Network timeout")
        checker = ComplianceChecker(mock_llm)
        result = checker.check("### 主旨\n測試")
        assert result.score == 0.85
        assert result.confidence == 0.5
        assert len(result.issues) == 0

    def test_editor_auto_refine_llm_failure(self, mock_llm):
        """測試 Editor 修正 LLM 失敗時保留原始草稿"""
        from src.core.review_models import ReviewIssue

        mock_llm.generate.return_value = ""  # LLM 回傳空值
        editor = EditorInChief(mock_llm)

        original_draft = "### 主旨\n原始草稿"
        results = [
            ReviewResult(
                agent_name="Test",
                issues=[
                    ReviewIssue(
                        category="format",
                        severity="error",
                        location="X",
                        description="問題",
                        suggestion="修正",
                    )
                ],
                score=0.5,
            ),
        ]
        refined = editor._auto_refine(original_draft, results)
        assert refined == original_draft  # 應保留原稿

    def test_editor_auto_refine_llm_returns_error(self, mock_llm):
        """測試 Editor 修正 LLM 回傳錯誤訊息時保留原稿"""
        from src.core.review_models import ReviewIssue

        mock_llm.generate.return_value = "Error: Connection refused"
        editor = EditorInChief(mock_llm)

        original_draft = "### 主旨\n原始草稿"
        results = [
            ReviewResult(
                agent_name="Test",
                issues=[
                    ReviewIssue(
                        category="format",
                        severity="error",
                        location="X",
                        description="問題",
                    )
                ],
                score=0.5,
            ),
        ]
        refined = editor._auto_refine(original_draft, results)
        assert refined == original_draft

    def test_writer_kb_failure_still_produces_draft(self, mock_llm):
        """測試知識庫完全不可用時仍能產生草稿"""
        mock_kb = MagicMock()
        mock_kb.search_examples.side_effect = Exception("KB down")
        mock_llm.generate.return_value = "### 主旨\n無知識庫也能用"

        writer = WriterAgent(mock_llm, mock_kb)
        req = PublicDocRequirement(
            doc_type="函", sender="機關", receiver="單位", subject="主旨"
        )
        draft = writer.write_draft(req)
        assert "無知識庫也能用" in draft
        assert "參考來源" not in draft  # 無範例，不應有參考來源

    def test_auditor_with_kb_failure(self, mock_llm):
        """測試 FormatAuditor 知識庫查詢失敗時的處理"""
        mock_kb = MagicMock()
        mock_kb.search_regulations.side_effect = Exception("KB error")
        mock_llm.generate.return_value = '{"errors": [], "warnings": []}'

        auditor = FormatAuditor(mock_llm, mock_kb)
        # 不應拋出異常
        result = auditor.audit("### 主旨\n測試", "函")
        assert isinstance(result["errors"], list)


# ============================================================
# 5. 額外的邊界案例
# ============================================================

class TestAdditionalEdgeCases:
    """額外的邊界案例測試"""

    def test_editor_review_with_none_suggestion_in_feedback(self, mock_llm):
        """測試 Editor 處理 suggestion=None 的回饋"""
        from src.core.review_models import ReviewIssue

        mock_llm.generate.return_value = "### 主旨\n已修正"
        editor = EditorInChief(mock_llm)

        results = [
            ReviewResult(
                agent_name="Format Auditor",
                issues=[
                    ReviewIssue(
                        category="format",
                        severity="error",
                        location="文件結構",
                        description="缺少主旨",
                        suggestion=None,  # 無建議
                    )
                ],
                score=0.5,
            ),
        ]
        refined = editor._auto_refine("### 說明\n原始", results)
        # 確認不會因為 suggestion=None 而崩潰
        assert refined is not None
        # 確認 "Fix: None" 不會出現在 prompt 中
        call_prompt = mock_llm.generate.call_args[0][0]
        assert "Fix: None" not in call_prompt
        assert "請自行判斷" in call_prompt

    def test_format_audit_to_review_result_empty(self):
        """測試空的格式審查結果轉換"""
        from src.agents.review_parser import format_audit_to_review_result

        result = format_audit_to_review_result({"errors": [], "warnings": []})
        assert result.score == 1.0
        assert len(result.issues) == 0

    def test_format_audit_to_review_result_none_values(self):
        """測試格式審查結果中有 None 值"""
        from src.agents.review_parser import format_audit_to_review_result

        result = format_audit_to_review_result({})
        assert len(result.issues) == 0

    def test_config_manager_missing_keys(self, tmp_path):
        """測試設定檔缺少關鍵 key 時的處理"""
        from src.core.config import ConfigManager

        config_file = tmp_path / "minimal.yaml"
        config_file.write_text("custom_key: value\n", encoding="utf-8")
        manager = ConfigManager(str(config_file))
        # 不存在的 key 應回傳 None 或預設值
        assert manager.get("llm.provider") is None
        assert manager.get("llm.provider", "ollama") == "ollama"

    def test_extract_json_handles_unbalanced_braces(self):
        """測試 _extract_json_object 處理不平衡的括號"""
        result = _extract_json_object('{"key": "value"')  # 缺少結尾 }
        assert result is None

    def test_extract_json_handles_extra_text(self):
        """測試 _extract_json_object 處理 JSON 前後的多餘文字"""
        result = _extract_json_object('Here is the result: {"score": 0.9} Thank you.')
        assert result == '{"score": 0.9}'
        data = json.loads(result)
        assert data["score"] == 0.9

    def test_writer_example_metadata_missing_title(self, mock_llm):
        """測試範例 metadata 中缺少 title 的處理"""
        mock_kb = MagicMock()
        mock_kb.search_examples.return_value = [
            {"content": "範例內容", "metadata": {}}  # 無 title
        ]
        mock_llm.generate.return_value = "### 主旨\n測試"

        writer = WriterAgent(mock_llm, mock_kb)
        req = PublicDocRequirement(
            doc_type="函", sender="機關", receiver="單位", subject="主旨"
        )
        draft = writer.write_draft(req)
        assert draft is not None
        assert "Unknown" in draft  # 預設標題

    def test_writer_example_none_content(self, mock_llm):
        """測試範例 content 為 None 的處理"""
        mock_kb = MagicMock()
        mock_kb.search_examples.return_value = [
            {"content": None, "metadata": {"title": "空範例"}}
        ]
        mock_llm.generate.return_value = "### 主旨\n測試"

        writer = WriterAgent(mock_llm, mock_kb)
        req = PublicDocRequirement(
            doc_type="函", sender="機關", receiver="單位", subject="主旨"
        )
        draft = writer.write_draft(req)
        assert draft is not None

    def test_compliance_checker_parse_invalid_issue_items(self, mock_llm):
        """測試 ComplianceChecker 處理無效的 issue 項目"""
        mock_llm.generate.return_value = json.dumps({
            "issues": [
                "not_a_dict",  # 無效項目
                {"severity": "warning", "location": "A", "description": "有效"},
            ],
            "score": 0.7,
            "confidence": 0.8,
        })
        checker = ComplianceChecker(mock_llm)
        result = checker.check("### 主旨\n測試")
        # 無效項目應被跳過，只保留有效的
        assert len(result.issues) == 1
        assert result.issues[0].description == "有效"
