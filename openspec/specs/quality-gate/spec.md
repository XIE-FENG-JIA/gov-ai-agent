# quality-gate Specification

## Purpose

TBD - created by archiving change '06-live-ingest-quality-gate'. Update Purpose after archive.

## Requirements

### Requirement: Quality gate evaluates records across volume, schema, and provenance dimensions

Gov AI Agent MUST apply a quality gate between every public-source `fetch()`
output and the staging corpus merge. The gate evaluates each record against
three dimensions (volume floor, schema integrity, provenance signal) and raises
one of four named errors (`LiveIngestBelowFloor`, `SchemaIntegrityError`,
`StaleRecord`, `SyntheticContamination`) when a dimension check fails.

#### Scenario: volume below adapter floor raises LiveIngestBelowFloor

- **GIVEN** an adapter declares `expected_min_records=5`
- **WHEN** its `fetch()` returns only 2 records
- **THEN** the gate raises `LiveIngestBelowFloor` and the batch is not merged

#### Scenario: missing provenance keys raise SchemaIntegrityError

- **GIVEN** a record missing `source_doc_no`
- **WHEN** the gate evaluates it against `PublicGovDoc` schema
- **THEN** the gate raises `SchemaIntegrityError(record_id, missing_fields=["source_doc_no"])`

#### Scenario: stale or synthetic records are filtered under only-real path

- **GIVEN** records with `fixture_fallback=true`, `synthetic=true`, or
  `crawl_date` older than `freshness_window_days`
- **WHEN** the gate runs alongside `--require-live` / only-real rebuild
- **THEN** the gate raises `StaleRecord` or `SyntheticContamination`
  respectively, and those records never reach active retrieval


<!-- @trace
source: 06-live-ingest-quality-gate
updated: 2026-04-25
code:
  - engineer-log.md
  - results.log
  - program.md
-->

---
### Requirement: gate-check CLI returns structured GateReport with pass-rate exit code

`gov-ai kb gate-check --source <name>` MUST emit a JSON `GateReport` on stdout
(adapter, records_in/out, rejected_by breakdown, pass_rate, duration, timestamp)
and exit 0 when `pass_rate ≥ 0.5`, exit 1 otherwise.

#### Scenario: gate-check reports success when pass-rate clears threshold

- **GIVEN** an adapter with 7 input records and 2 stale rejections
- **WHEN** `gov-ai kb gate-check --source mohw_rss` runs
- **THEN** stdout carries a valid `GateReport` JSON with `pass_rate=0.71`
- **AND** exit code is 0

#### Scenario: rebuild --quality-gate aborts on any adapter gate failure

- **GIVEN** `gov-ai kb rebuild --quality-gate` is invoked across adapters
- **WHEN** one adapter raises any `QualityGateError`
- **THEN** rebuild aborts immediately, subsequent adapters are not run
- **AND** a structured error report is printed to stderr

<!-- @trace
source: 06-live-ingest-quality-gate
updated: 2026-04-25
code:
  - engineer-log.md
  - results.log
  - program.md
-->