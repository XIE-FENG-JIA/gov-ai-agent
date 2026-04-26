"""BM25 and TF-IDF scoring helpers for KnowledgeHybridSearchMixin.

Extracted from _manager_hybrid.py to keep it under the 260-line fat limit.
"""

import logging
import math
from collections import Counter

logger = logging.getLogger(__name__)

_MAX_QUERY_CHARS = 500


def bm25_search_docs(query: str, all_docs: list[dict], n_results: int = 10) -> list[dict]:
    """BM25 scoring over pre-fetched docs using jieba tokenization.

    Args:
        query: Search query string (will be capped at _MAX_QUERY_CHARS).
        all_docs: Pre-fetched and pre-filtered document list.
        n_results: Maximum number of results to return.
    """
    try:
        import jieba
    except ImportError:
        return []

    if len(query) > _MAX_QUERY_CHARS:
        logger.debug(
            "BM25 query 截短 %d → %d 字元（jieba 效能保護）",
            len(query), _MAX_QUERY_CHARS,
        )
        query = query[:_MAX_QUERY_CHARS]

    query_tokens = list(jieba.cut(query))
    query_tokens = [t for t in query_tokens if len(t.strip()) > 1]
    if not query_tokens:
        return []

    doc_count = len(all_docs)
    token_doc_freq: Counter = Counter()
    doc_token_freqs: list[Counter] = []
    doc_lengths: list[int] = []

    for doc in all_docs:
        tokens = list(jieba.cut(doc["content"]))
        freq = Counter(tokens)
        doc_token_freqs.append(freq)
        doc_lengths.append(len(tokens))
        for unique_token in freq:
            token_doc_freq[unique_token] += 1

    scored: list[tuple[float, dict]] = []
    for idx, doc in enumerate(all_docs):
        freq = doc_token_freqs[idx]
        doc_len = doc_lengths[idx] if doc_lengths[idx] > 0 else 1
        score = 0.0
        for qt in query_tokens:
            if qt in freq:
                tf = freq[qt] / doc_len
                df = token_doc_freq.get(qt, 0)
                idf = math.log(doc_count / (1 + df))
                score += tf * idf
        scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    results: list[dict] = []
    for score, doc in scored[:n_results]:
        if score > 0:
            doc["distance"] = 1.0 / (1.0 + score)
            doc["_bm25_score"] = score
            results.append(doc)
    return results


def tfidf_search_docs(query: str, all_docs: list[dict], n_results: int = 5) -> list[dict]:
    """TF-IDF scoring over pre-fetched docs using jieba tokenization.

    Args:
        query: Search query string.
        all_docs: Pre-fetched and pre-filtered document list.
        n_results: Maximum number of results to return.
    """
    try:
        import jieba
    except ImportError:
        return []

    query_tokens = set(jieba.cut(query))
    if not query_tokens:
        return []

    doc_count = len(all_docs)
    token_doc_freq: Counter = Counter()
    doc_tokens_list: list[set[str]] = []
    for doc in all_docs:
        tokens = set(jieba.cut(doc["content"]))
        doc_tokens_list.append(tokens)
        for token in tokens:
            token_doc_freq[token] += 1

    scored: list[tuple[float, dict]] = []
    for idx, doc in enumerate(all_docs):
        doc_tokens = doc_tokens_list[idx]
        score = 0.0
        for qt in query_tokens:
            if qt in doc_tokens:
                df = token_doc_freq.get(qt, 1)
                score += math.log((doc_count + 1) / (df + 1))
        scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, doc in scored[:n_results]:
        if score > 0:
            doc["distance"] = 1.0 / (1.0 + score)
            results.append(doc)
    return results
