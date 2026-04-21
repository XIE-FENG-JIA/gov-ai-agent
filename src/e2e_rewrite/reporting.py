from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any


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
