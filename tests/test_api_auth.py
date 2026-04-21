"""API client auth tests for route-level Bearer protection."""

import pytest

pytest.importorskip("multipart", reason="python-multipart 未安裝，跳過 API 測試")

from fastapi.testclient import TestClient

from conftest import make_api_config, make_mock_kb, make_mock_llm


@pytest.fixture(autouse=True)
def reset_api_auth_globals():
    import api_server
    import src.api.auth as api_auth

    api_server._config = None
    api_server._llm = None
    api_server._kb = None
    api_server._org_memory = None
    api_auth._dev_mode_warned = False
    yield
    api_server._config = None
    api_server._llm = None
    api_server._kb = None
    api_server._org_memory = None
    api_auth._dev_mode_warned = False


def _build_client():
    import api_server

    api_server._config = make_api_config(api={"auth_enabled": False})
    api_server._llm = make_mock_llm()
    api_server._kb = make_mock_kb()

    from api_server import app

    return TestClient(app, raise_server_exceptions=False)


def test_write_endpoint_requires_bearer_when_env_key_set(monkeypatch):
    monkeypatch.setenv("API_CLIENT_KEY", "env-key-001")
    client = _build_client()

    response = client.post("/api/v1/agent/requirement", json={"user_input": "寫一份函，測試 auth"})

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_write_endpoint_rejects_wrong_bearer_key(monkeypatch):
    monkeypatch.setenv("API_CLIENT_KEY", "env-key-001")
    client = _build_client()

    response = client.post(
        "/api/v1/agent/requirement",
        json={"user_input": "寫一份函，測試錯 key"},
        headers={"Authorization": "Bearer wrong-key"},
    )

    assert response.status_code == 401


def test_write_endpoint_accepts_valid_bearer_key(monkeypatch):
    monkeypatch.setenv("API_CLIENT_KEY", "env-key-001")
    client = _build_client()

    response = client.post(
        "/api/v1/agent/requirement",
        json={"user_input": "寫一份函，測試對 key"},
        headers={"Authorization": "Bearer env-key-001"},
    )

    assert response.status_code == 200


def test_workflow_endpoint_requires_bearer_when_env_key_set(monkeypatch):
    monkeypatch.setenv("API_CLIENT_KEY", "env-key-001")
    client = _build_client()

    response = client.post(
        "/api/v1/meeting",
        json={"user_input": "請寫一份函", "skip_review": True, "output_docx": False},
    )

    assert response.status_code == 401


def test_knowledge_endpoint_requires_bearer_when_env_key_set(monkeypatch):
    monkeypatch.setenv("API_CLIENT_KEY", "env-key-001")
    client = _build_client()

    response = client.post("/api/v1/kb/search", json={"query": "資源回收"})

    assert response.status_code == 401


def test_write_endpoint_allows_dev_mode_when_env_key_missing(monkeypatch):
    monkeypatch.delenv("API_CLIENT_KEY", raising=False)
    client = _build_client()

    response = client.post("/api/v1/agent/requirement", json={"user_input": "寫一份函，dev mode"})

    assert response.status_code == 200


def test_health_endpoint_stays_public_with_env_key(monkeypatch):
    monkeypatch.setenv("API_CLIENT_KEY", "env-key-001")
    client = _build_client()

    response = client.get("/api/v1/health")

    assert response.status_code == 200
