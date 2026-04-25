# Tasks: 13-cli-fat-rotate-v3

## Track A — Split utils.py (God Object)

- [x] **T13.1a** — Audit `utils.py`: annotate each function with target module (`io`/`display`/`text`).
  Validation: `python -c "import ast; tree = ast.parse(open('src/cli/utils.py').read()); print(len(tree.body))"` prints current function count.
  Commit: `docs(cli): annotate utils.py split targets for fat-rotate-v3`

- [x] **T13.1b** — Create `src/cli/utils_io.py` (file I/O, atomic write, path helpers); update all importers.
  Requirements: Every importer that used `from src.cli.utils import <io-fn>` now imports from `utils_io`.
  Validation: `python -m pytest tests/test_cli_commands.py -q` passes; `grep -rn "from src.cli.utils import" src/cli/ | wc -l` ≤ 20.
  Commit: `refactor(cli): extract utils_io from utils.py (fat-rotate-v3 A)`

- [x] **T13.1c** — Create `src/cli/utils_display.py` (Rich console, table, progress-bar); update importers.
  Requirements: Rich-dependent helpers moved; `utils.py` no longer imports `rich.*`.
  Validation: `python -m pytest tests/test_cli_commands.py -q` passes; `grep -n "from rich" src/cli/utils.py | wc -l` = 0.
  Commit: `refactor(cli): extract utils_display from utils.py (fat-rotate-v3 B)`

- [x] **T13.1d** — Create `src/cli/utils_text.py` (text normalisation, encoding); update importers.
  Requirements: All text-normalisation helpers moved; `utils.py` ≤ 80 lines (shim only).
  Validation: `python -m pytest tests/test_cli_commands.py -q` passes; `wc -l src/cli/utils.py` ≤ 80.
  Commit: `refactor(cli): extract utils_text from utils.py (fat-rotate-v3 C)`

- [ ] **T13.1e** — Delete `src/cli/utils.py` after confirming zero direct importers remain.
  Requirements: `grep -rn "from src.cli.utils import\|from .utils import" src/cli/` = 0 results.
  Validation: `python -m pytest tests/ -q --ignore=tests/integration` exits 0.
  Commit: `refactor(cli): remove utils.py shim after full importer migration`

---

## Track B — Break Iceberg Cross-Command Coupling

- [x] **T13.2** — Extract generate lint invocation to `src/cli/_shared/lint_invocation.py`.
  Requirements: `lint_cmd.py` still registers the CLI command; `generate/export.py` imports the public `run_lint` interface from `_shared/lint_invocation.py`.
  Validation: `python -m pytest tests/test_generate_pipeline.py tests/test_lint_cmd.py -q` passes; `grep -n "from src.cli.lint_cmd import" src/ -r` has no high-risk generate import.
  Commit: `refactor(cli): route generate lint through shared invocation (iceberg fix)`

- [x] **T13.3** — Extract citation mapping/format helpers to `src/cli/_shared/citation_format.py`.
  Requirements: `cite_cmd.py` and `generate/export.py` use the public citation formatting interface instead of cross-command private symbols.
  Validation: `python -m pytest tests/test_generate_pipeline.py tests/test_cite_cmd.py -q` passes; `grep -n "from src.cli.cite_cmd import _" src/ -r` has no high-risk generate import.
  Commit: `refactor(cli): route generate citations through shared formatter (iceberg fix)`

- [x] **T13.4** — Move `collect_citation_verification_checks` + `render_citation_verification_results` to `src/cli/shared/verify_service.py`.
  Requirements: Both `verify_cmd.py` and `kb/rebuild.py` import from `verify_service`; `verify_cmd.py` public interface unchanged.
  Validation: `python -m pytest tests/test_cli_commands.py -q -k "verify or kb_rebuild"` passes.
  Commit: `refactor(cli): extract verify helpers to shared/verify_service (iceberg fix)`

- [x] **T13.5** — Move `history.append_record` to `src/core/history_store.py`; update `history/__init__.py` and `generate/__init__.py`.
  Requirements: `generate/__init__.py` imports `history_store.append_record`; no direct `history` CLI group import in generate.
  Validation: `python -m pytest tests/test_cli_commands.py -q -k "generate or history"` passes.
  Commit: `refactor(core): extract history_store.append_record from cli/history layer`

---

## Track C — Micro-file Mergers

- [x] **T13.6a** — Merge `highlight_cmd.py` (43 lines) into `search_cmd.py` (keyword-match concern).
  Requirements: `gov-ai highlight` CLI command still registered via `search_cmd.py` delegating to `main.py`; `highlight_cmd.py` deleted.
  Validation: `python -m pytest tests/test_cli_commands.py -q -k "highlight or search"` passes.
  Commit: `refactor(cli): merge highlight_cmd into search_cmd (micro-merge)`

- [x] **T13.6b** — Fold `number_cmd.py` (44 lines) into `stamp_cmd.py`.
  Requirements: `gov-ai number` command still works; `number_cmd.py` deleted.
  Validation: `python -m pytest tests/test_cli_commands.py -q -k "number or stamp"` passes.
  Commit: `refactor(cli): fold number_cmd into stamp_cmd (micro-merge)`

- [x] **T13.6c** — Merge `replace_cmd.py` (44 lines) with `redact_cmd.py`.
  Requirements: Both commands registered; `replace_cmd.py` deleted.
  Validation: `python -m pytest tests/test_cli_commands.py -q -k "replace or redact"` passes.
  Commit: `refactor(cli): merge replace_cmd into redact_cmd (micro-merge)`

- [x] **T13.6d** — Merge `generate/pipeline/persist/__init__.py` (9 lines) + `batch_io.py` (22 lines) into `batch_runner.py`.
  Requirements: `batch_runner.py` absorbs batch I/O logic; `__init__.py` becomes re-export only.
  Validation: `python -m pytest tests/ -q --ignore=tests/integration` exits 0.
  Commit: `refactor(cli): merge generate pipeline persist micro-files into batch_runner`

---

## Track D — Regression Gate

- [x] **T13.7** — Full regression check after all track A/B/C tasks complete.
  Validation:
  - `python scripts/check_fat_files.py --strict` exits 0
  - `python scripts/sensor_refresh.py --human` fat_files.red_over_400 = []
  - `python scripts/cli_ast_audit.py 2>&1 | grep "HIGH"` = 0 lines
  - `python -m pytest tests/ -q --ignore=tests/integration` exits 0 in ≤ 120 s
  Commit: `chore(sensor): record cli-fat-rotate-v3 completion`
