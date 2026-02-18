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
