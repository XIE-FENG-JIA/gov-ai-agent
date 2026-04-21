from __future__ import annotations

import json
from typing import Any

from src.core.models import PublicDocRequirement

from .scenarios import RewriteScenario


class DeterministicLLM:
    def __init__(self, corpus: dict[str, dict[str, Any]], scenario: RewriteScenario) -> None:
        self.corpus = corpus
        self.scenario = scenario

    def generate(self, prompt: str, temperature: float | None = None) -> str:
        if "Output JSON (Traditional Chinese):" in prompt and "<user-input>" in prompt:
            return json.dumps(self.scenario.requirement, ensure_ascii=False)
        if "Please write the full draft with citations now." in prompt:
            return build_writer_draft(self.scenario, self.corpus)
        if "Return purely a JSON object" in prompt:
            return json.dumps({"errors": [], "warnings": []}, ensure_ascii=False)
        if '"issues": [' in prompt or '"issues": []' in prompt:
            return json.dumps({"issues": [], "score": 0.98, "confidence": 0.98}, ensure_ascii=False)
        return json.dumps({"issues": [], "score": 0.98, "confidence": 0.98}, ensure_ascii=False)

    def embed(self, text: str) -> list[float]:
        length = max(len(text), 1)
        return [float(length % 11), float(length % 7), float(length % 5)]


class CorpusFixtureKB:
    def __init__(self, corpus: dict[str, dict[str, Any]], scenario: RewriteScenario) -> None:
        self.corpus = corpus
        self.scenario = scenario

    def search_hybrid(
        self,
        query: str,
        n_results: int = 5,
        source_level: str | None = None,
    ) -> list[dict[str, Any]]:
        del query
        results: list[dict[str, Any]] = []
        for order, source_id in enumerate(self.scenario.source_ids, start=1):
            source = self.corpus[source_id]
            if source_level and source["source_level"] != source_level:
                continue
            results.append(
                {
                    "id": f"{self.scenario.slug}-{source_id}",
                    "content": source["content"],
                    "metadata": {
                        "title": source["title"],
                        "source_level": source["source_level"],
                        "source_url": source["source_url"],
                        "source": source["doc_type"],
                        "meta_id": source["source_id"],
                        "content_hash": f"{source['source_id']}-hash",
                    },
                    "distance": 0.12 + order / 100,
                }
            )
        return results[:n_results]

    def search_regulations(
        self,
        query: str,
        doc_type: str | None = None,
        n_results: int = 3,
        source_level: str | None = None,
    ) -> list[dict[str, Any]]:
        del query, doc_type
        law_results = [
            {
                "id": f"reg-{source['source_id']}",
                "content": source["content"],
                "metadata": {
                    "title": source["title"],
                    "source_level": source["source_level"],
                    "source_url": source["source_url"],
                    "source": source["doc_type"],
                    "meta_id": source["source_id"],
                },
                "distance": 0.05,
            }
            for source in self.corpus.values()
            if source["source_level"] == "A"
        ]
        if source_level:
            law_results = [item for item in law_results if item["metadata"]["source_level"] == source_level]
        return law_results[:n_results]

    def search_examples(
        self,
        query: str,
        n_results: int = 3,
        filter_metadata: dict | None = None,
        source_level: str | None = None,
    ) -> list[dict[str, Any]]:
        del filter_metadata
        return self.search_hybrid(query, n_results=n_results, source_level=source_level)

    def search_policies(self, query: str, n_results: int = 3, source_level: str | None = None) -> list[dict[str, Any]]:
        del query, n_results, source_level
        return []


def reference_definition(index: int, source: dict[str, Any]) -> str:
    return (
        f"[^{index}]: [Level {source['source_level']}] {source['title']} | "
        f"URL: {source['source_url']} | Hash: {source['source_id']}-hash"
    )


def build_writer_draft(scenario: RewriteScenario, corpus: dict[str, dict[str, Any]]) -> str:
    requirement = PublicDocRequirement(**scenario.requirement)
    sources = [corpus[source_id] for source_id in scenario.source_ids]
    references = "\n".join(reference_definition(index, source) for index, source in enumerate(sources, start=1))

    if requirement.doc_type == "函":
        return (
            f"### 主旨\n{requirement.subject}\n\n"
            "### 說明\n"
            f"一、依據《{sources[0]['title']}》所揭示之行政責任與公共治理原則辦理[^1]。\n"
            f"二、參酌「{sources[1]['title']}」所示公開統計資料，據以規劃本次宣導節點與回報節奏[^2]。\n\n"
            "### 辦法\n"
            f"一、{requirement.action_items[0]}。\n"
            f"二、{requirement.action_items[1]}。\n"
            "三、如有疑義，請逕洽本案承辦單位。\n\n"
            f"### 參考來源\n{references}\n"
        )

    if requirement.doc_type == "公告":
        return (
            f"### 主旨\n{requirement.subject}\n\n"
            f"### 依據\n依據《{sources[0]['title']}》關於行政機關發布公共措施之職權規範辦理[^1]。\n\n"
            "### 公告事項\n"
            f"一、{requirement.action_items[0]}。\n"
            f"二、{requirement.action_items[1]}。\n"
            f"三、另參酌「{sources[1]['title']}」公開資料，統一公告資訊揭露格式[^2]。\n\n"
            f"### 參考來源\n{references}\n"
        )

    if requirement.doc_type == "簽":
        return (
            f"### 主旨\n{requirement.subject}\n\n"
            "### 說明\n"
            f"一、依據《{sources[0]['title']}》所彰顯之公共事務推動責任，規劃辦理本案[^1]。\n"
            f"二、參照「{sources[1]['title']}」所列公開公文資料，整併本案場址與行政作業流程[^2]。\n\n"
            "### 擬辦\n"
            f"一、{requirement.action_items[0]}。\n"
            f"二、{requirement.action_items[1]}。\n"
            "三、如奉核可，續辦後續採購與執行事宜。\n\n"
            f"### 參考來源\n{references}\n"
        )

    if requirement.doc_type == "令":
        return (
            f"### 主旨\n{requirement.subject}\n\n"
            "### 說明\n"
            f"一、依據《{sources[0]['title']}》所定國家緊急應變準備程序辦理[^1]。\n"
            f"二、並參酌「{sources[1]['title']}」關於民生安定專案會議之應變經驗，納入本次整備重點[^2]。\n\n"
            "### 辦法\n"
            f"一、{requirement.action_items[0]}。\n"
            f"二、{requirement.action_items[1]}。\n"
            "三、各部會應於演練前完成責任分工與回報窗口建置。\n\n"
            f"### 參考來源\n{references}\n"
        )

    if requirement.doc_type == "開會通知單":
        return (
            f"### 主旨\n{requirement.subject}\n\n"
            "### 說明\n"
            f"一、依據《{sources[0]['title']}》關於國家治理與跨機關協調之基本規範辦理[^1]。\n"
            f"二、參酌「{sources[1]['title']}」揭示之產業協作經驗，作為本次聯防分工討論基礎[^2]。\n\n"
            "### 開會時間\n114年9月12日（星期五）上午10時\n\n"
            "### 開會地點\n數位發展部第一會議室\n\n"
            "### 議程\n"
            "一、跨機關資安聯防現況盤點。\n"
            "二、114年度演練分工與通報節點確認。\n\n"
            "### 辦法\n"
            "一、請各機關指派資安聯絡窗口與會。\n"
            "二、請於會前備妥演練需求摘要。\n\n"
            f"### 參考來源\n{references}\n"
        )

    raise ValueError(f"unsupported doc type: {requirement.doc_type}")
