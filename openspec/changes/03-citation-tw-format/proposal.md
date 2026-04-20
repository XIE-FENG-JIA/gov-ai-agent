## Problem

Current export and review flows can mention sources, but the repo still lacks a
single approved contract for Taiwan-style citation output. Citation behavior is
split across `src/knowledge/realtime_lookup.py`, `src/document/exporter.py`,
review agents, and ad hoc metadata assumptions. There is no change proposal that
defines when a generated document MUST emit a `## 引用來源` section, which
source identifiers must survive into the exported artifact, or how a future
`gov-ai verify <docx>` path should compare the finished DOCX against knowledge
base evidence. That gap blocks Epic 3 because implementation work would
otherwise guess at formatting, verification scope, and metadata keys.

## Solution

Create change `03-citation-tw-format` as the contract for citation output in
Taiwan government documents. The first slice should define one repo-owned
citation pipeline that future code can implement behind stable interfaces,
whether the logic lands in a new `src/core/citation.py` module or a similar
repo-owned seam. The approved output must support:

- a normalized `## 引用來源` section in generated markdown and exported DOCX
- source metadata keys `source_doc_ids`, `citation_count`, `ai_generated`, and
  `engine`
- alignment between writer output, citation checker review, and DOCX export
- a future `gov-ai verify <docx>` flow that checks exported citations against
  repo knowledge-base evidence instead of trusting free-form text

This proposal does not force the final module layout today. It fixes the target
behavior, metadata contract, and verification boundary so follow-up tasks can be
implemented without drifting from Taiwan public-document expectations.

## Non-Goals

- No full citation engine implementation in this change
- No DOCX parser or verifier CLI shipping yet
- No knowledge-base schema migration
- No redesign of the existing five-agent review stack

## Acceptance Criteria

1. `openspec/changes/03-citation-tw-format/` exists with proposal, tasks, and
   change spec files.
2. The proposal defines `## 引用來源` as the canonical citation section marker.
3. The proposal defines metadata keys `source_doc_ids`, `citation_count`,
   `ai_generated`, and `engine` for downstream export and verification.
4. Follow-up tasks can map directly to formatter/exporter/verify work without
   reopening the citation contract.
