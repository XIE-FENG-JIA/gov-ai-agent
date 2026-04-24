# Tasks: 08-bare-except-audit-iter6

- [ ] **T8.1** Sweep `src/agents/compliance_checker.py` (3 sites) to typed bucket + `logger.warning`.
  Requirements:
  - Bare exception handlers must surface a `logger.warning` and preserve caller contract
  Validation: `rg -c "except Exception|except:" src/agents/compliance_checker.py` returns 0; `pytest tests/test_agents.py tests/test_agents_extended.py -q -k compliance` green.
  Commit: `refactor(agents): compliance_checker typed bucket sweep`

- [ ] **T8.2** Sweep `src/agents/editor/__init__.py` (3 sites).
  Requirements:
  - Bare exception handlers must surface a `logger.warning` and preserve caller contract
  Validation: `rg -c "except Exception|except:" src/agents/editor/__init__.py` returns 0; `pytest tests/test_agents_extended.py -q -k editor` green (incl. `TestEditorSafeLowNoRefine`).
  Commit: `refactor(agents): editor typed bucket sweep`

- [ ] **T8.3** Sweep `src/api/routes/workflow/_endpoints.py` (3 sites).
  Requirements:
  - Bare exception handlers must surface a `logger.warning` and preserve caller contract
  Validation: `rg -c "except Exception|except:" src/api/routes/workflow/_endpoints.py` returns 0; `pytest tests/test_api_server.py -q -k workflow` green.
  Commit: `refactor(api): workflow endpoints typed bucket sweep`

- [ ] **T8.4** Sweep `src/cli/config_tools.py` (3 sites).
  Requirements:
  - Bare exception handlers must surface a `logger.warning` and preserve caller contract
  Validation: `rg -c "except Exception|except:" src/cli/config_tools.py` returns 0; `pytest tests/test_config_tools_extra.py -q` green.
  Commit: `refactor(cli): config_tools typed bucket sweep`

- [ ] **T8.5** Sweep `src/graph/nodes/reviewers.py` (3 sites).
  Requirements:
  - Bare exception handlers must surface a `logger.warning` and preserve caller contract
  Validation: `rg -c "except Exception|except:" src/graph/nodes/reviewers.py` returns 0; `pytest tests/test_graph_nodes_extra.py -q` green.
  Commit: `refactor(graph): reviewers typed bucket sweep`

- [ ] **T8.6** Sweep `src/knowledge/_manager_hybrid.py` (3 sites — do not touch BM25 cap or cache).
  Requirements:
  - Bare exception handlers must surface a `logger.warning` and preserve caller contract
  Validation: `rg -c "except Exception|except:" src/knowledge/_manager_hybrid.py` returns 0; `pytest tests/test_edge_cases.py -q -k KBEdge` green.
  Commit: `refactor(knowledge): _manager_hybrid typed bucket sweep`

- [ ] **T8.7** Regression check: `python scripts/sensor_refresh.py --human` reports `bare_except.total ≤ 80`; `pytest -q --ignore=tests/integration` full-suite green in ≤ 200 s.
  Requirements:
  - Repo-wide bare-except budget lowered after each audit iteration
  Validation: sensor output + `wc -l /tmp/pytest_iter6.out` confirm targets.
  Commit: `chore(sensor): record iter6 bare-except 89→≤80 baseline`
