## Problem

Iterations across change 07's sibling hotfixes (`adb531c` preflight re-bind,
`6b41335` workflow local-binding, `c0933f9` realtime_lookup preload,
`1eef399` BM25 cap) confirmed three distinct "test misses production cost"
iceberg types are alive in the repo:

- **Type 1 — `from X import Y` module-level local binding.** Patching
  `X.Y` never reaches the local name bound inside the importing module.
  Two confirmed patients (`src.api.app.get_config`,
  `src.api.routes.workflow.get_llm/get_kb`).
- **Type 2 — external service instantiation inside production `__init__`
  with hidden HTTP.** Tests only patch the service class, not its
  `_ensure_cache` HTTP call. One confirmed patient (`EditorInChief.__init__`
  triggering `LawVerifier._ensure_cache` → `law.moj.gov.tw` cold-boot 40 s).
- **Type 3 — production function lacks input-size cap, turning test
  fixtures into DoS vectors.** One confirmed patient
  (`_bm25_search` before `_MAX_QUERY_CHARS = 500` cap; `jieba.cut` on
  30 k-char query fixture = 8 s).

Four patients fixed so far. Sensor still lists residual candidates
(`test_switch_direct_provider` 2.4–3.3 s, `test_generate_post_returns_result`
2.5–3.2 s) without a systematic way to detect whether they belong to one of
the three types or to a genuine slow path.

## Solution

Convert the iceberg from "ad-hoc reactive fix after cold pytest" into a
repeatable audit:

1. `scripts/audit_local_binding.py --dry-run` — walks every test under
   `tests/`, inspects patches, detects any `patch("src.X.Y")` where `X.Y`
   is imported locally by a downstream module but not patched there; lists
   candidates ranked by heuristic risk score.
2. `tests/conftest.py` gains a documented `rebind_local` helper so future
   tests adopt the known-good pattern without copying from `adb531c`.
3. An `ast-grep` rule file shipped at `scripts/ast_grep/` to detect Type 1
   call sites in `src/` (any `from src.X.Y import Z` where `Z` is used as a
   module-level function indirection).
4. A CONTRIBUTING.md section ("Mock contract rules") walking authors
   through the three types with links to the canonical fixes
   (`adb531c / 6b41335 / c0933f9 / 1eef399`).
5. `docs/test-mock-iceberg-taxonomy.md` formal taxonomy page linked from
   CONTRIBUTING.md and from `openspec/changes/08-bare-except-audit-iter6`
   for cross-reference.

## Non-Goals

- No automatic rewrite of existing tests — the audit surfaces candidates,
  humans still fix them.
- No pytest plugin of our own (rely on ast-grep + simple static scan; a
  plugin is revisited only if the audit reliably detects > 20 patients).
- No change to `commit_msg_lint.py` or sensor behaviour (separate changes
  07 / 99619d3).
- No new runtime CLI; the audit is a test-time / CI-time tool only.

## Acceptance Criteria

1. `scripts/audit_local_binding.py --dry-run` exits 0 when no Type 1
   candidates exist, exit 1 with a ranked JSON report when at least one
   does. Runs in < 10 s on the current test tree.
2. `tests/conftest.py` exposes a `rebind_local(module, attr, target)`
   fixture helper with a docstring pointing to the three canonical fixes.
3. `scripts/ast_grep/local_binding.yml` present and runs via
   `ast-grep scan --rule scripts/ast_grep/local_binding.yml src/`.
4. `CONTRIBUTING.md` has a "Mock contract rules" section that names the
   three iceberg types and links to `docs/test-mock-iceberg-taxonomy.md`.
5. `docs/test-mock-iceberg-taxonomy.md` documents all three types with one
   example each (pre-fix / post-fix diff excerpt + commit hash).
6. `spectra validate --changes 10-test-local-binding-audit-systematic`
   returns `valid`.
