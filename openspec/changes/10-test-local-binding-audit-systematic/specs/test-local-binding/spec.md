# Spec: Test Local-Binding Audit Systematisation

## Summary

Converts the reactive "find-and-fix next iceberg patient" workflow into a
static-scan + CONTRIBUTING contract + documented taxonomy so future tests
never recreate the three patterns that produced the LOOP3 runtime collapse
evidence (960 s → 153 s; four individual patients fixed).

## ADDED Requirements

### Requirement: Audit tooling must enumerate Type 1 iceberg candidates reproducibly

`scripts/audit_local_binding.py` MUST statically detect any test that uses
`unittest.mock.patch("src.X.Y")` (or `mocker.patch(...)`) where `Y` is
imported locally by another module `Z` — implying the patch misses `Z.Y`.

The tool MUST emit a JSON report (candidate path, patch string, suspected
downstream binding, heuristic risk score 0–1) on stdout and an exit code
of 0 when the list is empty, 1 otherwise.

#### Scenario: audit exits 1 when a Type 1 candidate exists

- **GIVEN** a test patches `src.api.app.get_config` but a downstream module
  imported it as `from src.api.app import get_config`
- **WHEN** `scripts/audit_local_binding.py --dry-run` runs
- **THEN** the tool exits 1
- **AND** the report lists the candidate with a risk score > 0.5

### Requirement: Test authors can opt into the known-good rebind pattern without copying code

`tests/conftest.py` MUST expose a `rebind_local(module, attr, target)`
helper that performs the re-bind used by `adb531c` (the canonical fix for
Type 1). The helper's docstring MUST link to the two seminal fixes
(`adb531c` preflight re-bind, `6b41335` workflow re-bind).

#### Scenario: new test uses the helper instead of hand-rolled re-bind

- **GIVEN** a test file that needs to override a locally-bound name
- **WHEN** the author imports `rebind_local` from `tests.conftest`
- **THEN** the re-bind behaves identically to the hand-rolled form in
  `test_api_server.py::TestScenario5_APIEndpoints`
- **AND** the helper auto-restores the original binding at teardown

### Requirement: CONTRIBUTING walks authors through the three types before they write a mock

`CONTRIBUTING.md` MUST contain a "Mock contract rules" section that names
the three types, gives one canonical commit hash per type, and links to
`docs/test-mock-iceberg-taxonomy.md`. The section MUST appear above any
"how to write tests" section.

#### Scenario: author reads CONTRIBUTING before adding a test

- **WHEN** an author opens `CONTRIBUTING.md`
- **THEN** they see the three iceberg types named with SHAs
  (`adb531c`, `c0933f9`, `1eef399`) before any generic test-writing advice
- **AND** the section points at the taxonomy document for diffs

### Requirement: The taxonomy document maps sensor-observable symptoms to iceberg types

`docs/test-mock-iceberg-taxonomy.md` MUST define, per type:

- **Symptom** — what the sensor / pytest durations show
  (e.g., "single test > 30 s with mocked LLM"; "cold-boot warning in
  logs about HTTP retry")
- **Root cause** — one-sentence explanation
- **Canonical fix** — commit SHA + diff excerpt
- **Audit signal** — which sensor metric or `audit_local_binding.py` line
  flags it

#### Scenario: symptom lookup closes the fix loop

- **GIVEN** a developer observes a 40-second focused test
- **WHEN** they grep `docs/test-mock-iceberg-taxonomy.md` for "40 s"
- **THEN** they land on Type 2 (external service cold-boot)
- **AND** they see the `c0933f9` diff pattern and can replicate the fix
