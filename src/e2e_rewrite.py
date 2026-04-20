from __future__ import annotations

import json
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from src.agents.auditor import FormatAuditor
from src.agents.requirement import RequirementAgent
from src.agents.template import TemplateEngine
from src.agents.writer import WriterAgent
from src.document.citation_metadata import read_docx_citation_metadata
from src.document.exporter import DocxExporter
from src.core.models import PublicDocRequirement


@dataclass(frozen=True)
class RewriteScenario:
    slug: str
    user_input: str
    requirement: dict[str, Any]
    source_ids: tuple[str, ...]


SCENARIOS: tuple[RewriteScenario, ...] = (
    RewriteScenario(
        slug="han",
        user_input=(
            "請寫一份函，臺北市政府教育局發給各市立國民中學，"
            "主旨是辦理114年度校園資源回收宣導，並請各校於114年6月15日前回報成果。"
        ),
        requirement={
            "doc_type": "函",
            "urgency": "普通",
            "sender": "臺北市政府教育局",
            "receiver": "臺北市各市立國民中學",
            "subject": "有關辦理114年度校園資源回收宣導一案，請查照。",
            "reason": "為強化校園環境教育與資源回收執行成效。",
            "action_items": [
                "請於114年5月30日前完成校內宣導規劃",
                "請於114年6月15日前回報執行情形",
            ],
            "attachments": ["校園資源回收宣導表"],
        },
        source_ids=("A0000001", "162455"),
    ),
    RewriteScenario(
        slug="announcement",
        user_input=(
            "請寫一份公告，臺北市政府環境保護局公告114年端午節垃圾清運時間調整，"
            "並提醒市民依公告時段排出垃圾。"
        ),
        requirement={
            "doc_type": "公告",
            "urgency": "普通",
            "sender": "臺北市政府環境保護局",
            "receiver": "全體市民",
            "subject": "公告114年端午節期間垃圾清運時間調整事項。",
            "reason": "為維持節慶期間市容整潔並便利市民配合清運作業。",
            "action_items": [
                "114年6月8日停止夜間清運",
                "114年6月9日恢復正常清運",
            ],
            "attachments": ["端午節垃圾清運時程表"],
        },
        source_ids=("A0000002", "173524"),
    ),
    RewriteScenario(
        slug="sign",
        user_input=(
            "請寫一份簽，臺北市政府環境保護局要向局長簽報辦理114年度環保志工表揚活動，"
            "預算新臺幣30萬元，擬於114年8月15日舉行。"
        ),
        requirement={
            "doc_type": "簽",
            "urgency": "速件",
            "sender": "臺北市政府環境保護局",
            "receiver": "局長",
            "subject": "擬辦理114年度環保志工表揚活動一案，簽請核示。",
            "reason": "為肯定志工服務績效並強化環境保護政策推廣。",
            "action_items": [
                "活動日期定於114年8月15日",
                "所需經費新臺幣30萬元由相關預算支應",
            ],
            "attachments": ["活動規劃書", "經費概算表"],
        },
        source_ids=("A0000001", "30790"),
    ),
    RewriteScenario(
        slug="decree",
        user_input=(
            "請寫一份令，行政院命各部會於114年7月1日起配合重大緊急應變演練，"
            "並依規定完成內部通報機制整備。"
        ),
        requirement={
            "doc_type": "令",
            "urgency": "最速件",
            "sender": "行政院",
            "receiver": "各部會",
            "subject": "自114年7月1日起實施重大緊急應變演練整備事項。",
            "reason": "為強化跨機關緊急應變與通報協作機制。",
            "action_items": [
                "自114年7月1日起實施演練整備",
                "各部會應完成內部通報流程盤點",
            ],
            "attachments": ["演練整備重點表"],
        },
        source_ids=("A0000003", "5c4c4e1c-9f4f-4b75-a7d3-30be59522441"),
    ),
    RewriteScenario(
        slug="meeting-notice",
        user_input=(
            "請寫一份開會通知單，數位發展部邀集各部會在114年9月12日上午10時開會，"
            "討論跨機關資安聯防機制與演練分工。"
        ),
        requirement={
            "doc_type": "開會通知單",
            "urgency": "普通",
            "sender": "數位發展部",
            "receiver": "各部會資安聯絡窗口",
            "subject": "召開114年度跨機關資安聯防協調會議，請查照。",
            "reason": "為整合跨機關資安聯防機制與演練分工。",
            "action_items": [
                "114年9月12日上午10時出席會議",
                "會前彙整機關資安演練需求",
            ],
            "attachments": ["會議議程"],
        },
        source_ids=("A0000002", "6d5edda8-43b5-4e9a-84f8-c57798989ad0"),
    ),
)


def _read_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---\n"):
        return {}, raw
    parts = raw.split("---\n", 2)
    if len(parts) < 3:
        return {}, raw
    meta = yaml.safe_load(parts[1]) or {}
    return (meta if isinstance(meta, dict) else {}), parts[2].strip()


def load_real_corpus(base_dir: str | Path = "kb_data/corpus") -> dict[str, dict[str, Any]]:
    corpus_dir = Path(base_dir)
    corpus: dict[str, dict[str, Any]] = {}
    for path in sorted(corpus_dir.rglob("*.md")):
        meta, content = _read_frontmatter(path)
        source_id = str(meta.get("source_id") or meta.get("source_doc_no") or "").strip()
        if not source_id or meta.get("synthetic") is True:
            continue
        source_level = "A" if path.parts[-2] == "mojlaw" else "B"
        corpus[source_id] = {
            "source_id": source_id,
            "title": str(meta.get("title") or source_id),
            "source_url": str(meta.get("source_url") or ""),
            "doc_type": str(meta.get("doc_type") or ""),
            "source_level": source_level,
            "content": content,
            "path": str(path),
        }
    return corpus


def _find_scenario(text: str) -> RewriteScenario:
    payloads = [text]

    for tag in ("user-input", "requirement-data"):
        match = re.search(fr"<{tag}>\s*(.*?)\s*</{tag}>", text, re.DOTALL)
        if match:
            payloads.insert(0, match.group(1).strip())

    for payload in payloads:
        subject_match = re.search(r"- Subject:\s*(.+)", payload)
        if subject_match:
            subject = subject_match.group(1).strip()
            for scenario in SCENARIOS:
                if str(scenario.requirement["subject"]) == subject:
                    return scenario

        for scenario in SCENARIOS:
            if scenario.user_input == payload:
                return scenario
            if scenario.user_input in payload:
                return scenario
            if str(scenario.requirement["subject"]) in payload:
                return scenario
            if str(scenario.requirement["sender"]) in payload:
                return scenario
            if scenario.slug in payload:
                return scenario
    raise ValueError(f"unable to match scenario from prompt: {text[:120]}")


class DeterministicLLM:
    def __init__(self, corpus: dict[str, dict[str, Any]], scenario: RewriteScenario) -> None:
        self.corpus = corpus
        self.scenario = scenario

    def generate(self, prompt: str, temperature: float | None = None) -> str:
        if "Output JSON (Traditional Chinese):" in prompt and "<user-input>" in prompt:
            return json.dumps(self.scenario.requirement, ensure_ascii=False)
        if "Please write the full draft with citations now." in prompt:
            return _build_writer_draft(self.scenario, self.corpus)
        if "Return purely a JSON object" in prompt:
            return json.dumps({"errors": [], "warnings": []}, ensure_ascii=False)
        if '"issues": [' in prompt or '"issues": []' in prompt:
            return json.dumps(
                {"issues": [], "score": 0.98, "confidence": 0.98},
                ensure_ascii=False,
            )
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
        del doc_type
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

    def search_examples(self, query: str, n_results: int = 3, filter_metadata: dict | None = None, source_level: str | None = None) -> list[dict[str, Any]]:
        del filter_metadata
        return self.search_hybrid(query, n_results=n_results, source_level=source_level)

    def search_policies(self, query: str, n_results: int = 3, source_level: str | None = None) -> list[dict[str, Any]]:
        del query, n_results, source_level
        return []


def _reference_definition(index: int, source: dict[str, Any]) -> str:
    return (
        f"[^{index}]: [Level {source['source_level']}] {source['title']} | "
        f"URL: {source['source_url']} | Hash: {source['source_id']}-hash"
    )


def _build_writer_draft(scenario: RewriteScenario, corpus: dict[str, dict[str, Any]]) -> str:
    requirement = PublicDocRequirement(**scenario.requirement)
    sources = [corpus[source_id] for source_id in scenario.source_ids]
    references = "\n".join(_reference_definition(index, source) for index, source in enumerate(sources, start=1))

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


def run_rewrite_e2e(
    output_dir: str | Path,
    *,
    report_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    corpus = load_real_corpus()
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for scenario in SCENARIOS:
        llm = DeterministicLLM(corpus, scenario)
        kb = CorpusFixtureKB(corpus, scenario)
        requirement = RequirementAgent(llm).analyze(scenario.user_input)
        writer = WriterAgent(llm, kb)
        raw_draft = writer.write_draft(requirement)
        template_engine = TemplateEngine()
        sections = template_engine.parse_draft(raw_draft)
        formatted = template_engine.apply_template(requirement, sections)
        audit_result = FormatAuditor(llm, kb).audit(formatted, requirement.doc_type)

        output_file = (output_root / f"{scenario.slug}.docx").resolve()
        with tempfile.TemporaryDirectory(prefix="gov-ai-e2e-") as temp_dir:
            staged_path = Path(temp_dir) / output_file.name
            exported_path = DocxExporter().export(
                formatted,
                str(staged_path),
                qa_report=json.dumps(audit_result, ensure_ascii=False),
                citation_metadata={
                    "reviewed_sources": list(writer._last_sources_list),
                    "engine": "deterministic-e2e",
                    "ai_generated": True,
                },
            )
            if output_file.exists():
                output_file.unlink()
            shutil.copy2(exported_path, output_file)
            metadata = read_docx_citation_metadata(str(output_file))
        citation_sources = list(metadata.get("citation_sources_json") or [])
        traced_paths = [
            corpus[str(item.get("source_doc_id"))]["path"]
            for item in citation_sources
            if str(item.get("source_doc_id")) in corpus
        ]

        result = {
            "slug": scenario.slug,
            "doc_type": requirement.doc_type,
            "user_input": scenario.user_input,
            "output_path": str(output_file),
            "citation_count": int(metadata.get("citation_count") or 0),
            "source_doc_ids": list(metadata.get("source_doc_ids") or []),
            "traced_paths": traced_paths,
            "audit_errors": len(audit_result.get("errors") or []),
            "audit_warnings": len(audit_result.get("warnings") or []),
        }
        if result["citation_count"] <= 0:
            raise AssertionError(f"{scenario.slug}: citation_count should be > 0")
        if not result["source_doc_ids"]:
            raise AssertionError(f"{scenario.slug}: source_doc_ids should not be empty")
        if len(result["traced_paths"]) != len(citation_sources):
            raise AssertionError(f"{scenario.slug}: some citation sources are not traceable to kb_data/corpus")
        results.append(result)

    if report_path is not None:
        write_e2e_report(results, report_path)
    return results


def run_e2e_suite(
    output_dir: str | Path,
    report_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    return run_rewrite_e2e(output_dir=output_dir, report_path=report_path)


def write_e2e_report(results: list[dict[str, Any]], report_path: str | Path) -> None:
    lines = [
        "# E2E Rewrite Report",
        "",
        f"- Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"- Total scenarios: {len(results)}",
        "",
        "| Type | Output | citation_count | source_doc_ids | Traceable | Errors | Warnings |",
        "| --- | --- | ---: | --- | --- | ---: | ---: |",
    ]
    for result in results:
        lines.append(
            "| {doc_type} | `{output}` | {citation_count} | `{source_doc_ids}` | {traceable} | {errors} | {warnings} |".format(
                doc_type=result["doc_type"],
                output=result["output_path"],
                citation_count=result["citation_count"],
                source_doc_ids=", ".join(result["source_doc_ids"]),
                traceable="yes" if result["traced_paths"] else "no",
                errors=result["audit_errors"],
                warnings=result["audit_warnings"],
            )
        )
    lines.extend(["", "## Traceability", ""])
    for result in results:
        lines.append(f"### {result['doc_type']}")
        lines.append(f"- Input: {result['user_input']}")
        lines.append(f"- Output: `{result['output_path']}`")
        lines.append(f"- source_doc_ids: `{', '.join(result['source_doc_ids'])}`")
        for path in result["traced_paths"]:
            lines.append(f"- repo evidence: `{path}`")
        lines.append("")

    report_file = Path(report_path)
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text("\n".join(lines), encoding="utf-8")
