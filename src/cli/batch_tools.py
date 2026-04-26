"""批次處理工具指令群組。"""
import os
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from src.cli._batch_runner import (
    BatchLoadError,
    _TEMPLATE_ITEMS,
    _load_items,
    check_doc_content,
    lint_doc_content,
)
from src.cli.utils_io import atomic_json_write, atomic_text_write

app = typer.Typer()
console = Console()


@app.command()
def template() -> None:
    """產生批次 JSON 範本檔案。"""
    path = Path("batch_template.json")
    atomic_json_write(str(path), _TEMPLATE_ITEMS)
    console.print(f"[green]已產生範本：{path}[/green]")
    console.print("請修改內容後執行 [bold]gov-ai generate --batch batch_template.json[/bold]")


@app.command()
def validate(file_path: str = typer.Argument(..., help="批次 JSON 或 CSV 檔案路徑")) -> None:
    """驗證批次檔案格式是否正確（支援 JSON 與 CSV）。"""
    p = Path(file_path)
    if not p.exists():
        console.print(f"[red]檔案不存在：{file_path}[/red]")
        raise typer.Exit(code=1)

    try:
        data = _load_items(p)
    except BatchLoadError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)

    if len(data) == 0:
        console.print("[red]檔案必須包含至少一筆資料[/red]")
        raise typer.Exit(code=1)
    for i, item in enumerate(data):
        if not isinstance(item, dict) or "input" not in item or "output" not in item:
            console.print(f"[red]第 {i+1} 筆缺少 input 或 output 欄位[/red]")
            raise typer.Exit(code=1)

    table = Table(title="批次任務預覽")
    table.add_column("#", style="bold")
    table.add_column("輸入（前 40 字）")
    table.add_column("輸出檔名")
    for i, item in enumerate(data, 1):
        table.add_row(str(i), item["input"][:40], item["output"])
    console.print(table)
    console.print(f"[green]驗證通過，共 {len(data)} 筆[/green]")


@app.command()
def create() -> None:
    """互動式建立批次 JSON 檔案。"""
    items: list[dict] = []
    console.print("[bold]互動式批次建立[/bold]（輸入空行結束）")
    n = 0
    while True:
        n += 1
        desc = typer.prompt(f"第 {n} 筆公文需求描述（空行結束）", default="", show_default=False)
        if not desc.strip():
            break
        default_out = f"batch_output_{n}.docx"
        out = typer.prompt("輸出檔名", default=default_out)
        items.append({"input": desc, "output": out})

    if not items:
        console.print("[yellow]未輸入任何資料，取消建立。[/yellow]")
        raise typer.Exit(code=1)

    path = Path("batch.json")
    atomic_json_write(str(path), items)
    console.print(f"[green]已儲存 {len(items)} 筆至 {path}[/green]")


@app.command(name="validate-docs")
def validate_docs(
    files: list[str] = typer.Argument(..., help="要驗證的公文檔案路徑"),
    strict: bool = typer.Option(False, "--strict", help="嚴格模式（口語化用詞也視為錯誤）"),
    report: str = typer.Option("", "--report", "-r", help="匯出驗證報告（JSON 檔案路徑）"),
) -> None:
    """批次驗證多份公文的基本格式。"""

    if not files:
        console.print("[red]錯誤：請指定至少一個檔案。[/red]")
        raise typer.Exit(1)

    results = []
    has_failure = False

    for f in files:
        if not os.path.isfile(f):
            results.append({"file": f, "status": "錯誤", "detail": "找不到檔案"})
            has_failure = True
            continue

        try:
            with open(f, "r", encoding="utf-8-sig") as fh:
                text = fh.read()
        except UnicodeDecodeError:
            results.append({"file": f, "status": "錯誤", "detail": "編碼不支援"})
            has_failure = True
            continue

        status, detail = check_doc_content(text, strict)
        results.append({"file": os.path.basename(f), "status": status, "detail": detail})
        if status == "失敗":
            has_failure = True
    table = Table(title="批次驗證結果")
    table.add_column("檔案", style="cyan")
    table.add_column("狀態", style="bold")
    table.add_column("詳情", style="white")

    for r in results:
        style = "green" if r["status"] == "通過" else "red"
        table.add_row(r["file"], f"[{style}]{r['status']}[/{style}]", r["detail"])

    console.print(table)

    passed = sum(1 for r in results if r["status"] == "通過")
    failed = len(results) - passed
    console.print(f"\n[dim]驗證 {len(results)} 個檔案：{passed} 通過，{failed} 失敗[/dim]")

    if report:
        report_data = {
            "total_files": len(files),
            "passed": passed,
            "failed": failed,
            "results": results,
        }
        atomic_json_write(report, report_data)
        console.print(f"[green]驗證報告已匯出至：{report}[/green]")

    if has_failure:
        raise typer.Exit(1)


@app.command(name="lint")
def batch_lint(
    files: list[str] = typer.Argument(..., help="要檢查的公文檔案路徑"),
) -> None:
    """批次檢查多份公文的用語品質。"""

    if not files:
        console.print("[red]錯誤：請指定至少一個檔案。[/red]")
        raise typer.Exit(1)

    has_issues = False
    results = []

    for f in files:
        if not os.path.isfile(f):
            results.append({"file": os.path.basename(f), "issues": -1, "detail": "找不到檔案"})
            has_issues = True
            continue
        try:
            with open(f, "r", encoding="utf-8-sig") as fh:
                text = fh.read()
        except UnicodeDecodeError:
            results.append({"file": os.path.basename(f), "issues": -1, "detail": "編碼錯誤"})
            has_issues = True
            continue

        issue_count, detail_text = lint_doc_content(text)
        if issue_count > 0:
            has_issues = True
        results.append({
            "file": os.path.basename(f),
            "issues": issue_count,
            "detail": detail_text,
        })

    table = Table(title="批次 Lint 結果")
    table.add_column("檔案", style="cyan")
    table.add_column("問題數", style="bold", justify="right")
    table.add_column("詳情", style="white")

    for r in results:
        style = "red" if r["issues"] != 0 else "green"
        issues_str = str(r["issues"]) if r["issues"] >= 0 else "錯誤"
        table.add_row(r["file"], f"[{style}]{issues_str}[/{style}]", r["detail"])

    console.print(table)
    total_issues = sum(r["issues"] for r in results if r["issues"] > 0)
    console.print(f"\n[dim]檢查 {len(results)} 個檔案，共 {total_issues} 個問題。[/dim]")

    if has_issues:
        raise typer.Exit(1)


@app.command(name="convert")
def batch_convert(
    files: list[str] = typer.Argument(..., help="要轉換的檔案路徑（支援多個）"),
    to_format: str = typer.Option("md", "--to", help="目標格式（md/txt）"),
    output_dir: str = typer.Option("", "--output-dir", "-o", help="輸出目錄（預設同目錄）"),
) -> None:
    """批次轉換檔案格式（md/txt 互轉）。"""
    # 驗證所有檔案存在
    for f in files:
        if not os.path.isfile(f):
            console.print(f"[red]找不到檔案：{f}[/red]")
            raise typer.Exit(code=1)

    target_ext = f".{to_format}"
    converted = 0

    for f in files:
        p = Path(f)
        content = p.read_text(encoding="utf-8")
        new_name = p.stem + target_ext
        if output_dir:
            out_path = Path(output_dir) / new_name
        else:
            out_path = p.parent / new_name
        atomic_text_write(str(out_path), content)
        console.print(f"[green]{p.name} → {out_path.name}[/green]")
        converted += 1

    console.print(f"\n[bold]已轉換 {converted} 個檔案[/bold]")


@app.command(name="merge")
def batch_merge(
    files: list[str] = typer.Argument(..., help="要合併的檔案路徑"),
    output: str = typer.Option("merged.txt", "--output", "-o", help="輸出檔案路徑"),
    separator: str = typer.Option("\n---\n", "--separator", "-s", help="檔案間分隔符"),
) -> None:
    """批次合併多個檔案為單一檔案。"""
    for f in files:
        if not os.path.isfile(f):
            console.print(f"[red]找不到檔案：{f}[/red]")
            raise typer.Exit(code=1)

    contents = []
    for f in files:
        text = Path(f).read_text(encoding="utf-8")
        contents.append(text)

    merged = separator.join(contents)
    atomic_text_write(output, merged)
    console.print(f"[green]已合併 {len(files)} 個檔案至 {output}[/green]")
