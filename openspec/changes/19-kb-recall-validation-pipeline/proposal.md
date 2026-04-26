## Problem

The KB (knowledge base) rewrite pipeline consists of three stages — embed, cite,
rewrite — but currently has no quantitative validation of retrieval quality.
Specifically:

- `recall@k` (were the ground-truth docs retrieved in the top-k results?) is
  never measured; we don't know if embedding model changes regress recall.
- There are only ~400 corpus docs; T5.2/T5.3 (corpus 500 expansion + recall@k
  measurement) were frozen in v7.5 and never implemented.
- Engineers rely on manual inspection to judge "is the KB helping rewrites?" —
  no automated signal detects recall regression.

Concrete pain points:
- When we swap `embedding_model` in `config.yaml`, there is no test that verifies
  recall@k on a held-out evaluation set.
- The `cite` stage returns citations, but accuracy (did it find the right doc?)
  is only checked by spot-inspection.
- The `scripts/eval_quality.py` evaluates rewrite quality holistically but is
  blind to *why* a rewrite degrades (embed? cite? rewrite?).

## Solution

Introduce a **KB Recall Validation Pipeline** that adds automated recall@k
measurement as a first-class quality gate:

```
scripts/
  eval_recall.py          # run recall@k evaluation, emit JSON report
  recall_baseline.json    # recall@k baseline per embedding model/k

tests/
  test_recall_eval.py     # unit + integration tests for recall pipeline

kb_data/
  eval_set/               # held-out evaluation pairs (query → expected doc ids)
    recall_eval.jsonl     # 50 query–doc_id pairs from real public docs
```

The pipeline:
1. Loads `kb_data/eval_set/recall_eval.jsonl` (50 query-doc_id pairs).
2. For each query, calls `knowledge_manager.search(query, k=5)` and checks if
   the expected doc_id appears in results.
3. Computes `recall@1`, `recall@3`, `recall@5` and writes to `recall_report.json`.
4. `recall_baseline.json` stores the baseline per `embedding_model`; a sensor
   soft violation triggers when recall@5 drops below `baseline - tolerance`.
5. CI `pytest tests/test_recall_eval.py` uses a mocked KB for unit coverage;
   `GOV_AI_RUN_INTEGRATION=1` triggers live KB measurement.

## Non-Goals

- No corpus expansion to 500 docs in this epic (that is T5.2/T5.3 scope).
- No end-to-end rewrite quality scoring (that is `eval_quality.py` scope).
- No new embedding models; existing `config.yaml` `embedding_model` is tested.

## Acceptance Criteria

1. `kb_data/eval_set/recall_eval.jsonl` contains ≥ 30 evaluation pairs from
   public government documents already in the corpus.
2. `scripts/eval_recall.py` runs without error on a cold KB and produces
   `recall_report.json` with `recall@1`, `recall@3`, `recall@5` keys.
3. `scripts/recall_baseline.json` stores baseline values per embedding model.
4. Sensor soft violation triggered when `recall@5 < baseline * (1 - tolerance)`.
5. `tests/test_recall_eval.py` covers: loader, metric computation, baseline
   comparison, soft violation; all unit tests pass without live KB.
6. `python -m pytest tests/test_recall_eval.py -q` = all passed.
7. `python -m pytest tests --ignore=tests/integration -q` = full green (no regression).
