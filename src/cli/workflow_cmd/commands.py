"""workflow 指令實作。"""

import json
import os
import shutil

import typer
import yaml
from rich.panel import Panel
from rich.table import Table
from src.cli.utils import atomic_json_write

from . import app, console, _ensure_dir, _workflow_path
from .helpers import build_generate_command, builtin_templates, load_workflow, validate_workflow_yaml


@app.command()
def create(
    name: str = typer.Argument(..., help="範本名稱"),
) -> None:
    """互動式建立工作流程範本。"""
    path = _workflow_path(name, for_write=True)
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
    atomic_json_write(path, workflow)
    console.print(f"[green]範本 '{name}' 已建立。[/green]")


@app.command("list")
def list_workflows(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="顯示詳細資訊"),
) -> None:
    """列出所有已存工作流程範本。"""
    workflow_dir = os.path.dirname(_workflow_path("probe", for_write=False))
    if not os.path.isdir(workflow_dir):
        console.print("[yellow]尚無任何範本。[/yellow]")
        return

    files = [name for name in os.listdir(workflow_dir) if name.endswith(".json")]
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

    for filename in sorted(files):
        file_path = os.path.join(workflow_dir, filename)
        try:
            workflow = load_workflow(file_path)
            row = [
                workflow.get("name", filename.replace(".json", "")),
                workflow.get("doc_type", ""),
                "是" if workflow.get("skip_review") else "否",
                str(workflow.get("max_rounds", "")),
                workflow.get("output_format", ""),
            ]
            if verbose:
                row.extend([f"{os.path.getsize(file_path)} bytes", file_path])
            table.add_row(*row)
        except (json.JSONDecodeError, OSError):
            if verbose:
                table.add_row(filename.replace(".json", ""), "（讀取失敗）", "", "", "", "", "")
            else:
                table.add_row(filename.replace(".json", ""), "（讀取失敗）", "", "", "")

    console.print(table)
    if verbose:
        console.print("  [dim]詳細模式已啟用[/dim]")


@app.command()
def show(
    name: str = typer.Argument(..., help="範本名稱"),
) -> None:
    """顯示指定範本的內容。"""
    path = _workflow_path(name, for_write=False)
    if not os.path.exists(path):
        console.print(f"[red]錯誤：找不到範本 '{name}'。[/red]")
        raise typer.Exit(1)

    console.print_json(json.dumps(load_workflow(path), ensure_ascii=False))


@app.command()
def delete(
    name: str = typer.Argument(..., help="範本名稱"),
) -> None:
    """刪除指定的工作流程範本。"""
    path = _workflow_path(name, for_write=True)
    if not os.path.exists(path):
        console.print(f"[red]錯誤：找不到範本 '{name}'。[/red]")
        raise typer.Exit(1)

    try:
        os.remove(path)
    except OSError as exc:
        console.print(f"[red]無法刪除範本（可能被其他程序佔用）: {exc}[/red]")
        raise typer.Exit(1)
    console.print(f"[green]範本 '{name}' 已刪除。[/green]")


@app.command()
def run(
    name: str = typer.Argument(..., help="範本名稱"),
    input_text: str = typer.Option(..., "--input", "-i", help="公文需求描述"),
    output_path: str = typer.Option("output.docx", "--output", "-o", help="輸出檔案路徑"),
) -> None:
    """依據範本設定執行公文生成。"""
    path = _workflow_path(name, for_write=False)
    if not os.path.exists(path):
        console.print(f"[red]錯誤：找不到範本 '{name}'。[/red]")
        raise typer.Exit(1)

    workflow = load_workflow(path)
    skip_review = workflow.get("skip_review", False)
    max_rounds = workflow.get("max_rounds", 3)
    convergence = workflow.get("convergence", False)
    skip_info = workflow.get("skip_info", False)
    output_format = workflow.get("output_format", "docx")

    command_preview = build_generate_command(
        input_text=input_text,
        output_path=output_path,
        skip_review=skip_review,
        max_rounds=max_rounds,
        convergence=convergence,
        skip_info=skip_info,
        output_format=output_format,
    )
    console.print(f"[bold cyan]執行指令：[/bold cyan]{command_preview}")

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
) -> None:
    """顯示工作流程範本的詳細資訊。"""
    templates = builtin_templates()

    if name:
        template = templates.get(name)
        if not template:
            console.print(f"[red]錯誤：找不到工作流程「{name}」[/red]")
            console.print(f"[dim]可用流程：{', '.join(templates.keys())}[/dim]")
            raise typer.Exit(1)
        steps_text = "\n".join(f"  {index}. {step}" for index, step in enumerate(template["steps"], 1))
        content = (
            f"[bold]{template['name']}[/bold]\n\n{template['description']}"
            f"\n\n步驟：\n{steps_text}\n\n來源：{template['created']}"
        )
        console.print(Panel(content, title=f"[cyan]{name}[/cyan]", border_style="cyan"))
        return

    table = Table(title="工作流程範本")
    table.add_column("名稱", style="cyan")
    table.add_column("說明", style="white")
    table.add_column("步驟數", style="green", justify="right")
    table.add_column("來源", style="dim")

    for key, template in templates.items():
        table.add_row(key, template["description"], str(len(template["steps"])), template["created"])

    console.print(table)
    console.print("\n[dim]使用 gov-ai workflow detail <name> 查看詳情。[/dim]")


@app.command(name="validate")
def workflow_validate(
    file_path: str = typer.Argument(..., help="工作流程 YAML 檔案路徑"),
) -> None:
    """驗證工作流程 YAML 檔案的結構與內容。"""
    if not os.path.exists(file_path):
        console.print(f"[red]錯誤：找不到檔案 '{file_path}'[/red]")
        raise typer.Exit(1)

    try:
        with open(file_path, "r", encoding="utf-8") as file_obj:
            data = yaml.safe_load(file_obj)
    except yaml.YAMLError:
        console.print(f"[red]錯誤：YAML 格式錯誤，無法解析 '{file_path}'[/red]")
        raise typer.Exit(1)

    problems = validate_workflow_yaml(data)
    if problems:
        console.print("[red]驗證失敗：[/red]")
        for problem in problems:
            console.print(f"  - {problem}")
        raise typer.Exit(1)

    console.print(f"[green]工作流程驗證通過：'{file_path}'[/green]")


@app.command(name="export")
def workflow_export(
    name: str = typer.Argument(..., help="範本名稱"),
    output: str = typer.Option("", "-o", "--output", help="匯出路徑（預設 <name>.export.json）"),
) -> None:
    """匯出工作流程範本為 JSON 檔案。"""
    path = _workflow_path(name, for_write=False)
    if not os.path.exists(path):
        console.print(f"[red]錯誤：找不到範本 '{name}'[/red]")
        raise typer.Exit(1)

    destination = output if output else f"{name}.export.json"
    shutil.copy2(path, destination)
    console.print(f"[green]已匯出範本 '{name}' 至 {destination}[/green]")
