# Embedding Validation — Nemotron via OpenRouter

**Date**: 2026-04-26  
**Task**: T-NEMOTRON-EMBEDDING-VALIDATE-CLOSE  
**Model**: `nvidia/llama-nemotron-embed-vl-1b-v2:free`  
**Provider**: OpenRouter (direct REST API)  
**Embedding dim**: 2048

## Background

`litellm` 1.77.0 does not support OpenRouter as an embedding provider.  
`litellm.embedding(model="openrouter/...", ...)` raises `BadRequestError: Unmapped LLM provider`.  
The fix: bypass litellm and call `POST https://openrouter.ai/api/v1/embeddings` directly.

## Fixes Applied

| File | Change |
|------|--------|
| `config.yaml` | Added `embedding_api_key: ${OPENROUTER_API_KEY}` in `llm` section |
| `src/core/llm.py` | Added OpenRouter direct-HTTP branch in `embed()` (bypasses litellm) |
| `src/core/llm.py` | Text truncated to 8000 chars before sending (free model context limit) |
| `kb_data/chroma.sqlite3` | Fixed `config_json_str` `_type` field for ChromaDB 0.6.x compatibility |

## KB Rebuild Results

```
only-real mode: rebuild from kb_data/corpus/
regulations: 100 docs
policies:    300 docs
total:       400 docs
```

## Recall@5 Measurement

Test: 5 queries against `search_regulations()` with `n_results=5`.

| Query | Before rebuild | After rebuild |
|-------|---------------|---------------|
| 政府採購法適用範圍 | 0 (no KB) | 5/5 |
| 行政程序法聽證程序 | 0 (no KB) | 5/5 |
| 公務員服務規範 | 0 (no KB) | 5/5 |
| 地方自治法規 | 0 (no KB) | 5/5 |
| 環境影響評估 | 0 (no KB) | 5/5 |
| **Average** | **0/5** | **5/5 (100%)** |

## Regression Tests

```
python -m pytest tests/ -q --ignore=tests/integration -n 8
→ 3958 passed in 235.69s
```

No regressions introduced.

## OpenSpec Change

See `openspec/changes/archive/` — `embedding-provider-rest-fallback` specification.  
The direct-HTTP fallback pattern for OpenRouter embeddings is now established as a project convention.
