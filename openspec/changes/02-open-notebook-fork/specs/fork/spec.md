# Spec: Open Notebook Fork Boundary

## Summary

This change defines the integration boundary for adopting a forked
`open-notebook` runtime inside Gov AI Agent. The fork becomes the base
orchestration layer for `ask_service`-style retrieval and response assembly,
while this repo keeps Taiwan public-document rules, review agents, and export
logic.

## ADDED Requirements

### Requirement: The forked runtime stays behind a narrow import boundary

Gov AI Agent MUST treat `vendor/open-notebook` as a vendored runtime dependency,
not as a place for Taiwan-specific business rules.

The approved boundary is:

- `vendor/open-notebook` owns notebook runtime, retrieval orchestration, and
  `ask_service` execution flow
- `src/` owns public-document schemas, review agents, citation formatting, and
  export rules
- repo code MUST import the fork through a thin adapter or service layer rather
  than scattering direct imports across unrelated modules

#### Scenario: Writer code uses one integration seam

- **GIVEN** a Gov AI writer flow that needs fork capabilities
- **WHEN** it calls into the vendored runtime
- **THEN** the call goes through one repo-owned integration seam
- **AND** Taiwan-specific prompt and policy logic remains in `src/`

### Requirement: Ask-service integration preserves source-grounded review flow

The forked runtime MUST support a repo-owned `ask_service` integration contract
that keeps retrieval output available for downstream review and citation checks.

The contract MUST preserve:

- the final answer text
- the retrieved source list or equivalent evidence payload
- a stable request/response shape that repo review agents can inspect

#### Scenario: Downstream review receives answer and evidence

- **GIVEN** a successful ask-service call through the vendored runtime
- **WHEN** the repo passes that result into writer, fact checker, or citation checker
- **THEN** both answer text and evidence metadata are available to downstream code

### Requirement: The first integration slice is import and smoke only

This change MUST keep the first approved scope intentionally narrow so Epic 2
does not front-run storage migration or a full writer rewrite.

The first approved slice includes:

- cloning or vendoring `open-notebook`
- confirming repo imports work in the current Python environment
- documenting the adapter boundary
- defining a smoke path for one minimal ask-style invocation

The first approved slice excludes:

- SurrealDB migration
- production UI replacement
- benchmark reset
- replacing all existing Gov AI flows in one step

#### Scenario: Storage migration stays frozen

- **GIVEN** this change is under implementation
- **WHEN** follow-up tasks are planned
- **THEN** SurrealDB work remains blocked until the integration plan is reviewed

### Requirement: The repo owns fallback behavior when the fork is absent or fails

Gov AI Agent MUST define a repo-level fallback strategy for cases where
`vendor/open-notebook` is missing, import fails, or the ask-service smoke path
cannot execute.

The fallback rules are:

- fail fast with a clear operator-facing error when the vendored fork is missing
- keep existing writer path available until the new seam is proven
- do not silently degrade into unreviewed pure generation

#### Scenario: Missing vendor path produces an explicit failure

- **GIVEN** the integration seam is invoked without a valid vendored fork
- **WHEN** import or initialization fails
- **THEN** the system raises a clear setup error
- **AND** operators can still use the pre-fork writer path until cutover

### Requirement: Five-agent review layering stays repo-owned

The five-agent review stack for public-document generation MUST remain defined in
this repo even after the forked runtime is introduced.

The protected repo-owned layers are:

- writer
- fact checker
- citation checker
- compliance checker
- auditor

#### Scenario: Fork adoption does not move review policy into vendor code

- **GIVEN** a follow-up change that integrates the vendored runtime
- **WHEN** review agents are wired on top
- **THEN** the review policy and Taiwan-specific checks remain implemented in `src/agents`
