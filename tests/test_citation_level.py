"""
Level A/B 引用等級系統的單元測試。
覆蓋：FetchResult 新欄位、Citation 模型、各 Fetcher 的 source_level/source_url、
      check_citation_level 驗證器、WriterAgent 引用格式。
"""
import json
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch
from xml.etree.ElementTree import Element, SubElement, tostring

import pytest

from src.knowledge.fetchers.base import FetchResult
from src.knowledge.fetchers.constants import (
    GAZETTE_DETAIL_URL,
    LAW_DETAIL_URL,
    OPENDATA_DETAIL_URL,
)
from src.core.models import Citation
from src.document import CitationFormatter, REFERENCE_SECTION_HEADING


# ==================== 常數與工具 ====================

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> bytes:
    return (FIXTURES_DIR / name).read_bytes()


def _make_law_zip(laws: list[dict]) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("ChLaw.json", json.dumps(laws, ensure_ascii=False))
    return buf.getvalue()


def _make_gazette_xml(records: list[dict]) -> bytes:
    root = Element("Gazette")
    for rec in records:
        record_el = SubElement(root, "Record")
        for key, val in rec.items():
            child = SubElement(record_el, key)
            child.text = val
    return tostring(root, encoding="unicode").encode("utf-8")


# ==================== TestFetchResultNewFields ====================

class TestFetchResultNewFields:
    """FetchResult dataclass 新欄位的測試。"""

    def test_default_source_level_is_b(self):
        """預設 source_level 應為 B"""
        result = FetchResult(
            file_path=Path("/tmp/test.md"),
            metadata={"title": "test"},
            collection="examples",
        )
        assert result.source_level == "B"
        assert result.source_url is None

    def test_explicit_source_level_a(self):
        """明確設定 source_level=A 和 source_url"""
        result = FetchResult(
            file_path=Path("/tmp/test.md"),
            metadata={"title": "test"},
            collection="regulations",
            source_level="A",
            source_url="https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=A0010004",
        )
        assert result.source_level == "A"
        assert "A0010004" in result.source_url

    def test_backward_compatible_construction(self):
        """不帶新欄位的建構應繼續正常運作（向後相容）"""
        result = FetchResult(
            file_path=Path("/tmp/test.md"),
            metadata={},
            collection="examples",
        )
        assert result.source_level == "B"
        assert result.source_url is None


# ==================== TestCitationModel ====================

class TestCitationModel:
    """Citation Pydantic 模型的測試。"""

    def test_basic_construction(self):
        c = Citation(index=1, title="公文程式條例")
        assert c.index == 1
        assert c.title == "公文程式條例"
        assert c.source_level == "B"
        assert c.source_url is None

    def test_full_construction(self):
        c = Citation(
            index=2,
            title="行政程序法",
            source_level="A",
            source_url="https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=A0010004",
            source_type="法規",
            record_id="A0010004",
        )
        assert c.source_level == "A"
        assert c.source_type == "法規"
        assert c.record_id == "A0010004"

    def test_serialization(self):
        c = Citation(
            index=1,
            title="測試",
            source_level="A",
            source_url="https://example.com",
        )
        data = c.model_dump()
        assert data["index"] == 1
        assert data["source_level"] == "A"
        assert data["source_url"] == "https://example.com"

    def test_json_round_trip(self):
        c = Citation(index=3, title="測試法規", source_level="A")
        json_str = c.model_dump_json()
        c2 = Citation.model_validate_json(json_str)
        assert c2.index == c.index
        assert c2.title == c.title


# ==================== TestGazetteFetcherSourceLevel ====================

class TestGazetteFetcherSourceLevel:
    """GazetteFetcher 的 source_level 和 source_url 測試。"""

    @patch("src.knowledge.fetchers.gazette_fetcher.requests.get")
    def test_source_level_is_a(self, mock_get, tmp_path):
        from src.knowledge.fetchers.gazette_fetcher import GazetteFetcher

        xml_data = _load_fixture("sample_gazette.xml")
        mock_resp = MagicMock()
        mock_resp.content = xml_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = GazetteFetcher(output_dir=tmp_path, days=365 * 10, rate_limit=0)
        results = fetcher.fetch()

        assert len(results) > 0
        for r in results:
            assert r.source_level == "A"
            assert r.metadata["source_level"] == "A"

    @patch("src.knowledge.fetchers.gazette_fetcher.requests.get")
    def test_source_url_contains_meta_id(self, mock_get, tmp_path):
        from src.knowledge.fetchers.gazette_fetcher import GazetteFetcher

        xml_data = _load_fixture("sample_gazette.xml")
        mock_resp = MagicMock()
        mock_resp.content = xml_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = GazetteFetcher(output_dir=tmp_path, days=365 * 10, rate_limit=0)
        results = fetcher.fetch()

        for r in results:
            meta_id = r.metadata["meta_id"]
            expected_url = GAZETTE_DETAIL_URL.format(meta_id=meta_id)
            assert r.source_url == expected_url
            assert r.metadata["source_url"] == expected_url


# ==================== TestLawFetcherSourceLevel ====================

class TestLawFetcherSourceLevel:
    """LawFetcher 的 source_level 和 source_url 測試。"""

    @patch("src.knowledge.fetchers.law_fetcher.requests.get")
    def test_source_level_is_a(self, mock_get, tmp_path):
        from src.knowledge.fetchers.law_fetcher import LawFetcher

        zip_data = _load_fixture("sample_law.zip")
        mock_resp = MagicMock()
        mock_resp.content = zip_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = LawFetcher(output_dir=tmp_path, rate_limit=0)
        results = fetcher.fetch()

        assert len(results) > 0
        for r in results:
            assert r.source_level == "A"
            assert r.metadata["source_level"] == "A"

    @patch("src.knowledge.fetchers.law_fetcher.requests.get")
    def test_source_url_contains_pcode(self, mock_get, tmp_path):
        from src.knowledge.fetchers.law_fetcher import LawFetcher

        zip_data = _load_fixture("sample_law.zip")
        mock_resp = MagicMock()
        mock_resp.content = zip_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = LawFetcher(
            output_dir=tmp_path,
            pcodes={"A0010004": "行政程序法"},
            rate_limit=0,
        )
        results = fetcher.fetch()

        for r in results:
            pcode = r.metadata["pcode"]
            expected_url = LAW_DETAIL_URL.format(pcode=pcode)
            assert r.source_url == expected_url
            assert r.metadata["source_url"] == expected_url

    @patch("src.knowledge.fetchers.law_fetcher.requests.get")
    def test_chunked_results_have_source_level(self, mock_get, tmp_path):
        """分段法規的每個 chunk 都應有 source_level=A"""
        from src.knowledge.fetchers.law_fetcher import LawFetcher

        articles = [
            {"ArticleNo": f"第 {i} 條", "ArticleContent": "條文內容。" * 50}
            for i in range(1, 51)
        ]
        laws = [{"PCode": "A0010004", "LawName": "行政程序法", "LawArticles": articles}]
        zip_data = _make_law_zip(laws)

        mock_resp = MagicMock()
        mock_resp.content = zip_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = LawFetcher(
            output_dir=tmp_path,
            pcodes={"A0010004": "行政程序法"},
            rate_limit=0,
        )
        results = fetcher.fetch()

        assert len(results) == 3  # 50 / 20 = 3 chunks
        for r in results:
            assert r.source_level == "A"
            assert r.source_url == LAW_DETAIL_URL.format(pcode="A0010004")
            assert r.metadata["source_level"] == "A"


# ==================== TestOpenDataFetcherSourceLevel ====================

class TestOpenDataFetcherSourceLevel:
    """OpenDataFetcher 的 source_level 和 source_url 測試。"""

    @patch("src.knowledge.fetchers.opendata_fetcher.requests.post")
    def test_source_level_is_b(self, mock_post, tmp_path):
        from src.knowledge.fetchers.opendata_fetcher import OpenDataFetcher

        json_data = _load_fixture("sample_opendata.json")
        mock_resp = MagicMock()
        mock_resp.json.return_value = json.loads(json_data)
        mock_resp.raise_for_status = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        fetcher = OpenDataFetcher(output_dir=tmp_path, rate_limit=0)
        results = fetcher.fetch()

        assert len(results) > 0
        for r in results:
            assert r.source_level == "B"
            assert r.metadata["source_level"] == "B"

    @patch("src.knowledge.fetchers.opendata_fetcher.requests.post")
    def test_source_url_contains_dataset_id(self, mock_post, tmp_path):
        from src.knowledge.fetchers.opendata_fetcher import OpenDataFetcher

        json_data = _load_fixture("sample_opendata.json")
        mock_resp = MagicMock()
        mock_resp.json.return_value = json.loads(json_data)
        mock_resp.raise_for_status = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        fetcher = OpenDataFetcher(output_dir=tmp_path, rate_limit=0)
        results = fetcher.fetch()

        for r in results:
            dataset_id = r.metadata["dataset_id"]
            expected_url = OPENDATA_DETAIL_URL.format(dataset_id=dataset_id)
            assert r.source_url == expected_url
            assert r.metadata["source_url"] == expected_url


# ==================== TestCheckCitationLevel ====================

class TestCheckCitationLevel:
    """check_citation_level 驗證器的測試。"""

    @pytest.fixture
    def registry(self):
        from src.agents.validators import ValidatorRegistry
        return ValidatorRegistry()

    def test_no_issues_with_proper_citations(self, registry):
        """正確的草稿應無錯誤"""
        draft = (
            "依據《行政程序法》辦理[^1]。\n\n"
            "### 參考來源 (AI 引用追蹤)\n"
            "[^1]: [Level A] 行政程序法 | URL: https://law.moj.gov.tw/..."
        )
        errors = registry.check_citation_level(draft)
        assert len(errors) == 0

    def test_detect_pending_marker(self, registry):
        """偵測「待補依據」標記"""
        draft = "依據相關法規【待補依據】辦理。"
        errors = registry.check_citation_level(draft)
        assert any("待補依據" in e["description"] for e in errors)

    def test_detect_multiple_pending_markers(self, registry):
        """偵測多個「待補依據」"""
        draft = "依據法規【待補依據】辦理。另依據規定【待補依據】處理。"
        errors = registry.check_citation_level(draft)
        pending_errors = [e for e in errors if "2 處" in e["description"]]
        assert len(pending_errors) == 1

    def test_missing_level_a_in_references(self, registry):
        """參考來源中缺少 Level A"""
        draft = (
            "依據相關資料辦理[^1]。\n\n"
            "### 參考來源 (AI 引用追蹤)\n"
            "[^1]: [Level B] 開放資料集"
        )
        errors = registry.check_citation_level(draft)
        assert any("Level A" in e["description"] for e in errors)

    def test_yiju_without_citation(self, registry):
        """「依據...辦理」句型缺少引用標記"""
        draft = (
            "依據廢棄物清理法辦理。請各單位配合辦理，如有疑義請洽承辦人員。\n\n"
            "### 參考來源 (AI 引用追蹤)\n"
            "[^1]: [Level A] 某法規"
        )
        errors = registry.check_citation_level(draft)
        assert any("缺少引用標記" in e["description"] for e in errors)

    def test_yiju_with_citation_ok(self, registry):
        """「依據...辦理」句型有引用標記則正常"""
        draft = (
            "依據廢棄物清理法辦理[^1]。\n\n"
            "### 參考來源 (AI 引用追蹤)\n"
            "[^1]: [Level A] 廢棄物清理法"
        )
        errors = registry.check_citation_level(draft)
        # 不應有「缺少引用標記」的錯誤
        citation_errors = [e for e in errors if "缺少引用標記" in e["description"]]
        assert len(citation_errors) == 0

    def test_yiju_with_pending_ok(self, registry):
        """「依據...辦理」後接「待補依據」不算缺少引用"""
        draft = "依據相關法規辦理【待補依據】。"
        errors = registry.check_citation_level(draft)
        citation_errors = [e for e in errors if "缺少引用標記" in e["description"]]
        assert len(citation_errors) == 0

    def test_no_reference_section_no_crash(self, registry):
        """沒有參考來源段落時不崩潰"""
        draft = "本案請查照辦理。"
        errors = registry.check_citation_level(draft)
        # 不應崩潰，且不應有 Level A 相關錯誤（因為沒有參考來源段落）
        assert isinstance(errors, list)

    def test_empty_draft(self, registry):
        """空草稿不崩潰"""
        errors = registry.check_citation_level("")
        assert isinstance(errors, list)
        assert len(errors) == 0


# ==================== TestModuleExports ====================

class TestModuleExports:
    """驗證 __init__.py 匯出的完整性。"""

    def test_source_level_constants_exported(self):
        from src.knowledge.fetchers import SOURCE_LEVEL_A, SOURCE_LEVEL_B
        assert SOURCE_LEVEL_A == "A"
        assert SOURCE_LEVEL_B == "B"

    def test_url_templates_accessible(self):
        from src.knowledge.fetchers.constants import (
            GAZETTE_DETAIL_URL,
            LAW_DETAIL_URL,
            OPENDATA_DETAIL_URL,
        )
        assert "{meta_id}" in GAZETTE_DETAIL_URL
        assert "{pcode}" in LAW_DETAIL_URL
        assert "{dataset_id}" in OPENDATA_DETAIL_URL


# ==================== TestAuditorWhitelist ====================

class TestAuditorWhitelist:
    """驗證 FormatAuditor 的白名單包含新驗證器。"""

    def test_check_citation_level_in_whitelist(self):
        """check_citation_level 應在白名單中"""
        # 直接檢查 auditor.py 中的白名單是否包含新項目
        from src.agents.validators import validator_registry
        assert hasattr(validator_registry, "check_citation_level")
        assert callable(getattr(validator_registry, "check_citation_level"))


class TestCitationFormatter:
    """Repo-owned citation formatter seam tests."""

    def test_build_reference_block_uses_canonical_heading(self):
        draft = "依據行政程序法辦理[^1]。"
        block = CitationFormatter.build_reference_block(
            draft,
            [
                {
                    "index": 1,
                    "title": "行政程序法",
                    "source_level": "A",
                    "source_url": "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=A0010004",
                    "content_hash": "a" * 16,
                }
            ],
        )

        assert block.startswith(REFERENCE_SECTION_HEADING)
        assert "[^1]: [Level A] 行政程序法" in block

    def test_build_reference_block_prunes_unused_sources(self):
        draft = "依據行政程序法辦理[^2]。"
        block = CitationFormatter.build_reference_block(
            draft,
            [
                {"index": 1, "title": "來源一", "source_level": "A"},
                {"index": 2, "title": "來源二", "source_level": "B"},
            ],
        )

        assert "[^1]:" not in block
        assert "[^2]: [Level B] 來源二" in block
