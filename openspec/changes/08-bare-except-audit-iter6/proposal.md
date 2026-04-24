## Problem

Sensor `scripts/sensor_refresh.py` run against HEAD reports **89 bare-except
occurrences across 58 files**. After iterations 1–5 cleared the historical
top hotspots (`web_preview/app`, `cli/kb/stats`, `manager`, `gazette_fetcher`,
`_manager_search`, `core/llm`, `generate/export`, `auditor`, `fact_checker`),
the residue migrated to a **new tier of 6 files each carrying 3 occurrences**:

- `src/agents/compliance_checker.py`
- `src/agents/editor/__init__.py`
- `src/api/routes/workflow/_endpoints.py`
- `src/cli/config_tools.py`
- `src/graph/nodes/reviewers.py`
- `src/knowledge/_manager_hybrid.py`

Bare `except Exception` / `except:` handlers at these locations swallow
unexpected exceptions silently, block typed error analytics, and break the
red-line rule "downstream callers must see a `logger.warning` record when a
dependency fails". Two hotspots (`editor/__init__.py` and
`workflow/_endpoints.py`) sit on the critical rewrite path — a silent swallow
there is indistinguishable from a degraded-agent fallback, which has already
caused one pre-existing flake (`test_preflight_check_warns_missing_*` series,
see `adb531c`).

## Solution

Sweep the 6 files using the same "typed bucket + `logger.warning`" template
that closed iterations 3–5:

1. Identify the actual exception classes that reach each `except` site
   (read call graph and imports; prefer specific classes like
   `AttributeError / KeyError / RuntimeError / TypeError / ValueError`
   before the `Exception` fallback).
2. Replace bare `except` with `except (A, B, C) as exc:` and add
   `logger.warning("... %s", exc)` at each site.
3. Where the callsite already has a wider-scope try block that does the
   warning, keep the outer behaviour but narrow the inner.
4. Add or update a test per file asserting the `logger.warning` path fires
   when the corresponding error is injected.

Target: bare-except total ≤ 80 across the repo when
`scripts/sensor_refresh.py` runs after merge (reduction of ≥ 9 from current
89, corresponding to the 18 sweeps in this change plus some collateral).

## Non-Goals

- No behaviour change for the happy path (the sweep MUST stay contract-safe;
  if an exception was previously swallowed and callers relied on that, the
  warning replaces the silent swallow but keeps the fall-through semantics).
- No attempt to remove all remaining bare-except occurrences; the next
  iteration (刀 7) will target the next tier once this one lands.
- No refactor of the underlying modules beyond the immediate try/except sites.
- No change to `_manager_hybrid.py` BM25 query-length cap or cache contract
  (`1eef399`); the sweep only touches exception handlers there.

## Acceptance Criteria

1. `rg -c "except Exception|except:" src/{agents/compliance_checker,agents/editor/__init__,api/routes/workflow/_endpoints,cli/config_tools,graph/nodes/reviewers,knowledge/_manager_hybrid}.py`
   returns **0** for all six files after the sweep.
2. `python scripts/sensor_refresh.py --human` reports
   `bare_except.total ≤ 80`.
3. `pytest tests/test_compliance_checker*.py tests/test_editor*.py tests/test_workflow*.py tests/test_config_tools*.py tests/test_graph_nodes_extra.py tests/test_knowledge_manager_hybrid*.py -q`
   all pass; at least one test per file asserts the new
   `logger.warning` fires for the targeted exception type.
4. `spectra validate --changes 08-bare-except-audit-iter6` returns `valid`.
5. Regression: full `pytest -q --ignore=tests/integration` still exits 0
   with runtime ≤ 200 s (current cold-start baseline 153 s, allow +47 s).
