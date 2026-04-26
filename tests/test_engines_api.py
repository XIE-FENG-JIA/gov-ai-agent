from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from conftest import make_api_config
from src.api.app import create_app
import src.api.dependencies as dependencies
import src.api.routes.engines as engines


def test_engines_endpoint_enriches_pricing_and_quota(tmp_path, monkeypatch):
    engines_yaml = tmp_path / "engines.yaml"
    pricing_json = tmp_path / "pricing.json"
    quota_json = tmp_path / "quota.json"

    engines_yaml.write_text(
        """
_meta:
  stale_warn_days: 14
engines:
  - id: test
    display_name: Test Engine
    pricing_ref: test-model
""".strip(),
        encoding="utf-8",
    )
    pricing_json.write_text(
        json.dumps({"_updated": datetime.now(timezone.utc).isoformat(), "test-model": {"input": 1, "output": 2}}),
        encoding="utf-8",
    )
    quota_json.write_text(json.dumps({"cost": {"premium_left": 7}, "engine": {"model": "test-model"}}), encoding="utf-8")

    monkeypatch.setattr(engines, "ENGINES_YAML", engines_yaml)
    monkeypatch.setattr(engines, "PRICING_JSON", pricing_json)
    monkeypatch.setattr(engines, "_quota_snapshot", lambda: {"premium_left": 7})
    monkeypatch.setattr(dependencies, "_config", make_api_config())

    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.get("/api/v1/engines")

    assert response.status_code == 200
    data = response.json()
    assert data["engines"][0]["id"] == "test"
    assert data["engines"][0]["pricing"] == {"input": 1, "cached_read": None, "output": 2, "note": None}
    assert data["pricing_meta"]["stale"] is False
    assert data["quota"] == {"premium_left": 7}


def test_staleness_accepts_offset_aware_timestamp():
    pricing = {"_updated": "2026-04-26T12:00:00+00:00"}

    result = engines._staleness(pricing, warn_days=14)

    assert result["updated"] == "2026-04-26T12:00:00+00:00"
    assert isinstance(result["days_since_update"], int)
