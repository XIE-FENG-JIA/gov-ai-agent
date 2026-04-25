# audit Specification

## Purpose

Epic 3 already fixed citation output and DOCX verification metadata, but the
review layer still has no approved contract for how citation traceability is
audited before export. Current behavior is spread across
`src/agents/fact_checker.py`, `src/agents/auditor.py`,
`src/agents/validators.py`, and `src/knowledge/realtime_lookup.py`:

- `FactChecker` mixes real-time law verification, document-type cross checks,
  and semantic similarity checks
- `FormatAuditor` runs citation-related validators, but only as part of a broad
  format audit path
- there is no repo-owned `citation_checker` seam that focuses on source
  traceability, orphan references, and missing evidence links as one review
  responsibility
- there is no approved failure matrix for cases where retrieval evidence,
  reference definitions, or law-verification data are missing

That gap blocks Epic 4. Without a change package, future audit work would keep
drifting between validators, LLM prompts, and export verification without one
stable definition of "citation audit passed".

## Requirements

### Requirement: Citation audit stays repo-owned and source-grounded

Gov AI Agent MUST keep citation-traceability review in repo-owned code rather
than hiding it inside generic prompts or export-only validation.

The protected repo-owned audit layers are:

- a dedicated citation-checker seam for traceability findings
- fact-checker use of repo evidence and law-verification state
- auditor/editor aggregation of citation findings into review output

#### Scenario: citation review runs through a dedicated seam

- **GIVEN** a generated draft with legal claims or source footnotes
- **WHEN** Epic 4 citation audit runs
- **THEN** citation-traceability findings are produced by a repo-owned review
  seam
- **AND** downstream audit output can distinguish citation failures from generic
  formatting advice


<!-- @trace
source: 04-audit-citation
updated: 2026-04-25
code:
  - engineer-log.md
  - results.log
  - program.md
-->

---
### Requirement: Citation audit uses repo evidence and verification state

Citation audit MUST combine repo evidence links with real-time verification
state when judging whether a legal claim is trustworthy.

The audit inputs MUST support:

- reference definitions or equivalent evidence links
- repo knowledge-base evidence identifiers when available
- `realtime_lookup` verification results for law and article existence

#### Scenario: legal claim is checked against evidence and verification data

- **GIVEN** a draft cites a law, article, or authority claim
- **WHEN** the citation audit evaluates that claim
- **THEN** it checks for evidence linkage and verification state
- **AND** unverifiable or ungrounded claims are surfaced as findings instead of
  being silently accepted


<!-- @trace
source: 04-audit-citation
updated: 2026-04-25
code:
  - engineer-log.md
  - results.log
  - program.md
-->

---
### Requirement: Citation audit failures fail loudly before export handoff

The review layer MUST fail loudly when citation traceability is missing or
degraded before the document is treated as audit-clean.

The required loud-failure cases include:

- orphan footnotes or missing reference definitions
- legal claims without evidence linkage
- regulations or article numbers that verification rejects
- degraded verification upstreams that remove confidence in citation review

#### Scenario: missing or degraded citation traceability blocks clean handoff

- **GIVEN** a generated draft contains one of the required loud-failure cases
- **WHEN** citation audit completes
- **THEN** the review output contains explicit citation-related findings
- **AND** downstream audit/export code does not treat the draft as citation-clean

<!-- @trace
source: 04-audit-citation
updated: 2026-04-25
code:
  - engineer-log.md
  - results.log
  - program.md
-->