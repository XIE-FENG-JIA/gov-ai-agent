# Baseline Capability: Taiwan Citation Export And Verification

## Summary

Gov AI Agent keeps a repo-owned baseline contract for Taiwan public-document
citation output, export metadata, and verification. Change-specific work may
expand the workflow, but it must preserve one canonical citation marker,
stable metadata keys, and repo-evidence verification.

## Baseline Requirements

### Canonical citation marker

Generated public-document drafts MUST use `## 引用來源` as the canonical
section marker for reviewed source citations.

The baseline guardrails are:

- reviewed drafts emit one `## 引用來源` section
- downstream tooling MUST NOT invent alternate headings for the same payload
- template, writer, and export paths stay aligned on the same marker

### Citation metadata continuity

The repo MUST preserve citation metadata keys `source_doc_ids`,
`citation_count`, `ai_generated`, and `engine` from reviewed generation output
through exported artifacts.

The baseline preserved fields are:

- `source_doc_ids`
- `citation_count`
- `ai_generated`
- `engine`

Citation reviewers and verifier flows MUST be able to read the same keys
without reconstructing them from free text.

### DOCX verification metadata

DOCX export MUST retain enough citation metadata for later verification against
repo evidence.

The baseline export contract is:

- exported DOCX carries citation verification metadata
- later verification does not guess provenance from rendered prose alone
- reviewed source linkage survives the export boundary

### Repo-evidence verification

The repo-owned verify flow MUST compare exported citation state against
knowledge-base evidence instead of trusting document text alone.

The baseline verify contract is:

- `gov-ai verify <docx>` reads exported citation metadata and source references
- verification compares exported state against repo evidence or
  source-grounded review payloads
- missing metadata or missing evidence MUST fail loudly

## Non-Goals

This baseline does not promise broader citation UX, alternate export formats,
or non-repo verification backends. It only fixes the minimum citation/output
contract that future changes must honor.
