"""公文骨架範本指令。"""

import os
import subprocess
import sys
import tempfile

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from src.cli.template_cmd.catalog import _TEMPLATE_CATEGORIES, _TEMPLATES

console = Console()


def _launch_generate(
    template_content: str,
    gen_output: str,
    *,
    preview: bool = False,
    skip_review: bool = False,
    quiet: bool = False,
    no_lint: bool = False,
) -> int:
    """將範本寫入暫存檔並以 subprocess 啟動 generate 子流程。"""
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".md",
            encoding="utf-8",
            delete=False,
            prefix="govai_tpl_",
        ) as handle:
            handle.write(template_content)
            tmp_path = handle.name

        cmd = [
            sys.executable,
            "-c",
            "from src.cli.main import app; app(prog_name='gov-ai')",
            "generate",
            "--from-file",
            tmp_path,
            "--output",
            gen_output,
        ]
        if preview:
            cmd.append("--preview")
        if skip_review:
            cmd.append("--skip-review")
        if quiet:
            cmd.append("--quiet")
        if no_lint:
            cmd.append("--no-lint")

        result = subprocess.run(cmd)
        return result.returncode
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def template(
    doc_type: str = typer.Argument("函", help="公文類型（函、公告、簽、書函、令等）"),
    output: str = typer.Option("", "--output", "-o", help="匯出範本至檔案"),
    list_all: bool = typer.Option(False, "--list", "-l", help="列出所有可用範本類型（依分類）"),
    generate_doc: bool = typer.Option(
        False,
        "--generate",
        "-g",
        help="顯示範本後直接啟動 generate 生成流程（template → generate → lint 一鍵閉環）",
    ),
    gen_output: str = typer.Option(
        "output.docx",
        "--gen-output",
        help="generate 的輸出 .docx 路徑（搭配 --generate 使用）",
    ),
    gen_preview: bool = typer.Option(False, "--gen-preview", help="generate 完成後在終端預覽（搭配 --generate 使用）"),
    gen_skip_review: bool = typer.Option(
        False,
        "--gen-skip-review",
        help="generate 時跳過多 Agent 審查步驟（搭配 --generate 使用）",
    ),
    gen_no_lint: bool = typer.Option(False, "--gen-no-lint", help="generate 時關閉自動 lint 檢查（搭配 --generate 使用）"),
) -> None:
    """顯示公文骨架範本，包含佔位符供快速填寫。"""
    if list_all:
        _show_template_list()
        return

    if doc_type not in _TEMPLATES:
        available = "、".join(_TEMPLATES.keys())
        console.print(f"[red]錯誤：不支援的範本類型「{doc_type}」。[/red]")
        console.print(f"[dim]可用類型：{available}[/dim]")
        console.print("[dim]使用 gov-ai template --list 查看分類清單。[/dim]")
        raise typer.Exit(1)

    content = _TEMPLATES[doc_type]
    console.print(
        Panel(
            Markdown(content),
            title=f"[bold cyan]公文範本 — {doc_type}[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    if not generate_doc:
        console.print("[dim]修改佔位符後可直接用作需求描述。[/dim]")
        console.print('[dim]填寫完成後可使用：gov-ai generate -i "填寫後的內容"[/dim]')
        console.print(f"[dim]或直接一鍵生成：gov-ai template {doc_type} --generate[/dim]")

    if output:
        with open(output, "w", encoding="utf-8") as handle:
            handle.write(content)
        console.print(f"[green]範本已匯出至：{output}[/green]")

    if generate_doc:
        console.print()
        console.print(
            Panel(
                f"[bold green]正在啟動 generate 流程...[/bold green]\n"
                f"[dim]範本類型：{doc_type}　輸出：{gen_output}[/dim]",
                title="[bold green]template → generate → lint[/bold green]",
                border_style="green",
            )
        )
        return_code = _launch_generate(
            content,
            gen_output,
            preview=gen_preview,
            skip_review=gen_skip_review,
            no_lint=gen_no_lint,
        )
        if return_code != 0:
            console.print(f"[yellow]generate 子流程以代碼 {return_code} 結束。[/yellow]")
            raise typer.Exit(return_code)


def _show_template_list() -> None:
    """以分類方式顯示所有可用範本。"""
    from rich.table import Table

    table = Table(
        title="[bold cyan]公文範本清單[/bold cyan]",
        border_style="cyan",
        header_style="bold",
        show_lines=True,
    )
    table.add_column("分類", style="bold yellow", min_width=12)
    table.add_column("範本類型", min_width=10)
    table.add_column("使用指令", style="dim")

    for category, types in _TEMPLATE_CATEGORIES.items():
        for index, template_type in enumerate(types):
            table.add_row(
                category if index == 0 else "",
                template_type,
                f"gov-ai template {template_type}",
            )

    console.print(table)
    console.print(f"[dim]共 {len(_TEMPLATES)} 種範本。使用 gov-ai template <類型> 顯示骨架。[/dim]")
