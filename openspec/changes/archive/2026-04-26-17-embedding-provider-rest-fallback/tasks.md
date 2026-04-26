# Tasks: 17-embedding-provider-rest-fallback

- [x] **T17.1** Record OpenRouter embedding REST fallback in OpenSpec.
  Requirements:
  - `embedding_provider=openrouter` bypasses `litellm.embedding()` and calls OpenRouter `/embeddings` directly.
  - The spec cites the implementation history: `cf26345`, `00330c0`, `e0d673a`.
  Validation: `spectra validate --changes 17-embedding-provider-rest-fallback` returns valid.
  Commit: this change.

- [x] **T17.2** Bind the contract to existing unit coverage.
  Requirements:
  - Tests mock `src.core.llm._requests.post`, not `litellm.embedding`, for the OpenRouter embedding path.
  - Tests assert REST URL, Bearer header, JSON model/input body, success vector parsing, and failure envelope handling.
  Validation: `pytest tests/test_llm.py -q` = 52 passed.
  Commit: `e0d673a feat(llm): T-LLM-EMBED-TEST-FIX — mock _requests.post for OpenRouter embedding tests`.

- [x] **T17.3** Preserve production validation evidence.
  Requirements:
  - The direct REST embedding path remains tied to Nemotron/OpenRouter KB rebuild evidence.
  - Validation evidence includes 400-document KB rebuild and Recall@5 = 5/5.
  Validation: `docs/embedding-validation.md` records OpenRouter direct REST API, 400 docs, and Recall@5 = 100%.
  Commit: `00330c0 fix(llm,kb): T-NEMOTRON-EMBEDDING-VALIDATE-CLOSE — OpenRouter embedding text truncation + ChromaDB schema fix + KB rebuild 400 docs + Recall@5=100%`.
