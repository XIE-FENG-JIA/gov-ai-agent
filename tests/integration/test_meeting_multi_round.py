"""Integration tests: meeting API multi-round interaction.

Gated by GOV_AI_RUN_INTEGRATION=1 — default skip.
Tests the /api/v1/meeting endpoint with multiple scenarios:
  - happy path (standard draft request)
  - boundary: empty user_input returns structured error
  - boundary: oversized input is handled gracefully
  - multi-round: two sequential requests share no cross-session state
Uses the live_api_server fixture from test_api_server_smoke (module-level scope).
"""

from __future__ import annotations

import os
import socket
import threading
import time
from typing import Any

import pytest


pytestmark = pytest.mark.integration


def _require_live_integration() -> None:
    if os.getenv("GOV_AI_RUN_INTEGRATION") != "1":
        pytest.skip("set GOV_AI_RUN_INTEGRATION=1 to run meeting API multi-round tests")


def _auth_headers() -> dict[str, str]:
    from src.core.config import ConfigManager

    api_keys = ConfigManager().get("api.api_keys", [])
    api_key = os.getenv("API_CLIENT_KEY") or (api_keys[0] if api_keys else "")
    if not isinstance(api_key, str) or not api_key:
        return {}
    return {"Authorization": f"Bearer {api_key}"}


# ---------------------------------------------------------------------------
# Server fixture (same pattern as test_api_server_smoke)
# ---------------------------------------------------------------------------

def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def _wait_for_server(base_url: str, *, timeout: float = 30.0, interval: float = 0.3) -> bool:
    import requests as _req
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            resp = _req.get(f"{base_url}/", timeout=2.0)
            if resp.status_code == 200:
                return True
        except _req.ConnectionError:
            pass
        time.sleep(interval)
    return False


class _UvicornThread(threading.Thread):
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
        config = uvicorn.Config(app, host=self.host, port=self.port,
                                log_level="warning", lifespan="on")
        self._server = uvicorn.Server(config)
        self._started.set()
        self._server.run()

    def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True


@pytest.fixture(scope="module")
def meeting_api_server():
    """Start a dedicated uvicorn server for meeting multi-round tests."""
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
# Happy path
# ---------------------------------------------------------------------------

def test_meeting_happy_path_returns_session_id(meeting_api_server: str) -> None:
    """POST /api/v1/meeting with valid input returns session_id."""
    import requests

    resp = requests.post(
        f"{meeting_api_server}/api/v1/meeting",
        json={
            "user_input": "草擬一份關於年度預算審查的開會通知單",
            "skip_review": True,
            "max_rounds": 1,
            "output_docx": False,
        },
        headers=_auth_headers(),
        timeout=120.0,
    )
    assert resp.status_code == 200, f"meeting happy path: {resp.status_code} {resp.text[:300]}"
    body: dict[str, Any] = resp.json()
    assert "success" in body, "MeetingResponse missing 'success'"
    assert "session_id" in body, "MeetingResponse missing 'session_id'"
    assert isinstance(body["session_id"], str) and body["session_id"]


def test_meeting_two_requests_get_different_session_ids(meeting_api_server: str) -> None:
    """Two independent meeting requests must receive distinct session_ids."""
    import requests

    payload = {
        "user_input": "草擬函文通知各機關配合停電演習",
        "skip_review": True,
        "max_rounds": 1,
        "output_docx": False,
    }

    resp1 = requests.post(
        f"{meeting_api_server}/api/v1/meeting",
        json=payload,
        headers=_auth_headers(),
        timeout=120.0,
    )
    resp2 = requests.post(
        f"{meeting_api_server}/api/v1/meeting",
        json=payload,
        headers=_auth_headers(),
        timeout=120.0,
    )

    assert resp1.status_code == 200
    assert resp2.status_code == 200

    sid1 = resp1.json().get("session_id", "")
    sid2 = resp2.json().get("session_id", "")

    assert sid1 != sid2, (
        f"Two independent meeting requests returned the same session_id={sid1!r}"
    )


# ---------------------------------------------------------------------------
# Boundary: empty input
# ---------------------------------------------------------------------------

def test_meeting_empty_user_input_returns_error_or_400(meeting_api_server: str) -> None:
    """POST /api/v1/meeting with empty user_input must not crash (4xx or success=False)."""
    import requests

    resp = requests.post(
        f"{meeting_api_server}/api/v1/meeting",
        json={"user_input": "", "skip_review": True, "max_rounds": 1, "output_docx": False},
        headers=_auth_headers(),
        timeout=30.0,
    )
    # Server must not crash (5xx)
    assert resp.status_code < 500, (
        f"Meeting API crashed on empty input: {resp.status_code} {resp.text[:300]}"
    )
    if resp.status_code == 200:
        body = resp.json()
        # If 200, success must be False or an error must be present
        assert body.get("success") is False or "error" in body, (
            "Meeting API returned success=True for empty user_input — unexpected"
        )


# ---------------------------------------------------------------------------
# Boundary: oversized input
# ---------------------------------------------------------------------------

def test_meeting_oversized_input_handled_gracefully(meeting_api_server: str) -> None:
    """POST /api/v1/meeting with very long input must return 4xx or 200 without crash."""
    import requests
    from src.core.constants import MAX_USER_INPUT_LENGTH

    oversized = "草" * (MAX_USER_INPUT_LENGTH + 500)
    resp = requests.post(
        f"{meeting_api_server}/api/v1/meeting",
        json={"user_input": oversized, "skip_review": True, "max_rounds": 1, "output_docx": False},
        headers=_auth_headers(),
        timeout=30.0,
    )
    assert resp.status_code < 500, (
        f"Meeting API crashed on oversized input: {resp.status_code} {resp.text[:300]}"
    )
