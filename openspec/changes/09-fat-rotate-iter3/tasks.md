# Tasks: 09-fat-rotate-iter3

- [ ] **T9.1 [BACKLOG-next-fat-rotate]** Split `src/cli/kb/rebuild.py 572` → `src/cli/kb/rebuild/{__init__, orchestrate, adapters, quality_gate_integration}.py`.
  Requirements:
  - No module larger than 300 lines after rotation
  - Import contract preserved through `__init__.py` re-exports
  Validation: `wc -l src/cli/kb/rebuild/*.py` all ≤ 300; `pytest tests/test_cli_kb_rebuild*.py tests/test_cli_commands.py -q -k rebuild` green.
  Commit: `refactor(cli): split kb/rebuild 572 into orchestrate/adapters/quality_gate_integration`

- [x] **T9.2** Split `src/sources/datagovtw.py 410` → `src/sources/datagovtw/{__init__, client, normalize, fixtures}.py`.
  Requirements:
  - No module larger than 300 lines after rotation
  - Import contract preserved through `__init__.py` re-exports
  Validation: `wc -l src/sources/datagovtw/*.py` all ≤ 300; `pytest tests/test_datagovtw_adapter.py -q` green.
  Commit: `refactor(sources): split datagovtw 410 into client/normalize/fixtures`

- [x] **T9.3** Split `src/api/routes/agents.py 397` → `src/api/routes/agents/{__init__, read, write}.py`.
  Requirements:
  - No module larger than 300 lines after rotation
  - Import contract preserved through `__init__.py` re-exports
  Validation: `wc -l src/api/routes/agents/*.py` all ≤ 300; `pytest tests/test_api_server.py -q -k agent` green; FastAPI router path stable (`gov-ai` CLI or curl smoke).
  Commit: `refactor(api): split routes/agents 397 into read/write`

- [ ] **T9.4 [BLOCKED-by-T9.1]** Sensor regression check — fat-file red tier hits 0, yellow excludes the three ex-fat modules.
  Requirements:
  - No module larger than 300 lines after rotation
  Validation: `python scripts/sensor_refresh.py --human` reports `fat_files.red_over_400 == []` and `rebuild/datagovtw/routes-agents` not in yellow list.
  Commit: `chore(sensor): record iter3 fat-rotate 572+410+397 → ≤ 300`

- [ ] **T9.5 [REGRESSION-440s-vs-200s-acceptance]** Regression: full `pytest -q --ignore=tests/integration` green in ≤ 200 s.
  Requirements:
  - Import contract preserved through `__init__.py` re-exports
  Validation: `pytest -q --ignore=tests/integration --durations=10 --tb=no` exits 0 with runtime line ≤ 200 s.
  Commit: `chore(tests): confirm iter3 fat-rotate full-suite runtime budget`
  Status (2026-04-25 15:32): **3913 passed / 0 failed in 440.62 s** — 22 fail 已修 (commit `827e601 fix(agents): T-REGRESSION-FIX-刀8`) 但 runtime 從 cold-start 153s / 雙 baseline 173-180s 退到 440s (+222%). Likely causes: (a) typed bucket broadening 在 graceful-degradation path 上加 retry / sleep; (b) auto-engineer 加了 22 個新 test (3891 → 3913) 但無並行加速; (c) Windows Defender 等外部因素. **T9.5 acceptance 未達, 退回 `[ ]`**. 開新 backlog task T-PYTEST-RUNTIME-REGRESSION-iter6 處理.
