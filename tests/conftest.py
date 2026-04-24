import copy
import logging
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock

# 確保 src 在 Python 路徑中
sys.path.append(str(Path(__file__).parent.parent))

from src.cli.utils import cleanup_orphan_tmps
from src.core.logging_config import install_litellm_async_cleanup_filter
from src.core.llm import LLMProvider
from src.core.models import PublicDocRequirement
from src.core.review_models import ReviewResult, ReviewIssue


# ============================================================
# API 測試用共用配置 — 單一來源，避免各檔案重複定義導致不同步
# Round 4/9/10 三次因漏加 auth_enabled:False 造成 401 假失敗
# ============================================================

_BASE_API_CONFIG: dict = {
    "llm": {"provider": "mock", "model": "test"},
    "knowledge_base": {"path": "./test_kb"},
    "api": {"auth_enabled": False},
}


@pytest.fixture(scope="session", autouse=True)
def suppress_litellm_async_cleanup_noise():
    """避免 litellm 在測試 teardown 階段透過 asyncio 噴 closed-file logging error。"""
    install_litellm_async_cleanup_filter()
    logging.getLogger("asyncio").setLevel(logging.WARNING)


@pytest.fixture(scope="session", autouse=True)
def cleanup_repo_root_atomic_tmps():
    """每次測試 session 前後都清理 repo root 遺留的 atomic tmp。"""
    repo_root = Path(__file__).resolve().parent.parent
    cleanup_orphan_tmps(str(repo_root), max_age_seconds=None)
    yield
    cleanup_orphan_tmps(str(repo_root), max_age_seconds=None)


@pytest.fixture(scope="session", autouse=True)
def _preload_empty_realtime_lookup_caches():
    """預先以 empty cache 佔位，阻止 LawVerifier / RecentPolicyFetcher 首次 cold-boot
    對 law.moj.gov.tw / www.ey.gov.tw 發 HTTP 請求（本機無網路時 ~40s retry 死時間）。

    命中 draft: EditorInChief 全鏈路 test 只要 draft 含「依據相關法規辦理」等模糊
    citation 片段，`_CITATION_PATTERN` 會匹配 → `verify_citations` → `_ensure_cache`
    → download → `Max retries exceeded` 等 40s。

    test_realtime_lookup.py 有自己的 autouse `_clear_caches` 會把 `_cache = None`
    覆蓋本 preload，真正驗 cache 行為的測試不受影響。

    對症源: T-TEST-LOCAL-BINDING-AUDIT 冰山第 2 型（外部服務實例化漏 mock）。
    """
    from src.knowledge.realtime_lookup import (
        LawVerifier,
        RecentPolicyFetcher,
        _LawCacheEntry,
        _GazetteCacheEntry,
    )

    if LawVerifier._cache is None:
        LawVerifier._cache = _LawCacheEntry(data={})
    if RecentPolicyFetcher._cache is None:
        RecentPolicyFetcher._cache = _GazetteCacheEntry(records=[])
    yield


def make_api_config(**overrides) -> dict:
    """建立 API 測試配置（auth 預設關閉）。

    每次呼叫回傳獨立的 deep copy，避免測試間互相汙染。
    可透過 keyword args 覆蓋頂層 key。

    範例::

        cfg = make_api_config()  # 標準配置
        cfg = make_api_config(api={"auth_enabled": True, "api_keys": ["k1"]})
    """
    config = copy.deepcopy(_BASE_API_CONFIG)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(config.get(key), dict):
            config[key].update(value)
        else:
            config[key] = value
    return config


def make_mock_llm(**overrides) -> MagicMock:
    """建立 mock LLM 提供者（標準配置，可覆蓋）。

    與 make_api_config() 同手法——單一來源，避免各檔重複定義導致不同步。
    Round 4/9/10 三次 auth 401 假失敗的教訓同樣適用於 LLM/KB mock。

    範例::

        llm = make_mock_llm()  # 標準配置
        llm = make_mock_llm(generate_return="自訂回應")
    """
    llm = MagicMock(spec=LLMProvider)
    llm.generate.return_value = overrides.get("generate_return", "Mock Response")
    llm.embed.return_value = overrides.get("embed_return", [0.1] * 384)
    return llm


def make_mock_kb(**overrides) -> MagicMock:
    """建立 mock 知識庫管理器（標準配置，可覆蓋）。

    預設所有搜尋方法回傳空 list，search_hybrid 帶 distance
    避免觸發 Agentic RAG 精煉迴圈。

    範例::

        kb = make_mock_kb()  # 標準配置
        kb = make_mock_kb(search_hybrid_return=[...])  # 自訂 hybrid 結果
    """
    kb = MagicMock()
    kb.search_examples.return_value = overrides.get("search_examples_return", [])
    kb.search_regulations.return_value = overrides.get("search_regulations_return", [])
    kb.search_policies.return_value = overrides.get("search_policies_return", [])
    kb.search_hybrid.return_value = overrides.get("search_hybrid_return", [])
    kb.is_available = overrides.get("is_available", True)
    kb.get_stats.return_value = overrides.get("get_stats_return", {
        "examples_count": 0,
        "regulations_count": 0,
        "policies_count": 0,
    })
    return kb


@pytest.fixture
def mock_llm():
    """回傳一個 mock LLM 提供者。"""
    return make_mock_llm()


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
def sample_meeting_minutes_requirement():
    """回傳一個開會紀錄類型的 PublicDocRequirement 物件。"""
    return PublicDocRequirement(
        doc_type="開會紀錄",
        sender="臺北市政府",
        receiver="相關單位",
        subject="115年度第1次預算審查會議紀錄",
        reason="為審議115年度預算案召開會議",
        action_items=["請各單位依決議事項辦理"],
        attachments=["出席人員簽到表"]
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
