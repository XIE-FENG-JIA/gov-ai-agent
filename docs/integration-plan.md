# Integration Plan: Gov AI Agent x `vendor/open-notebook`

## Status
This document defines the repo-owned integration seam for Epic 2.
It is based on the current repo architecture and the approved spec in
`openspec/changes/02-open-notebook-fork/specs/fork/spec.md`.

Current constraint:

- `vendor/open-notebook` is importable in this workspace through the repo-owned seam
- the current slice is still smoke-first and does not prove production writer readiness
- therefore this plan is architecture-first, implementation-ready, and still intentionally narrow

Human review is still required before any SurrealDB migration or full writer cutover.

## Decision
Choose **Fork + thin adapter seam**.

Do not choose:

- **overlay everywhere**: would scatter vendor imports across `src/agents/`, `src/api/`, and CLI code
- **full rewrite**: would front-run storage and workflow changes before the fork is even proven

The repo will integrate `open-notebook` through one repo-owned boundary module.
All Taiwan-specific drafting rules, review policy, and export contracts stay in `src/`.

## Approved Integration Seam
The seam lives in repo-owned code, not under `vendor/`.

Proposed module boundary:

```text
src/integrations/open_notebook/
  __init__.py
  models.py          # request/response dataclasses shared by repo code
  loader.py          # vendor path detection and import bootstrapping
  service.py         # ask-style service adapter used by writer / smoke CLI
  errors.py          # explicit setup/runtime errors
```

Call shape:

```text
src/agents/writer.py or smoke CLI
  -> OpenNotebookService.ask(request)
  -> loader resolves vendor runtime once
  -> vendored ask_service executes
  -> repo-normalized response returns answer + evidence + diagnostics
```

Hard rules:

- `src/agents/writer.py` must not import vendored modules directly
- `src/api/` must not know vendor internals
- `src/graph/` continues to orchestrate the Gov AI workflow
- vendored code stays replaceable as a dependency boundary

## Request and Response Contract
The first stable contract should be repo-defined dataclasses.

Proposed request shape:

```python
OpenNotebookAskRequest(
    prompt: str,
    user_query: str,
    top_k: int,
    trace_id: str | None,
    metadata_filters: dict[str, str] | None,
)
```

Proposed response shape:

```python
OpenNotebookAskResponse(
    answer_text: str,
    evidence: list[RetrievedEvidence],
    provider_name: str,
    latency_ms: int | None,
    used_fallback: bool,
    diagnostics: dict[str, str],
)
```

`RetrievedEvidence` must preserve enough data for downstream review:

- source title
- source url
- snippet or extracted text
- source type / collection
- retrieval rank or score when available
- raw vendor payload reference when debugging is enabled

This contract is repo-owned even if the vendor runtime uses a different internal shape.

## Ownership Split
### Vendor-owned
- ask-style orchestration internals
- vendor retrieval execution
- notebook runtime bootstrapping
- any fork-specific internal router state

### Repo-owned
- `PublicDocRequirement` parsing
- Taiwan public-document prompt rules
- writer post-processing and citation normalization
- fact checker, citation checker, compliance checker, auditor
- export, audit log, and operator-facing errors
- fallback policy

## Writer Integration Path
The writer cutover must be staged.

Stage 1:

- keep current `WriterAgent.write_draft()` as production path
- add `OpenNotebookService` beside it
- expose a smoke-only path that does not alter normal generation

Stage 2:

- add an explicit runtime toggle to writer
- use vendor ask-service only when the operator enables it
- normalize vendor answer into current writer post-processing

Stage 3:

- pass vendor evidence into repo review agents
- keep current review fan-out in `src/graph/` and `src/agents/editor.py`

Stage 4:

- only after human review, consider deeper workflow adoption
- SurrealDB remains frozen until after this review

## Runtime Toggle
Do not use silent auto-detection for production behavior.

Use an explicit mode:

```text
GOV_AI_OPEN_NOTEBOOK_MODE=off|smoke|writer
```

Meaning:

- `off`: current repo behavior only
- `smoke`: allow smoke CLI or test path, but do not touch production writer flow
- `writer`: allow `WriterAgent` to invoke the adapter seam

Optional supporting env vars:

- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL=elephant-alpha`
- `GOV_AI_OPEN_NOTEBOOK_VENDOR_PATH`
- `GOV_AI_OPEN_NOTEBOOK_TIMEOUT_SECONDS`

The final env list can expand after T2.1 vendor study, but the mode flag should be fixed now.

## Local Setup Notes
Local operators should treat this integration as an opt-in seam, not as the
default runtime.

Recommended local setup:

1. keep `vendor/open-notebook/` present and importable
2. set `GOV_AI_OPEN_NOTEBOOK_MODE=smoke` for smoke validation first
3. export `OPENROUTER_API_KEY` before any vendor-backed ask flow
4. pin `OPENROUTER_MODEL=elephant-alpha` for the current study slice unless a
   later review approves a different default
5. switch to `GOV_AI_OPEN_NOTEBOOK_MODE=writer` only when the operator wants to
   exercise the explicit legacy writer fallback contract

Operator reminder:

- `writer` mode is not the default production path
- setup or runtime failure in `writer` mode must fall back to the legacy writer
- missing evidence is a hard integration failure, not a soft success
- current non-goals stay in force during local setup; do not treat smoke success as cutover approval

## Fallback Policy
Fallback must be explicit and review-safe.

Failure cases:

- vendor path missing
- import bootstrap fails
- ask-service initialization fails
- ask request times out
- vendor returns answer without evidence payload

Repo response:

1. Raise a clear setup/runtime error from `src/integrations/open_notebook/errors.py`
2. If mode is `smoke`, fail the smoke path loudly
3. If mode is `writer`, log the adapter failure and fall back to the legacy writer path
4. Mark fallback in diagnostics so operators can see that the vendor path did not run
5. Never silently downgrade into an unreviewed pure-generation path

## Review-Agent Layering
The vendor runtime can help produce an answer and evidence bundle.
It does not replace Gov AI review policy.

Repo-owned review sequence stays:

1. Writer or ask-service answer assembly
2. Format / structure normalization
3. Fact checker
4. Citation checker
5. Compliance checker
6. Auditor / report build

Evidence handoff rule:

- the exact evidence bundle returned by `OpenNotebookService.ask()` must remain available to downstream reviewers
- reviewer code may enrich or summarize the evidence, but must not discard the original source list before audit/report steps

## Data and Storage Boundary
Current storage truth stays unchanged:

- ChromaDB remains the active retrieval store
- `kb_data/raw` and `kb_data/corpus` remain the source archive
- no code in this slice may depend on SurrealDB

Implication:

- the integration seam must accept repo-provided context and return answer/evidence
- it must not force a storage migration just to make smoke or writer mode work

## Implementation Slice Mapping
This plan defines the follow-up build order.

### T2.3 Service adapter
- create `src/integrations/open_notebook/`
- add request/response models and loader/service wrappers
- unit-test missing-vendor and import-failure paths

### T2.4 Smoke path
- add a CLI or script that calls `OpenNotebookService.ask()`
- use `GOV_AI_OPEN_NOTEBOOK_MODE=smoke`
- no writer replacement yet

### T2.5 Writer toggle
- add explicit writer mode wiring
- preserve existing writer as the default path

### T2.6 Evidence preservation
- make evidence available to fact/citation/compliance review code
- keep a stable payload contract

### T2.7 Fallback hardening
- test all missing-vendor and init-failure branches
- keep legacy writer available

### T2.8 Operator docs
- document env vars, local setup, and current non-goals

### T2.9 Human review gate
- no SurrealDB migration or full cutover before review

## Review Gate
Human review is required before these moves:

- any SurrealDB migration work
- replacing the default writer path
- moving review policy into vendor code
- changing API contracts to expose vendor internals directly

Frozen until review:

- `T2.3` data-layer migration in `program.md`
- any claim that `open-notebook` is the production runtime

## Current Non-Goals
The current non-goals for this slice are intentionally strict:

- no SurrealDB migration work
- no full writer cutover
- no review-agent policy move into vendor code
- no benchmark reset tied to the fork adoption
- no removal of the legacy writer fallback path

## Validation Markers
This document must continue to contain the following anchors for task validation:

- `integration seam`
- `fallback`
- `review agents`
- `vendor/open-notebook`
