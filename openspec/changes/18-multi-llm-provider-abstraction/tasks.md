# Tasks: 18-multi-llm-provider-abstraction

- [x] **T18.1** Define `LLMProvider` protocol in `src/core/providers/_protocol.py`.
  Requirements:
  - `LLMProvider(Protocol)` with three methods: `complete(prompt, **kwargs) -> str`,
    `embed(texts: list[str]) -> list[list[float]]`, `stream(prompt, **kwargs) -> Iterator[str]`.
  - Each method has a docstring describing the contract (input types, return shape, error behaviour).
  Validation: `python -c "from src.core.providers import LLMProvider; print(LLMProvider)"` exits 0.
  Commit: this epic's first commit.

- [x] **T18.2** Create `LiteLLMProvider` implementing `LLMProvider`.
  Requirements:
  - `complete()` delegates to existing `litellm.completion()` path.
  - `embed()` delegates to existing `litellm.embedding()` path.
  - `stream()` raises `NotImplementedError` (stub for future).
  - No behaviour change vs current `src/core/llm.py` default path.
  Validation: `python -m pytest tests/test_llm.py -q` = 52 passed.
  Commit: migration commit.

- [x] **T18.3** Migrate `OpenRouterProvider` embedding REST shim.
  Requirements:
  - `OpenRouterProvider.embed()` encapsulates the existing direct REST call from
    `src/core/llm.py` (`POST /api/v1/embeddings`, Bearer auth, 8000-char cap).
  - `OpenRouterProvider.complete()` delegates to `litellm.completion()` with
    `openrouter/` prefix (current behaviour).
  Validation: `python -m pytest tests/test_llm.py -q` = 52 passed (no regression).
  Commit: migration commit.

- [x] **T18.4** Implement `make_provider(config) -> LLMProvider` factory.
  Requirements:
  - Reads `config["llm_provider"]` (default: `"litellm"`).
  - Returns `LiteLLMProvider` for `"litellm"`, `OpenRouterProvider` for `"openrouter"`.
  - Raises `ValueError` for unknown provider names.
  Validation: `python -m pytest tests/test_llm_provider.py::test_factory_dispatch -q` = 3 passed.
  Commit: factory commit.

- [x] **T18.5** Refactor `src/core/llm.py` to delegate through `make_provider()`.
  Requirements:
  - Remove inline `if embedding_provider == "openrouter":` branch.
  - Call `make_provider(config).embed(texts)` and `make_provider(config).complete(prompt)`.
  - LLM module must not import `requests` directly after refactor.
  Validation: `python -m pytest tests/ -q --ignore=tests/test_e2e.py` = all passed.
  Commit: refactor commit.

- [x] **T18.6** Add `tests/test_llm_provider.py` covering factory and both providers.
  Requirements:
  - `test_factory_dispatch`: 3 cases (litellm, openrouter, unknown → ValueError).
  - `test_litellm_complete`: mock `litellm.completion`, assert return.
  - `test_litellm_embed`: mock `litellm.embedding`, assert return.
  - `test_openrouter_embed_success`: mock `requests.post`, assert URL/headers/body.
  - `test_openrouter_embed_failure`: mock 4xx response → raises `EmbeddingError`.
  Validation: `python -m pytest tests/test_llm_provider.py -q` = ≥5 passed.
  Commit: test commit.
