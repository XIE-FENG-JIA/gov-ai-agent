#!/usr/bin/env python3
"""Recall baseline management with ratchet-down semantics.

Stores per-model recall@5 floor values.  The floor can only decrease
(ratchet down) — it never increases — ensuring the 'baseline never
increases' contract (T19.3).

Usage::

    from scripts.recall_baseline import save_recall_baseline, read_recall_baseline

    save_recall_baseline("my-model", 0.85)
    entry = read_recall_baseline("my-model")
    # {"floor": 0.85, "last_measured": 0.85, "tolerance": 0.10}
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path(__file__).resolve().parent / "recall_baseline.json"
DEFAULT_TOLERANCE = 0.10  # 10 % allowed degradation below floor before violation


def save_recall_baseline(
    model: str,
    recall_at_5: float,
    *,
    path: Path = DEFAULT_PATH,
    tolerance: float = DEFAULT_TOLERANCE,
) -> None:
    """Persist recall@5 baseline with ratchet-down semantics.

    The floor tracks the minimum observed recall and can only decrease
    (ratchet down), never increase.  This enforces the contract that
    *baseline never increases*.

    Args:
        model:        Embedding model identifier (matches recall_report.json).
        recall_at_5:  Measured recall@5 value (0.0–1.0).
        path:         JSON file path (default: scripts/recall_baseline.json).
        tolerance:    Allowed fractional degradation below floor (default 0.10).
    """
    data: dict[str, Any] = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}

    entry = data.get(str(model), {})
    current_floor = float(entry.get("floor", -1.0))
    # Ratchet-down: floor is initialised on first call, then can only decrease.
    new_floor = recall_at_5 if current_floor < 0 else min(current_floor, recall_at_5)

    data[str(model)] = {
        "floor": new_floor,
        "last_measured": recall_at_5,
        "tolerance": tolerance,
    }

    try:
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def read_recall_baseline(
    model: str,
    *,
    path: Path = DEFAULT_PATH,
) -> dict[str, Any]:
    """Read recall baseline entry for a model.

    Returns:
        dict with keys ``floor``, ``last_measured``, ``tolerance``, or
        empty dict if no entry exists for the model.
    """
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return dict(data.get(str(model), {}))
    except (OSError, json.JSONDecodeError):
        return {}
