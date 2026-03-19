"""即時法規驗證與政策查詢服務測試。"""
import json
import io
import zipfile
import warnings
import pytest
from unittest.mock import MagicMock, patch, call

from src.knowledge.realtime_lookup import (
    Citation,
    CitationCheck,
    LawVerifier,
    RecentPolicyFetcher,
    format_verification_results,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_law_json(laws: list[dict]) -> bytes:
    """建立模擬法規 JSON（ZIP 格式）。"""
    payload = json.dumps({"Laws": laws}, ensure_ascii=False).encode("utf-8")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("ChLaw.json", payload)
    return buf.getvalue()


def _make_gazette_xml(records: list[dict]) -> bytes:
    """建立模擬公報 XML。"""
    parts = ['<?xml version="1.0" encoding="utf-8"?><Records>']
    for rec in records:
        parts.append("<Record>")
        for k, v in rec.items():
            parts.append(f"<{k}>{v}</{k}>")
        parts.append("</Record>")
    parts.append("</Records>")
    return "".join(parts).encode("utf-8")


SAMPLE_LAWS = [
    {
        "PCode": "A0030055",
        "LawName": "行政程序法",
        "LawArticles": [
            {"ArticleNo": "第 1 條", "ArticleContent": "為使行政行為遵循公正、公開與民主之程序。"},
            {"ArticleNo": "第 100 條", "ArticleContent": "書面之行政處分自送達相對人及已知之利害關係人起。"},
            {"ArticleNo": "第 175 條", "ArticleContent": "本法自中華民國九十年一月一日施行。"},
        ],
    },
    {
        "PCode": "O0060001",
        "LawName": "空氣污染防制法",
        "LawArticles": [
            {"ArticleNo": "第 1 條", "ArticleContent": "為防制空氣污染，維護生活環境及國民健康。"},
            {"ArticleNo": "第 32 條", "ArticleContent": "在各級防制區及總量管制區內，不得有下列行為。"},
        ],
    },
    {
        "PCode": "J0150028",
        "LawName": "資通安全管理法",
        "LawArticles": [
            {"ArticleNo": "第 1 條", "ArticleContent": "為積極推動國家資通安全政策。"},
        ],
    },
]

SAMPLE_GAZETTE_RECORDS = [
    {
        "MetaId": "001",
        "Title": "修正空氣污染防制法施行細則部分條文",
        "Category": "法規命令",
        "PubGov": "行政院環境保護署",
        "Date_Published": "2026-03-01",
    },
    {
        "MetaId": "002",
        "Title": "公告110年度政府採購統計報表",
        "Category": "施政計畫",
        "PubGov": "行政院公共工程委員會",
        "Date_Published": "2026-03-02",
    },
    {
        "MetaId": "003",
        "Title": "促進數位轉型發展方案",
        "Category": "施政計畫",
        "PubGov": "數位發展部",
        "Date_Published": "2026-03-03",
    },
]


@pytest.fixture(autouse=True)
def _clear_caches():
    """每個測試前後清除類別級快取。"""
    LawVerifier._cache = None
    RecentPolicyFetcher._cache = None
    yield
    LawVerifier._cache = None
    RecentPolicyFetcher._cache = None


# ===========================================================================
# TestLawVerifier
# ===========================================================================

class TestLawVerifier:

    def test_extract_citations_basic(self):
        """驗證正則提取法規引用。"""
        v = LawVerifier()
        text = "依據行政程序法第100條辦理。另按空氣污染防制法第32條規定。"
        citations = v._extract_citations(text)
        assert len(citations) == 2
        assert citations[0].law_name == "行政程序法"
        assert citations[0].article_no == "100"
        assert citations[1].law_name == "空氣污染防制法"
        assert citations[1].article_no == "32"

    def test_extract_citations_no_article(self):
        """法規引用不含條文號。"""
        v = LawVerifier()
        text = "依據個人資料保護法辦理。"
        citations = v._extract_citations(text)
        assert len(citations) == 1
        assert citations[0].law_name == "個人資料保護法"
        assert citations[0].article_no is None

    def test_extract_citations_with_brackets(self):
        """「」括號包圍的法規名稱。"""
        v = LawVerifier()
        text = "依據「行政程序法」第100條辦理。"
        citations = v._extract_citations(text)
        assert len(citations) >= 1
        assert any(c.law_name == "行政程序法" for c in citations)

    def test_extract_citations_dedup(self):
        """重複引用只出現一次。"""
        v = LawVerifier()
        text = "依據行政程序法第100條。另依行政程序法第100條。"
        citations = v._extract_citations(text)
        assert len(citations) == 1

    def test_extract_citations_hyphenated_article(self):
        """支援「第 32-1 條」格式。"""
        v = LawVerifier()
        text = "按空氣污染防制法第32-1條規定"
        citations = v._extract_citations(text)
        assert len(citations) == 1
        assert citations[0].article_no == "32-1"

    def test_extract_citations_empty(self):
        """無法規引用。"""
        v = LawVerifier()
        assert v._extract_citations("今天天氣很好") == []

    @patch("src.knowledge.realtime_lookup._request_with_retry")
    def test_verify_existing_law(self, mock_req):
        """mock API 回傳，驗證法規存在。"""
        mock_resp = MagicMock()
        mock_resp.content = _make_law_json(SAMPLE_LAWS)
        mock_req.return_value = mock_resp

        v = LawVerifier()
        draft = "依據行政程序法第100條辦理。"
        checks = v.verify_citations(draft)

        assert len(checks) == 1
        assert checks[0].law_exists is True
        assert checks[0].article_exists is True
        assert checks[0].pcode == "A0030055"
        assert "書面之行政處分" in (checks[0].actual_content or "")
        assert checks[0].confidence == 1.0

    @patch("src.knowledge.realtime_lookup._request_with_retry")
    def test_verify_nonexistent_law(self, mock_req):
        """驗證不存在的法規。"""
        mock_resp = MagicMock()
        mock_resp.content = _make_law_json(SAMPLE_LAWS)
        mock_req.return_value = mock_resp

        v = LawVerifier()
        draft = "依據政府資訊安全管理辦法辦理。"
        checks = v.verify_citations(draft)

        assert len(checks) == 1
        assert checks[0].law_exists is False
        assert checks[0].confidence == 0.0

    @patch("src.knowledge.realtime_lookup._request_with_retry")
    def test_verify_article_number_out_of_range(self, mock_req):
        """法規存在但條文號超出範圍。"""
        mock_resp = MagicMock()
        mock_resp.content = _make_law_json(SAMPLE_LAWS)
        mock_req.return_value = mock_resp

        v = LawVerifier()
        draft = "依據空氣污染防制法第999條辦理。"
        checks = v.verify_citations(draft)

        assert len(checks) == 1
        assert checks[0].law_exists is True
        assert checks[0].article_exists is False
        assert checks[0].confidence == 0.0

    @patch("src.knowledge.realtime_lookup._request_with_retry")
    def test_fuzzy_match(self, mock_req):
        """模糊比對法規名稱（包含關係）。"""
        mock_resp = MagicMock()
        mock_resp.content = _make_law_json(SAMPLE_LAWS)
        mock_req.return_value = mock_resp

        v = LawVerifier()
        # 「資通安全管理法」在快取中存在，但用「資安管理法」搜尋
        # 直接測試 _fuzzy_match
        v._ensure_cache()
        best, ratio = v._fuzzy_match("資通安全管理法", LawVerifier._cache.data.keys())
        assert best == "資通安全管理法"
        assert ratio >= 0.75

    @patch("src.knowledge.realtime_lookup._request_with_retry")
    def test_cache_reuse(self, mock_req):
        """確認快取重用（不重複下載）。"""
        mock_resp = MagicMock()
        mock_resp.content = _make_law_json(SAMPLE_LAWS)
        mock_req.return_value = mock_resp

        v = LawVerifier()
        v.verify_citations("依據行政程序法辦理。")
        v.verify_citations("依據空氣污染防制法辦理。")

        # 只應呼叫一次 API
        assert mock_req.call_count == 1

    @patch("src.knowledge.realtime_lookup._request_with_retry")
    def test_network_failure_graceful(self, mock_req):
        """網路失敗時拋出例外（由呼叫端捕獲）。"""
        import requests
        mock_req.side_effect = requests.ConnectionError("No network")

        v = LawVerifier()
        with pytest.raises(requests.ConnectionError):
            v.verify_citations("依據行政程序法辦理。")

    @patch("src.knowledge.realtime_lookup._request_with_retry")
    def test_verify_law_without_article(self, mock_req):
        """引用法規但不指定條文。"""
        mock_resp = MagicMock()
        mock_resp.content = _make_law_json(SAMPLE_LAWS)
        mock_req.return_value = mock_resp

        v = LawVerifier()
        draft = "依據行政程序法辦理。"
        checks = v.verify_citations(draft)

        assert len(checks) == 1
        assert checks[0].law_exists is True
        assert checks[0].article_exists is None
        assert checks[0].confidence == 1.0


# ===========================================================================
# TestRecentPolicyFetcher
# ===========================================================================

class TestRecentPolicyFetcher:

    @patch("src.knowledge.realtime_lookup._request_with_retry")
    def test_fetch_recent(self, mock_req):
        """mock gazette XML 回傳。"""
        mock_resp = MagicMock()
        mock_resp.content = _make_gazette_xml(SAMPLE_GAZETTE_RECORDS)
        mock_req.return_value = mock_resp

        f = RecentPolicyFetcher()
        result = f.fetch_recent_policies("空氣污染", days=3)

        assert "空氣污染防制法" in result
        assert "行政院環境保護署" in result

    @patch("src.knowledge.realtime_lookup._request_with_retry")
    def test_filter_relevance(self, mock_req):
        """相關性過濾。"""
        mock_resp = MagicMock()
        mock_resp.content = _make_gazette_xml(SAMPLE_GAZETTE_RECORDS)
        mock_req.return_value = mock_resp

        f = RecentPolicyFetcher()
        result = f.fetch_recent_policies("數位轉型", days=3)

        assert "數位轉型" in result
        # 不相關的條目不應出現在最前面
        assert "空氣污染" not in result or result.index("數位轉型") < result.index("空氣污染")

    @patch("src.knowledge.realtime_lookup._request_with_retry")
    def test_network_failure_graceful(self, mock_req):
        """網路失敗時回傳空字串。"""
        import requests
        mock_req.side_effect = requests.ConnectionError("No network")

        f = RecentPolicyFetcher()
        result = f.fetch_recent_policies("測試", days=3)
        assert result == ""

    @patch("src.knowledge.realtime_lookup._request_with_retry")
    def test_cache_reuse(self, mock_req):
        """確認快取重用。"""
        mock_resp = MagicMock()
        mock_resp.content = _make_gazette_xml(SAMPLE_GAZETTE_RECORDS)
        mock_req.return_value = mock_resp

        f = RecentPolicyFetcher()
        f.fetch_recent_policies("測試1", days=3)
        f.fetch_recent_policies("測試2", days=3)

        assert mock_req.call_count == 1

    @patch("src.knowledge.realtime_lookup._request_with_retry")
    def test_empty_query(self, mock_req):
        """空查詢回傳前 10 筆。"""
        mock_resp = MagicMock()
        mock_resp.content = _make_gazette_xml(SAMPLE_GAZETTE_RECORDS)
        mock_req.return_value = mock_resp

        f = RecentPolicyFetcher()
        result = f.fetch_recent_policies("", days=3)
        assert result  # 應回傳內容


# ===========================================================================
# TestFormatVerificationResults
# ===========================================================================

class TestFormatVerificationResults:

    def test_format_verified(self):
        """驗證通過的格式。"""
        checks = [
            CitationCheck(
                citation=Citation("行政程序法", "100", "依據行政程序法第100條", "第 1 行"),
                law_exists=True,
                article_exists=True,
                actual_content="書面之行政處分自送達相對人及已知之利害關係人起。",
                pcode="A0030055",
                confidence=1.0,
            )
        ]
        text = format_verification_results(checks)
        assert "✅" in text
        assert "行政程序法" in text
        assert "A0030055" in text

    def test_format_nonexistent(self):
        """不存在的法規格式。"""
        checks = [
            CitationCheck(
                citation=Citation("政府資訊安全管理辦法", None, "依據政府資訊安全管理辦法", "第 1 行"),
                law_exists=False,
                article_exists=None,
                actual_content=None,
                pcode=None,
                confidence=0.0,
                closest_match="資通安全管理法",
            )
        ]
        text = format_verification_results(checks)
        assert "❌" in text
        assert "查無" in text
        assert "資通安全管理法" in text

    def test_format_empty(self):
        """空結果。"""
        assert format_verification_results([]) == ""


# ===========================================================================
# TestFactCheckerWithVerifier
# ===========================================================================

class TestFactCheckerWithVerifier:

    @patch("src.knowledge.realtime_lookup._request_with_retry")
    def test_verified_citation_in_prompt(self, mock_req):
        """驗證結果有被包含在 prompt 中。"""
        mock_resp = MagicMock()
        mock_resp.content = _make_law_json(SAMPLE_LAWS)
        mock_req.return_value = mock_resp

        from src.agents.fact_checker import FactChecker

        mock_llm = MagicMock()
        mock_llm.generate.return_value = '{"issues": [], "score": 0.9}'

        verifier = LawVerifier()
        checker = FactChecker(mock_llm, law_verifier=verifier)
        checker.check("依據行政程序法第100條辦理。")

        # 確認 LLM prompt 包含驗證結果
        call_args = mock_llm.generate.call_args
        prompt = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
        assert "Real-Time Verification Results" in prompt
        assert "行政程序法" in prompt
        assert "✅" in prompt

    def test_fallback_without_verifier(self):
        """無驗證器時的降級行為。"""
        from src.agents.fact_checker import FactChecker

        mock_llm = MagicMock()
        mock_llm.generate.return_value = '{"issues": [], "score": 0.9}'

        checker = FactChecker(mock_llm, law_verifier=None)
        checker.check("依據行政程序法第100條辦理。")

        # 確認 prompt 中有降級訊息
        call_args = mock_llm.generate.call_args
        prompt = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
        assert "即時驗證不可用" in prompt


# ===========================================================================
# TestComplianceCheckerWithFetcher
# ===========================================================================

class TestComplianceCheckerWithFetcher:

    @patch("src.knowledge.realtime_lookup._request_with_retry")
    def test_realtime_policy_in_context(self, mock_req):
        """即時政策有被包含在 policy context 中。"""
        mock_resp = MagicMock()
        mock_resp.content = _make_gazette_xml(SAMPLE_GAZETTE_RECORDS)
        mock_req.return_value = mock_resp

        from src.agents.compliance_checker import ComplianceChecker

        mock_llm = MagicMock()
        mock_llm.generate.return_value = '{"issues": [], "score": 0.9, "confidence": 0.8}'

        fetcher = RecentPolicyFetcher()
        checker = ComplianceChecker(mock_llm, kb_manager=None, policy_fetcher=fetcher)

        draft = "### 主旨\n關於空氣污染防制一案。\n### 說明\n依據相關規定辦理。"
        checker.check(draft)

        call_args = mock_llm.generate.call_args
        prompt = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
        assert "最近行政院公報" in prompt or "空氣污染" in prompt

    def test_fallback_without_fetcher(self):
        """無 fetcher 時原有行為不變。"""
        from src.agents.compliance_checker import ComplianceChecker

        mock_llm = MagicMock()
        mock_llm.generate.return_value = '{"issues": [], "score": 0.9, "confidence": 0.8}'

        checker = ComplianceChecker(mock_llm, kb_manager=None, policy_fetcher=None)
        result = checker.check("### 主旨\n測試主旨。\n### 說明\n測試說明。")

        assert result.agent_name == "Compliance Checker"


# ===========================================================================
# TestSSLVerificationEnabled (GOV-23)
# ===========================================================================

class TestSSLVerificationEnabled:
    """確認 SSL 驗證已啟用，不再繞過政府 API 的 SSL 驗證。"""

    def test_no_global_urllib3_warning_suppression(self):
        """模組不應有全域 urllib3 InsecureRequestWarning 抑制。"""
        import urllib3
        # 重新載入模組確認 disable_warnings 未被呼叫
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            # 確認 InsecureRequestWarning 過濾器未被設定為 ignore
            active_filters = [
                f for f in warnings.filters
                if f[2] is urllib3.exceptions.InsecureRequestWarning
                and f[0] == "ignore"
            ]
            assert len(active_filters) == 0, (
                "urllib3 InsecureRequestWarning 不應被全域抑制"
            )

    @patch("src.knowledge.realtime_lookup.requests.get")
    def test_request_with_retry_uses_ssl_verification(self, mock_get):
        """_request_with_retry 應對所有 URL（含政府 API）啟用 SSL 驗證。"""
        from src.knowledge.realtime_lookup import _request_with_retry

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        _request_with_retry("https://law.moj.gov.tw/api/Ch/Law/json")

        # 確認 requests.get 被呼叫時沒有 verify=False
        call_kwargs = mock_get.call_args
        verify_value = call_kwargs.kwargs.get("verify", True)
        assert verify_value is not False, (
            "對政府 API 的請求不應使用 verify=False"
        )

    @patch("src.knowledge.realtime_lookup.requests.get")
    def test_gazette_api_uses_ssl_verification(self, mock_get):
        """公報 API 也應啟用 SSL 驗證。"""
        from src.knowledge.realtime_lookup import _request_with_retry

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        _request_with_retry("https://gazette.nat.gov.tw/egFront/OpenData/downloadXML.jsp")

        call_kwargs = mock_get.call_args
        verify_value = call_kwargs.kwargs.get("verify", True)
        assert verify_value is not False, (
            "對公報 API 的請求不應使用 verify=False"
        )

    def test_no_gov_ssl_domains_bypass_in_realtime_lookup(self):
        """realtime_lookup 模組不應包含 SSL 繞過域名清單。"""
        import src.knowledge.realtime_lookup as mod
        assert not hasattr(mod, "_GOV_SSL_DOMAINS"), (
            "realtime_lookup 不應有 _GOV_SSL_DOMAINS 域名繞過清單"
        )

    def test_no_gov_ssl_domains_bypass_in_base_fetcher(self):
        """base fetcher 模組不應包含 SSL 繞過域名清單。"""
        import src.knowledge.fetchers.base as mod
        assert not hasattr(mod, "_GOV_SSL_DOMAINS"), (
            "base fetcher 不應有 _GOV_SSL_DOMAINS 域名繞過清單"
        )

    def test_base_fetcher_request_no_verify_false(self):
        """BaseFetcher._request_with_retry 不應對任何 URL 設定 verify=False。"""
        from src.knowledge.fetchers.base import BaseFetcher

        class _StubFetcher(BaseFetcher):
            def fetch(self):
                return []
            def name(self):
                return "stub"

        fetcher = _StubFetcher(output_dir=__import__("pathlib").Path("/tmp"), rate_limit=0.0)

        with patch("src.knowledge.fetchers.base.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            fetcher._request_with_retry(
                "get",
                "https://law.moj.gov.tw/api/Ch/Law/json",
                timeout=10,
            )

            call_kwargs = mock_get.call_args
            verify_value = call_kwargs.kwargs.get("verify", True)
            assert verify_value is not False, (
                "BaseFetcher 對政府 API 的請求不應使用 verify=False"
            )


# ===========================================================================
# TestXXEPrevention (GOV-24)
# ===========================================================================

class TestXXEPrevention:
    """確認 XML 解析使用 defusedxml，可防禦 XXE 攻擊。"""

    def test_realtime_lookup_uses_defusedxml(self):
        """realtime_lookup 模組應使用 defusedxml 而非標準 xml.etree.ElementTree。"""
        import src.knowledge.realtime_lookup as mod
        import inspect
        source = inspect.getsource(mod)
        assert "defusedxml" in source, (
            "realtime_lookup 應使用 defusedxml.ElementTree"
        )
        assert "import xml.etree.ElementTree" not in source, (
            "realtime_lookup 不應使用標準 xml.etree.ElementTree"
        )

    def test_gazette_fetcher_uses_defusedxml(self):
        """gazette_fetcher 模組應使用 defusedxml。"""
        import src.knowledge.fetchers.gazette_fetcher as mod
        import inspect
        source = inspect.getsource(mod)
        assert "defusedxml" in source
        assert "import xml.etree.ElementTree" not in source

    def test_law_fetcher_uses_defusedxml(self):
        """law_fetcher 模組應使用 defusedxml。"""
        import src.knowledge.fetchers.law_fetcher as mod
        import inspect
        source = inspect.getsource(mod)
        assert "defusedxml" in source
        assert "import xml.etree.ElementTree" not in source

    def test_npa_fetcher_uses_defusedxml(self):
        """npa_fetcher 模組應使用 defusedxml。"""
        import src.knowledge.fetchers.npa_fetcher as mod
        import inspect
        source = inspect.getsource(mod)
        assert "defusedxml" in source
        assert "import xml.etree.ElementTree" not in source

    def test_xxe_payload_rejected_by_parse_xml(self):
        """RecentPolicyFetcher._parse_xml 應拒絕含 XXE 的 XML。"""
        xxe_payload = b"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<Records>
  <Record>
    <Title>&xxe;</Title>
  </Record>
</Records>"""
        from defusedxml.common import EntitiesForbidden
        with pytest.raises(EntitiesForbidden):
            RecentPolicyFetcher._parse_xml(xxe_payload)

    def test_safe_xml_still_parsed(self):
        """正常 XML 仍應正確解析。"""
        safe_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<Records>
  <Record>
    <Title>Test Title</Title>
    <Category>Test</Category>
  </Record>
</Records>"""
        records = RecentPolicyFetcher._parse_xml(safe_xml)
        assert len(records) == 1
        assert records[0]["Title"] == "Test Title"
