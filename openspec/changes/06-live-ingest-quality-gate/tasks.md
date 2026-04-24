# Tasks: 06-live-ingest-quality-gate

- [ ] **T-LIQG-0** Finalize the live-ingest quality-gate change package with proposal, tasks, and one spec module under `specs/quality-gate/`.
  Requirements:
  - The first quality-gate slice is contract + reference helper, not a full rewrite
  Validation: `spectra status --change 06-live-ingest-quality-gate` shows `✓ specs` and `✓ tasks`
  Commit: `docs(spec): 06-live-ingest-quality-gate add specs/quality-gate + tasks.md`

- [x] **T-LIQG-1** Implement `src/sources/quality_gate.py` exposing `QualityGate.evaluate(records, adapter_name) -> GateReport` and the four named failure types (`LiveIngestBelowFloor`, `SchemaIntegrityError`, `StaleRecord`, `SyntheticContamination`).
  Requirements:
  - Quality gate enforces volume floor, schema integrity, and provenance signal as one contract
  - Gate failures surface as named exceptions, not silent empties
  Validation: `pytest tests/test_quality_gate.py -q`
  Commit: `feat(sources): add live-ingest quality gate contract + reference helper`

- [x] **T-LIQG-2** Add per-adapter quality config in `src/sources/quality_config.py` mapping adapter name → `{expected_min_records, freshness_window_days, allow_fallback}`. Include defaults for the seven Epic 1 adapters.
  Requirements:
  - Each adapter declares its own quality policy
  Validation: `pytest tests/test_quality_config.py -q`
  Commit: `feat(sources): add per-adapter quality config and defaults`

- [x] **T-LIQG-3** Wire `gov-ai kb gate-check --source <name>` CLI subcommand that runs the gate against a fresh fetch and emits a structured report (JSON + human modes).
  Requirements:
  - Operators can probe a single source through the gate without a full rebuild
  Validation: `pytest tests/test_kb_gate_check_cli.py -q`
  Commit: `feat(cli): add gov-ai kb gate-check subcommand`

- [x] **T-LIQG-4** Add `--quality-gate` flag to `gov-ai kb rebuild`; when set, every adapter's output is gated before merging into the staging corpus. Default off until Epic 6 lands fully.
  Requirements:
  - kb rebuild can opt-in to gate enforcement without breaking existing flows
  Validation: `pytest tests/test_kb_rebuild_cli.py -q -k gate`
  Commit: `feat(cli): wire --quality-gate flag into kb rebuild`

- [x] **T-LIQG-5** Add the gate failure-mode matrix doc at `docs/quality-gate-failure-matrix.md` covering the four named errors, their operator triage steps, and how each interacts with `--require-live`.
  Requirements:
  - Operators have a single source for triaging gate failures
  Validation: `rg -n "LiveIngestBelowFloor|SchemaIntegrityError|StaleRecord|SyntheticContamination" docs/quality-gate-failure-matrix.md`
  Commit: `docs(governance): add quality-gate failure matrix`

- [ ] **T-LIQG-6** Requirement coverage: Quality gate enforces volume floor, schema integrity, and provenance signal as one contract is satisfied by `T-LIQG-1`, `T-LIQG-2`, and `T-LIQG-4`.
  Validation: `spectra analyze 06-live-ingest-quality-gate`

- [ ] **T-LIQG-7** Requirement coverage: Gate failures surface as named exceptions, not silent empties is satisfied by `T-LIQG-1`, `T-LIQG-3`, and `T-LIQG-5`.
  Validation: `spectra analyze 06-live-ingest-quality-gate`

- [ ] **T-LIQG-8** Requirement coverage: Each adapter declares its own quality policy is satisfied by `T-LIQG-2` and `T-LIQG-4`.
  Validation: `spectra analyze 06-live-ingest-quality-gate`

- [ ] **T-LIQG-9** Requirement coverage: The first quality-gate slice is contract + reference helper, not a full rewrite is satisfied by `T-LIQG-0` and `T-LIQG-1`.
  Validation: `spectra analyze 06-live-ingest-quality-gate`

- [ ] **T-LIQG-10** Requirement coverage: Operators can probe a single source through the gate without a full rebuild is satisfied by `T-LIQG-3` and `T-LIQG-5`.
  Validation: `spectra analyze 06-live-ingest-quality-gate`

- [ ] **T-LIQG-11** Requirement coverage: kb rebuild can opt-in to gate enforcement without breaking existing flows is satisfied by `T-LIQG-4` and `T-LIQG-5`.
  Validation: `spectra analyze 06-live-ingest-quality-gate`

- [ ] **T-LIQG-12** Requirement coverage: Operators have a single source for triaging gate failures is satisfied by `T-LIQG-5`.
  Validation: `spectra analyze 06-live-ingest-quality-gate`

## Requirement Mapping

- Requirement: Quality gate enforces volume floor, schema integrity, and provenance signal as one contract
  Tasks: `T-LIQG-1`, `T-LIQG-2`, `T-LIQG-4`, `T-LIQG-6`

- Requirement: Gate failures surface as named exceptions, not silent empties
  Tasks: `T-LIQG-1`, `T-LIQG-3`, `T-LIQG-5`, `T-LIQG-7`

- Requirement: Each adapter declares its own quality policy
  Tasks: `T-LIQG-2`, `T-LIQG-4`, `T-LIQG-8`

- Requirement: The first quality-gate slice is contract + reference helper, not a full rewrite
  Tasks: `T-LIQG-0`, `T-LIQG-1`, `T-LIQG-9`

- Requirement: Operators can probe a single source through the gate without a full rebuild
  Tasks: `T-LIQG-3`, `T-LIQG-5`, `T-LIQG-10`

- Requirement: kb rebuild can opt-in to gate enforcement without breaking existing flows
  Tasks: `T-LIQG-4`, `T-LIQG-5`, `T-LIQG-11`

- Requirement: Operators have a single source for triaging gate failures
  Tasks: `T-LIQG-5`, `T-LIQG-12`
