"""互動式公文精靈。

引導使用者逐步輸入公文資訊，無需記憶 65+ 個 CLI 參數，
自動組合並呼叫 generate 流程產生合規公文草稿。
"""
from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm

console = Console()

# 12 種公文類型 — 依使用頻率排序
DOC_TYPES: list[tuple[str, str, str]] = [
    ("函",        "一般公文",         "機關間往復聯繫最常用，適合申請、通知、詢問等"),
    ("公告",      "對外公告",         "向公眾或特定對象宣布事項"),
    ("簽",        "內部簽呈",         "內部陳報、請示或提案，上簽長官核示"),
    ("書函",      "平行函文",         "與平行機關或民眾的正式往來文書"),
    ("令",        "行政命令",         "發布法規、命令或人事令"),
    ("開會通知單","會議通知",         "召集開會、通知與會人員"),
    ("呈",        "下級呈上級",       "下級機關向上級或向總統陳報"),
    ("咨",        "總統↔立法院",      "總統與立法院間的往復文書"),
    ("會勘通知單","現場勘查通知",     "通知相關單位到場會同勘查"),
    ("公務電話紀錄","電話溝通紀錄",   "記錄公務電話內容以備查考"),
    ("手令",      "首長指令",         "機關首長對所屬人員的指示命令"),
    ("箋函",      "機關內部簡便文書", "機關內部便箋、聯絡單等簡便文書"),
]

URGENCY_OPTIONS = ["普通", "速件", "最速件"]


def _show_type_menu() -> None:
    """顯示公文類型選單。"""
    table = Table(
        title="公文類型選單",
        show_header=True,
        header_style="bold cyan",
        show_lines=True,
        border_style="cyan",
    )
    table.add_column("序號", width=4, justify="right", style="dim")
    table.add_column("類型", width=10, style="bold yellow")
    table.add_column("說明", width=12, style="cyan")
    table.add_column("使用時機", style="dim")

    for i, (dtype, label, hint) in enumerate(DOC_TYPES, 1):
        table.add_row(str(i), dtype, label, hint)

    console.print(table)


def _select_doc_type() -> str:
    """互動選擇公文類型，傳回類型名稱。"""
    _show_type_menu()
    while True:
        raw = Prompt.ask(
            "\n[bold cyan]請選擇公文類型[/bold cyan] (輸入序號 1-12，或直接輸入類型名稱)",
            default="1",
        )
        # 數字選擇
        if raw.strip().isdigit():
            idx = int(raw.strip()) - 1
            if 0 <= idx < len(DOC_TYPES):
                chosen = DOC_TYPES[idx][0]
                console.print(f"  [green]✓[/green] 已選擇：[bold]{chosen}[/bold]（{DOC_TYPES[idx][1]}）")
                return chosen
            console.print(f"  [red]請輸入 1 到 {len(DOC_TYPES)} 之間的數字[/red]")
        else:
            # 名稱選擇
            names = [t[0] for t in DOC_TYPES]
            if raw.strip() in names:
                idx = names.index(raw.strip())
                console.print(f"  [green]✓[/green] 已選擇：[bold]{raw.strip()}[/bold]（{DOC_TYPES[idx][1]}）")
                return raw.strip()
            console.print(f"  [red]未知類型「{raw.strip()}」，請重新選擇[/red]")


def _build_input_text(
    doc_type: str,
    sender: str,
    receiver: str,
    subject: str,
    urgency: str,
    extra_context: str,
) -> str:
    """從精靈蒐集到的欄位組合成 generate -i 所需的自然語言描述。"""
    parts = [f"{sender}"]
    if doc_type in ("函", "書函", "呈", "咨", "箋函"):
        parts.append(f"發給{receiver}")
    elif doc_type == "公告":
        parts.append("公告")
    elif doc_type == "簽":
        parts.append("簽請")
    elif doc_type in ("令", "手令"):
        parts.append(f"發布{doc_type}")
    elif doc_type == "開會通知單":
        parts.append(f"通知{receiver}開會")
    elif doc_type == "會勘通知單":
        parts.append(f"通知{receiver}會勘")
    elif doc_type == "公務電話紀錄":
        parts.append(f"與{receiver}電話聯繫")
    else:
        parts.append(f"致{receiver}")

    parts.append(f"，主旨：{subject}")

    if urgency != "普通":
        parts.append(f"（{urgency}）")
    if extra_context:
        parts.append(f"，補充說明：{extra_context}")

    return "".join(parts)


def _show_summary(
    doc_type: str,
    sender: str,
    receiver: str,
    subject: str,
    urgency: str,
    output_path: str,
    date: str,
    cite: bool,
) -> None:
    """顯示即將生成的公文摘要。"""
    lines = [
        f"[bold]公文類型：[/bold]{doc_type}",
        f"[bold]發文機關：[/bold]{sender}",
        f"[bold]收文機關：[/bold]{receiver}",
        f"[bold]主  旨：[/bold]{subject}",
        f"[bold]速    別：[/bold]{urgency}",
        f"[bold]輸出路徑：[/bold]{output_path}",
    ]
    if date:
        lines.append(f"[bold]發文日期：[/bold]{date}")
    lines.append(f"[bold]法規引用：[/bold]{'自動顯示' if cite else '略過'}")

    console.print(Panel(
        "\n".join(lines),
        title="[bold green]公文精靈 — 生成摘要[/bold green]",
        border_style="green",
    ))


def wizard(
    dry_run: bool = typer.Option(False, "--dry-run", help="顯示將執行的命令，但不實際生成"),
    quick: bool = typer.Option(False, "--quick", "-q", help="快速模式：略過可選欄位（速別/日期/補充說明）"),
    output: str = typer.Option("output.docx", "--output", "-o", help="輸出檔案路徑"),
    cite: bool = typer.Option(True, "--cite/--no-cite", help="生成後顯示法規引用建議（預設開啟）"),
    skip_review: bool = typer.Option(False, "--skip-review", help="跳過多 Agent 審查（加快速度）"),
    preview: bool = typer.Option(False, "--preview", "-p", help="在終端預覽生成內容"),
) -> None:
    """互動式公文精靈 — 逐步引導，無需記憶 CLI 參數。

    適合首次使用者或不熟悉公文格式的同仁。精靈會詢問：
    公文類型、發文機關、收文機關、主旨，以及選用的速別與日期，
    最後自動組合並呼叫 generate 命令產生合規公文草稿。

    範例：
        gov-ai wizard
        gov-ai wizard --quick
        gov-ai wizard --dry-run
        gov-ai wizard -o 環保局函文.docx
    """
    console.print(Panel(
        "[bold cyan]公文精靈[/bold cyan] — 逐步引導，快速生成合規公文草稿\n\n"
        "本精靈將詢問幾個問題，自動組合完整的公文生成指令。\n"
        "[dim]按 Ctrl+C 可隨時中止[/dim]",
        border_style="cyan",
        title="[bold]gov-ai wizard[/bold]",
    ))

    try:
        # === 步驟 1：公文類型 ===
        console.print("\n[bold]步驟 1／4 — 選擇公文類型[/bold]")
        doc_type = _select_doc_type()

        # === 步驟 2：發文與收文機關 ===
        console.print("\n[bold]步驟 2／4 — 機關資訊[/bold]")
        sender = Prompt.ask("[bold cyan]發文機關[/bold cyan]（如：臺北市政府環境保護局）")
        while not sender.strip():
            console.print("  [red]發文機關不可空白[/red]")
            sender = Prompt.ask("[bold cyan]發文機關[/bold cyan]")

        if doc_type in ("簽",):
            receiver = Prompt.ask("[bold cyan]受文者（簽請對象）[/bold cyan]（如：局長）", default="局長")
        else:
            receiver = Prompt.ask("[bold cyan]收文機關／受文者[/bold cyan]（如：各區公所）")
        while not receiver.strip():
            console.print("  [red]收文機關不可空白[/red]")
            receiver = Prompt.ask("[bold cyan]收文機關／受文者[/bold cyan]")

        # === 步驟 3：主旨 ===
        console.print("\n[bold]步驟 3／4 — 公文主旨[/bold]")
        console.print("  [dim]請簡述公文目的，精靈將以此作為 AI 生成的核心依據[/dim]")
        subject = Prompt.ask("[bold cyan]主旨[/bold cyan]（如：請配合辦理資源回收宣導活動）")
        while len(subject.strip()) < 5:
            console.print("  [red]主旨至少需要 5 個字[/red]")
            subject = Prompt.ask("[bold cyan]主旨[/bold cyan]")

        # === 步驟 4：選用欄位 ===
        urgency = "普通"
        date = ""
        extra_context = ""

        if not quick:
            console.print("\n[bold]步驟 4／4 — 選用設定（直接 Enter 跳過）[/bold]")

            # 速別
            urgency_input = Prompt.ask(
                f"[cyan]速別[/cyan]（{' / '.join(URGENCY_OPTIONS)}）",
                default="普通",
            )
            if urgency_input in URGENCY_OPTIONS:
                urgency = urgency_input
            else:
                console.print(f"  [yellow]未知速別「{urgency_input}」，使用預設「普通」[/yellow]")

            # 日期
            date = Prompt.ask(
                "[cyan]發文日期[/cyan]（如：114年3月27日，留空由系統填入）",
                default="",
            )

            # 補充說明
            extra_context = Prompt.ask(
                "[cyan]補充說明[/cyan]（選填，如法規依據、背景說明等）",
                default="",
            )

        # === 組合輸入文字 ===
        input_text = _build_input_text(
            doc_type=doc_type,
            sender=sender.strip(),
            receiver=receiver.strip(),
            subject=subject.strip(),
            urgency=urgency,
            extra_context=extra_context.strip(),
        )

        # === 顯示摘要 ===
        console.print()
        _show_summary(
            doc_type=doc_type,
            sender=sender.strip(),
            receiver=receiver.strip(),
            subject=subject.strip(),
            urgency=urgency,
            output_path=output,
            date=date.strip(),
            cite=cite,
        )

        if dry_run:
            # 顯示等效命令但不執行
            date_flag = f' --date "{date.strip()}"' if date.strip() else ""
            cite_flag = " --no-cite" if not cite else ""
            review_flag = " --skip-review" if skip_review else ""
            preview_flag = " --preview" if preview else ""
            console.print(Panel(
                f'gov-ai generate \\\n'
                f'  --input "{input_text}" \\\n'
                f'  --output "{output}"{date_flag}{cite_flag}{review_flag}{preview_flag}',
                title="[bold yellow]等效命令（dry-run 模式，未實際執行）[/bold yellow]",
                border_style="yellow",
            ))
            return

        if not Confirm.ask("\n[bold]確認生成？[/bold]", default=True):
            console.print("[yellow]已取消。如需重新設定，請再次執行 gov-ai wizard[/yellow]")
            raise typer.Exit()

        # === 呼叫 generate ===
        console.print("\n[dim]正在啟動生成流程…[/dim]\n")
        from src.cli.generate import generate as _generate

        _generate(
            input_text=input_text,
            output_path=output,
            skip_review=skip_review,
            max_rounds=3,
            convergence=False,
            skip_info=False,
            show_rounds=False,
            batch="",
            workers=1,
            preview=preview,
            retries=1,
            save_markdown=False,
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
            date=date.strip(),
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
            cite=cite,
        )

    except (KeyboardInterrupt, typer.Abort):
        console.print("\n[yellow]公文精靈已中止。[/yellow]")
        raise typer.Exit()
