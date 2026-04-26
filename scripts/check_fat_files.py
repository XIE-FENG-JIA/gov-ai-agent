#!/usr/bin/env python3
"""Fat-file ratchet gate — 防止胖檔新增.

規則:
  1. 任何 src/ Python 檔 ≥ 400 行 → exit 1 (hard)
  2. --strict: yellow (350-399) 檔數不得超過 baseline_max，且 max_lines 不得增加 (ratchet)

用法:
  python scripts/check_fat_files.py                  # 只檢查 red (≥400)
  python scripts/check_fat_files.py --strict          # 檢查 red + yellow ratchet
  python scripts/check_fat_files.py --update-baseline # 更新 baseline 並 exit 0
  python scripts/check_fat_files.py --watch-band 300-350 # 列出指定行數帶檔案，不阻斷
  python scripts/check_fat_files.py --json            # JSON 輸出到 stdout
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BASELINE_PATH = _REPO_ROOT / "scripts" / "fat_baseline.json"
_RED_LIMIT = 400
_YELLOW_LOW = 350


def parse_watch_band(value: str) -> tuple[int, int]:
    """Parse LOW-HIGH watch band values for non-blocking line-count monitoring."""
    try:
        low_text, high_text = value.split("-", 1)
        low = int(low_text)
        high = int(high_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("watch band must use LOW-HIGH, e.g. 300-350") from exc
    if low < 1 or high < 1 or low > high:
        raise argparse.ArgumentTypeError("watch band must be positive and LOW <= HIGH")
    return low, high


def scan_fat_files(repo: Path) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """掃 src/ 下所有 .py 的行數，分 red (≥400) / yellow (350-399)."""
    src = repo / "src"
    if not src.exists():
        return [], []
    red: list[tuple[str, int]] = []
    yellow: list[tuple[str, int]] = []
    for py in src.rglob("*.py"):
        try:
            lines = len(py.read_text(encoding="utf-8", errors="replace").splitlines())
        except OSError:
            continue
        rel = py.relative_to(repo).as_posix()
        if lines >= _RED_LIMIT:
            red.append((rel, lines))
        elif _YELLOW_LOW <= lines < _RED_LIMIT:
            yellow.append((rel, lines))
    red.sort(key=lambda x: -x[1])
    yellow.sort(key=lambda x: -x[1])
    return red, yellow


def scan_line_band(repo: Path, low: int, high: int) -> list[tuple[str, int]]:
    """Return src/ Python files with line counts inside inclusive [low, high]."""
    src = repo / "src"
    if not src.exists():
        return []
    watched: list[tuple[str, int]] = []
    for py in src.rglob("*.py"):
        try:
            lines = len(py.read_text(encoding="utf-8", errors="replace").splitlines())
        except OSError:
            continue
        if low <= lines <= high:
            watched.append((py.relative_to(repo).as_posix(), lines))
    watched.sort(key=lambda x: (-x[1], x[0]))
    return watched


def load_baseline() -> dict:
    """讀取 fat_baseline.json；不存在時回傳空基線."""
    if _BASELINE_PATH.exists():
        try:
            return json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {"yellow_count_max": 0, "yellow_max_lines": 0, "yellow_files": []}


def save_baseline(yellow: list[tuple[str, int]]) -> None:
    """寫入當前 yellow 清單作為 ratchet 基線."""
    data = {
        "yellow_count_max": len(yellow),
        "yellow_max_lines": yellow[0][1] if yellow else 0,
        "yellow_files": [{"path": p, "lines": n} for p, n in yellow],
    }
    _BASELINE_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"[fat-gate] baseline saved → {_BASELINE_PATH.name} "
        f"({len(yellow)} yellow files, max {data['yellow_max_lines']} lines)",
        file=sys.stderr,
    )


def build_report(
    repo: Path,
    baseline: dict,
    *,
    strict: bool,
    watch_band: tuple[int, int] | None = None,
) -> dict:
    red, yellow = scan_fat_files(repo)
    result: dict = {
        "red": [{"path": p, "lines": n} for p, n in red],
        "yellow": [{"path": p, "lines": n} for p, n in yellow],
        "baseline_yellow_count_max": baseline.get("yellow_count_max", 0),
        "baseline_yellow_max_lines": baseline.get("yellow_max_lines", 0),
        "violations": [],
    }

    if watch_band is not None:
        low, high = watch_band
        watched = scan_line_band(repo, low, high)
        result["watch_band"] = {"low": low, "high": high}
        result["watch"] = [{"path": p, "lines": n} for p, n in watched]

    for path, lines in red:
        result["violations"].append(f"RED {path}: {lines} lines ≥ {_RED_LIMIT}")

    if strict:
        baseline_count = baseline.get("yellow_count_max", 0)
        baseline_max = baseline.get("yellow_max_lines", 0)
        cur_count = len(yellow)
        cur_max = yellow[0][1] if yellow else 0

        if cur_count > baseline_count:
            result["violations"].append(
                f"yellow count {cur_count} > baseline {baseline_count} (new yellow file added)"
            )
        if baseline_max > 0 and cur_max > baseline_max:
            result["violations"].append(
                f"yellow max_lines {cur_max} > baseline {baseline_max} (existing yellow file grew)"
            )
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fat-file ratchet gate for src/ Python files")
    parser.add_argument("--strict", action="store_true", help="Also enforce yellow ratchet (count + max_lines)")
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Write current state as new baseline, then exit 0",
    )
    parser.add_argument("--json", dest="output_json", action="store_true", help="Output JSON report to stdout")
    parser.add_argument(
        "--watch-band",
        type=parse_watch_band,
        metavar="LOW-HIGH",
        help="Print non-blocking src/ Python files within inclusive line-count band",
    )
    args = parser.parse_args(argv)

    red, yellow = scan_fat_files(_REPO_ROOT)
    baseline = load_baseline()

    if args.update_baseline:
        save_baseline(yellow)
        result = build_report(_REPO_ROOT, baseline, strict=args.strict, watch_band=args.watch_band)
        if args.output_json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    result = build_report(_REPO_ROOT, baseline, strict=args.strict, watch_band=args.watch_band)

    if args.output_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))

    if result["violations"]:
        for v in result["violations"]:
            print(f"[fat-gate] FAIL: {v}", file=sys.stderr)
        return 1

    if args.watch_band:
        low, high = args.watch_band
        watch = result.get("watch", [])
        print(f"[fat-gate] WATCH {low}-{high}: {len(watch)} files", file=sys.stderr)
        for item in watch:
            print(f"[fat-gate] WATCH: {item['path']} {item['lines']} lines", file=sys.stderr)

    print(
        f"[fat-gate] OK: red={len(red)} yellow={len(yellow)}"
        f" (baseline count={baseline.get('yellow_count_max', 0)}"
        f" max_lines={baseline.get('yellow_max_lines', 0)})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
