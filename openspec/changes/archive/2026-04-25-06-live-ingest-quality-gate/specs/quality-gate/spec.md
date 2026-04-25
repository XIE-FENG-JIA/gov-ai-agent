# Spec: live-ingest quality gate

## Scope

The quality gate is a thin policy layer that sits between every public-source `fetch()` call and the staging corpus merge. It does not replace any adapter, retrieval index, or rebuild script — it observes and approves output.

Module: `src/sources/quality_gate.py`
CLI: `gov-ai kb gate-check --source <name>`, `gov-ai kb rebuild --quality-gate`

## ADDED Requirements

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

## Three Contract Dimensions

### 1. Volume Floor

Each adapter declares `expected_min_records` (e.g., MOHW `≥ 5`, MOJ-Law `≥ 50`, FDA `≥ 1`). A run that returns fewer records than the floor raises `LiveIngestBelowFloor` instead of silently merging an empty batch.

### 2. Schema Integrity

Each record must round-trip through `PublicGovDoc` (Epic 1) without missing required fields. The four mandatory provenance keys are:

- `source_url` — non-empty https URL
- `source_agency` — non-empty Chinese agency name
- `source_doc_no` — non-empty document number (機關發文字號)
- `source_date` — ISO-8601 date

Records missing any field raise `SchemaIntegrityError(record_id, missing_fields)`.

### 3. Provenance Signal

- **Synthetic contamination**: any record with `synthetic=true` flag in `source_agency` metadata raises `SyntheticContamination` (consistent with Epic 5's `only-real` invariant)
- **Stale fixture fallback**: any record marked `fixture_fallback=true` or whose `crawl_date` is older than the adapter's `freshness_window_days` raises `StaleRecord`

## Named Failure Types

```
class QualityGateError(RuntimeError): ...
class LiveIngestBelowFloor(QualityGateError): ...
class SchemaIntegrityError(QualityGateError): ...
class StaleRecord(QualityGateError): ...
class SyntheticContamination(QualityGateError): ...
```

## GateReport (success path)

```python
@dataclass
class GateReport:
    adapter: str
    records_in: int
    records_out: int
    rejected_by: dict[str, int]   # error_type -> count
    pass_rate: float              # records_out / records_in
    duration_seconds: float
    timestamp: datetime
```

## Per-Adapter Quality Config

`src/sources/quality_config.py`:

```python
QUALITY_CONFIG: dict[str, dict] = {
    "mojlaw":              {"expected_min_records": 50, "freshness_window_days": 90,  "allow_fallback": False},
    "datagovtw":           {"expected_min_records": 10, "freshness_window_days": 30,  "allow_fallback": False},
    "executive_yuan_rss":  {"expected_min_records": 5,  "freshness_window_days": 14,  "allow_fallback": False},
    "mohw_rss":            {"expected_min_records": 5,  "freshness_window_days": 14,  "allow_fallback": False},
    "fda_api":             {"expected_min_records": 1,  "freshness_window_days": 30,  "allow_fallback": False},
    "pcc":                 {"expected_min_records": 1,  "freshness_window_days": 30,  "allow_fallback": False},
}
```

Adapters not listed inherit a permissive default `{expected_min_records: 1, freshness_window_days: 365, allow_fallback: True}` and emit a `WARNING` log so config drift is visible.

## CLI Behavior

### `gov-ai kb gate-check --source <name>`

```
$ gov-ai kb gate-check --source mohw_rss
{
  "adapter": "mohw_rss",
  "records_in": 7,
  "records_out": 5,
  "rejected_by": {"StaleRecord": 2},
  "pass_rate": 0.71,
  "duration_seconds": 1.8,
  "timestamp": "2026-04-24T15:30:12+00:00"
}
```

Exit 0 when `pass_rate ≥ 0.5`, exit 1 otherwise.

### `gov-ai kb rebuild --quality-gate`

When the flag is set, every adapter's output is gated before merging. A single adapter failure aborts the rebuild with a structured error report on stderr; subsequent adapters are not run.

## Interaction With Existing Invariants

- **`--require-live`** (Epic 5) still applies first; gate runs on records that survived live-only filtering
- **`--prune-fixture-fallback`** is now a no-op when `--quality-gate` is set (the gate's `StaleRecord` rule supersedes it)
- **`only-real` rebuild path** stays the active default. Gate strengthens it; cannot weaken it.

## Human Review Requirement

Before any adapter raises `expected_min_records` floor above the values in this spec, human review is required and must be recorded in `docs/quality-gate-policy-changes.md`. Storage migration (T2.3) and full writer cutover stay frozen until that review is complete.

## Validation Hooks

- `pytest tests/test_quality_gate.py -q` — gate logic, all four failure types
- `pytest tests/test_quality_config.py -q` — per-adapter config defaults
- `pytest tests/test_kb_gate_check_cli.py -q` — CLI report shape + exit codes
- `pytest tests/test_kb_rebuild_cli.py -q -k gate` — rebuild integration with `--quality-gate`
