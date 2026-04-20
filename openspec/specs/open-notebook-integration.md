# Baseline Capability: Open Notebook Integration

## Summary

Gov AI Agent keeps a repo-owned baseline seam for any future `open-notebook`
adoption. Change-specific work may deepen the integration, but it must keep the
vendor boundary, fallback rules, and review-agent ownership intact.

## Baseline Requirements

### Narrow vendor seam

The vendored runtime MUST stay behind a repo-owned adapter or service seam.

The baseline ownership split is:

- `vendor/open-notebook` owns vendored runtime code
- `src/integrations/open_notebook/` owns the repo-facing seam
- unrelated repo modules MUST NOT scatter direct vendor imports

### Adapter contract

The repo-owned seam MUST expose a stable ask/index contract.

The baseline contract includes:

- `OpenNotebookAdapter.ask(question, docs=None) -> AskResult`
- `OpenNotebookAdapter.index(docs) -> int`
- `AskResult.answer_text`
- `AskResult.evidence`
- `AskResult.diagnostics`
- `AskResult.used_fallback`

Evidence payloads MUST stay visible to downstream review and citation layers.

### Runtime modes

The integration seam MUST support controlled runtime modes through
`GOV_AI_OPEN_NOTEBOOK_MODE`.

The baseline supported modes are:

- `off` keeps the integration disabled by default
- `smoke` uses a repo-owned in-memory smoke adapter
- `writer` is reserved for future deep integration and MUST fail loudly until wired

### Fallback behavior

The repo MUST own fallback behavior when the vendor runtime is absent or not
ready.

The baseline fallback rules are:

- missing or incomplete vendor checkout MUST raise a clear setup error
- the legacy writer path MUST remain available until explicit cutover
- the system MUST NOT silently degrade into unreviewed pure generation

### Review-layer ownership

Taiwan-specific review policy MUST remain repo-owned even if the vendored
runtime is adopted.

The protected repo-owned layers are:

- writer orchestration
- fact checker
- citation checker
- compliance checker
- auditor

### Freeze boundary

The first approved slice for this capability stays intentionally narrow.

The baseline frozen items are:

- SurrealDB migration
- full writer cutover
- production UI replacement
- broad benchmark resets

Human review is REQUIRED before any storage migration or full writer cutover.

## Non-Goals

This baseline does not promise a ready vendor checkout, working writer mode, or
production cutover. It only fixes the minimum seam and guardrails that future
changes must honor.
