"""範例公文指令。

產生預設的公文範例供使用者參考格式。
"""
import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

console = Console()

_SAMPLES = {
    "函": """\
### 臺北市政府環境保護局 函

**受文者：** 各級學校

**發文日期：** 中華民國 114 年 3 月 9 日
**發文字號：** 北環資字第 1140000001 號
**速別：** 普通件
**密等及解密條件或保密期限：**
**附件：** 如說明二

### 主旨
為加強校園資源回收工作，請各校配合辦理。

### 說明
一、依據本局 114 年度資源回收推動計畫辦理。
二、檢附「校園資源回收實施要點」乙份，請各校參照辦理。
三、請於本（114）年 6 月 30 日前將辦理情形函報本局。

### 正本
各級學校

### 副本
本市各區公所

**局長 OOO**
""",
    "公告": """\
### 臺北市政府 公告

**發文日期：** 中華民國 114 年 3 月 9 日
**發文字號：** 府法規字第 1140000002 號

### 主旨
公告修正「臺北市公園管理自治條例」部分條文。

### 依據
地方制度法第二十五條及第二十六條。

### 公告事項
一、修正「臺北市公園管理自治條例」第五條、第八條及第十二條條文。
二、修正重點如下：
  （一）增訂公園內禁止使用擴音設備之規定。
  （二）調整違規罰鍰金額。
三、本公告自即日起生效。

**市長 OOO**
""",
    "簽": """\
### 簽

**機關：** 臺北市政府環境保護局
**簽署人：** 環保稽查科 OOO

**日期：** 中華民國 114 年 3 月 9 日

### 主旨
簽請同意派員出差參加「全國環保技術研討會」。

### 說明
一、行政院環境保護署訂於 114 年 4 月 15 日至 16 日假高雄市舉辦旨揭研討會。
二、擬派本科技正 OOO 及技士 OOO 等 2 人出席。
三、所需差旅費約新臺幣 8,000 元整，由本局公務預算項下支應。

### 擬辦
請核示。

**科長 OOO**
""",
}


def sample(
    doc_type: str = typer.Argument("函", help="公文類型（函、公告、簽）"),
):
    """
    顯示公文格式範例供參考。

    範例：

        gov-ai sample 函

        gov-ai sample 公告

        gov-ai sample 簽
    """
    if doc_type not in _SAMPLES:
        available = "、".join(_SAMPLES.keys())
        console.print(f"[red]錯誤：不支援的範例類型「{doc_type}」。[/red]")
        console.print(f"[dim]可用範例：{available}[/dim]")
        raise typer.Exit(1)

    console.print(Panel(
        Markdown(_SAMPLES[doc_type]),
        title=f"[bold cyan]公文範例 — {doc_type}[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    ))
    console.print("[dim]此為格式範例，非 LLM 生成內容。[/dim]")
    console.print(f'[dim]欲 AI 產生公文，請使用：gov-ai generate -i "您的需求"[/dim]')
