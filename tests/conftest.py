import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock

# 確保 src 在 Python 路徑中
sys.path.append(str(Path(__file__).parent.parent))

from src.core.llm import LLMProvider
from src.core.models import PublicDocRequirement
from src.core.review_models import ReviewResult, ReviewIssue


@pytest.fixture
def mock_llm():
    """回傳一個 mock LLM 提供者。"""
    llm = MagicMock(spec=LLMProvider)
    llm.generate.return_value = "Mock Response"
    llm.embed.return_value = [0.1] * 384  # 假的 embedding 向量
    return llm


@pytest.fixture
def sample_requirement():
    """回傳一個有效的 PublicDocRequirement 物件。"""
    return PublicDocRequirement(
        doc_type="函",
        urgency="普通",
        sender="測試機關",
        receiver="測試單位",
        subject="測試主旨",
        reason="測試說明",
        action_items=["動作1", "動作2"],
        attachments=["附件1"]
    )


@pytest.fixture
def sample_announcement_requirement():
    """回傳一個公告類型的 PublicDocRequirement 物件。"""
    return PublicDocRequirement(
        doc_type="公告",
        urgency="普通",
        sender="環保局",
        receiver="各機關",
        subject="公告回收相關事項",
        reason="為加強資源回收",
        action_items=["加強宣導", "落實分類"],
        attachments=["回收指南"]
    )


@pytest.fixture
def sample_sign_requirement():
    """回傳一個簽類型的 PublicDocRequirement 物件。"""
    return PublicDocRequirement(
        doc_type="簽",
        sender="市府",
        receiver="局長",
        subject="簽呈測試",
        reason="為辦理某項業務",
    )


@pytest.fixture
def sample_decree_requirement():
    """回傳一個令類型的 PublicDocRequirement 物件。"""
    return PublicDocRequirement(
        doc_type="令",
        sender="行政院",
        receiver="各部會",
        subject="修正某條例施行細則",
        reason="依據某法第X條規定",
        action_items=["自公布日施行"],
        attachments=["修正條文對照表"]
    )


@pytest.fixture
def sample_meeting_notice_requirement():
    """回傳一個開會通知單類型的 PublicDocRequirement 物件。"""
    return PublicDocRequirement(
        doc_type="開會通知單",
        sender="臺北市政府",
        receiver="相關單位",
        subject="召開年度預算審查會議",
        reason="為審議115年度預算案",
        action_items=["請準時出席", "攜帶相關資料"],
        attachments=["議程表", "預算案摘要"]
    )


@pytest.fixture
def sample_letter_requirement():
    """回傳一個書函類型的 PublicDocRequirement 物件。"""
    return PublicDocRequirement(
        doc_type="書函",
        sender="臺北市政府環境保護局",
        receiver="各區清潔隊",
        subject="函送資源回收作業注意事項",
        reason="配合中央政策",
        action_items=["請依規定辦理"],
    )


@pytest.fixture
def sample_draft():
    """回傳一份標準公文草稿文字。"""
    return """# 函

**機關**：測試機關
**受文者**：測試單位
**速別**：普通
**發文日期**：中華民國114年2月18日

---

### 主旨
關於加強辦理某項業務一案，請查照。

### 說明
一、依據某法規辦理。
二、為落實相關政策。

### 辦法
一、請各單位配合辦理。
二、請於期限內完成。
"""


@pytest.fixture
def sample_review_result_with_errors():
    """回傳一個包含錯誤的 ReviewResult。"""
    return ReviewResult(
        agent_name="Format Auditor",
        issues=[
            ReviewIssue(
                category="format",
                severity="error",
                risk_level="high",
                location="文件結構",
                description="缺少主旨欄位"
            ),
            ReviewIssue(
                category="format",
                severity="warning",
                risk_level="medium",
                location="說明",
                description="說明段落過短"
            ),
        ],
        score=0.5,
        confidence=1.0,
    )


@pytest.fixture
def sample_review_result_clean():
    """回傳一個沒有問題的 ReviewResult。"""
    return ReviewResult(
        agent_name="Style Checker",
        issues=[],
        score=0.95,
        confidence=0.9,
    )


@pytest.fixture
def sample_chen_requirement():
    """回傳一個呈類型的 PublicDocRequirement 物件。"""
    return PublicDocRequirement(
        doc_type="呈",
        sender="行政院",
        receiver="總統府",
        subject="呈報115年度施政成果報告",
        reason="依據行政院組織法規定",
        action_items=["擬請鈞府鑒核"],
    )


@pytest.fixture
def sample_zi_requirement():
    """回傳一個咨類型的 PublicDocRequirement 物件。"""
    return PublicDocRequirement(
        doc_type="咨",
        sender="總統府",
        receiver="立法院",
        subject="咨請貴院審議國際條約案",
        reason="依據憲法第63條規定",
        action_items=["請審議"],
    )


@pytest.fixture
def sample_inspection_requirement():
    """回傳一個會勘通知單類型的 PublicDocRequirement 物件。"""
    return PublicDocRequirement(
        doc_type="會勘通知單",
        sender="臺北市政府工務局",
        receiver="相關單位",
        subject="辦理信義路段道路損壞會勘",
        reason="接獲民眾陳情道路損壞",
        action_items=["請派員參加", "攜帶相關圖說"],
    )


@pytest.fixture
def sample_phone_requirement():
    """回傳一個公務電話紀錄類型的 PublicDocRequirement 物件。"""
    return PublicDocRequirement(
        doc_type="公務電話紀錄",
        sender="臺北市政府秘書處",
        receiver="臺北市政府環境保護局",
        subject="確認環境影響評估會議時間",
        reason="因原訂會議時間與其他會議衝突",
    )


@pytest.fixture
def sample_directive_requirement():
    """回傳一個手令類型的 PublicDocRequirement 物件。"""
    return PublicDocRequirement(
        doc_type="手令",
        sender="臺北市市長",
        receiver="都市發展局局長",
        subject="指派辦理社會住宅專案",
        reason="為加速推動社會住宅政策",
        action_items=["即日起督導辦理"],
    )


@pytest.fixture
def sample_memo_requirement():
    """回傳一個箋函類型的 PublicDocRequirement 物件。"""
    return PublicDocRequirement(
        doc_type="箋函",
        sender="臺北市政府秘書處",
        receiver="臺北市政府人事處",
        subject="請提供本年度員工訓練計畫",
        reason="配合年度施政報告彙整",
    )
