# Architecture Split SOP

## Purpose
This SOP captures the split pattern that already worked for four clusters:

- `src/agents/editor.py` -> `src/agents/editor/{flow,segment,refine,merge}.py`
- `src/agents/writer.py` -> `src/agents/writer/{strategy,rewrite,cite,cleanup,ask_service}.py`
- `src/cli/kb.py` -> `src/cli/kb/{corpus,ingest,rebuild,stats,status}.py`
- `src/cli/generate/pipeline.py` -> `src/cli/generate/pipeline/{compose,render,persist}.py`

Goal: prevent new 500-1000 line files, keep public imports stable, and make future refactors smaller than one review cycle.

## Trigger Rules
Split a file when one or more conditions hit:

- file size exceeds 400 lines
- one file owns more than 3 distinct responsibilities
- tests need heavy monkeypatching against unrelated helpers in the same file
- CLI/API files mix routing, validation, persistence, and rendering in one module
- review changes repeatedly touch unrelated sections of the same file

Do not wait for 800+ lines. Split at the first stable seam.

## Non-Negotiables
- Split by responsibility, not arbitrary line count chunks.
- Keep one compatibility facade at package root when existing imports or monkeypatch paths matter.
- Move logic first. Rename symbols only when needed.
- Preserve repo-owned seams. Vendor code, external payloads, and review policy must stay isolated.
- Land with targeted tests plus one broader regression pass.

## Standard Procedure
1. Measure current file responsibilities and line counts.
2. Choose package slices by behavior boundary.
3. Create package folder with `__init__.py` as the stable import facade.
4. Move cohesive functions or mixins into leaf modules.
5. Re-export public symbols from `__init__.py`.
6. Keep comments only where compatibility or split rationale is non-obvious.
7. Run the narrowest relevant tests first.
8. Run one broader regression suite before declaring PASS.
9. Update `program.md` and `results.log` with hard evidence.

## Package Patterns
### 1. Agent mixin split
Use for large orchestration classes with separable behaviors.

Pattern:

```text
src/agents/<name>/
  __init__.py
  strategy.py
  rewrite.py
  cite.py
  cleanup.py
```

Rules:

- `__init__.py` owns the concrete agent class and imports mixins
- leaf modules own one behavior family each
- shared dependencies stay imported at the facade only if tests patch there

Current reference:

- editor modules: 85-272 lines each
- writer modules: 39-221 lines each

### 2. CLI command split
Use when one command group grows subcommands with separate validation and reporting paths.

Pattern:

```text
src/cli/<group>/
  __init__.py
  _shared.py
  ingest.py
  stats.py
  status.py
```

Rules:

- `_shared.py` only holds shared app/logger/console state
- each subcommand file owns one command family
- parsing helpers stay near the command that uses them unless reused twice

Current reference:

- `src/cli/kb/` modules: 6-243 lines each

### 3. Pipeline split
Use when one pipeline file mixes input resolution, execution, rendering, and persistence.

Pattern:

```text
src/cli/<flow>/pipeline/
  __init__.py
  compose.py
  render.py
  persist.py
```

Rules:

- `compose.py` resolves inputs, engines, retries
- `render.py` owns user-visible output and dry-run handling
- `persist.py` owns file writes and batch item processing
- `__init__.py` re-exports the old call surface

Current reference:

- generate pipeline modules: 25-224 lines each

## Validation Matrix
Every split must keep three things true:

1. Public import compatibility still works.
2. Targeted tests for the changed area pass.
3. One broader regression suite passes.

Recommended commands:

- agent split: `python -m pytest tests/test_writer_agent.py tests/test_agents.py -q`
- CLI split: `python -m pytest tests/test_cli_commands.py tests/test_fetchers.py tests/test_robustness.py -q`
- pipeline split: `python -m pytest tests/test_cli_commands.py tests/test_batch_perf.py tests/test_workflow_cmd.py -q`
- full safety net: `python -m pytest tests/ -q --no-header --ignore=tests/integration`

## Anti-Patterns
- Splitting only because the file is large while keeping cross-module circular imports.
- Leaving `__init__.py` empty and breaking old import paths.
- Mixing transport concerns with domain logic in the same new module.
- Declaring PASS from file-count changes without regression evidence.
- Moving dead code into new files instead of deleting or isolating it.

## Next Targets
Apply this SOP next to:

- `src/api/routes/workflow.py`
- `src/agents/template.py`
- `src/cli/template_cmd.py`
- `src/document/exporter.py`
- `src/knowledge/manager.py`

Use the smallest seam that preserves behavior and testability.
