## Problem

`docs/cli-module-audit.md` (produced by `scripts/cli_ast_audit.py`) reveals three structural
issues in `src/cli/` (80 files, 10 924 lines):

**1. utils.py God Object (310 lines, 26 importers)**
`utils.py` is the single most-imported module (32.5% of all cli files). A docstring change
cascades to 26 dependents. Functions span three unrelated concerns: file I/O, Rich display,
and text normalisation.

**2. Iceberg Cross-Command Coupling (4 high-risk imports)**
Three import chains use private (`_`-prefixed) symbols across sub-command boundaries:

- `generate/export.py` → `lint_cmd._run_lint` (private)
- `generate/export.py` → `cite_cmd._MAPPING_PATH`, `_filter_applicable`, `_load_mapping` (all private)
- `kb/rebuild.py` → `verify_cmd.collect_citation_verification_checks`, `render_citation_verification_results`
- `generate/__init__.py` → `history.append_record` (direct history storage write)

Any rename or refactor of `lint_cmd`, `cite_cmd`, `verify_cmd`, or `history` silently breaks
unrelated commands.

**3. Bimodal Size Distribution**
11 files ≥ 250 lines (resist review/test isolation) and 9 files < 50 lines (navigation overhead
with no architectural value) coexist in the same module.

## Solution

**(a) Split `utils.py` into three domain modules** — progressively switch all 26 importers:
- `utils_io.py` — file read/write, atomic write, path helpers
- `utils_display.py` — Rich console, table, progress-bar helpers
- `utils_text.py` — text normalisation, encoding helpers
- Keep `utils.py` as a thin re-export shim until all importers are migrated; delete after T13.1e.

**(b) Extract private symbols to `src/cli/shared/` services** — break iceberg coupling:
- `src/cli/shared/lint_service.py` ← `_run_lint` from `lint_cmd`
- `src/cli/shared/cite_service.py` ← `_MAPPING_PATH`, `_filter_applicable`, `_load_mapping` from `cite_cmd`
- `src/cli/shared/verify_service.py` ← `collect_citation_verification_checks`, `render_citation_verification_results` from `verify_cmd`
- `src/core/history_store.py` ← `append_record` from `history` (lower-level service)

**(c) Merge micro-files** — merge pairs/groups that share a single concern:
- `highlight_cmd.py` + `search_cmd.py` → keyword-match concern
- `number_cmd.py` folded into `stamp_cmd.py`
- `replace_cmd.py` merged with `redact_cmd.py`
- `generate/pipeline/persist/__init__.py` + `batch_io.py` → `batch_runner.py`

## Non-Goals

- No behaviour change to route paths, CLI flags, or function signatures.
- No SQLite/SurrealDB migration touching these files.
- No bare-except cleanup (handled by separate T-BARE-EXCEPT knife tasks).
- No cross-layer refactor beyond `src/cli/` and `src/core/history_store.py`.

## Acceptance Criteria

1. `python scripts/check_fat_files.py --strict` exits 0; no files in `src/cli/` exceed 300 lines.
2. `python -c "from src.cli import utils; from src.cli.shared import lint_service, cite_service, verify_service"` exits 0.
3. `python -m pytest tests/test_cli_commands.py tests/test_agents.py -q` = all previously-passing tests pass.
4. `python -m pytest tests/ -q --ignore=tests/integration` exits 0 in ≤ 120 s.
5. `python scripts/sensor_refresh.py --human` fat_files.red_over_400 = [].
6. `python scripts/cli_ast_audit.py 2>&1 | grep "HIGH"` = 0 lines (all HIGH-risk cross-group imports resolved).
