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
