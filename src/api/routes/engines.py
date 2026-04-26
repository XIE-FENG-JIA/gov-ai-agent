"""引擎清單 + 成本/quota 拉通 endpoint

L3 顶层設計：UI、CLI、auto-engineer 全部從這個 endpoint 讀引擎清單。
改 engines.yaml 一處 → 立即經 ws 推到所有 client。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter()

ROOT = Path(__file__).resolve().parents[3]
ENGINES_YAML = ROOT / "config" / "engines.yaml"
PRICING_JSON = Path(os.environ.get(
    "GOVAI_PRICING_JSON",
    "D:/auto-dev/scripts/model-pricing.json",
))


def _load_engines() -> dict[str, Any]:
    if not ENGINES_YAML.exists():
        return {"_meta": {}, "engines": []}
    with ENGINES_YAML.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _load_pricing() -> dict[str, Any]:
    if not PRICING_JSON.exists():
        return {}
    try:
        with PRICING_JSON.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("pricing load failed: %s", e)
        return {}


def _staleness(pricing: dict[str, Any], warn_days: int) -> dict[str, Any]:
    updated = pricing.get("_updated")
    if not updated:
        return {"stale": False, "days_since_update": None, "updated": None}
    try:
        last = datetime.fromisoformat(updated)
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - last).days
    except (TypeError, ValueError):
        return {"stale": False, "days_since_update": None, "updated": updated}
    return {
        "stale": age > warn_days,
        "days_since_update": age,
        "updated": updated,
        "next_review": pricing.get("_next_review"),
    }


def _quota_snapshot() -> dict[str, Any]:
    """從 auto-dev dashboard data.json 拉即時 quota（盡力，失敗給 None）。"""
    data_file = Path("D:/auto-dev/dashboard/data.json")
    if not data_file.exists():
        return {}
    try:
        with data_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
        cost = data.get("cost", {}) or {}
        engine = data.get("engine", {}) or {}
        return {
            "premium_left": cost.get("premium_left"),
            "usd_rolling7d": cost.get("usd"),
            "twd_rolling7d": cost.get("twd"),
            "cache_hit_pct": cost.get("cache_hit_pct"),
            "current_engine_model": engine.get("model"),
            "current_round": engine.get("round"),
            "ts": cost.get("ts"),
        }
    except (OSError, json.JSONDecodeError, AttributeError) as e:
        logger.warning("quota snapshot failed: %s", e)
        return {}


def _enrich(engine: dict[str, Any], pricing: dict[str, Any]) -> dict[str, Any]:
    out = dict(engine)
    ref = engine.get("pricing_ref")
    if ref and ref in pricing and isinstance(pricing[ref], dict):
        p = pricing[ref]
        out["pricing"] = {
            "input": p.get("input"),
            "cached_read": p.get("cached_read"),
            "output": p.get("output"),
            "note": p.get("_note"),
        }
    else:
        out["pricing"] = None
    return out


def _build_payload() -> dict[str, Any]:
    cfg = _load_engines()
    pricing = _load_pricing()
    meta = cfg.get("_meta", {}) or {}
    warn_days = int(meta.get("stale_warn_days", 14))
    engines = [_enrich(e, pricing) for e in (cfg.get("engines") or [])]
    return {
        "engines": engines,
        "meta": meta,
        "pricing_meta": _staleness(pricing, warn_days),
        "quota": _quota_snapshot(),
        "ts": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/v1/engines", tags=["引擎"])
async def list_engines() -> JSONResponse:
    """列出所有引擎 + 即時 pricing/quota/stale 狀態。"""
    return JSONResponse(_build_payload())


@router.get("/api/v1/engines/{engine_id}", tags=["引擎"])
async def get_engine(engine_id: str) -> JSONResponse:
    payload = _build_payload()
    for e in payload["engines"]:
        if e.get("id") == engine_id:
            return JSONResponse({
                "engine": e,
                "pricing_meta": payload["pricing_meta"],
                "quota": payload["quota"],
                "ts": payload["ts"],
            })
    return JSONResponse({"error": "not found", "engine_id": engine_id}, status_code=404)


@router.websocket("/api/v1/engines/ws")
async def engines_ws(ws: WebSocket) -> None:
    """每 30s 推一次最新 payload；engines.yaml mtime 改動立即觸發推送。"""
    await ws.accept()
    last_mtime = ENGINES_YAML.stat().st_mtime if ENGINES_YAML.exists() else 0.0
    last_pricing_mtime = PRICING_JSON.stat().st_mtime if PRICING_JSON.exists() else 0.0
    try:
        await ws.send_json({"type": "init", **_build_payload()})
        while True:
            await asyncio.sleep(5)
            mtime = ENGINES_YAML.stat().st_mtime if ENGINES_YAML.exists() else 0.0
            pmtime = PRICING_JSON.stat().st_mtime if PRICING_JSON.exists() else 0.0
            changed = mtime != last_mtime or pmtime != last_pricing_mtime
            if changed:
                last_mtime, last_pricing_mtime = mtime, pmtime
                await ws.send_json({"type": "config_changed", **_build_payload()})
            else:
                # 30s tick 推 quota（每 6 次 sleep 5s）
                await ws.send_json({"type": "quota_tick", "quota": _quota_snapshot(),
                                    "pricing_meta": _staleness(_load_pricing(),
                                                               int(_load_engines().get("_meta", {}).get("stale_warn_days", 14))),
                                    "ts": datetime.now(timezone.utc).isoformat()})
    except WebSocketDisconnect:
        return
    except (OSError, RuntimeError, ValueError) as e:
        logger.warning("engines_ws error: %s", e)
        try:
            await ws.close()
        except RuntimeError:
            pass
