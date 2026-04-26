## Problem

OpenRouter embeddings shipped before their provider contract was captured in
OpenSpec. The implementation history is now spread across three commits:

- `cf26345 feat(llm): OpenRouter direct REST API for embeddings + log`
- `00330c0 fix(llm,kb): T-NEMOTRON-EMBEDDING-VALIDATE-CLOSE — OpenRouter embedding text truncation + ChromaDB schema fix + KB rebuild 400 docs + Recall@5=100%`
- `e0d673a feat(llm): T-LLM-EMBED-TEST-FIX — mock _requests.post for OpenRouter embedding tests`

The code is green, but the spec is missing. That creates the same governance
failure as prior commit-message drift: a real behavior can land, be tested,
and still be invisible to future acceptance audits.

## Solution

Add an `embedding-provider` capability that records the OpenRouter direct REST
fallback contract:

1. When `embedding_provider=openrouter`, `LiteLLMProvider.embed()` MUST call
   `POST /api/v1/embeddings` directly instead of `litellm.embedding()`,
   because LiteLLM rejects OpenRouter embeddings as an unmapped provider.
2. The request MUST include Bearer auth, the configured model, and a bounded
   input payload capped at 8000 characters.
3. The response MUST be parsed from `data[0].embedding`; provider error
   envelopes MUST become embedding failures instead of silent fallback.
4. The behavior MUST have tests that mock `src.core.llm._requests.post` and
   assert URL, headers, body, success parsing, and failure handling.

## Non-Goals

- No code changes to `src/core/llm.py`; commits `cf26345`, `00330c0`, and
  `e0d673a` already landed the implementation and tests.
- No live OpenRouter call in unit tests. Network-dependent validation stays in
  the documented KB rebuild / Recall@5 evidence path.
- No generic provider abstraction rewrite. This change only documents the
  OpenRouter embedding REST fallback seam.

## Acceptance Criteria

1. `openspec/changes/17-embedding-provider-rest-fallback/specs/embedding-provider/spec.md` defines the REST fallback requirement and test scenarios.
2. `tasks.md` maps spec documentation to commits `cf26345`, `00330c0`, and `e0d673a`.
3. `spectra validate --changes 17-embedding-provider-rest-fallback` returns valid.
4. `pytest tests/test_llm.py -q` passes with OpenRouter embedding requests mocked at `src.core.llm._requests.post`.
