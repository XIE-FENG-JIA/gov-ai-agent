## Problem

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

## Solution

Create change `04-audit-citation` as the contract for citation-traceability
review in Gov AI Agent. The first slice keeps scope narrow and repo-owned:

- add a dedicated `src/agents/citation_checker.py` seam for citation
  traceability checks
- strengthen `FactChecker` so citation-related factual review stays aligned with
  repo evidence and `realtime_lookup` verification results
- define how `FormatAuditor` and future editor/auditor flows aggregate citation
  checker results instead of burying them inside generic format findings
- require a regression-focused failure matrix for missing evidence, orphan
  footnotes, unverifiable laws, and degraded upstream verification

This proposal does not lock the final class layout beyond one repo-owned
citation checker seam. It fixes the behavior boundary: a generated document must
fail review loudly when its legal claims are not traceable to evidence,
footnotes, or verified law citations.

## Non-Goals

- No full Epic 4 implementation in this change
- No redesign of Epic 3 export metadata keys or `gov-ai verify <docx>`
- No replacement of `realtime_lookup` upstream behavior
- No benchmark, UI, or storage changes

## Acceptance Criteria

1. `openspec/changes/04-audit-citation/` exists with proposal, tasks, and
   `specs/audit/spec.md`.
2. The proposal defines citation audit as a repo-owned review layer distinct
   from export formatting.
3. The proposal names the first required implementation slices: citation
   checker seam, fact-checker strengthening, auditor integration, and failure
   matrix coverage.
4. Follow-up tasks can map directly to Epic 4 without reopening the audit
   boundary.
