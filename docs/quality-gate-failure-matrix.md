# Quality Gate Failure Matrix

This matrix is the operator runbook for `gov-ai kb gate-check --source <name>` and `gov-ai kb rebuild --quality-gate`. The gate blocks records before they enter the staging corpus, so fixes should happen at the adapter, source endpoint, or quality policy layer before rerunning a rebuild.

## Failure Matrix

| Failure | Trigger | Operator triage | `--require-live` interaction |
| --- | --- | --- | --- |
| `LiveIngestBelowFloor` | Adapter returns fewer records than `expected_min_records`. | Run `gov-ai kb gate-check --source <name> --format json`; confirm upstream HTTP status and pagination; lower the floor only if the public source truly publishes fewer records for this window. | `--require-live` also rejects empty or fallback-only live runs; this error is stricter because it names the configured floor and actual count. |
| `SchemaIntegrityError` | A record fails `PublicGovDoc` validation or has empty `source_url`, `source_agency`, `source_doc_no`, or `source_date`. | Inspect the failing record id in JSON output; fix the adapter normalizer; add a regression test for the missing field; avoid filling fields with synthetic placeholders. | `--require-live` may still see a live fetch as present, but the quality gate blocks promotion until required provenance fields survive normalization. |
| `StaleRecord` | `fixture_fallback=true` while fallback is disallowed, or `crawl_date` is older than `freshness_window_days`. | Check whether the adapter fell back to fixtures; refresh endpoint parsing or cache TTL; if the source is archival by design, adjust that adapter's freshness window in `src/sources/quality_config.py`. | `--require-live` prevents fixture-only rebuilds; this failure also catches old live/cache records that would otherwise pass a simple non-empty live check. |
| `SyntheticContamination` | A record has `synthetic=true`. | Remove synthetic examples from the live adapter path; keep demos under fixture/example corpora; verify the adapter emits `synthetic=false` only for traceable public records. | `--require-live` protects live fetch presence, not content authenticity; the quality gate preserves the Epic 5 only-real invariant by refusing synthetic records. |

## Triage Flow

1. Reproduce the failure with `gov-ai kb gate-check --source <name> --format json`.
2. Read the named `error_type`, `adapter`, and record details from the JSON payload.
3. Fix the adapter normalizer, source fetch path, or per-adapter policy.
4. Rerun the single-source gate check before running `gov-ai kb rebuild --only-real --quality-gate`.
5. Use `--require-live` together with `--quality-gate` when promoting corpus data, so live availability and record quality are both enforced.

## Policy Boundaries

- Do not bypass `SyntheticContamination`; synthetic records must never enter the active retrieval corpus.
- Do not paper over `SchemaIntegrityError` with placeholder agency, date, URL, or document numbers.
- Treat `LiveIngestBelowFloor` as an upstream or pagination signal first, not as an automatic config change.
- Treat `StaleRecord` as a cache/fallback issue unless the adapter policy explicitly models an archival source.
