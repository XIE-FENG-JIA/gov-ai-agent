# Test Mock Iceberg Taxonomy — Type 1 / 2 / 3

> This document maps sensor-observable symptoms to their root-cause iceberg
> type, shows a minimal before/after diff, and links the canonical cure commit.
> All three types have been observed in this repo; fixing them cut the total
> `pytest` cold-start runtime by **84 %** (960 s → 153 s).

---

## Type 1 — Module local binding (`from src.X import Y`)

### Observable symptom

A test patches `src.api.dependencies.get_config` but the production code under
test keeps returning the *real* config.  The patch "misses" even though it looks
correct.

Sensor: slow test or wrong result despite a seemingly correct `patch()` call.

### Root cause

When `src.B` does `from src.A import foo` at module level, Python binds `foo`
into `src.B`'s namespace.  A later `patch("src.A.foo")` replaces the reference
in `src.A` but **not** the copy already held by `src.B`.

```
src.A.foo  ────────── (original)
               ↑ patch here misses
src.B.foo  ────────── (copy made at import time)  ← production code uses this
```

### Pre-fix diff (adb531c)

```python
# tests/test_api_server.py  (before adb531c)
with patch("src.api.app.get_config", return_value=cfg):
    # ↑ patches src.api.app, but route handlers imported get_config
    # from src.api.dependencies at load time — patch never reaches them
    response = client.post("/v1/generate", ...)
```

### Post-fix diff

```python
# after adb531c
with patch("src.api.routes.generate.get_config", return_value=cfg):
    # ↑ patches the consuming module — now the route handler sees mock
    response = client.post("/v1/generate", ...)
```

### Second instance (6b41335)

```python
# tests/test_api_server.py  meeting_exporter path (before 6b41335)
# workflow _endpoints.py imported get_llm / get_kb at module level
# total runtime: 119.77 s (real LLM/KB init on every test)

# after 6b41335 — patch consuming module
with patch("src.api.routes.workflow._endpoints.get_llm", ...):
    ...
# total runtime: 2.53 s  (−117 s)
```

**Canonical commits:** `adb531c`, `6b41335`

**Detection tool:** `python scripts/audit_local_binding.py --dry-run`

---

## Type 2 — External-service instantiation leaking HTTP (`_ensure_cache`)

### Observable symptom

`TestEditorSafeLowNoRefine::test_safe_score_no_auto_refine` takes 44 s on
CI but < 1 s locally when the law endpoint happens to be cached.  Cold starts
or network-isolated runners always hit the slow path.

Sensor: test with `safe_score` / `verify_citations` in call stack timing > 10 s.

### Root cause

`LawVerifier` and `RecentPolicyFetcher` use a class-level `_cache = None`
singleton.  On first access they call `_ensure_cache()` which fires real HTTP
to `law.moj.gov.tw` / `www.ey.gov.tw`.  If the test doesn't pre-seed the
cache, every cold-start session hits the full retry stack (up to 42 s).

```
test_safe_score
  → EditorInChief.edit()
      → _citation_check()
          → LawVerifier._ensure_cache()  ← None → HTTP → 7× retry = 42 s
```

### Pre-fix diff

```python
# tests/conftest.py  (before c0933f9)
# No preload — LawVerifier._cache stays None until first test that imports it
```

### Post-fix diff (c0933f9)

```python
# tests/conftest.py  (after c0933f9)
@pytest.fixture(scope="session", autouse=True)
def _preload_empty_realtime_lookup_caches():
    """Pre-seed class-level caches so _ensure_cache() never fires HTTP."""
    from src.knowledge.realtime_lookup import (
        LawVerifier, RecentPolicyFetcher,
        _LawCacheEntry, _GazetteCacheEntry,
    )
    if LawVerifier._cache is None:
        LawVerifier._cache = _LawCacheEntry(data={})
    if RecentPolicyFetcher._cache is None:
        RecentPolicyFetcher._cache = _GazetteCacheEntry(records=[])
    yield
# Result: test_safe_score 44 s → 0.11 s
```

**Canonical commit:** `c0933f9`

---

## Type 3 — Production code missing input-length guard (DoS vector)

### Observable symptom

`TestKBEdgeCases::test_search_very_long_string` passes a 10 000-character
query and takes 7.95 s.  The same code path is reachable via the HTTP API,
making it a live DoS vector.

Sensor: any test constructing an unusually long string (> 500 chars) and
exercising a search / similarity / BM25 path that takes > 2 s.

### Root cause

BM25 tokenization is super-linear in input length.  Without a cap the 10 000-
character query is tokenized in full, pegging a CPU core for several seconds.
Vector similarity is not as bad but also degrades.

```python
# src/knowledge/_manager_hybrid.py  (before 1eef399)
def search_hybrid(self, query: str, n_results: int = 5):
    bm25_hits = self._bm25.get_scores(query.split())  # ← no length cap
    # 10 000-char query → BM25 tokenizes ~2000 tokens → 7.95 s
```

### Post-fix diff (1eef399)

```python
# after 1eef399 — BM25 query cap 500 chars (DoS protection)
_MAX_QUERY_LEN = 500

def search_hybrid(self, query: str, n_results: int = 5):
    query = query[:_MAX_QUERY_LEN]          # ← cap before any heavy work
    bm25_hits = self._bm25.get_scores(query.split())
    # same test: 7.95 s → 1.00 s
```

**Canonical commit:** `1eef399`

---

## Summary table

| Type | Root cause | Sensor signal | Cure strategy | Canonical commit |
|------|-----------|---------------|---------------|-----------------|
| 1 | Module local binding (`from X import Y` at module level) | Test passes in isolation, fails in suite; patch "misses" | Patch consuming module, not defining module | `adb531c`, `6b41335` |
| 2 | External service class-level cache not pre-seeded | Slow cold-start test (> 10 s) with network call in stack | Pre-seed `_cache` in session-autouse conftest fixture | `c0933f9` |
| 3 | No input-length cap in production search path | Slow test with oversized input string (> 500 chars) | Add `query = query[:MAX]` at function entry | `1eef399` |

---

## Audit tool

```bash
# List Type 1 candidates in the repo
python scripts/audit_local_binding.py --dry-run

# Check a specific module
python scripts/audit_local_binding.py --module src/api/routes/workflow/_endpoints.py
```

See `scripts/audit_local_binding.py` and `CONTRIBUTING.md` for full usage.
