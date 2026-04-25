## Problem

Current writer flow is still a single-file, retrieval-light path. Epic 2 requires `ask_service`-style orchestration, review layers, and source-grounded reasoning, but the repo has no approved spec for how an `open-notebook` fork enters the system. Without that contract, integration work will drift and SurrealDB discussions will keep front-running the actual application boundary.

## Solution

Fork `lfnovo/open-notebook` into `vendor/open-notebook` and treat it as the base runtime for retrieval, note context, and `ask_service` flows. Keep this change focused on importability and a thin smoke path. Layer the gov-doc review stack on top with five agents: writer, fact checker, citation checker, compliance checker, and auditor. Reuse the fork for orchestration; keep Taiwan public-document rules in this repo.

## Non-Goals

- No SurrealDB migration in this change
- No full writer rewrite yet
- No production UI redesign
- No benchmark or blind-eval reset

## Acceptance Criteria

1. `vendor/open-notebook` can be imported from the repo environment.
2. A smoke CLI path runs without patching core business logic.
3. Follow-up tasks can wire the five-agent review layer on top of the forked runtime.
