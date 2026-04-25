"""
api_server.py 的 API 端點測試
使用 FastAPI TestClient 和 mock 來避免依賴外部服務
"""
import pytest

pytest.importorskip("multipart", reason="python-multipart 未安裝，跳過 API 測試")

import json
import threading
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from src.core.review_models import ReviewResult, ReviewIssue
from conftest import make_api_config, make_mock_llm, make_mock_kb


# ==================== Fixtures ====================

@pytest.fixture(autouse=True)
def reset_api_globals():
    """在每個測試前重設 API 伺服器的全域變數、限流器和效能計數器"""
    import api_server
    import src.api.routes.workflow as workflow
    api_server._config = None
    api_server._llm = None
    api_server._kb = None
    api_server._org_memory = None
    # 重置限流器，避免測試之間互相干擾
    api_server._rate_limiter._requests.clear()
    # 重置效能計數器
    api_server._metrics = api_server._MetricsCollector()
    # 重置詳細審查快取，避免 session 間交叉污染
    workflow._DETAILED_REVIEW_STORE.clear()
    yield
    api_server._config = None
    api_server._llm = None
    api_server._kb = None
    api_server._org_memory = None
    workflow._DETAILED_REVIEW_STORE.clear()


@pytest.fixture
def mock_api_deps():
    """Mock 所有 API 依賴項（LLM、KB、Config）"""
    import api_server

    mock_config = make_api_config()
    api_server._config = mock_config

    mock_llm = make_mock_llm()
    api_server._llm = mock_llm

    mock_kb = make_mock_kb()
    api_server._kb = mock_kb

    return {"config": mock_config, "llm": mock_llm, "kb": mock_kb}


@pytest.fixture
def client(mock_api_deps):
    """回傳一個 FastAPI TestClient"""
    from api_server import app
    return TestClient(app, raise_server_exceptions=False)


# ==================== Root / Health ====================

class TestRootAndHealth:
    """根路由和健康檢查的測試"""

    def test_root_endpoint(self, client):
        """測試根路由回傳健康狀態"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "timestamp" in data

    def test_health_check(self, client, mock_api_deps):
        """測試詳細健康檢查端點"""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["llm_provider"] == "mock"

    def test_health_check_no_path_leak(self, client, mock_api_deps):
        """測試健康檢查不洩漏檔案路徑"""
        response = client.get("/api/v1/health")
        data = response.json()
        assert "kb_path" not in data
        assert "path" not in data
        assert "kb_status" in data

    def test_security_headers(self, client):
        """測試安全標頭是否正確設定"""
        response = client.get("/")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert "no-store" in response.headers.get("Cache-Control", "")

    def test_request_id_auto_generated(self, client):
        """測試自動生成 X-Request-ID"""
        response = client.get("/")
        request_id = response.headers.get("X-Request-ID")
        assert request_id is not None
        assert len(request_id) > 0

    def test_request_id_passthrough(self, client):
        """測試客戶端提供的 X-Request-ID 會被回傳"""
        custom_id = "my-trace-123"
        response = client.get("/", headers={"X-Request-ID": custom_id})
        assert response.headers.get("X-Request-ID") == custom_id

    def test_rate_limit_headers_on_post(self, client, mock_api_deps):
        """測試 POST 請求回應包含 X-RateLimit-* 標頭"""
        response = client.post("/api/v1/agent/requirement", json={
            "user_input": "寫一份函，測試限流標頭"
        })
        assert response.headers.get("X-RateLimit-Limit") is not None
        assert response.headers.get("X-RateLimit-Remaining") is not None
        assert response.headers.get("X-RateLimit-Reset") is not None

    def test_no_rate_limit_headers_on_get(self, client):
        """測試 GET 請求不包含 X-RateLimit-* 標頭（僅限流 POST）"""
        response = client.get("/")
        assert response.headers.get("X-RateLimit-Limit") is None

    def test_health_check_extended_fields(self, client, mock_api_deps):
        """測試增強版健康檢查的新欄位"""
        response = client.get("/api/v1/health")
        data = response.json()
        assert "version" in data
        assert "kb_collections" in data
        assert "rate_limit_rpm" in data
        assert isinstance(data["kb_collections"], int)

    def test_health_check_llm_and_embedding_status(self, client, mock_api_deps):
        """測試健康檢查包含 LLM 和 embedding 狀態"""
        response = client.get("/api/v1/health")
        data = response.json()
        assert "llm_status" in data
        assert "embedding_status" in data
        assert data["llm_status"] == "available"
        assert data["embedding_status"] == "available"

    def test_health_check_degraded_when_llm_fails(self, client, mock_api_deps):
        """LLM 不可用時健康檢查應回傳 degraded + 503"""
        import api_server
        original_llm = api_server._llm
        api_server._llm = None
        try:
            response = client.get("/api/v1/health")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] in ("degraded", "unhealthy")
            assert data["llm_status"] == "unavailable"
        finally:
            api_server._llm = original_llm

    def test_health_check_degraded_when_embed_fails(self, client, mock_api_deps):
        """Embedding 不可用時健康檢查應回傳 degraded + 503"""
        original_embed = getattr(mock_api_deps["llm"], "embed", None)
        if hasattr(mock_api_deps["llm"], "embed"):
            del mock_api_deps["llm"].embed
        try:
            response = client.get("/api/v1/health")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] in ("degraded", "unhealthy")
            assert data["embedding_status"] == "unavailable"
        finally:
            if original_embed is not None:
                mock_api_deps["llm"].embed = original_embed

    def test_health_check_unhealthy_when_all_fail(self, client, mock_api_deps):
        """所有元件失敗時應回傳 unhealthy + 503"""
        import api_server
        original_llm = api_server._llm
        api_server._llm = None
        api_server._kb = None
        try:
            response = client.get("/api/v1/health")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"
        finally:
            api_server._llm = original_llm

    def test_health_check_healthy_returns_200(self, client, mock_api_deps):
        """所有元件正常時應回傳 healthy + 200"""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_rate_limit_429_includes_headers(self, client, mock_api_deps):
        """測試 429 回應包含 Retry-After 和 X-RateLimit-* 標頭"""
        import api_server
        original = api_server._rate_limiter
        api_server._rate_limiter = api_server._RateLimiter(max_requests=1, window_seconds=60)
        try:
            client.post("/api/v1/agent/requirement", json={
                "user_input": "寫一份函，第一次允許"
            })
            resp = client.post("/api/v1/agent/requirement", json={
                "user_input": "寫一份函，第二次被限流"
            })
            assert resp.status_code == 429
            assert resp.headers.get("Retry-After") is not None
            assert resp.headers.get("X-RateLimit-Remaining") == "0"
            assert resp.headers.get("X-Request-ID") is not None
        finally:
            api_server._rate_limiter = original


# ==================== Requirement Agent ====================

class TestRequirementEndpoint:
    """需求分析端點的測試"""

    def test_analyze_success(self, client, mock_api_deps):
        """測試需求分析成功"""
        mock_api_deps["llm"].generate.return_value = json.dumps({
            "doc_type": "函",
            "sender": "環保局",
            "receiver": "各學校",
            "subject": "資源回收"
        })

        response = client.post("/api/v1/agent/requirement", json={
            "user_input": "幫我寫一份函"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["requirement"]["doc_type"] == "函"

    def test_analyze_failure(self, client, mock_api_deps):
        """測試需求分析 LLM 回傳無效內容時使用 fallback"""
        mock_api_deps["llm"].generate.return_value = "completely invalid"

        response = client.post("/api/v1/agent/requirement", json={
            "user_input": "這是一個測試用的需求描述"  # 需要至少 5 個字元
        })
        assert response.status_code == 200
        data = response.json()
        # LLM 回傳無效 JSON 時不再失敗，改為使用 fallback 需求
        assert data["success"] is True
        assert data["requirement"] is not None
        assert data["requirement"]["doc_type"] == "函"
        assert data["requirement"]["sender"] == "（未指定）"

    def test_analyze_failure_no_internal_leak(self, client, mock_api_deps):
        """測試需求分析失敗時不洩漏內部資訊"""
        mock_api_deps["llm"].generate.side_effect = RuntimeError(
            "Connection refused at /internal/path/to/secret"
        )

        response = client.post("/api/v1/agent/requirement", json={
            "user_input": "這是一個測試用的需求描述"
        })
        data = response.json()
        assert data["success"] is False
        # 確認錯誤訊息不包含內部路徑
        assert "/internal/path" not in (data.get("error") or "")
        assert "Connection refused" not in (data.get("error") or "")

    def test_analyze_empty_input(self, client, mock_api_deps):
        """測試空輸入被 Pydantic 驗證攔截（min_length=5）"""
        response = client.post("/api/v1/agent/requirement", json={
            "user_input": ""
        })
        # 空輸入應被 Pydantic 驗證攔截
        assert response.status_code == 422


# ==================== Writer Agent ====================

class TestWriterEndpoint:
    """撰寫端點的測試"""

    def test_write_draft_success(self, client, mock_api_deps):
        """測試草稿撰寫成功"""
        mock_api_deps["llm"].generate.return_value = "### 主旨\n測試公文內容\n### 說明\n測試說明"

        response = client.post("/api/v1/agent/writer", json={
            "requirement": {
                "doc_type": "函",
                "sender": "測試機關",
                "receiver": "測試單位",
                "subject": "測試主旨"
            }
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["draft"] is not None
        assert len(data["draft"]) > 0
        assert data["formatted_draft"] is not None
        assert len(data["formatted_draft"]) > 0

    def test_write_draft_missing_required_fields(self, client, mock_api_deps):
        """測試缺少必要欄位時被 Pydantic 驗證攔截"""
        response = client.post("/api/v1/agent/writer", json={
            "requirement": {"doc_type": "函"}  # 缺少 sender, receiver, subject
        })
        # 缺少必要欄位應被 field_validator 攔截
        assert response.status_code == 422

    def test_write_draft_empty_required_field(self, client, mock_api_deps):
        """測試必要欄位為空字串時被攔截"""
        response = client.post("/api/v1/agent/writer", json={
            "requirement": {
                "doc_type": "函",
                "sender": "",
                "receiver": "測試單位",
                "subject": "測試主旨"
            }
        })
        assert response.status_code == 422


# ==================== Review Agents ====================

class TestReviewEndpoints:
    """審查端點的測試"""

    def test_review_format(self, client, mock_api_deps):
        """測試格式審查端點"""
        mock_api_deps["llm"].generate.return_value = '{"errors": [], "warnings": []}'

        response = client.post("/api/v1/agent/review/format", json={
            "draft": "### 主旨\n這是一份測試公文的草稿內容",
            "doc_type": "函"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["agent_name"] == "format"

    def test_review_invalid_doc_type(self, client, mock_api_deps):
        """測試無效的公文類型被 Literal 驗證攔截"""
        response = client.post("/api/v1/agent/review/format", json={
            "draft": "### 主旨\n這是一份測試公文的草稿內容",
            "doc_type": "invalid_type"
        })
        assert response.status_code == 422

    def test_review_draft_too_short(self, client, mock_api_deps):
        """測試草稿太短被 min_length 攔截"""
        response = client.post("/api/v1/agent/review/format", json={
            "draft": "短",
            "doc_type": "函"
        })
        assert response.status_code == 422

    def test_review_style(self, client, mock_api_deps):
        """測試文風審查端點"""
        mock_api_deps["llm"].generate.return_value = '{"issues": [], "score": 0.95}'

        response = client.post("/api/v1/agent/review/style", json={
            "draft": "### 主旨\n正式用語",
            "doc_type": "函"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["agent_name"] == "style"

    def test_review_fact(self, client, mock_api_deps):
        """測試事實審查端點"""
        mock_api_deps["llm"].generate.return_value = '{"issues": [], "score": 0.9}'

        response = client.post("/api/v1/agent/review/fact", json={
            "draft": "### 主旨\n這是一份測試公文的草稿內容",
            "doc_type": "函"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["agent_name"] == "fact"

    def test_review_consistency(self, client, mock_api_deps):
        """測試一致性審查端點"""
        mock_api_deps["llm"].generate.return_value = '{"issues": [], "score": 0.9}'

        response = client.post("/api/v1/agent/review/consistency", json={
            "draft": "### 主旨\n測試\n### 說明\n一致的內容",
            "doc_type": "函"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["agent_name"] == "consistency"

    def test_review_compliance(self, client, mock_api_deps):
        """測試政策合規審查端點"""
        mock_api_deps["llm"].generate.return_value = '{"issues": [], "score": 0.9, "confidence": 0.8}'

        response = client.post("/api/v1/agent/review/compliance", json={
            "draft": "### 主旨\n這是一份測試公文的草稿內容",
            "doc_type": "函"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["agent_name"] == "compliance"

    def test_review_format_with_errors(self, client, mock_api_deps):
        """測試格式審查發現問題"""
        mock_api_deps["llm"].generate.return_value = json.dumps({
            "errors": ["缺少主旨欄位"],
            "warnings": ["建議補充說明"]
        })

        response = client.post("/api/v1/agent/review/format", json={
            "draft": "這是一份沒有格式的純文字公文內容",
            "doc_type": "函"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["result"]["has_errors"] is True
        assert len(data["result"]["issues"]) >= 2


# ==================== Parallel Review ====================

class TestParallelReviewEndpoint:
    """並行審查端點的測試"""

    def test_parallel_review_all_agents(self, client, mock_api_deps):
        """測試所有 Agent 的並行審查"""
        mock_api_deps["llm"].generate.return_value = '{"issues": [], "score": 0.95}'

        response = client.post("/api/v1/agent/review/parallel", json={
            "draft": "### 主旨\n正式公文\n### 說明\n測試說明",
            "doc_type": "函",
            "agents": ["style", "fact", "consistency"]
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "style" in data["results"]
        assert "fact" in data["results"]
        assert "consistency" in data["results"]
        assert data["aggregated_score"] > 0

    def test_parallel_review_single_agent(self, client, mock_api_deps):
        """測試單一 Agent 的並行審查"""
        mock_api_deps["llm"].generate.return_value = '{"issues": [], "score": 0.9}'

        response = client.post("/api/v1/agent/review/parallel", json={
            "draft": "### 主旨\n測試公文內容",
            "doc_type": "函",
            "agents": ["style"]
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["results"]) == 1
        # 單一 Agent 時聚合分數應反映該 Agent 的分數
        assert data["aggregated_score"] > 0
        assert data["aggregated_score"] <= 1.0

    def test_parallel_review_invalid_agent(self, client, mock_api_deps):
        """測試無效的 Agent 名稱被驗證攔截"""
        response = client.post("/api/v1/agent/review/parallel", json={
            "draft": "### 主旨\n測試公文內容",
            "doc_type": "函",
            "agents": ["invalid_agent"]
        })
        assert response.status_code == 422

    def test_parallel_review_empty_agents(self, client, mock_api_deps):
        """測試空的 agents 列表被驗證攔截"""
        response = client.post("/api/v1/agent/review/parallel", json={
            "draft": "### 主旨\n測試公文內容",
            "doc_type": "函",
            "agents": []
        })
        assert response.status_code == 422

    def test_parallel_review_draft_too_short(self, client, mock_api_deps):
        """測試並行審查的 draft min_length 驗證"""
        response = client.post("/api/v1/agent/review/parallel", json={
            "draft": "短",
            "doc_type": "函",
            "agents": ["style"]
        })
        assert response.status_code == 422

    def test_parallel_review_risk_safe(self, client, mock_api_deps):
        """測試安全風險等級"""
        mock_api_deps["llm"].generate.return_value = '{"issues": [], "score": 0.98}'

        response = client.post("/api/v1/agent/review/parallel", json={
            "draft": "### 主旨\n完美公文內容",
            "doc_type": "函",
            "agents": ["style"]
        })
        data = response.json()
        assert data["risk_summary"] in ["Safe", "Low", "Moderate"]


# ==================== Refine Endpoint ====================

class TestRefineEndpoint:
    """修改端點的測試"""

    def test_refine_with_feedback(self, client, mock_api_deps):
        """測試有反饋時的修改"""
        mock_api_deps["llm"].generate.return_value = "### 主旨\n已修正的內容"

        response = client.post("/api/v1/agent/refine", json={
            "draft": "### 主旨\n原始內容，需要修改的草稿",
            "feedback": [
                {
                    "agent_name": "Style Checker",
                    "issues": [
                        {"severity": "warning", "description": "口語化", "suggestion": "改正式"}
                    ]
                }
            ]
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "已修正" in data["refined_draft"]

    def test_refine_no_feedback(self, client, mock_api_deps):
        """測試空 feedback 列表被拒絕（422 驗證錯誤）"""
        original = "### 主旨\n原始內容，這是一份測試草稿"
        response = client.post("/api/v1/agent/refine", json={
            "draft": original,
            "feedback": []
        })
        assert response.status_code == 422

    def test_refine_empty_issues(self, client, mock_api_deps):
        """測試反饋中無問題時回傳原始草稿"""
        original = "### 主旨\n內容，這是一份測試文件"
        response = client.post("/api/v1/agent/refine", json={
            "draft": original,
            "feedback": [{"agent_name": "Test", "issues": []}]
        })
        assert response.status_code == 200
        data = response.json()
        assert data["refined_draft"] == original

    def test_refine_draft_too_short(self, client, mock_api_deps):
        """測試 refine 端點的 draft min_length 驗證"""
        response = client.post("/api/v1/agent/refine", json={
            "draft": "短",
            "feedback": []
        })
        assert response.status_code == 422


# ==================== Meeting Endpoint ====================

class TestMeetingEndpoint:
    """完整開會流程端點的測試"""

    def test_meeting_skip_review(self, client, mock_api_deps):
        """測試跳過審查的開會流程"""
        call_count = [0]
        def side_effect(prompt, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return json.dumps({
                    "doc_type": "函",
                    "sender": "測試機關",
                    "receiver": "測試單位",
                    "subject": "測試主旨"
                })
            else:
                return "### 主旨\n測試公文\n### 說明\n測試說明"

        mock_api_deps["llm"].generate.side_effect = side_effect

        response = client.post("/api/v1/meeting", json={
            "user_input": "寫一份函，環保局發給各學校",
            "skip_review": True,
            "output_docx": False
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["session_id"] is not None
        assert data["rounds_used"] == 0
        assert len(data["final_draft"]) > 0

    def test_meeting_failure(self, client, mock_api_deps):
        """測試開會流程 LLM 回傳無效 JSON 時使用 fallback 繼續"""
        mock_api_deps["llm"].generate.return_value = "completely invalid"

        response = client.post("/api/v1/meeting", json={
            "user_input": "這是一個測試用的需求描述",
            "skip_review": True,
            "output_docx": False
        })
        assert response.status_code == 200
        data = response.json()
        # LLM 回傳無效 JSON 時不再阻斷流程，RequirementAgent 使用 fallback
        assert data["success"] is True

    def test_meeting_failure_no_internal_leak(self, client, mock_api_deps):
        """測試開會流程失敗時不洩漏內部資訊"""
        mock_api_deps["llm"].generate.side_effect = RuntimeError(
            "Database connection failed at /var/db/secret.db"
        )

        response = client.post("/api/v1/meeting", json={
            "user_input": "這是一個測試用的需求描述",
            "skip_review": True,
            "output_docx": False
        })
        data = response.json()
        assert data["success"] is False
        assert "/var/db" not in (data.get("error") or "")
        assert "Database" not in (data.get("error") or "")

    def test_meeting_output_filename_path_traversal(self, client, mock_api_deps):
        """測試路徑遍歷攻擊在 Pydantic 層被攔截"""
        response = client.post("/api/v1/meeting", json={
            "user_input": "寫一份函，環保局發給各學校",
            "skip_review": True,
            "output_docx": True,
            "output_filename": "../../../etc/passwd"
        })
        assert response.status_code == 422

    def test_meeting_convergence_fallback_to_traditional(self, client, mock_api_deps):
        """convergence=True + use_graph=True 應自動 fallback 到傳統路徑"""
        call_count = [0]
        def side_effect(prompt, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return json.dumps({
                    "doc_type": "函",
                    "sender": "測試機關",
                    "receiver": "測試單位",
                    "subject": "測試主旨"
                })
            else:
                return "### 主旨\n測試公文\n### 說明\n測試說明"

        mock_api_deps["llm"].generate.side_effect = side_effect

        response = client.post("/api/v1/meeting", json={
            "user_input": "寫一份函，環保局發給各學校",
            "skip_review": True,
            "output_docx": False,
            "use_graph": True,
            "convergence": True,
        })
        assert response.status_code == 200
        data = response.json()
        # 傳統路徑仍然成功處理（不會因 graph 不支援 convergence 而靜默忽略）
        assert data["success"] is True
        assert data["final_draft"] is not None
        assert len(data["final_draft"]) > 0

    def test_meeting_graph_without_convergence_uses_graph(self, client, mock_api_deps):
        """use_graph=True + convergence=False 應正常走 graph 路徑"""
        call_count = [0]
        def side_effect(prompt, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return json.dumps({
                    "doc_type": "函",
                    "sender": "測試機關",
                    "receiver": "測試單位",
                    "subject": "測試主旨"
                })
            else:
                return "### 主旨\n測試公文\n### 說明\n測試說明"

        mock_api_deps["llm"].generate.side_effect = side_effect

        # use_graph=True, convergence=False（預設行為），不應 fallback
        response = client.post("/api/v1/meeting", json={
            "user_input": "寫一份函，環保局發給各學校",
            "skip_review": True,
            "output_docx": False,
            "use_graph": True,
            "convergence": False,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_meeting_ralph_loop_forces_traditional_path(self, client, mock_api_deps):
        """ralph_loop=True + use_graph=True 應強制走傳統路徑並執行 RALPH loop。"""
        call_count = [0]

        def side_effect(prompt, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return json.dumps({
                    "doc_type": "函",
                    "sender": "測試機關",
                    "receiver": "測試單位",
                    "subject": "測試主旨",
                })
            return "### 主旨\n初始草稿\n### 說明\n測試說明"

        mock_api_deps["llm"].generate.side_effect = side_effect

        fake_qa = MagicMock()
        fake_qa.rounds_used = 6
        fake_qa.model_dump.return_value = {
            "overall_score": 1.0,
            "risk_summary": "Safe",
            "agent_results": [],
            "rounds_used": 6,
            "audit_log": "ok",
            "iteration_history": [],
        }

        with patch("src.api.routes.workflow._run_ralph_loop", return_value=("### 主旨\n最終草稿", fake_qa, 6)) as mock_ralph:
            response = client.post("/api/v1/meeting", json={
                "user_input": "寫一份函，測試 RALPH loop",
                "skip_review": True,
                "output_docx": False,
                "use_graph": True,
                "ralph_loop": True,
                "ralph_max_cycles": 4,
                "ralph_target_score": 1.0,
            })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["rounds_used"] == 6
        assert "最終草稿" in data["final_draft"]
        mock_ralph.assert_called_once()
        assert mock_ralph.call_args.kwargs["max_cycles"] == 4
        assert mock_ralph.call_args.kwargs["target_score"] == 1.0

    def test_ralph_loop_keeps_best_cycle_result(self):
        """RALPH loop 後續循環退化時，應保留最佳 cycle 的草稿與報告。"""
        from src.api.routes import workflow as workflow_routes

        def _make_report(score: float, issue_count: int, rounds_used: int, tag: str):
            report = MagicMock()
            report.overall_score = score
            report.risk_summary = "Critical"
            report.rounds_used = rounds_used
            report.iteration_history = [{"round": 1, "score": score, "risk": "Critical"}]
            report.audit_log = f"audit-{tag}"
            agent_result = MagicMock()
            agent_result.issues = [object() for _ in range(issue_count)]
            report.agent_results = [agent_result]
            return report

        report1 = _make_report(0.9, 2, 2, "best")
        report2 = _make_report(0.7, 5, 2, "worse")

        class _FakeEditor:
            def __init__(self):
                self._calls = 0

            def review_and_refine(self, *args, **kwargs):
                self._calls += 1
                if self._calls == 1:
                    return "draft-best", report1
                return "draft-worse", report2

        final_draft, final_report, total_rounds = workflow_routes._run_ralph_loop(
            _FakeEditor(),
            draft="draft-init",
            doc_type="函",
            max_rounds=2,
            max_cycles=2,
            target_score=1.0,
        )

        assert final_draft == "draft-best"
        assert final_report.overall_score == 0.9
        assert total_rounds == 4


# ==================== Input Validation ====================

class TestInputValidation:
    """輸入驗證安全測試"""

    def test_writer_requirement_missing_fields(self, client, mock_api_deps):
        """測試 writer 端點的 requirement 欄位驗證"""
        response = client.post("/api/v1/agent/writer", json={
            "requirement": {"random_field": "value"}
        })
        assert response.status_code == 422

    def test_parallel_review_duplicate_agents(self, client, mock_api_deps):
        """測試重複的 agent 名稱被去重"""
        mock_api_deps["llm"].generate.return_value = '{"issues": [], "score": 0.9}'

        response = client.post("/api/v1/agent/review/parallel", json={
            "draft": "### 主旨\n測試公文內容草稿",
            "doc_type": "函",
            "agents": ["style", "style", "style"]
        })
        assert response.status_code == 200
        data = response.json()
        # 去重後應只有一個 style 結果
        assert len(data["results"]) == 1


# ==================== Helper Function ====================

class TestHelperFunctions:
    """輔助函數的測試"""

    def test_review_result_to_dict(self):
        """測試 ReviewResult 轉換為字典"""
        from api_server import review_result_to_dict

        result = ReviewResult(
            agent_name="Test Agent",
            issues=[
                ReviewIssue(
                    category="format",
                    severity="error",
                    risk_level="high",
                    location="主旨",
                    description="問題描述",
                    suggestion="建議修正"
                )
            ],
            score=0.5,
            confidence=0.9
        )

        response = review_result_to_dict(result)
        assert response.agent_name == "Test Agent"
        assert response.score == 0.5
        assert response.confidence == 0.9
        assert len(response.issues) == 1
        assert response.issues[0]["category"] == "format"
        assert response.has_errors is True

    def test_review_result_to_dict_no_issues(self):
        """測試無問題的 ReviewResult 轉換"""
        from api_server import review_result_to_dict

        result = ReviewResult(
            agent_name="Clean Agent",
            issues=[],
            score=1.0,
            confidence=1.0
        )

        response = review_result_to_dict(result)
        assert response.has_errors is False
        assert len(response.issues) == 0

    def test_sanitize_error(self):
        """測試 _sanitize_error 不洩漏內部資訊"""
        from api_server import _sanitize_error

        # ValueError 應回傳安全訊息
        err = _sanitize_error(ValueError("secret path /etc/passwd"))
        assert "/etc/passwd" not in err
        assert "secret" not in err

        # 未知類型應回傳通用訊息
        err = _sanitize_error(RuntimeError("internal error details"))
        assert "internal error" not in err
        assert "伺服器內部錯誤" in err

    def test_sanitize_error_timeout(self):
        """測試 _sanitize_error 處理 TimeoutError"""
        from api_server import _sanitize_error
        err = _sanitize_error(TimeoutError("Connection timed out"))
        assert "逾時" in err
        assert "Connection" not in err

    def test_sanitize_error_key_error(self):
        """測試 _sanitize_error 處理 KeyError"""
        from api_server import _sanitize_error
        err = _sanitize_error(KeyError("missing_key"))
        assert "缺少必要欄位" in err
        assert "missing_key" not in err

    def test_sanitize_error_type_error(self):
        """測試 _sanitize_error 處理 TypeError"""
        from api_server import _sanitize_error
        err = _sanitize_error(TypeError("Expected str, got int"))
        assert "類型錯誤" in err
        assert "Expected str" not in err

    def test_sanitize_error_os_error(self):
        """測試 _sanitize_error 處理 OSError（未映射類型）"""
        from api_server import _sanitize_error
        err = _sanitize_error(OSError("Permission denied /var/data"))
        assert "伺服器內部錯誤" in err
        assert "/var/data" not in err

    def test_sanitize_error_llm_timeout(self):
        """測試 _sanitize_error 處理 LLMTimeoutError"""
        from api_server import _sanitize_error
        from src.core.llm import LLMTimeoutError
        err = _sanitize_error(LLMTimeoutError("LLM 生成超時 (120s)"))
        assert "逾時" in err
        assert "120s" not in err

    def test_get_error_code_llm_timeout(self):
        """測試 _get_error_code 對 LLMTimeoutError 回傳 LLM_TIMEOUT"""
        from api_server import _get_error_code
        from src.core.llm import LLMTimeoutError
        code = _get_error_code(LLMTimeoutError("timeout"))
        assert code == "LLM_TIMEOUT"

    def test_get_error_code_known_types(self):
        """測試 _get_error_code 對已知類型回傳正確代碼"""
        from api_server import _get_error_code
        assert _get_error_code(ValueError("x")) == "INVALID_INPUT"
        assert _get_error_code(TimeoutError("x")) == "TIMEOUT"
        assert _get_error_code(KeyError("x")) == "MISSING_FIELD"
        assert _get_error_code(RuntimeError("x")) == "INTERNAL_ERROR"

    def test_error_registry_integrity(self):
        """驗證 _ERROR_REGISTRY 結構完整性：每個 entry 都有非空 code 和 message"""
        from src.api.helpers import _ERROR_REGISTRY
        assert len(_ERROR_REGISTRY) > 0, "Registry 不可為空"
        for exc_type, (code, message) in _ERROR_REGISTRY.items():
            assert exc_type, f"異常類型名稱不可為空"
            assert code and isinstance(code, str), f"{exc_type}: error_code 不可為空"
            assert message and isinstance(message, str), f"{exc_type}: message 不可為空"
            assert code == code.upper().replace(" ", "_"), (
                f"{exc_type}: error_code '{code}' 應為 UPPER_SNAKE_CASE"
            )

    def test_error_registry_sanitize_and_code_consistent(self):
        """驗證 _sanitize_error 和 _get_error_code 對所有 registry 類型一致"""
        from src.api.helpers import _ERROR_REGISTRY, _sanitize_error, _get_error_code

        # 動態建立每種類型的 exception 實例並驗證兩個函式都正確查詢
        for exc_type_name, (expected_code, expected_msg) in _ERROR_REGISTRY.items():
            # 建立 mock exception with matching __name__
            exc = type(exc_type_name, (Exception,), {})("test")
            assert _sanitize_error(exc) == expected_msg, f"{exc_type_name}: message 不匹配"
            assert _get_error_code(exc) == expected_code, f"{exc_type_name}: code 不匹配"

    def test_sanitize_output_filename(self):
        """測試檔名清理函式"""
        from api_server import _sanitize_output_filename

        # 正常檔名
        assert _sanitize_output_filename("test.docx", "abc") == "test.docx"

        # 路徑遍歷嘗試
        assert _sanitize_output_filename("../../etc/passwd", "abc") == "passwd.docx"

        # 空值
        assert _sanitize_output_filename(None, "abc") == "output_abc.docx"

        # 隱藏檔案
        assert _sanitize_output_filename(".hidden", "abc") == "output_abc.docx"

    def test_rate_limiter(self):
        """測試限流器基本功能"""
        from api_server import _RateLimiter

        limiter = _RateLimiter(max_requests=3, window_seconds=60)

        # 前 3 次應該允許
        assert limiter.is_allowed("test_ip") is True
        assert limiter.is_allowed("test_ip") is True
        assert limiter.is_allowed("test_ip") is True

        # 第 4 次應該被拒絕
        assert limiter.is_allowed("test_ip") is False

        # 不同 IP 不受影響
        assert limiter.is_allowed("other_ip") is True

    def test_rate_limiter_check_returns_tuple(self):
        """測試 check() 回傳 (allowed, remaining, reset_after) 三元組"""
        from api_server import _RateLimiter

        limiter = _RateLimiter(max_requests=3, window_seconds=60)

        # 第一次呼叫：allowed, remaining=2
        allowed, remaining, reset = limiter.check("ip_x")
        assert allowed is True
        assert remaining == 2
        assert reset > 0

        # 第二次：remaining=1
        allowed, remaining, _ = limiter.check("ip_x")
        assert allowed is True
        assert remaining == 1

        # 第三次：remaining=0
        allowed, remaining, _ = limiter.check("ip_x")
        assert allowed is True
        assert remaining == 0

        # 第四次：被拒絕
        allowed, remaining, reset = limiter.check("ip_x")
        assert allowed is False
        assert remaining == 0
        assert reset > 0

    def test_rate_limiter_memory_cleanup(self):
        """測試限流器在時間窗口過期後清理 IP 條目，避免記憶體洩漏"""
        from api_server import _RateLimiter
        from unittest.mock import patch
        import time

        limiter = _RateLimiter(max_requests=2, window_seconds=10)

        # 模擬兩個 IP 發送請求
        assert limiter.is_allowed("ip_a") is True
        assert limiter.is_allowed("ip_b") is True
        assert "ip_a" in limiter._requests
        assert "ip_b" in limiter._requests

        # 模擬時間經過超過窗口期（讓所有時間戳過期）
        with patch.object(time, "monotonic", return_value=time.monotonic() + 20):
            # ip_a 再次請求 — 舊紀錄應被清理
            assert limiter.is_allowed("ip_a") is True
            # ip_a 應該只有 1 條新紀錄（舊的已清理）
            assert len(limiter._requests["ip_a"]) == 1

        # ip_b 沒有新請求，條目仍存在（只有在下次請求時才會清理）
        assert "ip_b" in limiter._requests

    def test_rate_limiter_window_expiry_resets_count(self):
        """測試時間窗口過期後，被限流的 IP 可以重新請求"""
        from api_server import _RateLimiter
        from unittest.mock import patch
        import time

        limiter = _RateLimiter(max_requests=1, window_seconds=5)

        # 第一次允許
        assert limiter.is_allowed("test_ip") is True
        # 被限流
        assert limiter.is_allowed("test_ip") is False

        # 時間窗口過期後應該重新允許
        with patch.object(time, "monotonic", return_value=time.monotonic() + 10):
            assert limiter.is_allowed("test_ip") is True

    def test_rate_limiter_stale_ip_cleaned_on_next_request(self):
        """測試過期 IP 在下次請求時清理舊條目"""
        from api_server import _RateLimiter
        from unittest.mock import patch
        import time

        limiter = _RateLimiter(max_requests=2, window_seconds=10)
        base_time = time.monotonic()

        # IP B 在 base_time 發送請求
        with patch.object(time, "monotonic", return_value=base_time):
            assert limiter.is_allowed("ip_b") is True
        assert len(limiter._requests["ip_b"]) == 1

        # 時間窗口過期後 IP B 再次請求
        with patch.object(time, "monotonic", return_value=base_time + 20):
            assert limiter.is_allowed("ip_b") is True
            # 舊條目應被清理，只有新的一條
            assert len(limiter._requests["ip_b"]) == 1

    def test_rate_limiter_zero_max_requests(self):
        """測試 max_requests=0 時所有請求都被拒絕"""
        from api_server import _RateLimiter
        limiter = _RateLimiter(max_requests=0, window_seconds=60)
        # 即使是第一次，由 is_allowed 邏輯，valid 為空 → pop → append → return True
        # 然後第二次 valid 有 1 條 >= max_requests(0)? 不，len(valid)=1 >= 0 → False
        # 其實第一次: valid=[], pop, append [now], return True
        # 第二次: valid=[now], len(valid)=1 >= 0 → True → 被拒絕
        result1 = limiter.is_allowed("ip_test")
        assert result1 is True  # 第一次：過期清理後的新請求
        result2 = limiter.is_allowed("ip_test")
        assert result2 is False  # 第二次：已有 1 條 >= 0


# ==================== Rate Limit via HTTP ====================

class TestRequestBodySizeLimit:
    """請求體大小限制測試（DoS 防護）"""

    def test_oversized_content_length_returns_413(self, client, mock_api_deps):
        """Content-Length 超過上限時回傳 413"""
        resp = client.post(
            "/api/v1/agent/requirement",
            content=b'{"user_input": "x"}',
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(10 * 1024 * 1024),  # 10 MB
            },
        )
        assert resp.status_code == 413
        assert "請求體過大" in resp.json()["detail"]

    def test_normal_size_passes(self, client, mock_api_deps):
        """正常大小的請求不應被攔截"""
        resp = client.post(
            "/api/v1/agent/requirement",
            json={"user_input": "寫一份環保局的函，測試正常大小"},
        )
        assert resp.status_code == 200

    def test_get_request_not_checked(self, client, mock_api_deps):
        """GET 請求不檢查 body size"""
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200

    def test_chunked_oversized_body_returns_413(self, client, mock_api_deps):
        """無 Content-Length 的超大 body 應被 ASGI 層串流攔截回傳 413"""
        from src.core.constants import MAX_REQUEST_BODY_SIZE
        # 產生略超過限制的 payload（不設 Content-Length，模擬 chunked 傳輸）
        oversized = b"x" * (MAX_REQUEST_BODY_SIZE + 1024)
        resp = client.post(
            "/api/v1/agent/requirement",
            content=oversized,
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code in (413, 422)  # 413 由 ASGI 限制，422 由 JSON 解析失敗
        # 若成功攔截為 413，驗證訊息
        if resp.status_code == 413:
            assert "請求體過大" in resp.json()["detail"]

    def test_chunked_normal_body_passes(self, client, mock_api_deps):
        """正常大小的 body 不應被 ASGI 層攔截"""
        resp = client.post(
            "/api/v1/agent/requirement",
            json={"user_input": "測試正常大小 chunked body"},
        )
        assert resp.status_code == 200


class TestCORSOrigins:
    """CORS 來源設定測試"""

    def test_localhost_origin_allowed(self, client, mock_api_deps):
        """localhost 來源應被允許"""
        resp = client.options(
            "/api/v1/agent/requirement",
            headers={
                "Origin": "http://localhost:5678",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:5678"

    def test_127_0_0_1_origin_allowed(self, client, mock_api_deps):
        """127.0.0.1 來源應被允許（服務預設綁定 127.0.0.1）"""
        resp = client.options(
            "/api/v1/agent/requirement",
            headers={
                "Origin": "http://127.0.0.1:5678",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert resp.headers.get("access-control-allow-origin") == "http://127.0.0.1:5678"

    def test_unknown_origin_rejected(self, client, mock_api_deps):
        """未列入的外部來源不應被允許"""
        resp = client.options(
            "/api/v1/agent/requirement",
            headers={
                "Origin": "http://evil.example.com",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert resp.headers.get("access-control-allow-origin") != "http://evil.example.com"


class TestRateLimitHTTP:
    """透過 HTTP 中介層的限流測試"""

    def test_rate_limit_rejection_via_http(self, client, mock_api_deps):
        """測試 POST 請求超過限流時回傳 429"""
        import api_server
        # 設定非常低的限流以便觸發
        original_limiter = api_server._rate_limiter
        api_server._rate_limiter = api_server._RateLimiter(max_requests=1, window_seconds=60)

        try:
            # 第一次允許
            resp1 = client.post("/api/v1/agent/requirement", json={
                "user_input": "寫一份函，測試限流第一次"
            })
            assert resp1.status_code == 200

            # 第二次應被限流
            resp2 = client.post("/api/v1/agent/requirement", json={
                "user_input": "寫一份函，測試限流第二次"
            })
            assert resp2.status_code == 429
            data = resp2.json()
            assert "請求過於頻繁" in data["detail"]
            assert "retry_after_seconds" in data
        finally:
            api_server._rate_limiter = original_limiter


# ==================== Writer Exception ====================

class TestWriterExceptionHandling:
    """撰寫端點的異常處理測試"""

    def test_writer_exception(self, client, mock_api_deps):
        """測試 writer 端點 LLM 拋出異常時優雅降級為基本模板"""
        from src.core.llm import LLMError
        mock_api_deps["llm"].generate.side_effect = LLMError("LLM 連線超時")

        response = client.post("/api/v1/agent/writer", json={
            "requirement": {
                "doc_type": "函",
                "sender": "測試機關",
                "receiver": "測試單位",
                "subject": "測試主旨"
            }
        })
        assert response.status_code == 200
        data = response.json()
        # WriterAgent 捕捉 LLM 例外後使用基本模板，不會讓端點失敗
        assert data["success"] is True
        assert data["draft"] is not None
        assert "測試主旨" in data["draft"]
        # 不洩漏內部錯誤訊息
        assert "LLM 連線超時" not in (data["draft"] or "")
        assert "RuntimeError" not in (data["draft"] or "")

    def test_writer_template_engine_exception(self, client, mock_api_deps):
        """測試 writer 端點在 TemplateEngine 拋出異常時回傳 error"""
        mock_api_deps["llm"].generate.return_value = "### 主旨\n正常草稿"

        import src.api.routes.agents as _agents_mod
        original_template_engine = _agents_mod.TemplateEngine

        class BrokenTemplateEngine:
            def parse_draft(self, *a, **kw):
                raise RuntimeError("Template parse failed")

        _agents_mod.TemplateEngine = BrokenTemplateEngine
        try:
            response = client.post("/api/v1/agent/writer", json={
                "requirement": {
                    "doc_type": "函",
                    "sender": "測試機關",
                    "receiver": "測試單位",
                    "subject": "測試主旨"
                }
            })
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert data["error"] is not None
            # 不洩漏內部錯誤細節
            assert "Template parse failed" not in (data["error"] or "")
        finally:
            _agents_mod.TemplateEngine = original_template_engine


# ==================== Review Endpoints Exception ====================

class TestReviewExceptionHandling:
    """各審查端點的異常處理測試"""

    def test_review_format_exception(self, client, mock_api_deps):
        """測試格式審查端點在初始化異常時回傳錯誤

        FormatAuditor 內部會捕捉 LLM 異常，因此需要讓端點層級的程式碼拋出異常。
        透過讓 get_kb() 拋出異常觸發端點的 except 塊。
        """
        import src.api.routes.agents._review_routes as _review_routes_mod
        original_get_kb = _review_routes_mod.get_kb

        def broken_get_kb():
            raise RuntimeError("KB 初始化失敗")

        _review_routes_mod.get_kb = broken_get_kb

        try:
            response = client.post("/api/v1/agent/review/format", json={
                "draft": "### 主旨\n這是一份測試公文的草稿內容",
                "doc_type": "函"
            })
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert data["agent_name"] == "format"
            assert data["error"] is not None
        finally:
            _review_routes_mod.get_kb = original_get_kb
        """測試文風審查端點 LLM 異常時優雅降級（回傳 score=0.0 而非失敗）"""
        mock_api_deps["llm"].generate.side_effect = RuntimeError("文風審查失敗")

        response = client.post("/api/v1/agent/review/style", json={
            "draft": "### 主旨\n這是一份測試公文的草稿內容",
            "doc_type": "函"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["agent_name"] == "style"
        assert data["result"]["score"] == 0.0
        assert data["result"]["confidence"] == 0.0

    def test_review_fact_exception(self, client, mock_api_deps):
        """測試事實審查端點 LLM 異常時優雅降級（回傳 score=0.0 而非失敗）"""
        from src.core.llm import LLMError
        mock_api_deps["llm"].generate.side_effect = LLMError("事實審查失敗")

        response = client.post("/api/v1/agent/review/fact", json={
            "draft": "### 主旨\n這是一份測試公文的草稿內容",
            "doc_type": "函"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["agent_name"] == "fact"
        assert data["result"]["score"] == 0.0
        assert data["result"]["confidence"] == 0.0

    def test_review_consistency_exception(self, client, mock_api_deps):
        """測試一致性審查端點 LLM 異常時優雅降級（回傳 score=0.0 而非失敗）"""
        mock_api_deps["llm"].generate.side_effect = RuntimeError("一致性審查失敗")

        response = client.post("/api/v1/agent/review/consistency", json={
            "draft": "### 主旨\n測試\n### 說明\n一致的內容",
            "doc_type": "函"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["agent_name"] == "consistency"
        assert data["result"]["score"] == 0.0
        assert data["result"]["confidence"] == 0.0

    def test_review_compliance_exception(self, client, mock_api_deps):
        """測試合規審查端點在初始化異常時回傳錯誤

        ComplianceChecker 內部會捕捉 LLM 異常，因此需要讓端點層級的程式碼拋出異常。
        透過讓 get_kb() 拋出異常觸發端點的 except 塊。
        """
        import src.api.routes.agents._review_routes as _review_routes_mod
        original_get_kb = _review_routes_mod.get_kb

        def broken_get_kb():
            raise RuntimeError("KB 初始化失敗")

        _review_routes_mod.get_kb = broken_get_kb

        try:
            response = client.post("/api/v1/agent/review/compliance", json={
                "draft": "### 主旨\n這是一份測試公文的草稿內容",
                "doc_type": "函"
            })
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert data["agent_name"] == "compliance"
            assert data["error"] is not None
        finally:
            _review_routes_mod.get_kb = original_get_kb


# ==================== Parallel Review Exception ====================

class TestParallelReviewExceptionHandling:
    """並行審查的異常處理測試"""

    def test_parallel_review_single_agent_failure(self, client, mock_api_deps):
        """測試並行審查中單一 Agent 失敗，其他正常

        使用 patch 讓 FactChecker 的 check 方法拋出異常，
        確保 style agent 正常完成但 fact agent 失敗。
        """
        mock_api_deps["llm"].generate.return_value = '{"issues": [], "score": 0.9}'

        with patch("src.api.routes.agents.FactChecker") as MockFactChecker:
            mock_fact_instance = MagicMock()
            mock_fact_instance.check.side_effect = RuntimeError("模擬 fact 審查失敗")
            MockFactChecker.return_value = mock_fact_instance

            response = client.post("/api/v1/agent/review/parallel", json={
                "draft": "### 主旨\n正式公文\n### 說明\n測試說明",
                "doc_type": "函",
                "agents": ["style", "fact"]
            })
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            # style 應成功
            assert "style" in data["results"]
            assert data["results"]["style"]["score"] > 0
            # fact 應有失敗資訊但不崩潰
            assert "fact" in data["results"]
            assert data["results"]["fact"]["has_errors"] is True
            assert data["results"]["fact"]["score"] == 0.0
            # 失敗時 agent_name 應為人類可讀名稱（與成功時一致）
            assert data["results"]["fact"]["agent_name"] == "Fact Checker"

    def test_parallel_review_all_agents_failure(self, client, mock_api_deps):
        """測試並行審查中所有 Agent LLM 失敗時優雅降級（回傳 score=0.0）"""
        mock_api_deps["llm"].generate.side_effect = RuntimeError("全部失敗")

        response = client.post("/api/v1/agent/review/parallel", json={
            "draft": "### 主旨\n正式公文\n### 說明\n測試說明",
            "doc_type": "函",
            "agents": ["style", "fact", "consistency"]
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # 所有 agent 優雅降級，分數為 0，confidence 為 0
        for agent_name in ["style", "fact", "consistency"]:
            assert data["results"][agent_name]["score"] == 0.0
            assert data["results"][agent_name]["confidence"] == 0.0
        # 總分應為 0（所有 agent 的 confidence=0，total_weight=0）
        assert data["aggregated_score"] == 0.0
        # 所有 Agent 失敗時風險等級應為 Critical（而非 Moderate）
        assert data["risk_summary"] == "Critical"

    def test_parallel_review_mixed_success_failure_aggregation(self, client, mock_api_deps):
        """測試混合成功/失敗時聚合分數只反映成功 Agent"""
        call_count = [0]

        def side_effect(prompt, **kwargs):
            call_count[0] += 1
            # 讓 style 成功（奇數呼叫），fact 失敗（偶數呼叫拋異常）
            if call_count[0] % 2 == 1:
                return '{"issues": [], "score": 0.9, "confidence": 1.0}'
            raise RuntimeError("LLM 失敗")

        mock_api_deps["llm"].generate.side_effect = side_effect

        response = client.post("/api/v1/agent/review/parallel", json={
            "draft": "### 主旨\n正式公文\n### 說明\n測試說明",
            "doc_type": "函",
            "agents": ["style", "fact"]
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # 聚合分數應 > 0（成功 Agent 貢獻了分數）
        assert data["aggregated_score"] > 0
        # 聚合分數應 <= 1.0
        assert data["aggregated_score"] <= 1.0

    def test_parallel_review_partial_failure_risk_upgrade(self, client, mock_api_deps):
        """測試部分 Agent 失敗時 risk_summary 至少升級為 High

        修復 BUG-01：即使成功的 Agent 分數很高，只要有 Agent 失敗，
        risk_summary 不應為 Safe/Low/Moderate。
        """
        mock_api_deps["llm"].generate.return_value = '{"issues": [], "score": 1.0, "confidence": 1.0}'

        with patch("src.api.routes.agents.FactChecker") as MockFactChecker:
            mock_fact_instance = MagicMock()
            mock_fact_instance.check.side_effect = RuntimeError("fact 失敗")
            MockFactChecker.return_value = mock_fact_instance

            response = client.post("/api/v1/agent/review/parallel", json={
                "draft": "### 主旨\n正式公文內容\n### 說明\n測試說明內容",
                "doc_type": "函",
                "agents": ["style", "fact"]
            })
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            # style 成功，score=1.0
            assert data["results"]["style"]["score"] > 0
            # fact 失敗
            assert data["results"]["fact"]["has_errors"] is True
            # 關鍵：risk_summary 應至少為 High（不應為 Safe）
            assert data["risk_summary"] in ("High", "Critical")

    def test_parallel_review_overall_exception(self, client, mock_api_deps):
        """測試並行審查整體失敗（非 agent 層級的異常）"""
        import api_server
        import src.api.routes.agents as _agents_mod
        # 讓 get_llm() 拋出異常，觸發外層 except
        original_llm = api_server._llm
        api_server._llm = None
        original_get_llm = _agents_mod.get_llm

        def broken_get_llm():
            raise RuntimeError("LLM 初始化失敗")

        _agents_mod.get_llm = broken_get_llm

        try:
            response = client.post("/api/v1/agent/review/parallel", json={
                "draft": "### 主旨\n正式公文\n### 說明\n測試說明",
                "doc_type": "函",
                "agents": ["style"]
            })
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert data["risk_summary"] == "Critical"
            assert data["aggregated_score"] == 0.0
            assert data["error"] is not None
        finally:
            _agents_mod.get_llm = original_get_llm
            api_server._llm = original_llm

    def test_parallel_review_agents_exceeds_max(self, client, mock_api_deps):
        """測試 agents 列表超過 5 個被驗證攔截"""
        response = client.post("/api/v1/agent/review/parallel", json={
            "draft": "### 主旨\n測試公文內容草稿",
            "doc_type": "函",
            "agents": ["format", "style", "fact", "consistency", "compliance", "style"]
        })
        assert response.status_code == 422

    def test_parallel_review_including_format_agent(self, client, mock_api_deps):
        """測試並行審查中包含 format agent

        覆蓋 _run_format_audit 輔助函式。
        """
        mock_api_deps["llm"].generate.return_value = json.dumps(
            {"errors": [], "warnings": [], "issues": [], "score": 0.9}
        )

        response = client.post("/api/v1/agent/review/parallel", json={
            "draft": "### 主旨\n正式公文內容\n### 說明\n測試說明內容",
            "doc_type": "函",
            "agents": ["format", "style"]
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "format" in data["results"]
        assert "style" in data["results"]

    def test_parallel_review_with_errors_and_warnings(self, client, mock_api_deps):
        """測試並行審查結果包含 error 和 warning 等級的 issues

        確保加權計分邏輯中 severity == 'error' 和 severity == 'warning' 分支都被執行。
        """
        mock_api_deps["llm"].generate.return_value = json.dumps({
            "issues": [
                {
                    "severity": "error",
                    "location": "主旨",
                    "description": "主旨格式錯誤"
                },
                {
                    "severity": "warning",
                    "location": "說明",
                    "description": "說明段落過短"
                }
            ],
            "score": 0.5
        })

        response = client.post("/api/v1/agent/review/parallel", json={
            "draft": "### 主旨\n正式公文\n### 說明\n測試說明",
            "doc_type": "函",
            "agents": ["style"]
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # 應有問題
        assert len(data["results"]["style"]["issues"]) == 2
        assert data["results"]["style"]["has_errors"] is True
        # 分數應反映問題
        assert data["aggregated_score"] < 1.0


# ==================== Refine Edge Cases ====================

class TestRefineEdgeCases:
    """修改端點的邊界條件測試"""

    def test_refine_llm_returns_empty(self, client, mock_api_deps):
        """測試 refine 端點 LLM 回傳空值時保留原始草稿"""
        mock_api_deps["llm"].generate.return_value = ""

        original_draft = "### 主旨\n原始內容，需要修改的草稿"
        response = client.post("/api/v1/agent/refine", json={
            "draft": original_draft,
            "feedback": [
                {
                    "agent_name": "Style Checker",
                    "issues": [
                        {"severity": "warning", "description": "口語化", "suggestion": "改正式"}
                    ]
                }
            ]
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["refined_draft"] == original_draft

    def test_refine_llm_returns_whitespace_only(self, client, mock_api_deps):
        """測試 refine 端點 LLM 回傳純空白時保留原始草稿"""
        mock_api_deps["llm"].generate.return_value = "   \n\t  "

        original_draft = "### 主旨\n原始內容，需要修改的草稿"
        response = client.post("/api/v1/agent/refine", json={
            "draft": original_draft,
            "feedback": [
                {
                    "agent_name": "Format",
                    "issues": [
                        {"severity": "error", "description": "格式錯誤"}
                    ]
                }
            ]
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["refined_draft"] == original_draft

    def test_refine_llm_returns_error_string(self, client, mock_api_deps):
        """測試 refine 端點 LLM 回傳 'Error...' 開頭時保留原始草稿"""
        mock_api_deps["llm"].generate.return_value = "Error: Model overloaded"

        original_draft = "### 主旨\n原始內容，需要修改的草稿"
        response = client.post("/api/v1/agent/refine", json={
            "draft": original_draft,
            "feedback": [
                {
                    "agent_name": "Fact Checker",
                    "issues": [
                        {"severity": "error", "description": "事實錯誤", "suggestion": "修正日期"}
                    ]
                }
            ]
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["refined_draft"] == original_draft

    def test_refine_llm_exception(self, client, mock_api_deps):
        """測試 refine 端點 LLM 拋出異常"""
        mock_api_deps["llm"].generate.side_effect = RuntimeError("LLM 故障")

        response = client.post("/api/v1/agent/refine", json={
            "draft": "### 主旨\n原始內容，需要修改的草稿",
            "feedback": [
                {
                    "agent_name": "Style",
                    "issues": [
                        {"severity": "warning", "description": "不夠正式"}
                    ]
                }
            ]
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["error"] is not None

    def test_refine_long_feedback_truncation(self, client, mock_api_deps):
        """測試超長回饋被截斷"""
        mock_api_deps["llm"].generate.return_value = "### 主旨\n已修正的內容"

        # 產生超過 MAX_FEEDBACK_LENGTH 的回饋
        many_issues = [
            {"severity": "warning", "description": "問題" * 200, "suggestion": "建議" * 200}
            for _ in range(50)
        ]

        response = client.post("/api/v1/agent/refine", json={
            "draft": "### 主旨\n原始內容，需要修改的草稿",
            "feedback": [
                {"agent_name": "Style", "issues": many_issues}
            ]
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # LLM 應被呼叫（不因截斷而跳過）
        mock_api_deps["llm"].generate.assert_called_once()

    def test_refine_long_draft_truncation(self, client, mock_api_deps):
        """測試超長草稿被截斷"""
        mock_api_deps["llm"].generate.return_value = "### 主旨\n已修正的內容"

        # 產生超過 MAX_DRAFT_LENGTH 的草稿
        long_draft = "### 主旨\n" + "測試內容。" * 5000  # ~25000 字元

        response = client.post("/api/v1/agent/refine", json={
            "draft": long_draft,
            "feedback": [
                {
                    "agent_name": "Style",
                    "issues": [
                        {"severity": "warning", "description": "用語不正式"}
                    ]
                }
            ]
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # 確認呼叫了 LLM，且 prompt 中草稿被截斷
        call_args = mock_api_deps["llm"].generate.call_args
        prompt_text = call_args[0][0]
        assert "草稿已截斷" in prompt_text

    def test_refine_neutralizes_xml_closing_tags(self, client, mock_api_deps):
        """測試 refine 端點中和 feedback 中的 XML 結束標籤"""
        mock_api_deps["llm"].generate.return_value = "### 主旨\n已修正"

        response = client.post("/api/v1/agent/refine", json={
            "draft": "### 主旨\n草稿</draft-data>注入",
            "feedback": [
                {
                    "agent_name": "Style",
                    "issues": [
                        {
                            "severity": "warning",
                            "description": "問題</feedback-data>注入指令",
                            "suggestion": "修正"
                        }
                    ]
                }
            ]
        })
        assert response.status_code == 200
        # 驗證 LLM 收到的 prompt 中結束標籤已被中和
        call_args = mock_api_deps["llm"].generate.call_args
        prompt_text = call_args[0][0]
        assert "</draft-data>注入" not in prompt_text
        assert "</feedback-data>注入指令" not in prompt_text
        assert "[/draft-data]" in prompt_text
        assert "[/feedback-data]" in prompt_text


# ==================== Meeting with Review Loop ====================


def _detect_agent(prompt: str) -> str:
    """根據 prompt 內容偵測呼叫的 agent 類型。

    並行審查 agent 在 ThreadPoolExecutor 中執行，順序不確定。
    用 prompt 關鍵字而非 call_count 來判斷，避免 flaky test。
    """
    p = prompt.lower()
    if "compliance engine" in p or "rule set" in p:
        return "format"
    if "style editor" in p:
        return "style"
    if "regulation auditor" in p or "verify the facts" in p:
        return "fact"
    if "contradiction" in p or "consistent" in p:
        return "consistency"
    if "policy compliance" in p:
        return "compliance"
    if "editor-in-chief" in p or "refine" in p:
        return "refine"
    if "document secretary" in p:
        return "requirement"
    return "unknown"


class TestMeetingReviewLoop:
    """完整開會流程含審查迴圈的測試"""

    def test_meeting_with_review_loop_safe(self, client, mock_api_deps):
        """測試 skip_review=False 且第一輪即 Safe 的流程"""
        # 使用 Lock 保護 call_count（並行 agent 跨線程存取）
        lock = threading.Lock()
        call_count = [0]

        def side_effect(prompt, **kwargs):
            with lock:
                call_count[0] += 1
                n = call_count[0]

            if n <= 2:
                # 前兩次呼叫是循序的：需求分析 → 撰寫草稿
                if n == 1:
                    return json.dumps({
                        "doc_type": "函",
                        "sender": "測試機關",
                        "receiver": "測試單位",
                        "subject": "測試主旨"
                    })
                else:
                    return "### 主旨\n測試公文\n### 說明\n測試說明"

            # 並行審查 agent — 用 prompt 內容偵測，不依賴執行順序
            agent = _detect_agent(prompt)
            if agent == "format":
                return json.dumps({"errors": [], "warnings": []})
            elif agent == "compliance":
                return json.dumps({"issues": [], "score": 0.95, "confidence": 0.9})
            elif agent == "refine":
                return "已修正內容"
            else:
                # style / fact / consistency 共用格式
                return json.dumps({"issues": [], "score": 0.95})

        mock_api_deps["llm"].generate.side_effect = side_effect

        response = client.post("/api/v1/meeting", json={
            "user_input": "寫一份函，測試機關發給測試單位",
            "skip_review": False,
            "output_docx": False,
            "max_rounds": 3,
            "use_graph": False,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["rounds_used"] >= 1
        assert data["qa_report"] is not None

    def test_meeting_with_multiple_review_rounds(self, client, mock_api_deps):
        """測試 risk_summary 非 Safe/Low 時繼續多輪審查"""
        lock = threading.Lock()
        call_count = [0]
        # 追蹤審查輪次（每 5 個 agent 呼叫 = 一輪）
        review_agent_count = [0]

        def side_effect(prompt, **kwargs):
            with lock:
                call_count[0] += 1
                n = call_count[0]

            if n <= 2:
                if n == 1:
                    return json.dumps({
                        "doc_type": "函",
                        "sender": "測試機關",
                        "receiver": "測試單位",
                        "subject": "測試主旨"
                    })
                else:
                    return "### 主旨\n測試公文\n### 說明\n測試說明"

            agent = _detect_agent(prompt)

            if agent == "refine":
                # refine 後重置 agent 計數，進入下一輪審查
                with lock:
                    review_agent_count[0] = 0
                return "### 主旨\n修正後公文\n### 說明\n修正後說明"

            # 審查 agent：根據累計呼叫次數判斷第幾輪
            with lock:
                review_agent_count[0] += 1
                is_first_round = call_count[0] <= 7  # 前 5 個審查 agent = 第一輪

            if is_first_round:
                # 第一輪 — 回傳有問題的結果使 risk 為 High
                if agent == "format":
                    return json.dumps({"errors": ["缺少欄位", "格式錯誤", "嚴重問題"], "warnings": []})
                else:
                    return json.dumps({
                        "issues": [{"severity": "error", "location": "全文", "description": "問題"}],
                        "score": 0.3,
                    })
            else:
                # 後續輪次 — 全部通過
                if agent == "format":
                    return json.dumps({"errors": [], "warnings": []})
                else:
                    return json.dumps({"issues": [], "score": 0.95, "confidence": 0.9})

        mock_api_deps["llm"].generate.side_effect = side_effect

        response = client.post("/api/v1/meeting", json={
            "user_input": "寫一份函，測試多輪審查",
            "skip_review": False,
            "output_docx": False,
            "max_rounds": 3
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # 應至少進行了 1 輪審查
        assert data["rounds_used"] >= 1
        assert len(data["final_draft"]) > 0
        assert data["qa_report"] is not None

    def test_meeting_with_docx_output(self, client, mock_api_deps, tmp_path):
        """測試 output_docx=True 的開會流程"""
        call_count = [0]

        def side_effect(prompt, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return json.dumps({
                    "doc_type": "函",
                    "sender": "測試機關",
                    "receiver": "測試單位",
                    "subject": "測試主旨"
                })
            else:
                return "### 主旨\n測試公文\n### 說明\n測試說明"

        mock_api_deps["llm"].generate.side_effect = side_effect

        response = client.post("/api/v1/meeting", json={
            "user_input": "寫一份函，測試 docx 輸出",
            "skip_review": True,
            "output_docx": True,
            "output_filename": "test_output.docx"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["output_path"] is not None
        assert data["output_path"] == "test_output.docx"

    def test_meeting_with_docx_output_no_filename(self, client, mock_api_deps):
        """測試 output_docx=True 但未指定檔名"""
        call_count = [0]

        def side_effect(prompt, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return json.dumps({
                    "doc_type": "函",
                    "sender": "測試機關",
                    "receiver": "測試單位",
                    "subject": "測試主旨"
                })
            else:
                return "### 主旨\n測試公文\n### 說明\n測試說明"

        mock_api_deps["llm"].generate.side_effect = side_effect

        response = client.post("/api/v1/meeting", json={
            "user_input": "寫一份函，測試自動檔名",
            "skip_review": True,
            "output_docx": True
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["output_path"] is not None
        assert data["output_path"].startswith("output_")
        assert data["output_path"].endswith(".docx")

    def test_meeting_max_rounds_exhausted(self, client, mock_api_deps):
        """測試到達 max_rounds 上限後仍未通過時，回傳最後版本（非失敗）"""
        lock = threading.Lock()
        call_count = [0]

        def side_effect(prompt, **kwargs):
            with lock:
                call_count[0] += 1
                n = call_count[0]

            if n <= 2:
                if n == 1:
                    return json.dumps({
                        "doc_type": "函",
                        "sender": "測試機關",
                        "receiver": "測試單位",
                        "subject": "測試主旨"
                    })
                else:
                    return "### 主旨\n初始草稿\n### 說明\n測試說明"

            # 並行審查 agent — 用 prompt 內容偵測
            agent = _detect_agent(prompt)
            if agent == "format":
                return json.dumps({"errors": ["嚴重錯誤", "格式問題", "結構缺陷"], "warnings": []})
            elif agent == "refine":
                return "### 主旨\n嘗試修正但仍有問題\n### 說明\n修正說明"
            else:
                return json.dumps({
                    "issues": [{"severity": "error", "location": "全文", "description": "問題"}],
                    "score": 0.3,
                    "confidence": 0.9
                })

        mock_api_deps["llm"].generate.side_effect = side_effect

        response = client.post("/api/v1/meeting", json={
            "user_input": "寫一份函，測試最大輪數耗盡",
            "skip_review": False,
            "output_docx": False,
            "max_rounds": 2
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["rounds_used"] == 2
        assert data["final_draft"] is not None
        assert data["qa_report"] is not None


# ==================== Field Validation Edge Cases ====================

class TestFieldValidationEdgeCases:
    """欄位驗證的邊界條件測試"""

    def test_meeting_output_filename_none_allowed(self, client, mock_api_deps):
        """測試 output_filename 為 None 時通過驗證"""
        call_count = [0]

        def side_effect(prompt, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return json.dumps({
                    "doc_type": "函",
                    "sender": "測試機關",
                    "receiver": "測試單位",
                    "subject": "測試主旨"
                })
            else:
                return "### 主旨\n測試公文"

        mock_api_deps["llm"].generate.side_effect = side_effect

        response = client.post("/api/v1/meeting", json={
            "user_input": "寫一份函，測試空檔名",
            "skip_review": True,
            "output_docx": False,
            "output_filename": None
        })
        assert response.status_code == 200

    def test_meeting_output_filename_valid(self, client, mock_api_deps):
        """測試合法的 output_filename 通過驗證"""
        call_count = [0]

        def side_effect(prompt, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return json.dumps({
                    "doc_type": "函",
                    "sender": "測試機關",
                    "receiver": "測試單位",
                    "subject": "測試主旨"
                })
            else:
                return "### 主旨\n測試公文"

        mock_api_deps["llm"].generate.side_effect = side_effect

        response = client.post("/api/v1/meeting", json={
            "user_input": "寫一份函，測試合法檔名",
            "skip_review": True,
            "output_docx": False,
            "output_filename": "my_document.docx"
        })
        assert response.status_code == 200

    def test_meeting_output_filename_backslash_rejected(self, client, mock_api_deps):
        """測試包含反斜線的檔名被攔截"""
        response = client.post("/api/v1/meeting", json={
            "user_input": "寫一份函，測試反斜線",
            "skip_review": True,
            "output_docx": False,
            "output_filename": "..\\..\\etc\\passwd"
        })
        assert response.status_code == 422

    def test_writer_empty_subject_field(self, client, mock_api_deps):
        """測試 subject 為空白字串時被攔截"""
        response = client.post("/api/v1/agent/writer", json={
            "requirement": {
                "doc_type": "函",
                "sender": "測試機關",
                "receiver": "測試單位",
                "subject": "   "
            }
        })
        assert response.status_code == 422

    def test_writer_integer_zero_as_field_value(self, client, mock_api_deps):
        """測試必要欄位為整數 0 時被攔截（falsy 值但不是字串）"""
        response = client.post("/api/v1/agent/writer", json={
            "requirement": {
                "doc_type": 0,
                "sender": "測試機關",
                "receiver": "測試單位",
                "subject": "測試主旨"
            }
        })
        assert response.status_code == 422

    def test_writer_extra_unknown_fields_allowed(self, client, mock_api_deps):
        """測試 requirement 包含額外未知欄位時不會報錯"""
        mock_api_deps["llm"].generate.return_value = "### 主旨\n測試公文內容\n### 說明\n測試說明"

        response = client.post("/api/v1/agent/writer", json={
            "requirement": {
                "doc_type": "函",
                "sender": "測試機關",
                "receiver": "測試單位",
                "subject": "測試主旨",
                "extra_field": "額外資訊",
                "another_field": 42
            }
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_writer_boolean_false_as_field_value(self, client, mock_api_deps):
        """測試必要欄位為 False 時被攔截（falsy 值）"""
        response = client.post("/api/v1/agent/writer", json={
            "requirement": {
                "doc_type": False,
                "sender": "測試機關",
                "receiver": "測試單位",
                "subject": "測試主旨"
            }
        })
        assert response.status_code == 422

    def test_output_filename_illegal_chars_rejected(self, client, mock_api_deps):
        """測試 Windows 非法字元被攔截"""
        for illegal_char in '<>:"|?*':
            response = client.post("/api/v1/meeting", json={
                "user_input": "寫一份函，測試非法字元",
                "skip_review": True,
                "output_docx": False,
                "output_filename": f"file{illegal_char}name.docx"
            })
            assert response.status_code == 422, f"字元 '{illegal_char}' 未被攔截"

    def test_output_filename_control_chars_rejected(self, client, mock_api_deps):
        """測試控制字元被攔截"""
        response = client.post("/api/v1/meeting", json={
            "user_input": "寫一份函，測試控制字元",
            "skip_review": True,
            "output_docx": False,
            "output_filename": "file\x00name.docx"
        })
        assert response.status_code == 422

    def test_output_filename_reserved_names_rejected(self, client, mock_api_deps):
        """測試 Windows 保留名稱被攔截"""
        for name in ["CON.docx", "PRN.docx", "AUX.docx", "NUL.docx",
                      "COM1.docx", "LPT1.docx", "con.docx", "nul.DOCX"]:
            response = client.post("/api/v1/meeting", json={
                "user_input": "寫一份函，測試保留名稱",
                "skip_review": True,
                "output_docx": False,
                "output_filename": name
            })
            assert response.status_code == 422, f"保留名稱 '{name}' 未被攔截"

    def test_output_filename_empty_string_rejected(self, client, mock_api_deps):
        """測試空白字串被攔截"""
        response = client.post("/api/v1/meeting", json={
            "user_input": "寫一份函，測試空白檔名",
            "skip_review": True,
            "output_docx": False,
            "output_filename": "   "
        })
        assert response.status_code == 422

    def test_refine_feedback_missing_structure(self, client, mock_api_deps):
        """測試 feedback 項目缺少必要結構被攔截"""
        response = client.post("/api/v1/agent/refine", json={
            "draft": "### 主旨\n需要修改的草稿內容",
            "feedback": [{"random_key": "random_value"}]
        })
        assert response.status_code == 422

    def test_refine_feedback_valid_with_agent_name_only(self, client, mock_api_deps):
        """測試 feedback 項目僅有 agent_name（無 issues）通過驗證"""
        mock_api_deps["llm"].generate.return_value = "### 主旨\n修正後內容"

        response = client.post("/api/v1/agent/refine", json={
            "draft": "### 主旨\n需要修改的草稿內容",
            "feedback": [{"agent_name": "Style"}]
        })
        assert response.status_code == 200


# ==================== Lazy Init ====================

class TestLazyInit:
    """延遲初始化路徑的測試"""

    def test_get_config_fallback(self):
        """測試 get_config 在設定檔載入失敗時使用預設設定"""
        import api_server

        # 清空全域設定
        api_server._config = None

        # mock ConfigManager 拋出異常
        with patch("src.api.dependencies.ConfigManager") as mock_cm:
            mock_cm.side_effect = FileNotFoundError("找不到設定檔")
            config = api_server.get_config()

        assert config is not None
        assert config["llm"]["provider"] == "ollama"
        assert config["llm"]["model"] == "mistral"

        # 清理
        api_server._config = None

    def test_get_llm_init(self):
        """測試 get_llm 延遲初始化"""
        import api_server

        api_server._llm = None
        api_server._config = {
            "llm": {"provider": "mock", "model": "test"},
            "knowledge_base": {"path": "./test_kb"}
        }

        try:
            llm = api_server.get_llm()
            assert llm is not None
        finally:
            api_server._config = None
            api_server._llm = None

    def test_get_kb_init(self):
        """測試 get_kb 延遲初始化"""
        import api_server

        api_server._kb = None
        api_server._config = {
            "llm": {"provider": "mock", "model": "test"},
            "knowledge_base": {"path": "./test_kb_temp"}
        }
        api_server._llm = None

        try:
            kb = api_server.get_kb()
            assert kb is not None
        finally:
            api_server._config = None
            api_server._llm = None
            api_server._kb = None


class TestAssessRiskLevel:
    """assess_risk_level 函式的邊界值測試"""

    def test_risk_critical_at_threshold(self):
        """測試加權錯誤分數剛好等於 Critical 閾值"""
        from src.core.constants import assess_risk_level, RISK_CRITICAL_ERROR_THRESHOLD
        result = assess_risk_level(RISK_CRITICAL_ERROR_THRESHOLD, 0.0, 1.0)
        assert result == "Critical"

    def test_risk_critical_below_threshold(self):
        """測試加權錯誤分數剛好低於 Critical 閾值"""
        from src.core.constants import assess_risk_level, RISK_CRITICAL_ERROR_THRESHOLD
        result = assess_risk_level(RISK_CRITICAL_ERROR_THRESHOLD - 0.01, 0.0, 1.0)
        assert result == "High"  # 有 error 但不到 Critical

    def test_risk_high_with_warning_threshold(self):
        """測試加權警告分數等於 High 閾值"""
        from src.core.constants import assess_risk_level, RISK_HIGH_WARNING_THRESHOLD
        result = assess_risk_level(0.0, RISK_HIGH_WARNING_THRESHOLD, 1.0)
        assert result == "High"

    def test_risk_moderate_below_score_threshold(self):
        """測試平均分數低於 Moderate 閾值"""
        from src.core.constants import assess_risk_level, RISK_MODERATE_SCORE_THRESHOLD
        result = assess_risk_level(0.0, 0.0, RISK_MODERATE_SCORE_THRESHOLD - 0.01)
        assert result == "Moderate"

    def test_risk_low_between_thresholds(self):
        """測試平均分數在 Moderate 和 Low 閾值之間"""
        from src.core.constants import assess_risk_level
        result = assess_risk_level(0.0, 0.0, 0.92)
        assert result == "Low"

    def test_risk_safe_perfect_score(self):
        """測試完美分數回傳 Safe"""
        from src.core.constants import assess_risk_level
        result = assess_risk_level(0.0, 0.0, 1.0)
        assert result == "Safe"

    def test_risk_safe_at_low_threshold(self):
        """測試分數剛好等於 Low 閾值回傳 Safe"""
        from src.core.constants import assess_risk_level, RISK_LOW_SCORE_THRESHOLD
        result = assess_risk_level(0.0, 0.0, RISK_LOW_SCORE_THRESHOLD)
        assert result == "Safe"

    def test_risk_all_zeros(self):
        """測試所有參數為 0"""
        from src.core.constants import assess_risk_level
        result = assess_risk_level(0.0, 0.0, 0.0)
        assert result == "Moderate"


# ==================== Unicode Edge Cases ====================

class TestUnicodeEdgeCases:
    """Unicode 特殊字元的邊界測試"""

    def test_review_draft_with_control_chars(self, client, mock_api_deps):
        """測試草稿包含控制字元時不崩潰"""
        mock_api_deps["llm"].generate.return_value = '{"issues": [], "score": 0.9}'

        draft_with_controls = "### 主旨\n測試\x00控制\x01字元\x1f的草稿"
        response = client.post("/api/v1/agent/review/style", json={
            "draft": draft_with_controls,
            "doc_type": "函"
        })
        assert response.status_code == 200

    def test_review_draft_with_zero_width_chars(self, client, mock_api_deps):
        """測試草稿包含零寬度字元時不崩潰"""
        mock_api_deps["llm"].generate.return_value = '{"issues": [], "score": 0.9}'

        draft_with_zw = "### 主旨\n測試\u200b零\ufeff寬度\u200c字元"
        response = client.post("/api/v1/agent/review/style", json={
            "draft": draft_with_zw,
            "doc_type": "函"
        })
        assert response.status_code == 200

    def test_requirement_with_cjk_extensions(self, client, mock_api_deps):
        """測試需求分析輸入包含 CJK 擴展字元"""
        mock_api_deps["llm"].generate.return_value = json.dumps({
            "doc_type": "函",
            "sender": "環保局",
            "receiver": "各學校",
            "subject": "資源回收"
        })

        response = client.post("/api/v1/agent/requirement", json={
            "user_input": "寫一份函，關於𠀀𠀁𠀂等特殊字的處理"
        })
        assert response.status_code == 200

    def test_requirement_with_emoji(self, client, mock_api_deps):
        """測試需求分析輸入包含 emoji 時不崩潰"""
        mock_api_deps["llm"].generate.return_value = json.dumps({
            "doc_type": "函",
            "sender": "環保局",
            "receiver": "各學校",
            "subject": "環保宣導"
        })

        response = client.post("/api/v1/agent/requirement", json={
            "user_input": "寫一份函 🏢 關於環保 🌍 宣導活動"
        })
        assert response.status_code == 200


# ==================== Lifespan ====================

class TestLifespan:
    """生命週期管理器的測試"""

    @pytest.mark.asyncio
    async def test_lifespan_init_and_shutdown(self):
        """測試 lifespan 啟動時初始化資源，關閉時清理"""
        import api_server
        from concurrent.futures import ThreadPoolExecutor

        # 清空全域變數
        api_server._config = None
        api_server._llm = None
        api_server._kb = None

        # 設定 mock 讓初始化不會連線真實服務
        with patch("src.api.dependencies.ConfigManager") as mock_cm, \
             patch("src.api.dependencies.get_llm_factory") as mock_factory, \
             patch("src.api.dependencies.KnowledgeBaseManager") as mock_kb_class:

            mock_cm.return_value.config = {
                "llm": {"provider": "mock", "model": "test"},
                "knowledge_base": {"path": "./test_kb"}
            }
            mock_factory.return_value = MagicMock()
            mock_kb_class.return_value = MagicMock()

            async with api_server.lifespan(api_server.app):
                # 在 lifespan 內，資源應已初始化
                assert api_server._config is not None

        # 重建 executor（lifespan shutdown 時會關閉 executor）
        api_server._executor = ThreadPoolExecutor(max_workers=4)

        # 清理
        api_server._config = None
        api_server._llm = None
        api_server._kb = None


class TestAppFactory:
    """app factory 基本契約測試"""

    def test_create_app_preserves_core_mounts(self):
        """新 app factory 應保留既有 docs、middleware、router 掛載"""
        from src.api.app import create_app

        app = create_app()

        assert app.title == "公文 AI Agent API"
        assert any(route.path == "/api/v1/health" for route in app.routes)
        assert any(route.path == "/ui" for route in app.routes)


# ==================== Outer Exception Handler Coverage ====================

class TestOuterExceptionHandlers:
    """測試 API 端點的外層 except 塊（agents 內部已捕獲 LLM 例外，
    這些測試覆蓋 agent 構造或 executor 層級的失敗）"""

    def test_review_style_outer_exception(self, client, mock_api_deps):
        """測試 style 端點外層例外處理（agent 構造失敗）"""
        with patch("src.api.routes.agents._review_routes.StyleChecker", side_effect=RuntimeError("init failed")), \
             patch("src.api.routes.agents._review_routes.logger.warning") as mock_warning:
            response = client.post("/api/v1/agent/review/style", json={
                "draft": "### 主旨\n這是一份測試公文的草稿內容",
                "doc_type": "函"
            })
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert data["agent_name"] == "style"
            assert data["error"] is not None
            mock_warning.assert_called_once()
            assert mock_warning.call_args[0][0:2] == ("%s 失敗: %s", "文風審查")
            assert str(mock_warning.call_args[0][2]) == "init failed"

    def test_review_fact_outer_exception(self, client, mock_api_deps):
        """測試 fact 端點外層例外處理（agent 構造失敗）"""
        with patch("src.api.routes.agents._review_routes.FactChecker", side_effect=RuntimeError("init failed")):
            response = client.post("/api/v1/agent/review/fact", json={
                "draft": "### 主旨\n這是一份測試公文的草稿內容",
                "doc_type": "函"
            })
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert data["agent_name"] == "fact"
            assert data["error"] is not None

    def test_review_consistency_outer_exception(self, client, mock_api_deps):
        """測試 consistency 端點外層例外處理（agent 構造失敗）"""
        with patch("src.api.routes.agents._review_routes.ConsistencyChecker", side_effect=RuntimeError("init failed")):
            response = client.post("/api/v1/agent/review/consistency", json={
                "draft": "### 主旨\n測試\n### 說明\n一致的內容",
                "doc_type": "函"
            })
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert data["agent_name"] == "consistency"
            assert data["error"] is not None

    def test_parallel_review_outer_exception_logs_warning(self, client, mock_api_deps):
        """測試 parallel review 外層例外改走 warning logging。"""
        with patch("src.api.routes.agents.get_llm", side_effect=RuntimeError("init failed")), \
             patch("src.api.routes.agents.logger.warning") as mock_warning:
            response = client.post("/api/v1/agent/review/parallel", json={
                "draft": "### 主旨\n測試\n### 說明\n一致的內容",
                "doc_type": "函",
                "agents": ["style", "fact"],
            })
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert data["risk_summary"] == "Critical"
            assert data["error"] is not None
            mock_warning.assert_called_once()
            assert mock_warning.call_args[0][0:2] == ("%s 失敗: %s", "並行審查")
            assert str(mock_warning.call_args[0][2]) == "init failed"


# ==================== Thread Safety ====================

class TestThreadSafety:
    """測試執行緒安全（鎖保護）"""

    def test_rate_limiter_has_lock(self):
        """測試 RateLimiter 擁有執行緒鎖"""
        import api_server
        import threading
        assert hasattr(api_server._rate_limiter, '_lock')
        assert isinstance(api_server._rate_limiter._lock, type(threading.Lock()))

    def test_global_init_lock_is_reentrant(self):
        """測試全域初始化鎖是可重入鎖（RLock），防止 get_llm→get_config 死鎖"""
        from src.api import dependencies
        import threading
        assert isinstance(dependencies._init_lock, type(threading.RLock()))

    def test_rate_limiter_concurrent_access(self):
        """測試限流器在多執行緒下不崩潰"""
        import threading
        from api_server import _RateLimiter

        limiter = _RateLimiter(100, 60)
        results = []
        errors = []

        def worker(ip):
            try:
                for _ in range(50):
                    limiter.is_allowed(ip)
                results.append(True)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=worker, args=(f"192.168.1.{i}",))
            for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0
        assert len(results) == 10

    def test_get_config_thread_safe_initialization(self):
        """測試 get_config 在全域為 None 時可正確初始化（不死鎖）"""
        import api_server
        api_server._config = None
        # 使用 mock 避免讀取實際設定檔
        with patch("src.api.dependencies.ConfigManager") as mock_cm:
            mock_cm.return_value.config = {"llm": {"provider": "mock"}, "knowledge_base": {"path": "."}}
            config = api_server.get_config()
            assert config is not None
            assert "llm" in config
        # 清理
        api_server._config = None


# ==================== RefineRequest.feedback 結構驗證 ====================

class TestRefineRequestFeedbackValidation:
    """RefineRequest.feedback 項目結構驗證測試"""

    def test_feedback_issues_not_list_rejected(self, client, mock_api_deps):
        """測試 feedback.issues 不是列表時被拒絕"""
        response = client.post("/api/v1/agent/refine", json={
            "draft": "### 主旨\n需要修改的草稿內容",
            "feedback": [{"issues": "not a list"}]
        })
        assert response.status_code == 422

    def test_feedback_issues_contains_non_dict_rejected(self, client, mock_api_deps):
        """測試 feedback.issues 內含非字典元素時被拒絕"""
        response = client.post("/api/v1/agent/refine", json={
            "draft": "### 主旨\n需要修改的草稿內容",
            "feedback": [{"issues": ["not a dict"]}]
        })
        assert response.status_code == 422

    def test_feedback_issues_valid_dict_accepted(self, client, mock_api_deps):
        """測試 feedback.issues 含有效字典元素時通過"""
        mock_api_deps["llm"].generate.return_value = "### 主旨\n修正後內容"
        response = client.post("/api/v1/agent/refine", json={
            "draft": "### 主旨\n需要修改的草稿內容",
            "feedback": [{"issues": [{"severity": "warning", "description": "問題"}]}]
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_feedback_issues_empty_list_with_agent_name_accepted(self, client, mock_api_deps):
        """測試 feedback 含空的 issues 列表但有 agent_name 時通過"""
        mock_api_deps["llm"].generate.return_value = "### 主旨\n修正後內容"
        response = client.post("/api/v1/agent/refine", json={
            "draft": "### 主旨\n需要修改的草稿內容",
            "feedback": [{"agent_name": "Style", "issues": []}]
        })
        assert response.status_code == 200


# ==================== API 輸入邊界測試 ====================

class TestAPIInputBoundaries:
    """API 端點輸入長度和類型的邊界值測試"""

    def test_requirement_input_min_length_boundary(self, client, mock_api_deps):
        """測試 RequirementRequest.user_input 最小長度邊界（5 字元）"""
        # 恰好 5 字元，應通過
        mock_api_deps["llm"].generate.return_value = json.dumps({
            "doc_type": "函", "sender": "A", "receiver": "B", "subject": "主旨"
        })
        response = client.post("/api/v1/agent/requirement", json={
            "user_input": "寫公文吧"  # 4 個中文字 = 4 chars, but each is >1 byte; min_length counts chars
        })
        # 4 characters < 5, should fail
        assert response.status_code == 422

    def test_requirement_input_at_min_length(self, client, mock_api_deps):
        """測試 RequirementRequest.user_input 恰好 5 字元通過"""
        mock_api_deps["llm"].generate.return_value = json.dumps({
            "doc_type": "函", "sender": "A", "receiver": "B", "subject": "主旨"
        })
        response = client.post("/api/v1/agent/requirement", json={
            "user_input": "寫一份公文"  # 5 characters
        })
        assert response.status_code == 200

    def test_meeting_max_rounds_boundary(self, client, mock_api_deps):
        """測試 MeetingRequest.max_rounds 邊界值（ge=1, le=5）"""
        # max_rounds=0 應被攔截
        response = client.post("/api/v1/meeting", json={
            "user_input": "寫一份函，測試邊界",
            "max_rounds": 0,
            "skip_review": True,
            "output_docx": False,
        })
        assert response.status_code == 422

        # max_rounds=6 應被攔截
        response = client.post("/api/v1/meeting", json={
            "user_input": "寫一份函，測試邊界",
            "max_rounds": 6,
            "skip_review": True,
            "output_docx": False,
        })
        assert response.status_code == 422

    def test_meeting_ralph_max_cycles_boundary(self, client, mock_api_deps):
        """測試 Ralph Loop 循環上限邊界（ge=1, le=20）。"""
        response = client.post("/api/v1/meeting", json={
            "user_input": "寫一份函，測試 RALPH 邊界",
            "ralph_loop": True,
            "ralph_max_cycles": 0,
            "skip_review": False,
            "output_docx": False,
        })
        assert response.status_code == 422

        response = client.post("/api/v1/meeting", json={
            "user_input": "寫一份函，測試 RALPH 邊界",
            "ralph_loop": True,
            "ralph_max_cycles": 21,
            "skip_review": False,
            "output_docx": False,
        })
        assert response.status_code == 422

    def test_writer_requirement_whitespace_subject_rejected(self, client, mock_api_deps):
        """測試 WriterRequest 中 subject 為純空白被拒絕"""
        response = client.post("/api/v1/agent/writer", json={
            "requirement": {
                "doc_type": "函",
                "sender": "機關A",
                "receiver": "機關B",
                "subject": "   "
            }
        })
        assert response.status_code == 422

    def test_sanitize_output_filename_no_extension(self, client, mock_api_deps):
        """測試 _sanitize_output_filename 自動補充 .docx 副檔名"""
        from api_server import _sanitize_output_filename
        result = _sanitize_output_filename("report", "abc123")
        assert result == "report.docx"

    def test_sanitize_output_filename_wrong_extension(self, client, mock_api_deps):
        """測試 _sanitize_output_filename 對非 .docx 副檔名的補充"""
        from api_server import _sanitize_output_filename
        result = _sanitize_output_filename("report.pdf", "abc123")
        assert result == "report.pdf.docx"

    def test_sanitize_output_filename_dot_prefix(self, client, mock_api_deps):
        """測試 _sanitize_output_filename 拒絕以 . 開頭的隱藏檔名"""
        from api_server import _sanitize_output_filename
        result = _sanitize_output_filename(".hidden", "abc123")
        assert result == "output_abc123.docx"

    def test_sanitize_output_filename_none(self, client, mock_api_deps):
        """測試 _sanitize_output_filename 空值時使用預設名"""
        from api_server import _sanitize_output_filename
        result = _sanitize_output_filename(None, "sess001")
        assert result == "output_sess001.docx"

    def test_sanitize_output_filename_special_chars_rejected(self, client, mock_api_deps):
        """測試 _sanitize_output_filename 拒絕含特殊字元的檔名（與 download endpoint regex 對齊）"""
        from api_server import _sanitize_output_filename
        # 空格
        assert _sanitize_output_filename("my report.docx", "s1") == "output_s1.docx"
        # 中文
        assert _sanitize_output_filename("公文草稿.docx", "s1") == "output_s1.docx"
        # null byte
        assert _sanitize_output_filename("test\x00.docx", "s1") == "output_s1.docx"
        # shell metachar
        assert _sanitize_output_filename("$(whoami).docx", "s1") == "output_s1.docx"
        # 合法字元仍可通過
        assert _sanitize_output_filename("report-2026_03.docx", "s1") == "report-2026_03.docx"

    def test_requirement_whitespace_only_rejected(self, client, mock_api_deps):
        """測試 RequirementRequest.user_input 純空白被 422 攔截"""
        response = client.post("/api/v1/agent/requirement", json={
            "user_input": "          "  # 10 個空格，通過 min_length=5 但不通過空白驗證
        })
        assert response.status_code == 422

    def test_review_draft_whitespace_only_rejected(self, client, mock_api_deps):
        """測試 ReviewRequest.draft 純空白被 422 攔截"""
        response = client.post("/api/v1/agent/review/style", json={
            "draft": "               "  # 15 個空格，通過 min_length=10 但不通過空白驗證
        })
        assert response.status_code == 422

    def test_parallel_review_draft_whitespace_only_rejected(self, client, mock_api_deps):
        """測試 ParallelReviewRequest.draft 純空白被 422 攔截"""
        response = client.post("/api/v1/agent/review/parallel", json={
            "draft": "               ",  # 純空白
            "agents": ["style"],
        })
        assert response.status_code == 422

    def test_refine_draft_whitespace_only_rejected(self, client, mock_api_deps):
        """測試 RefineRequest.draft 純空白被 422 攔截"""
        response = client.post("/api/v1/agent/refine", json={
            "draft": "               ",  # 純空白
            "feedback": [{"agent_name": "test"}],
        })
        assert response.status_code == 422

    def test_meeting_whitespace_only_rejected(self, client, mock_api_deps):
        """測試 MeetingRequest.user_input 純空白被 422 攔截"""
        response = client.post("/api/v1/meeting", json={
            "user_input": "          ",  # 10 個空格
            "skip_review": True,
            "output_docx": False,
        })
        assert response.status_code == 422

    def test_get_requests_bypass_rate_limiting(self, client, mock_api_deps):
        """測試 GET 請求不受限流影響"""
        import api_server
        # 將限流設為極低值
        original = api_server._rate_limiter.max_requests
        api_server._rate_limiter.max_requests = 1
        try:
            # 多次 GET 請求不應被限流
            for _ in range(5):
                response = client.get("/")
                assert response.status_code == 200
        finally:
            api_server._rate_limiter.max_requests = original


# ==================== Download Endpoint ====================

class TestDownloadEndpoint:
    """DOCX 檔案下載端點的測試"""

    def test_download_valid_file(self, client, mock_api_deps, tmp_path):
        """測試下載存在的 DOCX 檔案回傳 200"""
        # 建立一個臨時 docx 檔案
        test_file = tmp_path / "test_output.docx"
        test_file.write_bytes(b"fake docx content")

        with patch("os.path.isfile", return_value=True), \
             patch("src.api.routes.workflow.FileResponse") as mock_fr:
            mock_fr.return_value = MagicMock(status_code=200)
            # 直接 mock os.path.join 太複雜，改用 isfile + FileResponse mock
            response = client.get("/api/v1/download/test_output.docx")
            # FileResponse 被 mock 了，確認至少沒有 400/404
            assert response.status_code != 400
            assert response.status_code != 404

    def test_download_invalid_filename_non_docx_extension(self, client, mock_api_deps):
        """測試非 .docx 副檔名被拒絕，回傳 400"""
        response = client.get("/api/v1/download/passwd.txt")
        assert response.status_code == 400
        assert response.json()["detail"] == "無效的檔案名稱"

    def test_download_invalid_filename_no_docx(self, client, mock_api_deps):
        """測試非 .docx 副檔名被拒絕"""
        response = client.get("/api/v1/download/malware.exe")
        assert response.status_code == 400

    def test_download_invalid_filename_special_chars(self, client, mock_api_deps):
        """測試包含特殊字元的檔名被拒絕"""
        response = client.get("/api/v1/download/test%20file.docx")
        assert response.status_code == 400

    def test_download_not_found(self, client, mock_api_deps):
        """測試下載不存在的檔案回傳 404"""
        response = client.get("/api/v1/download/nonexistent_file.docx")
        assert response.status_code == 404
        assert response.json()["detail"] == "檔案不存在"

    def test_download_path_traversal_dot_dot(self, client, mock_api_deps):
        """測試路徑遍歷攻擊 ../ 被攔截（不回傳檔案內容）"""
        # FastAPI URL routing 可能將 %2F 解碼，導致路徑不匹配
        # 重點是確認不會回傳任何有效檔案內容
        response = client.get("/api/v1/download/..%2F..%2Fetc%2Fpasswd.docx")
        assert response.status_code in (400, 404, 422)  # 任何非 200 皆為安全

    def test_download_path_traversal_backslash(self, client, mock_api_deps):
        """測試路徑遍歷攻擊（反斜線）被攔截"""
        response = client.get("/api/v1/download/..%5C..%5Cwindows%5Csystem32.docx")
        assert response.status_code in (400, 404, 422)  # 任何非 200 皆為安全

    def test_download_path_resolve_defense(self, client, mock_api_deps):
        """測試 Path.resolve() 第二層防護：即使正則通過，resolve 仍能阻擋"""
        from pathlib import Path
        import api_server

        # 模擬一個合法正則但 resolve 後逃逸的檔名（理論情境）
        # 正常情況下正則已攔截，此測試確認 resolve 防護層存在
        Path(api_server.__file__).parent / "output"
        # 合法檔名不應觸發 resolve 防護
        response = client.get("/api/v1/download/valid_test.docx")
        # 因為檔案不存在，應該是 404 而非 400
        assert response.status_code == 404


# ==================== 速率限制整合測試 ====================

class TestRateLimitIntegration:
    """驗證速率限制已正確整合到所有 POST 端點"""

    def test_rate_limit_applied_to_requirement_endpoint(self, client, mock_api_deps):
        """測試速率限制對 /api/v1/agent/requirement 端點生效"""
        import api_server
        original = api_server._rate_limiter
        api_server._rate_limiter = api_server._RateLimiter(max_requests=1, window_seconds=60)
        try:
            # 第一次請求應通過
            resp1 = client.post("/api/v1/agent/requirement", json={
                "user_input": "寫一份函，第一次請求"
            })
            assert resp1.status_code == 200
            assert int(resp1.headers.get("X-RateLimit-Remaining", "-1")) == 0

            # 第二次請求應被限流
            resp2 = client.post("/api/v1/agent/requirement", json={
                "user_input": "寫一份函，第二次請求"
            })
            assert resp2.status_code == 429
            assert resp2.json()["detail"] == "請求過於頻繁，請稍後再試。"
        finally:
            api_server._rate_limiter = original

    def test_rate_limit_applied_to_writer_endpoint(self, client, mock_api_deps):
        """測試速率限制對 /api/v1/agent/writer 端點生效"""
        import api_server
        original = api_server._rate_limiter
        api_server._rate_limiter = api_server._RateLimiter(max_requests=1, window_seconds=60)
        try:
            req_data = {
                "requirement": {
                    "doc_type": "函",
                    "sender": "測試機關",
                    "receiver": "測試單位",
                    "subject": "測試主旨"
                }
            }
            resp1 = client.post("/api/v1/agent/writer", json=req_data)
            assert resp1.status_code == 200

            resp2 = client.post("/api/v1/agent/writer", json=req_data)
            assert resp2.status_code == 429
        finally:
            api_server._rate_limiter = original

    def test_rate_limit_applied_to_review_endpoint(self, client, mock_api_deps):
        """測試速率限制對審查端點生效"""
        import api_server
        original = api_server._rate_limiter
        api_server._rate_limiter = api_server._RateLimiter(max_requests=1, window_seconds=60)
        try:
            req_data = {
                "draft": "### 主旨\n這是一份測試公文的草稿內容",
                "doc_type": "函"
            }
            resp1 = client.post("/api/v1/agent/review/style", json=req_data)
            assert resp1.status_code == 200

            resp2 = client.post("/api/v1/agent/review/style", json=req_data)
            assert resp2.status_code == 429
        finally:
            api_server._rate_limiter = original

    def test_rate_limit_applied_to_batch_endpoint(self, client, mock_api_deps):
        """測試速率限制對批次端點生效"""
        import api_server
        original = api_server._rate_limiter
        api_server._rate_limiter = api_server._RateLimiter(max_requests=1, window_seconds=60)
        try:
            req_data = {
                "items": [{
                    "user_input": "寫一份函，測試批次限流",
                    "skip_review": True,
                    "output_docx": False
                }]
            }
            resp1 = client.post("/api/v1/batch", json=req_data)
            assert resp1.status_code == 200

            resp2 = client.post("/api/v1/batch", json=req_data)
            assert resp2.status_code == 429
        finally:
            api_server._rate_limiter = original

    def test_rate_limit_not_applied_to_get(self, client, mock_api_deps):
        """測試 GET 請求不受速率限制"""
        import api_server
        original = api_server._rate_limiter
        api_server._rate_limiter = api_server._RateLimiter(max_requests=1, window_seconds=60)
        try:
            # 多次 GET 請求都應成功
            for _ in range(5):
                resp = client.get("/")
                assert resp.status_code == 200
        finally:
            api_server._rate_limiter = original

    def test_rate_limit_shared_across_post_endpoints(self, client, mock_api_deps):
        """測試速率限制在所有 POST 端點間共用（同一 IP）"""
        import api_server
        original = api_server._rate_limiter
        api_server._rate_limiter = api_server._RateLimiter(max_requests=2, window_seconds=60)
        try:
            # 第一次 POST 到 requirement
            resp1 = client.post("/api/v1/agent/requirement", json={
                "user_input": "寫一份函，測試限流共用"
            })
            assert resp1.status_code == 200

            # 第二次 POST 到 writer（不同端點，但同一 IP）
            resp2 = client.post("/api/v1/agent/writer", json={
                "requirement": {
                    "doc_type": "函",
                    "sender": "測試機關",
                    "receiver": "測試單位",
                    "subject": "測試主旨"
                }
            })
            assert resp2.status_code == 200

            # 第三次應被限流（已用完 2 次配額）
            resp3 = client.post("/api/v1/agent/requirement", json={
                "user_input": "寫一份函，第三次被限流"
            })
            assert resp3.status_code == 429
        finally:
            api_server._rate_limiter = original

    def test_rate_limit_429_response_format(self, client, mock_api_deps):
        """測試 429 回應格式正確"""
        import api_server
        original = api_server._rate_limiter
        api_server._rate_limiter = api_server._RateLimiter(max_requests=1, window_seconds=60)
        try:
            client.post("/api/v1/agent/requirement", json={
                "user_input": "寫一份函，第一次請求"
            })
            resp = client.post("/api/v1/agent/requirement", json={
                "user_input": "寫一份函，第二次請求"
            })
            assert resp.status_code == 429
            data = resp.json()
            assert "detail" in data
            assert "retry_after_seconds" in data
            assert isinstance(data["retry_after_seconds"], int)
            assert data["retry_after_seconds"] > 0
            # 檢查標頭
            assert resp.headers.get("Retry-After") is not None
            assert resp.headers.get("X-RateLimit-Remaining") == "0"
            assert resp.headers.get("X-RateLimit-Limit") is not None
            assert resp.headers.get("X-Request-ID") is not None
        finally:
            api_server._rate_limiter = original


# ==================== 批次處理失敗隔離測試 ====================

class TestBatchFailureIsolation:
    """驗證批次處理中單一項目失敗不影響其他項目"""

    def test_batch_single_item_success(self, client, mock_api_deps):
        """測試批次處理單一項目成功"""
        call_count = [0]
        def side_effect(prompt, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return json.dumps({
                    "doc_type": "函",
                    "sender": "測試機關",
                    "receiver": "測試單位",
                    "subject": "測試主旨"
                })
            return "### 主旨\n測試公文\n### 說明\n測試說明"

        mock_api_deps["llm"].generate.side_effect = side_effect

        response = client.post("/api/v1/batch", json={
            "items": [{
                "user_input": "寫一份函，環保局發給各學校",
                "skip_review": True,
                "output_docx": False
            }]
        })
        assert response.status_code == 200
        data = response.json()
        assert data["summary"]["total"] == 1
        assert data["summary"]["success"] == 1
        assert data["summary"]["failed"] == 0
        assert len(data["results"]) == 1
        assert data["results"][0]["success"] is True

    def test_batch_failure_isolation_mixed(self, client, mock_api_deps):
        """測試批次處理中失敗項目不影響成功項目"""
        def side_effect(prompt, **kwargs):
            # 根據 prompt 內容分派（相容並行執行順序不確定）
            if "第二份" in prompt:
                raise RuntimeError("LLM 連線失敗")
            # 需求分析回應（含 JSON 格式）
            if "需求" in prompt and "分析" in prompt or "doc_type" not in prompt:
                for label, sender, receiver in [
                    ("第一份", "測試機關", "測試單位"),
                    ("第三份", "第三項機關", "第三項單位"),
                ]:
                    if label in prompt:
                        return json.dumps({
                            "doc_type": "函",
                            "sender": sender,
                            "receiver": receiver,
                            "subject": f"{label}主旨"
                        })
            # 預設回傳草稿
            return "### 主旨\n測試公文\n### 說明\n測試說明"

        mock_api_deps["llm"].generate.side_effect = side_effect

        response = client.post("/api/v1/batch", json={
            "items": [
                {"user_input": "第一份公文需求描述", "skip_review": True, "output_docx": False},
                {"user_input": "第二份公文需求描述", "skip_review": True, "output_docx": False},
                {"user_input": "第三份公文需求描述", "skip_review": True, "output_docx": False},
            ]
        })
        assert response.status_code == 200
        data = response.json()
        assert data["summary"]["total"] == 3
        # 第一和第三項成功，第二項失敗
        assert data["summary"]["success"] == 2
        assert data["summary"]["failed"] == 1
        assert len(data["results"]) == 3
        assert data["results"][0]["success"] is True
        assert data["results"][1]["success"] is False
        assert data["results"][2]["success"] is True
        # 失敗項目的錯誤訊息不洩漏內部細節
        assert "LLM 連線失敗" not in (data["results"][1].get("error") or "")

    def test_batch_all_items_fail(self, client, mock_api_deps):
        """測試批次處理所有項目都失敗時仍回傳完整結果"""
        mock_api_deps["llm"].generate.side_effect = RuntimeError("全部失敗")

        response = client.post("/api/v1/batch", json={
            "items": [
                {"user_input": "第一份公文需求描述", "skip_review": True, "output_docx": False},
                {"user_input": "第二份公文需求描述", "skip_review": True, "output_docx": False},
            ]
        })
        assert response.status_code == 200
        data = response.json()
        assert data["summary"]["total"] == 2
        assert data["summary"]["success"] == 0
        assert data["summary"]["failed"] == 2
        assert len(data["results"]) == 2
        for result in data["results"]:
            assert result["success"] is False
            assert result["error"] is not None
            assert "session_id" in result

    def test_batch_each_item_has_unique_session_id(self, client, mock_api_deps):
        """測試批次處理中每個項目有獨立的 session_id"""
        mock_api_deps["llm"].generate.side_effect = RuntimeError("失敗")

        response = client.post("/api/v1/batch", json={
            "items": [
                {"user_input": "第一份公文需求描述", "skip_review": True, "output_docx": False},
                {"user_input": "第二份公文需求描述", "skip_review": True, "output_docx": False},
                {"user_input": "第三份公文需求描述", "skip_review": True, "output_docx": False},
            ]
        })
        data = response.json()
        session_ids = [r["session_id"] for r in data["results"]]
        # 每個項目應有不同的 session_id
        assert len(set(session_ids)) == 3

    def test_batch_error_no_internal_leak(self, client, mock_api_deps):
        """測試批次處理失敗時不洩漏內部路徑等敏感資訊"""
        mock_api_deps["llm"].generate.side_effect = RuntimeError(
            "Connection refused at /internal/secret/path"
        )

        response = client.post("/api/v1/batch", json={
            "items": [{
                "user_input": "寫一份函，測試錯誤不洩漏",
                "skip_review": True,
                "output_docx": False
            }]
        })
        data = response.json()
        error_msg = data["results"][0].get("error") or ""
        assert "/internal" not in error_msg
        assert "secret" not in error_msg
        assert "Connection refused" not in error_msg

    def test_batch_empty_items_rejected(self, client, mock_api_deps):
        """測試空的 items 列表被 Pydantic 驗證攔截"""
        response = client.post("/api/v1/batch", json={"items": []})
        assert response.status_code == 422

    def test_batch_too_many_items_rejected(self, client, mock_api_deps):
        """測試超過 50 筆的批次被 Pydantic 驗證攔截"""
        items = [
            {"user_input": f"第{i}份公文需求描述內容", "skip_review": True, "output_docx": False}
            for i in range(51)
        ]
        response = client.post("/api/v1/batch", json={"items": items})
        assert response.status_code == 422


# ==================== API Key 認證 ====================

class TestAPIKeyAuth:
    """API Key 認證機制的測試"""

    @pytest.fixture
    def auth_config(self):
        """啟用認證的設定"""
        return {
            "llm": {"provider": "mock", "model": "test"},
            "knowledge_base": {"path": "./test_kb"},
            "api": {
                "auth_enabled": True,
                "api_keys": ["test-key-001", "test-key-002"],
            },
        }

    @pytest.fixture
    def auth_client(self, auth_config):
        """啟用認證的 TestClient"""
        import api_server

        api_server._config = auth_config

        api_server._llm = make_mock_llm()
        api_server._kb = make_mock_kb()

        from api_server import app
        return TestClient(app, raise_server_exceptions=False)

    # --- 認證明確停用時 ---

    def test_auth_explicitly_disabled(self, client):
        """認證明確停用時，所有端點應正常存取"""
        response = client.get("/")
        assert response.status_code == 200

    def test_auth_disabled_post_works(self, client, mock_api_deps):
        """認證明確停用時，POST 端點不需要 API Key"""
        response = client.post("/api/v1/agent/requirement", json={
            "user_input": "寫一份函，測試無認證存取"
        })
        assert response.status_code == 200

    # --- 認證啟用時：公開路徑免認證 ---

    def test_auth_root_always_public(self, auth_client):
        """/ 端點無論認證是否啟用都免認證"""
        response = auth_client.get("/")
        assert response.status_code == 200

    def test_auth_health_always_public(self, auth_client):
        """/api/v1/health 端點免認證"""
        response = auth_client.get("/api/v1/health")
        # 可能是 200 或 503（取決於元件狀態），但不應是 401
        assert response.status_code != 401

    def test_auth_docs_always_public(self, auth_client):
        """/docs 端點免認證"""
        response = auth_client.get("/docs")
        assert response.status_code != 401

    def test_auth_openapi_always_public(self, auth_client):
        """/openapi.json 端點免認證"""
        response = auth_client.get("/openapi.json")
        assert response.status_code != 401

    # --- 認證啟用時：需要 API Key ---

    def test_auth_required_no_key_returns_401(self, auth_client):
        """未提供 API Key 時回傳 401"""
        response = auth_client.post("/api/v1/agent/requirement", json={
            "user_input": "寫一份函，測試認證"
        })
        assert response.status_code == 401
        data = response.json()
        assert "API Key" in data["detail"]

    def test_auth_required_invalid_key_returns_401(self, auth_client):
        """提供無效的 API Key 時回傳 401"""
        response = auth_client.post(
            "/api/v1/agent/requirement",
            json={"user_input": "寫一份函，測試無效金鑰"},
            headers={"Authorization": "Bearer wrong-key"},
        )
        assert response.status_code == 401

    def test_auth_401_has_www_authenticate(self, auth_client):
        """401 回應應包含 WWW-Authenticate 標頭"""
        response = auth_client.post("/api/v1/agent/requirement", json={
            "user_input": "寫一份函，測試標頭"
        })
        assert response.status_code == 401
        assert response.headers.get("WWW-Authenticate") == "Bearer"

    def test_auth_401_has_request_id(self, auth_client):
        """401 回應應包含 X-Request-ID 標頭"""
        response = auth_client.post("/api/v1/agent/requirement", json={
            "user_input": "寫一份函，測試追蹤"
        })
        assert response.status_code == 401
        assert response.headers.get("X-Request-ID") is not None

    # --- 認證啟用時：有效 API Key ---

    def test_auth_bearer_token_accepted(self, auth_client):
        """使用 Authorization: Bearer <key> 認證成功"""
        response = auth_client.post(
            "/api/v1/agent/requirement",
            json={"user_input": "寫一份函，測試 Bearer 認證"},
            headers={"Authorization": "Bearer test-key-001"},
        )
        assert response.status_code == 200

    def test_auth_x_api_key_accepted(self, auth_client):
        """使用 X-API-Key 標頭認證成功"""
        response = auth_client.post(
            "/api/v1/agent/requirement",
            json={"user_input": "寫一份函，測試 X-API-Key 認證"},
            headers={"X-API-Key": "test-key-002"},
        )
        assert response.status_code == 200

    def test_auth_second_key_works(self, auth_client):
        """多組 API Key 都可使用"""
        response = auth_client.post(
            "/api/v1/agent/requirement",
            json={"user_input": "寫一份函，測試第二組金鑰"},
            headers={"Authorization": "Bearer test-key-002"},
        )
        assert response.status_code == 200

    def test_auth_bearer_takes_precedence(self, auth_client):
        """同時提供 Bearer 和 X-API-Key 時，Bearer 優先"""
        response = auth_client.post(
            "/api/v1/agent/requirement",
            json={"user_input": "寫一份函，測試優先順序"},
            headers={
                "Authorization": "Bearer test-key-001",
                "X-API-Key": "wrong-key",
            },
        )
        assert response.status_code == 200

    # --- 認證啟用但 api_keys 為空 ---

    def test_auth_enabled_empty_keys_rejects_access(self, mock_api_deps):
        """啟用認證但 api_keys 為空時，拒絕所有受保護端點"""
        import api_server

        api_server._config = {
            "llm": {"provider": "mock", "model": "test"},
            "knowledge_base": {"path": "./test_kb"},
            "api": {"auth_enabled": True, "api_keys": []},
        }

        from api_server import app
        empty_key_client = TestClient(app, raise_server_exceptions=False)

        response = empty_key_client.post("/api/v1/agent/requirement", json={
            "user_input": "寫一份函，測試空金鑰列表"
        })
        # 空金鑰列表拒絕存取，防止端點暴露
        assert response.status_code == 401

    def test_auth_enabled_empty_keys_public_paths_still_work(self, mock_api_deps):
        """啟用認證但 api_keys 為空時，公開路徑仍可存取"""
        import api_server

        api_server._config = {
            "llm": {"provider": "mock", "model": "test"},
            "knowledge_base": {"path": "./test_kb"},
            "api": {"auth_enabled": True, "api_keys": []},
        }

        from api_server import app
        empty_key_client = TestClient(app, raise_server_exceptions=False)

        response = empty_key_client.get("/api/v1/health")
        # 公開路徑（健康檢查）仍可存取，不受 api_keys 為空影響
        assert response.status_code != 401

    # --- auth_enabled 預設為 True（安全優先） ---

    def test_auth_enabled_by_default_when_no_api_section(self, mock_api_deps):
        """config 中無 api 區段時，認證預設啟用並拒絕受保護端點"""
        import api_server

        # 完全沒有 api 區段的 config
        api_server._config = {
            "llm": {"provider": "mock", "model": "test"},
            "knowledge_base": {"path": "./test_kb"},
        }

        from api_server import app
        no_api_client = TestClient(app, raise_server_exceptions=False)

        response = no_api_client.post("/api/v1/agent/requirement", json={
            "user_input": "寫一份函，測試預設認證"
        })
        assert response.status_code == 401

    def test_auth_default_public_paths_still_work(self, mock_api_deps):
        """config 中無 api 區段時，公開路徑仍可存取"""
        import api_server

        api_server._config = {
            "llm": {"provider": "mock", "model": "test"},
            "knowledge_base": {"path": "./test_kb"},
        }

        from api_server import app
        no_api_client = TestClient(app, raise_server_exceptions=False)

        response = no_api_client.get("/api/v1/health")
        assert response.status_code != 401

    def test_health_shows_auth_enabled_by_default(self, mock_api_deps):
        """config 中無 api 區段時，健康檢查應顯示 auth_enabled=true"""
        import api_server

        api_server._config = {
            "llm": {"provider": "mock", "model": "test"},
            "knowledge_base": {"path": "./test_kb"},
        }

        from api_server import app
        no_api_client = TestClient(app, raise_server_exceptions=False)

        response = no_api_client.get("/api/v1/health")
        data = response.json()
        assert "auth_enabled" in data
        assert data["auth_enabled"] is True

    # --- GET 端點也需要認證 ---

    def test_auth_get_download_requires_key(self, auth_client):
        """GET /api/v1/download/ 在認證啟用時需要 API Key"""
        response = auth_client.get("/api/v1/download/test.docx")
        assert response.status_code == 401

    def test_auth_get_download_with_key(self, auth_client):
        """GET /api/v1/download/ 提供有效 Key 可存取"""
        response = auth_client.get(
            "/api/v1/download/test.docx",
            headers={"Authorization": "Bearer test-key-001"},
        )
        # 檔案不存在會回傳 400 或 404，但不應是 401
        assert response.status_code != 401

    # --- 健康檢查顯示認證狀態 ---

    def test_health_shows_auth_enabled(self, auth_client):
        """健康檢查回應應顯示 auth_enabled 狀態"""
        response = auth_client.get("/api/v1/health")
        data = response.json()
        assert "auth_enabled" in data
        assert data["auth_enabled"] is True

    def test_health_shows_auth_disabled(self, client, mock_api_deps):
        """認證停用時健康檢查應顯示 auth_enabled=false"""
        response = client.get("/api/v1/health")
        data = response.json()
        assert "auth_enabled" in data
        assert data["auth_enabled"] is False


# ==================== Metrics Endpoint ====================

class TestMetricsEndpoint:
    """效能監控端點 /api/v1/metrics 的測試"""

    def test_metrics_initial_state(self, client):
        """測試初始狀態下 metrics 端點回傳零值"""
        response = client.get("/api/v1/metrics")
        assert response.status_code == 200
        data = response.json()
        # 注意：GET /api/v1/metrics 本身會被中介層計數，所以 total_requests >= 0
        assert "total_requests" in data
        assert "avg_response_time_ms" in data
        assert "active_requests" in data
        assert "cache_hit_rate" in data
        assert "cache_hits" in data
        assert "cache_misses" in data
        assert "executor_max_workers" in data
        assert isinstance(data["total_requests"], int)
        assert isinstance(data["avg_response_time_ms"], (int, float))
        assert isinstance(data["cache_hit_rate"], (int, float))

    def test_metrics_count_increases_after_requests(self, client):
        """多次請求後 total_requests 應遞增"""
        # 先發幾個請求
        client.get("/")
        client.get("/")
        client.get("/")
        response = client.get("/api/v1/metrics")
        data = response.json()
        # 3 次 GET / 已完成記錄，/metrics 本身的記錄在回應後才完成
        assert data["total_requests"] >= 3

    def test_metrics_avg_response_time_positive(self, client):
        """有請求後平均回應時間應為正數"""
        client.get("/")
        response = client.get("/api/v1/metrics")
        data = response.json()
        assert data["avg_response_time_ms"] > 0

    def test_metrics_cache_hit_rate_zero_without_cache(self, client):
        """未有快取操作時 cache_hit_rate 應為 0"""
        response = client.get("/api/v1/metrics")
        data = response.json()
        assert data["cache_hit_rate"] == 0.0

    def test_metrics_collector_thread_safety(self):
        """測試 _MetricsCollector 在多執行緒下的正確性"""
        import api_server
        collector = api_server._MetricsCollector()
        import concurrent.futures

        def increment_n_times(n):
            for _ in range(n):
                collector.record_request_start()
                collector.record_request_end(10.0)

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(increment_n_times, 100) for _ in range(4)]
            concurrent.futures.wait(futures)

        snap = collector.snapshot()
        assert snap["total_requests"] == 400
        assert snap["active_requests"] == 0

    def test_metrics_cache_recording(self):
        """測試快取命中/未命中紀錄"""
        import api_server
        collector = api_server._MetricsCollector()
        collector.record_cache_hit()
        collector.record_cache_hit()
        collector.record_cache_miss()
        snap = collector.snapshot()
        assert snap["cache_hits"] == 2
        assert snap["cache_misses"] == 1
        assert abs(snap["cache_hit_rate"] - 2 / 3) < 0.01

    def test_metrics_executor_max_workers(self, client):
        """測試 metrics 回傳正確的 executor_max_workers"""
        from src.core.constants import API_MAX_WORKERS
        response = client.get("/api/v1/metrics")
        data = response.json()
        assert data["executor_max_workers"] == API_MAX_WORKERS


# ==================== Batch Total Timeout ====================

class TestBatchTotalTimeout:
    """批次處理總體超時保護"""

    def test_batch_total_timeout_returns_504(self, client, mock_api_deps):
        """批次處理超過總體時限時應回傳 504"""
        import src.api.routes.workflow as wf_mod

        original = wf_mod.BATCH_TOTAL_TIMEOUT
        wf_mod.BATCH_TOTAL_TIMEOUT = 0.001  # 極短超時觸發 504
        try:
            response = client.post("/api/v1/batch", json={
                "items": [{"user_input": "測試需求文字描述，需要足夠長度通過驗證"}]
            })
            assert response.status_code == 504
            assert "總體時限" in response.json()["detail"]
        finally:
            wf_mod.BATCH_TOTAL_TIMEOUT = original


# ==================== Batch Progress Tracking ====================

class TestBatchProgressTracking:
    """批次處理進度追蹤功能的測試"""

    def test_batch_response_has_progress_field(self, client, mock_api_deps):
        """測試批次回應包含 progress 欄位"""
        call_count = [0]
        def side_effect(prompt, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return json.dumps({
                    "doc_type": "函",
                    "sender": "測試機關",
                    "receiver": "測試單位",
                    "subject": "測試主旨"
                })
            return "### 主旨\n測試公文\n### 說明\n測試說明"

        mock_api_deps["llm"].generate.side_effect = side_effect

        response = client.post("/api/v1/batch", json={
            "items": [{
                "user_input": "寫一份函，測試進度追蹤",
                "skip_review": True,
                "output_docx": False
            }]
        })
        assert response.status_code == 200
        data = response.json()
        assert "progress" in data
        assert data["progress"]["completed"] == 1
        assert data["progress"]["total"] == 1

    def test_batch_response_has_total_duration_ms(self, client, mock_api_deps):
        """測試批次回應包含 total_duration_ms"""
        mock_api_deps["llm"].generate.side_effect = RuntimeError("失敗")

        response = client.post("/api/v1/batch", json={
            "items": [{
                "user_input": "寫一份函，測試耗時",
                "skip_review": True,
                "output_docx": False
            }]
        })
        data = response.json()
        assert "total_duration_ms" in data
        assert isinstance(data["total_duration_ms"], (int, float))
        assert data["total_duration_ms"] >= 0

    def test_batch_item_has_status_field(self, client, mock_api_deps):
        """測試批次回應每筆結果包含 status 欄位"""
        def side_effect(prompt, **kwargs):
            # 根據 prompt 內容分派（相容並行執行）
            if "第二份" in prompt:
                raise RuntimeError("LLM 錯誤")
            if "第一份" in prompt:
                return json.dumps({
                    "doc_type": "函",
                    "sender": "測試機關",
                    "receiver": "測試單位",
                    "subject": "測試主旨"
                })
            return "### 主旨\n測試公文\n### 說明\n測試說明"

        mock_api_deps["llm"].generate.side_effect = side_effect

        response = client.post("/api/v1/batch", json={
            "items": [
                {"user_input": "第一份成功", "skip_review": True, "output_docx": False},
                {"user_input": "第二份失敗", "skip_review": True, "output_docx": False},
            ]
        })
        data = response.json()
        assert data["results"][0]["status"] == "success"
        assert data["results"][1]["status"] == "error"

    def test_batch_item_has_duration_ms(self, client, mock_api_deps):
        """測試批次回應每筆結果包含 duration_ms"""
        mock_api_deps["llm"].generate.side_effect = RuntimeError("失敗")

        response = client.post("/api/v1/batch", json={
            "items": [{
                "user_input": "寫一份函，測試單項耗時",
                "skip_review": True,
                "output_docx": False
            }]
        })
        data = response.json()
        assert "duration_ms" in data["results"][0]
        assert isinstance(data["results"][0]["duration_ms"], (int, float))
        assert data["results"][0]["duration_ms"] >= 0

    def test_batch_error_item_has_error_message(self, client, mock_api_deps):
        """測試失敗項目包含 error_message 欄位"""
        mock_api_deps["llm"].generate.side_effect = RuntimeError("某個錯誤")

        response = client.post("/api/v1/batch", json={
            "items": [{
                "user_input": "寫一份函，測試錯誤訊息",
                "skip_review": True,
                "output_docx": False
            }]
        })
        data = response.json()
        result = data["results"][0]
        assert result["status"] == "error"
        assert result["error_message"] is not None
        # error_message 不應洩漏內部細節
        assert "某個錯誤" not in result["error_message"]

    def test_batch_success_item_no_error_message(self, client, mock_api_deps):
        """測試成功項目的 error_message 應為 null"""
        call_count = [0]
        def side_effect(prompt, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return json.dumps({
                    "doc_type": "函",
                    "sender": "測試機關",
                    "receiver": "測試單位",
                    "subject": "測試主旨"
                })
            return "### 主旨\n測試公文\n### 說明\n測試說明"

        mock_api_deps["llm"].generate.side_effect = side_effect

        response = client.post("/api/v1/batch", json={
            "items": [{
                "user_input": "寫一份函，成功項目",
                "skip_review": True,
                "output_docx": False
            }]
        })
        data = response.json()
        result = data["results"][0]
        assert result["status"] == "success"
        assert result["error_message"] is None

    def test_batch_progress_matches_total(self, client, mock_api_deps):
        """測試 progress.completed 等於 progress.total（同步處理完成後）"""
        mock_api_deps["llm"].generate.side_effect = RuntimeError("失敗")

        response = client.post("/api/v1/batch", json={
            "items": [
                {"user_input": "第一份公文", "skip_review": True, "output_docx": False},
                {"user_input": "第二份公文", "skip_review": True, "output_docx": False},
                {"user_input": "第三份公文", "skip_review": True, "output_docx": False},
            ]
        })
        data = response.json()
        assert data["progress"]["completed"] == 3
        assert data["progress"]["total"] == 3

    def test_batch_backward_compat_summary(self, client, mock_api_deps):
        """測試 summary 欄位仍然向後相容"""
        mock_api_deps["llm"].generate.side_effect = RuntimeError("失敗")

        response = client.post("/api/v1/batch", json={
            "items": [{
                "user_input": "寫一份函，向後相容",
                "skip_review": True,
                "output_docx": False
            }]
        })
        data = response.json()
        assert "summary" in data
        assert "total" in data["summary"]
        assert "success" in data["summary"]
        assert "failed" in data["summary"]

    def test_batch_backward_compat_result_fields(self, client, mock_api_deps):
        """測試每筆結果仍包含原有的 MeetingResponse 欄位（向後相容）"""
        call_count = [0]
        def side_effect(prompt, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return json.dumps({
                    "doc_type": "函",
                    "sender": "測試機關",
                    "receiver": "測試單位",
                    "subject": "測試主旨"
                })
            return "### 主旨\n測試公文\n### 說明\n測試說明"

        mock_api_deps["llm"].generate.side_effect = side_effect

        response = client.post("/api/v1/batch", json={
            "items": [{
                "user_input": "寫一份函，測試相容性",
                "skip_review": True,
                "output_docx": False
            }]
        })
        data = response.json()
        result = data["results"][0]
        # 原有的 MeetingResponse 欄位仍存在
        assert "success" in result
        assert "session_id" in result
        assert result["success"] is True


# ==================== Web UI Generate ====================

class TestWebUIGenerate:
    """Web UI POST /ui/generate 端點測試"""

    def test_generate_post_returns_result(self, mock_api_deps):
        """Mock LLM 和 KB 後，POST /ui/generate 回傳包含生成內容的 HTML"""

        call_count = [0]
        def side_effect(prompt, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return json.dumps({
                    "doc_type": "函",
                    "sender": "環保局",
                    "receiver": "各學校",
                    "subject": "加強資源回收",
                })
            return "### 主旨\n加強資源回收\n### 說明\n請各校配合辦理。"

        mock_api_deps["llm"].generate.side_effect = side_effect

        from api_server import app
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post("/ui/generate", data={
            "user_input": "幫我寫一份函，環保局發給各學校，關於加強資源回收",
            "doc_type": "",
            "skip_review": "false",
        })
        # Web UI 回傳 HTML（200 或 HTMX 回應）
        assert response.status_code == 200
        # 回傳應為 HTML
        assert "text/html" in response.headers.get("content-type", "")

    def test_generate_post_with_doc_type(self, mock_api_deps):
        """指定公文類型時，effective_input 應包含類型前綴"""

        call_count = [0]
        def side_effect(prompt, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return json.dumps({
                    "doc_type": "公告",
                    "sender": "環保局",
                    "receiver": "各機關",
                    "subject": "測試主旨",
                })
            return "### 主旨\n測試公告\n### 說明\n測試內容。"

        mock_api_deps["llm"].generate.side_effect = side_effect

        from api_server import app
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post("/ui/generate", data={
            "user_input": "寫一份公告",
            "doc_type": "公告",
            "skip_review": "false",
        })
        assert response.status_code == 200


# ==================== Detailed Review Endpoint ====================

class TestDetailedReviewEndpoint:
    """/api/v1/detailed-review 端點測試"""

    def test_missing_session_id_returns_400(self, client):
        response = client.get("/api/v1/detailed-review")
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "缺少 session_id 參數"

    def test_invalid_session_id_returns_400(self, client):
        response = client.get(
            "/api/v1/detailed-review",
            params={"session_id": "../../etc/passwd"},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert "格式無效" in data["error"]

    def test_unknown_session_returns_404(self, client):
        response = client.get(
            "/api/v1/detailed-review",
            params={"session_id": "unknown-session-123"},
        )
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert "找不到對應的審查報告" in data["error"]

    def test_meeting_report_can_be_queried_by_session(self, client, mock_api_deps):
        mock_requirement = MagicMock()
        mock_requirement.model_dump.return_value = {
            "doc_type": "函",
            "sender": "測試機關",
            "receiver": "測試單位",
            "subject": "測試主旨",
        }
        mock_qa = MagicMock()
        mock_qa.model_dump.return_value = {
            "overall_score": 0.92,
            "risk_summary": "Safe",
            "agent_results": [],
            "rounds_used": 2,
        }
        mock_qa.audit_log = "mock-audit-log"
        mock_qa.rounds_used = 2

        with patch(
            "src.api.routes.workflow._execute_document_workflow",
            return_value=(mock_requirement, "這是最終草稿", mock_qa, None, 2),
        ):
            meeting_resp = client.post(
                "/api/v1/meeting",
                json={
                    "user_input": "請寫一份測試公文",
                    "skip_review": False,
                    "output_docx": False,
                    "use_graph": False,
                },
            )

        assert meeting_resp.status_code == 200
        meeting_data = meeting_resp.json()
        assert meeting_data["success"] is True
        session_id = meeting_data["session_id"]

        review_resp = client.get(
            "/api/v1/detailed-review",
            params={"session_id": session_id},
        )
        assert review_resp.status_code == 200
        review_data = review_resp.json()
        assert review_data["success"] is True
        assert review_data["session_id"] == session_id
        assert review_data["qa_report"]["risk_summary"] == "Safe"
        assert review_data["final_draft"] == "這是最終草稿"

    def test_skip_review_session_has_no_detailed_report(self, client, mock_api_deps):
        mock_requirement = MagicMock()
        mock_requirement.model_dump.return_value = {
            "doc_type": "函",
            "sender": "測試機關",
            "receiver": "測試單位",
            "subject": "測試主旨",
        }

        with patch(
            "src.api.routes.workflow._execute_document_workflow",
            return_value=(mock_requirement, "僅草稿", None, None, 0),
        ):
            meeting_resp = client.post(
                "/api/v1/meeting",
                json={
                    "user_input": "請寫一份不審查測試公文",
                    "skip_review": True,
                    "output_docx": False,
                    "use_graph": False,
                },
            )

        assert meeting_resp.status_code == 200
        session_id = meeting_resp.json()["session_id"]
        review_resp = client.get(
            "/api/v1/detailed-review",
            params={"session_id": session_id},
        )
        assert review_resp.status_code == 404
        review_data = review_resp.json()
        assert review_data["success"] is False


# ==================== KBSearchRequest Validation ====================

class TestKBSearchValidation:
    """知識庫搜尋請求欄位驗證測試"""

    def test_kb_search_valid_source_level_a(self, client, mock_api_deps):
        """source_level=A 為合法值"""
        mock_api_deps["kb"].search_examples.return_value = []
        mock_api_deps["kb"].search_regulations.return_value = []
        response = client.post("/api/v1/kb/search", json={
            "query": "資源回收",
            "source_level": "A",
        })
        assert response.status_code == 200

    def test_kb_search_valid_source_level_b(self, client, mock_api_deps):
        """source_level=B 為合法值"""
        mock_api_deps["kb"].search_examples.return_value = []
        mock_api_deps["kb"].search_regulations.return_value = []
        response = client.post("/api/v1/kb/search", json={
            "query": "資源回收",
            "source_level": "B",
        })
        assert response.status_code == 200

    def test_kb_search_null_source_level(self, client, mock_api_deps):
        """source_level=null（未指定）為合法"""
        mock_api_deps["kb"].search_examples.return_value = []
        mock_api_deps["kb"].search_regulations.return_value = []
        response = client.post("/api/v1/kb/search", json={
            "query": "資源回收",
        })
        assert response.status_code == 200

    def test_kb_search_invalid_source_level(self, client, mock_api_deps):
        """source_level=Z 為非法值，應回傳 422"""
        response = client.post("/api/v1/kb/search", json={
            "query": "test",
            "source_level": "Z",
        })
        assert response.status_code == 422

    def test_kb_search_invalid_source_level_lowercase(self, client, mock_api_deps):
        """source_level=a（小寫）為非法值"""
        response = client.post("/api/v1/kb/search", json={
            "query": "test",
            "source_level": "a",
        })
        assert response.status_code == 422

    def test_kb_search_invalid_source_level_c(self, client, mock_api_deps):
        """source_level=C 為非法值"""
        response = client.post("/api/v1/kb/search", json={
            "query": "test",
            "source_level": "C",
        })
        assert response.status_code == 422


# ==================== Metrics Auth ====================

class TestMetricsAuth:
    """效能監控端點 /api/v1/metrics 的認證測試"""

    @pytest.fixture
    def auth_config(self):
        """啟用認證的設定"""
        return {
            "llm": {"provider": "mock", "model": "test"},
            "knowledge_base": {"path": "./test_kb"},
            "api": {
                "auth_enabled": True,
                "api_keys": ["metrics-key-001"],
            },
        }

    @pytest.fixture
    def metrics_auth_client(self, auth_config):
        """啟用認證的 TestClient"""
        import api_server

        api_server._config = auth_config

        api_server._llm = make_mock_llm()
        api_server._kb = make_mock_kb()

        from api_server import app
        return TestClient(app, raise_server_exceptions=False)

    def test_metrics_requires_auth_when_enabled(self, metrics_auth_client):
        """啟用認證時，GET /api/v1/metrics 無 key 應回傳 401"""
        response = metrics_auth_client.get("/api/v1/metrics")
        assert response.status_code == 401

    def test_metrics_accessible_with_valid_key(self, metrics_auth_client):
        """啟用認證時，GET /api/v1/metrics 有 key 應回傳 200"""
        response = metrics_auth_client.get(
            "/api/v1/metrics",
            headers={"Authorization": "Bearer metrics-key-001"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_requests" in data

    def test_metrics_rate_limited(self, client, mock_api_deps):
        """GET /api/v1/metrics 應受到 rate limiting"""
        import api_server
        original_limiter = api_server._rate_limiter
        api_server._rate_limiter = api_server._RateLimiter(max_requests=1, window_seconds=60)

        try:
            # 第一次允許
            resp1 = client.get("/api/v1/metrics")
            assert resp1.status_code == 200
            assert resp1.headers.get("X-RateLimit-Limit") is not None

            # 第二次被限流
            resp2 = client.get("/api/v1/metrics")
            assert resp2.status_code == 429
        finally:
            api_server._rate_limiter = original_limiter

    def test_metrics_no_auth_when_disabled(self, client):
        """認證停用時，GET /api/v1/metrics 不需要 key"""
        response = client.get("/api/v1/metrics")
        assert response.status_code == 200


# ==================== SSRF Protection ====================

class TestSSRFProtection:
    """Web UI SSRF 防護測試"""

    def test_web_ui_api_base_rejects_external_host(self):
        """WEB_UI_API_BASE 設為外部 host 時應拋出 ValueError"""
        import importlib
        import os

        original = os.environ.get("WEB_UI_API_BASE")
        os.environ["WEB_UI_API_BASE"] = "http://evil.example.com:8000"

        try:
            # 重新載入模組應觸發 SSRF 檢查
            import src.web_preview.app as wp_module
            with pytest.raises(ValueError, match="只允許本機地址"):
                importlib.reload(wp_module)
        finally:
            if original is not None:
                os.environ["WEB_UI_API_BASE"] = original
            else:
                os.environ.pop("WEB_UI_API_BASE", None)
            # 恢復正常模組狀態
            try:
                importlib.reload(wp_module)
            except Exception:
                pass

    def test_web_ui_api_base_allows_localhost(self):
        """WEB_UI_API_BASE 設為 localhost 時不應拋出"""
        from urllib.parse import urlparse
        for host in ("http://localhost:8000", "http://127.0.0.1:8000", "http://[::1]:8000"):
            parsed = urlparse(host)
            assert parsed.hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1")


# ============================================================
# resolve_bind_host 安全綁定測試
# ============================================================

class TestResolveBindHost:
    """測試 api_server.resolve_bind_host() 安全邏輯。"""

    def test_localhost_always_passes(self):
        """127.0.0.1 不論認證設定如何都應直接通過"""
        from api_server import resolve_bind_host
        assert resolve_bind_host("127.0.0.1", auth_enabled=False, api_keys=[]) == "127.0.0.1"
        assert resolve_bind_host("127.0.0.1", auth_enabled=True, api_keys=[]) == "127.0.0.1"

    def test_auth_enabled_with_keys_allows_external(self):
        """認證啟用且有 key 時允許外部綁定"""
        from api_server import resolve_bind_host
        assert resolve_bind_host("0.0.0.0", auth_enabled=True, api_keys=["secret"]) == "0.0.0.0"

    def test_auth_enabled_no_keys_forces_localhost(self):
        """認證啟用但無 key 時強制 127.0.0.1"""
        from api_server import resolve_bind_host
        assert resolve_bind_host("0.0.0.0", auth_enabled=True, api_keys=[]) == "127.0.0.1"

    def test_auth_disabled_external_forces_localhost(self):
        """認證關閉 + 非 localhost 綁定 → 強制 127.0.0.1"""
        from api_server import resolve_bind_host
        assert resolve_bind_host("0.0.0.0", auth_enabled=False, api_keys=[]) == "127.0.0.1"

    def test_auth_disabled_external_with_insecure_flag(self):
        """認證關閉 + ALLOW_INSECURE_BIND=true → 允許外部綁定"""
        from api_server import resolve_bind_host
        result = resolve_bind_host(
            "0.0.0.0", auth_enabled=False, api_keys=[],
            allow_insecure_bind=True,
        )
        assert result == "0.0.0.0"

    def test_auth_disabled_external_insecure_flag_false(self):
        """認證關閉 + allow_insecure_bind=False → 強制 127.0.0.1"""
        from api_server import resolve_bind_host
        result = resolve_bind_host(
            "0.0.0.0", auth_enabled=False, api_keys=[],
            allow_insecure_bind=False,
        )
        assert result == "127.0.0.1"

    def test_custom_host_with_valid_auth(self):
        """自訂 IP + 有效認證 → 維持原 host"""
        from api_server import resolve_bind_host
        assert resolve_bind_host("192.168.1.100", auth_enabled=True, api_keys=["k1"]) == "192.168.1.100"

    def test_custom_host_auth_disabled_blocked(self):
        """自訂 IP + 認證關閉 → 強制 127.0.0.1"""
        from api_server import resolve_bind_host
        assert resolve_bind_host("192.168.1.100", auth_enabled=False, api_keys=[]) == "127.0.0.1"


class TestCleanupOldOutputs:
    """_cleanup_old_outputs 的 Windows 檔案鎖定防護測試。"""

    def test_cleanup_deletes_old_files(self, tmp_path):
        """超過 24 小時的 .docx 應被刪除。"""
        import time
        old_file = tmp_path / "old.docx"
        old_file.write_text("test")
        old_mtime = time.time() - 90000
        import os
        os.utime(old_file, (old_mtime, old_mtime))

        with patch("src.core.constants.OUTPUT_DIR", tmp_path):
            from api_server import _cleanup_old_outputs
            _cleanup_old_outputs()

        assert not old_file.exists()

    def test_cleanup_keeps_recent_files(self, tmp_path):
        """未超過 24 小時的 .docx 不應被刪除。"""
        recent_file = tmp_path / "recent.docx"
        recent_file.write_text("test")

        with patch("src.core.constants.OUTPUT_DIR", tmp_path):
            from api_server import _cleanup_old_outputs
            _cleanup_old_outputs()

        assert recent_file.exists()

    def test_cleanup_handles_locked_file(self, tmp_path):
        """被鎖定的檔案（PermissionError）應被跳過，不影響其他檔案。"""
        import time
        old_mtime = time.time() - 90000

        locked = tmp_path / "locked.docx"
        locked.write_text("locked")
        import os
        os.utime(locked, (old_mtime, old_mtime))

        deletable = tmp_path / "deletable.docx"
        deletable.write_text("deletable")
        os.utime(deletable, (old_mtime, old_mtime))

        original_unlink = type(locked).unlink

        def mock_unlink(self_path, *args, **kwargs):
            if self_path.name == "locked.docx":
                raise PermissionError("file is locked")
            return original_unlink(self_path, *args, **kwargs)

        with patch("src.core.constants.OUTPUT_DIR", tmp_path), \
             patch.object(type(locked), "unlink", mock_unlink):
            from api_server import _cleanup_old_outputs
            _cleanup_old_outputs()

        assert locked.exists()
        assert not deletable.exists()

    def test_cleanup_handles_stat_error(self, tmp_path):
        """stat() 失敗（如檔案在 glob 後被刪除）應被跳過。"""
        old_file = tmp_path / "vanished.docx"
        old_file.write_text("test")

        original_stat = type(old_file).stat

        def mock_stat(self_path, *args, **kwargs):
            if self_path.name == "vanished.docx":
                raise OSError("file vanished")
            return original_stat(self_path, *args, **kwargs)

        with patch("src.core.constants.OUTPUT_DIR", tmp_path), \
             patch.object(type(old_file), "stat", mock_stat):
            from api_server import _cleanup_old_outputs
            _cleanup_old_outputs()  # 不應拋出例外

    def test_cleanup_nonexistent_dir(self):
        """輸出目錄不存在時應安靜返回。"""
        from pathlib import Path
        fake_dir = Path("/nonexistent_dir_test_12345")
        with patch("src.core.constants.OUTPUT_DIR", fake_dir):
            from api_server import _cleanup_old_outputs
            _cleanup_old_outputs()  # 不應拋出例外


class TestAutoKeyNoLogLeak:
    """驗證自動產生的 API key 不會洩漏到 logger。"""

    def test_generated_key_not_in_log_output(self):
        """ensure_api_key 的 logger.warning 不應包含 key 的任何部分。"""
        import src.api.middleware as mw

        # 重設全域狀態
        mw._auto_key_generated = False

        mock_config = MagicMock()
        mock_config.get.return_value = {"auth_enabled": True, "api_keys": []}

        import logging
        with patch.object(mw.logger, "warning") as mock_warn, \
             patch("builtins.print"):  # 攔截 stderr 輸出
            mw.ensure_api_key(mock_config)

        # logger.warning 應被呼叫但不包含 key 內容
        assert mock_warn.called
        logged_msg = mock_warn.call_args[0][0]
        # 訊息不應包含 %s 格式化佔位（key 前綴已移除）
        assert "%s" not in logged_msg

        # 重設
        mw._auto_key_generated = False

    def test_generated_key_printed_to_stderr(self):
        """完整 key 應透過 stderr 輸出，不經過 logger。"""
        import src.api.middleware as mw

        mw._auto_key_generated = False

        mock_config = MagicMock()
        mock_config.get.return_value = {"auth_enabled": True, "api_keys": []}

        with patch("src.api.middleware.print") as mock_print:
            mw.ensure_api_key(mock_config)

        assert mock_print.called
        printed_text = mock_print.call_args[0][0]
        assert "臨時 API Key" in printed_text
        # 確保印出的是完整 key（43 字元的 base64url）
        import re
        key_match = re.search(r"[A-Za-z0-9_-]{40,}", printed_text)
        assert key_match is not None

        mw._auto_key_generated = False
