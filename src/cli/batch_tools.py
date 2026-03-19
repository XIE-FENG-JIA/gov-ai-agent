"""批次處理工具指令群組。"""
import csv
import json
import os
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer()
console = Console()

_TEMPLATE_ITEMS = [
    {
        "input": "台北市政府環保局致各級學校，加強校園資源回收分類作業",
        "output": "batch_output_1.docx",
    },
    {
        "input": "衛生福利部函請各縣市衛生局，配合辦理流感疫苗接種事宜",
        "output": "batch_output_2.docx",
    },
    {
        "input": "教育部通知各大專校院，辦理校園安全防護演練",
        "output": "batch_output_3.docx",
    },
]


def _load_items(file_path: Path) -> list[dict]:
    """根據副檔名載入 JSON 或 CSV 批次檔案。"""
    if file_path.suffix.lower() == ".csv":
        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None or "input" not in reader.fieldnames:
                console.print("[red]CSV 必須包含 input 欄位[/red]")
                raise typer.Exit(code=1)
            items = []
            for row in reader:
                if not row.get("input", "").strip():
                    continue
                items.append({
                    "input": row["input"],
                    "output": row.get("output", "").strip() or f"batch_output_{len(items)+1}.docx",
                })
            return items
    else:
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            console.print(f"[red]JSON 格式錯誤：{e}[/red]")
            raise typer.Exit(code=1)
        if not isinstance(data, list):
            console.print("[red]JSON 必須是陣列[/red]")
            raise typer.Exit(code=1)
        return data


@app.command()
def template() -> None:
    """產生批次 JSON 範本檔案。"""
    path = Path("batch_template.json")
    path.write_text(json.dumps(_TEMPLATE_ITEMS, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"[green]已產生範本：{path}[/green]")
    console.print("請修改內容後執行 [bold]gov-ai generate --batch batch_template.json[/bold]")


@app.command()
def validate(file_path: str = typer.Argument(..., help="批次 JSON 或 CSV 檔案路徑")) -> None:
    """驗證批次檔案格式是否正確（支援 JSON 與 CSV）。"""
    p = Path(file_path)
    if not p.exists():
        console.print(f"[red]檔案不存在：{file_path}[/red]")
        raise typer.Exit(code=1)

    data = _load_items(p)

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
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
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

    required_sections = ["主旨", "說明"]
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

        missing = [s for s in required_sections if s not in text]
        issues = []
        if missing:
            issues.append(f"缺少：{'、'.join(missing)}")

        if strict:
            _INFORMAL = {"所以": "爰此", "但是": "惟", "而且": "且", "因為": "因", "可是": "然", "已經": "業已"}
            for informal in _INFORMAL:
                if informal in text:
                    issues.append(f"口語用詞「{informal}」")

        if issues:
            results.append({"file": os.path.basename(f), "status": "失敗", "detail": "；".join(issues)})
            has_failure = True
        else:
            results.append({"file": os.path.basename(f), "status": "通過", "detail": "格式正確"})

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
        with open(report, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
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

    _INFORMAL = {"所以": "爰此", "但是": "惟", "而且": "且", "因為": "因", "可是": "然", "還有": "另", "已經": "業已"}
    _REQUIRED = ["主旨", "說明"]
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

        issue_count = 0
        details = []
        for informal in _INFORMAL:
            if informal in text:
                issue_count += 1
                details.append(f"口語：{informal}")
        for section in _REQUIRED:
            if section not in text:
                issue_count += 1
                details.append(f"缺少：{section}")

        if issue_count > 0:
            has_issues = True
        detail_text = "；".join(details) if details else "通過"
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
        out_path.write_text(content, encoding="utf-8")
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
    Path(output).write_text(merged, encoding="utf-8")
    console.print(f"[green]已合併 {len(files)} 個檔案至 {output}[/green]")
