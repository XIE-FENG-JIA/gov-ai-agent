"""Integration tests: web_preview render smoke.

Gated by GOV_AI_RUN_INTEGRATION=1 — default skip.
Boots the web_preview FastAPI app via httpx AsyncClient (in-process, no real
network required) and asserts that the root path renders an HTML response
containing the expected UI elements (form, submit button, doc_type select).
"""

from __future__ import annotations

import os

import pytest


pytestmark = pytest.mark.integration


def _require_live_integration() -> None:
    if os.getenv("GOV_AI_RUN_INTEGRATION") != "1":
        pytest.skip("set GOV_AI_RUN_INTEGRATION=1 to run web_preview smoke tests")


# ---------------------------------------------------------------------------
# Smoke tests against the in-process web_app
# ---------------------------------------------------------------------------

def test_web_preview_root_returns_html() -> None:
    """GET / on web_preview app returns 200 with text/html content type."""
    _require_live_integration()

    from fastapi.testclient import TestClient
    from src.web_preview.app import web_app

    client = TestClient(web_app, raise_server_exceptions=False)
    response = client.get("/")
    assert response.status_code == 200, (
        f"web_preview GET / returned {response.status_code}: {response.text[:300]}"
    )
    content_type = response.headers.get("content-type", "")
    assert "text/html" in content_type, (
        f"Expected text/html content-type, got: {content_type!r}"
    )


def test_web_preview_root_contains_form_element() -> None:
    """GET / HTML response must contain a <form> element (main rewrite form)."""
    _require_live_integration()

    from fastapi.testclient import TestClient
    from src.web_preview.app import web_app

    client = TestClient(web_app, raise_server_exceptions=False)
    response = client.get("/")
    assert response.status_code == 200
    body = response.text
    assert "<form" in body.lower(), (
        "web_preview root page missing <form> element — UI may not be rendered"
    )


def test_web_preview_root_contains_doc_type_select() -> None:
    """GET / HTML must include doc_type selector for 公文 types."""
    _require_live_integration()

    from fastapi.testclient import TestClient
    from src.web_preview.app import web_app

    client = TestClient(web_app, raise_server_exceptions=False)
    response = client.get("/")
    assert response.status_code == 200
    body = response.text
    # The page should contain some reference to doc_type or 公文類型
    has_doc_type = "doc_type" in body or "公文類型" in body or "文件類型" in body
    assert has_doc_type, (
        "web_preview root page missing doc_type or 公文類型 selector — "
        f"page head: {body[:500]!r}"
    )


def test_web_preview_static_files_accessible() -> None:
    """Static assets mounted at /static should return a non-404 for at least one file."""
    _require_live_integration()

    from fastapi.testclient import TestClient
    from src.web_preview.app import web_app
    from pathlib import Path

    static_dir = Path("src/web_preview/static")
    if not static_dir.exists() or not any(static_dir.iterdir()):
        pytest.skip("No static files found in src/web_preview/static")

    # Pick any static file to check accessibility
    first_file = next(static_dir.rglob("*"), None)
    if first_file is None or not first_file.is_file():
        pytest.skip("No static files found under src/web_preview/static")

    rel_path = first_file.relative_to(static_dir)
    client = TestClient(web_app, raise_server_exceptions=False)
    resp = client.get(f"/static/{rel_path.as_posix()}")
    assert resp.status_code in (200, 304), (
        f"Static file /static/{rel_path} returned {resp.status_code}"
    )
