"""工作流程範本管理指令。

提供建立、列出、顯示、刪除與執行公文生成工作流程範本的功能。
範本以 JSON 格式儲存於 .gov-ai-workflows/ 目錄。
"""
import json
import os
import re

import typer
import yaml
from rich.console import Console
from rich.table import Table

app = typer.Typer()
console = Console()

_WORKFLOW_DIR = ".gov-ai-workflows"


def _ensure_dir() -> str:
    """確保工作流程目錄存在並回傳路徑。"""
    os.makedirs(_WORKFLOW_DIR, exist_ok=True)
    return _WORKFLOW_DIR


_VALID_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def _validate_workflow_name(name: str) -> None:
    """驗證工作流程名稱，防止路徑穿越攻擊。"""
    if not _VALID_NAME_RE.match(name):
        raise typer.BadParameter(
            f"範本名稱 '{name}' 包含不允許的字元，"
            "僅允許英數字、底線與連字號 [a-zA-Z0-9_-]。"
        )


def _workflow_path(name: str) -> str:
    """取得範本檔案路徑。"""
    _validate_workflow_name(name)
    return os.path.join(_WORKFLOW_DIR, f"{name}.json")


@app.command()
def create(
    name: str = typer.Argument(..., help="範本名稱"),
):
    """互動式建立工作流程範本。"""
    path = _workflow_path(name)
    if os.path.exists(path):
        console.print(f"[red]錯誤：範本 '{name}' 已存在。[/red]")
        raise typer.Exit(1)

    doc_type = typer.prompt("公文類型", default="函")
    skip_review = typer.confirm("是否跳過審查", default=False)
    convergence = False
    skip_info = False
    max_rounds = 3
    if not skip_review:
        convergence = typer.confirm("是否啟用分層收斂模式（零錯誤制）", default=False)
        if convergence:
            skip_info = typer.confirm("是否跳過 info 層級修正", default=False)
        else:
            max_rounds = typer.prompt("最大審查輪數", default=3, type=int)
    output_format = typer.prompt("輸出格式 (docx/markdown)", default="docx")

    if output_format not in ("docx", "markdown"):
        console.print("[red]錯誤：輸出格式必須為 docx 或 markdown。[/red]")
        raise typer.Exit(1)

    workflow = {
        "name": name,
        "doc_type": doc_type,
        "skip_review": skip_review,
        "max_rounds": max_rounds,
        "convergence": convergence,
        "skip_info": skip_info,
        "output_format": output_format,
    }

    _ensure_dir()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(workflow, f, ensure_ascii=False, indent=2)

    console.print(f"[green]範本 '{name}' 已建立。[/green]")


@app.command("list")
def list_workflows(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="顯示詳細資訊"),
):
    """列出所有已存工作流程範本。"""
    wf_dir = _WORKFLOW_DIR
    if not os.path.isdir(wf_dir):
        console.print("[yellow]尚無任何範本。[/yellow]")
        return

    files = [f for f in os.listdir(wf_dir) if f.endswith(".json")]
    if not files:
        console.print("[yellow]尚無任何範本。[/yellow]")
        return

    table = Table(title="工作流程範本")
    table.add_column("名稱", style="cyan")
    table.add_column("公文類型")
    table.add_column("跳過審查")
    table.add_column("最大輪數")
    table.add_column("輸出格式")
    if verbose:
        table.add_column("檔案大小", style="dim", justify="right")
        table.add_column("路徑", style="dim")

    for fname in sorted(files):
        fpath = os.path.join(wf_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                wf = json.load(f)
            if verbose:
                fsize = os.path.getsize(fpath)
                table.add_row(
                    wf.get("name", fname.replace(".json", "")),
                    wf.get("doc_type", ""),
                    "是" if wf.get("skip_review") else "否",
                    str(wf.get("max_rounds", "")),
                    wf.get("output_format", ""),
                    f"{fsize} bytes",
                    fpath,
                )
            else:
                table.add_row(
                    wf.get("name", fname.replace(".json", "")),
                    wf.get("doc_type", ""),
                    "是" if wf.get("skip_review") else "否",
                    str(wf.get("max_rounds", "")),
                    wf.get("output_format", ""),
                )
        except (json.JSONDecodeError, OSError):
            if verbose:
                table.add_row(fname.replace(".json", ""), "（讀取失敗）", "", "", "", "", "")
            else:
                table.add_row(fname.replace(".json", ""), "（讀取失敗）", "", "", "")

    console.print(table)
    if verbose:
        console.print("  [dim]詳細模式已啟用[/dim]")


@app.command()
def show(
    name: str = typer.Argument(..., help="範本名稱"),
):
    """顯示指定範本的內容。"""
    path = _workflow_path(name)
    if not os.path.exists(path):
        console.print(f"[red]錯誤：找不到範本 '{name}'。[/red]")
        raise typer.Exit(1)

    with open(path, "r", encoding="utf-8") as f:
        wf = json.load(f)

    console.print_json(json.dumps(wf, ensure_ascii=False))


@app.command()
def delete(
    name: str = typer.Argument(..., help="範本名稱"),
):
    """刪除指定的工作流程範本。"""
    path = _workflow_path(name)
    if not os.path.exists(path):
        console.print(f"[red]錯誤：找不到範本 '{name}'。[/red]")
        raise typer.Exit(1)

    os.remove(path)
    console.print(f"[green]範本 '{name}' 已刪除。[/green]")


@app.command()
def run(
    name: str = typer.Argument(..., help="範本名稱"),
    input_text: str = typer.Option(..., "--input", "-i", help="公文需求描述"),
    output_path: str = typer.Option("output.docx", "--output", "-o", help="輸出檔案路徑"),
):
    """依據範本設定執行公文生成。

    讀取範本中的設定，組合出對應的 generate 指令並執行。
    """
    path = _workflow_path(name)
    if not os.path.exists(path):
        console.print(f"[red]錯誤：找不到範本 '{name}'。[/red]")
        raise typer.Exit(1)

    with open(path, "r", encoding="utf-8") as f:
        wf = json.load(f)

    skip_review = wf.get("skip_review", False)
    max_rounds = wf.get("max_rounds", 3)
    convergence = wf.get("convergence", False)
    skip_info = wf.get("skip_info", False)
    output_format = wf.get("output_format", "docx")

    # 組合 generate 指令參數
    cmd_parts = ["gov-ai", "generate", "-i", f'"{input_text}"', "-o", output_path]
    if skip_review:
        cmd_parts.append("--skip-review")
    if convergence:
        cmd_parts.append("--convergence")
        if skip_info:
            cmd_parts.append("--skip-info")
    else:
        cmd_parts.extend(["--max-rounds", str(max_rounds)])
    if output_format == "markdown":
        cmd_parts.append("--markdown")

    cmd_str = " ".join(cmd_parts)
    console.print(f"[bold cyan]執行指令：[/bold cyan]{cmd_str}")

    # 直接呼叫 generate 函式
    from src.cli.generate import generate as gen_fn

    gen_fn(
        input_text=input_text,
        output_path=output_path,
        skip_review=skip_review,
        max_rounds=max_rounds,
        convergence=convergence,
        skip_info=skip_info,
        show_rounds=False,
        batch="",
        preview=False,
        retries=1,
        save_markdown=(output_format == "markdown"),
        quiet=False,
        confirm=False,
        export_report="",
        save_versions=False,
        from_file="",
        dry_run=False,
        lang_check=False,
        auto_sender=False,
        estimate=False,
        summary=False,
        priority_tag="",
        cc="",
        watermark="",
        header="",
        footnote="",
        ref_number="",
        encoding="utf-8",
        date="",
        sign="",
        attachment="",
        classification="",
        template_name="",
        receiver_title="",
        speed="normal",
        page_break=False,
        margin="standard",
        line_spacing="1.5",
        font_size="12",
        duplex="off",
        orientation="portrait",
        paper_size="A4",
        columns="1",
        seal="none",
        copy_count="1",
        draft_mark="none",
        urgency_label="normal",
        lang="zh-TW",
        header_logo="",
        disclaimer="",
    )


@app.command()
def detail(
    name: str = typer.Argument("", help="工作流程名稱（留空列出全部）"),
):
    """顯示工作流程範本的詳細資訊。"""
    from rich.panel import Panel

    # 預設範本
    templates = {
        "standard": {
            "name": "標準公文流程",
            "description": "一般公文的完整生成流程",
            "steps": ["需求分析", "草稿撰寫", "格式套用", "品質審查", "匯出"],
            "created": "內建範本",
        },
        "quick": {
            "name": "快速公文流程",
            "description": "跳過審查的快速生成流程",
            "steps": ["需求分析", "草稿撰寫", "格式套用", "匯出"],
            "created": "內建範本",
        },
        "review-only": {
            "name": "純審查流程",
            "description": "僅對現有公文進行品質審查",
            "steps": ["載入公文", "品質審查", "產生報告"],
            "created": "內建範本",
        },
    }

    if name:
        tmpl = templates.get(name)
        if not tmpl:
            console.print(f"[red]錯誤：找不到工作流程「{name}」[/red]")
            console.print(f"[dim]可用流程：{', '.join(templates.keys())}[/dim]")
            raise typer.Exit(1)
        steps_text = "\n".join(f"  {i}. {s}" for i, s in enumerate(tmpl["steps"], 1))
        content = (
            f"[bold]{tmpl['name']}[/bold]\n\n{tmpl['description']}"
            f"\n\n步驟：\n{steps_text}\n\n來源：{tmpl['created']}"
        )
        console.print(Panel(content, title=f"[cyan]{name}[/cyan]", border_style="cyan"))
        return

    # 列出全部
    table = Table(title="工作流程範本")
    table.add_column("名稱", style="cyan")
    table.add_column("說明", style="white")
    table.add_column("步驟數", style="green", justify="right")
    table.add_column("來源", style="dim")

    for key, tmpl in templates.items():
        table.add_row(key, tmpl["description"], str(len(tmpl["steps"])), tmpl["created"])

    console.print(table)
    console.print("\n[dim]使用 gov-ai workflow detail <name> 查看詳情。[/dim]")


@app.command(name="validate")
def workflow_validate(
    file_path: str = typer.Argument(..., help="工作流程 YAML 檔案路徑"),
):
    """驗證工作流程 YAML 檔案的結構與內容。"""
    if not os.path.exists(file_path):
        console.print(f"[red]錯誤：找不到檔案 '{file_path}'[/red]")
        raise typer.Exit(1)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError:
        console.print(f"[red]錯誤：YAML 格式錯誤，無法解析 '{file_path}'[/red]")
        raise typer.Exit(1)

    problems = []

    if not isinstance(data, dict):
        problems.append("檔案內容必須為 YAML 映射（字典）")
    else:
        if "name" not in data:
            problems.append("缺少必要欄位：name")
        if "steps" not in data:
            problems.append("缺少必要欄位：steps")
        elif not isinstance(data["steps"], list):
            problems.append("steps 必須為列表")
        elif len(data["steps"]) == 0:
            problems.append("steps 列表不得為空")
        else:
            for i, step in enumerate(data["steps"]):
                if not isinstance(step, dict) or "name" not in step:
                    problems.append(f"步驟 {i + 1} 缺少 name 欄位")

    if problems:
        console.print("[red]驗證失敗：[/red]")
        for p in problems:
            console.print(f"  - {p}")
        raise typer.Exit(1)

    console.print(f"[green]工作流程驗證通過：'{file_path}'[/green]")


@app.command(name="export")
def workflow_export(
    name: str = typer.Argument(..., help="範本名稱"),
    output: str = typer.Option("", "-o", "--output", help="匯出路徑（預設 <name>.export.json）"),
):
    """匯出工作流程範本為 JSON 檔案。"""
    import shutil
    path = _workflow_path(name)
    if not os.path.exists(path):
        console.print(f"[red]錯誤：找不到範本 '{name}'[/red]")
        raise typer.Exit(1)

    dst = output if output else f"{name}.export.json"
    shutil.copy2(path, dst)
    console.print(f"[green]已匯出範本 '{name}' 至 {dst}[/green]")
