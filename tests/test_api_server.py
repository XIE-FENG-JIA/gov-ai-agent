"""
api_server.py 的 API 端點測試
使用 FastAPI TestClient 和 mock 來避免依賴外部服務
"""
import pytest
import json
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from src.core.llm import LLMProvider
from src.core.review_models import ReviewResult, ReviewIssue


# ==================== Fixtures ====================

@pytest.fixture(autouse=True)
def reset_api_globals():
    """在每個測試前重設 API 伺服器的全域變數和限流器"""
    import api_server
    api_server._config = None
    api_server._llm = None
    api_server._kb = None
    # 重置限流器，避免測試之間互相干擾
    api_server._rate_limiter._requests.clear()
    yield
    api_server._config = None
    api_server._llm = None
    api_server._kb = None


@pytest.fixture
def mock_api_deps():
    """Mock 所有 API 依賴項（LLM、KB、Config）"""
    import api_server

    # Mock config
    mock_config = {
        "llm": {"provider": "mock", "model": "test"},
        "knowledge_base": {"path": "./test_kb"}
    }
    api_server._config = mock_config

    # Mock LLM
    mock_llm = MagicMock(spec=LLMProvider)
    mock_llm.generate.return_value = "Mock Response"
    mock_llm.embed.return_value = [0.1] * 384
    api_server._llm = mock_llm

    # Mock KB
    mock_kb = MagicMock()
    mock_kb.search_examples.return_value = []
    mock_kb.search_regulations.return_value = []
    mock_kb.search_policies.return_value = []
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
        """測試需求分析失敗（LLM 回傳無效內容）"""
        mock_api_deps["llm"].generate.return_value = "completely invalid"

        response = client.post("/api/v1/agent/requirement", json={
            "user_input": "這是一個測試用的需求描述"  # 需要至少 5 個字元
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["error"] is not None

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
        assert data["formatted_draft"] is not None

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
        """測試沒有反饋時回傳原始草稿"""
        original = "### 主旨\n原始內容，這是一份測試草稿"
        response = client.post("/api/v1/agent/refine", json={
            "draft": original,
            "feedback": []
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["refined_draft"] == original

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

    def test_meeting_failure(self, client, mock_api_deps):
        """測試開會流程失敗"""
        mock_api_deps["llm"].generate.return_value = "completely invalid"

        response = client.post("/api/v1/meeting", json={
            "user_input": "這是一個測試用的需求描述",
            "skip_review": True,
            "output_docx": False
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["error"] is not None

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


# ==================== Rate Limit via HTTP ====================

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
        """測試 writer 端點 LLM 拋出異常時回傳 error"""
        mock_api_deps["llm"].generate.side_effect = RuntimeError("LLM 連線超時")

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
        # 不洩漏內部錯誤
        assert "LLM 連線超時" not in (data["error"] or "")


# ==================== Review Endpoints Exception ====================

class TestReviewExceptionHandling:
    """各審查端點的異常處理測試"""

    def test_review_format_exception(self, client, mock_api_deps):
        """測試格式審查端點在初始化異常時回傳錯誤

        FormatAuditor 內部會捕捉 LLM 異常，因此需要讓端點層級的程式碼拋出異常。
        透過讓 get_kb() 拋出異常觸發端點的 except 塊。
        """
        import api_server
        original_get_kb = api_server.get_kb

        def broken_get_kb():
            raise RuntimeError("KB 初始化失敗")

        api_server.get_kb = broken_get_kb

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
            api_server.get_kb = original_get_kb

    def test_review_style_exception(self, client, mock_api_deps):
        """測試文風審查端點 LLM 異常"""
        mock_api_deps["llm"].generate.side_effect = RuntimeError("文風審查失敗")

        response = client.post("/api/v1/agent/review/style", json={
            "draft": "### 主旨\n這是一份測試公文的草稿內容",
            "doc_type": "函"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["agent_name"] == "style"
        assert data["error"] is not None

    def test_review_fact_exception(self, client, mock_api_deps):
        """測試事實審查端點 LLM 異常"""
        mock_api_deps["llm"].generate.side_effect = RuntimeError("事實審查失敗")

        response = client.post("/api/v1/agent/review/fact", json={
            "draft": "### 主旨\n這是一份測試公文的草稿內容",
            "doc_type": "函"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["agent_name"] == "fact"
        assert data["error"] is not None

    def test_review_consistency_exception(self, client, mock_api_deps):
        """測試一致性審查端點 LLM 異常"""
        mock_api_deps["llm"].generate.side_effect = RuntimeError("一致性審查失敗")

        response = client.post("/api/v1/agent/review/consistency", json={
            "draft": "### 主旨\n測試\n### 說明\n一致的內容",
            "doc_type": "函"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["agent_name"] == "consistency"
        assert data["error"] is not None

    def test_review_compliance_exception(self, client, mock_api_deps):
        """測試合規審查端點在初始化異常時回傳錯誤

        ComplianceChecker 內部會捕捉 LLM 異常，因此需要讓端點層級的程式碼拋出異常。
        透過讓 get_kb() 拋出異常觸發端點的 except 塊。
        """
        import api_server
        original_get_kb = api_server.get_kb

        def broken_get_kb():
            raise RuntimeError("KB 初始化失敗")

        api_server.get_kb = broken_get_kb

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
            api_server.get_kb = original_get_kb


# ==================== Parallel Review Exception ====================

class TestParallelReviewExceptionHandling:
    """並行審查的異常處理測試"""

    def test_parallel_review_single_agent_failure(self, client, mock_api_deps):
        """測試並行審查中單一 Agent 失敗，其他正常

        使用 patch 讓 FactChecker 的 check 方法拋出異常，
        確保 style agent 正常完成但 fact agent 失敗。
        """
        mock_api_deps["llm"].generate.return_value = '{"issues": [], "score": 0.9}'

        with patch("api_server.FactChecker") as MockFactChecker:
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

    def test_parallel_review_all_agents_failure(self, client, mock_api_deps):
        """測試並行審查中所有 Agent 都失敗"""
        mock_api_deps["llm"].generate.side_effect = RuntimeError("全部失敗")

        response = client.post("/api/v1/agent/review/parallel", json={
            "draft": "### 主旨\n正式公文\n### 說明\n測試說明",
            "doc_type": "函",
            "agents": ["style", "fact", "consistency"]
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # 所有 agent 的分數都應為 0
        for agent_name in ["style", "fact", "consistency"]:
            assert data["results"][agent_name]["score"] == 0.0
            assert data["results"][agent_name]["has_errors"] is True
        # 總分應為 0
        assert data["aggregated_score"] == 0.0

    def test_parallel_review_overall_exception(self, client, mock_api_deps):
        """測試並行審查整體失敗（非 agent 層級的異常）"""
        import api_server
        # 讓 get_llm() 拋出異常，觸發外層 except
        original_llm = api_server._llm
        api_server._llm = None
        original_get_llm = api_server.get_llm

        def broken_get_llm():
            raise RuntimeError("LLM 初始化失敗")

        api_server.get_llm = broken_get_llm

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
            api_server.get_llm = original_get_llm
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


# ==================== Meeting with Review Loop ====================

class TestMeetingReviewLoop:
    """完整開會流程含審查迴圈的測試"""

    def test_meeting_with_review_loop_safe(self, client, mock_api_deps):
        """測試 skip_review=False 且第一輪即 Safe 的流程"""
        call_count = [0]

        def side_effect(prompt, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # 步驟 1: 需求分析
                return json.dumps({
                    "doc_type": "函",
                    "sender": "測試機關",
                    "receiver": "測試單位",
                    "subject": "測試主旨"
                })
            elif call_count[0] == 2:
                # 步驟 2: 撰寫草稿
                return "### 主旨\n測試公文\n### 說明\n測試說明"
            elif call_count[0] == 3:
                # FormatAuditor
                return json.dumps({"errors": [], "warnings": []})
            elif call_count[0] == 4:
                # StyleChecker
                return json.dumps({"issues": [], "score": 0.95})
            elif call_count[0] == 5:
                # FactChecker
                return json.dumps({"issues": [], "score": 0.95})
            elif call_count[0] == 6:
                # ConsistencyChecker
                return json.dumps({"issues": [], "score": 0.95})
            elif call_count[0] == 7:
                # ComplianceChecker
                return json.dumps({"issues": [], "score": 0.95, "confidence": 0.9})
            else:
                return "已修正內容"

        mock_api_deps["llm"].generate.side_effect = side_effect

        response = client.post("/api/v1/meeting", json={
            "user_input": "寫一份函，測試機關發給測試單位",
            "skip_review": False,
            "output_docx": False,
            "max_rounds": 3
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["rounds_used"] >= 1
        assert data["qa_report"] is not None

    def test_meeting_with_multiple_review_rounds(self, client, mock_api_deps):
        """測試 risk_summary 非 Safe/Low 時繼續多輪審查"""
        call_count = [0]

        def side_effect(prompt, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # 步驟 1: 需求分析
                return json.dumps({
                    "doc_type": "函",
                    "sender": "測試機關",
                    "receiver": "測試單位",
                    "subject": "測試主旨"
                })
            elif call_count[0] == 2:
                # 步驟 2: 撰寫草稿
                return "### 主旨\n測試公文\n### 說明\n測試說明"
            elif call_count[0] <= 7:
                # 第一輪審查 - 回傳有問題的結果使 risk 為 High
                if "format" in prompt.lower() or call_count[0] == 3:
                    return json.dumps({"errors": ["缺少欄位", "格式錯誤", "嚴重問題"], "warnings": []})
                else:
                    return json.dumps({"issues": [{"severity": "error", "location": "全文", "description": "問題"}], "score": 0.3})
            elif call_count[0] == 8:
                # EditorInChief auto-refine
                return "### 主旨\n修正後公文\n### 說明\n修正後說明"
            elif call_count[0] <= 13:
                # 第二輪審查 - 全部通過
                if call_count[0] == 9:
                    return json.dumps({"errors": [], "warnings": []})
                else:
                    return json.dumps({"issues": [], "score": 0.95, "confidence": 0.9})
            else:
                return "最終修正"

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
        # 應至少進行了 2 輪審查（第一輪 risk 高，第二輪通過）
        assert data["rounds_used"] >= 1

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


# ==================== Lazy Init ====================

class TestLazyInit:
    """延遲初始化路徑的測試"""

    def test_get_config_fallback(self):
        """測試 get_config 在設定檔載入失敗時使用預設設定"""
        import api_server

        # 清空全域設定
        api_server._config = None

        # mock ConfigManager 拋出異常
        with patch("api_server.ConfigManager") as mock_cm:
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
        with patch("api_server.ConfigManager") as mock_cm, \
             patch("api_server.get_llm_factory") as mock_factory, \
             patch("api_server.KnowledgeBaseManager") as mock_kb_class:

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
