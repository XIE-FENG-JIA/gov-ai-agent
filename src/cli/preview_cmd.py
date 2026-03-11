import json
import os
import typer
from rich.console import Console
from rich.panel import Panel
from rich.tree import Tree

console = Console()

_SECTION_NAMES = ["主旨", "說明", "辦法", "擬辦", "正本", "副本", "備註", "附件"]


def preview(
    file: str = typer.Option(..., "-f", "--file", help="要預覽的公文檔案路徑"),
    color: bool = typer.Option(True, "--color/--no-color", help="是否啟用著色輸出"),
    as_json: bool = typer.Option(False, "--json", help="以 JSON 格式輸出"),
):
    """預覽公文的格式化結構。"""
    if not os.path.isfile(file):
        console.print(f"[red]錯誤：找不到檔案：{file}[/red]")
        raise typer.Exit(1)

    try:
        with open(file, "r", encoding="utf-8-sig") as f:
            text = f.read()
    except UnicodeDecodeError:
        console.print("[red]錯誤：檔案編碼不支援，請使用 UTF-8。[/red]")
        raise typer.Exit(1)

    lines = text.split("\n")

    # 解析段落結構
    sections = []
    current_section = None
    current_content = []

    for line in lines:
        stripped = line.strip()
        matched = None
        for s in _SECTION_NAMES:
            if stripped.startswith(s):
                matched = s
                break

        if matched:
            if current_section:
                sections.append((current_section, current_content))
            current_section = matched
            after = stripped[len(matched):].lstrip("：:").strip()
            current_content = [after] if after else []
        elif current_section and stripped:
            current_content.append(stripped)
        elif not current_section and stripped:
            sections.append(("（未分類）", [stripped]))

    if current_section:
        sections.append((current_section, current_content))

    # 檢查缺少的段落
    found_sections = {s[0] for s in sections}
    required = {"主旨", "說明"}
    missing = required - found_sections

    if as_json:
        json_data = {
            "sections": [{"name": name, "content": content} for name, content in sections],
            "missing": list(missing),
            "char_count": len(text.replace("\n", "").replace(" ", "")),
            "section_count": len(sections),
        }
        console.print(json.dumps(json_data, ensure_ascii=False, indent=2))
        return

    # 建構 Tree
    tree = Tree("[bold cyan]公文結構預覽[/bold cyan]" if color else "公文結構預覽")

    for section_name, content in sections:
        style = "bold green" if color else ""
        node = tree.add(f"[{style}]{section_name}[/{style}]" if color else section_name)
        for item in content:
            node.add(item)

    console.print(tree)

    # 缺少的段落警告
    if missing:
        console.print(f"\n[yellow]⚠ 缺少必要段落：{'、'.join(missing)}[/yellow]")

    # 統計
    char_count = len(text.replace("\n", "").replace(" ", ""))
    console.print(f"\n[dim]段落數：{len(sections)} | 字數：{char_count}[/dim]")
