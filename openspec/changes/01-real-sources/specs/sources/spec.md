# Spec: Real Public Source Intake

## Summary

This change defines the minimum contract for onboarding real public government
document sources into Gov AI Agent. It turns Epic 1 from ad hoc adapter work
into a spec-backed flow with shared metadata, compliance rules, and validation
targets.

## ADDED Requirements

### Requirement: Source adapters use one shared contract

All real-source integrations MUST implement a common adapter contract so the
ingest pipeline can treat each public source consistently.

The contract MUST define:

- `list(since_date=None)` to return upstream summaries newer than an optional cutoff
- `fetch(doc_id)` to return one raw upstream payload
- `normalize(raw)` to convert one upstream payload into a `PublicGovDoc`

#### Scenario: List returns source summaries

- **GIVEN** an adapter for a public source
- **WHEN** `list()` is called
- **THEN** it returns iterable summary records with enough data to choose a document id

#### Scenario: Normalize returns the internal model

- **GIVEN** one raw upstream payload
- **WHEN** `normalize(raw)` succeeds
- **THEN** the result is a `PublicGovDoc`

### Requirement: Normalized real-source documents preserve provenance

Every normalized public document MUST keep the minimum provenance fields needed
for traceability, ingest dedupe, and downstream citation.

The required `PublicGovDoc` fields are:

- `source_id`
- `source_url`
- `source_agency`
- `source_doc_no`
- `source_date`
- `doc_type`
- `raw_snapshot_path`
- `crawl_date`
- `content_md`
- `synthetic`

#### Scenario: Required provenance is present

- **GIVEN** a normalized real public document
- **THEN** `source_id`, `source_url`, `source_agency`, `doc_type`, `crawl_date`, and `content_md` are non-blank
- **AND** `synthetic` is `false`

### Requirement: Real-source ingestion follows public-data compliance rules

Every adapter and ingest run MUST stay within the project's public-data and
compliance boundary.

The compliance rules are:

- only public government sources SHALL be onboarded
- robots.txt restrictions MUST be respected
- request pacing MUST be at least 2 seconds between upstream requests unless the upstream explicitly allows more
- the User-Agent MUST identify the project as `GovAI-Agent/1.0`
- raw upstream payloads MUST be retained for auditability

#### Scenario: Adapter config includes safe defaults

- **GIVEN** a new real-source adapter
- **THEN** it includes a default rate limit of at least 2 seconds
- **AND** it sends the project User-Agent on upstream HTTP requests

### Requirement: Synthetic content stays outside real-source retrieval

Synthetic fixtures SHALL exist only for tests and offline development, and they MUST
remain explicitly marked and MUST NOT be treated as real-source corpus entries.

#### Scenario: Synthetic fixture is excluded from real corpus semantics

- **GIVEN** a fixture or generated sample used for testing
- **WHEN** it is normalized or stored
- **THEN** it is marked with `synthetic=true`
- **AND** it is not counted as a real public source document

### Requirement: The first approved source set is intentionally narrow

The first approved candidate sources for this change are `data.gov.tw`,
`law.moj.gov.tw`, and Executive Yuan RSS. Additional sources SHALL be added
later only through follow-up change sets, and they are out of scope for this
first change set.

#### Scenario: New work maps to the approved first slice

- **GIVEN** follow-up implementation tasks for this change
- **THEN** they target the approved first source set before expanding to lower-confidence sources
