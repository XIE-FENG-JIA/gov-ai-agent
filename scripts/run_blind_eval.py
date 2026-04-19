#!/usr/bin/env python3
"""執行 benchmark 盲測（以 API meeting 端點 + RALPH 嚴格模式）。"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DEFAULT_CORPUS_PATH = ROOT / "benchmark" / "mvp30_corpus.json"
DEFAULT_OUTPUT_PATH = ROOT / "benchmark" / "blind_eval_results.json"
DEFAULT_API_BASE = "http://127.0.0.1:8000"


def _load_default_auth_headers() -> dict[str, str]:
    try:
        from src.core.config import ConfigManager

        config = ConfigManager().config
        api_keys = config.get("api", {}).get("api_keys", [])
        if api_keys:
            return {"Authorization": f"Bearer {api_keys[0]}"}
    except Exception:
        pass
    return {}


def _extract_issue_stats(qa_report: dict[str, Any]) -> dict[str, Any]:
    severity = {"error": 0, "warning": 0, "info": 0}
    category: dict[str, int] = {}

    for agent in qa_report.get("agent_results", []) or []:
        issues = agent.get("issues", []) if isinstance(agent, dict) else []
        for issue in issues:
            sev = str(issue.get("severity", "")).lower()
            cat = str(issue.get("category", "")).lower()
            if sev in severity:
                severity[sev] += 1
            if cat:
                category[cat] = category.get(cat, 0) + 1

    return {
        "severity": severity,
        "category": category,
        "total": sum(severity.values()),
    }


def evaluate_item(
    client: httpx.Client,
    api_base: str,
    headers: dict[str, str],
    item: dict[str, Any],
    timeout: float,
) -> dict[str, Any]:
    payload = {"user_input": item["user_input"]}
    payload.update(item.get("strict_request", {}))

    started = time.perf_counter()
    try:
        response = client.post(
            f"{api_base}/api/v1/meeting",
            headers=headers,
            json=payload,
            timeout=timeout,
        )
        elapsed = round(time.perf_counter() - started, 3)
        data = response.json()
    except Exception as exc:
        return {
            "id": item["id"],
            "doc_type": item["doc_type"],
            "status_code": None,
            "success": False,
            "goal_met": False,
            "duration_sec": round(time.perf_counter() - started, 3),
            "score": None,
            "risk": None,
            "rounds_used": None,
            "error": str(exc),
            "error_code": None,
            "issue_stats": {"severity": {"error": 0, "warning": 0, "info": 0}, "category": {}, "total": 0},
        }

    qa_report = data.get("qa_report") or {}
    issue_stats = _extract_issue_stats(qa_report)
    score = qa_report.get("overall_score")
    risk = qa_report.get("risk_summary")
    rounds = data.get("rounds_used")
    target_score = payload.get("ralph_target_score", 1.0)
    goal_met = (
        data.get("success") is True
        and isinstance(score, (int, float))
        and score >= target_score
        and risk == "Safe"
        and issue_stats["total"] == 0
    )

    return {
        "id": item["id"],
        "doc_type": item["doc_type"],
        "status_code": response.status_code,
        "success": data.get("success") is True,
        "goal_met": goal_met,
        "duration_sec": elapsed,
        "score": score,
        "risk": risk,
        "rounds_used": rounds,
        "error": data.get("error"),
        "error_code": data.get("error_code"),
        "issue_stats": issue_stats,
    }


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    success_count = sum(1 for r in results if r["success"])
    goal_met_count = sum(1 for r in results if r["goal_met"])
    scores = [r["score"] for r in results if isinstance(r["score"], (int, float))]
    durations = [r["duration_sec"] for r in results if isinstance(r["duration_sec"], (int, float))]

    by_doc_type: dict[str, dict[str, Any]] = {}
    for r in results:
        slot = by_doc_type.setdefault(
            r["doc_type"],
            {"total": 0, "success": 0, "goal_met": 0, "avg_score": None},
        )
        slot["total"] += 1
        slot["success"] += int(bool(r["success"]))
        slot["goal_met"] += int(bool(r["goal_met"]))

    for doc_type, slot in by_doc_type.items():
        local_scores = [r["score"] for r in results if r["doc_type"] == doc_type and isinstance(r["score"], (int, float))]
        if local_scores:
            slot["avg_score"] = round(statistics.mean(local_scores), 4)

    issue_category_totals: dict[str, int] = {}
    for r in results:
        for cat, count in (r["issue_stats"].get("category") or {}).items():
            issue_category_totals[cat] = issue_category_totals.get(cat, 0) + int(count)

    top_issue_categories = sorted(
        issue_category_totals.items(),
        key=lambda kv: kv[1],
        reverse=True,
    )[:10]

    return {
        "total": total,
        "success_count": success_count,
        "success_rate": round(success_count / total, 4) if total else 0.0,
        "goal_met_count": goal_met_count,
        "goal_met_rate": round(goal_met_count / total, 4) if total else 0.0,
        "avg_score": round(statistics.mean(scores), 4) if scores else None,
        "median_duration_sec": round(statistics.median(durations), 3) if durations else None,
        "by_doc_type": by_doc_type,
        "top_issue_categories": [
            {"category": category, "count": count}
            for category, count in top_issue_categories
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="執行 benchmark 盲測（meeting API）")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--timeout", type=float, default=700.0)
    parser.add_argument("--limit", type=int, default=0, help="僅跑前 N 題（0=全部）")
    args = parser.parse_args()

    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    items: list[dict[str, Any]] = corpus.get("items", [])
    if args.limit > 0:
        items = items[: args.limit]

    headers = _load_default_auth_headers()
    results: list[dict[str, Any]] = []
    with httpx.Client(timeout=args.timeout) as client:
        for idx, item in enumerate(items, start=1):
            result = evaluate_item(
                client=client,
                api_base=args.api_base.rstrip("/"),
                headers=headers,
                item=item,
                timeout=args.timeout,
            )
            results.append(result)
            print(
                f"[{idx:02d}/{len(items):02d}] {item['id']} "
                f"success={result['success']} goal_met={result['goal_met']} "
                f"score={result['score']} risk={result['risk']} t={result['duration_sec']}s"
            )

    summary = summarize_results(results)
    payload = {
        "corpus": str(args.corpus),
        "api_base": args.api_base,
        "timeout_sec": args.timeout,
        "headers_used": bool(headers),
        "summary": summary,
        "results": results,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] 輸出盲測結果：{args.output}")
    print(
        f"[OK] success={summary['success_count']}/{summary['total']} "
        f"goal_met={summary['goal_met_count']}/{summary['total']} "
        f"avg_score={summary['avg_score']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
