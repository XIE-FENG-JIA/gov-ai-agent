from dataclasses import asdict
from datetime import date
from pathlib import Path
import json

import typer

from src.sources.quality_config import get_quality_policy
from src.sources.quality_gate import GateReport, QualityGate, QualityGateError

from ._shared import console
from .corpus import parse_markdown_with_metadata


def _build_gate_failure_payload(
    exc: QualityGateError,
    *,
    adapter_name: str,
    records_in: int,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "adapter": adapter_name,
        "records_in": records_in,
        "records_out": 0,
        "error_type": exc.__class__.__name__,
        "message": str(exc),
        "policy": asdict(get_quality_policy(adapter_name)),
    }
    if hasattr(exc, "record_id"):
        payload["record_id"] = getattr(exc, "record_id")
    if hasattr(exc, "missing_fields"):
        payload["missing_fields"] = getattr(exc, "missing_fields")
    return payload


def _corpus_gate_adapter_name(corpus_root: Path, file_path: Path) -> str:
    relative = file_path.relative_to(corpus_root)
    if len(relative.parts) > 1:
        return relative.parts[0]
    return "corpus"


def _corpus_gate_record(file_path: Path) -> dict[str, object]:
    metadata, content = parse_markdown_with_metadata(file_path)
    return {
        "source_id": str(metadata.get("source_id") or file_path.stem),
        "source_url": metadata.get("source_url", ""),
        "source_agency": metadata.get("source_agency", ""),
        "source_doc_no": metadata.get("source_doc_no"),
        "source_date": metadata.get("source_date"),
        "doc_type": metadata.get("doc_type", "unknown"),
        "raw_snapshot_path": metadata.get("raw_snapshot_path"),
        "crawl_date": metadata.get("crawl_date"),
        "content_md": content,
        "synthetic": bool(metadata.get("synthetic")),
        "fixture_fallback": bool(metadata.get("fixture_fallback")),
    }


def run_corpus_quality_gate(corpus_root: Path) -> list[GateReport]:
    adapter_records: dict[str, list[dict[str, object]]] = {}
    for file_path in sorted(corpus_root.rglob("*.md")):
        metadata, _ = parse_markdown_with_metadata(file_path)
        if metadata.get("deprecated"):
            continue
        adapter_name = _corpus_gate_adapter_name(corpus_root, file_path)
        adapter_records.setdefault(adapter_name, []).append(_corpus_gate_record(file_path))

    reports: list[GateReport] = []
    for adapter_name in sorted(adapter_records):
        records = adapter_records[adapter_name]
        gate = QualityGate.from_adapter_name(adapter_name)
        try:
            report = gate.evaluate(records, adapter_name=adapter_name)
        except QualityGateError as exc:
            payload = _build_gate_failure_payload(exc, adapter_name=adapter_name, records_in=len(records))
            typer.echo(json.dumps(payload), err=True)
            raise typer.Exit(1) from exc
        reports.append(report)
    return reports


def _build_gate_report_payload(report: GateReport) -> dict[str, object]:
    return {
        "adapter": report.adapter,
        "records_in": report.records_in,
        "records_out": report.records_out,
        "rejected_by": report.rejected_by,
        "pass_rate": report.pass_rate,
        "duration_seconds": report.duration_seconds,
        "timestamp": report.timestamp.isoformat(),
    }


def render_gate_check_success(report: GateReport, *, output_format: str) -> None:
    payload = _build_gate_report_payload(report)
    if output_format == "json":
        console.print_json(data=payload)
        return

    console.print("[bold green]quality gate: PASS[/bold green]")
    console.print(f"adapter={report.adapter}")
    console.print(f"records_in={report.records_in} records_out={report.records_out}")
    console.print(f"pass_rate={report.pass_rate:.2f}")
    console.print(f"duration_seconds={report.duration_seconds:.3f}")
    console.print(f"timestamp={report.timestamp.isoformat()}")


def render_gate_check_failure(
    exc: QualityGateError,
    *,
    adapter_name: str,
    records_in: int,
    output_format: str,
) -> None:
    payload = _build_gate_failure_payload(exc, adapter_name=adapter_name, records_in=records_in)

    if output_format == "json":
        console.print_json(data=payload)
        return

    console.print("[bold red]quality gate: FAIL[/bold red]")
    console.print(f"adapter={adapter_name}")
    console.print(f"records_in={records_in}")
    console.print(f"error_type={payload['error_type']}")
    console.print(f"message={payload['message']}")


def load_gate_check_records(
    source_key: str,
    *,
    registry: dict[str, type],
    since_date: date | None,
    limit: int,
):
    adapter_cls = registry[source_key]
    adapter = adapter_cls()
    documents = list(adapter.list(since_date=since_date, limit=limit))[:limit]
    records = []
    for item in documents:
        source_id = str(item.get("id", "")).strip()
        if not source_id:
            continue
        records.append(adapter.normalize(adapter.fetch(source_id)))
    return records
