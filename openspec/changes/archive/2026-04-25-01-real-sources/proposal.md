## Problem

Current knowledge-base intake still depends on synthetic examples and manual file drops. Epic 1 requires public, real government documents, but the repo has no approved source-onboarding spec, no acceptance boundary for provenance metadata, and no shared definition of "real-source ready". This blocks adapter work from landing with a stable contract.

## Solution

Create a first change proposal for real public sources. Scope the first slice to three high-confidence sources already researched: `data.gov.tw`, `law.moj.gov.tw`, and Executive Yuan RSS. Define a minimal ingestion contract:

- only public government sources
- store `source_url`, `source_agency`, `source_doc_no`, `source_date`, `crawl_date`, and raw snapshot path
- normalize each document into markdown with traceable metadata
- mark synthetic fixtures separately and exclude them from real-source retrieval paths

This proposal authorizes follow-up work for one adapter-first implementation path, starting with the clearest licensed source.

## Non-Goals

- No bulk crawl implementation in this change
- No SurrealDB or storage-engine migration
- No UI or citation-format redesign
- No commitment yet to all 10 candidate sources

## Acceptance Criteria

1. A change folder exists for `01-real-sources` with this proposal committed for team review.
2. The proposal names the initial three candidate sources and the required provenance metadata.
3. Future implementation can map directly to Epic 1 tasks: adapter scaffold, normalized `PublicGovDoc`, and incremental ingest pipeline.
4. The proposal keeps synthetic content out of the "real public source" definition.
