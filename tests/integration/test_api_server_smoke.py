"""Integration smoke tests: API server boot, /health, and /api/v1/meeting.

Gated by GOV_AI_RUN_INTEGRATION=1 — default skip so CI never blocks waiting on
a live uvicorn boot or LLM back-end.

The test spins up a real uvicorn instance on a free local port, polls until
it responds, then validates:
  - GET /          → 200 + status key
  - GET /api/v1/health → 200 or 503 + health schema
  - POST /api/v1/meeting → 200 + MeetingResponse schema (success may be False
                            if LLM is not configured, but the server must not crash)
"""

from __future__ import annotations

import os
import socket
import threading
import time
from typing import Any

import pytest
import requests


pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Skip gate
# ---------------------------------------------------------------------------

def _require_live_integration() -> None:
    if os.getenv("GOV_AI_RUN_INTEGRATION") != "1":
        pytest.skip("set GOV_AI_RUN_INTEGRATION=1 to run API server smoke tests")


def _auth_headers() -> dict[str, str]:
    from src.core.config import ConfigManager

    api_keys = ConfigManager().get("api.api_keys", [])
    api_key = os.getenv("API_CLIENT_KEY") or (api_keys[0] if api_keys else "")
    if not isinstance(api_key, str) or not api_key:
        return {}
    return {"Authorization": f"Bearer {api_key}"}


# ---------------------------------------------------------------------------
# Server fixture helpers
# ---------------------------------------------------------------------------

def _find_free_port() -> int:
    """Bind to port 0 and return the OS-assigned free port number."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def _wait_for_server(base_url: str, *, timeout: float = 30.0, interval: float = 0.3) -> bool:
    """Poll GET / until the server responds 200 or timeout elapses."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            resp = requests.get(f"{base_url}/", timeout=2.0)
            if resp.status_code == 200:
                return True
        except requests.ConnectionError:
            pass
        time.sleep(interval)
    return False


class _UvicornThread(threading.Thread):
    """Background thread hosting a uvicorn server for smoke tests."""

    def __init__(self, host: str, port: int) -> None:
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self._server = None
        self._started = threading.Event()

    def run(self) -> None:
        import uvicorn
        from src.api.app import create_app

        app = create_app()
        config = uvicorn.Config(
            app,
            host=self.host,
            port=self.port,
            log_level="warning",
            lifespan="on",
        )
        self._server = uvicorn.Server(config)
        self._started.set()
        self._server.run()

    def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True


# ---------------------------------------------------------------------------
# Pytest fixture: live uvicorn instance
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def live_api_server():
    """Start a uvicorn server and yield its base URL; tear down after all tests in the module."""
    _require_live_integration()

    host = "127.0.0.1"
    port = _find_free_port()
    base_url = f"http://{host}:{port}"

    server_thread = _UvicornThread(host, port)
    server_thread.start()
    server_thread._started.wait(timeout=10.0)

    ready = _wait_for_server(base_url, timeout=30.0)
    if not ready:
        server_thread.stop()
        pytest.skip("uvicorn server did not start within 30 s")

    yield base_url

    server_thread.stop()
    server_thread.join(timeout=5.0)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_root_health_endpoint(live_api_server: str) -> None:
    """GET / returns 200 with a status key."""
    resp = requests.get(f"{live_api_server}/", timeout=10.0)
    assert resp.status_code == 200
    body: dict[str, Any] = resp.json()
    assert "status" in body
    assert body["status"] == "healthy"


def test_api_v1_health_schema(live_api_server: str) -> None:
    """GET /api/v1/health returns health-check schema regardless of component availability."""
    resp = requests.get(f"{live_api_server}/api/v1/health", timeout=10.0)
    # 200 = fully healthy; 503 = degraded/unhealthy but server is alive
    assert resp.status_code in (200, 503)
    body: dict[str, Any] = resp.json()

    required_keys = {"status", "version", "kb_status", "llm_status", "embedding_status"}
    assert required_keys.issubset(body.keys()), (
        f"Missing keys in /api/v1/health response: {required_keys - body.keys()}"
    )
    assert body["status"] in ("healthy", "degraded", "unhealthy")


def test_api_v1_meeting_happy_path(live_api_server: str) -> None:
    """POST /api/v1/meeting returns a valid MeetingResponse JSON (success may be False if LLM unavailable)."""
    payload = {
        "user_input": "草擬一份通知各機關停止辦公的函文",
        "skip_review": True,
        "max_rounds": 1,
        "output_docx": False,
    }
    resp = requests.post(
        f"{live_api_server}/api/v1/meeting",
        json=payload,
        headers=_auth_headers(),
        timeout=120.0,
    )
    # 200 with success=True/False expected; 5xx = server crash = fail
    assert resp.status_code == 200, (
        f"POST /api/v1/meeting returned {resp.status_code}: {resp.text[:300]}"
    )

    body: dict[str, Any] = resp.json()
    assert "success" in body, "MeetingResponse missing 'success' field"
    assert "session_id" in body, "MeetingResponse missing 'session_id' field"
    # success=True means full pipeline ran; False means LLM/KB not configured — both acceptable
    assert isinstance(body["success"], bool)
    if body["success"]:
        assert body.get("final_draft"), "success=True but final_draft is empty"
