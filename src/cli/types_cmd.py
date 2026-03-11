"""列出支援的公文類型。"""
from rich.console import Console
from rich.table import Table

from src.core.models import VALID_DOC_TYPES

console = Console()

# 各文類的描述和範例
DOC_TYPE_INFO: dict[str, dict[str, str]] = {
    "函": {
        "desc": "最常見的公文類型，用於機關間一般往復行文",
        "example": "台北市環保局發給各學校，加強資源回收",
    },
    "公告": {
        "desc": "對外發布政策、法規修正或公開資訊",
        "example": "內政部公告修正建築法施行細則",
    },
    "簽": {
        "desc": "機關內部向上級簽請核示或報告事項",
        "example": "簽請同意出差計畫",
    },
    "書函": {
        "desc": "機關間的平行函文，語氣較函正式但略為簡便",
        "example": "台北市政府書函各區公所配合辦理市政調查",
    },
    "令": {
        "desc": "發布法規命令、人事命令或行政指令",
        "example": "發布新的行政規則施行令",
    },
    "開會通知單": {
        "desc": "通知與會人員出席會議",
        "example": "發送業務協調會議開會通知",
    },
    "呈": {
        "desc": "下級機關向總統或行政院呈報事項",
        "example": "行政院呈報總統年度施政成果",
    },
    "咨": {
        "desc": "總統與立法院之間的往復公文",
        "example": "總統咨請立法院審議法案",
    },
    "會勘通知單": {
        "desc": "通知相關單位進行現場勘查",
        "example": "工務局道路損壞會勘通知",
    },
    "公務電話紀錄": {
        "desc": "記錄公務電話聯繫的重點內容",
        "example": "記錄與環保局的公務電話內容",
    },
    "手令": {
        "desc": "機關首長以書面下達的指令",
        "example": "首長手令指示加速辦理案件",
    },
    "箋函": {
        "desc": "機關內部的簡便文書，用於不須正式行文的情形",
        "example": "各科室箋函轉知內部行政事項",
    },
}


def types_command():
    """列出所有支援的公文類型及其說明。"""
    table = Table(
        title="支援的公文類型（共 {} 種）".format(len(VALID_DOC_TYPES)),
        show_lines=True,
        expand=False,
    )
    table.add_column("#", style="dim", width=3, justify="right")
    table.add_column("類型", style="bold cyan", width=10)
    table.add_column("說明", width=40)
    table.add_column("範例需求", style="dim", width=40)

    for idx, doc_type in enumerate(VALID_DOC_TYPES, 1):
        info = DOC_TYPE_INFO.get(doc_type, {"desc": "（無說明）", "example": "—"})
        table.add_row(
            str(idx),
            doc_type,
            info["desc"],
            info["example"],
        )

    console.print(table)
    console.print(
        "\n[dim]使用方式：gov-ai generate -i \"<範例需求>\"[/dim]"
    )
