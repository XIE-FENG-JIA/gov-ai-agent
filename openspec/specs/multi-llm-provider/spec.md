# multi-llm-provider Specification

## Purpose

Define the stable provider abstraction used by completion, embedding, and
future streaming paths so `src/core/llm.py` does not grow provider-specific
branches for each backend.

## Requirements

### Requirement: LLM providers expose one uniform protocol

Provider implementations MUST satisfy `LLMProvider` with three methods:

- `complete(prompt: str, **kwargs: object) -> str`
- `embed(texts: list[str]) -> list[list[float]]`
- `stream(prompt: str, **kwargs: object) -> Iterator[str]`

`complete()` MUST return a single text string. `embed()` MUST return one vector
per input text and preserve input order. `stream()` MUST yield text chunks, or
raise `NotImplementedError` when a provider does not yet support streaming.

Provider failures MUST propagate as the existing provider or domain exceptions
so callers keep their current error-handling contracts.

#### Scenario: protocol can be imported from provider package

- **GIVEN** the application imports `LLMProvider` from `src.core.providers`
- **WHEN** import resolution runs
- **THEN** the protocol is available without importing provider internals

### Requirement: Factory dispatches configured providers

The provider factory MUST expose `make_provider(config) -> LLMProvider` from
`src.core.providers`. It MUST read the existing `provider` config key and
return:

- `OpenRouterProvider` when `provider == "openrouter"`
- `LiteLLMProvider` for the default LiteLLM-compatible providers
- `ValueError` for unknown provider names

The default provider path MUST remain LiteLLM-compatible and preserve existing
Ollama/default behavior.

#### Scenario: known providers dispatch to the expected implementation

- **GIVEN** config sets `provider` to `openrouter`
- **WHEN** `make_provider(config)` runs
- **THEN** it returns `OpenRouterProvider`
- **AND** LiteLLM-compatible provider names return `LiteLLMProvider`

#### Scenario: unknown provider fails loudly

- **GIVEN** config sets `provider` to an unsupported name
- **WHEN** `make_provider(config)` runs
- **THEN** it raises `ValueError` with known provider guidance

### Requirement: Core LLM path delegates through providers

`src/core/llm.py` MUST call `make_provider(config).complete()` and
`make_provider(config).embed()` instead of containing provider-specific REST or
LiteLLM branches. Provider-specific HTTP dependencies MUST stay in provider
modules or lower-level provider helpers, not in `src/core/llm.py`.

#### Scenario: completion delegates through provider abstraction

- **GIVEN** the configured provider implements `complete()`
- **WHEN** the core completion path runs
- **THEN** it calls the provider method and returns the provider text result

#### Scenario: embedding delegates through provider abstraction

- **GIVEN** the configured provider implements `embed()`
- **WHEN** the core embedding path runs
- **THEN** it calls the provider method and returns the provider vectors

### Requirement: OpenRouter keeps direct REST embeddings

`OpenRouterProvider.embed()` MUST use the direct OpenRouter embeddings REST path
and MUST wrap REST, JSON, schema, and network failures as `EmbeddingError`.
`OpenRouterProvider.complete()` MUST keep using LiteLLM completion with the
`openrouter/` model prefix when needed.

#### Scenario: OpenRouter embedding succeeds through REST

- **GIVEN** OpenRouter embedding config includes model and API key
- **WHEN** `OpenRouterProvider.embed([text])` runs
- **THEN** it posts to the OpenRouter embedding endpoint through the REST helper
- **AND** it returns the parsed embedding vector

#### Scenario: OpenRouter embedding failure is typed

- **GIVEN** the OpenRouter REST helper raises a provider, JSON, schema, or network error
- **WHEN** `OpenRouterProvider.embed([text])` runs
- **THEN** it raises `EmbeddingError`

<!-- @trace
source: 18-multi-llm-provider-abstraction
updated: 2026-04-26
code:
  - src/core/providers/__init__.py
  - src/core/providers/_protocol.py
  - src/core/providers/_litellm.py
  - src/core/providers/_openrouter.py
  - src/core/llm.py
  - tests/test_llm_provider.py
  - tests/test_llm.py
-->
