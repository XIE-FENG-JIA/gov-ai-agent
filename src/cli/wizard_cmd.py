"""互動式公文精靈。

引導使用者逐步輸入公文資訊，無需記憶 65+ 個 CLI 參數，
自動組合並呼叫 generate 流程產生合規公文草稿。
"""
from __future__ import annotations

import typer
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

from src.cli._wizard_helpers import (  # noqa: F401 — re-exported for backward compat
    DOC_TYPES,
    URGENCY_OPTIONS,
    _PROFILE_FILE,
    _build_input_text,
    _load_profile,
    _select_doc_type,
    _show_summary,
    _show_type_menu,
    console,
)


def wizard(
    dry_run: bool = typer.Option(False, "--dry-run", help="顯示將執行的命令，但不實際生成"),
    quick: bool = typer.Option(False, "--quick", "-q", help="快速模式：略過可選欄位（速別/日期/補充說明）"),
    output: str = typer.Option("output.docx", "--output", "-o", help="輸出檔案路徑"),
    cite: bool = typer.Option(True, "--cite/--no-cite", help="生成後顯示法規引用建議（預設開啟）"),
    skip_review: bool = typer.Option(False, "--skip-review", help="跳過多 Agent 審查（加快速度）"),
    preview: bool = typer.Option(False, "--preview", "-p", help="在終端預覽生成內容"),
    from_profile: bool = typer.Option(True, "--from-profile/--no-from-profile", help="自動從個人設定檔預填發文機關（預設開啟）"),
) -> None:
    """互動式公文精靈 — 逐步引導，無需記憶 CLI 參數。

    適合首次使用者或不熟悉公文格式的同仁。精靈會詢問：
    公文類型、發文機關、收文機關、主旨，以及選用的速別與日期，
    最後自動組合並呼叫 generate 命令產生合規公文草稿。

    如已使用 gov-ai profile set agency <機關名稱> 設定個人資料，
    精靈將自動預填發文機關，減少重複輸入。

    範例：
        gov-ai wizard
        gov-ai wizard --quick
        gov-ai wizard --dry-run
        gov-ai wizard -o 環保局函文.docx
        gov-ai wizard --no-from-profile
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

        # 從個人設定檔預填發文機關
        sender_default = ""
        if from_profile:
            profile = _load_profile()
            agency = profile.get("agency", "").strip()
            if agency:
                sender_default = agency
                console.print(f"  [dim]從個人設定檔預填：發文機關 = {agency}[/dim]")
                console.print("  [dim]（直接 Enter 採用，或輸入其他機關名稱覆寫）[/dim]")

        if sender_default:
            sender = Prompt.ask("[bold cyan]發文機關[/bold cyan]", default=sender_default)
        else:
            sender = Prompt.ask("[bold cyan]發文機關[/bold cyan]（如：臺北市政府環境保護局）")
        while not sender.strip():
            console.print("  [red]發文機關不可空白[/red]")
            sender = Prompt.ask("[bold cyan]發文機關[/bold cyan]（如：臺北市政府環境保護局）")

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
        run_wizard_generate(
            input_text=input_text,
            output=output,
            skip_review=skip_review,
            preview=preview,
            date=date.strip(),
            cite=cite,
        )

    except (KeyboardInterrupt, typer.Abort):
        console.print("\n[yellow]公文精靈已中止。[/yellow]")
        raise typer.Exit()
