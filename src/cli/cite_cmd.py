"""法規引用建議，給定公文草稿並推薦適用法規與標準引用格式。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.core.models import detect_doc_type

console = Console(width=120)

# 預設映射表路徑（相對於工作目錄）
_MAPPING_PATH = Path("kb_data/regulation_doc_type_mapping.yaml")

# 公文類型的中文顯示名（涵蓋 VALID_DOC_TYPES 全部 13 種）
_TYPE_LABELS = {
    "函":         "函（一般行政函文）",
    "公告":       "公告",
    "簽":         "簽呈（內部）",
    "令":         "法規命令",
    "書函":       "書函（機關間）",
    "開會通知單": "開會通知單",
    "開會紀錄":   "開會紀錄",
    "呈":         "呈（下對上）",
    "咨":         "咨（平行機關）",
    "會勘通知單": "會勘通知單",
    "公務電話紀錄": "公務電話紀錄",
    "手令":       "手令",
    "箋函":       "箋函",
}

# 法規引用格式範本（依《公文程式條例》慣例）
_CITE_TEMPLATE = "依據《{name}》"


# 法規映射表專用的擴充偵測規則（這些類型不在 VALID_DOC_TYPES 中，
# 但法規映射 YAML 需要更細粒度的分類來推薦適用法規）
_CITE_EXTRA_RULES: list[tuple[list[str], str]] = [
    (["主持人", "出席人員", "決議事項"],           "會議紀錄"),
    (["訴願", "訴願人", "處分機關", "決定書"],     "訴願決定書"),
    (["採購公告", "廠商", "開標", "底價"],         "採購公告"),
    (["環評", "環境影響", "廢水", "空氣污染"],     "環保公告"),
    (["任命", "派任", "遷調", "免職", "任用"],     "人事令"),
]


def _detect_doc_type(text: str) -> str | None:
    """從草稿文字中自動偵測公文類型。

    先檢查法規映射專用的擴充類型（人事令、環保公告等），
    再委託 src.core.models.detect_doc_type 統一偵測 13 種標準類型。
    空內容回傳 None 讓呼叫端處理。
    """
    if not text or not text.strip():
        return None
    # 先偵測法規映射專用的細分類型
    for keywords, doc_type in _CITE_EXTRA_RULES:
        if any(kw in text for kw in keywords):
            return doc_type
    # 再 fallback 到共用偵測（涵蓋 VALID_DOC_TYPES 全部 13 種）
    return detect_doc_type(text)


def _load_mapping(mapping_path: Path) -> dict:
    """載入法規-文件類型映射表。"""
    if not mapping_path.exists():
        raise FileNotFoundError(
            f"找不到法規映射表：{mapping_path}\n"
            "請確認工作目錄正確，或指定 --mapping 路徑。"
        )
    with mapping_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("regulations", {})


def _filter_applicable(regulations: dict, doc_type: str) -> list[dict]:
    """篩選適用於指定公文類型的法規清單（依名稱字母序排序）。"""
    result = []
    for name, meta in regulations.items():
        applicable = meta.get("applicable_doc_types", [])
        if doc_type in applicable:
            result.append(
                {
                    "name": name,
                    "pcode": meta.get("pcode", ""),
                    "description": meta.get("description", ""),
                    "source_level": meta.get("source_level", "A"),
                    "cite_format": _CITE_TEMPLATE.format(name=name),
                }
            )
    return sorted(result, key=lambda x: x["name"])


def _try_kb_search(draft_text: str, doc_type: str, top_n: int) -> list[dict]:
    """嘗試透過 KnowledgeBaseManager 語意搜尋相關法規條文。

    若 KB 不可用（ChromaDB 未初始化、embedding 未設定），靜默回傳空清單。
    """
    try:
        from src.core.config import ConfigManager
        from src.core.llm import get_llm_factory
        from src.knowledge.manager import KnowledgeBaseManager

        config = ConfigManager()
        llm_factory = get_llm_factory(config)
        kb = KnowledgeBaseManager(llm_provider=llm_factory.get_provider())
        if not kb.is_available():
            return []
        query = f"{doc_type} 法令依據 {draft_text[:300]}"
        return kb.search_regulations(query, doc_type=doc_type, n_results=top_n)
    except Exception:  # noqa: BLE001
        return []


def _render_rich(
    doc_type: str,
    detected: bool,
    applicable: list[dict],
    kb_results: list[dict],
    mapping_path: Path,
) -> None:
    """Rich 格式輸出（終端機互動模式）。"""
    type_label = _TYPE_LABELS.get(doc_type, doc_type)
    source_note = "（自動偵測）" if detected else "（手動指定）"
    console.print(
        Panel(
            f"[bold cyan]公文類型：{type_label}[/bold cyan] {source_note}",
            title="[bold]gov-ai cite - 法規引用建議[/bold]",
            border_style="cyan",
        )
    )

    if not applicable:
        console.print("[yellow]警告：未找到適用法規。請確認公文類型是否正確。[/yellow]")
        return

    # ── 適用法規清單 ─────────────────────────────────
    table = Table(
        title=f"適用法規（共 {len(applicable)} 部）",
        show_lines=True,
        header_style="bold",
    )
    table.add_column("法規名稱", style="bold cyan", width=24)
    table.add_column("PCode", width=12)
    table.add_column("用途說明", width=36)
    table.add_column("建議引用格式", width=28)

    for reg in applicable:
        table.add_row(
            reg["name"],
            reg["pcode"],
            reg["description"],
            reg["cite_format"],
        )

    console.print(table)

    # ── 語意搜尋結果（KB 模式）──────────────────────
    if kb_results:
        console.print()
        console.print("[bold]知識庫相關條文（語意匹配）[/bold]")
        for i, r in enumerate(kb_results, 1):
            title = r.get("metadata", {}).get("title", "未知法規")
            score = r.get("distance", 0.0)
            excerpt = r.get("document", "")[:200].replace("\n", " ")
            console.print(
                f"  [dim]{i}.[/dim] [bold]{title}[/bold]  "
                f"[dim]相似度：{1 - score:.2%}[/dim]"
            )
            console.print(f"     {excerpt}…")
    else:
        console.print(
            "\n[dim]提示：加上 --kb 旗標可啟用語意搜尋，"
            "從知識庫中找出最相關的具體條文。[/dim]"
        )

    # ── 引用格式提示 ─────────────────────────────────
    console.print()
    console.print("[bold]法令依據區塊範本[/bold]")
    cite_lines = [f"  {reg['cite_format']}" for reg in applicable[:5]]
    console.print(
        Panel("\n".join(cite_lines), title="建議填入「法令依據」欄位", border_style="dim")
    )
    console.print(
        f"[dim]資料來源：{mapping_path}[/dim]\n"
        "[dim]提示：確切條號請查閱全國法規資料庫 https://law.moj.gov.tw[/dim]"
    )


def _render_json(doc_type: str, applicable: list[dict], kb_results: list[dict]) -> None:
    """JSON 格式輸出（供程式解析）。"""
    output = {
        "doc_type": doc_type,
        "applicable_regulations": applicable,
        "kb_semantic_results": kb_results,
    }
    console.print_json(json.dumps(output, ensure_ascii=False, indent=2))


def cite(
    draft: Optional[str] = typer.Argument(
        None,
        help="草稿檔案路徑（省略或 '-' 則從 stdin 讀取）",
    ),
    doc_type: Optional[str] = typer.Option(
        None,
        "--type",
        "-t",
        help="公文類型（函/公告/簽/令/書函/開會通知單/會議紀錄/人事令/環保公告/採購公告/訴願決定書）",
    ),
    top_n: int = typer.Option(5, "--top", "-n", help="語意搜尋回傳筆數（--kb 模式）"),
    use_kb: bool = typer.Option(
        False,
        "--kb",
        help="啟用知識庫語意搜尋，找出草稿最相關的具體法條（需先執行 kb ingest）",
    ),
    output_format: str = typer.Option(
        "rich",
        "--format",
        "-f",
        help="輸出格式：rich（終端機彩色）或 json（程式解析）",
    ),
    mapping: Optional[str] = typer.Option(
        None,
        "--mapping",
        help="自訂法規映射表路徑（預設：kb_data/regulation_doc_type_mapping.yaml）",
    ),
) -> None:
    """法規引用建議 - 給定公文草稿，推薦適用法規與標準引用格式。

    \b
    範例：
        gov-ai cite draft.md                    # 自動偵測類型
        gov-ai cite draft.md --type 公告        # 指定類型
        gov-ai cite draft.md --kb               # 啟用語意搜尋
        gov-ai cite - < draft.txt               # 從 stdin 讀取
        gov-ai cite draft.md --format json      # JSON 輸出
    """
    # ── 讀取草稿 ──────────────────────────────────────
    if not draft or draft == "-":
        if sys.stdin.isatty():
            console.print("[yellow]請輸入草稿文字（Ctrl+D 結束）：[/yellow]")
        draft_text = sys.stdin.read()
    else:
        path = Path(draft)
        if not path.exists():
            console.print(f"[red]找不到檔案：{draft}[/red]")
            raise typer.Exit(1)
        draft_text = path.read_text(encoding="utf-8")

    if not draft_text.strip():
        console.print("[red]草稿內容為空，無法分析。[/red]")
        raise typer.Exit(1)

    # ── 偵測公文類型 ──────────────────────────────────
    detected = False
    if not doc_type:
        doc_type = _detect_doc_type(draft_text)
        detected = True
        if not doc_type:
            console.print(
                "[yellow]警告：無法自動偵測公文類型。請使用 --type 指定。[/yellow]\n"
                f"可用類型：{', '.join(_TYPE_LABELS.keys())}"
            )
            raise typer.Exit(1)

    # ── 載入映射表並篩選 ──────────────────────────────
    mapping_path = Path(mapping) if mapping else _MAPPING_PATH
    try:
        regulations = _load_mapping(mapping_path)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e

    applicable = _filter_applicable(regulations, doc_type)

    # ── 語意搜尋（可選）──────────────────────────────
    kb_results: list[dict] = []
    if use_kb:
        with console.status("[dim]正在查詢知識庫...[/dim]"):
            kb_results = _try_kb_search(draft_text, doc_type, top_n)
        if not kb_results:
            console.print(
                "[dim]警告：知識庫查詢無結果（可能尚未執行 gov-ai kb ingest）。[/dim]"
            )

    # ── 輸出 ───────────────────────────────────────────
    if output_format == "json":
        _render_json(doc_type, applicable, kb_results)
    else:
        _render_rich(doc_type, detected, applicable, kb_results, mapping_path)
