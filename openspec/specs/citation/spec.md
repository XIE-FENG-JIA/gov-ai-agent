# citation Specification

## Purpose

Current export and review flows can mention sources, but the repo still lacks a
single approved contract for Taiwan-style citation output. Citation behavior is
split across `src/knowledge/realtime_lookup.py`, `src/document/exporter.py`,
review agents, and ad hoc metadata assumptions. There is no change proposal that
defines when a generated document MUST emit a `## 引用來源` section, which
source identifiers must survive into the exported artifact, or how a future
`gov-ai verify <docx>` path should compare the finished DOCX against knowledge
base evidence. That gap blocks Epic 3 because implementation work would
otherwise guess at formatting, verification scope, and metadata keys.

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