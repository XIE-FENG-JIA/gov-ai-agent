"""gov-ai review — 對現有草稿執行多 Agent 審查，輸出具體修改建議。

使用方式：
    gov-ai review draft.md
    gov-ai review draft.md --doc-type 函
    gov-ai review draft.md --apply --output revised.md
    gov-ai review draft.md --apply --no-diff
    gov-ai review draft.md --json
"""
from __future__ import annotations

import difflib
import json
import logging
import os

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.cli.utils import atomic_text_write
from src.core.models import detect_doc_type as _detect_doc_type

logger = logging.getLogger(__name__)
console = Console()

# 延遲 import 封裝成模組層級變數，方便測試 mock
try:
    from src.api.dependencies import get_llm, get_kb
    from src.agents.editor import EditorInChief
except ImportError:  # pragma: no cover
    get_llm = None  # type: ignore[assignment]
    get_kb = None   # type: ignore[assignment]
    EditorInChief = None  # type: ignore[assignment]


def _severity_icon(severity: str) -> Text:
    icons = {
        "error": Text("[錯誤]", style="bold red"),
        "warning": Text("[警告]", style="bold yellow"),
        "info": Text("[資訊]", style="bold blue"),
    }
    return icons.get(severity, Text(f"[{severity}]"))


def _render_apply_diff(original: str, revised: str) -> None:
    """以 Rich 彩色格式顯示 apply 前後的 unified diff。

    綠色行（+）代表新增／修正內容，紅色行（-）代表被移除的原始文字。
    無差異時顯示「草稿未產生變更」提示。
    """
    diff_lines = list(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            revised.splitlines(keepends=True),
            fromfile="原始草稿",
            tofile="修正後草稿",
            lineterm="",
        )
    )

    if not diff_lines:
        console.print("[dim]（審查後草稿未產生任何變更）[/dim]")
        return

    diff_text = Text()
    for line in diff_lines:
        stripped = line.rstrip("\n")
        if stripped.startswith("+++") or stripped.startswith("---"):
            diff_text.append(stripped + "\n", style="bold")
        elif stripped.startswith("@@"):
            diff_text.append(stripped + "\n", style="cyan")
        elif stripped.startswith("+"):
            diff_text.append(stripped + "\n", style="bold green")
        elif stripped.startswith("-"):
            diff_text.append(stripped + "\n", style="bold red")
        else:
            diff_text.append(stripped + "\n")

    console.print(
        Panel(diff_text, title="[bold cyan]修改內容 Diff[/bold cyan]", expand=True)
    )


def _render_issues_table(agent_results: list[dict]) -> None:
    """以 Rich table 顯示所有 issues 及其具體修改建議。"""
    all_issues: list[tuple[str, dict]] = []
    for res in agent_results:
        for issue in res.get("issues", []):
            all_issues.append((res.get("agent_name", "Unknown"), issue))

    if not all_issues:
        console.print("[bold green]✓ 所有審查通過，未發現問題。[/bold green]")
        return

    table = Table(
        title="審查意見與修改建議",
        show_lines=True,
        expand=True,
        header_style="bold cyan",
    )
    table.add_column("嚴重度", width=8, justify="center")
    table.add_column("審查 Agent", width=18)
    table.add_column("位置", width=16)
    table.add_column("問題描述", width=36)
    table.add_column("具體修改建議", width=44, style="green")

    for agent_name, issue in all_issues:
        severity = issue.get("severity", "info")
        suggestion = issue.get("suggestion") or ""

        # 若無建議，顯示提示而非空白
        if not suggestion:
            suggestion = Text("（無自動建議，請人工判斷）", style="dim")
        else:
            suggestion = Text(suggestion, style="bold green")

        table.add_row(
            _severity_icon(severity),
            agent_name,
            issue.get("location", ""),
            issue.get("description", ""),
            suggestion,
        )

    console.print(table)


def review(
    draft_file: str = typer.Argument(..., help="要審查的草稿 Markdown 檔案路徑"),
    doc_type: str = typer.Option(
        None, "--doc-type", "-t",
        help="公文類型（如：函、公告、簽）。省略時自動從草稿內容偵測。",
    ),
    apply: bool = typer.Option(
        False, "--apply", "-a",
        help="審查後自動套用修改建議，輸出修正後的草稿。",
    ),
    output: str = typer.Option(
        None, "--output", "-o",
        help="--apply 時，修正後草稿的輸出路徑（預設：<原檔名>_revised.md）。",
    ),
    max_rounds: int = typer.Option(
        1, "--max-rounds",
        help="--apply 時的最大修正輪數（預設 1）。",
    ),
    show_diff: bool = typer.Option(
        True, "--diff/--no-diff",
        help="--apply 後顯示修改內容 diff（預設開啟）。",
    ),
    json_output: bool = typer.Option(
        False, "--json",
        help="以 JSON 格式輸出審查結果（適合程式化處理）。",
    ),
) -> None:
    """對現有草稿執行多 Agent 審查，輸出具體修改建議。

    不會修改原始檔案，除非加上 --apply 旗標。
    加上 --apply 後，預設會顯示修改 diff，可用 --no-diff 關閉。

    範例：

        gov-ai review draft.md

        gov-ai review draft.md --doc-type 函

        gov-ai review draft.md --apply --output revised.md

        gov-ai review draft.md --apply --no-diff

        gov-ai review draft.md --json > report.json
    """
    # 1. 讀取草稿
    if not os.path.isfile(draft_file):
        console.print(f"[red]錯誤：找不到檔案 {draft_file}[/red]")
        raise typer.Exit(1)

    try:
        with open(draft_file, encoding="utf-8") as f:
            draft_content = f.read()
    except OSError as exc:
        console.print(f"[red]錯誤：無法讀取檔案 {draft_file}：{exc}[/red]")
        raise typer.Exit(1)

    if not draft_content.strip():
        console.print("[red]錯誤：草稿檔案內容為空。[/red]")
        raise typer.Exit(1)

    # 2. 偵測公文類型
    detected_type = doc_type or _detect_doc_type(draft_content)
    if not doc_type:
        console.print(f"[dim]（自動偵測公文類型：{detected_type}）[/dim]")

    # 3. 初始化 LLM 與知識庫
    try:
        llm = get_llm()
        kb = get_kb()
    except Exception as exc:
        console.print(f"[red]錯誤：無法初始化 LLM/KB：{exc}[/red]")
        raise typer.Exit(1)

    # 4. 執行審查
    console.print(
        Panel(
            f"[bold]草稿：[/bold]{draft_file}\n"
            f"[bold]類型：[/bold]{detected_type}\n"
            f"[bold]模式：[/bold]{'審查 + 套用建議' if apply else '僅審查'}",
            title="[bold cyan]gov-ai review[/bold cyan]",
            expand=False,
        )
    )

    try:
        with EditorInChief(llm, kb) as editor:
            if apply:
                # 審查 + 套用建議
                refined_draft, qa_report = editor.review_and_refine(
                    draft_content, detected_type, max_rounds=max_rounds,
                )
            else:
                # 僅審查，不修改草稿
                qa_report = editor.run_review_only(draft_content, detected_type)
                refined_draft = None

    except Exception as exc:
        logger.exception("審查流程失敗: %s", exc)
        console.print(f"[red]審查失敗：{exc}[/red]")
        raise typer.Exit(1)

    # 5. 輸出結果
    if json_output:
        result_dict = {
            "draft_file": draft_file,
            "doc_type": detected_type,
            "overall_score": qa_report.overall_score,
            "risk_summary": qa_report.risk_summary,
            "agent_results": [
                {
                    "agent_name": r.agent_name,
                    "score": r.score,
                    "issues": [
                        {
                            "severity": i.severity,
                            "category": i.category,
                            "location": i.location,
                            "description": i.description,
                            "suggestion": i.suggestion,
                        }
                        for i in r.issues
                    ],
                }
                for r in qa_report.agent_results
            ],
        }
        typer.echo(json.dumps(result_dict, ensure_ascii=False, indent=2))
    else:
        # Rich 顯示：分數摘要 + 詳細 issues 表格
        risk_color = {
            "Safe": "green", "Low": "green",
            "Moderate": "yellow", "High": "red", "Critical": "bold red",
        }.get(qa_report.risk_summary, "white")

        console.print()
        console.print(
            f"  總分：[bold]{qa_report.overall_score:.2f}[/bold]  "
            f"風險：[{risk_color}]{qa_report.risk_summary}[/{risk_color}]"
        )
        console.print()
        _render_issues_table(
            [r.model_dump() for r in qa_report.agent_results]
        )

    # 6. 若 --apply，寫出修正草稿並顯示 diff
    if apply and refined_draft is not None:
        if not output:
            base = os.path.splitext(draft_file)[0]
            output = f"{base}_revised.md"
        try:
            atomic_text_write(output, refined_draft)
            console.print(f"\n[bold green]✓ 修正後草稿已寫入：{output}[/bold green]")
        except OSError as exc:
            console.print(f"[red]警告：無法寫入輸出檔案 {output}：{exc}[/red]")

        # 顯示 diff（--no-diff 可關閉）
        if show_diff and not json_output:
            console.print()
            _render_apply_diff(draft_content, refined_draft)
