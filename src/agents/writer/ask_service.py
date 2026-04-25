import logging

from rich.console import Console

from src.integrations.open_notebook.stub import AskResult

logger = logging.getLogger(__name__)
console = Console()


def _writer_runtime_symbols():
    from src.agents import writer as writer_module

    return {
        "IntegrationDisabled": writer_module.IntegrationDisabled,
        "IntegrationSetupError": writer_module.IntegrationSetupError,
        "OpenNotebookAskRequest": writer_module.OpenNotebookAskRequest,
        "OpenNotebookService": writer_module.OpenNotebookService,
        "get_open_notebook_mode": writer_module.get_open_notebook_mode,
    }


class WriterAskServiceMixin:
    @staticmethod
    def _normalize_open_notebook_diagnostics(
        diagnostics: dict[str, object],
        *,
        mode: str,
        used_fallback: bool,
    ) -> dict[str, str]:
        normalized = {
            str(key): str(value)
            for key, value in diagnostics.items()
        }
        normalized.setdefault("service", "open-notebook")
        normalized.setdefault("mode", mode)
        if used_fallback:
            normalized.setdefault("used_fallback", "true")
            normalized.setdefault("fallback_stage", "service")
        return normalized

    @staticmethod
    def _build_open_notebook_docs(examples: list[dict]) -> list[dict[str, object]]:
        docs: list[dict[str, object]] = []
        for index, example in enumerate(examples, start=1):
            metadata = example.get("metadata", {})
            docs.append(
                {
                    "title": metadata.get("title", f"kb-doc-{index}"),
                    "content_md": example.get("content", "") or "",
                    "source_url": metadata.get("source_url", ""),
                    "source_level": metadata.get("source_level", "B"),
                    "source_type": metadata.get("source", ""),
                    "record_id": metadata.get(
                        "meta_id",
                        metadata.get("pcode", metadata.get("dataset_id", "")),
                    ),
                }
            )
        return docs

    @staticmethod
    def _build_open_notebook_question(requirement) -> str:
        reason_text = requirement.reason or "（未提供）"
        actions_text = "；".join(requirement.action_items) if requirement.action_items else "（未提供）"
        attachments_text = "；".join(requirement.attachments) if requirement.attachments else "（無）"
        return (
            f"請撰寫一份{requirement.doc_type}。"
            f"發文機關：{requirement.sender}。"
            f"受文者：{requirement.receiver}。"
            f"主旨：{requirement.subject}。"
            f"說明：{reason_text}。"
            f"辦理事項：{actions_text}。"
            f"附件：{attachments_text}。"
            "保留台灣公文格式與引用痕跡。"
        )

    @classmethod
    def _sources_from_open_notebook_result(
        cls,
        result: AskResult,
        docs: list[dict[str, object]],
    ) -> list[dict]:
        if not result.evidence:
            evidence_rows = [
                {
                    "title": str(doc.get("title") or f"Source {index}"),
                    "snippet": str(doc.get("content_md") or ""),
                    "source_url": str(doc.get("source_url") or ""),
                    "rank": index,
                }
                for index, doc in enumerate(docs, start=1)
            ]
        else:
            evidence_rows = [
                {
                    "title": evidence.title,
                    "snippet": evidence.snippet,
                    "source_url": evidence.source_url,
                    "rank": evidence.rank or index,
                }
                for index, evidence in enumerate(result.evidence, start=1)
            ]

        sources: list[dict] = []
        for index, evidence in enumerate(evidence_rows, start=1):
            matched_doc = cls._match_open_notebook_doc(evidence, docs)
            sources.append(
                {
                    "index": index,
                    "title": str(evidence["title"] or f"Source {index}"),
                    "source_level": str(matched_doc.get("source_level") or "B"),
                    "source_url": str(evidence["source_url"] or matched_doc.get("source_url") or ""),
                    "source_type": str(matched_doc.get("source_type") or ""),
                    "record_id": str(matched_doc.get("record_id") or ""),
                    "content_hash": "",
                    "evidence_rank": str(evidence["rank"] or ""),
                    "evidence_snippet": str(evidence["snippet"] or ""),
                }
            )
        return sources

    @staticmethod
    def _match_open_notebook_doc(
        evidence: dict[str, object],
        docs: list[dict[str, object]],
    ) -> dict[str, object]:
        rank = evidence.get("rank")
        if isinstance(rank, int) and 1 <= rank <= len(docs):
            return docs[rank - 1]

        source_url = str(evidence.get("source_url") or "")
        if source_url:
            for doc in docs:
                if str(doc.get("source_url") or "") == source_url:
                    return doc

        title = str(evidence.get("title") or "")
        if title:
            for doc in docs:
                if str(doc.get("title") or "") == title:
                    return doc
        return {}

    def _try_open_notebook_draft(self, requirement, examples: list[dict]) -> tuple[str, list[dict]] | None:
        runtime = _writer_runtime_symbols()
        runtime_mode = runtime["get_open_notebook_mode"]()
        if runtime_mode == "off":
            return None

        docs = self._build_open_notebook_docs(examples)
        service = runtime["OpenNotebookService"](mode=runtime_mode)
        request = runtime["OpenNotebookAskRequest"](
            question=self._build_open_notebook_question(requirement),
            docs=tuple(docs),
            top_k=max(len(docs), 1),
            metadata_filters={"doc_type": requirement.doc_type},
        )

        try:
            result = service.ask(request)
            self._last_open_notebook_diagnostics = self._normalize_open_notebook_diagnostics(
                dict(result.diagnostics),
                mode=runtime_mode,
                used_fallback=result.used_fallback,
            )
        except (runtime["IntegrationDisabled"], runtime["IntegrationSetupError"]) as exc:
            self._last_open_notebook_diagnostics = {
                "service": "open-notebook",
                "mode": runtime_mode,
                "used_fallback": "true",
                "fallback_stage": "setup",
                "fallback_reason": str(exc),
            }
            logger.warning("open-notebook writer path unavailable; fallback to legacy LLM: %s", exc)
            console.print(f"[yellow]open-notebook 不可用，退回 legacy writer：{exc}[/yellow]")
            return None
        except (RuntimeError, OSError, ConnectionError) as exc:
            console.print(f"[yellow]open-notebook 執行失敗，退回 legacy writer：{exc}[/yellow]")
            return None

        console.print(
            f"[cyan]open-notebook {runtime_mode} 模式已產生草稿，"
            f"evidence={len(result.evidence)}。[/cyan]"
        )
        return result.answer_text, self._sources_from_open_notebook_result(result, docs)
