# Contributing Guide

## 開發環境

```bash
pip install -r requirements.txt
python -m pytest tests/ -q --ignore=tests/integration
```

---

## Mock contract rules

> **Read before writing any `unittest.mock.patch` or `MagicMock` in this repo.**
> Three iceberg types cause slow, flaky, or silently-wrong tests; each has a
> canonical cure commit.

### Type 1 — Module local binding (`from src.X import Y`)

**Symptom:** `patch("src.A.real_func")` passes in isolation but fails when
`src.B` imports `real_func` once at module load time, creating a local
reference that the patch never reaches.

**Pattern to watch:**

```python
# src/api/routes/workflow/_endpoints.py  (before adb531c)
from src.api.dependencies import get_config  # bound at import time
...
# patch("src.api.dependencies.get_config")  # ← misses bound reference
```

**Fix:** patch the *module that uses* the name, not the module that defines it:

```python
# after adb531c / 6b41335
with patch("src.api.routes.workflow._endpoints.get_config", ...):
    ...
```

**Detection:** `python scripts/audit_local_binding.py --dry-run`

**Canonical commits:** `adb531c` (preflight get_config), `6b41335` (workflow get_llm/get_kb)

---

### Type 2 — External-service instantiation leaking HTTP (`_ensure_cache`)

**Symptom:** A test that exercises `EditorInChief` takes 40-120 s on a machine
without network because `LawVerifier._ensure_cache()` fires a real HTTP
request that exhausts all retries.

**Pattern to watch:**

```python
# src/knowledge/realtime_lookup.py
class LawVerifier:
    _cache: Optional[_LawCacheEntry] = None  # class-level singleton

    def _ensure_cache(self):
        if self._cache is None:   # ← if test doesn't pre-set, HTTP fires
            self._cache = _fetch_from_moj(...)
```

**Fix:** Pre-seed the class-level cache in `conftest.py` session fixture:

```python
# tests/conftest.py — _preload_empty_realtime_lookup_caches (c0933f9)
if LawVerifier._cache is None:
    LawVerifier._cache = _LawCacheEntry(data={})
```

**Canonical commit:** `c0933f9` (conftest preload empty realtime_lookup caches)

---

### Type 3 — Production code missing input-length guard (DoS vector)

**Symptom:** `test_search_very_long_string` takes 7-10 s because production
code passes a 10 000-character query verbatim to BM25 / vector search,
which is both a performance sink and a DoS vector.

**Pattern to watch:**

```python
# src/knowledge/_manager_hybrid.py  (before 1eef399)
def search_hybrid(self, query: str, ...):
    results = self._bm25_search(query)   # no length cap
    # 10 000-char BM25 query → seconds of CPU
```

**Fix:** Add an input cap at the top of the production function:

```python
# after 1eef399 — BM25 query cap 500 chars (DoS protection)
MAX_QUERY_LEN = 500
query = query[:MAX_QUERY_LEN]
```

**Canonical commit:** `1eef399` (BM25 query cap 500 chars)

---

### Global re-bind helper

Use `rebind_local(module, attr, target)` in `tests/conftest.py` to apply
the Type 1 fix without copy-pasting the pattern each time:

```python
from tests.conftest import rebind_local

def test_something(monkeypatch):
    rebind_local(monkeypatch, "src.api.routes.workflow._endpoints", "get_config", mock_cfg)
```

See `tests/conftest.py::rebind_local` docstring for full details.

---

## Conventional Commit

See `docs/commit-plan.md` for the full contract.  Short version:

```
<type>(<scope>): <subject ≥ 10 chars>
```

Allowed types: `feat fix refactor docs chore test perf style build ci revert`

Never use `auto-commit: checkpoint` — it will be rejected by
`scripts/commit_msg_lint.py`.

---

## Test guidelines

- New code **must** have pytest coverage.
- External HTTP in tests **must** be mocked (Type 2 iceberg rule).
- All patches **must** target the consuming module (Type 1 iceberg rule).
- Long-input paths in production code **should** be capped (Type 3 iceberg rule).

Run the full suite before submitting:

```bash
python -m pytest tests/ -q --ignore=tests/integration
```

### Live Recall Evaluation

The KB recall evaluator (`scripts/eval_recall.py`) requires a live KB to run
actual queries.  Unit tests in `tests/test_recall_eval.py` and
`tests/test_eval_recall.py` use mocks or `--dry-run` and run without any env
flag.

To run a full live recall evaluation (requires a populated KB):

```bash
GOV_AI_RUN_INTEGRATION=1 python scripts/eval_recall.py
```

### Pytest Runtime Baseline

The runtime regression guard (`scripts/measure_pytest_runtime.py`) records how
long the test suite takes and enforces a ratchet-down ceiling so regressions are
caught automatically.

**Quick start (dry-run — no actual pytest)**:

```bash
python scripts/measure_pytest_runtime.py --dry-run
```

**Full measurement with custom timeout**:

```bash
python scripts/measure_pytest_runtime.py --timeout 300
```

The script writes `scripts/pytest_runtime_baseline.json` with:

| Field | Meaning |
|---|---|
| `ceiling_s` | Ratchet-down ceiling (only improves, never worsens) |
| `last_s` | Most-recently measured elapsed time |
| `tolerance` | Allowed over-run fraction (default 0.20 = 20%) |
| `measured_at` | ISO-8601 timestamp of last measurement |

**Ratchet-down semantics**: if the new run is faster than the current ceiling,
`ceiling_s` is updated to `last_s × 1.5` (a fresh buffer).  If the run is
slower, `ceiling_s` stays unchanged — the ceiling can only improve, never
worsen.  When `last_s > ceiling_s × (1 + tolerance)`, `sensor_refresh.py`
fires a `pytest-runtime-regression` soft violation.

The `pytest_runtime` field appears in `python scripts/sensor_refresh.py --human`
output showing `ceiling_s`, `last_s`, and `status` (ok / violation / skip).

---

## Adapter Health

The adapter health probe (`scripts/adapter_health.py`) runs a quick dry-fetch
(limit=3) for each live source adapter and records per-adapter latency, record
count, and status.  This lets you detect silent stalls (adapters returning 0
records) without running a full `kb rebuild`.

**Quick start (dry-run — no live network calls)**:

```bash
python scripts/adapter_health.py --dry-run
```

**Human-readable summary**:

```bash
python scripts/adapter_health.py --human
```

Output format:

```
✅ mojlaw                    latency=  432ms  count=3
⚠️  fda_api                   latency=   50ms  count=0
❌ mohw_rss                  latency=   10ms  count=0 — connection timeout
```

**Icons:**

| Icon | Meaning |
|------|---------|
| ✅ | Adapter returned ≥1 record (`status=ok`) |
| ⚠️  | Adapter returned 0 records (`status=zero_records` or `dry_run`) |
| ❌ | Adapter raised an exception (`status=error`) |

The probe writes `scripts/adapter_health_report.json` which is loaded by
`sensor_refresh.py`.  When any adapter has `count=0` or `status=error`, a
**soft violation** (`adapter-health-stall`) is added to the sensor report.

**Adding a new adapter**: register it in `_ADAPTER_REGISTRY` inside
`scripts/adapter_health.py` — provide `(name, dotted_module_path, class_name)`.
Add a corresponding test case in `tests/test_adapter_health.py`.

---

## CLI Output Format

All primary commands support `--format {text,json}` (default: `text`).  JSON
mode emits a single-line JSON object to stdout — suitable for pipe / CI.

### `gov-ai stats --format json`

```json
{
  "total": 5,
  "success": 4,
  "failed": 1,
  "type_counts": {"函": 3, "公告": 2},
  "avg_score": 0.87
}
```

`avg_score` is `null` when no history records have a `score` field.

### `gov-ai status --format json`

```json
{
  "config": {"llm": {"provider": "openai", "model": "gpt-4"}},
  "history_count": 10,
  "feedback_count": 3,
  "kb_status": "ok"
}
```

`kb_status` is one of `ok | missing | error | unknown`.
`config` is `{}` when `config.yaml` is absent or unreadable.

### Common rules

| Rule | Detail |
|------|--------|
| Default | `text` (Rich terminal output) |
| JSON | `--format json`, plain stdout — pipe-friendly |
| Invalid format | exit 1 + 錯誤訊息 |
| Backward compat | `--format text` behaviour unchanged |

See `docs/cli-output-audit.md` for full field reference and output path details.
