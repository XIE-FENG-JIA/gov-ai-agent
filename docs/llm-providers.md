# LLM Provider Inventory

## Purpose
This note fixes the missing architecture link around `src/core/llm.py`.
Epic 2 should treat that file as the single repo-owned seam for provider selection, connectivity checks, and embedding dispatch.

## What `src/core/llm.py` Owns
`src/core/llm.py` currently owns four things:

1. Provider-facing exception types: `LLMError`, `LLMConnectionError`, `LLMAuthError`, `LLMTimeoutError`
2. Test-double path: `MockLLMProvider`
3. Production runtime path: `LiteLLMProvider`
4. Factory and config merge path: `get_llm_factory(config, full_config=None)`

That means Epic 2 should not scatter provider branching into writer, API routes, or vendored `open-notebook` glue.

## Provider Matrix
Current generation providers handled by `LiteLLMProvider`:

| Provider key | Generation model naming | API key required | Notes |
|---|---|---|---|
| `ollama` | `ollama/{model}` | No | Local-first default |
| `gemini` | `gemini/{model}` unless already prefixed | Yes | LiteLLM cloud path |
| `openrouter` | `openrouter/{model}` unless already prefixed | Yes | Hosted model path |
| `mock` | N/A | No | Deterministic fake text and embeddings for tests |
| `other` | raw model string | Depends | Falls through to LiteLLM as-is |

Current embedding providers handled by `LiteLLMProvider.embed()`:

| Embedding provider | Model mapping | Transport |
|---|---|---|
| `ollama` | `ollama/{embedding_model}` | LiteLLM embedding API |
| `gemini` | `gemini/text-embedding-004` | LiteLLM embedding API |
| `openrouter` | `openrouter/{embedding_model}` | LiteLLM embedding API |
| `local` | sentence-transformers model name | `_LocalEmbedder` singleton |
| `other` | raw embedding model string | LiteLLM embedding API |

## Factory Behavior
`get_llm_factory()` is the control point that merges runtime config with provider defaults from `full_config["providers"]`.

Important behavior:

- Reads active provider from `config["provider"]`, default `ollama`
- Pulls provider defaults from `full_config["providers"][provider]`
- Lets explicit runtime config override provider defaults
- Backfills `api_key` and `model` from provider defaults when caller input is empty
- Returns `MockLLMProvider` only for provider key `mock`
- Returns `LiteLLMProvider` for every non-mock runtime today

Implication for Epic 2:
ask-service wiring should continue to consume a provider built by `get_llm_factory()` instead of creating vendor-specific clients ad hoc.

## Current Call Sites
Main repo-owned consumers already import the provider seam instead of binding directly to LiteLLM:

- CLI boot paths: `src/cli/generate.py`, `src/cli/kb.py`, `src/cli/rewrite_cmd.py`, `src/cli/explain_cmd.py`, `src/cli/quickstart.py`
- API dependency injection: `src/api/dependencies.py`
- KB search and ingest: `src/knowledge/manager.py`
- Review and drafting agents: `src/agents/writer.py`, `src/agents/requirement.py`, `src/agents/editor.py`, `src/agents/auditor.py`, `src/agents/style_checker.py`, `src/agents/consistency_checker.py`, `src/agents/compliance_checker.py`, `src/agents/fact_checker.py`

This is the seam Epic 2 should preserve.
Do not bypass it by importing `litellm` directly from multiple layers.

## Epic 2 Rules
For `T2.0.a`, `T2.6`, and `T2.8`, keep these boundaries:

- `src/core/llm.py` remains the repo-owned provider factory
- `vendor/open-notebook` should receive a ready provider or one thin adapter, not raw config branching everywhere
- Writer migration to ask-service should happen behind one adapter layer
- Embedding behavior for KB retrieval must stay compatible with `src/knowledge/manager.py`
- Connectivity and auth failures should keep surfacing as repo-owned exception classes

## Read Together
Before starting ask-service thin-shell work, read this file together with:

- `docs/architecture.md`
- `docs/integration-plan.md`
- `program.md`
- `src/core/llm.py`

That keeps Epic 2 on one provider seam instead of inventing a second one.
