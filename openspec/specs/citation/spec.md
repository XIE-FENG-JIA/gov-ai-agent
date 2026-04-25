# citation Specification

## Purpose

TBD - created by archiving change '03-citation-tw-format'. Update Purpose after archive.

## Requirements

### Requirement: Citation output uses one canonical section marker

Generated public-document drafts MUST use `## 引用來源` as the canonical section
marker for reviewed source citations.

### Scenario: reviewed draft carries canonical citation heading

- **WHEN** a writer/export pipeline emits reviewed citations
- **THEN** the generated draft includes a `## 引用來源` section
- **AND** downstream tooling does not invent alternate headings for the same payload

<!-- @trace
source: 03-citation-tw-format
updated: 2026-04-25
code:
  - results.log
  - program.md
  - engineer-log.md
-->