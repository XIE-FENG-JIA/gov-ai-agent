# Baseline Capability: Real Public Sources

## Summary

Gov AI Agent keeps one repo-owned baseline contract for onboarding and ingesting
real public government document sources. Change-specific specs may extend this
baseline, but they must not weaken provenance, compliance, or synthetic-data
separation.

## Baseline Requirements

### Shared adapter contract

All real-source integrations MUST implement one shared adapter contract so the
ingest pipeline can treat sources consistently.

The baseline adapter contract includes:

- `list(since_date=None, limit=3)` for upstream summaries
- `fetch(doc_id)` for one raw upstream payload
- `normalize(raw)` for conversion into `PublicGovDoc`

### Normalized document shape

All normalized real-source records MUST map into `PublicGovDoc`.

The baseline required fields are:

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
- `fixture_fallback`

Core provenance fields such as `source_id`, `source_url`, `source_agency`,
`doc_type`, `crawl_date`, and `content_md` MUST be non-blank.

### Compliance boundary

Real-source ingestion MUST stay inside the project's public-data boundary.

The baseline compliance rules are:

- only public government sources MAY be onboarded
- robots.txt restrictions MUST be respected
- request pacing MUST be at least 2 seconds unless upstream policy explicitly allows more
- the User-Agent MUST identify the project as `GovAI-Agent/1.0`
- raw upstream payloads MUST be retained for auditability

### Synthetic-data separation

Synthetic or fixture-backed content MUST stay outside real-source semantics.

The baseline rules are:

- fixtures and generated examples MUST be explicitly marked
- synthetic records MUST set `synthetic=true`
- fixture-backed records MUST set `fixture_fallback=true`
- synthetic or fixture-backed corpus entries MUST NOT be counted as live-source success

### Ingest behavior

The repo-owned ingest path MUST persist both raw and normalized outputs.

The baseline ingest guarantees are:

- raw snapshots are written for later audit
- normalized markdown corpus entries preserve source provenance
- live re-ingest MAY upgrade an older fixture-backed corpus file into a real one
- require-live flows MUST fail loudly when a source falls back to fixtures

## Non-Goals

This baseline does not approve any one source mix, live-network guarantee, or
benchmark target by itself. Those belong to change-specific plans and tasks.
