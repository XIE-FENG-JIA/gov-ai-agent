import typer
from rich.console import Console
from rich.table import Table

console = Console()

# 口語化用詞對照（依《文書處理手冊》口語化 → 正式用語建議）
_INFORMAL_TERMS = {
    "所以": "爰此",
    "但是": "惟",
    "而且": "且",
    "因為": "因",
    "可是": "然",
    "還有": "另",
    "已經": "業已",
    "馬上": "即刻",
    "大概": "約",
    "一定要": "應",
    # 擴充：10 → 18 個常見白話詞
    "以後": "嗣後",
    "不過": "惟",
    "同時": "並",
    "為了": "為",
    "沒有": "無",
    "快點": "儘速",
    "先前": "前",
    "有些": "部分",
}

# 必要段落
_REQUIRED_SECTIONS = ["主旨", "說明"]

# 函文主旨應以下列結尾語之一收尾（依《文書處理手冊》規定）
# 僅列明確作為結尾語的詞彙，避免「配合辦理」等常見片語造成偽陰性
_SUBJECT_CLOSINGS = [
    "查照", "照辦", "鑒核", "核示", "遵照辦理",
    "辦理見復", "備查", "鑒察", "核備",
]

# 具有「受文者」的外發文件類型，視為需要速別/字號的正式函文
_FORMAL_DOC_INDICATOR = "受文者"


def _check_speed_level(text: str) -> list[dict]:
    """含「受文者」的外發函文若缺少「速別」標示則回報 issue。

    依《政府文書格式參考規範》，函、書函、開會通知單等外發公文
    均應填列速別（最速件／速件／普通件）。
    """
    if _FORMAL_DOC_INDICATOR in text and "速別" not in text:
        return [{
            "line": 0,
            "category": "缺少速別",
            "detail": "函文含「受文者」但缺少「速別」標示（普通件／速件／最速件）",
        }]
    return []


def _check_subject_closing(text: str) -> list[dict]:
    """外發函文的「主旨」段落宜以正式結尾語收尾。

    依《文書處理手冊》，函的主旨以「請　查照」「請　照辦」等結尾；
    呈以「請　鑒核」結尾；若完全無結尾語則提示。
    僅對含「受文者」的外發文件執行此規則。
    """
    if _FORMAL_DOC_INDICATOR not in text:
        return []

    lines = text.split("\n")
    subject_lines: list[str] = []
    in_subject = False
    _NEXT_SECTION_KEYWORDS = ("說明", "公告事項", "依據", "正本", "副本", "擬辦", "附件")

    for line in lines:
        stripped = line.strip()
        if "主旨" in stripped and ("：" in stripped or ":" in stripped):
            in_subject = True
            subject_lines.append(stripped)
            continue
        if in_subject:
            if stripped and any(
                kw in stripped and ("：" in stripped or ":" in stripped)
                for kw in _NEXT_SECTION_KEYWORDS
            ):
                break
            if stripped:
                subject_lines.append(stripped)

    if not subject_lines:
        return []

    subject_text = " ".join(subject_lines)
    if not any(closing in subject_text for closing in _SUBJECT_CLOSINGS):
        return [{
            "line": 0,
            "category": "主旨結尾",
            "detail": "函文主旨宜以「請　查照」「請　照辦」「請　鑒核」等結尾語收尾",
        }]
    return []


def _check_doc_number(text: str) -> list[dict]:
    """正式外發公文含「受文者」但缺少發文字號時回報 issue。

    依《政府文書格式參考規範》，函應填列發文字號（格式：XX字第XXXXXXXXXX號）。
    """
    if _FORMAL_DOC_INDICATOR in text and "字號" not in text and "字第" not in text:
        return [{
            "line": 0,
            "category": "缺少字號",
            "detail": "正式公文應標示發文字號（格式：XX字第XXXXXXXXXX號）",
        }]
    return []


def _run_lint(text: str) -> list[dict]:
    """對公文純文字內容執行 lint 檢查，回傳 issue 清單。

    每個 issue 為 dict，含 ``line``（行號，0 = 全文）、``category``、``detail``。
    此函式不依賴檔案 I/O，可直接被其他模組（如 generate）呼叫。
    """
    lines = text.split("\n")
    issues: list[dict] = []

    # 1. 口語化用詞
    for i, line in enumerate(lines, 1):
        for informal, formal in _INFORMAL_TERMS.items():
            if informal in line:
                issues.append({
                    "line": i,
                    "category": "口語化用詞",
                    "detail": f"「{informal}」建議改為「{formal}」",
                })

    # 2. 必要段落檢查
    for section in _REQUIRED_SECTIONS:
        if section not in text:
            issues.append({
                "line": 0,
                "category": "缺少段落",
                "detail": f"缺少「{section}」段落",
            })

    # 3. 句末標點不一致
    punctuations_used = set()
    for line in lines:
        stripped = line.strip()
        if stripped and stripped[-1] in ("。", "；", ".", "："):
            punctuations_used.add(stripped[-1])
    if len(punctuations_used) > 1:
        issues.append({
            "line": 0,
            "category": "標點不一致",
            "detail": f"句末混用多種標點：{'、'.join(sorted(punctuations_used))}",
        })

    # 4. 速別缺失
    issues.extend(_check_speed_level(text))

    # 5. 主旨結尾用語
    issues.extend(_check_subject_closing(text))

    # 6. 缺少發文字號
    issues.extend(_check_doc_number(text))

    return issues


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
