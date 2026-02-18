"""
端到端使用者場景模擬測試
=========================
模擬完整的使用者操作流程，不需要實際 LLM 後端。
所有外部依賴（LLM、ChromaDB、檔案系統）皆以 mock 取代。

測試場景：
  1. 生成「函」類型公文
  2. 生成「公告」類型公文
  3. 生成「簽」類型公文
  4. 知識庫匯入和搜尋
  5. API 端點呼叫
  6. 配置切換（Ollama → OpenRouter）
  7. 錯誤輸入處理（空輸入、超長輸入、特殊字元）
  8. 並行審查超時處理
  9. Word 匯出格式驗證
"""
import json
import os
import sys
import pytest
import yaml
from pathlib import Path
from unittest.mock import MagicMock, patch

# 確保 src 在 Python 路徑中
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import ConfigManager, LLMProvider
from src.core.models import PublicDocRequirement
from src.core.review_models import ReviewIssue, ReviewResult, QAReport
from src.core.llm import MockLLMProvider, LiteLLMProvider, get_llm_factory
from src.agents.requirement import RequirementAgent
from src.agents.writer import WriterAgent
from src.agents.template import TemplateEngine, clean_markdown_artifacts, renumber_provisions
from src.agents.editor import EditorInChief
from src.agents.auditor import FormatAuditor
from src.agents.style_checker import StyleChecker
from src.agents.fact_checker import FactChecker
from src.agents.consistency_checker import ConsistencyChecker
from src.agents.compliance_checker import ComplianceChecker
from src.agents.org_memory import OrganizationalMemory
from src.agents.validators import ValidatorRegistry
from src.document.exporter import DocxExporter
from src.knowledge.manager import KnowledgeBaseManager


# ============================================================
# 共用 Fixtures
# ============================================================

@pytest.fixture
def mock_llm():
    """建立模擬 LLM 提供者"""
    llm = MagicMock(spec=LLMProvider)
    llm.generate.return_value = "Mock Response"
    llm.embed.return_value = [0.1] * 384
    return llm


@pytest.fixture
def mock_kb(mock_llm):
    """建立模擬知識庫管理器"""
    kb = MagicMock(spec=KnowledgeBaseManager)
    kb.search_examples.return_value = []
    kb.search_regulations.return_value = []
    kb.search_policies.return_value = []
    kb.get_stats.return_value = {
        "examples_count": 0,
        "regulations_count": 0,
        "policies_count": 0,
    }
    return kb


@pytest.fixture
def sample_han_requirement():
    """「函」類型的範例需求"""
    return PublicDocRequirement(
        doc_type="函",
        urgency="普通",
        sender="臺北市政府環境保護局",
        receiver="臺北市各級學校",
        subject="函轉有關加強校園資源回收工作一案，請查照。",
        reason="為提升本市資源回收成效，落實環境教育。",
        action_items=["請加強宣導資源回收", "落實垃圾分類"],
        attachments=["校園資源回收指南"],
    )


@pytest.fixture
def sample_announcement_requirement():
    """「公告」類型的範例需求"""
    return PublicDocRequirement(
        doc_type="公告",
        urgency="普通",
        sender="臺北市政府環境保護局",
        receiver="全體市民",
        subject="公告春節期間垃圾清運時間調整事宜。",
        reason="因應春節連假，調整垃圾清運時間。",
        action_items=["停止清運日期：114年1月28日至2月1日", "恢復清運日期：114年2月2日"],
        attachments=["春節垃圾清運時間表"],
    )


@pytest.fixture
def sample_sign_requirement():
    """「簽」類型的範例需求"""
    return PublicDocRequirement(
        doc_type="簽",
        urgency="速件",
        sender="臺北市政府環境保護局",
        receiver="局長",
        subject="擬辦理本局114年度環保志工表揚大會一案，陳請核示。",
        reason="為肯定環保志工的無私奉獻，擬舉辦年度表揚大會。",
        action_items=["活動日期：114年3月15日", "地點：市政大樓一樓大廳", "預算：新臺幣50萬元"],
        attachments=["活動企劃書", "經費概算表"],
    )


@pytest.fixture
def temp_config_dir(tmp_path):
    """建立暫時配置目錄"""
    config_file = tmp_path / "config.yaml"
    config_data = {
        "llm": {
            "provider": "ollama",
            "model": "llama3.1:8b",
            "api_key": "",
            "base_url": "http://localhost:11434",
        },
        "knowledge_base": {"path": str(tmp_path / "kb_data")},
        "providers": {
            "ollama": {
                "base_url": "http://localhost:11434",
                "model": "llama3.1:8b",
            },
            "openrouter": {
                "api_key": "test-key-123",
                "base_url": "https://openrouter.ai/api/v1",
                "model": "google/gemma-2-9b-it:free",
            },
            "gemini": {
                "api_key": "test-gemini-key",
                "model": "gemini-2.5-pro",
            },
        },
    }
    with open(config_file, "w", encoding="utf-8") as f:
        yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
    return tmp_path, config_file


def _make_mock_llm_json_response(data: dict) -> str:
    """將 dict 轉為 LLM 模擬 JSON 回應字串"""
    return json.dumps(data, ensure_ascii=False)


# ============================================================
# 場景 1：生成「函」類型公文（完整端到端流程）
# ============================================================

class TestScenario1_GenerateHan:
    """場景 1：模擬使用者輸入需求 → 分析 → 撰寫 → 模板化 → 審查 → 匯出"""

    def test_requirement_analysis_for_han(self, mock_llm):
        """測試「函」類型需求分析"""
        # 模擬 LLM 返回結構化 JSON
        expected_json = {
            "doc_type": "函",
            "urgency": "普通",
            "sender": "臺北市政府環境保護局",
            "receiver": "臺北市各級學校",
            "subject": "函轉有關加強校園資源回收工作一案，請查照。",
            "reason": "為提升本市資源回收成效",
            "action_items": ["請加強宣導"],
            "attachments": ["回收指南"],
        }
        mock_llm.generate.return_value = _make_mock_llm_json_response(expected_json)

        agent = RequirementAgent(mock_llm)
        result = agent.analyze("幫我寫一份函，台北市環保局發給各學校，關於加強資源回收")

        assert result.doc_type == "函"
        assert "環保" in result.sender or "環境" in result.sender
        assert result.subject is not None
        assert len(result.subject) > 0

    def test_writer_draft_generation(self, mock_llm, mock_kb, sample_han_requirement):
        """測試「函」類型草稿撰寫"""
        mock_llm.generate.return_value = """### 主旨
函轉有關加強校園資源回收工作一案，請查照。

### 說明
一、為提升本市資源回收成效，落實環境教育。
二、請各校配合辦理。

### 辦法
一、請加強宣導資源回收。
二、落實垃圾分類。
"""
        # 模擬知識庫有範例
        mock_kb.search_examples.return_value = [
            {
                "content": "範例公文內容",
                "metadata": {"title": "環保回收函"},
            }
        ]

        writer = WriterAgent(mock_llm, mock_kb)
        draft = writer.write_draft(sample_han_requirement)

        assert "主旨" in draft or "函轉" in draft
        mock_llm.generate.assert_called_once()
        mock_kb.search_examples.assert_called_once()

    def test_template_standardization_for_han(self, sample_han_requirement):
        """測試「函」模板套用"""
        engine = TemplateEngine()
        raw_draft = """### 主旨
函轉加強校園資源回收一案

### 說明
一、為提升本市資源回收成效
二、請各校配合辦理

### 辦法
一、請加強宣導
二、落實分類
"""
        sections = engine.parse_draft(raw_draft)
        assert sections["subject"] != ""
        assert sections["explanation"] != ""

        formatted = engine.apply_template(sample_han_requirement, sections)
        assert "函" in formatted
        assert "臺北市政府環境保護局" in formatted
        assert "主旨" in formatted
        assert "說明" in formatted

    def test_full_han_pipeline(self, mock_llm, mock_kb, sample_han_requirement, tmp_path):
        """測試「函」完整流水線（分析→撰寫→模板→審查→匯出）"""
        # 撰寫 Mock
        mock_llm.generate.return_value = """### 主旨
函轉有關加強校園資源回收工作一案，請查照。

### 說明
一、為提升本市資源回收成效。

### 辦法
一、請加強宣導。
"""
        writer = WriterAgent(mock_llm, mock_kb)
        raw_draft = writer.write_draft(sample_han_requirement)

        # 模板
        engine = TemplateEngine()
        sections = engine.parse_draft(raw_draft)
        formatted = engine.apply_template(sample_han_requirement, sections)

        assert "函" in formatted
        assert "主旨" in formatted

        # 審查 Mock（返回通過結果）
        mock_llm.generate.return_value = json.dumps(
            {"errors": [], "warnings": []}, ensure_ascii=False
        )

        editor = EditorInChief(mock_llm, mock_kb)
        # 覆寫各 checker 的回應
        mock_llm.generate.side_effect = [
            # FormatAuditor
            json.dumps({"errors": [], "warnings": []}),
            # StyleChecker
            json.dumps({"issues": [], "score": 0.95}),
            # FactChecker
            json.dumps({"issues": [], "score": 0.95}),
            # ConsistencyChecker
            json.dumps({"issues": [], "score": 0.95}),
            # ComplianceChecker
            json.dumps({"issues": [], "score": 0.95, "confidence": 0.9}),
        ]
        refined_draft, qa_report = editor.review_and_refine(formatted, "函")

        assert qa_report is not None
        assert isinstance(qa_report, QAReport)
        assert qa_report.overall_score > 0

        # 匯出
        output_file = tmp_path / "test_han.docx"
        exporter = DocxExporter()
        exporter.export(refined_draft, str(output_file), qa_report=qa_report.audit_log)

        assert output_file.exists()
        assert output_file.stat().st_size > 0


# ============================================================
# 場景 2：生成「公告」類型公文
# ============================================================

class TestScenario2_GenerateAnnouncement:
    """場景 2：「公告」類型公文生成"""

    def test_announcement_template_selection(self, sample_announcement_requirement):
        """測試公告模板正確選擇"""
        engine = TemplateEngine()
        raw_draft = """### 主旨
公告春節期間垃圾清運時間調整事宜。

### 公告事項
一、停止清運日期：114年1月28日至2月1日
二、恢復清運日期：114年2月2日
"""
        sections = engine.parse_draft(raw_draft)
        formatted = engine.apply_template(sample_announcement_requirement, sections)

        # 公告應該有「公告事項」而不是「辦法」
        assert "公告" in formatted
        assert "主旨" in formatted
        # 公告模板不應包含「受文者」
        assert "受文者" not in formatted or "全體市民" not in formatted

    def test_announcement_requirement_parsing(self, mock_llm):
        """測試公告需求解析"""
        expected = {
            "doc_type": "公告",
            "urgency": "普通",
            "sender": "臺北市政府環境保護局",
            "receiver": "全體市民",
            "subject": "公告春節垃圾清運調整",
            "reason": "春節連假調整",
            "action_items": ["停止清運"],
            "attachments": [],
        }
        mock_llm.generate.return_value = _make_mock_llm_json_response(expected)

        agent = RequirementAgent(mock_llm)
        result = agent.analyze("發一份公告，告訴市民春節垃圾清運時間調整")

        assert result.doc_type == "公告"

    def test_announcement_export(self, sample_announcement_requirement, tmp_path):
        """測試公告匯出為 Word"""
        engine = TemplateEngine()
        raw_draft = """### 主旨
公告春節期間垃圾清運時間調整

### 公告事項
一、停止清運
二、恢復清運
"""
        sections = engine.parse_draft(raw_draft)
        formatted = engine.apply_template(sample_announcement_requirement, sections)

        output_file = tmp_path / "announcement.docx"
        exporter = DocxExporter()
        exporter.export(formatted, str(output_file))

        assert output_file.exists()
        assert output_file.stat().st_size > 0


# ============================================================
# 場景 3：生成「簽」類型公文
# ============================================================

class TestScenario3_GenerateSign:
    """場景 3：「簽」類型公文生成"""

    def test_sign_template_selection(self, sample_sign_requirement):
        """測試簽呈模板正確選擇"""
        engine = TemplateEngine()
        raw_draft = """### 主旨
擬辦理本局114年度環保志工表揚大會一案，陳請核示。

### 說明
一、為肯定環保志工的無私奉獻。
二、預計邀請200名志工參加。

### 擬辦
一、活動日期：114年3月15日
二、地點：市政大樓一樓大廳
三、預算：新臺幣50萬元
"""
        sections = engine.parse_draft(raw_draft)
        formatted = engine.apply_template(sample_sign_requirement, sections)

        assert "簽" in formatted
        assert "主旨" in formatted
        # 簽呈應有「擬辦」段落
        assert "擬辦" in formatted

    def test_sign_urgency_display(self, sample_sign_requirement):
        """測試簽呈速別顯示"""
        engine = TemplateEngine()
        raw_draft = "### 主旨\n測試簽呈\n### 說明\n測試說明"
        sections = engine.parse_draft(raw_draft)
        formatted = engine.apply_template(sample_sign_requirement, sections)

        # 速件應顯示
        assert "速件" in formatted

    def test_sign_export(self, sample_sign_requirement, tmp_path):
        """測試簽呈匯出為 Word"""
        engine = TemplateEngine()
        raw_draft = "### 主旨\n簽呈主旨\n### 說明\n說明內容\n### 擬辦\n一、擬辦事項"
        sections = engine.parse_draft(raw_draft)
        formatted = engine.apply_template(sample_sign_requirement, sections)

        output_file = tmp_path / "sign.docx"
        exporter = DocxExporter()
        exporter.export(formatted, str(output_file))

        assert output_file.exists()


# ============================================================
# 場景 4：知識庫匯入和搜尋
# ============================================================

class TestScenario4_KnowledgeBase:
    """場景 4：知識庫管理"""

    def test_kb_add_and_search(self, mock_llm, tmp_path):
        """測試知識庫新增文件及搜尋"""
        kb = KnowledgeBaseManager(str(tmp_path / "test_kb"), mock_llm)

        # 新增文件
        doc_id = kb.add_document(
            content="這是一份函的範例，主旨是加強資源回收。",
            metadata={"title": "回收函範例", "doc_type": "函"},
            collection_name="examples",
        )
        assert doc_id is not None

        # 搜尋
        results = kb.search_examples("資源回收", n_results=1)
        assert isinstance(results, list)

    def test_kb_add_regulation(self, mock_llm, tmp_path):
        """測試法規文件新增"""
        kb = KnowledgeBaseManager(str(tmp_path / "test_kb"), mock_llm)

        doc_id = kb.add_document(
            content="函的格式規範：必須包含主旨、說明、辦法三段。",
            metadata={"title": "函格式規範", "doc_type": "函"},
            collection_name="regulations",
        )
        assert doc_id is not None

    def test_kb_add_policy(self, mock_llm, tmp_path):
        """測試政策文件新增"""
        kb = KnowledgeBaseManager(str(tmp_path / "test_kb"), mock_llm)

        doc_id = kb.add_document(
            content="淨零碳排政策方針：各機關應落實減碳措施。",
            metadata={"title": "淨零碳排政策"},
            collection_name="policies",
        )
        assert doc_id is not None

    def test_kb_stats(self, mock_llm, tmp_path):
        """測試知識庫統計資訊"""
        kb = KnowledgeBaseManager(str(tmp_path / "test_kb"), mock_llm)
        stats = kb.get_stats()

        assert "examples_count" in stats
        assert "regulations_count" in stats
        assert "policies_count" in stats
        assert all(isinstance(v, int) for v in stats.values())

    def test_kb_empty_embedding_handling(self, mock_llm, tmp_path):
        """測試嵌入向量為空時的處理"""
        mock_llm.embed.return_value = []  # 模擬嵌入失敗
        kb = KnowledgeBaseManager(str(tmp_path / "test_kb"), mock_llm)

        doc_id = kb.add_document(
            content="測試文件",
            metadata={"title": "測試"},
            collection_name="examples",
        )
        # 嵌入失敗時應返回 None
        assert doc_id is None

    def test_kb_search_empty_collection(self, mock_llm, tmp_path):
        """測試空集合搜尋"""
        kb = KnowledgeBaseManager(str(tmp_path / "test_kb"), mock_llm)
        results = kb.search_examples("任何查詢", n_results=3)
        assert results == []

    def test_kb_reset(self, mock_llm, tmp_path):
        """測試知識庫重置"""
        kb = KnowledgeBaseManager(str(tmp_path / "test_kb"), mock_llm)

        # 新增文件
        kb.add_document(
            content="測試文件",
            metadata={"title": "測試"},
            collection_name="examples",
        )

        # 重置
        kb.reset_db()
        stats = kb.get_stats()
        assert stats["examples_count"] == 0


# ============================================================
# 場景 5：API 端點呼叫
# ============================================================

class TestScenario5_APIEndpoints:
    """場景 5：FastAPI API 端點測試"""

    @pytest.fixture(autouse=True)
    def setup_api(self):
        """設定 API 測試環境"""
        # 延遲匯入避免初始化問題
        from fastapi.testclient import TestClient

        # Mock 全域資源
        with patch("api_server.get_config") as mock_config, \
             patch("api_server.get_llm") as mock_llm_fn, \
             patch("api_server.get_kb") as mock_kb_fn:

            mock_config.return_value = {
                "llm": {"provider": "mock", "model": "test"},
                "knowledge_base": {"path": "./test_kb"},
            }

            self.mock_llm = MagicMock(spec=LLMProvider)
            self.mock_llm.generate.return_value = json.dumps({
                "doc_type": "函",
                "urgency": "普通",
                "sender": "測試機關",
                "receiver": "測試單位",
                "subject": "測試主旨",
                "reason": "測試原因",
                "action_items": [],
                "attachments": [],
            }, ensure_ascii=False)
            self.mock_llm.embed.return_value = [0.1] * 384
            mock_llm_fn.return_value = self.mock_llm

            self.mock_kb = MagicMock(spec=KnowledgeBaseManager)
            self.mock_kb.search_examples.return_value = []
            self.mock_kb.search_regulations.return_value = []
            self.mock_kb.search_policies.return_value = []
            mock_kb_fn.return_value = self.mock_kb

            from api_server import app
            self.client = TestClient(app)
            yield

    def test_root_endpoint(self):
        """測試根端點健康檢查"""
        response = self.client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    def test_health_check(self):
        """測試詳細健康檢查"""
        response = self.client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_requirement_agent_endpoint(self):
        """測試需求分析 API"""
        response = self.client.post(
            "/api/v1/agent/requirement",
            json={"user_input": "寫一份函，環保局發給各學校"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["requirement"] is not None

    def test_writer_agent_endpoint(self):
        """測試撰寫 API"""
        self.mock_llm.generate.return_value = "### 主旨\n測試主旨\n### 說明\n測試說明"

        response = self.client.post(
            "/api/v1/agent/writer",
            json={
                "requirement": {
                    "doc_type": "函",
                    "sender": "測試機關",
                    "receiver": "測試單位",
                    "subject": "測試主旨",
                }
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_review_format_endpoint(self):
        """測試格式審查 API"""
        self.mock_llm.generate.return_value = json.dumps(
            {"errors": [], "warnings": []}, ensure_ascii=False
        )
        response = self.client.post(
            "/api/v1/agent/review/format",
            json={"draft": "# 函\n### 主旨\n測試", "doc_type": "函"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["agent_name"] == "format"

    def test_review_style_endpoint(self):
        """測試文風審查 API"""
        self.mock_llm.generate.return_value = json.dumps(
            {"issues": [], "score": 0.95}, ensure_ascii=False
        )
        response = self.client.post(
            "/api/v1/agent/review/style",
            json={"draft": "# 函\n### 主旨\n測試"},
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_review_fact_endpoint(self):
        """測試事實審查 API"""
        self.mock_llm.generate.return_value = json.dumps(
            {"issues": [], "score": 0.9}, ensure_ascii=False
        )
        response = self.client.post(
            "/api/v1/agent/review/fact",
            json={"draft": "# 函\n### 主旨\n測試"},
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_review_consistency_endpoint(self):
        """測試一致性審查 API"""
        self.mock_llm.generate.return_value = json.dumps(
            {"issues": [], "score": 0.9}, ensure_ascii=False
        )
        response = self.client.post(
            "/api/v1/agent/review/consistency",
            json={"draft": "# 函\n### 主旨\n測試"},
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_review_compliance_endpoint(self):
        """測試合規審查 API"""
        self.mock_llm.generate.return_value = json.dumps(
            {"issues": [], "score": 0.9, "confidence": 0.8}, ensure_ascii=False
        )
        response = self.client.post(
            "/api/v1/agent/review/compliance",
            json={"draft": "# 函\n### 主旨\n測試"},
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_refine_endpoint(self):
        """測試修改 API"""
        self.mock_llm.generate.return_value = "修改後的草稿內容"
        response = self.client.post(
            "/api/v1/agent/refine",
            json={
                "draft": "### 主旨\n原始草稿內容，需要修改的部分",
                "feedback": [
                    {
                        "agent_name": "Style",
                        "issues": [
                            {"severity": "warning", "description": "用語不夠正式", "suggestion": "改用正式用語"}
                        ],
                    }
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_refine_no_feedback(self):
        """測試無修改意見時直接返回原稿"""
        original = "### 主旨\n原始草稿內容，無需修改"
        response = self.client.post(
            "/api/v1/agent/refine",
            json={"draft": original, "feedback": []},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["refined_draft"] == original

    def test_parallel_review_endpoint(self):
        """測試並行審查 API"""
        # 為每個 agent 設定回應
        self.mock_llm.generate.return_value = json.dumps(
            {"errors": [], "warnings": [], "issues": [], "score": 0.95, "confidence": 0.9},
            ensure_ascii=False,
        )

        response = self.client.post(
            "/api/v1/agent/review/parallel",
            json={
                "draft": "# 函\n### 主旨\n測試草稿\n### 說明\n測試說明",
                "doc_type": "函",
                "agents": ["format", "style"],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "aggregated_score" in data

    def test_api_invalid_request(self):
        """測試無效請求"""
        response = self.client.post(
            "/api/v1/agent/requirement",
            json={},  # 缺少必要欄位
        )
        assert response.status_code == 422  # Pydantic 驗證錯誤


# ============================================================
# 場景 6：配置切換（Ollama → OpenRouter）
# ============================================================

class TestScenario6_ConfigSwitching:
    """場景 6：LLM 提供者切換"""

    def test_switch_ollama_to_openrouter(self, temp_config_dir):
        """測試從 Ollama 切換到 OpenRouter"""
        tmp_path, config_file = temp_config_dir

        # 讀取原始配置
        with open(config_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        assert config["llm"]["provider"] == "ollama"

        # 模擬切換
        config["llm"]["provider"] = "openrouter"
        config["llm"]["model"] = config["providers"]["openrouter"]["model"]
        config["llm"]["api_key"] = config["providers"]["openrouter"]["api_key"]
        config["llm"]["base_url"] = config["providers"]["openrouter"]["base_url"]

        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

        # 驗證
        with open(config_file, "r", encoding="utf-8") as f:
            updated = yaml.safe_load(f)

        assert updated["llm"]["provider"] == "openrouter"
        assert updated["llm"]["model"] == "google/gemma-2-9b-it:free"

    def test_switch_to_gemini(self, temp_config_dir):
        """測試切換到 Gemini"""
        tmp_path, config_file = temp_config_dir

        with open(config_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        config["llm"]["provider"] = "gemini"
        config["llm"]["model"] = config["providers"]["gemini"]["model"]

        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

        cm = ConfigManager(str(config_file))
        assert cm.get("llm.provider") == "gemini"

    def test_config_env_var_expansion(self, temp_config_dir):
        """測試環境變數展開"""
        tmp_path, config_file = temp_config_dir

        # 寫入帶環境變數的配置
        config = {
            "llm": {
                "provider": "openrouter",
                "api_key": "${TEST_API_KEY_E2E}",
            }
        }
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config, f)

        # 設定環境變數
        os.environ["TEST_API_KEY_E2E"] = "my-secret-key"
        try:
            cm = ConfigManager(str(config_file))
            assert cm.get("llm.api_key") == "my-secret-key"
        finally:
            del os.environ["TEST_API_KEY_E2E"]

    def test_config_missing_env_var(self, temp_config_dir):
        """測試缺少環境變數時返回空字串"""
        tmp_path, config_file = temp_config_dir

        config = {
            "llm": {
                "provider": "openrouter",
                "api_key": "${NONEXISTENT_KEY_XYZ}",
            }
        }
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config, f)

        cm = ConfigManager(str(config_file))
        assert cm.get("llm.api_key") == ""

    def test_llm_factory_mock_provider(self):
        """測試 Mock 提供者工廠方法"""
        config = {"provider": "mock", "model": "test-model"}
        llm = get_llm_factory(config)
        assert isinstance(llm, MockLLMProvider)

    def test_llm_factory_litellm_provider(self):
        """測試 LiteLLM 提供者工廠方法"""
        config = {"provider": "ollama", "model": "llama3.1:8b"}
        llm = get_llm_factory(config)
        assert isinstance(llm, LiteLLMProvider)

    def test_litellm_model_name_construction(self):
        """測試 LiteLLM 模型名稱構建"""
        # Ollama
        llm = LiteLLMProvider({"provider": "ollama", "model": "llama3.1:8b"})
        assert llm.model_name == "ollama/llama3.1:8b"

        # Gemini
        llm = LiteLLMProvider({"provider": "gemini", "model": "gemini-2.5-pro"})
        assert llm.model_name == "gemini/gemini-2.5-pro"

        # OpenRouter
        llm = LiteLLMProvider({"provider": "openrouter", "model": "google/gemma-2-9b-it:free"})
        assert llm.model_name == "openrouter/google/gemma-2-9b-it:free"

        # 已有前綴時不重複
        llm = LiteLLMProvider({"provider": "gemini", "model": "gemini/gemini-2.5-pro"})
        assert llm.model_name == "gemini/gemini-2.5-pro"


# ============================================================
# 場景 7：錯誤輸入處理
# ============================================================

class TestScenario7_ErrorHandling:
    """場景 7：各種錯誤輸入的處理"""

    def test_empty_input_to_requirement(self, mock_llm):
        """測試空輸入"""
        mock_llm.generate.return_value = "Invalid response without JSON"

        agent = RequirementAgent(mock_llm)
        with pytest.raises(ValueError, match="使用者輸入不可為空白"):
            agent.analyze("")

    def test_very_long_input(self, mock_llm):
        """測試超長輸入（10000 字元）"""
        long_input = "測試" * 5000  # 10000 個字元

        expected = {
            "doc_type": "函",
            "sender": "測試",
            "receiver": "測試",
            "subject": "超長輸入測試",
        }
        mock_llm.generate.return_value = _make_mock_llm_json_response(expected)

        agent = RequirementAgent(mock_llm)
        result = agent.analyze(long_input)
        assert result.doc_type == "函"
        # 確認 LLM 被呼叫（不因超長輸入而崩潰）
        mock_llm.generate.assert_called_once()

    def test_special_characters_input(self, mock_llm):
        """測試特殊字元輸入（SQL injection、XSS、換行等）"""
        special_inputs = [
            "'; DROP TABLE users; --",
            "<script>alert('xss')</script>",
            "測試\n\n\r\n換行\t和\ttab",
            "emoji 😀🎉 和 unicode ±§©",
            "零寬字元\u200b\u200c\u200d",
        ]

        expected = {
            "doc_type": "函",
            "sender": "測試",
            "receiver": "測試",
            "subject": "特殊字元測試",
        }
        mock_llm.generate.return_value = _make_mock_llm_json_response(expected)

        agent = RequirementAgent(mock_llm)
        for inp in special_inputs:
            result = agent.analyze(inp)
            assert result is not None
            assert result.doc_type == "函"

    def test_invalid_json_from_llm(self, mock_llm):
        """測試 LLM 返回無效 JSON"""
        mock_llm.generate.return_value = "這不是 JSON 格式"

        agent = RequirementAgent(mock_llm)
        with pytest.raises(ValueError):
            agent.analyze("測試輸入")

    def test_partial_json_from_llm(self, mock_llm):
        """測試 LLM 返回部分 JSON（使用 regex 回退策略）"""
        # 模擬 LLM 返回嵌入在文字中的 JSON 欄位
        mock_llm.generate.return_value = """
好的，以下是分析結果：
"doc_type": "函",
"sender": "環保局",
"receiver": "各學校",
"subject": "資源回收"
完成。
"""
        agent = RequirementAgent(mock_llm)
        result = agent.analyze("測試")
        assert result.doc_type == "函"

    def test_llm_returns_markdown_wrapped_json(self, mock_llm):
        """測試 LLM 在 markdown 程式碼區塊中返回 JSON"""
        expected = {
            "doc_type": "公告",
            "sender": "環保局",
            "receiver": "市民",
            "subject": "公告主旨",
        }
        mock_llm.generate.return_value = f"```json\n{json.dumps(expected, ensure_ascii=False)}\n```"

        agent = RequirementAgent(mock_llm)
        result = agent.analyze("發公告")
        assert result.doc_type == "公告"

    def test_missing_required_fields_in_json(self, mock_llm):
        """測試 JSON 缺少必要欄位"""
        mock_llm.generate.return_value = json.dumps(
            {"doc_type": "函", "subject": "只有兩個欄位"}
        )

        agent = RequirementAgent(mock_llm)
        with pytest.raises((ValueError, Exception)):
            agent.analyze("測試")

    def test_template_parse_empty_draft(self):
        """測試空草稿的模板解析"""
        engine = TemplateEngine()
        sections = engine.parse_draft("")
        assert sections["subject"] == ""
        assert sections["explanation"] == ""
        assert sections["provisions"] == ""

    def test_template_parse_no_sections(self):
        """測試沒有段落標題的草稿"""
        engine = TemplateEngine()
        sections = engine.parse_draft("這是一段沒有任何標題的純文字。")
        # 應該不會崩潰，所有段落為空
        assert sections["subject"] == ""

    def test_clean_markdown_none_input(self):
        """測試 clean_markdown_artifacts 處理 None/空值"""
        assert clean_markdown_artifacts("") == ""
        assert clean_markdown_artifacts(None) == ""

    def test_renumber_provisions_empty(self):
        """測試空文字重新編排"""
        assert renumber_provisions("") == ""
        assert renumber_provisions(None) == ""

    def test_validator_invalid_date(self):
        """測試日期驗證器處理無效日期"""
        registry = ValidatorRegistry()
        errors = registry.check_date_logic("會議日期：99年13月32日")
        assert len(errors) > 0  # 應偵測到無效日期

    def test_validator_attachment_inconsistency(self):
        """測試附件一致性驗證"""
        registry = ValidatorRegistry()
        # 提及附件但沒有附件段落
        errors = registry.check_attachment_consistency("說明中提到檢附相關文件。")
        assert len(errors) > 0

    def test_validator_attachment_consistent(self):
        """測試附件一致（有提及且有段落）"""
        registry = ValidatorRegistry()
        errors = registry.check_attachment_consistency("檢附相關文件。\n附件：相關文件")
        assert len(errors) == 0

    def test_format_auditor_empty_response(self, mock_llm, mock_kb):
        """測試格式審查收到空回應"""
        mock_llm.generate.return_value = ""
        auditor = FormatAuditor(mock_llm, mock_kb)
        result = auditor.audit("測試草稿", "函")

        assert "errors" in result
        assert "warnings" in result
        # 不應崩潰

    def test_style_checker_empty_response(self, mock_llm):
        """測試文風審查收到空回應"""
        mock_llm.generate.return_value = ""
        checker = StyleChecker(mock_llm)
        result = checker.check("測試草稿")

        assert isinstance(result, ReviewResult)
        assert result.agent_name == "Style Checker"

    def test_fact_checker_empty_response(self, mock_llm):
        """測試事實審查收到空回應"""
        mock_llm.generate.return_value = ""
        checker = FactChecker(mock_llm)
        result = checker.check("測試草稿")

        assert isinstance(result, ReviewResult)

    def test_consistency_checker_empty_response(self, mock_llm):
        """測試一致性審查收到空回應"""
        mock_llm.generate.return_value = ""
        checker = ConsistencyChecker(mock_llm)
        result = checker.check("測試草稿")

        assert isinstance(result, ReviewResult)

    def test_compliance_checker_empty_response(self, mock_llm, mock_kb):
        """測試合規審查收到空回應"""
        mock_llm.generate.return_value = ""
        checker = ComplianceChecker(mock_llm, mock_kb)
        result = checker.check("測試草稿")

        assert isinstance(result, ReviewResult)
        assert result.confidence == 0.5  # 預設低信心度


# ============================================================
# 場景 8：並行審查超時處理
# ============================================================

class TestScenario8_ParallelReviewTimeout:
    """場景 8：並行審查的超時與異常處理"""

    def test_parallel_review_with_agent_exception(self, mock_llm, mock_kb):
        """測試某個審查代理失敗時不影響其他代理"""
        # 設定回應：部分成功、部分失敗
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # FormatAuditor（同步）
                return json.dumps({"errors": [], "warnings": []})
            elif call_count[0] == 2:
                # StyleChecker 成功
                return json.dumps({"issues": [], "score": 0.9})
            elif call_count[0] == 3:
                # FactChecker 拋出例外
                raise Exception("模擬 FactChecker 錯誤")
            else:
                # 其他 agent 正常
                return json.dumps({"issues": [], "score": 0.9, "confidence": 0.8})

        mock_llm.generate.side_effect = side_effect

        editor = EditorInChief(mock_llm, mock_kb)
        refined, report = editor.review_and_refine("# 函\n### 主旨\n測試", "函")

        # 應該正常完成，不因單一代理失敗而崩潰
        assert report is not None
        assert isinstance(report, QAReport)
        assert len(report.agent_results) > 0

    def test_parallel_review_all_pass(self, mock_llm, mock_kb):
        """測試所有審查代理都通過"""
        mock_llm.generate.side_effect = [
            # FormatAuditor
            json.dumps({"errors": [], "warnings": []}),
            # StyleChecker
            json.dumps({"issues": [], "score": 1.0}),
            # FactChecker
            json.dumps({"issues": [], "score": 1.0}),
            # ConsistencyChecker
            json.dumps({"issues": [], "score": 1.0}),
            # ComplianceChecker
            json.dumps({"issues": [], "score": 1.0, "confidence": 1.0}),
        ]

        editor = EditorInChief(mock_llm, mock_kb)
        refined, report = editor.review_and_refine("# 函\n### 主旨\n測試", "函")

        assert report.risk_summary in ["Safe", "Low"]
        assert report.overall_score > 0.9

    def test_parallel_review_critical_issues(self, mock_llm, mock_kb):
        """測試審查發現嚴重問題時觸發自動修改"""
        mock_llm.generate.side_effect = [
            # FormatAuditor - 發現錯誤
            json.dumps({"errors": ["缺少主旨段落", "缺少說明段落", "格式嚴重錯誤"], "warnings": []}),
            # StyleChecker
            json.dumps({"issues": [{"severity": "error", "location": "全文", "description": "用語不正式"}], "score": 0.3}),
            # FactChecker
            json.dumps({"issues": [], "score": 0.5}),
            # ConsistencyChecker
            json.dumps({"issues": [], "score": 0.5}),
            # ComplianceChecker
            json.dumps({"issues": [], "score": 0.5, "confidence": 0.8}),
            # EditorInChief auto-refine
            "修改後的草稿",
        ]

        editor = EditorInChief(mock_llm, mock_kb)
        refined, report = editor.review_and_refine("不完整的草稿", "函")

        # 應觸發自動修改
        assert report.risk_summary in ["Critical", "High", "Moderate"]

    def test_qa_report_weighted_scoring(self, mock_llm, mock_kb):
        """測試 QA 報告加權評分邏輯"""

        editor = EditorInChief(mock_llm, mock_kb)

        # 建立測試結果
        results = [
            ReviewResult(
                agent_name="Format Auditor",
                issues=[
                    ReviewIssue(category="format", severity="error", location="x", description="y")
                ],
                score=0.5,
                confidence=1.0,
            ),
            ReviewResult(
                agent_name="Style Checker",
                issues=[],
                score=1.0,
                confidence=1.0,
            ),
        ]

        report = editor._generate_qa_report(results)

        # 格式權重 3.0，文風權重 1.0
        # 加權分 = (0.5*3.0*1.0 + 1.0*1.0*1.0) / (3.0*1.0 + 1.0*1.0) = 2.5/4.0 = 0.625
        assert 0.6 < report.overall_score < 0.7

    def test_agent_category_detection(self):
        """測試代理類別自動偵測"""
        editor = EditorInChief.__new__(EditorInChief)

        assert editor._get_agent_category("Format Auditor") == "format"
        assert editor._get_agent_category("Style Checker") == "style"
        assert editor._get_agent_category("Fact Checker") == "fact"
        assert editor._get_agent_category("Consistency Checker") == "consistency"
        assert editor._get_agent_category("Compliance Checker") == "compliance"
        assert editor._get_agent_category("Unknown Agent") == "style"  # 預設


# ============================================================
# 場景 9：Word 匯出格式驗證
# ============================================================

class TestScenario9_WordExportValidation:
    """場景 9：Word 文件匯出格式的詳細驗證"""

    def test_export_han_structure(self, tmp_path):
        """測試「函」匯出的結構完整性"""
        exporter = DocxExporter()
        output_file = tmp_path / "han.docx"

        draft = """# 函

**機關**：臺北市政府環境保護局
**受文者**：臺北市各級學校
**速別**：普通
**密等及解密條件或保密期限**：普通
**發文日期**：中華民國 114 年 2 月 18 日
**發文字號**：環署字第1140001號

---

### 主旨
函轉有關加強校園資源回收工作一案，請查照。

### 說明
一、為提升本市資源回收成效。
二、請各校配合辦理。

### 辦法
一、請加強宣導。
二、落實分類。

---
附件：校園資源回收指南
"""
        exporter.export(draft, str(output_file))
        assert output_file.exists()
        assert output_file.stat().st_size > 1000  # 合理大小

        # 使用 python-docx 驗證內容
        from docx import Document

        doc = Document(str(output_file))
        full_text = "\n".join([p.text for p in doc.paragraphs])

        assert "函" in full_text
        assert "主旨" in full_text

    def test_export_with_qa_appendix(self, tmp_path):
        """測試帶 QA 報告附件的匯出"""
        exporter = DocxExporter()
        output_file = tmp_path / "with_qa.docx"

        draft = "# 函\n### 主旨\n測試主旨\n### 說明\n測試說明"
        qa_report = """# Quality Assurance Report
- Overall Score: 0.92
- Risk Level: Low

## Detailed Findings
### Format Auditor (Score: 1.00)
- Pass
"""
        exporter.export(draft, str(output_file), qa_report=qa_report)
        assert output_file.exists()

        from docx import Document

        doc = Document(str(output_file))
        full_text = "\n".join([p.text for p in doc.paragraphs])
        # QA 報告應在文件中
        assert "Quality Assurance" in full_text or "品質保證" in full_text

    def test_export_announcement_format(self, tmp_path):
        """測試公告匯出格式"""
        exporter = DocxExporter()
        output_file = tmp_path / "announcement.docx"

        draft = """# 公告

**機關**：臺北市政府環境保護局

---

### 主旨
公告春節垃圾清運時間

### 公告事項
一、停止清運
二、恢復清運
"""
        exporter.export(draft, str(output_file))
        assert output_file.exists()

        from docx import Document

        doc = Document(str(output_file))
        full_text = "\n".join([p.text for p in doc.paragraphs])
        assert "公告" in full_text

    def test_export_sign_format(self, tmp_path):
        """測試簽呈匯出格式"""
        exporter = DocxExporter()
        output_file = tmp_path / "sign.docx"

        draft = """# 簽

**機關**：臺北市政府環境保護局
**速別**：速件

---

### 主旨
擬辦理表揚大會

### 說明
一、表揚事由

### 擬辦
一、辦理方案
"""
        exporter.export(draft, str(output_file))
        assert output_file.exists()

        from docx import Document

        doc = Document(str(output_file))
        full_text = "\n".join([p.text for p in doc.paragraphs])
        assert "簽" in full_text

    def test_export_handles_unicode(self, tmp_path):
        """測試匯出處理 Unicode 字元"""
        exporter = DocxExporter()
        output_file = tmp_path / "unicode.docx"

        draft = "# 函\n### 主旨\n包含各種中文：繁體字、標點符號「」、括號（）\n### 說明\n數字：①②③"
        exporter.export(draft, str(output_file))
        assert output_file.exists()

    def test_export_markdown_cleanup_in_word(self, tmp_path):
        """測試 Word 匯出中 markdown 標記被清理"""
        exporter = DocxExporter()
        output_file = tmp_path / "cleanup.docx"

        draft = """# 函

### 主旨
**粗體** 和 _斜體_ 和 [連結](http://example.com) 應被清理

### 說明
```python
code_block = True
```
這段程式碼區塊標記應被移除
"""
        exporter.export(draft, str(output_file))

        from docx import Document

        doc = Document(str(output_file))
        full_text = "\n".join([p.text for p in doc.paragraphs])

        # 確認 markdown 標記被清理
        assert "**" not in full_text
        assert "```" not in full_text
        assert "[連結]" not in full_text

    def test_export_page_margins(self, tmp_path):
        """測試頁面邊距設定"""
        exporter = DocxExporter()
        output_file = tmp_path / "margins.docx"

        draft = "# 函\n### 主旨\n測試頁面邊距"
        exporter.export(draft, str(output_file))

        from docx import Document
        from docx.shared import Cm

        doc = Document(str(output_file))
        section = doc.sections[0]

        # 標準 A4 邊距
        assert abs(section.top_margin - Cm(2.54)) < Cm(0.1)
        assert abs(section.bottom_margin - Cm(2.54)) < Cm(0.1)
        assert abs(section.left_margin - Cm(3.17)) < Cm(0.1)
        assert abs(section.right_margin - Cm(3.17)) < Cm(0.1)


# ============================================================
# 額外測試：使用者體驗相關
# ============================================================

class TestUXIssues:
    """使用者體驗問題檢查"""

    def test_cli_version(self):
        """測試 CLI 版本資訊存在"""
        from src import __version__

        assert __version__ is not None
        assert len(__version__) > 0

    def test_template_engine_fallback(self, sample_han_requirement):
        """測試模板載入失敗時的 fallback"""
        engine = TemplateEngine()
        # 手動呼叫 fallback
        sections = {"subject": "測試", "explanation": "說明", "provisions": "辦法"}
        result = engine._fallback_apply(sample_han_requirement, sections)

        assert "函" in result
        assert "測試" in result
        assert "說明" in result

    def test_clean_markdown_comprehensive(self):
        """測試 markdown 清理的完整性"""
        cases = [
            ("```python\ncode\n```", "code"),
            ("# 標題", "標題"),
            ("## 二級標題", "二級標題"),
            ("**粗體**", "粗體"),
            ("*斜體*", "斜體"),
            ("__底線粗體__", "底線粗體"),
            ("_底線斜體_", "底線斜體"),
            ("[連結文字](http://example.com)", "連結文字"),
            ("---", ""),
            ("捺印處", ""),
        ]

        for input_text, expected in cases:
            result = clean_markdown_artifacts(input_text).strip()
            assert expected in result or result == expected, (
                f"清理 '{input_text}' 失敗：期望包含 '{expected}'，實際 '{result}'"
            )

    def test_renumber_provisions_correct(self):
        """測試辦法段落重新編號"""
        text = """1、第一項
2、第二項
3、第三項
(1)子項一
(2)子項二"""
        result = renumber_provisions(text)
        assert "一、第一項" in result
        assert "二、第二項" in result
        assert "三、第三項" in result
        assert "（一）子項一" in result
        assert "（二）子項二" in result

    def test_renumber_skip_signature_items(self):
        """測試重新編號時跳過簽署區項目"""
        text = """1、正本：各機關
2、副本：存檔
3、承辦人"""
        result = renumber_provisions(text)
        # 正本、副本、承辦人不應被重新編號（原始編號應被移除）
        assert "一、正本" not in result
        assert "二、副本" not in result
        assert "三、承辦" not in result
        # 但內容應保留
        assert "正本：各機關" in result
        assert "副本：存檔" in result
        assert "承辦人" in result

    def test_organizational_memory_crud(self, tmp_path):
        """測試機構記憶 CRUD 操作"""
        storage = tmp_path / "prefs.json"
        memory = OrganizationalMemory(str(storage))

        # 取得預設值
        profile = memory.get_agency_profile("測試機關")
        assert profile["formal_level"] == "standard"
        assert profile["usage_count"] == 0

        # 更新偏好
        memory.update_preference("測試機關", "formal_level", "formal")
        profile = memory.get_agency_profile("測試機關")
        assert profile["formal_level"] == "formal"

        # 學習編輯
        memory.learn_from_edit("測試機關", "原始文字", "修改後文字")
        profile = memory.get_agency_profile("測試機關")
        assert profile["usage_count"] == 1

        # 匯出報告
        report = memory.export_report()
        assert "測試機關" in report
        assert "使用次數" in report

    def test_organizational_memory_writing_hints(self, tmp_path):
        """測試機構記憶的寫作提示生成"""
        storage = tmp_path / "prefs.json"
        memory = OrganizationalMemory(str(storage))

        # 設定偏好
        memory.update_preference("正式機關", "formal_level", "formal")
        memory.update_preference("正式機關", "preferred_terms", {"請": "惠請"})

        hints = memory.get_writing_hints("正式機關")
        assert "正式" in hints
        assert "惠請" in hints

        # 無偏好時返回空
        hints_empty = memory.get_writing_hints("新機關")
        assert hints_empty == ""

    def test_review_models_serialization(self):
        """測試審查模型的序列化"""
        issue = ReviewIssue(
            category="format",
            severity="error",
            risk_level="high",
            location="主旨",
            description="缺少主旨段落",
            suggestion="請加入主旨",
        )
        result = ReviewResult(
            agent_name="Test Agent",
            issues=[issue],
            score=0.5,
            confidence=0.9,
        )
        report = QAReport(
            overall_score=0.75,
            risk_summary="Moderate",
            agent_results=[result],
            audit_log="# Report",
        )

        # 測試 model_dump
        data = report.model_dump()
        assert data["overall_score"] == 0.75
        assert len(data["agent_results"]) == 1
        assert data["agent_results"][0]["issues"][0]["category"] == "format"

    def test_mock_llm_provider(self):
        """測試 MockLLMProvider 的行為"""
        mock = MockLLMProvider({"model": "test"})

        response = mock.generate("測試提示")
        assert "[MOCK]" in response

        embedding = mock.embed("測試文字")
        assert len(embedding) == 384
        assert all(isinstance(v, float) for v in embedding)

    def test_mock_llm_reproducible_embeddings(self):
        """測試 MockLLMProvider 嵌入的可重現性"""
        mock = MockLLMProvider({"model": "test"})

        emb1 = mock.embed("同樣的文字")
        emb2 = mock.embed("同樣的文字")
        assert emb1 == emb2  # 相同文字應產生相同嵌入

    def test_public_doc_requirement_model_example(self):
        """測試模型範例資料正確性"""
        example = PublicDocRequirement.model_config["json_schema_extra"]["examples"][0]
        req = PublicDocRequirement(**example)
        assert req.doc_type == "函"
        assert req.sender == "臺北市政府"


# ============================================================
# 整合測試：完整流程模擬
# ============================================================

class TestIntegration:
    """完整流程整合測試"""

    def test_full_pipeline_with_review_loop(self, mock_llm, mock_kb, tmp_path):
        """測試完整流水線包含多輪審查"""
        # 第一輪：分析需求
        requirement_json = {
            "doc_type": "函",
            "urgency": "普通",
            "sender": "臺北市政府",
            "receiver": "各區公所",
            "subject": "函轉文書處理規定",
            "reason": "依據行政院函辦理",
            "action_items": ["更新規定"],
            "attachments": [],
        }

        # 設定所有 LLM 呼叫的回應
        responses = [
            # RequirementAgent
            json.dumps(requirement_json, ensure_ascii=False),
            # WriterAgent
            "### 主旨\n函轉文書處理規定\n### 說明\n依據行政院函辦理\n### 辦法\n一、更新規定",
            # FormatAuditor（第一輪）
            json.dumps({"errors": ["缺少發文字號"], "warnings": []}),
            # StyleChecker（第一輪）
            json.dumps({"issues": [], "score": 0.9}),
            # FactChecker（第一輪）
            json.dumps({"issues": [], "score": 0.9}),
            # ConsistencyChecker（第一輪）
            json.dumps({"issues": [], "score": 0.9}),
            # ComplianceChecker（第一輪）
            json.dumps({"issues": [], "score": 0.9, "confidence": 0.9}),
            # Editor auto-refine
            "### 主旨\n函轉文書處理規定（修正版）\n### 說明\n依據行政院函辦理",
        ]
        mock_llm.generate.side_effect = responses

        # 執行流水線
        req_agent = RequirementAgent(mock_llm)
        requirement = req_agent.analyze("寫一份函，轉達文書處理規定")

        writer = WriterAgent(mock_llm, mock_kb)
        raw_draft = writer.write_draft(requirement)

        engine = TemplateEngine()
        sections = engine.parse_draft(raw_draft)
        formatted = engine.apply_template(requirement, sections)

        editor = EditorInChief(mock_llm, mock_kb)
        refined, report = editor.review_and_refine(formatted, "函")

        # 匯出
        output_file = tmp_path / "integration_test.docx"
        exporter = DocxExporter()
        exporter.export(refined, str(output_file), qa_report=report.audit_log)

        assert output_file.exists()
        assert report is not None

    def test_multiple_doc_types_in_sequence(self, mock_llm, mock_kb, tmp_path):
        """測試依序產生多種公文類型"""
        doc_types = [
            ("函", "函轉通知"),
            ("公告", "公告事項"),
            ("簽", "簽呈核示"),
        ]

        for doc_type, subject in doc_types:
            requirement = PublicDocRequirement(
                doc_type=doc_type,
                sender="測試機關",
                receiver="受文者",
                subject=subject,
            )

            mock_llm.generate.return_value = f"### 主旨\n{subject}\n### 說明\n測試說明"

            writer = WriterAgent(mock_llm, mock_kb)
            draft = writer.write_draft(requirement)

            engine = TemplateEngine()
            sections = engine.parse_draft(draft)
            formatted = engine.apply_template(requirement, sections)

            assert doc_type in formatted

            output_file = tmp_path / f"{doc_type}.docx"
            exporter = DocxExporter()
            exporter.export(formatted, str(output_file))
            assert output_file.exists()


# ============================================================
# 整合流程模擬測試：完整公文生成流程
# ============================================================

class TestFullIntegrationFlow:
    """完整整合流程模擬測試

    模擬真實使用場景：需求分析 → 撰寫 → 模板套用 → 格式審查 → 修改 → 輸出
    所有 Agent 串聯執行。
    """

    def test_full_document_generation_pipeline(self, mock_llm, mock_kb, tmp_path):
        """完整公文生成流程：需求分析 → 撰寫 → 模板套用 → 審查 → 修改 → 匯出

        模擬從使用者輸入到最終 docx 檔案的完整路徑，
        含審查發現問題後觸發自動修改，再重新審查通過。
        """
        # === 步驟 1：需求分析 ===
        requirement_json = {
            "doc_type": "函",
            "urgency": "普通",
            "sender": "臺北市政府環境保護局",
            "receiver": "臺北市各級學校",
            "subject": "函轉有關加強校園資源回收工作一案，請查照。",
            "reason": "為提升本市資源回收成效，落實環境教育。",
            "action_items": ["請加強宣導資源回收", "落實垃圾分類"],
            "attachments": ["校園資源回收指南"],
        }

        responses = [
            # 需求分析
            json.dumps(requirement_json, ensure_ascii=False),
            # 撰寫草稿
            """### 主旨
函轉有關加強校園資源回收工作一案，請查照。

### 說明
一、為提升本市資源回收成效，落實環境教育。
二、依據行政院環境保護署函辦理。

### 辦法
一、請各校加強宣導資源回收。
二、請落實垃圾分類。
""",
            # 第一輪審查（格式有問題）
            json.dumps({"errors": ["缺少發文字號"], "warnings": ["建議補充法規依據"]}),
            # StyleChecker
            json.dumps({"issues": [{"severity": "warning", "location": "說明", "description": "建議增加正式引述"}], "score": 0.8}),
            # FactChecker
            json.dumps({"issues": [], "score": 0.9}),
            # ConsistencyChecker
            json.dumps({"issues": [], "score": 0.9}),
            # ComplianceChecker
            json.dumps({"issues": [], "score": 0.9, "confidence": 0.85}),
            # Editor auto-refine（修正後的草稿）
            """### 主旨
函轉有關加強校園資源回收工作一案，請查照。

### 說明
一、依據行政院環境保護署114年1月15日環署廢字第1140001號函辦理。
二、為提升本市資源回收成效，落實環境教育。

### 辦法
一、請各校加強宣導資源回收。
二、請落實垃圾分類。
""",
        ]
        mock_llm.generate.side_effect = responses

        # 執行流水線
        req_agent = RequirementAgent(mock_llm)
        requirement = req_agent.analyze("幫我寫一份函，環保局發給各學校，關於加強資源回收")

        assert requirement.doc_type == "函"
        assert "環保" in requirement.sender or "環境" in requirement.sender

        # === 步驟 2：撰寫草稿 ===
        writer = WriterAgent(mock_llm, mock_kb)
        raw_draft = writer.write_draft(requirement)

        assert "主旨" in raw_draft
        assert "說明" in raw_draft

        # === 步驟 3：模板套用 ===
        engine = TemplateEngine()
        sections = engine.parse_draft(raw_draft)
        formatted = engine.apply_template(requirement, sections)

        assert "函" in formatted
        assert "臺北市政府環境保護局" in formatted
        assert "主旨" in formatted

        # === 步驟 4：審查 + 自動修改 ===
        editor = EditorInChief(mock_llm, mock_kb)
        refined_draft, qa_report = editor.review_and_refine(formatted, "函")

        assert qa_report is not None
        assert isinstance(qa_report, QAReport)
        assert len(qa_report.agent_results) > 0
        assert qa_report.overall_score > 0

        # === 步驟 5：匯出 DOCX ===
        output_file = tmp_path / "full_pipeline_output.docx"
        exporter = DocxExporter()
        exporter.export(refined_draft, str(output_file), qa_report=qa_report.audit_log)

        assert output_file.exists()
        assert output_file.stat().st_size > 0

        # 驗證 docx 內容
        from docx import Document
        doc = Document(str(output_file))
        full_text = "\n".join([p.text for p in doc.paragraphs])
        assert "主旨" in full_text

    def test_multi_doc_type_full_flow(self, mock_llm, mock_kb, tmp_path):
        """多類型公文流程：函、公告、簽各生成一次，驗證全部成功

        每種公文類型都經過完整的「需求分析 → 撰寫 → 模板 → 審查 → 匯出」流程。
        """
        doc_configs = [
            {
                "type": "函",
                "user_input": "寫一份函，環保局發給各學校，關於加強回收",
                "requirement": {
                    "doc_type": "函",
                    "urgency": "普通",
                    "sender": "臺北市政府環境保護局",
                    "receiver": "臺北市各級學校",
                    "subject": "函轉加強校園資源回收一案",
                    "reason": "為提升回收成效",
                    "action_items": ["加強宣導"],
                    "attachments": [],
                },
                "draft": "### 主旨\n函轉加強校園資源回收一案\n### 說明\n一、為提升回收成效。\n### 辦法\n一、請加強宣導。",
            },
            {
                "type": "公告",
                "user_input": "發一份公告，告知市民春節垃圾清運調整",
                "requirement": {
                    "doc_type": "公告",
                    "urgency": "普通",
                    "sender": "臺北市政府環境保護局",
                    "receiver": "全體市民",
                    "subject": "公告春節期間垃圾清運時間調整",
                    "reason": "因應春節連假",
                    "action_items": ["停止清運", "恢復清運"],
                    "attachments": [],
                },
                "draft": "### 主旨\n公告春節期間垃圾清運時間調整\n### 公告事項\n一、停止清運日期。\n二、恢復清運日期。",
            },
            {
                "type": "簽",
                "user_input": "寫一份簽呈，擬辦環保志工表揚大會",
                "requirement": {
                    "doc_type": "簽",
                    "urgency": "速件",
                    "sender": "臺北市政府環境保護局",
                    "receiver": "局長",
                    "subject": "擬辦理環保志工表揚大會一案，陳請核示。",
                    "reason": "為肯定志工奉獻",
                    "action_items": ["活動日期", "地點", "預算"],
                    "attachments": ["企劃書"],
                },
                "draft": "### 主旨\n擬辦理環保志工表揚大會一案，陳請核示。\n### 說明\n一、為肯定志工奉獻。\n### 擬辦\n一、活動日期。",
            },
        ]

        results = []

        for config in doc_configs:
            # 設定 LLM 回應
            mock_llm.generate.side_effect = [
                # 需求分析
                json.dumps(config["requirement"], ensure_ascii=False),
                # 撰寫
                config["draft"],
                # 審查全部通過
                json.dumps({"errors": [], "warnings": []}),
                json.dumps({"issues": [], "score": 0.95}),
                json.dumps({"issues": [], "score": 0.95}),
                json.dumps({"issues": [], "score": 0.95}),
                json.dumps({"issues": [], "score": 0.95, "confidence": 0.9}),
            ]

            # 需求分析
            req_agent = RequirementAgent(mock_llm)
            requirement = req_agent.analyze(config["user_input"])
            assert requirement.doc_type == config["type"]

            # 撰寫
            writer = WriterAgent(mock_llm, mock_kb)
            raw_draft = writer.write_draft(requirement)
            assert "主旨" in raw_draft

            # 模板
            engine = TemplateEngine()
            sections = engine.parse_draft(raw_draft)
            formatted = engine.apply_template(requirement, sections)
            assert config["type"] in formatted

            # 審查
            editor = EditorInChief(mock_llm, mock_kb)
            refined, report = editor.review_and_refine(formatted, config["type"])
            assert report is not None
            assert report.overall_score > 0.8

            # 匯出
            output_file = tmp_path / f"e2e_{config['type']}.docx"
            exporter = DocxExporter()
            exporter.export(refined, str(output_file), qa_report=report.audit_log)
            assert output_file.exists()
            assert output_file.stat().st_size > 0

            results.append({
                "type": config["type"],
                "score": report.overall_score,
                "risk": report.risk_summary,
                "file_size": output_file.stat().st_size,
            })

        # 驗證三種類型全部成功
        assert len(results) == 3
        for r in results:
            assert r["score"] > 0
            assert r["file_size"] > 0

    def test_full_api_flow_via_http(self, mock_llm):
        """透過 HTTP API 完整流程測試：需求 → 撰寫 → 審查 → 修改

        模擬 n8n 等外部工具透過 API 串接的實際使用場景。
        """
        from fastapi.testclient import TestClient

        with patch("api_server.get_config") as mock_config, \
             patch("api_server.get_llm") as mock_llm_fn, \
             patch("api_server.get_kb") as mock_kb_fn:

            mock_config.return_value = {
                "llm": {"provider": "mock", "model": "test"},
                "knowledge_base": {"path": "./test_kb"},
            }
            mock_llm_fn.return_value = mock_llm
            mock_kb_fn.return_value = MagicMock(
                spec=KnowledgeBaseManager,
                search_examples=MagicMock(return_value=[]),
                search_regulations=MagicMock(return_value=[]),
                search_policies=MagicMock(return_value=[]),
            )

            from api_server import app
            client = TestClient(app, raise_server_exceptions=False)

            # --- 步驟 1：需求分析 ---
            mock_llm.generate.return_value = json.dumps({
                "doc_type": "函",
                "sender": "環保局",
                "receiver": "各學校",
                "subject": "加強回收",
            }, ensure_ascii=False)

            resp_req = client.post("/api/v1/agent/requirement", json={
                "user_input": "寫一份函，環保局發給各學校，關於資源回收"
            })
            assert resp_req.status_code == 200
            req_data = resp_req.json()
            assert req_data["success"] is True
            requirement = req_data["requirement"]

            # --- 步驟 2：撰寫 ---
            mock_llm.generate.return_value = "### 主旨\n加強回收\n### 說明\n依據某法\n### 辦法\n請配合"

            resp_writer = client.post("/api/v1/agent/writer", json={
                "requirement": requirement
            })
            assert resp_writer.status_code == 200
            writer_data = resp_writer.json()
            assert writer_data["success"] is True
            draft = writer_data["formatted_draft"]
            assert draft is not None

            # --- 步驟 3：並行審查 ---
            mock_llm.generate.return_value = json.dumps({
                "errors": [], "warnings": [],
                "issues": [], "score": 0.9, "confidence": 0.9
            }, ensure_ascii=False)

            resp_review = client.post("/api/v1/agent/review/parallel", json={
                "draft": draft,
                "doc_type": "函",
                "agents": ["format", "style", "fact"]
            })
            assert resp_review.status_code == 200
            review_data = resp_review.json()
            assert review_data["success"] is True
            assert review_data["aggregated_score"] > 0

            # --- 步驟 4：修改（若有問題） ---
            mock_llm.generate.return_value = "### 主旨\n已修正內容\n### 說明\n修正後\n### 辦法\n修正後"

            resp_refine = client.post("/api/v1/agent/refine", json={
                "draft": draft,
                "feedback": [
                    {
                        "agent_name": "format",
                        "issues": [
                            {"severity": "warning", "description": "缺少發文字號", "suggestion": "補充字號"}
                        ]
                    }
                ]
            })
            assert resp_refine.status_code == 200
            refine_data = resp_refine.json()
            assert refine_data["success"] is True
            assert refine_data["refined_draft"] is not None
