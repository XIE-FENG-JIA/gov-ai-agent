import json
from pathlib import Path

from src.cli.utils_io import resolve_state_read_path
from src.web_preview._helpers import (
    _WEB_UI_EXCEPTIONS,
    _log_web_warning,
    _sanitize_web_error,
)


def load_recent_history(project_root: Path, state_dir: str, limit: int = 100) -> tuple[list, str | None]:
    records = []
    error = None
    history_path = Path(
        resolve_state_read_path(
            ".gov-ai-history.json",
            cwd=str(project_root),
            state_dir=state_dir,
        ),
    )

    try:
        if history_path.exists():
            data = json.loads(history_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                records = list(reversed(data))[:limit]
    except _WEB_UI_EXCEPTIONS as exc:
        _log_web_warning("讀取歷史紀錄", exc)
        error = _sanitize_web_error(exc)
    return records, error
