# Spec: Citation Taiwan Format

## Summary

Canonical `## 引用來源` section marker, metadata preservation through export,
and DOCX verification against repo evidence — deltas to the citation contract.

## ADDED Requirements

### Requirement: Citation output uses one canonical section marker

Generated public-document drafts MUST use `## 引用來源` as the canonical section
marker for reviewed source citations.

### Scenario: reviewed draft carries canonical citation heading

- **WHEN** a writer/export pipeline emits reviewed citations
- **THEN** the generated draft includes a `## 引用來源` section
- **AND** downstream tooling does not invent alternate headings for the same payload

## Requirement: Citation metadata survives across generation and export

The repo MUST preserve citation metadata keys `source_doc_ids`,
`citation_count`, `ai_generated`, and `engine` from reviewed generation output
through exported artifacts.

### Scenario: export preserves citation metadata

- **WHEN** a reviewed draft is exported
- **THEN** the exported artifact keeps `source_doc_ids`, `citation_count`,
  `ai_generated`, and `engine`
- **AND** citation reviewers and verifier flows can read the same keys

## Requirement: DOCX export preserves citation verification metadata

DOCX export MUST retain enough citation metadata for later verification against
repo evidence.

### Scenario: docx can be verified later

- **WHEN** a generated DOCX is saved
- **THEN** the artifact exposes citation verification metadata
- **AND** a future verifier does not need to guess citation provenance from free text alone

## Requirement: Verify flow compares exported docx state against knowledge-base evidence

The repo-owned verify flow MUST compare exported citation state against
knowledge-base evidence instead of trusting document text alone.

### Scenario: verify checks exported docx against repo evidence

- **WHEN** `gov-ai verify <docx>` runs on an exported file
- **THEN** it reads exported citation metadata and source references
- **AND** it compares them against repo evidence or source-grounded review payloads
