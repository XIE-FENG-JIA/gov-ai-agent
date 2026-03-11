import csv
import json
import os
import re
import sys
import time

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
from rich.status import Status

# Import all our components
from src.core.config import ConfigManager
from src.core.llm import get_llm_factory, LiteLLMProvider
from src.knowledge.manager import KnowledgeBaseManager
from src.agents.editor import EditorInChief
from src.agents.requirement import RequirementAgent
from src.agents.writer import WriterAgent
from src.agents.template import TemplateEngine
from src.document.exporter import DocxExporter
from src.utils.tw_check import detect_simplified
from src.utils.lang_check import check_language
from src.cli.history import append_record
from src.core.error_analyzer import ErrorAnalyzer

console = Console()
app = typer.Typer()

from src.core.constants import MAX_USER_INPUT_LENGTH

_INPUT_MIN_LENGTH = 5
_INPUT_MAX_LENGTH = MAX_USER_INPUT_LENGTH

# 用於移除路徑資訊的 regex（Windows + Unix 路徑）
_PATH_PATTERN = re.compile(r"[A-Za-z]:\\[\w\\. -]+|/[\w/. -]{5,}")


def _save_version(content: str, output_path: str, version: int, label: str):
    """將草稿版本儲存至 <basename>_v<N>.md 檔案。"""
    base = os.path.splitext(output_path)[0]
    ver_path = f"{base}_v{version}.md"
    try:
        with open(ver_path, "w", encoding="utf-8") as f:
            f.write(content)
        console.print(f"  [dim]版本 {version}（{label}）已儲存：{ver_path}[/dim]")
    except OSError as e:
        console.print(f"  [yellow]版本儲存失敗：{e}[/yellow]")


def _sanitize_error(exc: Exception, max_len: int = 120) -> str:
    """將例外訊息截斷並移除可能的檔案系統路徑。"""
    msg = str(exc)
    msg = _PATH_PATTERN.sub("<path>", msg)
    if len(msg) > max_len:
        msg = msg[:max_len] + "..."
    return msg

def _read_interactive_input() -> str:
    """從 stdin 管道或互動式提示取得使用者輸入。"""
    # 檢查 stdin 是否有管道輸入
    if not sys.stdin.isatty():
        piped = sys.stdin.read().strip()
        if piped:
            console.print(f"[dim]從 stdin 讀取到 {len(piped)} 字的需求描述。[/dim]")
            return piped

    # 互動式提示
    console.print("[bold cyan]公文需求描述[/bold cyan]")
    console.print("[dim]請輸入您的公文需求（至少 5 字），包含發文者、受文者和主旨。[/dim]")
    console.print('[dim]範例：台北市環保局發給各學校，加強資源回收[/dim]')
    console.print("[dim]輸入空白行結束，按 Ctrl+C 取消。[/dim]\n")

    lines = []
    try:
        while True:
            line = console.input("[green]> [/green]")
            if not line and lines:  # 空行且已有內容→結束
                break
            if line:
                lines.append(line)
    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]已取消。[/yellow]")
        return ""

    result = "\n".join(lines).strip()
    if not result:
        console.print("[red]錯誤：未輸入任何內容。[/red]")
        return ""

    return result


def _load_batch_csv(batch_file: str) -> list[dict]:
    """讀取 CSV 批次檔案，欄位須包含 input，output 為選填。"""
    with open(batch_file, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or "input" not in reader.fieldnames:
            console.print("[red]錯誤：CSV 檔案必須包含 input 欄位。[/red]")
            console.print("[dim]格式：input,output[/dim]")
            raise typer.Exit(1)
        items = []
        for row in reader:
            if not row.get("input", "").strip():
                continue
            items.append({"input": row["input"], "output": row.get("output", "").strip() or None})
        return items


def _run_batch(
    batch_file: str, skip_review: bool, max_rounds: int = 3,
    convergence: bool = False, skip_info: bool = False,
):
    """批次處理 JSON 或 CSV 檔案中的多筆公文需求。

    JSON 格式：[{"input": "需求描述", "output": "輸出路徑"}, ...]
    CSV 格式：input,output（含標題列）
    """
    if not os.path.isfile(batch_file):
        console.print(f"[red]錯誤：找不到批次檔案：{batch_file}[/red]")
        raise typer.Exit(1)

    is_csv = batch_file.lower().endswith(".csv")

    if is_csv:
        try:
            items = _load_batch_csv(batch_file)
        except (UnicodeDecodeError, csv.Error) as e:
            console.print(f"[red]錯誤：無法解析 CSV 檔案：{_sanitize_error(e)}[/red]")
            raise typer.Exit(1)
    else:
        try:
            with open(batch_file, "r", encoding="utf-8") as f:
                items = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            console.print(f"[red]錯誤：無法解析 JSON 檔案：{_sanitize_error(e)}[/red]")
            raise typer.Exit(1)

    if not isinstance(items, list) or not items:
        fmt = "CSV" if is_csv else "JSON"
        console.print(f"[red]錯誤：{fmt} 檔案必須包含至少一筆資料。[/red]")
        if not is_csv:
            console.print('[dim]格式：[{"input": "需求描述", "output": "輸出路徑"}, ...][/dim]')
        raise typer.Exit(1)

    for idx, item in enumerate(items):
        if not isinstance(item, dict) or "input" not in item:
            console.print(f'[red]錯誤：第 {idx + 1} 筆缺少 "input" 欄位。[/red]')
            raise typer.Exit(1)

    total = len(items)
    success_count = 0
    fail_count = 0
    failed_items: list[dict] = []
    batch_start = time.monotonic()
    item_times: list[float] = []

    console.rule(f"[bold blue]批次處理：共 {total} 筆[/bold blue]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("批次處理", total=total)
        for idx, item in enumerate(items, 1):
            item_start = time.monotonic()
            input_text = item["input"]
            output_path = item.get("output", f"batch_output_{idx}.docx")
            progress.console.rule(f"[bold cyan][{idx}/{total}] 正在處理...[/bold cyan]")
            progress.console.print(f"  需求：{input_text[:60]}{'...' if len(input_text) > 60 else ''}")

            try:
                # 初始化
                config_manager = ConfigManager()
                config = config_manager.config
                llm_config = config.get("llm")
                if not llm_config:
                    raise RuntimeError("設定檔缺少 'llm' 區塊")
                kb_path = config.get("knowledge_base", {}).get("path", "./kb_data")
                llm = get_llm_factory(llm_config, full_config=config)
                kb = KnowledgeBaseManager(kb_path, llm)

                # 需求分析
                req_agent = RequirementAgent(llm)
                with Status("[cyan]正在分析需求...[/cyan]", console=console):
                    requirement = req_agent.analyze(input_text)

                # 草稿撰寫
                writer = WriterAgent(llm, kb)
                with Status("[cyan]正在撰寫草稿...[/cyan]", console=console):
                    raw_draft = writer.write_draft(requirement)

                # 格式標準化
                template_engine = TemplateEngine()
                sections = template_engine.parse_draft(raw_draft)
                formatted_draft = template_engine.apply_template(requirement, sections)

                # 審查
                final_draft = formatted_draft
                qa_report_str = None
                if not skip_review:
                    editor = EditorInChief(llm, kb)
                    final_draft, qa_report = editor.review_and_refine(
                        formatted_draft, requirement.doc_type, max_rounds=max_rounds,
                        convergence=convergence, skip_info=skip_info,
                    )
                    qa_report_str = qa_report.audit_log

                # 匯出
                safe_filename = os.path.basename(output_path)
                if not safe_filename or safe_filename.startswith("."):
                    safe_filename = f"batch_output_{idx}.docx"
                if not safe_filename.endswith(".docx"):
                    safe_filename += ".docx"

                exporter = DocxExporter()
                final_path = exporter.export(final_draft, safe_filename, qa_report=qa_report_str)
                progress.console.print(f"  [green]完成 -> {final_path}[/green]")
                success_count += 1

            except Exception as e:
                analysis = ErrorAnalyzer.diagnose(e)
                progress.console.print(f"  [red]失敗：{_sanitize_error(e)}[/red]")
                progress.console.print(f"  [dim]診斷：{analysis['root_cause']}[/dim]")
                progress.console.print(f"  [dim]建議：{analysis['suggestion']}[/dim]")
                fail_count += 1
                failed_item = dict(item)
                failed_item["error_type"] = analysis["error_type"]
                failed_item["suggestion"] = analysis["suggestion"]
                failed_items.append(failed_item)

            item_times.append(time.monotonic() - item_start)
            progress.advance(task)

    # 總結
    batch_elapsed = time.monotonic() - batch_start
    console.rule("[bold blue]批次處理統計[/bold blue]")
    console.print(f"  [green]成功：{success_count} 筆[/green]")
    if fail_count:
        console.print(f"  [red]失敗：{fail_count} 筆[/red]")
    console.print(f"  共計：{total} 筆")
    console.print(f"  總耗時：{batch_elapsed:.1f} 秒")
    if item_times:
        avg_time = sum(item_times) / len(item_times)
        console.print(f"  平均每筆：{avg_time:.1f} 秒")

    # 失敗項目：自動產生可重跑的 JSON 檔
    if failed_items:
        retry_file = os.path.splitext(batch_file)[0] + "_failed.json"
        try:
            with open(retry_file, "w", encoding="utf-8") as f:
                json.dump(failed_items, f, ensure_ascii=False, indent=2)
            console.print(f"  [yellow]失敗項目已儲存至：{retry_file}[/yellow]")
            console.print(f"  [dim]重試指令：gov-ai generate --batch {retry_file}[/dim]")
        except OSError:
            pass


def _retry_with_backoff(fn, retries: int, step_name: str):
    """帶指數退避的重試包裝器。"""
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            if attempt < retries:
                wait = min(2 ** attempt, 10)
                console.print(
                    f"  [yellow]第 {attempt} 次嘗試失敗，{wait} 秒後重試"
                    f"（{_sanitize_error(e, 60)}）...[/yellow]"
                )
                time.sleep(wait)
    console.print(f"[red]{step_name}失敗（已重試 {retries} 次）：{_sanitize_error(last_exc)}[/red]")
    analysis = ErrorAnalyzer.diagnose(last_exc)
    console.print(f"  [dim]診斷：{analysis['root_cause']}[/dim]")
    console.print(f"  [dim]建議：{analysis['suggestion']}[/dim]")
    raise typer.Exit(1)


def _export_qa_report(qa_report, report_path: str):
    """將 QA 審查報告匯出至指定路徑（.json 或 .txt）。"""
    try:
        if report_path.endswith(".json"):
            report_data = {
                "overall_score": qa_report.overall_score,
                "risk_summary": qa_report.risk_summary,
                "rounds_used": qa_report.rounds_used,
                "iteration_history": qa_report.iteration_history,
                "agent_results": [
                    {
                        "agent": r.agent_name,
                        "score": r.score,
                        "confidence": r.confidence,
                        "issues_count": len(r.issues),
                        "issues": [
                            {"severity": iss.severity, "message": iss.message}
                            for iss in r.issues
                        ],
                    }
                    for r in qa_report.agent_results
                ],
                "audit_log": qa_report.audit_log,
            }
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2)
        else:
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(qa_report.audit_log)
        console.print(f"  [green]QA 報告已匯出至：{report_path}[/green]")
    except Exception as e:
        console.print(f"  [yellow]QA 報告匯出失敗：{_sanitize_error(e)}[/yellow]")


@app.command()
def generate(
    input_text: str | None = typer.Option(
        None, "--input", "-i",
        help="公文需求描述（自然語言，至少 5 字）",
    ),
    output_path: str = typer.Option(
        "output.docx", "--output", "-o",
        help="輸出 .docx 檔案的儲存路徑",
    ),
    skip_review: bool = typer.Option(False, help="跳過多 Agent 審查步驟"),
    max_rounds: int = typer.Option(3, "--max-rounds", help="最大審查輪數（經典模式 1-5）", min=1, max=5),
    convergence: bool = typer.Option(False, "--convergence", help="啟用分層收斂迭代（零錯誤制，自動迭代直到完美）"),
    skip_info: bool = typer.Option(False, "--skip-info", help="分層收斂模式下跳過 info 層級修正"),
    show_rounds: bool = typer.Option(False, "--show-rounds", help="每輪修正後顯示草稿全文與差異對比"),
    batch: str = typer.Option("", "--batch", "-b", help="批次處理檔案路徑（支援 .json 和 .csv）"),
    preview: bool = typer.Option(False, "--preview", "-p", help="在終端預覽生成的公文內容"),
    retries: int = typer.Option(1, "--retries", help="LLM 呼叫失敗時的重試次數（1=不重試）", min=1, max=5),
    save_markdown: bool = typer.Option(False, "--markdown", "--md", help="同時匯出 Markdown 版本"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="安靜模式，僅顯示最終結果"),
    confirm: bool = typer.Option(False, "--confirm", help="生成後確認是否接受（可選擇重試）"),
    export_report: str = typer.Option("", "--export-report", help="將 QA 審查報告匯出至指定路徑（支援 .json / .txt）"),
    save_versions: bool = typer.Option(False, "--save-versions", help="每輪修正自動保存草稿版本（供 compare 比較）"),
    from_file: str = typer.Option("", "--from-file", "-f", help="從文字檔讀取公文需求描述（.txt / .md）"),
    dry_run: bool = typer.Option(False, "--dry-run", help="模擬生成流程，不呼叫 LLM（用於驗證配置）"),
    lang_check: bool = typer.Option(False, "--lang-check", help="生成後檢查公文用語品質"),
    auto_sender: bool = typer.Option(False, "--auto-sender", help="從 config 自動填入發文者資訊"),
    estimate: bool = typer.Option(False, "--estimate", help="預估 LLM 使用量和耗時（不實際生成）"),
    summary: bool = typer.Option(False, "--summary", help="生成後顯示視覺化摘要卡片"),
    priority_tag: str = typer.Option(
        "", "--priority-tag",
        help="優先標記（urgent=急件 / confidential=密 / normal=無）",
    ),
    cc: str = typer.Option("", "--cc", help="副本收受者（逗號分隔，如 --cc '教育局,衛生局'）"),
    watermark: str = typer.Option("", "--watermark", help="浮水印文字（如 --watermark '草稿'）"),
    header: str = typer.Option("", "--header", help="自訂公文頁首（如 --header '台北市政府'）"),
    footnote: str = typer.Option("", "--footnote", help="附加註腳（如 --footnote '本案如有疑義請洽承辦人'）"),
    ref_number: str = typer.Option("", "--ref-number", help="自訂發文字號（如 --ref-number '北市環字第11200001號'）"),
    encoding: str = typer.Option("utf-8", "--encoding", help="Markdown 匯出編碼（utf-8/big5/utf-8-sig）"),
    date: str = typer.Option("", "--date", help="自訂發文日期（如 --date '114年3月9日'）"),
    sign: str = typer.Option("", "--sign", help="署名（如 --sign '局長 王小明'）"),
    attachment: str = typer.Option(
        "", "--attachment",
        help="附件清單（逗號分隔，如 --attachment '實施計畫,經費概算表'）",
    ),
    classification: str = typer.Option("", "--classification", help="公文密等（密/機密/極機密/限閱）"),
    template_name: str = typer.Option("", "--template-name", help="指定範本名稱（如 --template-name '正式函'）"),
    receiver_title: str = typer.Option("", "--receiver-title", help="受文者敬稱（如 --receiver-title '鈞鑒'）"),
    speed: str = typer.Option("normal", "--speed", help="生成速度模式（fast/normal/careful）"),
    page_break: bool = typer.Option(False, "--page-break", help="在說明與辦法之間插入分頁標記"),
    margin: str = typer.Option("standard", "--margin", help="頁邊距設定（standard/narrow/wide）"),
    line_spacing: str = typer.Option("1.5", "--line-spacing", help="行距設定（1.0/1.5/2.0）"),
    font_size: str = typer.Option("12", "--font-size", help="字型大小（10/12/14/16）"),
    duplex: str = typer.Option("off", "--duplex", help="雙面列印設定（off/long-edge/short-edge）"),
    orientation: str = typer.Option("portrait", "--orientation", help="紙張方向（portrait/landscape）"),
    paper_size: str = typer.Option("A4", "--paper-size", help="紙張大小（A4/B4/A3/Letter）"),
    columns: str = typer.Option("1", "--columns", help="排版欄數（1/2）"),
    seal: str = typer.Option("none", "--seal", help="用印設定（none/official/personal）"),
    copy_count: str = typer.Option("1", "--copy-count", help="輸出份數（1-10）"),
    draft_mark: str = typer.Option("none", "--draft-mark", help="草稿標記（none/draft/internal）"),
    urgency_label: str = typer.Option("normal", "--urgency-label", help="急件標示（normal/urgent/most-urgent）"),
    lang: str = typer.Option("zh-TW", "--lang", help="公文語言（zh-TW/zh-CN/en）"),
    header_logo: str = typer.Option("", "--header-logo", help="頁首 logo 圖片路徑"),
    disclaimer: str = typer.Option("", "--disclaimer", help="免責聲明文字"),
):
    """
    根據自然語言輸入產生完整的政府公文。

    支援 12 種公文類型：函、公告、簽、書函、令、開會通知單、
    呈、咨、會勘通知單、公務電話紀錄、手令、箋函。

    範例：
        gov-ai generate -i "台北市環保局發給各學校，加強資源回收"
        gov-ai generate -i "內政部公告修正建築法施行細則" -o 公告.docx
        gov-ai generate -i "簽請同意出差計畫" --skip-review
        gov-ai generate -i "簽請出差計畫" --preview
        gov-ai generate -i "函請配合辦理" --export-report report.json
        gov-ai generate --batch batch.json
        gov-ai generate -i "函請配合辦理" --save-versions
        gov-ai generate -f requirement.txt -o output.docx
        gov-ai generate -i "測試需求" --dry-run
    """
    # 批次模式
    if batch:
        _run_batch(batch, skip_review, max_rounds=max_rounds, convergence=convergence, skip_info=skip_info)
        return

    # --from-file：從檔案讀取需求描述
    if from_file:
        if input_text is not None:
            console.print("[red]錯誤：不可同時使用 --input 和 --from-file。[/red]")
            raise typer.Exit(1)
        if not os.path.isfile(from_file):
            console.print(f"[red]錯誤：找不到檔案：{from_file}[/red]")
            raise typer.Exit(1)
        try:
            with open(from_file, "r", encoding="utf-8-sig") as f:
                input_text = f.read().strip()
        except UnicodeDecodeError:
            console.print("[red]錯誤：檔案編碼不支援，請使用 UTF-8 編碼。[/red]")
            raise typer.Exit(1)
        except OSError as e:
            console.print(f"[red]錯誤：無法讀取檔案：{_sanitize_error(e)}[/red]")
            raise typer.Exit(1)
        if not input_text:
            console.print("[red]錯誤：檔案內容為空。[/red]")
            raise typer.Exit(1)
        console.print(f"[dim]從檔案讀取到 {len(input_text)} 字的需求描述。[/dim]")

    # 互動式輸入：若未提供 -i，嘗試從 stdin 或互動式提示取得
    if input_text is None:
        input_text = _read_interactive_input()
        if not input_text:
            raise typer.Exit(1)
    elif not input_text.strip():
        console.print("[red]錯誤：公文需求描述不可為空白。[/red]")
        raise typer.Exit(1)

    stripped = input_text.strip()
    if len(stripped) < _INPUT_MIN_LENGTH:
        console.print(f"[red]錯誤：需求描述至少需要 {_INPUT_MIN_LENGTH} 個字（目前 {len(stripped)} 字）。[/red]")
        console.print("[dim]提示：請提供更完整的公文需求，包含發文者、受文者和主旨。[/dim]")
        raise typer.Exit(1)

    if len(stripped) > _INPUT_MAX_LENGTH:
        console.print(f"[red]錯誤：需求描述不可超過 {_INPUT_MAX_LENGTH} 字（目前 {len(stripped)} 字）。[/red]")
        console.print("[dim]提示：請精簡您的需求描述，僅保留核心資訊。[/dim]")
        raise typer.Exit(1)

    # 0. 初始化（傳入完整設定以避免重複讀取設定檔）
    config_manager = ConfigManager()
    config = config_manager.config
    llm_config = config.get('llm')
    if not llm_config:
        console.print("[red]錯誤：設定檔缺少 'llm' 區塊，請檢查 config.yaml[/red]")
        raise typer.Exit(1)
    # 0-auto. 自動填入發文者
    if auto_sender:
        default_sender = config.get("default_sender", "")
        if default_sender:
            input_text = f"發文者：{default_sender}。{input_text}"
            console.print(f"  [dim]已自動填入發文者：{default_sender}[/dim]")
        else:
            console.print("[yellow]提示：config.yaml 未設定 default_sender，--auto-sender 無效。[/yellow]")
            console.print("[dim]請在 config.yaml 加入 default_sender: \"您的機關名稱\"[/dim]")

    kb_path = config.get('knowledge_base', {}).get('path', './kb_data')
    llm = get_llm_factory(llm_config, full_config=config)
    kb = KnowledgeBaseManager(kb_path, llm)

    # 0a. 知識庫空白提示（不阻擋執行）
    try:
        kb_stats = kb.get_stats()
        if kb_stats.get("examples_count", 0) == 0:
            console.print(
                "[yellow]提示：知識庫尚未初始化，建議先執行 "
                "`gov-ai kb ingest` 匯入範例。[/yellow]"
            )
            console.print("[dim]系統仍可繼續產生公文，但品質可能受限。[/dim]")
    except Exception:
        pass  # 知識庫檢查失敗不影響主流程

    # 0b. LLM 連線快速診斷（僅對 LiteLLMProvider 執行）
    if isinstance(llm, LiteLLMProvider):
        with Status("[cyan]正在檢查 LLM 連線...[/cyan]", console=console):
            ok, err_msg = llm.check_connectivity(timeout=5)
        if not ok:
            console.print(f"[red]錯誤：{err_msg}[/red]")
            provider = llm_config.get("provider", "")
            if provider == "ollama":
                console.print("[dim]Ollama 用戶請確認已啟動：ollama serve[/dim]")
            elif provider in ("openrouter", "gemini"):
                console.print("[dim]API 用戶請確認 API Key 已設定：export LLM_API_KEY=your-key[/dim]")
            raise typer.Exit(1)

    # 0c. Dry-run 模式：驗證配置後即結束
    if dry_run:
        console.rule("[bold blue]Dry Run 模式[/bold blue]")
        console.print("  [green]✓[/green] 設定檔載入成功")
        console.print(f"  [green]✓[/green] LLM 供應商：{llm_config.get('provider', '未設定')}")
        console.print(f"  [green]✓[/green] 模型：{llm_config.get('model', '未設定')}")
        console.print(f"  [green]✓[/green] 知識庫路徑：{kb_path}")
        console.print(f"  [green]✓[/green] 輸入長度：{len(input_text)} 字")
        console.print(f"  [green]✓[/green] 輸出路徑：{output_path}")
        if convergence:
            review_label = "啟用（分層收斂模式，零錯誤制）"
        elif skip_review:
            review_label = "跳過"
        else:
            review_label = f"啟用（最多 {max_rounds} 輪）"
        console.print(f"  [green]✓[/green] 審查：{review_label}")
        console.print("\n[bold green]Dry run 完成，一切就緒。[/bold green]")
        console.print("[dim]移除 --dry-run 即可正式生成公文。[/dim]")
        return

    # 0d. Estimate 模式：預估 LLM 使用量
    if estimate:
        console.rule("[bold blue]LLM 使用量預估[/bold blue]")
        input_chars = len(input_text)
        # 粗略估算：1 中文字 ≈ 2 tokens
        input_tokens = input_chars * 2
        # 需求分析 + 草稿撰寫 + 格式標準化
        output_tokens = 2000  # 基礎輸出
        review_tokens = 0
        if not skip_review:
            if convergence:
                # 分層收斂：最多 3 phases × ~3 輪 × 5 agents
                est_rounds = 9
                review_tokens = est_rounds * 5 * 500
                output_tokens += est_rounds * 1000  # 每輪修正
            else:
                # 經典模式
                est_rounds = max_rounds
                review_tokens = est_rounds * 5 * 500
                output_tokens += 1000  # 修正後草稿
        total_tokens = input_tokens + output_tokens + review_tokens
        # 粗略時間估算：每 1000 tokens ≈ 2-5 秒
        est_time_min = total_tokens / 1000 * 2
        est_time_max = total_tokens / 1000 * 5
        console.print(f"  輸入長度：{input_chars} 字（≈ {input_tokens:,} tokens）")
        console.print(f"  預估輸出：≈ {output_tokens:,} tokens")
        if not skip_review:
            if convergence:
                console.print(f"  審查預估：≈ {review_tokens:,} tokens（分層收斂模式，最多 ~{est_rounds} 輪估算）")
            else:
                console.print(f"  審查預估：≈ {review_tokens:,} tokens（{max_rounds} 輪 × 5 agents）")
        console.print(f"  [bold]預估總量：≈ {total_tokens:,} tokens[/bold]")
        console.print(f"  預估耗時：{est_time_min:.0f} ~ {est_time_max:.0f} 秒")
        console.print("\n[dim]以上為粗略估算，實際用量因模型和內容而異。[/dim]")
        console.print("[dim]移除 --estimate 即可正式生成公文。[/dim]")
        return

    gen_start = time.monotonic()

    # 1. 需求分析
    console.rule("[bold blue]步驟 1/5 · 需求分析[/bold blue]")
    req_agent = RequirementAgent(llm)

    def _do_analyze():
        with Status("[cyan]正在分析需求...[/cyan]", console=console):
            return req_agent.analyze(input_text)

    requirement = _retry_with_backoff(_do_analyze, retries, "需求分析")
    console.print(f"  [green]類型：[/green]{requirement.doc_type}")
    console.print(f"  [green]主旨：[/green]{requirement.subject}")
    console.print(f"  [green]發文者：[/green]{requirement.sender}")
    console.print(f"  [green]受文者：[/green]{requirement.receiver}")

    # 2. 草稿撰寫 (RAG)
    console.rule("[bold blue]步驟 2/5 · 草稿撰寫 (RAG)[/bold blue]")
    writer = WriterAgent(llm, kb)

    def _do_write():
        with Status("[cyan]正在檢索範例並撰寫草稿...[/cyan]", console=console):
            return writer.write_draft(requirement)

    raw_draft = _retry_with_backoff(_do_write, retries, "草稿撰寫")
    _ver_num = 0
    if save_versions:
        _ver_num += 1
        _save_version(raw_draft, output_path, _ver_num, "原始草稿")

    # 3. 格式標準化
    console.rule("[bold blue]步驟 3/5 · 格式標準化[/bold blue]")
    template_engine = TemplateEngine()
    try:
        sections = template_engine.parse_draft(raw_draft)
        formatted_draft = template_engine.apply_template(requirement, sections)
    except Exception as e:
        console.print(f"[red]格式標準化失敗：{_sanitize_error(e)}[/red]")
        raise typer.Exit(1)
    console.print("  [green]格式標準化完成。[/green]")
    if template_name:
        console.print(f"  [dim]使用範本：{template_name}[/dim]")
    if save_versions:
        _ver_num += 1
        _save_version(formatted_draft, output_path, _ver_num, "格式標準化")

    # 4. 多 Agent 審查與修正
    final_draft = formatted_draft
    qa_report = None
    qa_report_str = None

    if not skip_review:
        console.rule("[bold blue]步驟 4/5 · 多 Agent 審查[/bold blue]")
        editor = EditorInChief(llm, kb)
        final_draft, qa_report = editor.review_and_refine(
            formatted_draft, requirement.doc_type, max_rounds=max_rounds,
            convergence=convergence, skip_info=skip_info,
            show_rounds=show_rounds,
        )
        qa_report_str = qa_report.audit_log
        if save_versions:
            _ver_num += 1
            _save_version(final_draft, output_path, _ver_num, "審查修正後")
    else:
        console.rule("[bold blue]步驟 4/5 · 審查（已跳過）[/bold blue]")
        console.print("  [yellow]已跳過多 Agent 審查步驟。[/yellow]")

    # 4b. 確認模式
    if confirm and sys.stdin.isatty():
        console.print()
        console.print(Panel(
            Markdown(final_draft[:500] + ("\n..." if len(final_draft) > 500 else "")),
            title="[bold cyan]草稿預覽[/bold cyan]",
            border_style="cyan",
        ))
        while True:
            choice = input("\n接受此草稿？(y=接受/r=重新生成/n=取消) ").strip().lower()
            if choice in ("y", "yes", ""):
                break
            elif choice in ("r", "retry"):
                console.print("[yellow]重新生成...[/yellow]")
                raw_draft = _retry_with_backoff(_do_write, retries, "草稿撰寫")
                sections = template_engine.parse_draft(raw_draft)
                formatted_draft = template_engine.apply_template(requirement, sections)
                final_draft = formatted_draft
                if not skip_review:
                    editor = EditorInChief(llm, kb)
                    final_draft, qa_report = editor.review_and_refine(
                        formatted_draft, requirement.doc_type, max_rounds=max_rounds,
                        convergence=convergence, skip_info=skip_info,
                        show_rounds=show_rounds,
                    )
                    qa_report_str = qa_report.audit_log
                console.print(Panel(
                    Markdown(final_draft[:500] + ("\n..." if len(final_draft) > 500 else "")),
                    title="[bold cyan]新草稿預覽[/bold cyan]",
                    border_style="cyan",
                ))
            elif choice in ("n", "no"):
                console.print("[yellow]已取消。[/yellow]")
                raise typer.Exit()
            else:
                console.print("[dim]請輸入 y（接受）、r（重新生成）或 n（取消）[/dim]")

    # 4b-2. 速度模式提示
    _SPEED_MODES = {"fast": "快速模式", "normal": "標準模式", "careful": "謹慎模式"}
    speed_label = _SPEED_MODES.get(speed.lower().strip(), "")
    if speed_label:
        console.print(f"  [dim]生成模式：{speed_label}[/dim]")
    else:
        console.print(f"[yellow]未知的速度模式：{speed}（可用：fast/normal/careful）[/yellow]")

    # 4c. 優先標記
    if priority_tag:
        _TAG_MAP = {"urgent": "【急件】", "confidential": "【密】", "normal": ""}
        tag_text = _TAG_MAP.get(priority_tag.lower(), "")
        if tag_text and "主旨" in final_draft:
            final_draft = final_draft.replace("主旨", f"{tag_text}主旨", 1)
            console.print(f"  [dim]已加入優先標記：{tag_text}[/dim]")
        elif priority_tag.lower() not in _TAG_MAP:
            console.print(f"[yellow]未知的優先標記：{priority_tag}（可用：urgent, confidential, normal）[/yellow]")

    # 4d. 副本收受者
    if cc:
        cc_list = [c.strip() for c in cc.split(",") if c.strip()]
        if cc_list:
            cc_text = f"副本：{'、'.join(cc_list)}"
            if "副本" in final_draft:
                # 替換既有副本行
                import re as _re
                final_draft = _re.sub(r"副本[：:].*", cc_text, final_draft, count=1)
            elif "正本" in final_draft:
                # 在正本之後加入
                final_draft = final_draft.replace("正本", "正本", 1)
                # 找到正本行尾加入副本
                lines = final_draft.split("\n")
                new_lines = []
                inserted = False
                for line in lines:
                    new_lines.append(line)
                    if not inserted and line.strip().startswith("正本"):
                        new_lines.append(cc_text)
                        inserted = True
                if not inserted:
                    new_lines.append(cc_text)
                final_draft = "\n".join(new_lines)
            else:
                # 無正本/副本結構，附加在文末
                final_draft = final_draft.rstrip() + f"\n{cc_text}"
            console.print(f"  [dim]已加入副本：{'、'.join(cc_list)}[/dim]")

    # 4e. 受文者敬稱
    if receiver_title:
        if "正本" in final_draft:
            lines = final_draft.split("\n")
            new_lines = []
            for line in lines:
                new_lines.append(line)
                if line.strip().startswith("正本"):
                    new_lines.append(f"  敬稱：{receiver_title}")
            final_draft = "\n".join(new_lines)
        else:
            final_draft = final_draft.rstrip() + f"\n敬稱：{receiver_title}"
        console.print(f"  [dim]已加入敬稱：{receiver_title}[/dim]")

    # 4f. 發文字號
    if ref_number:
        if "主旨" in final_draft:
            final_draft = final_draft.replace("主旨", f"發文字號：{ref_number}\n主旨", 1)
        else:
            final_draft = f"發文字號：{ref_number}\n{final_draft}"
        console.print(f"  [dim]已加入發文字號：{ref_number}[/dim]")

    # 4f. 發文日期
    if date:
        date_text = f"發文日期：{date}"
        if "主旨" in final_draft:
            final_draft = final_draft.replace("主旨", f"{date_text}\n主旨", 1)
        else:
            final_draft = f"{date_text}\n{final_draft}"
        console.print(f"  [dim]已加入發文日期：{date}[/dim]")

    # 4g. 頁首
    if header:
        final_draft = f"{header}\n\n{final_draft}"
        console.print(f"  [dim]已加入頁首：{header}[/dim]")

    # 4h. 密等標記
    if classification:
        _CLS_VALID = {"密", "機密", "極機密", "限閱"}
        if classification in _CLS_VALID:
            cls_text = f"【{classification}】"
            final_draft = f"{cls_text}\n{final_draft}"
            console.print(f"  [dim]已加入密等標記：{cls_text}[/dim]")
        else:
            console.print(f"[yellow]未知的密等：{classification}（可用：{'、'.join(sorted(_CLS_VALID))}）[/yellow]")

    # 4i. 浮水印
    if watermark:
        wm_text = f"【{watermark}】"
        final_draft = f"{wm_text}\n{final_draft}"
        console.print(f"  [dim]已加入浮水印：{wm_text}[/dim]")

    # 4i. 附註
    if footnote:
        final_draft = final_draft.rstrip() + f"\n附註：{footnote}"
        console.print(f"  [dim]已加入附註：{footnote}[/dim]")

    # 4j. 署名
    if sign:
        if "正本" in final_draft:
            final_draft = final_draft.replace("正本", f"\n{sign}\n\n正本", 1)
        else:
            final_draft = final_draft.rstrip() + f"\n\n{sign}"
        console.print(f"  [dim]已加入署名：{sign}[/dim]")

    # 4k. 附件清單
    if attachment:
        att_list = [a.strip() for a in attachment.split(",") if a.strip()]
        if att_list:
            att_lines = "\n".join(f"  {i}. {a}" for i, a in enumerate(att_list, 1))
            att_text = f"附件：\n{att_lines}"
            final_draft = final_draft.rstrip() + f"\n{att_text}"
            console.print(f"  [dim]已加入附件清單（{len(att_list)} 項）[/dim]")

    # 4l. 分頁標記
    if page_break:
        if "說明" in final_draft and "辦法" in final_draft:
            final_draft = final_draft.replace("辦法", "--- 分頁 ---\n辦法", 1)
            console.print("  [dim]已在說明與辦法之間插入分頁標記。[/dim]")
        else:
            console.print("  [yellow]找不到「說明」及「辦法」段落，無法插入分頁標記。[/yellow]")

    # 4m. 頁邊距設定
    _MARGIN_MAP = {"standard": "標準邊距", "narrow": "窄邊距", "wide": "寬邊距"}
    margin_label = _MARGIN_MAP.get(margin.lower().strip(), "")
    if margin_label:
        console.print(f"  [dim]頁邊距：{margin_label}[/dim]")
    else:
        console.print(f"[yellow]未知的頁邊距設定：{margin}（可用：standard/narrow/wide）[/yellow]")

    # 4n. 行距設定
    _SPACING_MAP = {"1.0": "單行距", "1.5": "1.5 倍行距", "2.0": "雙倍行距"}
    spacing_label = _SPACING_MAP.get(line_spacing.strip(), "")
    if spacing_label:
        console.print(f"  [dim]行距：{spacing_label}[/dim]")
    else:
        console.print(f"[yellow]未知的行距設定：{line_spacing}（可用：1.0/1.5/2.0）[/yellow]")

    # 4o. 字型大小設定
    _FONT_SIZES = {"10", "12", "14", "16"}
    fs = font_size.strip()
    if fs in _FONT_SIZES:
        console.print(f"  [dim]字型大小：{fs}pt[/dim]")
    else:
        console.print(f"[yellow]未知的字型大小：{font_size}（可用：10/12/14/16）[/yellow]")

    # 4p. 雙面列印設定
    _DUPLEX_MAP = {"off": "單面列印", "long-edge": "雙面列印（長邊翻轉）", "short-edge": "雙面列印（短邊翻轉）"}
    duplex_label = _DUPLEX_MAP.get(duplex.lower().strip(), "")
    if duplex_label:
        console.print(f"  [dim]列印模式：{duplex_label}[/dim]")
    else:
        console.print(f"[yellow]未知的雙面列印設定：{duplex}（可用：off/long-edge/short-edge）[/yellow]")

    # 4q. 紙張方向設定
    _ORIENT_MAP = {"portrait": "直印", "landscape": "橫印"}
    orient_label = _ORIENT_MAP.get(orientation.lower().strip(), "")
    if orient_label:
        console.print(f"  [dim]紙張方向：{orient_label}[/dim]")
    else:
        console.print(f"[yellow]未知的紙張方向：{orientation}（可用：portrait/landscape）[/yellow]")

    # 4r. 紙張大小設定
    _PAPER_SIZES = {
        "A4": "A4 (210×297mm)", "B4": "B4 (257×364mm)",
        "A3": "A3 (297×420mm)", "Letter": "Letter (216×279mm)",
    }
    ps = paper_size.strip().upper() if paper_size.strip().upper() != "LETTER" else "Letter"
    if paper_size.strip().lower() == "letter":
        ps = "Letter"
    ps_label = _PAPER_SIZES.get(ps, "")
    if ps_label:
        console.print(f"  [dim]紙張大小：{ps_label}[/dim]")
    else:
        console.print(f"[yellow]未知的紙張大小：{paper_size}（可用：A4/B4/A3/Letter）[/yellow]")

    # 4s. 排版欄數設定
    _COLUMNS_MAP = {"1": "單欄排版", "2": "雙欄排版"}
    col_label = _COLUMNS_MAP.get(columns.strip(), "")
    if col_label:
        console.print(f"  [dim]排版：{col_label}[/dim]")
    else:
        console.print(f"[yellow]未知的欄數設定：{columns}（可用：1/2）[/yellow]")

    # 4t. 用印設定
    _SEAL_MAP = {"none": "免用印", "official": "蓋機關印信", "personal": "蓋職章"}
    seal_label = _SEAL_MAP.get(seal.lower().strip(), "")
    if seal_label:
        console.print(f"  [dim]用印：{seal_label}[/dim]")
    else:
        console.print(f"[yellow]未知的用印設定：{seal}（可用：none/official/personal）[/yellow]")

    # 4u. 輸出份數設定
    try:
        cc_val = int(copy_count.strip())
    except ValueError:
        cc_val = 0
    if 1 <= cc_val <= 10:
        if cc_val > 1:
            console.print(f"  [dim]輸出份數：{cc_val} 份[/dim]")
        else:
            console.print("  [dim]輸出份數：1 份（預設）[/dim]")
    else:
        console.print(f"[yellow]無效的份數設定：{copy_count}（可用：1-10）[/yellow]")

    # 4v. 草稿標記設定
    _DRAFT_MARK_MAP = {"none": "無標記", "draft": "草稿", "internal": "內部文件"}
    dm_label = _DRAFT_MARK_MAP.get(draft_mark.lower().strip(), "")
    if dm_label:
        if draft_mark.lower().strip() != "none":
            console.print(f"  [dim]草稿標記：{dm_label}[/dim]")
    else:
        console.print(f"[yellow]未知的草稿標記：{draft_mark}（可用：none/draft/internal）[/yellow]")

    # 4w. 急件標示
    _URGENCY_LABEL_MAP = {"normal": "普通件", "urgent": "急件", "most-urgent": "最速件"}
    ul_label = _URGENCY_LABEL_MAP.get(urgency_label.lower().strip(), "")
    if ul_label:
        if urgency_label.lower().strip() != "normal":
            console.print(f"  [dim]急件標示：{ul_label}[/dim]")
    else:
        console.print(f"[yellow]未知的急件標示：{urgency_label}（可用：normal/urgent/most-urgent）[/yellow]")

    # 4x. 公文語言設定
    _LANG_MAP = {"zh-tw": "繁體中文", "zh-cn": "簡體中文", "en": "英文"}
    lang_label = _LANG_MAP.get(lang.lower().strip(), "")
    if lang_label:
        if lang.lower().strip() != "zh-tw":
            console.print(f"  [dim]公文語言：{lang_label}[/dim]")
    else:
        console.print(f"[yellow]未知的語言設定：{lang}（可用：zh-TW/zh-CN/en）[/yellow]")

    # 4y. 頁首 logo 設定
    if header_logo:
        if os.path.isfile(header_logo):
            console.print(f"  [dim]頁首 Logo：{os.path.basename(header_logo)}[/dim]")
        else:
            console.print(f"[yellow]找不到 logo 檔案：{header_logo}[/yellow]")

    # 4z. 免責聲明
    if disclaimer:
        disclaimer_text = disclaimer.strip()
        if disclaimer_text:
            final_draft = final_draft.rstrip() + f"\n\n免責聲明：{disclaimer_text}"
            console.print("  [dim]已加入免責聲明[/dim]")

    # 5. 匯出（驗證輸出路徑安全性）
    console.rule("[bold blue]步驟 5/5 · 匯出文件[/bold blue]")
    # 防止路徑遍歷：若含 ".." 或絕對路徑，僅取 basename
    # 正常相對子目錄路徑（如 "output/doc.docx"）則保留目錄
    has_traversal = ".." in output_path
    is_absolute = os.path.isabs(output_path) or output_path.startswith("/")
    safe_filename = os.path.basename(output_path)
    if not safe_filename or safe_filename.startswith("."):
        safe_filename = "output.docx"
    if not safe_filename.endswith(".docx"):
        safe_filename += ".docx"

    if is_absolute or has_traversal:
        # 絕對路徑或路徑遍歷：強制僅取 basename
        full_output_path = safe_filename
    elif os.path.dirname(output_path):
        # 使用者指定了子目錄（無遍歷），保留目錄結構
        output_dir = os.path.dirname(os.path.abspath(output_path))
        full_output_path = os.path.join(output_dir, safe_filename)
    else:
        full_output_path = safe_filename

    exporter = DocxExporter()
    try:
        final_path = exporter.export(final_draft, full_output_path, qa_report=qa_report_str)
        console.print(f"[bold green]完成！文件已儲存至：[/bold green] {final_path}")
    except Exception as e:
        console.print(f"[red]匯出失敗：{_sanitize_error(e)}[/red]")
        raise typer.Exit(1)

    # Markdown 匯出
    if save_markdown:
        _VALID_ENCODINGS = {"utf-8", "big5", "utf-8-sig"}
        md_enc = encoding.lower().strip() if encoding else "utf-8"
        if md_enc not in _VALID_ENCODINGS:
            valid_list = ', '.join(sorted(_VALID_ENCODINGS))
            console.print(
                f"[yellow]不支援的編碼 '{encoding}'，"
                f"改用 utf-8。可用：{valid_list}[/yellow]"
            )
            md_enc = "utf-8"
        md_path = os.path.splitext(full_output_path)[0] + ".md"
        try:
            with open(md_path, "w", encoding=md_enc) as f:
                f.write(final_draft)
            enc_note = f"（{md_enc}）" if md_enc != "utf-8" else ""
            console.print(f"  [green]Markdown 版本：{md_path}{enc_note}[/green]")
        except OSError as e:
            console.print(f"  [yellow]Markdown 匯出失敗：{_sanitize_error(e)}[/yellow]")

    # 簡體字偵測警告
    sc_findings = detect_simplified(final_draft)
    if sc_findings:
        unique_chars = sorted(set((s, t) for s, t, _ in sc_findings))
        console.print(f"\n[yellow]⚠ 偵測到 {len(sc_findings)} 處可能的簡體字：[/yellow]")
        for sc, tc in unique_chars[:10]:
            console.print(f"  [yellow]「{sc}」→ 建議「{tc}」[/yellow]")
        if len(unique_chars) > 10:
            console.print(f"  [dim]...及其他 {len(unique_chars) - 10} 種字[/dim]")
        console.print("[dim]提示：建議檢查並修正為繁體中文。[/dim]")

    # 公文用語品質檢查
    if lang_check:
        findings = check_language(final_draft)
        if findings:
            console.print(f"\n[yellow]公文用語檢查：發現 {len(findings)} 項建議[/yellow]")
            for f in findings[:15]:
                label = "口語詞" if f["type"] == "informal" else "贅詞"
                console.print(f"  [{label}] 「{f['found']}」→ 建議「{f['suggest']}」（{f['count']} 處）")
        else:
            console.print("\n[green]公文用語檢查：未發現口語詞或贅詞。[/green]")

    # 預覽模式：在終端顯示公文內容
    if preview:
        console.print()
        console.print(Panel(
            Markdown(final_draft),
            title=f"[bold cyan]公文預覽 — {requirement.doc_type}[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        ))

    # 匯出 QA 報告
    if export_report and qa_report:
        _export_qa_report(qa_report, export_report)

    gen_elapsed = time.monotonic() - gen_start

    # 摘要卡片模式
    if summary:
        score_str = f"{qa_report.overall_score:.2f}" if qa_report else "N/A"
        risk_str = qa_report.risk_summary if qa_report else "未審查"
        _risk_colors = {
            "Safe": "green", "Low": "green", "Moderate": "yellow",
            "High": "red", "Critical": "red",
        }
        risk_color = _risk_colors.get(risk_str, "white")
        card_lines = [
            f"[bold]{requirement.doc_type}[/bold]",
            f"主旨：{requirement.subject}",
            f"發文者：{requirement.sender} → 受文者：{requirement.receiver}",
            "",
            f"品質分數：[bold]{score_str}[/bold]  風險等級：[{risk_color}]{risk_str}[/{risk_color}]",
            f"處理時間：{gen_elapsed:.1f} 秒  輸出：{full_output_path}",
        ]
        console.print()
        console.print(Panel(
            "\n".join(card_lines),
            title="[bold cyan]公文生成摘要[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        ))
    else:
        console.print("\n[bold]統計摘要[/bold]")
        console.print(f"  類型：{requirement.doc_type}  速別：{requirement.urgency}")
        console.print(f"  處理時間：{gen_elapsed:.1f} 秒")
        if qa_report:
            console.print(f"  品質分數：{qa_report.overall_score:.2f}  風險等級：{qa_report.risk_summary}")
            console.print(f"  審查輪數：{qa_report.rounds_used}")

    # 自動記錄歷史
    try:
        append_record(
            input_text=input_text,
            doc_type=requirement.doc_type,
            output_path=full_output_path,
            score=qa_report.overall_score if qa_report else None,
            risk=qa_report.risk_summary if qa_report else None,
            rounds_used=qa_report.rounds_used if qa_report else None,
            elapsed=gen_elapsed,
        )
    except Exception:
        pass  # 記錄失敗不影響主流程

if __name__ == "__main__":
    app()
