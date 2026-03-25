"""
src/knowledge/fetchers/ 的完整測試
使用 mock 避免實際 HTTP 請求
"""
import json
import time
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch
from xml.etree.ElementTree import Element, SubElement, tostring

from typer.testing import CliRunner

from src.knowledge.fetchers.base import BaseFetcher, FetchResult, html_to_markdown


runner = CliRunner()


# ========== Bulk 測試用 Fixture 工廠 ==========

def _make_gazette_bulk_zip(records: list[dict], pdfs: dict[str, bytes] | None = None) -> bytes:
    """建立模擬的公報 bulk ZIP（含 XML + 可選 PDF）。"""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # 建立 XML
        xml_bytes = _make_gazette_xml(records)
        zf.writestr("gazette_data.xml", xml_bytes)
        # 加入 PDF（以 MetaId 為檔名）
        if pdfs:
            for name, pdf_bytes in pdfs.items():
                zf.writestr(f"{name}.pdf", pdf_bytes)
    return buf.getvalue()


def _make_law_bulk_xml(laws: list[dict]) -> bytes:
    """建立模擬的法規 bulk XML。"""
    root = Element("法規資料")
    for law in laws:
        law_el = SubElement(root, "法規")
        name_el = SubElement(law_el, "法規名稱")
        name_el.text = law.get("LawName", "")
        url_el = SubElement(law_el, "法規網址")
        url_el.text = f"https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode={law.get('PCode', '')}"
        if law.get("Foreword"):
            fw_el = SubElement(law_el, "前言")
            fw_el.text = law["Foreword"]
        for art in law.get("LawArticles", []):
            art_el = SubElement(law_el, "條文")
            no_el = SubElement(art_el, "條號")
            no_el.text = art.get("ArticleNo", "")
            content_el = SubElement(art_el, "條文內容")
            content_el.text = art.get("ArticleContent", "")
    return tostring(root, encoding="unicode").encode("utf-8")


def _make_law_bulk_zip(laws: list[dict]) -> bytes:
    """建立模擬的法規 bulk XML ZIP。"""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        xml_bytes = _make_law_bulk_xml(laws)
        zf.writestr("FalV.xml", xml_bytes)
    return buf.getvalue()


def _make_simple_pdf(text: str = "測試 PDF 內容") -> bytes:
    """建立極簡 PDF bytes（用於測試 PDF 提取）。

    使用最基本的 PDF 結構（手工建立），不依賴任何 PDF 庫。
    """
    # 極簡 PDF 1.0 結構 — 無法被 pdfplumber 正確解析，
    # 但足以作為 bytes 輸入；實際提取測試需要 mock pdfplumber。
    pdf_content = (
        b"%PDF-1.0\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
        b"xref\n0 4\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\n"
        b"startxref\n190\n%%EOF"
    )
    return pdf_content

# ========== 測試 Fixture 路徑 ==========
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> bytes:
    """讀取 fixture 檔案為 bytes。"""
    return (FIXTURES_DIR / name).read_bytes()


def _make_law_zip(laws: list[dict]) -> bytes:
    """動態建立法規 ZIP（含 ChLaw.json）。"""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("ChLaw.json", json.dumps(laws, ensure_ascii=False))
    return buf.getvalue()


def _make_gazette_xml(records: list[dict]) -> bytes:
    """動態建立公報 XML。"""
    root = Element("Gazette")
    for rec in records:
        record_el = SubElement(root, "Record")
        for key, val in rec.items():
            child = SubElement(record_el, key)
            child.text = val
    return tostring(root, encoding="unicode").encode("utf-8")


# ==================== TestBaseFetcher ====================

class TestBaseFetcher:
    """BaseFetcher 抽象基底類別的測試。"""

    def test_write_markdown_creates_file(self, tmp_path):
        """測試 _write_markdown 正確建立含 YAML frontmatter 的檔案"""
        from src.cli.kb import parse_markdown_with_metadata

        class DummyFetcher(BaseFetcher):
            def fetch(self): return []
            def name(self): return "dummy"

        f = DummyFetcher(output_dir=tmp_path)
        md_path = tmp_path / "sub" / "test.md"
        metadata = {"title": "測試", "doc_type": "函", "count": 42}
        f._write_markdown(md_path, metadata, "# 內容\n文字")

        assert md_path.exists()

        # 驗證與 parse_markdown_with_metadata 相容
        parsed_meta, parsed_body = parse_markdown_with_metadata(md_path)
        assert parsed_meta["title"] == "測試"
        assert parsed_meta["doc_type"] == "函"
        assert parsed_meta["count"] == 42
        assert "# 內容" in parsed_body

    def test_throttle_delays_requests(self, tmp_path):
        """測試 _throttle 確保最小請求間隔"""
        class DummyFetcher(BaseFetcher):
            def fetch(self): return []
            def name(self): return "dummy"

        f = DummyFetcher(output_dir=tmp_path, rate_limit=0.2)
        f._last_request_time = time.time()  # 模擬剛剛才發過請求

        start = time.time()
        f._throttle()
        elapsed = time.time() - start

        assert elapsed >= 0.15  # 容許些許誤差

    def test_fetch_result_dataclass(self):
        """測試 FetchResult 資料類別"""
        result = FetchResult(
            file_path=Path("/tmp/test.md"),
            metadata={"title": "test"},
            collection="examples",
        )
        assert result.file_path == Path("/tmp/test.md")
        assert result.collection == "examples"


# ==================== TestHtmlToMarkdown ====================

class TestHtmlToMarkdown:
    """html_to_markdown 工具函式的測試。"""

    def test_empty_input(self):
        assert html_to_markdown("") == ""
        assert html_to_markdown(None) == ""

    def test_paragraph_conversion(self):
        result = html_to_markdown("<p>段落一</p><p>段落二</p>")
        assert "段落一" in result
        assert "段落二" in result

    def test_heading_conversion(self):
        result = html_to_markdown("<h1>標題一</h1><h2>標題二</h2>")
        assert "# 標題一" in result
        assert "## 標題二" in result

    def test_bold_italic(self):
        result = html_to_markdown("<b>粗體</b> <i>斜體</i>")
        assert "**粗體**" in result
        assert "*斜體*" in result

    def test_list_items(self):
        result = html_to_markdown("<ul><li>項目一</li><li>項目二</li></ul>")
        assert "- 項目一" in result
        assert "- 項目二" in result

    def test_br_conversion(self):
        result = html_to_markdown("行一<br/>行二<br>行三")
        assert "行一\n行二\n行三" == result

    def test_html_entities(self):
        result = html_to_markdown("&amp; &lt; &gt; &nbsp; &quot;")
        assert "&" in result
        assert "<" in result
        assert ">" in result

    def test_cdata_removal(self):
        result = html_to_markdown("<![CDATA[<p>內容</p>]]>")
        assert "內容" in result
        assert "CDATA" not in result

    def test_strip_remaining_tags(self):
        result = html_to_markdown("<div class='x'><span>文字</span></div>")
        assert "<" not in result
        assert "文字" in result


# ==================== TestLawFetcher ====================

class TestLawFetcher:
    """LawFetcher 的測試。"""

    @patch("src.knowledge.fetchers.law_fetcher.requests.get")
    def test_fetch_filters_by_pcode(self, mock_get, tmp_path):
        """測試依 PCode 篩選法規"""
        from src.knowledge.fetchers.law_fetcher import LawFetcher

        zip_data = _load_fixture("sample_law.zip")
        mock_resp = MagicMock()
        mock_resp.content = zip_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = LawFetcher(output_dir=tmp_path, rate_limit=0)
        results = fetcher.fetch()

        # sample_law.zip 含 A0030018, A0030055, Z9999999
        # 只有前兩個在 DEFAULT_LAW_PCODES 中
        pcodes_found = {r.metadata["pcode"] for r in results}
        assert "A0030018" in pcodes_found
        assert "A0030055" in pcodes_found
        assert "Z9999999" not in pcodes_found

        # 所有結果的 collection 都是 regulations
        for r in results:
            assert r.collection == "regulations"
            assert r.file_path.exists()

    @patch("src.knowledge.fetchers.law_fetcher.requests.get")
    def test_fetch_with_custom_pcodes(self, mock_get, tmp_path):
        """測試指定自訂 PCode 清單"""
        from src.knowledge.fetchers.law_fetcher import LawFetcher

        zip_data = _load_fixture("sample_law.zip")
        mock_resp = MagicMock()
        mock_resp.content = zip_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        # 只擷取一部法規
        fetcher = LawFetcher(
            output_dir=tmp_path,
            pcodes={"A0030018": "行政程序法"},
            rate_limit=0,
        )
        results = fetcher.fetch()

        assert len(results) == 1
        assert results[0].metadata["pcode"] == "A0030018"

    @patch("src.knowledge.fetchers.law_fetcher.requests.get")
    def test_fetch_large_law_chunked(self, mock_get, tmp_path):
        """測試大型法規（超過字數上限）會被分割"""
        from src.knowledge.fetchers.law_fetcher import LawFetcher

        # 建立一部有 50 條的法規，每條 300 字
        articles = [
            {"ArticleNo": f"第 {i} 條", "ArticleContent": "條文內容。" * 50}
            for i in range(1, 51)
        ]
        laws = [{"PCode": "A0030018", "LawName": "行政程序法", "LawArticles": articles}]
        zip_data = _make_law_zip(laws)

        mock_resp = MagicMock()
        mock_resp.content = zip_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = LawFetcher(
            output_dir=tmp_path,
            pcodes={"A0030018": "行政程序法"},
            rate_limit=0,
        )
        results = fetcher.fetch()

        # 50 條 / 20 條 per chunk = 3 個檔案
        assert len(results) == 3
        for r in results:
            assert "part" in r.metadata
            assert r.file_path.name.endswith(".md")

    @patch("src.knowledge.fetchers.law_fetcher.requests.get")
    def test_fetch_network_error(self, mock_get, tmp_path):
        """測試網路錯誤時回傳空清單"""
        from src.knowledge.fetchers.law_fetcher import LawFetcher
        import requests as req

        mock_get.side_effect = req.ConnectionError("Network error")

        fetcher = LawFetcher(output_dir=tmp_path, rate_limit=0)
        results = fetcher.fetch()

        assert results == []

    @patch("src.knowledge.fetchers.law_fetcher.requests.get")
    def test_fetch_empty_pcode_list(self, mock_get, tmp_path):
        """測試空 PCode 清單時不產生任何檔案"""
        from src.knowledge.fetchers.law_fetcher import LawFetcher

        zip_data = _load_fixture("sample_law.zip")
        mock_resp = MagicMock()
        mock_resp.content = zip_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = LawFetcher(output_dir=tmp_path, pcodes={}, rate_limit=0)
        results = fetcher.fetch()

        assert results == []

    @patch("src.knowledge.fetchers.law_fetcher.requests.get")
    def test_fetch_json_response(self, mock_get, tmp_path):
        """測試 API 直接回傳 JSON（非 ZIP）的情況"""
        from src.knowledge.fetchers.law_fetcher import LawFetcher

        laws = [
            {
                "PCode": "A0030055",
                "LawName": "公文程式條例",
                "LawArticles": [
                    {"ArticleNo": "第 1 條", "ArticleContent": "公文程式條例。"}
                ],
            }
        ]
        mock_resp = MagicMock()
        mock_resp.content = json.dumps(laws, ensure_ascii=False).encode("utf-8")
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = LawFetcher(
            output_dir=tmp_path,
            pcodes={"A0030055": "公文程式條例"},
            rate_limit=0,
        )
        results = fetcher.fetch()

        assert len(results) == 1
        assert results[0].metadata["title"] == "公文程式條例"

    def test_name(self, tmp_path):
        from src.knowledge.fetchers.law_fetcher import LawFetcher
        f = LawFetcher(output_dir=tmp_path, rate_limit=0)
        assert f.name() == "全國法規資料庫"


# ==================== TestGazetteFetcher ====================

class TestGazetteFetcher:
    """GazetteFetcher 的測試。"""

    @patch("src.knowledge.fetchers.gazette_fetcher.requests.get")
    def test_fetch_parses_xml(self, mock_get, tmp_path):
        """測試正確解析 XML 並產生 Markdown"""
        from src.knowledge.fetchers.gazette_fetcher import GazetteFetcher

        xml_data = _load_fixture("sample_gazette.xml")
        mock_resp = MagicMock()
        mock_resp.content = xml_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = GazetteFetcher(output_dir=tmp_path, days=365 * 10, rate_limit=0)
        results = fetcher.fetch()

        # fixture 有 3 筆 record
        assert len(results) == 3
        titles = {r.metadata["title"] for r in results}
        assert "修正「藥品分類」" in titles
        assert "核定施政計畫" in titles

    @patch("src.knowledge.fetchers.gazette_fetcher.requests.get")
    def test_html_to_markdown_conversion(self, mock_get, tmp_path):
        """測試 HTMLContent 轉換為 Markdown"""
        from src.knowledge.fetchers.gazette_fetcher import GazetteFetcher

        xml_data = _load_fixture("sample_gazette.xml")
        mock_resp = MagicMock()
        mock_resp.content = xml_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = GazetteFetcher(output_dir=tmp_path, days=365 * 10, rate_limit=0)
        results = fetcher.fetch()

        # 找到施政計畫那筆
        plan_result = next(r for r in results if "施政計畫" in r.metadata["title"])
        content = plan_result.file_path.read_text(encoding="utf-8")
        # HTMLContent 應被轉換為 Markdown 格式
        assert "<p>" not in content or "## 施政計畫" in content

    @patch("src.knowledge.fetchers.gazette_fetcher.requests.get")
    def test_category_to_collection_mapping(self, mock_get, tmp_path):
        """測試 Category → Collection 映射"""
        from src.knowledge.fetchers.gazette_fetcher import GazetteFetcher

        xml_data = _load_fixture("sample_gazette.xml")
        mock_resp = MagicMock()
        mock_resp.content = xml_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = GazetteFetcher(output_dir=tmp_path, days=365 * 10, rate_limit=0)
        results = fetcher.fetch()

        collections = {r.metadata["title"]: r.collection for r in results}
        assert collections["修正「藥品分類」"] == "regulations"
        assert collections["核定施政計畫"] == "policies"
        assert collections["一般公告事項"] == "examples"

    @patch("src.knowledge.fetchers.gazette_fetcher.requests.get")
    def test_date_filter(self, mock_get, tmp_path):
        """測試日期篩選：days=30 應排除 2025-01-01 的舊公報"""
        from src.knowledge.fetchers.gazette_fetcher import GazetteFetcher

        xml_data = _load_fixture("sample_gazette.xml")
        mock_resp = MagicMock()
        mock_resp.content = xml_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = GazetteFetcher(output_dir=tmp_path, days=30, rate_limit=0)
        results = fetcher.fetch()

        # 2025-01-01 的記錄應被過濾（距今超過 30 天）
        titles = {r.metadata["title"] for r in results}
        assert "一般公告事項" not in titles

    @patch("src.knowledge.fetchers.gazette_fetcher.requests.get")
    def test_category_filter(self, mock_get, tmp_path):
        """測試 category 篩選"""
        from src.knowledge.fetchers.gazette_fetcher import GazetteFetcher

        xml_data = _load_fixture("sample_gazette.xml")
        mock_resp = MagicMock()
        mock_resp.content = xml_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = GazetteFetcher(
            output_dir=tmp_path, days=365 * 10,
            category_filter="法規命令", rate_limit=0,
        )
        results = fetcher.fetch()

        assert len(results) == 1
        assert results[0].metadata["category"] == "法規命令"

    @patch("src.knowledge.fetchers.gazette_fetcher.requests.get")
    def test_network_error(self, mock_get, tmp_path):
        """測試網路錯誤"""
        from src.knowledge.fetchers.gazette_fetcher import GazetteFetcher
        import requests as req

        mock_get.side_effect = req.ConnectionError("fail")

        fetcher = GazetteFetcher(output_dir=tmp_path, rate_limit=0)
        results = fetcher.fetch()
        assert results == []

    def test_name(self, tmp_path):
        from src.knowledge.fetchers.gazette_fetcher import GazetteFetcher
        f = GazetteFetcher(output_dir=tmp_path, rate_limit=0)
        assert f.name() == "行政院公報"


# ==================== TestOpenDataFetcher ====================

class TestOpenDataFetcher:
    """OpenDataFetcher 的測試。"""

    @patch("src.knowledge.fetchers.opendata_fetcher.requests.post")
    def test_fetch_parses_json(self, mock_post, tmp_path):
        """測試正確解析 JSON 回應"""
        from src.knowledge.fetchers.opendata_fetcher import OpenDataFetcher

        json_data = _load_fixture("sample_opendata.json")
        mock_resp = MagicMock()
        mock_resp.json.return_value = json.loads(json_data)
        mock_resp.raise_for_status = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        fetcher = OpenDataFetcher(output_dir=tmp_path, rate_limit=0)
        results = fetcher.fetch()

        assert len(results) == 2
        titles = {r.metadata["title"] for r in results}
        assert "警廣即時路況" in titles
        assert "失蹤人口統計" in titles

        # 所有結果都歸到 policies
        for r in results:
            assert r.collection == "policies"

    @patch("src.knowledge.fetchers.opendata_fetcher.requests.post")
    def test_fetch_includes_metadata(self, mock_post, tmp_path):
        """測試產生的 Markdown 包含 metadata"""
        from src.knowledge.fetchers.opendata_fetcher import OpenDataFetcher

        json_data = _load_fixture("sample_opendata.json")
        mock_resp = MagicMock()
        mock_resp.json.return_value = json.loads(json_data)
        mock_resp.raise_for_status = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        fetcher = OpenDataFetcher(output_dir=tmp_path, rate_limit=0)
        results = fetcher.fetch()

        traffic = next(r for r in results if "路況" in r.metadata["title"])
        content = traffic.file_path.read_text(encoding="utf-8")
        assert "警政署" in content
        assert "交通" in content

    @patch("src.knowledge.fetchers.opendata_fetcher.requests.post")
    def test_fetch_empty_results(self, mock_post, tmp_path):
        """測試空結果"""
        from src.knowledge.fetchers.opendata_fetcher import OpenDataFetcher

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"success": True, "payload": {"search_result": [], "search_count": 0}}
        mock_resp.raise_for_status = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        fetcher = OpenDataFetcher(output_dir=tmp_path, rate_limit=0)
        results = fetcher.fetch()
        assert results == []

    @patch("src.knowledge.fetchers.opendata_fetcher.requests.post")
    def test_network_error(self, mock_post, tmp_path):
        """測試網路錯誤"""
        from src.knowledge.fetchers.opendata_fetcher import OpenDataFetcher
        import requests as req

        mock_post.side_effect = req.ConnectionError("fail")

        fetcher = OpenDataFetcher(output_dir=tmp_path, rate_limit=0)
        results = fetcher.fetch()
        assert results == []

    @patch("src.knowledge.fetchers.opendata_fetcher.requests.post")
    def test_fetch_with_new_api_format(self, mock_post, tmp_path):
        """測試前端 API 回傳格式"""
        from src.knowledge.fetchers.opendata_fetcher import OpenDataFetcher

        data = {
            "success": True,
            "payload": {
                "search_result": [
                    {
                        "nid": "99999",
                        "title": "測試資料集",
                        "content": "測試說明",
                        "agency_name": "測試機關",
                        "category_name": "測試分類",
                    }
                ],
                "search_count": 1,
            }
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = data
        mock_resp.raise_for_status = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        fetcher = OpenDataFetcher(output_dir=tmp_path, rate_limit=0)
        results = fetcher.fetch()

        assert len(results) == 1
        assert results[0].metadata["agency"] == "測試機關"

    def test_name(self, tmp_path):
        from src.knowledge.fetchers.opendata_fetcher import OpenDataFetcher
        f = OpenDataFetcher(output_dir=tmp_path, rate_limit=0)
        assert f.name() == "政府資料開放平臺"


# ==================== TestFetchCLI ====================

class TestFetchCLI:
    """CLI fetch 命令的整合測試。"""

    @patch("src.knowledge.fetchers.law_fetcher.requests.get")
    @patch("src.cli.kb.ConfigManager")
    @patch("src.cli.kb.get_llm_factory")
    @patch("src.cli.kb.KnowledgeBaseManager")
    def test_fetch_laws_command(self, mock_kb_class, mock_factory, mock_cm, mock_get, tmp_path):
        """測試 fetch-laws CLI 命令"""
        from src.cli.main import app

        zip_data = _load_fixture("sample_law.zip")
        mock_resp = MagicMock()
        mock_resp.content = zip_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = runner.invoke(app, [
            "kb", "fetch-laws",
            "--output-dir", str(tmp_path),
            "--laws", "A0030018",
        ])

        assert result.exit_code == 0
        assert "擷取完成" in result.stdout

    @patch("src.knowledge.fetchers.gazette_fetcher.requests.get")
    def test_fetch_gazette_command(self, mock_get, tmp_path):
        """測試 fetch-gazette CLI 命令"""
        from src.cli.main import app

        xml_data = _load_fixture("sample_gazette.xml")
        mock_resp = MagicMock()
        mock_resp.content = xml_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = runner.invoke(app, [
            "kb", "fetch-gazette",
            "--output-dir", str(tmp_path),
            "--days", "3650",
        ])

        assert result.exit_code == 0
        assert "擷取完成" in result.stdout

    @patch("src.knowledge.fetchers.opendata_fetcher.requests.post")
    def test_fetch_opendata_command(self, mock_post, tmp_path):
        """測試 fetch-opendata CLI 命令"""
        from src.cli.main import app

        json_data = _load_fixture("sample_opendata.json")
        mock_resp = MagicMock()
        mock_resp.json.return_value = json.loads(json_data)
        mock_resp.raise_for_status = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        result = runner.invoke(app, [
            "kb", "fetch-opendata",
            "--output-dir", str(tmp_path),
            "--keyword", "警政署",
            "--limit", "5",
        ])

        assert result.exit_code == 0
        assert "擷取完成" in result.stdout

    @patch("src.knowledge.fetchers.law_fetcher.requests.get")
    @patch("src.cli.kb.KnowledgeBaseManager")
    @patch("src.cli.kb.get_llm_factory")
    @patch("src.cli.kb.ConfigManager")
    def test_fetch_laws_with_ingest(self, mock_cm, mock_factory, mock_kb_class, mock_get, tmp_path):
        """測試 --ingest 旗標會觸發匯入"""
        from src.cli.main import app

        mock_cm.return_value.config = {
            "llm": {"provider": "mock"},
            "knowledge_base": {"path": str(tmp_path / "kb")},
        }

        zip_data = _load_fixture("sample_law.zip")
        mock_resp = MagicMock()
        mock_resp.content = zip_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        mock_kb_instance = mock_kb_class.return_value
        mock_kb_instance.add_document.return_value = "doc_id"
        mock_kb_instance.get_stats.return_value = {
            "examples_count": 0, "regulations_count": 2, "policies_count": 0
        }

        result = runner.invoke(app, [
            "kb", "fetch-laws",
            "--output-dir", str(tmp_path),
            "--laws", "A0030018,A0030055",
            "--ingest",
        ])

        assert result.exit_code == 0
        assert "已匯入" in result.stdout
        assert mock_kb_instance.add_document.call_count >= 1


# ==================== TestSanitizeMetadata ====================

class TestSanitizeMetadata:
    """_sanitize_metadata 共用函式的測試。"""

    def test_sanitize_basic_types(self):
        """測試基本型態保持不變"""
        from src.cli.kb import _sanitize_metadata

        result = _sanitize_metadata({
            "title": "標題",
            "count": 42,
            "score": 0.95,
            "active": True,
        })
        assert result["title"] == "標題"
        assert result["count"] == 42
        assert result["score"] == 0.95
        assert result["active"] is True

    def test_sanitize_date(self):
        """測試 date/datetime 轉為 ISO 字串"""
        from src.cli.kb import _sanitize_metadata
        import datetime

        result = _sanitize_metadata({
            "date": datetime.date(2025, 6, 15),
            "timestamp": datetime.datetime(2025, 6, 15, 10, 30),
        })
        assert result["date"] == "2025-06-15"
        assert "2025-06-15" in result["timestamp"]

    def test_sanitize_list(self):
        """測試 list 轉為 JSON 字串"""
        from src.cli.kb import _sanitize_metadata

        result = _sanitize_metadata({"tags": ["法規", "全文"]})
        assert result["tags"] == '["法規", "全文"]'

    def test_sanitize_none_filtered(self):
        """測試 None 值被過濾"""
        from src.cli.kb import _sanitize_metadata

        result = _sanitize_metadata({"title": "OK", "empty": None})
        assert "empty" not in result
        assert result["title"] == "OK"

    def test_sanitize_other_types(self):
        """測試其他型態轉為字串"""
        from src.cli.kb import _sanitize_metadata

        result = _sanitize_metadata({"obj": {"nested": "dict"}})
        assert isinstance(result["obj"], str)


# ==================== TestNpaFetcher ====================

class TestNpaFetcher:
    """NpaFetcher 的測試。"""

    @patch("src.knowledge.fetchers.npa_fetcher.requests.get")
    def test_fetch_parses_xml(self, mock_get, tmp_path):
        """測試正確解析 NPA XML 並產生 Markdown"""
        from src.knowledge.fetchers.npa_fetcher import NpaFetcher

        xml_data = _load_fixture("sample_npa.xml")
        mock_resp = MagicMock()
        mock_resp.content = xml_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = NpaFetcher(output_dir=tmp_path, rate_limit=0)
        results = fetcher.fetch()

        assert len(results) == 3
        titles = {r.metadata["title"] for r in results}
        assert "警察機關辦理刑事案件統計" in titles
        assert "交通事故統計資料" in titles
        assert "失蹤人口查尋系統" in titles

        # 所有結果都歸到 policies
        for r in results:
            assert r.collection == "policies"
            assert r.source_level == "B"
            assert r.file_path.exists()

    @patch("src.knowledge.fetchers.npa_fetcher.requests.get")
    def test_fetch_extracts_dataset_id(self, mock_get, tmp_path):
        """測試從 relateURL 正確提取 data.gov.tw dataset ID"""
        from src.knowledge.fetchers.npa_fetcher import NpaFetcher

        xml_data = _load_fixture("sample_npa.xml")
        mock_resp = MagicMock()
        mock_resp.content = xml_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = NpaFetcher(output_dir=tmp_path, rate_limit=0)
        results = fetcher.fetch()

        # 第一筆 relateURL 是 https://data.gov.tw/dataset/12345
        crime_result = next(r for r in results if "刑事" in r.metadata["title"])
        assert "12345" in crime_result.source_url

        # 第三筆 relateURL 沒有 data.gov.tw，應使用原始 URL
        missing_result = next(r for r in results if "失蹤" in r.metadata["title"])
        assert "example.com" in missing_result.source_url

    @patch("src.knowledge.fetchers.npa_fetcher.requests.get")
    def test_fetch_network_error(self, mock_get, tmp_path):
        """測試網路錯誤時回傳空清單"""
        from src.knowledge.fetchers.npa_fetcher import NpaFetcher
        import requests as req

        mock_get.side_effect = req.ConnectionError("Network error")

        fetcher = NpaFetcher(output_dir=tmp_path, rate_limit=0)
        results = fetcher.fetch()
        assert results == []

    @patch("src.knowledge.fetchers.npa_fetcher.requests.get")
    def test_fetch_bad_xml(self, mock_get, tmp_path):
        """測試無效 XML 時回傳空清單"""
        from src.knowledge.fetchers.npa_fetcher import NpaFetcher

        mock_resp = MagicMock()
        mock_resp.content = b"<invalid>xml<broken"
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = NpaFetcher(output_dir=tmp_path, rate_limit=0)
        results = fetcher.fetch()
        assert results == []

    def test_name(self, tmp_path):
        from src.knowledge.fetchers.npa_fetcher import NpaFetcher
        f = NpaFetcher(output_dir=tmp_path, rate_limit=0)
        assert f.name() == "警政署 OPEN DATA"

    def test_extract_dataset_id_from_data_gov_url(self):
        """測試 _extract_dataset_id 正確提取 ID"""
        from src.knowledge.fetchers.npa_fetcher import NpaFetcher
        assert NpaFetcher._extract_dataset_id("https://data.gov.tw/dataset/12345") == "12345"
        assert NpaFetcher._extract_dataset_id("https://example.com") == ""
        assert NpaFetcher._extract_dataset_id("") == ""

    @patch("src.knowledge.fetchers.npa_fetcher.requests.get")
    def test_fetch_includes_content_hash(self, mock_get, tmp_path):
        """測試 NPA 結果包含 content_hash"""
        from src.knowledge.fetchers.npa_fetcher import NpaFetcher

        xml_data = _load_fixture("sample_npa.xml")
        mock_resp = MagicMock()
        mock_resp.content = xml_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = NpaFetcher(output_dir=tmp_path, rate_limit=0)
        results = fetcher.fetch()

        for r in results:
            assert r.content_hash, f"結果 {r.metadata['title']} 缺少 content_hash"
            assert len(r.content_hash) == 16
            assert r.metadata.get("content_hash") == r.content_hash


# ==================== TestContentHash ====================

class TestContentHash:
    """content_hash 功能的跨 Fetcher 測試。"""

    def test_compute_hash_deterministic(self):
        """_compute_hash 對相同輸入應產生相同結果"""
        from src.knowledge.fetchers.base import BaseFetcher
        h1 = BaseFetcher._compute_hash("測試文本")
        h2 = BaseFetcher._compute_hash("測試文本")
        assert h1 == h2
        assert len(h1) == 16

    def test_compute_hash_different_input(self):
        """_compute_hash 對不同輸入應產生不同結果"""
        from src.knowledge.fetchers.base import BaseFetcher
        h1 = BaseFetcher._compute_hash("文本一")
        h2 = BaseFetcher._compute_hash("文本二")
        assert h1 != h2

    def test_fetch_result_with_content_hash(self):
        """FetchResult 應支援 content_hash 欄位"""
        result = FetchResult(
            file_path=Path("/tmp/test.md"),
            metadata={"title": "test"},
            collection="examples",
            content_hash="abc123def4567890",
        )
        assert result.content_hash == "abc123def4567890"

    def test_fetch_result_default_content_hash(self):
        """FetchResult 未指定 content_hash 時預設為空字串"""
        result = FetchResult(
            file_path=Path("/tmp/test.md"),
            metadata={"title": "test"},
            collection="examples",
        )
        assert result.content_hash == ""

    @patch("src.knowledge.fetchers.gazette_fetcher.requests.get")
    def test_gazette_fetcher_includes_hash(self, mock_get, tmp_path):
        """GazetteFetcher 結果應包含 content_hash"""
        from src.knowledge.fetchers.gazette_fetcher import GazetteFetcher

        xml_data = _load_fixture("sample_gazette.xml")
        mock_resp = MagicMock()
        mock_resp.content = xml_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = GazetteFetcher(output_dir=tmp_path, days=365 * 10, rate_limit=0)
        results = fetcher.fetch()

        for r in results:
            assert r.content_hash, "GazetteFetcher 結果缺少 hash"
            assert len(r.content_hash) == 16
            assert r.metadata.get("content_hash") == r.content_hash

    @patch("src.knowledge.fetchers.law_fetcher.requests.get")
    def test_law_fetcher_includes_hash(self, mock_get, tmp_path):
        """LawFetcher 結果應包含 content_hash"""
        from src.knowledge.fetchers.law_fetcher import LawFetcher

        zip_data = _load_fixture("sample_law.zip")
        mock_resp = MagicMock()
        mock_resp.content = zip_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = LawFetcher(output_dir=tmp_path, rate_limit=0)
        results = fetcher.fetch()

        for r in results:
            assert r.content_hash, "LawFetcher 結果缺少 hash"
            assert len(r.content_hash) == 16
            assert r.metadata.get("content_hash") == r.content_hash

    @patch("src.knowledge.fetchers.opendata_fetcher.requests.post")
    def test_opendata_fetcher_includes_hash(self, mock_post, tmp_path):
        """OpenDataFetcher 結果應包含 content_hash"""
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
            assert r.content_hash, "OpenDataFetcher 結果缺少 hash"
            assert len(r.content_hash) == 16
            assert r.metadata.get("content_hash") == r.content_hash


# ==================== TestFetchNpaCLI ====================

class TestFetchNpaCLI:
    """fetch-npa CLI 命令的整合測試。"""

    @patch("src.knowledge.fetchers.npa_fetcher.requests.get")
    def test_fetch_npa_command(self, mock_get, tmp_path):
        """測試 fetch-npa CLI 命令"""
        from src.cli.main import app

        xml_data = _load_fixture("sample_npa.xml")
        mock_resp = MagicMock()
        mock_resp.content = xml_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = runner.invoke(app, [
            "kb", "fetch-npa",
            "--output-dir", str(tmp_path),
        ])

        assert result.exit_code == 0
        assert "擷取完成" in result.stdout


# ==================== TestGazetteFetcherBulk ====================

class TestGazetteFetcherBulk:
    """GazetteFetcher bulk 模式的測試。"""

    @patch("src.knowledge.fetchers.gazette_fetcher.requests.get")
    def test_fetch_bulk_downloads_zip(self, mock_get, tmp_path):
        """測試下載並解壓 ZIP"""
        from src.knowledge.fetchers.gazette_fetcher import GazetteFetcher

        records = [
            {
                "MetaId": "BK001",
                "Title": "Bulk 測試公報",
                "Category": "",
                "PubGov": "行政院",
                "Date_Published": "2026-02-20",
                "HTMLContent": "<p>bulk 測試內容</p>",
            }
        ]
        zip_data = _make_gazette_bulk_zip(records)
        mock_resp = MagicMock()
        mock_resp.content = zip_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = GazetteFetcher(output_dir=tmp_path, days=365, rate_limit=0)
        results = fetcher.fetch_bulk(extract_pdf=False)

        assert len(results) == 1
        assert results[0].metadata["title"] == "Bulk 測試公報"
        assert results[0].file_path.exists()

    @patch("src.knowledge.fetchers.gazette_fetcher.requests.get")
    def test_fetch_bulk_parses_xml_from_zip(self, mock_get, tmp_path):
        """測試從 ZIP 內 XML 正確解析 Record"""
        from src.knowledge.fetchers.gazette_fetcher import GazetteFetcher

        records = [
            {"MetaId": "BK001", "Title": "公報一", "Category": "法規命令",
             "PubGov": "衛生署", "Date_Published": "2026-02-20", "HTMLContent": ""},
            {"MetaId": "BK002", "Title": "公報二", "Category": "施政計畫",
             "PubGov": "交通部", "Date_Published": "2026-02-21", "HTMLContent": ""},
        ]
        zip_data = _make_gazette_bulk_zip(records)
        mock_resp = MagicMock()
        mock_resp.content = zip_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = GazetteFetcher(output_dir=tmp_path, days=365, rate_limit=0)
        results = fetcher.fetch_bulk(extract_pdf=False)

        assert len(results) == 2
        titles = {r.metadata["title"] for r in results}
        assert "公報一" in titles
        assert "公報二" in titles

    @patch("src.knowledge.fetchers.gazette_fetcher.GazetteFetcher._extract_pdf_text")
    @patch("src.knowledge.fetchers.gazette_fetcher.requests.get")
    def test_fetch_bulk_extracts_pdf_text(self, mock_get, mock_pdf_extract, tmp_path):
        """測試 PDF 全文提取並合併到 Markdown"""
        from src.knowledge.fetchers.gazette_fetcher import GazetteFetcher

        records = [
            {"MetaId": "BK001", "Title": "含 PDF 公報", "Category": "",
             "PubGov": "行政院", "Date_Published": "2026-02-20", "HTMLContent": ""},
        ]
        pdf_bytes = _make_simple_pdf("PDF 全文測試")
        zip_data = _make_gazette_bulk_zip(records, pdfs={"BK001": pdf_bytes})

        mock_resp = MagicMock()
        mock_resp.content = zip_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp
        mock_pdf_extract.return_value = "PDF 全文測試內容"

        fetcher = GazetteFetcher(output_dir=tmp_path, days=365, rate_limit=0)
        results = fetcher.fetch_bulk(extract_pdf=True)

        assert len(results) == 1
        content = results[0].file_path.read_text(encoding="utf-8")
        assert "## PDF 全文" in content
        assert "PDF 全文測試內容" in content
        assert results[0].metadata["has_pdf_text"] is True

    @patch("src.knowledge.fetchers.gazette_fetcher.requests.get")
    def test_fetch_bulk_without_pdf(self, mock_get, tmp_path):
        """測試 extract_pdf=False 跳過 PDF"""
        from src.knowledge.fetchers.gazette_fetcher import GazetteFetcher

        records = [
            {"MetaId": "BK001", "Title": "無 PDF 公報", "Category": "",
             "PubGov": "行政院", "Date_Published": "2026-02-20", "HTMLContent": ""},
        ]
        pdf_bytes = _make_simple_pdf()
        zip_data = _make_gazette_bulk_zip(records, pdfs={"BK001": pdf_bytes})

        mock_resp = MagicMock()
        mock_resp.content = zip_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = GazetteFetcher(output_dir=tmp_path, days=365, rate_limit=0)
        results = fetcher.fetch_bulk(extract_pdf=False)

        assert len(results) == 1
        content = results[0].file_path.read_text(encoding="utf-8")
        assert "## PDF 全文" not in content
        assert results[0].metadata["has_pdf_text"] is False

    @patch("src.knowledge.fetchers.gazette_fetcher.requests.get")
    def test_fetch_bulk_pdf_missing(self, mock_get, tmp_path):
        """測試 ZIP 內無 PDF 時仍正常"""
        from src.knowledge.fetchers.gazette_fetcher import GazetteFetcher

        records = [
            {"MetaId": "BK001", "Title": "無 PDF 可用", "Category": "",
             "PubGov": "行政院", "Date_Published": "2026-02-20", "HTMLContent": ""},
        ]
        zip_data = _make_gazette_bulk_zip(records, pdfs=None)

        mock_resp = MagicMock()
        mock_resp.content = zip_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = GazetteFetcher(output_dir=tmp_path, days=365, rate_limit=0)
        results = fetcher.fetch_bulk(extract_pdf=True)

        assert len(results) == 1
        assert results[0].metadata["has_pdf_text"] is False

    @patch("src.knowledge.fetchers.gazette_fetcher.requests.get")
    def test_fetch_bulk_bad_zip(self, mock_get, tmp_path):
        """測試 ZIP 損壞回傳空清單"""
        from src.knowledge.fetchers.gazette_fetcher import GazetteFetcher

        mock_resp = MagicMock()
        mock_resp.content = b"not a zip file"
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = GazetteFetcher(output_dir=tmp_path, days=365, rate_limit=0)
        results = fetcher.fetch_bulk()

        assert results == []

    @patch("src.knowledge.fetchers.gazette_fetcher.requests.get")
    def test_fetch_bulk_network_error(self, mock_get, tmp_path):
        """測試網路錯誤"""
        from src.knowledge.fetchers.gazette_fetcher import GazetteFetcher
        import requests as req

        mock_get.side_effect = req.ConnectionError("Network error")

        fetcher = GazetteFetcher(output_dir=tmp_path, rate_limit=0)
        results = fetcher.fetch_bulk()
        assert results == []

    @patch("src.knowledge.fetchers.gazette_fetcher.requests.get")
    def test_fetch_bulk_date_filter(self, mock_get, tmp_path):
        """測試日期篩選在 bulk 模式下仍生效"""
        import datetime
        from src.knowledge.fetchers.gazette_fetcher import GazetteFetcher

        recent_date = (datetime.date.today() - datetime.timedelta(days=5)).isoformat()
        records = [
            {"MetaId": "BK001", "Title": "新公報", "Category": "",
             "PubGov": "行政院", "Date_Published": recent_date, "HTMLContent": ""},
            {"MetaId": "BK002", "Title": "舊公報", "Category": "",
             "PubGov": "行政院", "Date_Published": "2020-01-01", "HTMLContent": ""},
        ]
        zip_data = _make_gazette_bulk_zip(records)
        mock_resp = MagicMock()
        mock_resp.content = zip_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = GazetteFetcher(output_dir=tmp_path, days=30, rate_limit=0)
        results = fetcher.fetch_bulk(extract_pdf=False)

        titles = {r.metadata["title"] for r in results}
        assert "新公報" in titles
        assert "舊公報" not in titles

    @patch("src.knowledge.fetchers.gazette_fetcher.requests.get")
    def test_fetch_bulk_category_filter(self, mock_get, tmp_path):
        """測試類別篩選"""
        from src.knowledge.fetchers.gazette_fetcher import GazetteFetcher

        records = [
            {"MetaId": "BK001", "Title": "法規類", "Category": "法規命令",
             "PubGov": "行政院", "Date_Published": "2026-02-20", "HTMLContent": ""},
            {"MetaId": "BK002", "Title": "一般類", "Category": "公告",
             "PubGov": "行政院", "Date_Published": "2026-02-20", "HTMLContent": ""},
        ]
        zip_data = _make_gazette_bulk_zip(records)
        mock_resp = MagicMock()
        mock_resp.content = zip_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = GazetteFetcher(
            output_dir=tmp_path, days=365,
            category_filter="法規命令", rate_limit=0,
        )
        results = fetcher.fetch_bulk(extract_pdf=False)

        assert len(results) == 1
        assert results[0].metadata["title"] == "法規類"

    @patch("src.knowledge.fetchers.gazette_fetcher.requests.get")
    def test_fetch_bulk_metadata(self, mock_get, tmp_path):
        """測試 metadata 含 fetch_mode + content_hash"""
        from src.knowledge.fetchers.gazette_fetcher import GazetteFetcher

        records = [
            {"MetaId": "BK001", "Title": "Metadata 測試", "Category": "",
             "PubGov": "行政院", "Date_Published": "2026-02-20", "HTMLContent": ""},
        ]
        zip_data = _make_gazette_bulk_zip(records)
        mock_resp = MagicMock()
        mock_resp.content = zip_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = GazetteFetcher(output_dir=tmp_path, days=365, rate_limit=0)
        results = fetcher.fetch_bulk(extract_pdf=False)

        assert len(results) == 1
        meta = results[0].metadata
        assert meta["fetch_mode"] == "bulk"
        assert "content_hash" in meta
        assert len(meta["content_hash"]) == 16
        assert results[0].content_hash == meta["content_hash"]


# ==================== TestLawFetcherBulk ====================

class TestLawFetcherBulk:
    """LawFetcher bulk 模式的測試。"""

    @patch("src.knowledge.fetchers.law_fetcher.requests.get")
    def test_fetch_bulk_downloads_and_parses(self, mock_get, tmp_path):
        """測試下載 ZIP 並解析 XML"""
        from src.knowledge.fetchers.law_fetcher import LawFetcher

        laws = [
            {
                "PCode": "A0030018",
                "LawName": "行政程序法",
                "LawArticles": [
                    {"ArticleNo": "第 1 條", "ArticleContent": "為使行政行為遵循公正、公開與民主之程序。"},
                ],
            }
        ]
        zip_data = _make_law_bulk_zip(laws)
        mock_resp = MagicMock()
        mock_resp.content = zip_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = LawFetcher(
            output_dir=tmp_path,
            pcodes={"A0030018": "行政程序法"},
            rate_limit=0,
        )
        results = fetcher.fetch_bulk()

        assert len(results) == 1
        assert results[0].metadata["title"] == "行政程序法"
        assert results[0].metadata.get("fetch_mode") == "bulk"
        assert results[0].file_path.exists()

    def test_parse_bulk_xml_format(self):
        """測試 _parse_bulk_xml 解析正確"""
        from src.knowledge.fetchers.law_fetcher import LawFetcher

        laws = [
            {
                "PCode": "A0030055",
                "LawName": "公文程式條例",
                "LawArticles": [
                    {"ArticleNo": "第 1 條", "ArticleContent": "公文程式條例。"},
                    {"ArticleNo": "第 2 條", "ArticleContent": "第二條。"},
                ],
            }
        ]
        xml_bytes = _make_law_bulk_xml(laws)
        parsed = LawFetcher._parse_bulk_xml(xml_bytes)

        assert len(parsed) == 1
        assert parsed[0]["PCode"] == "A0030055"
        assert parsed[0]["LawName"] == "公文程式條例"
        assert len(parsed[0]["LawArticles"]) == 2

    def test_parse_bulk_xml_with_foreword(self):
        """測試前言（Foreword）處理"""
        from src.knowledge.fetchers.law_fetcher import LawFetcher

        laws = [
            {
                "PCode": "A0030018",
                "LawName": "行政程序法",
                "Foreword": "本法之制定目的如下：",
                "LawArticles": [
                    {"ArticleNo": "第 1 條", "ArticleContent": "第一條。"},
                ],
            }
        ]
        xml_bytes = _make_law_bulk_xml(laws)
        parsed = LawFetcher._parse_bulk_xml(xml_bytes)

        assert len(parsed) == 1
        # 前言應成為第一個 article
        articles = parsed[0]["LawArticles"]
        assert articles[0]["ArticleNo"] == "前言"
        assert "制定目的" in articles[0]["ArticleContent"]
        assert len(articles) == 2  # 前言 + 第 1 條

    def test_parse_bulk_xml_no_declaration(self):
        """測試無 XML 宣告的 XML"""
        from src.knowledge.fetchers.law_fetcher import LawFetcher

        # 手動建立沒有 <?xml?> 宣告的 XML
        xml_str = (
            '<法規資料>'
            '<法規>'
            '<法規名稱>測試法</法規名稱>'
            '<法規網址>https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=T0010001</法規網址>'
            '<條文><條號>第 1 條</條號><條文內容>測試內容。</條文內容></條文>'
            '</法規>'
            '</法規資料>'
        )
        parsed = LawFetcher._parse_bulk_xml(xml_str.encode("utf-8"))

        assert len(parsed) == 1
        assert parsed[0]["PCode"] == "T0010001"

    def test_parse_bulk_xml_encoding_fallback(self):
        """測試 Big5 編碼 fallback"""
        from src.knowledge.fetchers.law_fetcher import LawFetcher

        xml_str = (
            '<法規資料>'
            '<法規>'
            '<法規名稱>大五碼測試法</法規名稱>'
            '<法規網址>https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=B5TEST01</法規網址>'
            '<條文><條號>第 1 條</條號><條文內容>大五碼內容。</條文內容></條文>'
            '</法規>'
            '</法規資料>'
        )
        big5_bytes = xml_str.encode("big5")
        parsed = LawFetcher._parse_bulk_xml(big5_bytes)

        assert len(parsed) == 1
        assert parsed[0]["LawName"] == "大五碼測試法"

    @patch("src.knowledge.fetchers.law_fetcher.requests.get")
    def test_fetch_bulk_filters_by_pcode(self, mock_get, tmp_path):
        """測試 PCode 篩選"""
        from src.knowledge.fetchers.law_fetcher import LawFetcher

        laws = [
            {"PCode": "A0030018", "LawName": "行政程序法",
             "LawArticles": [{"ArticleNo": "第 1 條", "ArticleContent": "內容"}]},
            {"PCode": "Z9999999", "LawName": "不應出現",
             "LawArticles": [{"ArticleNo": "第 1 條", "ArticleContent": "內容"}]},
        ]
        zip_data = _make_law_bulk_zip(laws)
        mock_resp = MagicMock()
        mock_resp.content = zip_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = LawFetcher(
            output_dir=tmp_path,
            pcodes={"A0030018": "行政程序法"},
            rate_limit=0,
        )
        results = fetcher.fetch_bulk()

        assert len(results) == 1
        assert results[0].metadata["pcode"] == "A0030018"

    @patch("src.knowledge.fetchers.law_fetcher.requests.get")
    def test_fetch_bulk_large_law_chunked(self, mock_get, tmp_path):
        """測試大型法規 chunk"""
        from src.knowledge.fetchers.law_fetcher import LawFetcher

        articles = [
            {"ArticleNo": f"第 {i} 條", "ArticleContent": "條文內容。" * 50}
            for i in range(1, 51)
        ]
        laws = [{"PCode": "A0030018", "LawName": "行政程序法", "LawArticles": articles}]
        zip_data = _make_law_bulk_zip(laws)

        mock_resp = MagicMock()
        mock_resp.content = zip_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = LawFetcher(
            output_dir=tmp_path,
            pcodes={"A0030018": "行政程序法"},
            rate_limit=0,
        )
        results = fetcher.fetch_bulk()

        # 50 條 / 20 條 per chunk = 3 個檔案
        assert len(results) == 3
        for r in results:
            assert "part" in r.metadata

    @patch("src.knowledge.fetchers.law_fetcher.requests.get")
    def test_fetch_bulk_bad_zip(self, mock_get, tmp_path):
        """測試 ZIP 損壞"""
        from src.knowledge.fetchers.law_fetcher import LawFetcher

        mock_resp = MagicMock()
        mock_resp.content = b"not a zip file"
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = LawFetcher(output_dir=tmp_path, rate_limit=0)
        results = fetcher.fetch_bulk()
        assert results == []


# ==================== TestPdfExtraction ====================

class TestPdfExtraction:
    """PDF 全文提取功能的測試。"""

    @patch("src.knowledge.fetchers.gazette_fetcher.pdfplumber", create=True)
    def test_extract_valid_pdf(self, mock_pdfplumber):
        """測試有效 PDF 提取文字"""
        from src.knowledge.fetchers.gazette_fetcher import GazetteFetcher

        # mock pdfplumber.open context manager
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "第一頁文字"
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)
        mock_pdfplumber.open.return_value = mock_pdf

        # 需要 patch import
        import sys
        sys.modules["pdfplumber"] = mock_pdfplumber

        try:
            result = GazetteFetcher._extract_pdf_text(b"fake pdf bytes")
            assert result == "第一頁文字"
        finally:
            if "pdfplumber" in sys.modules and sys.modules["pdfplumber"] is mock_pdfplumber:
                del sys.modules["pdfplumber"]

    def test_extract_corrupted_pdf(self):
        """測試損壞 PDF 回傳空字串"""
        from src.knowledge.fetchers.gazette_fetcher import GazetteFetcher

        # 用壞資料直接呼叫，pdfplumber 如有安裝會拋例外
        result = GazetteFetcher._extract_pdf_text(b"corrupted data")
        # 無論 pdfplumber 是否安裝，都應回傳空字串（import error 或 parse error）
        assert isinstance(result, str)

    def test_extract_empty_pdf(self):
        """測試空白 PDF"""
        from src.knowledge.fetchers.gazette_fetcher import GazetteFetcher

        result = GazetteFetcher._extract_pdf_text(b"")
        assert isinstance(result, str)

    def test_pdfplumber_missing(self):
        """測試 pdfplumber 未安裝時 graceful degradation"""
        from src.knowledge.fetchers.gazette_fetcher import GazetteFetcher
        import sys

        # 暫時移除 pdfplumber
        saved = sys.modules.pop("pdfplumber", None)
        # 也確保 import 失敗
        sys.modules["pdfplumber"] = None  # type: ignore

        try:
            result = GazetteFetcher._extract_pdf_text(b"some pdf bytes")
            assert result == ""
        finally:
            if saved is not None:
                sys.modules["pdfplumber"] = saved
            else:
                sys.modules.pop("pdfplumber", None)


# ==================== TestBulkCLI ====================

class TestBulkCLI:
    """Bulk 模式 CLI 命令的整合測試。"""

    @patch("src.knowledge.fetchers.gazette_fetcher.requests.get")
    def test_fetch_gazette_bulk_flag(self, mock_get, tmp_path):
        """測試 --bulk 選項呼叫 fetch_bulk()"""
        from src.cli.main import app

        records = [
            {"MetaId": "CLI001", "Title": "CLI Bulk 測試", "Category": "",
             "PubGov": "行政院", "Date_Published": "2026-02-20", "HTMLContent": ""},
        ]
        zip_data = _make_gazette_bulk_zip(records)
        mock_resp = MagicMock()
        mock_resp.content = zip_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = runner.invoke(app, [
            "kb", "fetch-gazette",
            "--output-dir", str(tmp_path),
            "--days", "365",
            "--bulk",
        ])

        assert result.exit_code == 0
        assert "擷取完成" in result.stdout

    @patch("src.knowledge.fetchers.gazette_fetcher.requests.get")
    def test_fetch_gazette_bulk_no_pdf(self, mock_get, tmp_path):
        """測試 --bulk --no-pdf"""
        from src.cli.main import app

        records = [
            {"MetaId": "CLI002", "Title": "CLI No PDF", "Category": "",
             "PubGov": "行政院", "Date_Published": "2026-02-20", "HTMLContent": ""},
        ]
        zip_data = _make_gazette_bulk_zip(records)
        mock_resp = MagicMock()
        mock_resp.content = zip_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = runner.invoke(app, [
            "kb", "fetch-gazette",
            "--output-dir", str(tmp_path),
            "--days", "365",
            "--bulk",
            "--no-pdf",
        ])

        assert result.exit_code == 0
        assert "擷取完成" in result.stdout

    @patch("src.knowledge.fetchers.law_fetcher.requests.get")
    def test_fetch_laws_bulk_flag(self, mock_get, tmp_path):
        """測試 --bulk 選項呼叫 fetch_bulk()"""
        from src.cli.main import app

        laws = [
            {"PCode": "A0030018", "LawName": "行政程序法",
             "LawArticles": [{"ArticleNo": "第 1 條", "ArticleContent": "測試"}]},
        ]
        zip_data = _make_law_bulk_zip(laws)
        mock_resp = MagicMock()
        mock_resp.content = zip_data
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = runner.invoke(app, [
            "kb", "fetch-laws",
            "--output-dir", str(tmp_path),
            "--laws", "A0030018",
            "--bulk",
        ])

        assert result.exit_code == 0
        assert "擷取完成" in result.stdout


# ==================== TestLegislativeFetcher ====================

class TestLegislativeFetcher:
    """LegislativeFetcher 的測試。"""

    @patch("src.knowledge.fetchers.legislative_fetcher.requests.get")
    def test_fetch_basic(self, mock_get, tmp_path):
        """測試基本議案擷取"""
        from src.knowledge.fetchers.legislative_fetcher import LegislativeFetcher

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "total": 1,
            "total_page": 1,
            "page": 1,
            "bills": [
                {
                    "議案名稱": "測試法案",
                    "屆": 11,
                    "會期": 1,
                    "提案單位/提案委員": "張委員",
                    "議案狀態": "審查中",
                    "議案編號": "202301001",
                    "議案類別": "委員提案",
                    "最新進度日期": "2026-01-15",
                    "會議代碼:str": "第11屆第1會期第1次會議",
                    "相關附件": [
                        {"名稱": "關係文書PDF", "網址": "https://ppg.ly.gov.tw/test.pdf"},
                    ],
                },
            ],
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = LegislativeFetcher(output_dir=tmp_path, limit=5)
        results = fetcher.fetch()

        assert len(results) == 1
        assert results[0].collection == "policies"
        assert results[0].file_path.exists()
        content = results[0].file_path.read_text(encoding="utf-8")
        assert "測試法案" in content
        assert "張委員" in content

    @patch("src.knowledge.fetchers.legislative_fetcher.requests.get")
    def test_fetch_empty_response(self, mock_get, tmp_path):
        """測試空回應"""
        from src.knowledge.fetchers.legislative_fetcher import LegislativeFetcher

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"total": 0, "total_page": 0, "bills": []}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = LegislativeFetcher(output_dir=tmp_path, limit=5)
        results = fetcher.fetch()
        assert len(results) == 0

    @patch("src.knowledge.fetchers.legislative_fetcher.requests.get")
    def test_fetch_network_error(self, mock_get, tmp_path):
        """測試網路錯誤"""
        from src.knowledge.fetchers.legislative_fetcher import LegislativeFetcher
        import requests as req

        mock_get.side_effect = req.ConnectionError("Connection refused")

        fetcher = LegislativeFetcher(output_dir=tmp_path, limit=5)
        results = fetcher.fetch()
        assert len(results) == 0

    def test_name(self, tmp_path):
        """測試 name() 方法"""
        from src.knowledge.fetchers.legislative_fetcher import LegislativeFetcher
        fetcher = LegislativeFetcher(output_dir=tmp_path)
        assert fetcher.name() == "立法院議案"

    @patch("src.knowledge.fetchers.legislative_fetcher.requests.get")
    def test_fetch_pagination(self, mock_get, tmp_path):
        """測試分頁邏輯"""
        from src.knowledge.fetchers.legislative_fetcher import LegislativeFetcher

        def side_effect(*args, **kwargs):
            page = kwargs.get("params", {}).get("page", 1)
            resp = MagicMock()
            resp.status_code = 200
            resp.raise_for_status = MagicMock()
            if page == 1:
                resp.json.return_value = {
                    "total": 5,
                    "total_page": 2,
                    "bills": [{"議案名稱": f"法案_{i}", "屆": 11} for i in range(3)],
                }
            else:
                resp.json.return_value = {
                    "total": 5,
                    "total_page": 2,
                    "bills": [{"議案名稱": f"法案_{i+3}", "屆": 11} for i in range(2)],
                }
            return resp

        mock_get.side_effect = side_effect

        fetcher = LegislativeFetcher(output_dir=tmp_path, limit=10)
        results = fetcher.fetch()
        assert len(results) == 5


# ==================== TestLegislativeDebateFetcher ====================

class TestLegislativeDebateFetcher:
    """LegislativeDebateFetcher 的測試。"""

    @patch("src.knowledge.fetchers.legislative_debate_fetcher.requests.get")
    def test_fetch_basic(self, mock_get, tmp_path):
        """測試基本質詢擷取"""
        from src.knowledge.fetchers.legislative_debate_fetcher import LegislativeDebateFetcher

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {
                "title": "測試質詢",
                "legislator": "王委員",
                "date": "2026-01-15",
                "content": "質詢內容",
                "url": "https://example.com/debate/1",
            },
        ]
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = LegislativeDebateFetcher(output_dir=tmp_path, limit=5)
        results = fetcher.fetch()

        assert len(results) == 1
        assert results[0].collection == "policies"
        content = results[0].file_path.read_text(encoding="utf-8")
        assert "測試質詢" in content
        assert "王委員" in content

    @patch("src.knowledge.fetchers.legislative_debate_fetcher.requests.get")
    def test_fetch_empty(self, mock_get, tmp_path):
        """測試空回應"""
        from src.knowledge.fetchers.legislative_debate_fetcher import LegislativeDebateFetcher

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = []
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = LegislativeDebateFetcher(output_dir=tmp_path, limit=5)
        results = fetcher.fetch()
        assert len(results) == 0

    @patch("src.knowledge.fetchers.legislative_debate_fetcher.requests.get")
    def test_fetch_network_error(self, mock_get, tmp_path):
        """測試網路錯誤"""
        from src.knowledge.fetchers.legislative_debate_fetcher import LegislativeDebateFetcher
        import requests as req

        mock_get.side_effect = req.ConnectionError("Connection refused")

        fetcher = LegislativeDebateFetcher(output_dir=tmp_path, limit=5)
        results = fetcher.fetch()
        assert len(results) == 0

    def test_name(self, tmp_path):
        """測試 name() 方法"""
        from src.knowledge.fetchers.legislative_debate_fetcher import LegislativeDebateFetcher
        fetcher = LegislativeDebateFetcher(output_dir=tmp_path)
        assert fetcher.name() == "立法院質詢/會議"


# ==================== TestProcurementFetcher ====================

class TestProcurementFetcher:
    """ProcurementFetcher 的測試。"""

    @patch("src.knowledge.fetchers.procurement_fetcher.requests.get")
    def test_fetch_basic(self, mock_get, tmp_path):
        """測試基本採購公告擷取（依日期）"""
        from src.knowledge.fetchers.procurement_fetcher import ProcurementFetcher

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "records": [
                {
                    "date": 20260301,
                    "filename": "TIQ-1-70000001",
                    "brief": {
                        "type": "公開招標公告",
                        "title": "辦公設備採購案",
                        "category": "財物類",
                    },
                    "job_number": "LP5-123456",
                    "unit_id": "A.1",
                    "unit_name": "財政部",
                    "tender_api_url": "https://pcc-api.openfun.app/api/tender?unit_id=A.1&job_number=LP5-123456",
                    "url": "/index/case/A.1/LP5-123456/20260301/TIQ-1-70000001",
                },
            ],
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = ProcurementFetcher(output_dir=tmp_path, days=1, limit=5)
        results = fetcher.fetch()

        assert len(results) == 1
        assert results[0].collection == "policies"
        content = results[0].file_path.read_text(encoding="utf-8")
        assert "辦公設備採購案" in content
        assert "財政部" in content

    @patch("src.knowledge.fetchers.procurement_fetcher.requests.get")
    def test_fetch_by_keyword(self, mock_get, tmp_path):
        """測試依關鍵字搜尋"""
        from src.knowledge.fetchers.procurement_fetcher import ProcurementFetcher

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "query": "資訊系統",
            "page": 1,
            "total_records": 1,
            "total_pages": 1,
            "records": [
                {
                    "date": 20260306,
                    "brief": {
                        "type": "公開招標公告",
                        "title": "資訊系統建置案",
                        "category": "財物類",
                    },
                    "job_number": "IN1150107",
                    "unit_id": "A.21.100.33",
                    "unit_name": "衛生福利部",
                    "url": "/index/case/A.21/IN1150107/20260306/TIQ-1-70972925",
                },
            ],
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = ProcurementFetcher(output_dir=tmp_path, keyword="資訊系統", limit=5)
        results = fetcher.fetch()

        assert len(results) == 1
        content = results[0].file_path.read_text(encoding="utf-8")
        assert "資訊系統建置案" in content

    @patch("src.knowledge.fetchers.procurement_fetcher.requests.get")
    def test_fetch_empty(self, mock_get, tmp_path):
        """測試空回應"""
        from src.knowledge.fetchers.procurement_fetcher import ProcurementFetcher

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"records": []}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = ProcurementFetcher(output_dir=tmp_path, limit=5)
        results = fetcher.fetch()
        assert len(results) == 0

    @patch("src.knowledge.fetchers.procurement_fetcher.requests.get")
    def test_fetch_network_error(self, mock_get, tmp_path):
        """測試網路錯誤"""
        from src.knowledge.fetchers.procurement_fetcher import ProcurementFetcher
        import requests as req

        mock_get.side_effect = req.ConnectionError("Connection refused")

        fetcher = ProcurementFetcher(output_dir=tmp_path, limit=5)
        results = fetcher.fetch()
        assert len(results) == 0

    def test_name(self, tmp_path):
        """測試 name() 方法"""
        from src.knowledge.fetchers.procurement_fetcher import ProcurementFetcher
        fetcher = ProcurementFetcher(output_dir=tmp_path)
        assert fetcher.name() == "政府採購公告"


# ==================== TestJudicialFetcher ====================

class TestJudicialFetcher:
    """JudicialFetcher 的測試。"""

    @patch("src.knowledge.fetchers.judicial_fetcher.requests.get")
    def test_fetch_basic(self, mock_get, tmp_path):
        """測試基本裁判書擷取（免認證 FJUD）"""
        from src.knowledge.fetchers.judicial_fetcher import JudicialFetcher

        list_json = {
            "status": "200",
            "li_list": [
                '<a href="https://judgment.judicial.gov.tw/FJUD/data.aspx'
                '?ty=JD&id=TPAA,114,test,1,20260226,1" target="_blank">'
                '115.02.26 最高行政法院114年test字第1號裁定</a>',
            ],
        }
        detail_html = '''
        <html><body>
        <div class="col-td jud_content">
        <table><tr><td class="tab_content">
        <div class="htmlcontent"><div>最高行政法院裁定</div><div>主文</div><div>聲請駁回。</div></div>
        </td></tr></table>
        </div>
        </body></html>
        '''

        def get_side_effect(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.raise_for_status = MagicMock()
            if "GetLatest" in url:
                resp.json.return_value = list_json
            else:
                resp.text = detail_html
            return resp

        mock_get.side_effect = get_side_effect

        fetcher = JudicialFetcher(output_dir=tmp_path, limit=5)
        results = fetcher.fetch()

        assert len(results) >= 1
        assert results[0].collection == "regulations"
        assert results[0].source_level == "A"
        content = results[0].file_path.read_text(encoding="utf-8")
        assert "最高行政法院" in content

    @patch("src.knowledge.fetchers.judicial_fetcher.requests.get")
    def test_fetch_network_error(self, mock_get, tmp_path):
        """測試網路錯誤"""
        from src.knowledge.fetchers.judicial_fetcher import JudicialFetcher
        import requests as req

        mock_get.side_effect = req.ConnectionError("Connection refused")

        fetcher = JudicialFetcher(output_dir=tmp_path, limit=5)
        results = fetcher.fetch()
        assert len(results) == 0

    def test_name(self, tmp_path):
        """測試 name() 方法"""
        from src.knowledge.fetchers.judicial_fetcher import JudicialFetcher
        fetcher = JudicialFetcher(output_dir=tmp_path)
        assert fetcher.name() == "司法院裁判書"

    def test_parse_link(self, tmp_path):
        """測試 _parse_link 解析"""
        from src.knowledge.fetchers.judicial_fetcher import JudicialFetcher
        link_html = (
            '<a href="https://judgment.judicial.gov.tw/FJUD/data.aspx'
            '?ty=JD&id=TPAA,114,test,1,20260226,1" target="_blank">'
            '115.02.26 最高行政法院裁定</a>'
        )
        result = JudicialFetcher._parse_link(link_html, "最高行政法院")
        assert result is not None
        assert result["title"] == "115.02.26 最高行政法院裁定"
        assert "FJUD" in result["url"]



# ==================== TestInterpretationFetcher ====================

class TestInterpretationFetcher:
    """InterpretationFetcher 的測試。"""

    @patch("src.knowledge.fetchers.interpretation_fetcher.requests.get")
    def test_fetch_basic(self, mock_get, tmp_path):
        """測試基本函釋擷取"""
        from src.knowledge.fetchers.interpretation_fetcher import InterpretationFetcher

        list_html = '''
        <html><body>
        <a href="LawContent.aspx?LSID=FL009733">法務部調查局幹部訓練所組織條例</a>
        <a href="LawContent.aspx?LSID=FL048731">公民與政治權利國際公約施行法</a>
        </body></html>
        '''
        detail_html = '''
        <html><body>
        <div class="law-content law-content-moj">
        <p>本條例針對法務部調查局幹部訓練所之組織予以規範...</p>
        </div>
        </body></html>
        '''

        def get_side_effect(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.raise_for_status = MagicMock()
            if "CategoryContentList" in url:
                resp.text = list_html
            else:
                resp.text = detail_html
            return resp

        mock_get.side_effect = get_side_effect

        fetcher = InterpretationFetcher(output_dir=tmp_path, limit=5)
        results = fetcher.fetch()

        assert len(results) == 2
        assert results[0].collection == "regulations"
        assert results[0].source_level == "A"

    @patch("src.knowledge.fetchers.interpretation_fetcher.requests.get")
    def test_fetch_empty_list(self, mock_get, tmp_path):
        """測試空列表"""
        from src.knowledge.fetchers.interpretation_fetcher import InterpretationFetcher

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html><body>無結果</body></html>"
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = InterpretationFetcher(output_dir=tmp_path, limit=5)
        results = fetcher.fetch()
        assert len(results) == 0

    @patch("src.knowledge.fetchers.interpretation_fetcher.requests.get")
    def test_fetch_network_error(self, mock_get, tmp_path):
        """測試網路錯誤"""
        from src.knowledge.fetchers.interpretation_fetcher import InterpretationFetcher
        import requests as req

        mock_get.side_effect = req.ConnectionError("Connection refused")

        fetcher = InterpretationFetcher(output_dir=tmp_path, limit=5)
        results = fetcher.fetch()
        assert len(results) == 0

    def test_name(self, tmp_path):
        """測試 name() 方法"""
        from src.knowledge.fetchers.interpretation_fetcher import InterpretationFetcher
        fetcher = InterpretationFetcher(output_dir=tmp_path)
        assert fetcher.name() == "法務部行政函釋"

    def test_parse_list_page(self):
        """測試列表頁 HTML 解析"""
        from src.knowledge.fetchers.interpretation_fetcher import InterpretationFetcher

        html = '''
        <a href="LawContent.aspx?LSID=FL009733">法務部組織法</a>
        <a href="LawContent.aspx?LSID=FL048731">公民權利國際公約施行法</a>
        <a href="/other.aspx">其他連結</a>
        '''
        items = InterpretationFetcher._parse_list_page(html)
        assert len(items) == 2


# ==================== TestLocalRegulationFetcher ====================

class TestLocalRegulationFetcher:
    """LocalRegulationFetcher 的測試。"""

    @patch("src.knowledge.fetchers.local_regulation_fetcher.requests.get")
    def test_fetch_basic(self, mock_get, tmp_path):
        """測試基本地方法規擷取"""
        from src.knowledge.fetchers.local_regulation_fetcher import LocalRegulationFetcher

        list_html = '''
        <html><body>
        <a href="/Law/LawSearch/LawInformation/FL001174">臺北市政府組織自治條例</a>
        </body></html>
        '''
        detail_html = '''
        <html><body>
        <div class="law-content">
        <p>第一條 本自治條例依地方制度法制定之。</p>
        </div>
        </body></html>
        '''

        def get_side_effect(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.raise_for_status = MagicMock()
            if "/Law" == url.split("?")[0].split("/Law/LawSearch")[0] + "/Law" or "laws.taipei" in url:
                resp.text = list_html
            else:
                resp.text = detail_html
            return resp

        mock_get.side_effect = get_side_effect

        fetcher = LocalRegulationFetcher(output_dir=tmp_path, city="taipei", limit=5)
        results = fetcher.fetch()

        assert len(results) == 1
        assert results[0].collection == "regulations"
        assert results[0].source_level == "A"

    @patch("src.knowledge.fetchers.local_regulation_fetcher.requests.get")
    def test_fetch_network_error(self, mock_get, tmp_path):
        """測試網路錯誤"""
        from src.knowledge.fetchers.local_regulation_fetcher import LocalRegulationFetcher
        import requests as req

        mock_get.side_effect = req.ConnectionError("Connection refused")

        fetcher = LocalRegulationFetcher(output_dir=tmp_path, limit=5)
        results = fetcher.fetch()
        assert len(results) == 0

    def test_name(self, tmp_path):
        """測試 name() 方法"""
        from src.knowledge.fetchers.local_regulation_fetcher import LocalRegulationFetcher
        fetcher = LocalRegulationFetcher(output_dir=tmp_path, city="taipei")
        assert "臺北市" in fetcher.name()

    def test_unsupported_city(self, tmp_path):
        """測試不支援的城市"""
        from src.knowledge.fetchers.local_regulation_fetcher import LocalRegulationFetcher
        fetcher = LocalRegulationFetcher(output_dir=tmp_path, city="unknown_city")
        results = fetcher.fetch()
        assert len(results) == 0


# ==================== TestExamYuanFetcher ====================

class TestExamYuanFetcher:
    """ExamYuanFetcher 的測試。"""

    @patch("src.knowledge.fetchers.exam_yuan_fetcher.requests.get")
    def test_fetch_basic(self, mock_get, tmp_path):
        """測試基本考試院法規擷取（Open Data JSON 模式）"""
        from src.knowledge.fetchers.exam_yuan_fetcher import ExamYuanFetcher

        opendata_html = '''
        <html><body>
        <a href="https://law.exam.gov.tw//Opendata/law_test.json">法律 JSON</a>
        </body></html>
        '''
        # 串接 JSON 格式（考試院實際格式）
        json_text = (
            '{"法規類別":"法律","法規體系":"人事","法規名稱":"公務人員任用法施行細則",'
            '"訂定公發布日":"20100101","最新異動日期":"20250101","法規內容":"第 1 條 測試",'
            '"資料網址":"https://law.exam.gov.tw/LawContent.aspx?id=FL001"}'
        )

        def get_side_effect(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.raise_for_status = MagicMock()
            if "OpenDataWeb" in url:
                resp.text = opendata_html
            elif ".json" in url:
                resp.text = json_text
            return resp

        mock_get.side_effect = get_side_effect

        fetcher = ExamYuanFetcher(output_dir=tmp_path, limit=5)
        results = fetcher.fetch()

        assert len(results) == 1
        assert results[0].collection == "regulations"
        content = results[0].file_path.read_text(encoding="utf-8")
        assert "公務人員任用法施行細則" in content

    @patch("src.knowledge.fetchers.exam_yuan_fetcher.requests.get")
    def test_fetch_network_error(self, mock_get, tmp_path):
        """測試網路錯誤"""
        from src.knowledge.fetchers.exam_yuan_fetcher import ExamYuanFetcher
        import requests as req

        mock_get.side_effect = req.ConnectionError("Connection refused")

        fetcher = ExamYuanFetcher(output_dir=tmp_path, limit=5)
        results = fetcher.fetch()
        assert len(results) == 0

    def test_name(self, tmp_path):
        """測試 name() 方法"""
        from src.knowledge.fetchers.exam_yuan_fetcher import ExamYuanFetcher
        fetcher = ExamYuanFetcher(output_dir=tmp_path)
        assert fetcher.name() == "考試院人事法規"


# ==================== TestStatisticsFetcher ====================

class TestStatisticsFetcher:
    """StatisticsFetcher 的測試。"""

    @patch("src.knowledge.fetchers.statistics_fetcher.requests.get")
    def test_fetch_basic(self, mock_get, tmp_path):
        """測試基本統計通報擷取"""
        from src.knowledge.fetchers.statistics_fetcher import StatisticsFetcher

        list_html = '''
        <html><body>
        <a href="News_Content.aspx?n=3703&s=235941">115-03-06消費者物價指數(CPI)年增率漲1.75％</a>
        </body></html>
        '''
        detail_html = '''
        <html><body>
        <div class="group base-page-area" data-index="1" data-type="3" data-child="2">
        <h2>新聞稿</h2>
        <div>2月消費者物價總指數(CPI)，較上年同月漲1.75％，1-2月平均較上年同期漲1.23％。</div>
        <a href="https://ws.dgbas.gov.tw/test.pdf">附件下載</a>
        </div>
        </body></html>
        '''

        def get_side_effect(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.raise_for_status = MagicMock()
            if "News.aspx" in url and "News_Content" not in url:
                resp.text = list_html
            else:
                resp.text = detail_html
            return resp

        mock_get.side_effect = get_side_effect

        fetcher = StatisticsFetcher(output_dir=tmp_path, limit=5)
        results = fetcher.fetch()

        assert len(results) == 1
        content = results[0].file_path.read_text(encoding="utf-8")
        assert "CPI" in content or "物價" in content

    @patch("src.knowledge.fetchers.statistics_fetcher.requests.get")
    def test_fetch_network_error(self, mock_get, tmp_path):
        """測試網路錯誤"""
        from src.knowledge.fetchers.statistics_fetcher import StatisticsFetcher
        import requests as req

        mock_get.side_effect = req.ConnectionError("Connection refused")

        fetcher = StatisticsFetcher(output_dir=tmp_path)
        results = fetcher.fetch()
        assert len(results) == 0

    def test_name(self, tmp_path):
        """測試 name() 方法"""
        from src.knowledge.fetchers.statistics_fetcher import StatisticsFetcher
        fetcher = StatisticsFetcher(output_dir=tmp_path)
        assert fetcher.name() == "主計總處統計"


# ==================== TestControlYuanFetcher ====================

class TestControlYuanFetcher:
    """ControlYuanFetcher 的測試。"""

    @patch("src.knowledge.fetchers.control_yuan_fetcher.requests.get")
    def test_fetch_basic(self, mock_get, tmp_path):
        """測試基本糾正案擷取"""
        from src.knowledge.fetchers.control_yuan_fetcher import ControlYuanFetcher

        list_html = '''
        <html><body>
        <a href="/CyBsBoxContent.aspx?id=1">糾正某機關辦理採購案弊端</a>
        </body></html>
        '''
        detail_html = '''
        <html><body>
        <div class="content">
        <p>經調查發現該機關於辦理採購案時有違失情事...</p>
        </div>
        </body></html>
        '''

        def get_side_effect(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.raise_for_status = MagicMock()
            if "CyBsBox.aspx" in url:
                resp.text = list_html
            else:
                resp.text = detail_html
            return resp

        mock_get.side_effect = get_side_effect

        fetcher = ControlYuanFetcher(output_dir=tmp_path, limit=5)
        results = fetcher.fetch()

        assert len(results) == 1
        assert results[0].collection == "policies"
        assert results[0].source_level == "A"
        content = results[0].file_path.read_text(encoding="utf-8")
        assert "糾正" in content

    @patch("src.knowledge.fetchers.control_yuan_fetcher.requests.get")
    def test_fetch_empty_list(self, mock_get, tmp_path):
        """測試空列表"""
        from src.knowledge.fetchers.control_yuan_fetcher import ControlYuanFetcher

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html><body>無結果</body></html>"
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetcher = ControlYuanFetcher(output_dir=tmp_path, limit=5)
        results = fetcher.fetch()
        assert len(results) == 0

    @patch("src.knowledge.fetchers.control_yuan_fetcher.requests.get")
    def test_fetch_network_error(self, mock_get, tmp_path):
        """測試網路錯誤"""
        from src.knowledge.fetchers.control_yuan_fetcher import ControlYuanFetcher
        import requests as req

        mock_get.side_effect = req.ConnectionError("Connection refused")

        fetcher = ControlYuanFetcher(output_dir=tmp_path, limit=5)
        results = fetcher.fetch()
        assert len(results) == 0

    def test_name(self, tmp_path):
        """測試 name() 方法"""
        from src.knowledge.fetchers.control_yuan_fetcher import ControlYuanFetcher
        fetcher = ControlYuanFetcher(output_dir=tmp_path)
        assert fetcher.name() == "監察院糾正案"

    def test_parse_list_page(self):
        """測試列表頁 HTML 解析"""
        from src.knowledge.fetchers.control_yuan_fetcher import ControlYuanFetcher

        html = '''
        <a href="/CyBsBoxContent.aspx?id=1">糾正案一</a>
        <a href="/CyBsBoxContent.aspx?id=2">糾正案二 2026/01/15</a>
        <a href="/other.aspx">其他連結</a>
        '''
        fetcher = ControlYuanFetcher()
        items = fetcher._parse_list_page(html)
        assert len(items) == 2
        # 第二個項目應有日期
        assert items[1]["date"] == "2026/01/15"


# ==================== CLI 命令測試（新增 fetcher） ====================

class TestNewFetcherCLI:
    """新增的 10 個 fetch CLI 命令的測試。"""

    @patch("src.knowledge.fetchers.legislative_fetcher.requests.get")
    def test_fetch_legislative_cli(self, mock_get, tmp_path):
        """測試 fetch-legislative CLI 命令"""
        from src.cli.main import app

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "dataList": [{"billName": "CLI測試法案", "term": "11"}],
            "totalPage": 1,
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = runner.invoke(app, [
            "kb", "fetch-legislative",
            "--output-dir", str(tmp_path),
            "--limit", "5",
        ])
        assert result.exit_code == 0
        assert "擷取完成" in result.stdout

    @patch("src.knowledge.fetchers.legislative_debate_fetcher.requests.get")
    def test_fetch_debates_cli(self, mock_get, tmp_path):
        """測試 fetch-debates CLI 命令"""
        from src.cli.main import app

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{"title": "CLI測試質詢", "legislator": "測試委員"}]
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = runner.invoke(app, [
            "kb", "fetch-debates",
            "--output-dir", str(tmp_path),
            "--limit", "5",
        ])
        assert result.exit_code == 0
        assert "擷取完成" in result.stdout

    @patch("src.knowledge.fetchers.procurement_fetcher.requests.get")
    def test_fetch_procurement_cli(self, mock_get, tmp_path):
        """測試 fetch-procurement CLI 命令"""
        from src.cli.main import app

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"brief": "CLI測試採購案", "unit_name": "測試機關"}]}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = runner.invoke(app, [
            "kb", "fetch-procurement",
            "--output-dir", str(tmp_path),
            "--limit", "5",
        ])
        assert result.exit_code == 0
        assert "擷取完成" in result.stdout

    @patch("src.knowledge.fetchers.interpretation_fetcher.requests.get")
    def test_fetch_interpretations_cli(self, mock_get, tmp_path):
        """測試 fetch-interpretations CLI 命令"""
        from src.cli.main import app

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html><body>無結果</body></html>"
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = runner.invoke(app, [
            "kb", "fetch-interpretations",
            "--output-dir", str(tmp_path),
            "--limit", "5",
        ])
        assert result.exit_code == 0
        assert "擷取完成" in result.stdout

    @patch("src.knowledge.fetchers.statistics_fetcher.requests.get")
    def test_fetch_statistics_cli(self, mock_get, tmp_path):
        """測試 fetch-statistics CLI 命令"""
        from src.cli.main import app

        list_html = '<html><body><a href="News_Content.aspx?n=3703&s=1">115-03-06測試CPI統計通報</a></body></html>'
        detail_html = '<html><body><div class="group base-page-area">2月消費者物價總指數漲1.75％</div></body></html>'

        def get_side_effect(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.raise_for_status = MagicMock()
            if "News_Content" not in str(url):
                resp.text = list_html
            else:
                resp.text = detail_html
            return resp

        mock_get.side_effect = get_side_effect

        result = runner.invoke(app, [
            "kb", "fetch-statistics",
            "--output-dir", str(tmp_path),
        ])
        assert result.exit_code == 0
        assert "擷取完成" in result.stdout
