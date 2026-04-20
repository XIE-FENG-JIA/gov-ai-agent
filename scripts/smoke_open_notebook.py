from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.integrations.open_notebook import probe_vendor_runtime
from src.integrations.open_notebook.config import get_open_notebook_vendor_path


@dataclass(frozen=True)
class SmokeReport:
    status: str
    message: str
    version: str = "?"
    origin: str = ""
    missing_modules: list[str] = field(default_factory=list)

    def to_line(self) -> str:
        parts = [f"status={self.status}", f"message={self.message}"]
        if self.version:
            parts.append(f"version={self.version}")
        if self.origin:
            parts.append(f"origin={self.origin}")
        if self.missing_modules:
            parts.append(f"missing={','.join(self.missing_modules)}")
        return " ".join(parts)


def _candidate_sys_paths(vendor_path: Path) -> list[str]:
    entries: list[str] = []
    for candidate in (vendor_path, vendor_path / "src"):
        if candidate.exists():
            entries.append(str(candidate))
    return entries


def smoke_import(vendor_path: Path | None = None) -> SmokeReport:
    resolved_path = vendor_path or get_open_notebook_vendor_path()
    is_ready, reason = probe_vendor_runtime(resolved_path)
    if not is_ready:
        status = "vendor-incomplete" if "vendor checkout is incomplete" in reason else "vendor-unready"
        return SmokeReport(status=status, message=reason)

    module_name = "open_notebook"
    candidate_entries = _candidate_sys_paths(resolved_path)
    original_module = sys.modules.pop(module_name, None)
    original_sys_path = list(sys.path)
    sys.path[:0] = candidate_entries
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        missing_modules = [exc.name] if getattr(exc, "name", None) else []
        return SmokeReport(
            status="import-error",
            message=f"{type(exc).__name__}: {exc}",
            missing_modules=missing_modules,
        )
    finally:
        sys.path[:] = original_sys_path
        sys.modules.pop(module_name, None)
        if original_module is not None:
            sys.modules[module_name] = original_module

    return SmokeReport(
        status="ok",
        message="imported open_notebook successfully",
        version=str(getattr(module, "__version__", "?")),
        origin=str(getattr(module, "__file__", "")),
    )


def main(argv: Sequence[str] | None = None) -> int:
    _ = argv
    report = smoke_import()
    print(report.to_line())
    return 0 if report.status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
