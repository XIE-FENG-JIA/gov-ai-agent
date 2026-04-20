# Architecture Overview

## Purpose
This document is the repo-level architecture source of truth for Epic 1 to Epic 3.
It describes what already exists in `src/`, what is still planned, and where the hard boundaries are.
It does not replace `program.md` task order or `openspec/` change specs.

## System Shape
The project currently runs as a local-first Python application with four main surfaces:

1. CLI entrypoint via `src/cli/main.py`
2. FastAPI server via `api_server.py` and `src/api/routes/`
3. Web UI via `src/web_preview/app.py`
4. Offline and nightly data ingestion via `src/sources/ingest.py` and `tests/integration/test_sources_smoke.py`

The codebase is still organized around three product layers named in `program.md`:

- `sources`: public-source adapters and ingest persistence for real government documents
- `kb`: knowledge retrieval and storage over ChromaDB-backed collections
- `agents`: requirement parsing, drafting, review, refinement, export

Supporting layers sit around those three cores:

- `core`: shared models, config, constants, LLM abstraction
- `api`: HTTP dependencies, middleware, routes, request/response models
- `graph`: LangGraph orchestration for the document workflow
- `document`: DOCX export
- `web_preview`: Jinja2 + HTMX UI

## High-Level Flow
The happy-path generation flow is:

```text
User input
  -> CLI / API / Web UI
  -> Requirement parsing
  -> Org memory lookup
  -> KB hybrid retrieval (examples + regulations + policies)
  -> Writer draft generation
  -> Formatter
  -> Parallel reviewers
  -> Review aggregation
  -> Optional refine loop
  -> Report build
  -> DOCX export / API response / UI download
```

The public-source ingest flow is separate from generation:

```text
Public source adapter
  -> list()
  -> fetch()
  -> normalize() -> PublicGovDoc
  -> raw snapshot json in kb_data/raw/{adapter}/{yyyymm}/
  -> normalized markdown in kb_data/corpus/{adapter}/
  -> optional later KB ingest / retrieval consumption
```

## Layer Breakdown
### 1. Sources Layer
Current implementation lives in `src/sources/`.
There are 5 source adapters in production code:

| Adapter key | Class | Upstream type | Main job |
|---|---|---|---|
| `mojlaw` | `MojLawAdapter` | law API / JSON | statutes and legal texts |
| `datagovtw` | `DataGovTwAdapter` | JSON API | open dataset metadata |
| `executiveyuanrss` | `ExecutiveYuanRssAdapter` | RSS / XML | Executive Yuan announcements |
| `mohw` | `MohwRssAdapter` | RSS / XML | MOHW notices |
| `fda` | `FdaApiAdapter` | JSON/HTML | FDA notices |

Common source contract:

- `BaseSourceAdapter.list(since_date, limit)`
- `BaseSourceAdapter.fetch(source_id)`
- `BaseSourceAdapter.normalize(raw_payload) -> PublicGovDoc`

Common safety and fallback behavior:

- Shared fallback helpers live in `src/sources/_common.py`
- Offline or malformed upstream payloads can fall back to local fixtures for unit tests
- Fixture fallback is test support, not production success criteria for real ingest baseline
- `tests/integration/test_sources_smoke.py` explicitly blocks fixture fallback for live smoke runs

Persistence layout:

- Raw snapshots: `kb_data/raw/{adapter}/{YYYYMM}/{doc_id}.json`
- Normalized markdown corpus: `kb_data/corpus/{adapter}/{doc_id}.md`
- Synthetic seed examples remain under `kb_data/examples/`

Operational entrypoints:

- CLI ingest: `gov-ai sources ingest`
- CLI source stats: `gov-ai sources status` and `gov-ai sources stats`
- Direct module run: `python -m src.sources.ingest`

### 2. Knowledge Base Layer
Current implementation lives in `src/knowledge/manager.py`.
Storage engine today is ChromaDB `PersistentClient`, not SurrealDB.

Current collections:

- `public_doc_examples`
- `regulations`
- `policies`

Current retrieval behavior:

- Embedding path through `LLMProvider.embed()`
- ChromaDB vector search
- BM25-style keyword search fallback
- Reciprocal Rank Fusion for hybrid results
- TTL caches for search results, embeddings, and fetched document sets

Important current constraint:

- ChromaDB is the active runtime store for retrieval and review
- Epic 2 references SurrealDB, but migration work is frozen
- No new code should assume SurrealDB exists until human review unfreezes that plan

### 3. Agents Layer
Current implementation lives in `src/agents/`.
There are 13 agent-related modules in this directory today.

Main roles:

- `requirement.py`: parse user requirement into `PublicDocRequirement`
- `writer.py`: retrieval-augmented drafting with source-aware post-processing
- `style_checker.py`, `fact_checker.py`, `consistency_checker.py`, `compliance_checker.py`: reviewer agents
- `auditor.py`: format-oriented review and audit output
- `org_memory.py`: organization-specific memory helpers
- `template.py`: template rendering support

The writer is still repo-owned and retrieval-aware.
It is not yet a thin wrapper over `open-notebook` ask-service.
That cutover is planned in Epic 2 and remains future work.

### 4. Orchestration Layer
Current orchestration lives in `src/graph/builder.py`.
LangGraph owns the review loop:

- `parse_requirement`
- `fetch_org_memory`
- `write_draft`
- `format_document`
- `init_review`
- parallel reviewer fan-out
- `aggregate_reviews`
- optional `refine_draft` loop
- `build_report`
- `export_docx`

This is the current production workflow contract.
Any future `open-notebook` integration must preserve these repo-owned checkpoints:

- requirement parsing
- reviewer fan-out
- review aggregation
- export and audit behavior

### 5. Interface Layer
CLI:

- Main Typer app in `src/cli/main.py`
- 49 CLI modules currently exist under `src/cli/`
- Source management is grouped under `sources`
- KB management is grouped under `kb`
- State files auto-relocate to a user-scoped directory when running from repo root via `src/cli/utils.py`
- `GOV_AI_STATE_DIR` can override the default state directory

API:

- `api_server.py` composes FastAPI app, lifespan, middleware, and routers
- Route modules live in `src/api/routes/`
- Current route groups are `health`, `agents`, `workflow`, and `knowledge`
- Shared instances come from `src/api/dependencies.py`

Web UI:

- `src/web_preview/app.py`
- Template-driven server-side UI
- HTMX for incremental page actions
- No Node.js build step

## Data Contracts
### Public Source Contract
`PublicGovDoc` in `src/core/models.py` is the normalized public-document shape.
Important fields:

- `source_id`
- `source_url`
- `source_agency`
- `source_doc_no`
- `source_date`
- `doc_type`
- `raw_snapshot_path`
- `crawl_date`
- `content_md`
- `synthetic`

This model is the handoff point between source adapters and downstream corpus persistence.

### Drafting Contract
`PublicDocRequirement` is the structured input to drafting and review.
It carries:

- doc type
- urgency
- sender
- receiver
- subject
- reason
- action items
- attachments

### Storage Contract
There are two different document worlds in this repo:

- retrieval-ready KB collections in ChromaDB
- source-of-record markdown/json files in `kb_data/`

They are related but not identical.
`kb_data/corpus/` is the normalized source archive.
ChromaDB collections are the retrieval index for generation and review.

## Epic 2 Boundary: `vendor/open-notebook`
The approved boundary is defined by `openspec/changes/02-open-notebook-fork/specs/fork/spec.md`.
The repo must treat `vendor/open-notebook` as a vendored runtime dependency, not as a place to scatter product logic.

Boundary rules:

- `vendor/open-notebook` owns notebook runtime and ask-style orchestration internals
- repo-owned code in `src/` owns Taiwan government document rules
- repo-owned code in `src/` owns review agents and compliance logic
- repo-owned code in `src/` owns export contracts and citation/output policies
- integration must happen through a thin adapter seam, not direct imports everywhere

Practical consequence:

- do not rewrite `src/agents/writer.py` to import vendored modules directly in many places
- add one repo-owned adapter module first
- keep failure fallback to legacy writer flow until integration is proven

Current seam status:

- `src/integrations/open_notebook/` exists and is the only approved import boundary
- `get_adapter(mode)` currently exposes `off`, `smoke`, and `writer` modes
- `off` raises a repo-owned `IntegrationDisabled`
- `smoke` returns a repo-owned in-memory adapter for seam verification
- `writer` is intentionally reserved and still fails loudly until ask-service wiring is implemented
- the seam never silently auto-enables vendor code; operators must opt in with `GOV_AI_OPEN_NOTEBOOK_MODE`

Runtime switch:

- `GOV_AI_OPEN_NOTEBOOK_MODE=off` keeps the integration disabled
- `GOV_AI_OPEN_NOTEBOOK_MODE=smoke` enables `gov-ai open-notebook smoke`
- `GOV_AI_OPEN_NOTEBOOK_MODE=writer` is a guarded future mode, not a live production path

Operator entrypoints:

- `python scripts/smoke_open_notebook.py`
- `python -m src.cli.main open-notebook --help`
- `GOV_AI_OPEN_NOTEBOOK_MODE=smoke python -m src.cli.main open-notebook smoke --question "..." --doc "..."`

## SurrealDB Freeze
SurrealDB is mentioned in `program.md` Epic 2 as a future storage migration.
It is explicitly frozen today.

Freeze conditions:

- no production code should depend on SurrealDB
- no docs should present SurrealDB as current architecture
- migration planning can exist in specs and docs
- implementation starts only after T2.1 and T2.2 are complete and human review clears the freeze

Current storage truth:

- active runtime retrieval store: ChromaDB
- active on-disk ingest archive: `kb_data/raw` and `kb_data/corpus`
- rollback-friendly state: keep ChromaDB until any future migration proves stable

## Current Risks
- `src/cli/kb.py` and `src/cli/generate.py` are still large modules and remain split candidates
- `.git` ACL DENY is still blocking normal commit flow, so documentation and code can be locally correct but not yet cleanly landed
- Epic 1 true-live ingest baseline is still pending; fixture-backed tests are green, but baseline success requires real upstream data
- `vendor/open-notebook` is now importable locally, but only smoke validation is wired; writer integration and fallback cutover are still future work

## Operator Notes
- Run full regression with `pytest tests -q`
- Run live source smoke only with `GOV_AI_RUN_INTEGRATION=1`
- Use `gov-ai sources status --base-dir kb_data` to inspect current source inventory
- Use `GOV_AI_STATE_DIR=<path>` when you need CLI state outside the default user profile directory
- Treat `python scripts/smoke_open_notebook.py` as the first health check for the vendored runtime before touching writer work
- Treat `docs/architecture.md`, `program.md`, and `openspec/` as a matched set when changing architecture

## Change Rule
If a change moves responsibility across layers, update this file first or in the same patch.
