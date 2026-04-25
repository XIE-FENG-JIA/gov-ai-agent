# Tasks: 10-test-local-binding-audit-systematic

- [x] **T10.1** Write `scripts/audit_local_binding.py` detecting Type 1 candidates (`patch("src.X.Y")` where X imports Y locally into a different module).
  Requirements:
  - Audit tooling must enumerate Type 1 iceberg candidates reproducibly
  Validation: `python scripts/audit_local_binding.py --dry-run` on current repo exits with a candidate count matching manual count; `pytest tests/test_audit_local_binding.py -q` ≥ 6 tests.
  Commit: `feat(governance): add audit_local_binding static scan (Type 1)`

- [x] **T10.2** Add `rebind_local(module, attr, target)` helper in `tests/conftest.py` with docstring linking `adb531c / 6b41335`.
  Requirements:
  - Test authors can opt into the known-good rebind pattern without copying code
  Validation: `pytest tests/ -q -k "rebind"` green; at least one existing test migrated to the helper as a reference.
  Commit: `feat(tests): rebind_local helper for module local binding`

- [x] **T10.3** Ship `scripts/ast_grep/local_binding.yml` rule detecting `from src.X import Y` where Y is used as module-level indirection in src/.
  Requirements:
  - Audit tooling must enumerate Type 1 iceberg candidates reproducibly
  Validation: `ast-grep scan --rule scripts/ast_grep/local_binding.yml src/` runs without error; matches the known Type 1 sites (`src.api.app` / `src.api.routes.workflow`).
  Commit: `feat(governance): ast-grep rule for local_binding static detection`

- [x] **T10.4** Write `CONTRIBUTING.md` "Mock contract rules" section naming the three iceberg types with canonical commit links.
  Requirements:
  - CONTRIBUTING walks authors through the three types before they write a mock
  Validation: `rg "Mock contract rules" CONTRIBUTING.md` matches; section contains the three type names and at least three commit SHAs (`adb531c`, `c0933f9`, `1eef399`).
  Commit: `docs(contributing): mock contract rules — three iceberg types`

- [x] **T10.5** Write `docs/test-mock-iceberg-taxonomy.md` with one example per type (pre-fix / post-fix diff excerpt).
  Requirements:
  - The taxonomy document maps sensor-observable symptoms to iceberg types
  Validation: `wc -l docs/test-mock-iceberg-taxonomy.md` ≥ 80; `rg "Type [1-3]" docs/test-mock-iceberg-taxonomy.md` finds all three headings.
  Commit: `docs(tests): add mock iceberg taxonomy Type 1/2/3 with diffs`

- [x] **T10.6** Regression: `python scripts/sensor_refresh.py` still runs; `pytest -q --ignore=tests/integration` still green ≤ 200 s.
  Requirements:
  - Systematic audit must not regress repo baselines
  Validation: sensor + pytest logs confirm thresholds.
  Commit: `chore(governance): record iceberg audit baseline post-merge`
