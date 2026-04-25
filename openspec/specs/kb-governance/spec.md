# kb-governance Specification

## Purpose

TBD - created by archiving change '05-kb-governance'. Update Purpose after archive.

## Requirements

### Requirement: Active retrieval excludes synthetic or fixture-backed corpus entries

Gov AI Agent MUST treat `synthetic=true` or `fixture_fallback=true` corpus
entries as ineligible for active retrieval in rebuild, rewrite, and verify
flows unless a task explicitly opts into synthetic fixtures for test-only work.

The protected active-retrieval paths include:

- `gov-ai kb rebuild --only-real`
- rewrite and E2E corpus loading used for reviewed citations
- exported DOCX verification against repo evidence

#### Scenario: only real corpus entries are eligible for trusted retrieval

- **GIVEN** a corpus directory contains both real and fixture-backed markdown
  files
- **WHEN** an operator runs an only-real rebuild or a rewrite/verify flow that
  consumes trusted evidence
- **THEN** entries marked `synthetic=true` or `fixture_fallback=true` are
  excluded from the active evidence set
- **AND** only real corpus entries remain eligible for trusted retrieval


<!-- @trace
source: 05-kb-governance
updated: 2026-04-25
code:
  - program.md
  - results.log
  - engineer-log.md
-->

---
### Requirement: Live ingest and retirement rules fail loudly and leave audit evidence

Gov AI Agent MUST fail loudly when a supposedly live ingest path falls back to
fixtures, and corpus retirement or replacement actions MUST leave auditable
disk evidence instead of silently mutating the active corpus set.

The required governance signals are:

- `--require-live` exits with a loud failure instead of silently accepting
  fixture-backed results
- live re-ingest SHALL upgrade an older fixture-backed corpus file into a real
  one only when the replacement preserves provenance and raw snapshot evidence
- fixture-backed or retired corpus artifacts MUST remain traceable through
  archive, raw snapshot, or report outputs

#### Scenario: fixture fallback is rejected for live ingest

- **GIVEN** an operator runs live ingest with `--require-live`
- **AND** the upstream source can only return fixture-backed content
- **WHEN** the ingest completes
- **THEN** the command fails loudly instead of counting the run as live success
- **AND** the resulting report or retained files still show what source was
  retired, replaced, or rejected


<!-- @trace
source: 05-kb-governance
updated: 2026-04-25
code:
  - program.md
  - results.log
  - engineer-log.md
-->

---
### Requirement: Only-real rebuilds require explicit post-rebuild verification

Gov AI Agent MUST treat `gov-ai kb rebuild --only-real` as an operational
rebuild boundary that is incomplete until post-rebuild verification confirms
the rebuilt index still resolves exported citations back to active repo
evidence.

The required post-rebuild verification signals include:

- imported versus skipped counts for the rebuild
- preserved `source_doc_ids` and citation metadata in exported DOCX outputs
- repo-evidence verification that resolves citation metadata only to active
  corpus entries after the rebuild

#### Scenario: only-real rebuild is closed by evidence verification

- **GIVEN** an operator finishes `gov-ai kb rebuild --only-real`
- **WHEN** the rebuild result is validated
- **THEN** the rebuild reports which corpus entries were imported or skipped by
  provenance status
- **AND** exported citation metadata still resolves to active repo evidence
- **AND** the rebuild is not treated as complete until that verification passes

<!-- @trace
source: 05-kb-governance
updated: 2026-04-25
code:
  - program.md
  - results.log
  - engineer-log.md
-->