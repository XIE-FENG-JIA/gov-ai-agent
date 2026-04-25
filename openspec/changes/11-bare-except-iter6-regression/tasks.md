# Tasks: 11-bare-except-iter6-regression

- [ ] **T11.1** Identify the upstream caller in writer / editor / fact_checker chain that regressed `RuntimeError` propagation; locate its typed bucket.
  Requirements:
  - LLM/KB graceful-degradation contract restored without bypassing tests
  Validation: `python -m pytest tests/test_robustness.py::TestWriterAgentLLMException -q` reproduces the failure on the same line; `git diff HEAD` shows the typed bucket missing `RuntimeError` / `ConnectionError` / `TimeoutError`.
  Commit: included in T11.5 combined commit.

- [ ] **T11.2** Patch all swept sites in writer / editor / fact_checker / robustness paths so typed bucket catches `RuntimeError` plus concrete I/O exceptions (`OSError`, `ConnectionError`, `TimeoutError`) where upstream tests inject them.
  Requirements:
  - LLM/KB graceful-degradation contract restored without bypassing tests
  Validation: `pytest tests/test_robustness.py tests/test_editor_coverage.py tests/test_edge_cases.py tests/test_fact_checker_coverage.py tests/test_fact_checker_enhanced.py -q` 0 failed.
  Commit: included in T11.5 combined commit.

- [ ] **T11.3** Patch e2e fallout in `test_scenario_long_requirement` / `test_scenario_malicious_input` if their root is the same regression (likely; verify before patching).
  Requirements:
  - LLM/KB graceful-degradation contract restored without bypassing tests
  Validation: `pytest tests/test_e2e.py::TestUserSimulation -q` 0 failed.
  Commit: included in T11.5 combined commit.

- [ ] **T11.4** Patch `tests/test_robustness.py::TestCoverageImprovement::test_save_preferences_failure_logs_warning` regression by ensuring the preferences write-path catches the injected `OSError`.
  Requirements:
  - LLM/KB graceful-degradation contract restored without bypassing tests
  Validation: focused `pytest -k save_preferences_failure -q` green.
  Commit: included in T11.5 combined commit.

- [ ] **T11.5** Combined repair commit + full regression run.
  Requirements:
  - Single semantic commit landing iter6 sweep + repair, no broken intermediate on HEAD
  Validation: `pytest -q --ignore=tests/integration --tb=no` exits 0 with 0 failed and runtime ≤ 200 s; `python scripts/sensor_refresh.py --human` shows `bare_except.total ≤ 80` and no new soft violation introduced.
  Commit: `fix(agents): T-BARE-EXCEPT-AUDIT 刀 6 — typed bucket adds RuntimeError/ConnectionError to writer/editor/fact_checker/robustness fallbacks (+ change 08 sweep land)`
