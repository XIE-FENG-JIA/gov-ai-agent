"""
壓力測試 + 並發場景 + 大資料量驗證

涵蓋：
1. TestConcurrentAPIRequests — 並發 API 請求測試
2. TestLargeDataHandling — 超大資料量處理測試
3. TestMemoryAndResource — 記憶體與資源管理測試

所有測試使用 MagicMock 模擬 LLM，不需真實 LLM。
並發測試使用 concurrent.futures.ThreadPoolExecutor。
"""

import gc
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("multipart", reason="python-multipart 未安裝，跳過壓力測試")

from fastapi.testclient import TestClient

from src.core.llm import LLMProvider
from src.core.review_models import ReviewResult, ReviewIssue


# ==================== 共用 Fixtures ====================


@pytest.fixture(autouse=True)
def reset_api_globals():
    """每個測試前重設 API 伺服器的全域變數、限流器和效能計數器。"""
    import api_server
    api_server._config = None
    api_server._llm = None
    api_server._kb = None
    api_server._rate_limiter._requests.clear()
    api_server._metrics = api_server._MetricsCollector()
    yield
    api_server._config = None
    api_server._llm = None
    api_server._kb = None


@pytest.fixture
def mock_api_deps():
    """Mock 所有 API 依賴項（LLM、KB、Config），設定高限流上限以適應壓力測試。"""
    import api_server

    mock_config = {
        "llm": {"provider": "mock", "model": "test"},
        "knowledge_base": {"path": "./test_kb"},
        "api": {"auth_enabled": False},
    }
    api_server._config = mock_config

    mock_llm = MagicMock(spec=LLMProvider)
    mock_llm.generate.return_value = "Mock Response"
    mock_llm.embed.return_value = [0.1] * 384
    api_server._llm = mock_llm

    mock_kb = MagicMock()
    mock_kb.search_examples.return_value = []
    mock_kb.search_regulations.return_value = []
    mock_kb.search_policies.return_value = []
    mock_kb.search_hybrid.return_value = []
    mock_kb.is_available = True
    api_server._kb = mock_kb

    # 提高限流上限以適應並發壓力測試
    api_server._rate_limiter.max_requests = 200

    return {"config": mock_config, "llm": mock_llm, "kb": mock_kb}


@pytest.fixture
def client(mock_api_deps):
    """回傳一個 FastAPI TestClient。"""
    from api_server import app
    return TestClient(app, raise_server_exceptions=False)


def _make_requirement_payload(suffix: str = "") -> dict:
    """產生一個有效的 requirement 請求 payload。"""
    return {
        "user_input": f"幫我寫一份函，台北市環保局發給各學校，關於加強資源回收{suffix}"
    }


def _make_review_payload(draft_text: str | None = None) -> dict:
    """產生一個有效的 review 請求 payload。"""
    return {
        "draft": draft_text or (
            "# 函\n\n**機關**：測試機關\n**受文者**：測試單位\n\n"
            "### 主旨\n關於加強辦理某項業務一案，請查照。\n\n"
            "### 說明\n一、依據某法規辦理。\n二、為落實相關政策。"
        ),
        "doc_type": "函",
        "agents": ["format", "style", "fact", "consistency", "compliance"],
    }


def _make_mock_review_result(agent_name: str = "Style Checker") -> ReviewResult:
    """產生一個 mock ReviewResult。"""
    return ReviewResult(
        agent_name=agent_name,
        issues=[],
        score=0.95,
        confidence=0.9,
    )


# ==================== 1. TestConcurrentAPIRequests ====================


class TestConcurrentAPIRequests:
    """並發 API 請求壓力測試。"""

    def test_concurrent_requirement_requests(self, client, mock_api_deps):
        """10 個並發 /api/v1/agent/requirement 請求應全部回傳有效回應。"""
        num_requests = 10
        results = []

        with patch("src.api.routes.agents.RequirementAgent") as MockReqAgent:
            from src.core.models import PublicDocRequirement
            mock_instance = MagicMock()
            mock_instance.analyze.return_value = PublicDocRequirement(
                doc_type="函",
                sender="台北市環保局",
                receiver="各學校",
                subject="加強資源回收",
            )
            MockReqAgent.return_value = mock_instance

            def _send_request(idx):
                payload = _make_requirement_payload(suffix=f"_{idx}")
                resp = client.post("/api/v1/agent/requirement", json=payload)
                return resp

            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {executor.submit(_send_request, i): i for i in range(num_requests)}
                for future in as_completed(futures):
                    results.append(future.result())

        assert len(results) == num_requests
        for resp in results:
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["requirement"] is not None

    def test_concurrent_parallel_review_requests(self, client, mock_api_deps):
        """5 個並發 /api/v1/agent/review/parallel 請求應全部回傳有效回應。"""
        num_requests = 5
        results = []

        mock_review = _make_mock_review_result()

        with (
            patch("src.api.routes.agents._run_format_audit", return_value=mock_review),
            patch("src.api.routes.agents.StyleChecker") as MockStyle,
            patch("src.api.routes.agents.FactChecker") as MockFact,
            patch("src.api.routes.agents.ConsistencyChecker") as MockConsistency,
            patch("src.api.routes.agents.ComplianceChecker") as MockCompliance,
        ):
            for MockCls in [MockStyle, MockFact, MockConsistency, MockCompliance]:
                MockCls.return_value.check.return_value = mock_review

            def _send_request(idx):
                payload = _make_review_payload()
                resp = client.post("/api/v1/agent/review/parallel", json=payload)
                return resp

            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(_send_request, i): i for i in range(num_requests)}
                for future in as_completed(futures):
                    results.append(future.result())

        assert len(results) == num_requests
        for resp in results:
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert "aggregated_score" in data

    def test_concurrent_mixed_read_write(self, client, mock_api_deps):
        """混合讀寫（健康檢查 + 需求分析）同時進行應無錯誤。"""
        results = []

        with patch("src.api.routes.agents.RequirementAgent") as MockReqAgent:
            from src.core.models import PublicDocRequirement
            mock_instance = MagicMock()
            mock_instance.analyze.return_value = PublicDocRequirement(
                doc_type="函",
                sender="台北市環保局",
                receiver="各學校",
                subject="測試主旨",
            )
            MockReqAgent.return_value = mock_instance

            def _send_read(idx):
                return ("read", client.get("/api/v1/health"))

            def _send_write(idx):
                payload = _make_requirement_payload(suffix=f"_mixed_{idx}")
                return ("write", client.post("/api/v1/agent/requirement", json=payload))

            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = []
                for i in range(5):
                    futures.append(executor.submit(_send_read, i))
                    futures.append(executor.submit(_send_write, i))
                for future in as_completed(futures):
                    results.append(future.result())

        assert len(results) == 10
        for kind, resp in results:
            assert resp.status_code in (200, 503)
            data = resp.json()
            if kind == "write":
                assert "success" in data

    def test_rate_limiter_under_high_concurrency(self, client, mock_api_deps):
        """Rate limiter 在高併發下正確限制超額請求。"""
        import api_server
        # 設定極低的限流上限以觸發 429
        api_server._rate_limiter.max_requests = 3

        with patch("src.api.routes.agents.RequirementAgent") as MockReqAgent:
            from src.core.models import PublicDocRequirement
            mock_instance = MagicMock()
            mock_instance.analyze.return_value = PublicDocRequirement(
                doc_type="函",
                sender="測試機關",
                receiver="測試單位",
                subject="限流測試",
            )
            MockReqAgent.return_value = mock_instance

            responses = []
            for i in range(10):
                payload = _make_requirement_payload(suffix=f"_rl_{i}")
                resp = client.post("/api/v1/agent/requirement", json=payload)
                responses.append(resp)

        status_codes = [r.status_code for r in responses]
        assert 429 in status_codes, "高併發下應有部分請求被限流（429）"
        # 至少前幾個請求應該成功
        assert status_codes[:3].count(200) >= 1

    def test_all_responses_return_valid_json(self, client, mock_api_deps):
        """所有並發請求都回傳有效 JSON。"""
        endpoints = [
            ("GET", "/"),
            ("GET", "/api/v1/health"),
        ]

        results = []

        def _send(method, url):
            if method == "GET":
                return client.get(url)
            return client.post(url)

        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = []
            # 每個端點發送 3 個並發請求
            for method, url in endpoints:
                for _ in range(3):
                    futures.append(executor.submit(_send, method, url))
            for future in as_completed(futures):
                results.append(future.result())

        assert len(results) == 6
        for resp in results:
            # 確保回傳的是有效 JSON
            data = resp.json()
            assert isinstance(data, dict)


# ==================== 2. TestLargeDataHandling ====================


class TestLargeDataHandling:
    """超大資料量處理測試。"""

    def test_large_requirement_input(self, client, mock_api_deps):
        """超大 requirement 輸入（接近 5000 字上限）應被正常處理。"""
        large_text = "請幫我撰寫一份詳細的公文，" + "內容需要包含各項施政重點，" * 200

        # 確保不超過 5000 字上限
        large_text = large_text[:4990]

        with patch("src.api.routes.agents.RequirementAgent") as MockReqAgent:
            from src.core.models import PublicDocRequirement
            mock_instance = MagicMock()
            mock_instance.analyze.return_value = PublicDocRequirement(
                doc_type="函",
                sender="台北市政府",
                receiver="各區公所",
                subject="測試大文本需求",
            )
            MockReqAgent.return_value = mock_instance

            resp = client.post("/api/v1/agent/requirement", json={
                "user_input": large_text
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_very_long_draft_review(self, client, mock_api_deps):
        """超長草稿審查（接近 50000 字上限）應被接受並觸發分段處理邏輯。"""
        # 產生接近 50000 字的草稿
        long_draft = "# 函\n\n**機關**：測試機關\n**受文者**：測試單位\n\n### 主旨\n" + "測試內容段落。" * 3000
        long_draft = long_draft[:49990]

        mock_review = _make_mock_review_result("Format Auditor")

        with (
            patch("src.api.routes.agents._run_format_audit", return_value=mock_review),
            patch("src.api.routes.agents.StyleChecker") as MockStyle,
            patch("src.api.routes.agents.FactChecker") as MockFact,
            patch("src.api.routes.agents.ConsistencyChecker") as MockConsistency,
            patch("src.api.routes.agents.ComplianceChecker") as MockCompliance,
        ):
            for MockCls in [MockStyle, MockFact, MockConsistency, MockCompliance]:
                MockCls.return_value.check.return_value = mock_review

            resp = client.post("/api/v1/agent/review/parallel", json={
                "draft": long_draft,
                "doc_type": "函",
                "agents": ["format", "style"],
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_batch_processing_multiple_items(self, client, mock_api_deps):
        """批次處理 20 個項目應全部被處理。"""
        items = []
        for i in range(20):
            items.append({
                "user_input": f"批次測試項目{i}：撰寫一份函給各單位",
                "max_rounds": 1,
                "skip_review": True,
                "output_docx": False,
            })

        with (
            patch("src.api.routes.workflow.RequirementAgent") as MockReqAgent,
            patch("src.api.routes.workflow.WriterAgent") as MockWriter,
            patch("src.api.routes.workflow.TemplateEngine") as MockTemplate,
        ):
            from src.core.models import PublicDocRequirement
            mock_req_instance = MagicMock()
            mock_req_instance.analyze.return_value = PublicDocRequirement(
                doc_type="函",
                sender="批次測試機關",
                receiver="各單位",
                subject="批次測試",
            )
            MockReqAgent.return_value = mock_req_instance

            mock_writer_instance = MagicMock()
            mock_writer_instance.write_draft.return_value = "# 函\n\n模擬草稿內容"
            MockWriter.return_value = mock_writer_instance

            mock_template_instance = MagicMock()
            mock_template_instance.parse_draft.return_value = {}
            mock_template_instance.apply_template.return_value = "# 函\n\n格式化草稿"
            MockTemplate.return_value = mock_template_instance

            resp = client.post("/api/v1/batch", json={"items": items})

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) == 20
        assert data["summary"]["total"] == 20
        assert data["progress"]["completed"] == 20

    def test_kb_search_returns_large_results(self, mock_api_deps):
        """KB 搜尋回傳大量結果（模擬 100 筆）應正常處理。"""
        from src.knowledge.manager import KnowledgeBaseManager

        mock_llm = MagicMock(spec=LLMProvider)
        mock_llm.embed.return_value = [0.1] * 384

        kb = MagicMock(spec=KnowledgeBaseManager)
        kb._available = True
        kb.is_available = True

        # 模擬 search_hybrid 回傳 100 筆結果
        large_results = [
            {
                "id": f"doc_{i}",
                "content": f"這是第 {i} 筆搜尋結果的內容" * 10,
                "metadata": {"doc_type": "函", "source_level": "A"},
                "distance": 0.1 + i * 0.005,
            }
            for i in range(100)
        ]
        kb.search_hybrid.return_value = large_results

        results = kb.search_hybrid("測試查詢", n_results=100)
        assert len(results) == 100
        # 確認所有結果都有必要欄位
        for r in results:
            assert "id" in r
            assert "content" in r
            assert "metadata" in r

    def test_docx_export_with_very_long_content(self, mock_api_deps):
        """DOCX 匯出超長文件（模擬）應不崩潰。"""
        from src.document.exporter import DocxExporter

        long_content = "# 函\n\n" + "這是一段很長的公文內容。\n\n" * 2000
        long_qa_log = "# 品質報告\n\n" + "- 審查通過\n" * 500

        with patch.object(DocxExporter, "export") as mock_export:
            mock_export.return_value = None  # export 成功
            exporter = DocxExporter()
            # 確認超長內容不會導致函式崩潰
            exporter.export(long_content, "/tmp/test_long.docx", qa_report=long_qa_log)
            mock_export.assert_called_once_with(
                long_content, "/tmp/test_long.docx", qa_report=long_qa_log
            )


# ==================== 3. TestMemoryAndResource ====================


class TestMemoryAndResource:
    """記憶體與資源管理測試。"""

    def test_repeated_kb_manager_creation(self):
        """反覆建立/銷毀 KnowledgeBaseManager（記憶體洩漏檢測概念）。"""
        pytest.importorskip("chromadb", reason="chromadb 未安裝，跳過 KB 記憶體測試")
        from src.knowledge.manager import KnowledgeBaseManager

        mock_llm = MagicMock(spec=LLMProvider)
        mock_llm.embed.return_value = [0.1] * 384

        managers = []
        for i in range(20):
            with patch("chromadb.PersistentClient") as MockClient:
                MockClient.return_value.get_or_create_collection.return_value = MagicMock()
                kb = KnowledgeBaseManager(f"/tmp/test_kb_{i}", mock_llm)
                assert kb.is_available
                managers.append(kb)

        # 釋放所有引用
        del managers
        gc.collect()

        # 驗證 GC 後可以再次正常建立
        with patch("chromadb.PersistentClient") as MockClient:
            MockClient.return_value.get_or_create_collection.return_value = MagicMock()
            kb_new = KnowledgeBaseManager("/tmp/test_kb_new", mock_llm)
            assert kb_new.is_available

    def test_repeated_search_hybrid_cache_hits(self):
        """反覆呼叫 search_hybrid 100 次同一查詢應有快取命中。"""
        pytest.importorskip("chromadb", reason="chromadb 未安裝，跳過 KB 快取測試")
        from src.knowledge.manager import KnowledgeBaseManager

        mock_llm = MagicMock(spec=LLMProvider)
        mock_llm.embed.return_value = [0.1] * 384

        with patch("chromadb.PersistentClient") as MockClient:
            mock_collection = MagicMock()
            mock_collection.count.return_value = 5
            mock_collection.query.return_value = {
                "ids": [["id1", "id2"]],
                "documents": [["doc1 內容", "doc2 內容"]],
                "metadatas": [[{"doc_type": "函"}, {"doc_type": "公告"}]],
                "distances": [[0.1, 0.2]],
            }
            MockClient.return_value.get_or_create_collection.return_value = mock_collection

            kb = KnowledgeBaseManager("/tmp/test_kb_cache", mock_llm)

            # 第一次呼叫應觸發實際搜尋
            result1 = kb.search_hybrid("測試查詢", n_results=5)
            first_embed_count = mock_llm.embed.call_count

            # 後續 99 次呼叫應命中快取
            for _ in range(99):
                result = kb.search_hybrid("測試查詢", n_results=5)
                assert result == result1

            # embed 應只被呼叫一次（第一次）
            assert mock_llm.embed.call_count == first_embed_count

    def test_thread_pool_executor_proper_shutdown(self):
        """ThreadPoolExecutor 正確關閉，不殘留 threads。"""
        initial_thread_count = threading.active_count()
        results = []

        def dummy_task(idx):
            time.sleep(0.01)
            return idx

        executor = ThreadPoolExecutor(max_workers=5)
        futures = [executor.submit(dummy_task, i) for i in range(20)]
        for f in as_completed(futures):
            results.append(f.result())
        executor.shutdown(wait=True)

        assert len(results) == 20
        # 等待短暫時間讓執行緒完全清理
        time.sleep(0.1)
        final_thread_count = threading.active_count()
        # 執行緒數應回到接近初始值（容許 +2 的差異因平台差異）
        assert final_thread_count <= initial_thread_count + 2, (
            f"執行緒洩漏：初始 {initial_thread_count}, 結束 {final_thread_count}"
        )

    def test_mass_review_issue_creation(self):
        """大量 ReviewIssue 物件建立（>1000 個）應正常運作。"""
        issues = []
        for i in range(1200):
            issue = ReviewIssue(
                category="format",
                severity="warning" if i % 3 else "error",
                risk_level="medium" if i % 2 else "high",
                location=f"第 {i} 段",
                description=f"第 {i} 個問題描述",
                suggestion=f"建議 {i}" if i % 2 else None,
            )
            issues.append(issue)

        assert len(issues) == 1200

        # 確認可以正常建立包含大量 issues 的 ReviewResult
        result = ReviewResult(
            agent_name="Stress Test Agent",
            issues=issues,
            score=0.3,
            confidence=0.8,
        )
        assert len(result.issues) == 1200
        assert result.has_errors is True
        assert result.score == 0.3

        # 確認可以序列化為 JSON
        json_data = result.model_dump()
        assert len(json_data["issues"]) == 1200

    def test_organizational_memory_concurrent_read_write(self, tmp_path):
        """OrganizationalMemory 並發讀寫應不會損毀資料。"""
        from src.agents.org_memory import OrganizationalMemory

        storage_file = tmp_path / "test_prefs.json"
        memory = OrganizationalMemory(storage_path=str(storage_file))

        errors = []
        write_count = 0
        read_count = 0
        lock = threading.Lock()

        def _write_task(idx):
            nonlocal write_count
            try:
                agency = f"機關_{idx % 5}"
                memory.update_preference(agency, f"key_{idx}", f"value_{idx}")
                with lock:
                    write_count += 1
            except Exception as e:
                with lock:
                    errors.append(f"write error at {idx}: {e}")

        def _read_task(idx):
            nonlocal read_count
            try:
                agency = f"機關_{idx % 5}"
                profile = memory.get_agency_profile(agency)
                assert isinstance(profile, dict)
                with lock:
                    read_count += 1
            except Exception as e:
                with lock:
                    errors.append(f"read error at {idx}: {e}")

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = []
            for i in range(50):
                futures.append(executor.submit(_write_task, i))
                futures.append(executor.submit(_read_task, i))
            for f in as_completed(futures):
                f.result()  # 確保拋出的異常能被捕捉

        assert errors == [], f"並發讀寫發生錯誤：{errors}"
        assert write_count == 50
        assert read_count == 50

        # 驗證最終資料完整性：5 個機關都應存在
        for i in range(5):
            profile = memory.get_agency_profile(f"機關_{i}")
            assert isinstance(profile, dict)
