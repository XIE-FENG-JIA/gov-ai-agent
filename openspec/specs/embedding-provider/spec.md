# embedding-provider Specification

## Purpose

Define embedding-provider contracts that must stay stable across retrieval,
knowledge-base rebuild, and unit-test validation paths.

## Requirements

### Requirement: OpenRouter embeddings use direct REST fallback

When `embedding_provider` is `openrouter`, Gov AI Agent MUST call the
OpenRouter embeddings REST endpoint directly instead of routing through
`litellm.embedding()`. This is required because LiteLLM can reject OpenRouter
embedding models with an unmapped-provider error even when generation through
OpenRouter is valid.

The REST request MUST:

- target `https://openrouter.ai/api/v1/embeddings` unless an explicit embedding base URL is configured
- send `Authorization: Bearer <embedding_api_key>`
- send JSON containing the configured embedding model and the input text
- cap the input text at 8000 characters before transmission

The REST response MUST return `data[0].embedding` as the embedding vector.
Provider error envelopes MUST raise an embedding failure rather than silently
falling back to deterministic or local embeddings.

#### Scenario: OpenRouter embed sends authenticated REST request

- **GIVEN** `LiteLLMProvider` is configured with `embedding_provider=openrouter`, model `nvidia/llama-nemotron-embed-vl-1b-v2:free`, and an embedding API key
- **WHEN** `embed("hello")` runs
- **THEN** the provider posts to `https://openrouter.ai/api/v1/embeddings`
- **AND** the request includes a Bearer authorization header
- **AND** the JSON body includes the configured model and input text

#### Scenario: OpenRouter embed does not call LiteLLM embedding

- **GIVEN** OpenRouter is the configured embedding provider
- **WHEN** `embed()` runs successfully
- **THEN** `litellm.embedding()` is not required for that path
- **AND** unit tests mock `src.core.llm._requests.post` to prove the REST seam

#### Scenario: OpenRouter embed caps large input

- **GIVEN** an input string longer than 8000 characters
- **WHEN** `embed()` sends the OpenRouter request
- **THEN** the transmitted input is truncated to 8000 characters
- **AND** the provider still parses `data[0].embedding` on success

#### Scenario: OpenRouter provider error fails loudly

- **GIVEN** OpenRouter returns a JSON error envelope
- **WHEN** `embed()` receives the response
- **THEN** the embedding call raises an embedding failure with the provider message
- **AND** no silent deterministic fallback is used for trusted retrieval

<!-- @trace
source: 17-embedding-provider-rest-fallback
updated: 2026-04-26
commits:
  - cf26345 feat(llm): OpenRouter direct REST API for embeddings + log
  - 00330c0 fix(llm,kb): T-NEMOTRON-EMBEDDING-VALIDATE-CLOSE — OpenRouter embedding text truncation + ChromaDB schema fix + KB rebuild 400 docs + Recall@5=100%
  - e0d673a feat(llm): T-LLM-EMBED-TEST-FIX — mock _requests.post for OpenRouter embedding tests
code:
  - src/core/llm.py
  - tests/test_llm.py
  - docs/embedding-validation.md
-->
