import json
import sys
from pathlib import Path

import typer
from rich.console import Console

console = Console()

FIELD_PREFIXES = {
    "subject": "主旨：",
    "description": "說明：",
    "sender": "正本：",
    "receiver": "副本：",
}


def _parse_fields(content: str) -> dict[str, str]:
    """從公文內容中解析欄位。"""
    fields: dict[str, str] = {}
    for key, prefix in FIELD_PREFIXES.items():
        for line in content.splitlines():
            if line.startswith(prefix):
                fields[key] = line[len(prefix):].strip()
    return fields


def extract(
    file_path: str = typer.Argument(..., help="公文檔案路徑（.txt/.md）"),
    field: str = typer.Option("all", "--field", "-f", help="擷取的欄位（all/subject/description/sender/receiver）"),
    output_format: str = typer.Option("text", "--format", help="輸出格式（text/json）"),
    output: str = typer.Option("", "--output", "-o", help="匯出結果至檔案"),
):
    """擷取公文欄位內容。"""
    path = Path(file_path)
    if not path.exists():
        console.print("[red]錯誤：找不到檔案[/red]")
        raise typer.Exit(1)

    content = path.read_text(encoding="utf-8")
    fields = _parse_fields(content)

    if field != "all":
        if field in fields:
            fields = {field: fields[field]}
        else:
            fields = {}

    if output_format == "json":
        console.print(json.dumps(fields, ensure_ascii=False, indent=2))
    else:
        for key, value in fields.items():
            label = FIELD_PREFIXES.get(key, key)
            console.print(f"{label}{value}")

    if output:
        with open(output, "w", encoding="utf-8") as out_f:
            if output_format == "json":
                out_f.write(json.dumps(fields, ensure_ascii=False, indent=2))
            else:
                lines = []
                for key, value in fields.items():
                    label = FIELD_PREFIXES.get(key, key)
                    lines.append(f"{label}{value}")
                out_f.write("\n".join(lines))
        console.print(f"[green]已匯出擷取結果至：{output}[/green]")
