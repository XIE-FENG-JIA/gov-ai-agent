import typer
from rich.console import Console
from rich.table import Table

from src.cli._lint_rules import (
    _INFORMAL_TERMS,
    _SUBJECT_CLOSINGS,
    _check_attachment_numbering,
    _check_doc_number,
    _check_main_copy,
    _check_seal_format,
    _check_speed_level,
    _check_subject_closing,
    _run_lint,
)

console = Console()


def lint(
    file: str = typer.Option(..., "-f", "--file", help="要檢查的公文檔案路徑"),
    fix: bool = typer.Option(False, "--fix", help="自動修正口語化用詞"),
):
    """輕量公文用語與格式檢查。"""
    import os
    if not os.path.isfile(file):
        console.print(f"[red]錯誤：找不到檔案：{file}[/red]")
        raise typer.Exit(1)

    try:
        with open(file, "r", encoding="utf-8-sig") as f:
            text = f.read()
    except UnicodeDecodeError:
        console.print("[red]錯誤：檔案編碼不支援，請使用 UTF-8。[/red]")
        raise typer.Exit(1)

    issues = _run_lint(text)

    # 自動修正
    if fix:
        fixed_text = text
        fix_count = 0
        for informal, formal in _INFORMAL_TERMS.items():
            if informal in fixed_text:
                count = fixed_text.count(informal)
                fixed_text = fixed_text.replace(informal, formal)
                fix_count += count
        if fix_count > 0:
            with open(file, "w", encoding="utf-8") as f:
                f.write(fixed_text)
            console.print(f"[green]已自動修正 {fix_count} 處口語化用詞。[/green]")
        else:
            console.print("[green]無需修正。[/green]")
        return

    # 輸出結果
    if not issues:
        console.print("[bold green]✓ 未發現問題，公文用語與格式良好。[/bold green]")
        return

    table = Table(title="公文 Lint 檢查結果")
    table.add_column("行號", style="cyan", width=6)
    table.add_column("類別", style="yellow", width=12)
    table.add_column("說明", style="white")

    for issue in issues:
        line_str = str(issue["line"]) if issue["line"] > 0 else "—"
        table.add_row(line_str, issue["category"], issue["detail"])

    console.print(table)
    console.print(f"\n[bold yellow]共發現 {len(issues)} 個問題。[/bold yellow]")
    raise typer.Exit(1)
