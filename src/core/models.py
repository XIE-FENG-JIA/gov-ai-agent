import logging
import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

logger = logging.getLogger(__name__)

# 已知公文類型（用於驗證與 API Literal 類型）
VALID_DOC_TYPES = (
    "函", "公告", "簽", "書函", "令", "開會通知單", "開會紀錄",
    "呈", "咨", "會勘通知單", "公務電話紀錄", "手令", "箋函",
)

# 公文類型關鍵字自動偵測規則（優先匹配順序：越具體的規則排越前面）
# 與 VALID_DOC_TYPES 同步維護，所有需要偵測公文類型的 CLI 命令共用此表。
_DOC_TYPE_PATTERNS: list[tuple[str, str]] = [
    (r"開會紀錄|會議紀錄|出席人員|主席", "開會紀錄"),
    (r"會勘通知", "會勘通知單"),
    (r"公務電話紀錄|發話人|受話人", "公務電話紀錄"),
    (r"手令", "手令"),
    (r"箋函", "箋函"),
    (r"公告", "公告"),
    (r"開會通知", "開會通知單"),
    (r"書函", "書函"),
    (r"^#+\s*呈\b|^呈\b", "呈"),
    (r"^#+\s*咨\b|^咨\b", "咨"),
    (r"簽\s*（|簽$|^#+\s*簽", "簽"),
    (r"令\s|發布.*令|廢止.*令", "令"),
    (r"函$|^#+\s*函\b|主旨|說明|辦法", "函"),
]


def detect_doc_type(content: str, *, fallback: str = "函") -> str:
    """從草稿內容自動偵測公文類型。

    使用 regex 匹配前 500 字，優先匹配具體類型，
    偵測失敗時回傳 fallback（預設「函」，最常見的公文類型）。

    Args:
        content: 公文草稿全文
        fallback: 無法偵測時的預設類型

    Returns:
        偵測到的公文類型字串
    """
    first_500 = content[:500]
    for pattern, doc_type in _DOC_TYPE_PATTERNS:
        if re.search(pattern, first_500, re.MULTILINE):
            return doc_type
    return fallback


# Literal 型別別名：供 API 模型使用，確保與 VALID_DOC_TYPES 同步
DocTypeLiteral = Literal[
    "函", "公告", "簽", "書函", "令", "開會通知單", "開會紀錄",
    "呈", "咨", "會勘通知單", "公務電話紀錄", "手令", "箋函",
]
# 合法速別
VALID_URGENCY_LEVELS = ("普通", "速件", "最速件")


class PublicDocRequirement(BaseModel):
    """
    政府公文的結構化需求模型。
    """
    model_config = ConfigDict(json_schema_extra={
        "examples": [{
            "doc_type": "函",
            "urgency": "普通",
            "sender": "臺北市政府",
            "receiver": "各區公所",
            "subject": "函轉行政院修正文書處理手冊",
            "reason": "依據行政院函辦理",
            "action_items": ["請下載手冊", "更新內部規範"],
            "attachments": ["修正對照表"]
        }]
    })

    doc_type: str = Field(..., description="公文類型（如：函、公告、簽、書函、開會通知單）")
    urgency: str = Field("普通", description="速別（如：普通、速件、最速件）")

    sender: str = Field(..., min_length=1, max_length=200, description="發文機關名稱")
    receiver: str = Field(..., min_length=1, max_length=500, description="受文者（機關或個人）")

    subject: str = Field(..., min_length=1, max_length=500, description="主旨 - 簡要摘述")

    # 主要內容欄位
    reason: str | None = Field(None, description="說明 - 緣起或依據")
    action_items: list[str] = Field(default_factory=list, description="待辦事項清單（說明/辦法）")

    attachments: list[str] = Field(default_factory=list, description="附件清單")

    @field_validator("doc_type")
    @classmethod
    def validate_doc_type(cls, v: str) -> str:
        """驗證公文類型是否為已知類型，不在已知清單中則發出警告但仍接受。"""
        v = v.strip()
        if not v:
            raise ValueError("公文類型不可為空白")
        if v not in VALID_DOC_TYPES:
            logger.warning("未知的公文類型「%s」，已知類型: %s", v, ", ".join(VALID_DOC_TYPES))
        return v

    @field_validator("urgency")
    @classmethod
    def validate_urgency(cls, v: str) -> str:
        """驗證速別是否為合法值。"""
        v = v.strip()
        if v and v not in VALID_URGENCY_LEVELS:
            # 容錯：不嚴格拒絕，但正規化為最接近的值
            logger.warning("未知的速別「%s」，已正規化為「普通」", v)
            return "普通"
        return v if v else "普通"

    @field_validator("sender", "receiver")
    @classmethod
    def validate_sender_receiver_not_blank(cls, v: str) -> str:
        """確保發文機關和受文者去除空白後不為空。"""
        v = v.strip()
        if not v:
            raise ValueError("欄位不可為空白")
        return v

    @field_validator("subject")
    @classmethod
    def validate_subject(cls, v: str) -> str:
        """確保主旨去除空白後不為空。"""
        v = v.strip()
        if not v:
            raise ValueError("主旨不可為空白")
        return v


class Citation(BaseModel):
    """公文引用來源的結構化表示。"""
    index: int = Field(..., description="引用編號，對應 [^i] 標記")
    title: str = Field(..., description="來源標題")
    source_level: str = Field("B", description="來源等級：A=權威, B=輔助")
    source_url: str | None = Field(None, description="原始來源 URL")
    source_type: str = Field("", description="來源類型（公報/法規/開放資料）")
    record_id: str | None = Field(None, description="記錄識別碼")


class PublicGovDoc(BaseModel):
    """公開政府文件的標準化資料模型。"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{
                "source_id": "A0030055",
                "source_url": "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=A0030055",
                "source_agency": "法務部全國法規資料庫",
                "source_doc_no": "A0030055",
                "source_date": "2026-01-15",
                "doc_type": "法規",
                "raw_snapshot_path": None,
                "crawl_date": "2026-04-20",
                "content_md": "# 行政程序法\n\n### 第 1 條\n為使行政行為遵循公正、公開與民主之程序。",
                "synthetic": False,
                "fixture_fallback": False,
            }]
        }
    )

    source_id: str = Field(..., min_length=1, description="來源系統內的唯一識別碼")
    source_url: str = Field(..., min_length=1, description="原始來源 URL")
    source_agency: str = Field(..., min_length=1, description="來源機關")
    source_doc_no: str | None = Field(None, description="原始文號或法規代碼")
    source_date: date | None = Field(None, description="來源文件日期")
    doc_type: str = Field(..., min_length=1, description="文件類型")
    raw_snapshot_path: str | None = Field(None, description="原始快照路徑")
    crawl_date: date = Field(..., description="抓取日期")
    content_md: str = Field(..., min_length=1, description="標準化 Markdown 內容")
    synthetic: bool = Field(False, description="是否為合成資料")
    fixture_fallback: bool = Field(False, description="是否由本地 fixture fallback 產生")

    @field_validator("source_id", "source_url", "source_agency", "doc_type", "content_md")
    @classmethod
    def validate_non_blank_fields(cls, v: str) -> str:
        """核心字串欄位不可為空白。"""
        v = v.strip()
        if not v:
            raise ValueError("欄位不可為空白")
        return v
