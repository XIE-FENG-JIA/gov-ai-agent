## Problem

The system currently hard-codes two LLM paths: LiteLLM (default) and an
OpenRouter direct REST fallback for embeddings. As we evaluate alternative
providers (Anthropic Claude, OpenAI GPT-4o, local Ollama), the coupling
between `src/core/llm.py` and provider-specific request shapes is growing.

Concrete pain points:
- `_openrouter_rest.py` is a one-off REST shim; adding Anthropic would require
  another shim with different auth headers and request envelope.
- There is no uniform interface for: text-completion, embedding, and streaming.
- Tests mock `src.core.llm._requests.post` or `litellm.embedding` depending on
  which provider is active; swapping providers in CI is fragile.
- Config supports `model`, `embedding_provider`, `embedding_model` but has no
  concept of completion-provider vs embedding-provider separation.

## Solution

Introduce a **provider abstraction layer** in `src/core/providers/`:

```
src/core/providers/
  __init__.py          # re-export LLMProvider protocol
  _protocol.py         # LLMProvider(Protocol): complete(), embed(), stream()
  _litellm.py          # LiteLLMProvider (default)
  _openrouter.py       # OpenRouterProvider (completion + embedding REST)
  _factory.py          # make_provider(config) -> LLMProvider
```

The abstraction decouples `src/core/llm.py` from provider details:
1. `LLMProvider` protocol defines three methods: `complete()`, `embed()`, `stream()`.
2. `_factory.py` reads `config.yaml` key `llm_provider` (default: `litellm`) and
   returns the correct implementation.
3. Existing OpenRouter embedding REST path migrates into `OpenRouterProvider.embed()`.
4. `src/core/llm.py` calls `make_provider(config).complete()` / `.embed()` —
   no longer contains provider-specific branches.
5. Tests mock the provider at the `src.core.providers._factory.make_provider`
   boundary, not at the internal REST/litellm level.

## Non-Goals

- No removal of LiteLLM as the default provider.
- No Anthropic or OpenAI provider implementation in this epic (only spec).
- No streaming implementation in this epic (stub only).
- No breaking changes to CLI or API surfaces.

## Acceptance Criteria

1. `openspec/specs/multi-llm-provider/spec.md` defines `LLMProvider` protocol
   and the three required methods.
2. `src/core/providers/` package created with protocol + factory (≥3 files).
3. `src/core/llm.py` delegates to `make_provider()` instead of inline branches.
4. `tests/test_llm_provider.py` covers: factory dispatch, LiteLLM path,
   OpenRouter path (mocked), and graceful fallback.
5. `python -m pytest tests/test_llm_provider.py -q` = all passed.
6. `python -m pytest tests/test_llm.py -q` = existing 52 tests still pass
   (non-regression).
7. `python scripts/check_fat_files.py --strict` = red=0 (no new fat files).
