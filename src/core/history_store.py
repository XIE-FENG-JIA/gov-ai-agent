"""Core history record persistence."""

from __future__ import annotations

from datetime import datetime

from src.cli.utils_io import JSONStore

_MAX_HISTORY = 100
_history_store = JSONStore(".gov-ai-history.json", default=[])


def append_record(
    input_text: str,
    doc_type: str,
    output_path: str,
    score: float | None = None,
    risk: str | None = None,
    rounds_used: int | None = None,
    elapsed: float | None = None,
    status: str = "success",
) -> None:
    """Append one history record."""
    record = {
        "timestamp": datetime.now().isoformat(),
        "input": input_text[:200],
        "doc_type": doc_type,
        "output": output_path,
        "score": score,
        "risk": risk,
        "rounds_used": rounds_used,
        "elapsed_sec": round(elapsed, 1) if elapsed else None,
        "status": status,
    }
    history = _history_store.load()
    history.append(record)
    if len(history) > _MAX_HISTORY:
        history = history[-_MAX_HISTORY:]

    try:
        _history_store.save(history)
    except OSError:
        pass


__all__ = ["append_record", "_history_store"]
