# Spec: Citation Audit Review Boundary

## Summary

This change defines the repo-owned audit contract for checking whether
generated legal claims remain traceable to evidence, footnotes, and verified
law citations before export handoff.

## ADDED Requirements

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
