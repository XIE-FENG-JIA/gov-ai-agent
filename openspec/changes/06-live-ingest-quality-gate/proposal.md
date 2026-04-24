## Problem

Epic 1 (`01-real-sources`) shipped seven public adapters and `gov-ai kb rebuild --only-real`, so the corpus has a real-source path. Epic 5 (`05-kb-governance`) added `--require-live` and post-rebuild verification. But there is no shared **quality gate** between live ingest and corpus promotion: a fetcher can return zero records, fall through to fixture fallback, or import unreadable PDFs, and nothing on the path stops it from landing in the active retrieval set.

Symptoms already observed:

- MOHW fetcher silently returns `[]` while `--require-live` blocks the rebuild but leaves no diagnostic
- FDA adapter's first probe took five rounds of debug because no schema check ran on returned payloads
- Corpus regression from 200 → 173 markdown files went undetected for two rounds because no SLO existed

Without an explicit quality contract, scaling the corpus past 300 docs amplifies these silent failures.

## Solution

Define a **live-ingest quality gate** that every adapter run must pass before its output enters the staging corpus. Treat it as a thin policy layer between adapter `fetch()` and the existing `kb rebuild --only-real` path. Scope this change to the contract + a reference enforcement helper, not a full rewrite of any adapter.

Three contract dimensions:

1. **Volume floor** — each adapter declares a minimum yield (`expected_min_records` per run); below floor → `LiveIngestBelowFloor`, surfaced to operator instead of silent empty
2. **Schema integrity** — each record must round-trip through `PublicGovDoc` (already from Epic 1) and have non-empty `source_url`, `source_agency`, `source_doc_no`, `source_date`
3. **Provenance signal** — refuse records flagged `synthetic=true` or `fixture_fallback=true`; refuse records whose `crawl_date` is older than `freshness_window_days`

Reference enforcement: `src/sources/quality_gate.py` implementing `QualityGate.evaluate(records, adapter_name) -> GateReport`, with a CLI entrypoint `gov-ai kb gate-check --source <name>` and a one-line wire from `kb rebuild` so existing flows pick it up automatically when `--quality-gate` is set.

## Non-Goals

- No new adapter implementations (Epic 1 already covers seven sources)
- No SurrealDB or storage migration (T2.3 frozen)
- No UI or dashboard work (separate `audit-trail-ui` proposal can pick that up)
- No re-design of `PublicGovDoc` — reuse as-is
- No retroactive enforcement on the current 173-doc corpus (gate applies to future ingests; corpus migration is a follow-up)

## Acceptance Criteria

1. A change folder exists for `06-live-ingest-quality-gate` with this proposal + tasks.md + specs/quality-gate/spec.md committed for team review.
2. The proposal names the three contract dimensions and the reference enforcement seam.
3. Follow-up implementation can map directly to:
   - `QualityGate.evaluate` + per-adapter `expected_min_records` config
   - `src/sources/quality_gate.py` + tests
   - `gov-ai kb gate-check` CLI subcommand
   - `kb rebuild --quality-gate` flag wiring
4. Failure modes are explicitly named: `LiveIngestBelowFloor`, `SchemaIntegrityError`, `StaleRecord`, `SyntheticContamination`.
5. The spec keeps synthetic-content gating consistent with Epic 5 (`only-real` invariant must not weaken).
