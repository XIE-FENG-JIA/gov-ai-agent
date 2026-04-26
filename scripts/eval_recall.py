#!/usr/bin/env python3
"""Evaluate KB retrieval recall@k on a held-out query set."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_EVAL_SET = ROOT / "kb_data" / "eval_set" / "recall_eval.jsonl"
DEFAULT_REPORT = ROOT / "recall_report.json"


@dataclass(frozen=True)
class RecallEvalPair:
    query: str
    expected_doc_id: str


def load_eval_set(path: Path) -> tuple[list[RecallEvalPair], list[str]]:
    pairs: list[RecallEvalPair] = []
    errors: list[str] = []
    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_no}: malformed JSON ({exc.msg})")
            continue

        query = row.get("query")
        expected_doc_id = row.get("expected_doc_id")
        if not isinstance(query, str) or not query.strip():
            errors.append(f"line {line_no}: missing query")
            continue
        if not isinstance(expected_doc_id, str) or not expected_doc_id.strip():
            errors.append(f"line {line_no}: missing expected_doc_id")
            continue
        pairs.append(RecallEvalPair(query=query.strip(), expected_doc_id=expected_doc_id.strip()))
    return pairs, errors


def _result_doc_ids(result: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    result_id = result.get("id")
    if result_id is not None:
        ids.add(str(result_id))
    metadata = result.get("metadata")
    if isinstance(metadata, dict):
        for key in ("doc_id", "document_id", "source_id", "id"):
            value = metadata.get(key)
            if value is not None:
                ids.add(str(value))
    return ids


def search_kb(kb: Any, query: str, k: int) -> list[dict[str, Any]]:
    if hasattr(kb, "search"):
        return list(kb.search(query, k=k))
    return list(kb.search_hybrid(query, n_results=k))


def compute_recall(
    pairs: list[RecallEvalPair],
    search_fn: Any,
    max_k: int,
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    hits = {1: 0, 3: 0, 5: 0}
    rows: list[dict[str, Any]] = []
    for pair in pairs:
        results = search_fn(pair.query, max_k)
        retrieved_ids = [_result_doc_ids(result) for result in results[:max_k]]
        hit_ranks = [idx + 1 for idx, ids in enumerate(retrieved_ids) if pair.expected_doc_id in ids]
        first_hit = hit_ranks[0] if hit_ranks else None
        for k in hits:
            if k <= max_k and first_hit is not None and first_hit <= k:
                hits[k] += 1
        rows.append(
            {
                "query": pair.query,
                "expected_doc_id": pair.expected_doc_id,
                "hit_rank": first_hit,
                "top_ids": [sorted(ids)[0] if ids else None for ids in retrieved_ids],
            }
        )

    total = len(pairs) or 1
    return {f"recall@{k}": hits[k] / total for k in hits}, rows


def _load_kb_and_model() -> tuple[Any, str]:
    from src.core.config import ConfigManager
    from src.core.llm import get_llm_factory
    from src.knowledge import KnowledgeBaseManager

    config = ConfigManager().config
    llm_config = config.get("llm") or {}
    if not llm_config:
        raise RuntimeError("config.yaml missing llm section")
    llm = get_llm_factory(llm_config, full_config=config)
    kb_path = config.get("knowledge_base", {}).get("path", "./kb_data")
    contextual_retrieval = bool(config.get("knowledge_base", {}).get("contextual_retrieval", False))
    kb = KnowledgeBaseManager(kb_path, llm, contextual_retrieval=contextual_retrieval)
    embedding_model = getattr(llm, "emb_model", None) or llm_config.get("embedding_model") or "unknown"
    return kb, str(embedding_model)


def build_report(
    *,
    eval_path: Path,
    max_k: int,
    dry_run: bool,
) -> dict[str, Any]:
    pairs, load_errors = load_eval_set(eval_path)
    if not pairs:
        raise RuntimeError(f"no valid eval pairs in {eval_path}")

    if dry_run:
        metrics = {"recall@1": None, "recall@3": None, "recall@5": None}
        details: list[dict[str, Any]] = []
        embedding_model = "dry-run"
    else:
        kb, embedding_model = _load_kb_and_model()
        metrics, details = compute_recall(pairs, lambda query, k: search_kb(kb, query, k), max_k)

    return {
        "embedding_model": embedding_model,
        **metrics,
        "n_eval": len(pairs),
        "max_k": max_k,
        "eval_set": str(eval_path),
        "load_errors": load_errors,
        "details": details,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate KB recall@k")
    parser.add_argument("--eval-set", type=Path, default=DEFAULT_EVAL_SET)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs without querying the KB")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.k < 1:
            raise ValueError("--k must be >= 1")
        report = build_report(eval_path=args.eval_set, max_k=args.k, dry_run=args.dry_run)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"recall report written: {args.output}")
        return 0
    except Exception as exc:
        print(f"eval_recall failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
