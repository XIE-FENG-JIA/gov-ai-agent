## Problem

`scripts/sensor_refresh.py` run against HEAD shows **3 Python files breaching
the repo-wide 400-line anchor** (set in v7.0 header, confirmed by
`openspec/config.yaml` "each task within 2 hours" rule which implies bounded
module size):

- `src/cli/kb/rebuild.py` — **572 lines** (historical sensor blind spot;
  first discovered by `scripts/sensor_refresh.py` first run on 2026-04-25)
- `src/sources/datagovtw.py` — 410 lines (listed in v7.0 header for 3+
  rounds, iteration 10 waiting)
- `src/api/routes/agents.py` — 397 lines (yellow-tier in v7.3 sensor, rising
  toward red; preempt before drift)

`rebuild.py 572` is the largest unreported fat file in repo history — it
slipped past every manual fat-watch pass in v7.0, v7.2-sensor, and v7.3-sensor
because the curated "top" list stopped at two candidates. Sensor automation
caught it on first run, which validates the new "每輪第 0 步跑 sensor" red
line (v4). Letting it keep growing blocks future refactoring windows.

## Solution

Split each of the three files into a package with a stable `__init__.py`
re-export surface (the template used for iterations 7–9 of
`T-FAT-ROTATE-V2`), then rename tasks accordingly:

1. `src/cli/kb/rebuild.py 572` → `src/cli/kb/rebuild/{__init__, orchestrate,
   adapters, quality_gate_integration}.py` (natural seams: orchestration,
   per-adapter logic, `--quality-gate` flag wiring from Epic 6 T-LIQG-4).
2. `src/sources/datagovtw.py 410` → `src/sources/datagovtw/{__init__, client,
   normalize, fixtures}.py` (seams: HTTP client, payload → `PublicGovDoc`
   normalizer, fixture-fallback path).
3. `src/api/routes/agents.py 397` → `src/api/routes/agents/{__init__, read,
   write}.py` (FastAPI router seam: GET-only endpoints vs mutating endpoints).

Each split preserves `from <old.path> import <Name>` contracts so call sites
and tests do not need coupled edits. Tests MUST stay byte-identical (or
amended only for new file location in import-from-specific paths).

## Non-Goals

- No API-surface behaviour change (route paths / CLI flags / function
  signatures stay identical).
- No collateral refactor (the same files carry bare-except hotspots —
  iteration 6 in change 08 handles those first; splits here only touch
  layout, not exception handling).
- No retry of iteration 10 (`datagovtw`) independently — it's bundled here
  because splitting 3 files in one change matches the anchor deadline.
- No SQLite / SurrealDB migration touching `rebuild.py` (frozen under
  `T2.3`).

## Acceptance Criteria

1. `wc -l src/cli/kb/rebuild/*.py src/sources/datagovtw/*.py src/api/routes/agents/*.py`
   shows every file **≤ 300 lines**.
2. `python scripts/sensor_refresh.py --human` reports zero files in the red
   tier (>400) and zero of the three source modules in yellow (350–400).
3. `pytest tests/test_cli_kb_rebuild*.py tests/test_datagovtw_adapter*.py tests/test_api_server.py -q`
   all pass; full suite `pytest -q --ignore=tests/integration` exits 0 in
   ≤ 200 s.
4. `spectra validate --changes 09-fat-rotate-iter3` returns `valid`.
5. `git grep -nE "^from src\\.(cli\\.kb\\.rebuild|sources\\.datagovtw|api\\.routes\\.agents) import"`
   still compiles (import paths preserved via `__init__.py` re-export).
