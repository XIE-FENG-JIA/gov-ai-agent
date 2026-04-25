# except-safety Specification

## Purpose

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

## Requirements

### Requirement: Bare exception handlers must surface a `logger.warning` and preserve caller contract

Any `except Exception:` / `except:` handler in the 6 targeted modules MUST
be rewritten as `except (A, B, C) as exc:` naming the actual exception
classes that can reach the site, followed by a `logger.warning(..., exc)`
call and the pre-existing fallback behaviour.

The sweep MUST NOT silently absorb errors the caller previously relied on
seeing. If a test asserted "exception escapes", the rewrite MUST preserve
that; if the silent swallow was accidental, the rewrite MUST add or update
a test asserting the `logger.warning` path.

#### Scenario: silent swallow becomes typed warning

- **GIVEN** a bare-except block that previously swallowed any `Exception`
- **WHEN** the targeted dependency raises (for example) `RuntimeError`
- **THEN** the rewritten block catches it via the typed bucket
- **AND** emits a `logger.warning` carrying the exception string
- **AND** the caller observes the same post-except behaviour (fall-through
  value, cached result, or default)

#### Scenario: tests assert warning path for each swept file

- **GIVEN** a swept file has at least one `logger.warning` call added
- **WHEN** the module's pytest suite runs
- **THEN** at least one test injects the targeted exception and asserts the
  warning record is present (via `caplog.at_level("WARNING")`)


<!-- @trace
source: 08-bare-except-audit-iter6
updated: 2026-04-25
code:
  - engineer-log.md
  - program.md
  - results.log
-->

---
### Requirement: Repo-wide bare-except budget lowered after each audit iteration

Each audit iteration MUST drive the `bare_except.total` counter reported by
`scripts/sensor_refresh.py` toward 0. Iteration 6's budget is ≤ 80 (reduction
of ≥ 9 from the starting 89). The sensor's soft-violation threshold
(currently 90) MUST be tightened to 80 after this iteration lands.

#### Scenario: sensor gates the next iteration

- **WHEN** `python scripts/sensor_refresh.py` runs after iteration 6 merges
- **THEN** `bare_except.total ≤ 80`
- **AND** `violations.soft` does not list `bare_except_total`


<!-- @trace
source: 08-bare-except-audit-iter6
updated: 2026-04-25
code:
  - engineer-log.md
  - program.md
  - results.log
-->

---
### Requirement: Iteration 6 MUST NOT alter BM25 cap or cache contract in `_manager_hybrid.py`

The bare-except sweep of `src/knowledge/_manager_hybrid.py` MUST be limited
to the three exception handlers. The BM25 query-length cap (`1eef399`,
`_MAX_QUERY_CHARS = 500`), hybrid cache keys, and retrieval ordering MUST
remain byte-identical.

#### Scenario: BM25 cap regression test still green

- **WHEN** `pytest tests/test_edge_cases.py::TestKBEdgeCases::test_search_very_long_string -q` runs after the sweep
- **THEN** the test passes in < 2 s (cap still active)
- **AND** `git diff src/knowledge/_manager_hybrid.py` shows no change outside
  the three handler sites

<!-- @trace
source: 08-bare-except-audit-iter6
updated: 2026-04-25
code:
  - engineer-log.md
  - program.md
  - results.log
-->