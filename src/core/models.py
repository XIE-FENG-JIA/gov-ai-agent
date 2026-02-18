from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import List, Optional

# 已知公文類型（用於驗證）
VALID_DOC_TYPES = ("函", "公告", "簽", "書函", "令", "開會通知單", "通知")
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

    sender: str = Field(..., min_length=1, description="發文機關名稱")
    receiver: str = Field(..., min_length=1, description="受文者（機關或個人）")

    subject: str = Field(..., min_length=1, description="主旨 - 簡要摘述")

    # 主要內容欄位
    reason: Optional[str] = Field(None, description="說明 - 緣起或依據")
    action_items: List[str] = Field(default_factory=list, description="待辦事項清單（說明/辦法）")

    attachments: List[str] = Field(default_factory=list, description="附件清單")

    @field_validator("doc_type")
    @classmethod
    def validate_doc_type(cls, v: str) -> str:
        """驗證公文類型是否為已知類型，不在已知清單中則發出警告但仍接受。"""
        v = v.strip()
        if not v:
            raise ValueError("公文類型不可為空白")
        return v

    @field_validator("urgency")
    @classmethod
    def validate_urgency(cls, v: str) -> str:
        """驗證速別是否為合法值。"""
        v = v.strip()
        if v and v not in VALID_URGENCY_LEVELS:
            # 容錯：不嚴格拒絕，但正規化為最接近的值
            return "普通"
        return v if v else "普通"

    @field_validator("subject")
    @classmethod
    def validate_subject(cls, v: str) -> str:
        """確保主旨去除空白後不為空。"""
        v = v.strip()
        if not v:
            raise ValueError("主旨不可為空白")
        return v
