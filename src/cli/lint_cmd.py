import typer
from rich.console import Console
from rich.table import Table

console = Console()

# 口語化用詞對照
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
}

# 必要段落
_REQUIRED_SECTIONS = ["主旨", "說明"]


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

    lines = text.split("\n")
    issues = []

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
        line = line.strip()
        if line and line[-1] in ("。", "；", ".", "："):
            punctuations_used.add(line[-1])
    if len(punctuations_used) > 1:
        issues.append({
            "line": 0,
            "category": "標點不一致",
            "detail": f"句末混用多種標點：{'、'.join(punctuations_used)}",
        })

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
