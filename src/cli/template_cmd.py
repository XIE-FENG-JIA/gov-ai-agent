"""公文骨架範本指令。

顯示各類公文的骨架範本（含佔位符），供使用者快速填寫。
支援 --generate 旗標，直接進入 generate → lint 完整 pipeline。
"""
import os
import subprocess
import sys
import tempfile
import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

console = Console()

# 範本分類對應表（供 --list 使用）
_TEMPLATE_CATEGORIES: dict[str, list[str]] = {
    "正式公文": ["函", "公告", "令", "呈", "咨"],
    "內部簽核": ["簽", "箋函"],
    "對外行文": ["書函", "手令"],
    "通知與紀錄": ["開會通知單", "會勘通知單", "公務電話紀錄"],
    "公示與資訊公開": ["公示", "公示送達", "政府資訊公開", "簡便行文表"],
}

_TEMPLATES: dict[str, str] = {
    "函": """\
# 函

**機關全銜：** [機關全銜]
**受文者：** [受文者]
**發文日期：** 中華民國 [年] 年 [月] 月 [日] 日
**發文字號：** [字號]
**速別：** [普通件／最速件／速件]
**密等及解密條件或保密期限：**
**附件：** [附件名稱，無則免填]

### 主旨
[一段完整敘述，說明行文目的，以「請 查照」或「請 照辦」結尾]

### 說明
一、[引述依據或背景]
二、[補充細節]
三、[期限或配合事項]

### 正本
[主要受文機關]

### 副本
[副知機關，無則免填]
""",
    "公告": """\
# 公告

**機關全銜：** [機關全銜]
**發文日期：** 中華民國 [年] 年 [月] 月 [日] 日
**發文字號：** [字號]

### 主旨
[公告事由，一段完整敘述]

### 依據
[法規名稱及條次]

### 公告事項
一、[第一項公告內容]
二、[第二項公告內容]
三、[生效日期或其他事項]
""",
    "簽": """\
# 簽

**機關：** [機關全銜]
**簽署人：** [單位及職稱姓名]
**日期：** 中華民國 [年] 年 [月] 月 [日] 日

### 主旨
[簽請核示事項，一段完整敘述]

### 說明
一、[事由背景]
二、[分析或補充資料]
三、[經費或其他考量]

### 擬辦
[建議處理方式，如「擬同意辦理，請核示。」]
""",
    "書函": """\
# 書函

**機關全銜：** [機關全銜]
**受文者：** [受文者]
**發文日期：** 中華民國 [年] 年 [月] 月 [日] 日
**發文字號：** [字號]
**速別：** [普通件／最速件／速件]

### 主旨
[行文目的，一段完整敘述]

### 說明
一、[背景或依據]
二、[具體事項]

### 正本
[主要受文機關]

### 副本
[副知機關，無則免填]
""",
    "令": """\
# 令

**機關全銜：** [機關全銜]
**發文日期：** 中華民國 [年] 年 [月] 月 [日] 日
**發文字號：** [字號]

### 主旨
[發布、修正或廢止之法規名稱及事由]

### 說明
一、[法規依據]
二、[施行日期或其他事項]
""",
    "開會通知單": """\
# 開會通知單

**機關全銜：** [機關全銜]
**受文者：** [受文者]
**發文日期：** 中華民國 [年] 年 [月] 月 [日] 日
**發文字號：** [字號]

### 開會事由
[會議名稱或事由]

### 開會時間
中華民國 [年] 年 [月] 月 [日] 日（星期[X]）[上午／下午] [時] 時 [分] 分

### 開會地點
[地點名稱及地址]

### 主持人
[職稱及姓名]

### 出席者
[應出席單位或人員]

### 議程
一、[報告事項]
二、[討論事項]
三、[臨時動議]

### 備註
[其他注意事項，無則免填]
""",
    "會勘通知單": """\
# 會勘通知單

**機關全銜：** [機關全銜]
**受文者：** [受文者]
**發文日期：** 中華民國 [年] 年 [月] 月 [日] 日
**發文字號：** [字號]

### 會勘事由
[會勘目的]

### 會勘時間
中華民國 [年] 年 [月] 月 [日] 日（星期[X]）[上午／下午] [時] 時

### 會勘地點
[地點名稱及地址]

### 會勘事項
一、[勘查項目一]
二、[勘查項目二]

### 應出席單位
[出席單位及人員]

### 應攜文件
[需攜帶之資料或文件]
""",
    "公務電話紀錄": """\
# 公務電話紀錄

**機關：** [機關全銜]
**日期：** 中華民國 [年] 年 [月] 月 [日] 日

### 發話人
[機關、單位、職稱、姓名]

### 受話人
[機關、單位、職稱、姓名]

### 通話時間
[年] 年 [月] 月 [日] 日 [時] 時 [分] 分

### 通話摘要
[通話內容重點摘要]

### 追蹤事項
一、[後續辦理事項]

### 紀錄人
[姓名]

### 核閱
[主管職稱及姓名]
""",
    "手令": """\
# 手令

**機關全銜：** [機關全銜]
**日期：** 中華民國 [年] 年 [月] 月 [日] 日

### 受令者
[受令單位或人員]

### 指示事項
[具體指示內容]

### 完成期限
中華民國 [年] 年 [月] 月 [日] 日前

### 副知
[副知單位，無則免填]
""",
    "箋函": """\
# 箋函

**機關全銜：** [機關全銜]
**受文者：** [受文者]
**日期：** 中華民國 [年] 年 [月] 月 [日] 日

### 主旨
[行文目的，語氣較函柔和]

### 說明
一、[背景說明]
二、[具體事項]
""",
    "呈": """\
# 呈

**機關全銜：** [下級機關全銜]
**受文者：** [上級機關]
**發文日期：** 中華民國 [年] 年 [月] 月 [日] 日
**發文字號：** [字號]

### 主旨
[呈報事項，一段完整敘述，以「請 鑒核」結尾]

### 說明
一、[事由或依據]
二、[詳細說明]
""",
    "咨": """\
# 咨

**機關全銜：** [機關全銜]
**受文者：** [平行機關]
**發文日期：** 中華民國 [年] 年 [月] 月 [日] 日
**發文字號：** [字號]

### 主旨
[行文目的，一段完整敘述]

### 說明
一、[背景或依據]
二、[具體事項]
""",
    "公示": """\
# 公示

**機關全銜：** [機關全銜]
**發文日期：** 中華民國 [年] 年 [月] 月 [日] 日
**發文字號：** [字號]

### 主旨
公示[計畫/方案名稱]，自本公示發布之翌日起至[年月日]止，公開徵求各界意見，請 查照。

### 依據
[法規名稱及條次，例：都市計畫法第19條、環境影響評估法第7條]

### 公示事項
一、公示範圍：[地理範圍或適用對象]
二、公示內容：[主要計畫內容摘要]
三、公示期間：自中華民國[年月日]起至[年月日]止，共[天數]日。
四、公示地點：[機關名稱及地址]；亦可至本機關官網（[網址]）查閱相關資料。
五、意見提送方式：
    （一）書面意見：請於公示期間內寄送至[地址]，或逕送本機關收文窗口。
    （二）電子郵件：[email@gov.tw]
六、聯絡窗口：[承辦單位] [承辦人姓名]，電話：[電話號碼]。

機關長官職銜　[姓名]
""",
    "公示送達": """\
# 公示送達

**機關全銜：** [機關全銜]
**發文日期：** 中華民國 [年] 年 [月] 月 [日] 日
**發文字號：** [字號]

### 主旨
公示送達[受送達人姓名/全銜]（[身分證字號/統一編號]）[文書名稱]，請 查照。

### 依據
行政程序法第78條第1項第[款次]款。

### 公告事項
一、受送達人：[姓名]（[身分證字號]），戶籍/通訊地址：[地址]。
二、應送達文書：[文書名稱及字號]。
三、無法完成送達原因：[應受送達人不明／寄存送達無人收受等，依實況填寫]。
四、依行政程序法第78條規定，以公示送達方式辦理。
五、公示送達自本公告揭示之翌日起，經20日發生送達效力。
六、如受送達人有異議，請於送達效力發生後[X]日內向本機關提出。

機關長官職銜　[姓名]
""",
    "政府資訊公開": """\
# 函（政府資訊公開申請回覆）

**機關全銜：** [機關全銜]
**受文者：** [申請人姓名/全銜]
**發文日期：** 中華民國 [年] 年 [月] 月 [日] 日
**發文字號：** [字號]
**速別：** 普通件
**附件：** [附上之資訊或文件，無則免填]

### 主旨
復貴[君/府/機關]中華民國[年月日][來文字號]申請政府資訊公開乙案，[准予提供／部分提供／不予提供]，請 查照。

### 說明
一、依據：政府資訊公開法第[條次]條。
二、本案申請資訊為：[申請資訊名稱及範圍]。
三、[准予提供] 本機關就所申請資訊，業已備妥，[如附件提供／請逕至本機關洽取]。
   [部分提供] 其中[部分資訊名稱]，因涉及[政府資訊公開法第18條各款事由]，依法不予提供；其餘部分，如附件。
   [不予提供] 本案申請之資訊，因[敘明理由，如：涉及個人隱私／妨害偵查／例外事由條文]，依政府資訊公開法第18條第1項第[款]款規定，不予提供。
四、如不服本決定，得依訴願法第14條規定，自送達翌日起30日內向[訴願管轄機關]提起訴願。

### 正本
[申請人姓名/全銜]

### 副本
[無]
""",
    "簡便行文表": """\
# 簡便行文表

**機關全銜：** [機關全銜]
**受文者：** [受文機關或單位]
**日期：** 中華民國 [年] 年 [月] 月 [日] 日
**字號：** [字號，得免填]

### 事由
[以一段簡短文字說明行文事由，不需分段]

### 附件
[附件名稱及份數，無則填「無」]

### 聯絡人
[承辦單位] [承辦人姓名]，電話：[電話號碼]，電子郵件：[email]

（本行文表適用機關間日常例行聯繫、通知等事項，不得用於正式公文行為）
""",
}


def _launch_generate(
    template_content: str,
    gen_output: str,
    *,
    preview: bool = False,
    skip_review: bool = False,
    quiet: bool = False,
    no_lint: bool = False,
) -> int:
    """將範本寫入暫存檔並以 subprocess 啟動 generate 子流程。

    回傳 generate 子流程的 returncode。
    """
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".md",
            encoding="utf-8",
            delete=False,
            prefix="govai_tpl_",
        ) as f:
            f.write(template_content)
            tmp_path = f.name

        cmd = [
            sys.executable,
            "-c",
            "from src.cli.main import app; app(prog_name='gov-ai')",
            "generate",
            "--from-file", tmp_path,
            "--output", gen_output,
        ]
        if preview:
            cmd.append("--preview")
        if skip_review:
            cmd.append("--skip-review")
        if quiet:
            cmd.append("--quiet")
        if no_lint:
            cmd.append("--no-lint")

        result = subprocess.run(cmd)
        return result.returncode
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def template(
    doc_type: str = typer.Argument("函", help="公文類型（函、公告、簽、書函、令等）"),
    output: str = typer.Option("", "--output", "-o", help="匯出範本至檔案"),
    list_all: bool = typer.Option(False, "--list", "-l", help="列出所有可用範本類型（依分類）"),
    generate_doc: bool = typer.Option(
        False, "--generate", "-g",
        help="顯示範本後直接啟動 generate 生成流程（template → generate → lint 一鍵閉環）",
    ),
    gen_output: str = typer.Option(
        "output.docx", "--gen-output",
        help="generate 的輸出 .docx 路徑（搭配 --generate 使用）",
    ),
    gen_preview: bool = typer.Option(
        False, "--gen-preview",
        help="generate 完成後在終端預覽（搭配 --generate 使用）",
    ),
    gen_skip_review: bool = typer.Option(
        False, "--gen-skip-review",
        help="generate 時跳過多 Agent 審查步驟（搭配 --generate 使用）",
    ),
    gen_no_lint: bool = typer.Option(
        False, "--gen-no-lint",
        help="generate 時關閉自動 lint 檢查（搭配 --generate 使用）",
    ),
):
    """
    顯示公文骨架範本，包含佔位符供快速填寫。

    加上 --generate 可直接進入 generate → lint 完整 pipeline（一鍵閉環）。

    範例：

        gov-ai template 函

        gov-ai template 公告

        gov-ai template 簽 -o template.md

        gov-ai template --list

        gov-ai template 函 --generate

        gov-ai template 函 --generate --gen-output 函文.docx --gen-preview
    """
    if list_all:
        _show_template_list()
        return

    if doc_type not in _TEMPLATES:
        available = "、".join(_TEMPLATES.keys())
        console.print(f"[red]錯誤：不支援的範本類型「{doc_type}」。[/red]")
        console.print(f"[dim]可用類型：{available}[/dim]")
        console.print("[dim]使用 gov-ai template --list 查看分類清單。[/dim]")
        raise typer.Exit(1)

    content = _TEMPLATES[doc_type]

    console.print(Panel(
        Markdown(content),
        title=f"[bold cyan]公文範本 — {doc_type}[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    ))

    if not generate_doc:
        console.print("[dim]修改佔位符後可直接用作需求描述。[/dim]")
        console.print('[dim]填寫完成後可使用：gov-ai generate -i "填寫後的內容"[/dim]')
        console.print(f'[dim]或直接一鍵生成：gov-ai template {doc_type} --generate[/dim]')

    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(content)
        console.print(f"[green]範本已匯出至：{output}[/green]")

    if generate_doc:
        console.print()
        console.print(Panel(
            f"[bold green]正在啟動 generate 流程...[/bold green]\n"
            f"[dim]範本類型：{doc_type}　輸出：{gen_output}[/dim]",
            title="[bold green]template → generate → lint[/bold green]",
            border_style="green",
        ))
        rc = _launch_generate(
            content,
            gen_output,
            preview=gen_preview,
            skip_review=gen_skip_review,
            no_lint=gen_no_lint,
        )
        if rc != 0:
            console.print(f"[yellow]generate 子流程以代碼 {rc} 結束。[/yellow]")
            raise typer.Exit(rc)


def _show_template_list() -> None:
    """以分類方式顯示所有可用範本。"""
    from rich.table import Table

    table = Table(
        title="[bold cyan]公文範本清單[/bold cyan]",
        border_style="cyan",
        header_style="bold",
        show_lines=True,
    )
    table.add_column("分類", style="bold yellow", min_width=12)
    table.add_column("範本類型", min_width=10)
    table.add_column("使用指令", style="dim")

    for category, types in _TEMPLATE_CATEGORIES.items():
        for i, t in enumerate(types):
            table.add_row(
                category if i == 0 else "",
                t,
                f"gov-ai template {t}",
            )

    console.print(table)
    console.print(f"[dim]共 {len(_TEMPLATES)} 種範本。使用 gov-ai template <類型> 顯示骨架。[/dim]")
