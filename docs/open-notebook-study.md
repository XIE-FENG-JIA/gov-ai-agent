# Open Notebook Study

## Purpose
This note closes T2.1 / P1.10 with a repo-first study of the planned
`vendor/open-notebook` integration.

The local checkout is still incomplete, so this document does not pretend to be
a code-reading report of the real upstream runtime.
It is an implementation study based on the approved repo specs, current seam
code, and the observable local vendor state.

## Sources Read
The study is grounded in these repo-owned sources:

1. `openspec/changes/02-open-notebook-fork/specs/fork/spec.md`
2. `openspec/changes/02-open-notebook-fork/tasks.md`
3. `docs/integration-plan.md`
4. `docs/architecture.md`
5. `docs/llm-providers.md`
6. `src/integrations/open_notebook/__init__.py`
7. `src/integrations/open_notebook/config.py`
8. `src/integrations/open_notebook/stub.py`
9. `src/cli/open_notebook_cmd.py`
10. `tests/test_integrations_open_notebook.py`

## Local Facts
Observed in this workspace today:

- `vendor/open-notebook/` exists
- that directory currently contains only `.git/`
- there is no checked-out Python package under `vendor/open-notebook/`
- `src/integrations/open_notebook/` already exists as a repo-owned seam skeleton
- `pytest tests/test_integrations_open_notebook.py -q` passes
- `python -m src.cli.main open-notebook --help` shows the smoke CLI

This means Epic 2 is no longer "zero code".
The seam is present.
What is still missing is the real vendor runtime and a validated import path.

## What The Fork Is Supposed To Own
Per the approved spec, the forked runtime is expected to own:

- notebook runtime bootstrapping
- retrieval orchestration
- ask-style execution flow
- vendor-internal router state

Per the same spec, Gov AI must keep these layers repo-owned:

- Taiwan public-document rules
- writer policy
- fact checker
- citation checker
- compliance checker
- auditor
- export contracts

This is the key architectural constraint.
`open-notebook` is not the product.
It is one runtime dependency behind a narrow seam.

## ask_service Contract Inference
The spec and integration plan both center the future integration around
`ask_service`.

The most likely repo-facing `ask_service` contract is:

```text
ask_service.ask(question, docs/context, options) -> answer + evidence + diagnostics
```

For this repo, `ask_service` cannot be treated as a plain text generator.
The repo needs `ask_service` to return three stable outputs:

1. answer text
2. retrieved evidence list
3. diagnostics metadata

The current seam already models that shape through `AskResult`:

- `answer_text`
- `evidence`
- `diagnostics`
- `used_fallback`

That is a good first approximation of the future `ask_service` wrapper because
it preserves exactly what downstream review needs.

## Evidence Shape Required By Gov AI
Gov AI cannot accept an `ask_service` response that drops provenance.

The minimum evidence payload needed by the repo is already visible in
`RetrievedEvidence`:

- `title`
- `snippet`
- `source_url`
- `rank`

This should be considered the minimum adapter-normalized shape even if the real
vendor `ask_service` returns a richer object.

Why this matters:

- writer needs source-aware rewrite behavior
- citation checker needs stable source references
- fact checker needs evidence text or snippet context
- auditor needs a traceable answer-to-source record

If the vendored `ask_service` returns answer text without evidence, that is not
"partial success".
That is an explicit integration failure for this repo.

## Current Repo-Owned Seam
The current seam code already encodes the first approved slice.

### `config.py`
Owns:

- `GOV_AI_OPEN_NOTEBOOK_MODE`
- `GOV_AI_OPEN_NOTEBOOK_VENDOR_PATH`
- mode normalization for `off|smoke|writer`

This is correct because runtime selection belongs to repo-owned operator logic,
not vendor internals.

### `__init__.py`
Owns:

- `OpenNotebookAdapter` protocol
- `probe_vendor_runtime()`
- `get_adapter()`

Important behavior already implemented:

- `off` returns `OffAdapter`
- `smoke` returns `SmokeAdapter`
- `writer` checks vendor readiness first
- invalid vendor state raises `IntegrationSetupError`

That matches the spec requirement that missing vendor runtime must fail clearly.

### `stub.py`
Owns the safe pre-vendor implementations:

- `OffAdapter`
- `SmokeAdapter`
- `AskResult`
- `RetrievedEvidence`

`SmokeAdapter` is especially useful because it proves the repo-side shape before
real vendor wiring starts.

### `src/cli/open_notebook_cmd.py`
Owns the smoke-only operator path:

- `gov-ai open-notebook smoke --question "..."`

This matches the "import and smoke only" scope from the spec.

## Extension Seams Still Needed
The current skeleton is enough for smoke mode, but not enough for real vendor
execution.

The missing seams are:

### 1. Vendor loader
A dedicated loader should eventually isolate:

- `sys.path` bootstrapping
- import-time error capture
- one-time runtime initialization
- version reporting

Today `probe_vendor_runtime()` only checks filesystem shape.
It does not attempt a real import.

### 2. Service wrapper
The future wrapper should translate from vendor `ask_service` output into the
repo-owned `AskResult` contract.

That wrapper is where:

- vendor exceptions become repo exceptions
- vendor evidence becomes `RetrievedEvidence`
- fallback state becomes explicit diagnostics

### 3. Writer toggle
`WriterAgent` must eventually call the seam only behind
`GOV_AI_OPEN_NOTEBOOK_MODE=writer`.

The default path must stay legacy writer until human review clears cutover.

## Provider Boundary
`docs/llm-providers.md` establishes another important rule:

- provider selection stays in `src/core/llm.py`
- vendor code should receive a ready provider or one thin bridge
- repo code should not scatter raw LiteLLM/OpenRouter branching into the new
  seam

This means future `ask_service` integration should not invent a second provider
factory.

The fork may internally speak to a model backend, but repo operator policy
should still flow through one repo-owned provider seam.

## Storage Boundary
The spec and integration plan are aligned here:

- ChromaDB is the active runtime retrieval store today
- `kb_data/raw` and `kb_data/corpus` remain the source archive
- SurrealDB migration stays frozen

So the first usable `ask_service` integration must accept repo-provided context
without requiring SurrealDB to exist.

If the upstream runtime assumes SurrealDB immediately, that becomes either:

- a wrapper problem to isolate, or
- a proof that the current adoption slice is too early

It must not silently force T2.3 ahead of review.

## Fallback Rules Confirmed
The local seam and the approved spec agree on fallback:

- `smoke` mode fails loudly when vendor is absent
- `writer` mode must keep legacy writer available
- no silent downgrade into unreviewed pure generation

That is the correct policy for a regulated, source-grounded drafting system.

For Gov AI, a "successful" answer without review-safe evidence is worse than an
explicit failure because it looks trustworthy while breaking auditability.

## 6. Import Smoke Result
Current measured result in this workspace after adding
`scripts/smoke_open_notebook.py`:

```text
status=vendor-incomplete message=vendor checkout is incomplete: .git contains [config.lock, description, hooks, info] but is missing [HEAD, config, objects, refs] under vendor\open-notebook version=?
```

Interpretation:

- the smoke path now distinguishes a half-finished clone from a generic missing checkout
- the failure is no longer the vague `ImportError: No module named 'open_notebook'`
- there is still no checked-out Python package under `vendor/open-notebook`
- the local vendor dir specifically looks like an interrupted clone, not a usable git checkout

Practical consequence:

- P0.X is complete because the repo now has a stable importability probe
- T2.3 cannot start until Admin or a later sync produces a real vendor checkout
- any future dependency miss will surface as `status=import-error missing=<module>`

This keeps the next step honest.
The repo now knows whether it is blocked by:

- missing checkout
- missing dependency
- successful import

## Risks
The biggest near-term risks are:

1. vendor checkout remains incomplete, so integration stalls at filesystem probe
2. future vendor runtime may return evidence in a shape that loses source URLs
3. provider configuration may get duplicated between repo code and vendor glue
4. writer cutover may happen before review agents receive the same evidence
5. SurrealDB pressure may leak back into the first integration slice

## Next Build Order
Recommended next order after this study:

1. complete a real `vendor/open-notebook` checkout instead of the current interrupted clone
2. keep using the existing seam skeleton as the single boundary
3. only after a real checkout exists, implement a loader that attempts import
4. then wire a real service wrapper around vendor `ask_service`
5. only after answer + evidence survive intact, consider writer mode

## Exit Criteria For Real Vendor Readiness
The fork should be treated as actually ready for the next slice only when all of
these are true:

- `vendor/open-notebook` contains checked-out project files
- a real import works in the current Python environment
- the runtime can execute one minimal `ask_service` call
- the wrapper returns answer text and evidence together
- writer fallback remains intact when vendor init fails

Until then, the correct posture is:

- seam skeleton: done
- repo study: done
- vendor importability: not done
- writer cutover: not done
