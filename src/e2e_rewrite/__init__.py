from __future__ import annotations

import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from src.agents.auditor import FormatAuditor
from src.agents.requirement import RequirementAgent
from src.agents.template import TemplateEngine
from src.agents.writer import WriterAgent
from src.document.citation_metadata import read_docx_citation_metadata
from src.document.exporter import DocxExporter
from src.knowledge.corpus_provenance import is_active_corpus_metadata, read_markdown_frontmatter

from .fixtures import CorpusFixtureKB, DeterministicLLM
from .reporting import write_e2e_report
from .scenarios import RewriteScenario, SCENARIOS


def load_real_corpus(base_dir: str | Path = "kb_data/corpus") -> dict[str, dict[str, Any]]:
    corpus_dir = Path(base_dir)
    corpus: dict[str, dict[str, Any]] = {}
    for path in sorted(corpus_dir.rglob("*.md")):
        meta, content = read_markdown_frontmatter(path)
        source_id = str(meta.get("source_id") or meta.get("source_doc_no") or "").strip()
        if not source_id or not is_active_corpus_metadata(meta):
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
        sections = TemplateEngine().parse_draft(raw_draft)
        formatted = TemplateEngine().apply_template(requirement, sections)
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
