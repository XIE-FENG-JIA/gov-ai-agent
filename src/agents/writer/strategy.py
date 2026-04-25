import logging

from rich.console import Console

from src.core.constants import KB_WRITER_RESULTS, LLM_TEMPERATURE_PRECISE, MAX_EXAMPLE_LENGTH
from src.core.llm import LLMError

logger = logging.getLogger(__name__)
console = Console()


class WriterStrategyMixin:
    def _search_with_refinement(
        self,
        query: str,
        kb,
        n_results: int = 5,
        max_retries: int = 2,
        source_level: str | None = None,
    ) -> list[dict]:
        """Agentic RAG：自主判斷搜尋結果品質，不佳則精煉查詢重新搜尋。"""
        results = kb.search_hybrid(query, n_results=n_results, source_level=source_level)

        for attempt in range(max_retries):
            if not results or not self._check_relevance(query, results):
                refined = self._refine_query(query, results, attempt + 1)
                if refined and refined != query:
                    logger.info(
                        "Agentic RAG 精煉 #%d: '%s' → '%s'",
                        attempt + 1,
                        query[:40],
                        refined[:40],
                    )
                    console.print(
                        f"[yellow]搜尋結果相關性不足，精煉查詢 (第 {attempt + 1} 次)...[/yellow]"
                    )
                    results = kb.search_hybrid(
                        refined,
                        n_results=n_results,
                        source_level=source_level,
                    )
                    query = refined
                else:
                    logger.info("Agentic RAG: 精煉 #%d 未產生新查詢，停止迭代", attempt + 1)
                    break
            else:
                logger.info(
                    "Agentic RAG: 搜尋結果通過相關性檢查 (attempt=%d, results=%d)",
                    attempt,
                    len(results),
                )
                break

        return results

    @staticmethod
    def _check_relevance(query: str, results: list[dict]) -> bool:
        """檢查搜尋結果是否與查詢相關。"""
        if not results:
            return False

        distances = [result.get("distance", 1.5) for result in results]
        avg_distance = sum(distances) / len(distances)
        min_distance = min(distances)
        is_relevant = avg_distance < 1.2 and min_distance < 1.0

        logger.debug(
            "Agentic RAG 相關性檢查: avg_dist=%.3f, min_dist=%.3f, relevant=%s",
            avg_distance,
            min_distance,
            is_relevant,
        )
        return is_relevant

    def _refine_query(self, original_query: str, poor_results: list[dict], attempt: int) -> str:
        """用 LLM 精煉搜尋查詢，嘗試用不同關鍵字找到更相關的結果。"""
        result_summaries = ""
        if poor_results:
            snippets = []
            for index, result in enumerate(poor_results[:3], 1):
                title = result.get("metadata", {}).get("title", "無標題")
                distance = result.get("distance", "N/A")
                preview = (result.get("content", "") or "")[:80]
                snippets.append(f"  {index}. [{title}] (距離: {distance}) {preview}...")
            result_summaries = "\n".join(snippets)

        prompt = (
            "你是公文知識庫搜尋助手。以下搜尋查詢未找到足夠相關的結果，"
            "請用不同的關鍵字或同義詞重新表述查詢。\n\n"
            f"原始查詢: {original_query}\n"
            f"精煉次數: 第 {attempt} 次\n"
        )
        if result_summaries:
            prompt += f"\n目前搜尋結果（相關性不足）:\n{result_summaries}\n"
        prompt += (
            "\n請分析原始查詢和搜尋結果，用不同的關鍵字重新表述查詢，"
            "以找到更相關的公文範例或法規。\n"
            "策略：嘗試使用同義詞、上位概念、或更具體的法規名稱。\n"
            "只輸出新的查詢文字，不要任何其他說明。"
        )

        try:
            refined = self.llm.generate(prompt, temperature=LLM_TEMPERATURE_PRECISE)
            refined = (refined or "").strip()
            if refined and 2 <= len(refined) <= 200 and refined != original_query:
                return refined
            logger.debug(
                "Agentic RAG: 精煉結果無效或與原查詢相同 (len=%d)",
                len(refined) if refined else 0,
            )
            return original_query
        except (LLMError, RuntimeError, OSError, ValueError) as exc:
            return original_query

    def _search_examples(self, query: str) -> list[dict]:
        """兩段式 Agentic RAG：先 Level A，再補足所有來源，合併去重。"""
        level_a_results = self._search_with_refinement(
            query,
            self.kb,
            n_results=3,
            max_retries=2,
            source_level="A",
        )
        all_results = self._search_with_refinement(
            query,
            self.kb,
            n_results=KB_WRITER_RESULTS,
            max_retries=2,
        )
        seen_ids: set[str] = set()
        merged: list[dict] = []
        for result in level_a_results + all_results:
            result_id = result.get("id", id(result))
            if result_id not in seen_ids:
                seen_ids.add(result_id)
                merged.append(result)

        if not merged:
            doc_hint = (query.split(" ", 1)[0] or "").strip()
            fallback_query = f"{doc_hint} 公文範例" if doc_hint else "公文範例"
            fallback = self.kb.search_hybrid(
                fallback_query,
                n_results=KB_WRITER_RESULTS,
                source_level="A",
            )
            for result in fallback or []:
                result_id = result.get("id", id(result))
                if result_id not in seen_ids:
                    seen_ids.add(result_id)
                    merged.append(result)
        return merged[:KB_WRITER_RESULTS]

    @staticmethod
    def _format_examples(examples: list[dict]) -> tuple[list[str], list[dict]]:
        """將搜尋結果格式化為 prompt 片段和來源清單。"""
        parts: list[str] = []
        sources: list[dict] = []
        for index, example in enumerate(examples, 1):
            metadata = example.get("metadata", {})
            title = metadata.get("title", "Unknown")
            source_level = metadata.get("source_level", "B")
            content = example.get("content", "") or ""
            if len(content) > MAX_EXAMPLE_LENGTH:
                content = content[:MAX_EXAMPLE_LENGTH] + "\n...(內容已截斷)"
            parts.append(
                f"--- Source {index} [Level {source_level}]: {title} ---\n{content}\n"
            )
            sources.append(
                {
                    "index": index,
                    "title": title,
                    "source_level": source_level,
                    "source_url": metadata.get("source_url", ""),
                    "source_type": metadata.get("source", ""),
                    "record_id": metadata.get(
                        "meta_id",
                        metadata.get("pcode", metadata.get("dataset_id", "")),
                    ),
                    "content_hash": metadata.get("content_hash", ""),
                }
            )
        return parts, sources
