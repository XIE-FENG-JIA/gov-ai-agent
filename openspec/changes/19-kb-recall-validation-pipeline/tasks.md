# Tasks — Epic 19: KB Recall Validation Pipeline

Status legend: `[ ]` pending · `[~]` in-progress · `[x]` done

---

## T19.1 — Create evaluation set

**Goal:** Build `kb_data/eval_set/recall_eval.jsonl` with ≥ 30 query–doc_id pairs
derived from public government documents already in the KB corpus.

- [x] Scan `kb_data/` for existing corpus doc IDs
- [x] Write 30+ pairs: `{"query": "...", "expected_doc_id": "..."}` in JSONL
- [x] Validate every `expected_doc_id` exists in the KB index
- [x] Acceptance: `wc -l kb_data/eval_set/recall_eval.jsonl` ≥ 30

---

## T19.2 — Implement `scripts/eval_recall.py`

**Goal:** Runnable script that loads the eval set, queries the KB, and computes
`recall@1`, `recall@3`, `recall@5`.

- [x] Accept `--k` flag (default 5); load `recall_eval.jsonl`
- [x] Call `knowledge_manager.search(query, k=k)` for each pair
- [x] Compute recall@k: fraction of queries where `expected_doc_id` in top-k
- [x] Write `recall_report.json`: `{"embedding_model": ..., "recall@1": ..., "recall@3": ..., "recall@5": ..., "n_eval": ...}`
- [x] Exit code 0 on success, 1 on any exception
- [x] Acceptance: `python scripts/eval_recall.py --dry-run` exits 0

---

## T19.3 — Recall baseline + ratchet

**Goal:** Store per-model recall baselines and ratchet the floor.

- [ ] Create `scripts/recall_baseline.json` with initial baselines from first run
- [ ] Add `save_recall_baseline(model, recall_at_5)` that ratchets floor down
- [ ] Add `read_recall_baseline(model)` → returns floor + `last_measured`
- [ ] Acceptance: unit test verifies ratchet semantics (baseline never increases)

---

## T19.4 — Sensor integration (soft violation)

**Goal:** Wire recall@5 into the sensor system so degradation triggers a soft violation.

- [ ] In `scripts/sensor_refresh.py`, add `check_recall_health(repo)` function
- [ ] Call `read_recall_baseline()` and compare to `recall_report.json` latest run
- [ ] Emit `"recall-degradation"` soft violation when `recall@5 < baseline * (1 - tolerance)`
- [ ] `tolerance` loaded from `recall_baseline.json` (default 0.10 = 10%)
- [ ] Acceptance: unit test with mocked baseline triggers soft violation at -11%

---

## T19.5 — Unit tests: `tests/test_recall_eval.py`

**Goal:** Full unit coverage without live KB.

- [ ] Mock `knowledge_manager.search` to return controlled results
- [ ] Test: perfect recall (all top-1 hits) → `recall@1 = 1.0`
- [ ] Test: miss at k=1, hit at k=3 → `recall@1 = 0.0, recall@3 > 0.0`
- [ ] Test: baseline ratchet (T19.3 logic)
- [ ] Test: soft violation trigger (T19.4 logic)
- [ ] Test: JSONL loader handles malformed lines without crash
- [ ] Acceptance: `pytest tests/test_recall_eval.py -q` = all passed, no live KB needed

---

## T19.6 — CI integration

**Goal:** Make `test_recall_eval.py` part of default `pytest` run.

- [ ] Ensure `tests/test_recall_eval.py` uses mock KB; no `GOV_AI_RUN_INTEGRATION` guard needed for unit tests
- [ ] Add integration marker `@pytest.mark.integration` to any live-KB tests
- [ ] Verify `pytest tests --ignore=tests/integration -q` is still green
- [ ] Update `CONTRIBUTING.md` with note about `GOV_AI_RUN_INTEGRATION=1` for live recall eval
- [ ] Acceptance: CI baseline run (no env vars) passes all tests
