"""
自動化評估測試套件：引用正確率、可追溯性、幻覺率、格式一致率
"""
import re
from unittest.mock import MagicMock

import pytest

from src.core.models import PublicDocRequirement
from src.agents.writer import WriterAgent
from src.agents.validators import ValidatorRegistry
from src.document import CitationFormatter, REFERENCE_SECTION_HEADING


# ==================== 測試用 Fixture ====================

@pytest.fixture
def mock_llm():
    """Mock LLM 提供者。"""
    llm = MagicMock()
    llm.generate.return_value = (
        "### 主旨\n測試主旨\n\n"
        "### 說明\n一、依據《公文程式條例》辦理[^1]。\n"
        "二、為加強辦理相關業務。\n\n"
        "### 辦法\n一、請各單位配合辦理。\n"
    )
    llm.embed.return_value = [0.1] * 384
    return llm


@pytest.fixture
def mock_kb():
    """Mock 知識庫管理器。"""
    kb = MagicMock()
    kb.is_available = True
    kb.search_hybrid.return_value = [
        {
            "id": "doc-1",
            "content": "公文程式條例全文內容...",
            "metadata": {
                "title": "公文程式條例",
                "source_level": "A",
                "source_url": "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=A0030055",
                "source": "全國法規資料庫",
                "content_hash": "a1b2c3d4e5f67890",
            },
            "distance": 0.1,
        },
        {
            "id": "doc-2",
            "content": "警政資料...",
            "metadata": {
                "title": "警政統計",
                "source_level": "B",
                "source_url": "https://data.gov.tw/dataset/12345",
                "source": "警政署 OPEN DATA",
                "content_hash": "f0e1d2c3b4a59876",
            },
            "distance": 0.3,
        },
    ]
    return mock_kb


@pytest.fixture
def sample_requirement():
    """標準測試需求。"""
    return PublicDocRequirement(
        doc_type="函",
        urgency="普通",
        sender="測試機關",
        receiver="測試單位",
        subject="關於加強公文品質管理一案",
        reason="為提升公文撰寫品質",
        action_items=["加強管理"],
        attachments=[],
    )


@pytest.fixture
def draft_with_citations():
    """含引用標記的完整草稿。"""
    return """### 主旨
關於加強公文品質管理一案，請查照。

### 說明
一、依據《公文程式條例》辦理[^1]。
二、為提升公文撰寫品質，特函知。

### 辦法
一、請各單位配合辦理[^1][^2]。

### 參考來源 (AI 引用追蹤)
[^1]: [Level A] 公文程式條例 | URL: https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=A0030055 | Hash: a1b2c3d4e5f67890
[^2]: [Level B] 警政統計 | URL: https://data.gov.tw/dataset/12345 | Hash: f0e1d2c3b4a59876"""


@pytest.fixture
def draft_without_citations():
    """不含引用標記的草稿。"""
    return """### 主旨
關於加強公文品質管理一案，請查照。

### 說明
一、依據公文程式條例辦理。
二、為提升公文撰寫品質，特函知。

### 辦法
一、請各單位配合辦理。"""


@pytest.fixture
def draft_skeleton_mode():
    """骨架模式草稿。"""
    return """> **注意**：本草稿為骨架模式，知識庫中未找到相關 evidence。
> 所有法律主張均標記為「待補依據」，請手動補充 Level A 權威來源。

### 主旨
測試主旨

### 說明
一、待補依據。"""


# ==================== TestCitationCorrectness ====================

class TestCitationCorrectness:
    """引用正確率：每個 [^n] 是否對應到實際 evidence。"""

    def test_all_citations_have_matching_reference(self, draft_with_citations):
        """草稿中所有 [^n] 都應在 ### 參考來源 中有對應條目"""
        # 提取正文中的引用標記
        body_citations = set(re.findall(r"\[\^(\d+)\]", draft_with_citations.split("### 參考來源")[0]))
        # 提取參考來源中的定義
        ref_section = draft_with_citations.split("### 參考來源")[1] if "### 參考來源" in draft_with_citations else ""
        ref_definitions = set(re.findall(r"\[\^(\d+)\]:", ref_section))

        # 所有引用都應有定義
        missing = body_citations - ref_definitions
        assert not missing, f"引用標記 {missing} 在參考來源中缺少定義"

    def test_no_orphan_references(self, draft_with_citations):
        """### 參考來源 中的條目都應在草稿正文被引用"""
        body_part = draft_with_citations.split("### 參考來源")[0]
        ref_section = draft_with_citations.split("### 參考來源")[1] if "### 參考來源" in draft_with_citations else ""

        body_citations = set(re.findall(r"\[\^(\d+)\]", body_part))
        ref_definitions = set(re.findall(r"\[\^(\d+)\]:", ref_section))

        orphans = ref_definitions - body_citations
        assert not orphans, f"參考來源條目 {orphans} 未被正文引用"

    def test_draft_without_citations_has_no_refs(self, draft_without_citations):
        """無引用標記的草稿不應有參考來源段落"""
        assert "### 參考來源" not in draft_without_citations


# ==================== TestTraceability ====================

class TestTraceability:
    """可追溯性：引用的 URL 格式是否正確。"""

    def test_level_a_citations_have_valid_urls(self, draft_with_citations):
        """Level A 引用應包含有效的 source_url"""
        ref_section = draft_with_citations.split("### 參考來源")[1]
        level_a_refs = re.findall(r"\[Level A\].*?URL:\s*(https?://\S+)", ref_section)
        assert len(level_a_refs) > 0, "至少應有一個 Level A 引用含 URL"
        for url in level_a_refs:
            assert url.startswith("https://"), f"URL 應為 HTTPS: {url}"

    def test_urls_point_to_official_domains(self, draft_with_citations):
        """source_url 應指向官方域名"""
        ref_section = draft_with_citations.split("### 參考來源")[1]
        urls = re.findall(r"URL:\s*(https?://\S+)", ref_section)

        official_domains = {"gazette.nat.gov.tw", "law.moj.gov.tw", "data.gov.tw"}
        for url in urls:
            # 移除尾部的 | 或空格
            url = url.rstrip("|").strip()
            domain_match = re.search(r"https?://([^/]+)", url)
            if domain_match:
                domain = domain_match.group(1)
                assert any(d in domain for d in official_domains), f"URL 域名 {domain} 非官方來源"

    def test_content_hash_present_in_references(self, draft_with_citations):
        """引用應包含 content_hash"""
        ref_section = draft_with_citations.split("### 參考來源")[1]
        hash_matches = re.findall(r"Hash:\s*([a-f0-9]+)", ref_section)
        assert len(hash_matches) > 0, "至少應有一個引用含 content_hash"
        for h in hash_matches:
            assert len(h) == 16, f"content_hash 長度應為 16 字元，實際為 {len(h)}"


# ==================== TestHallucinationPrevention ====================

class TestHallucinationPrevention:
    """幻覺率：未被引用支持的關鍵主張比例。"""

    def test_legal_assertions_have_citations(self, draft_with_citations):
        """「依據 xxx」句型應附帶 [^n] 或 【待補依據】"""
        # 找到所有「依據...」句型
        body_part = draft_with_citations.split("### 參考來源")[0]
        yiju_matches = list(re.finditer(r"依據[^。\n]{2,30}", body_part))

        for m in yiju_matches:
            # 檢查句子附近是否有引用標記
            start = max(0, m.start() - 5)
            end = min(len(body_part), m.end() + 15)
            context = body_part[start:end]
            has_citation = "[^" in context or "【待補依據】" in context
            assert has_citation, f"法律主張「{m.group(0)}」缺少引用標記"

    def test_no_fabricated_law_names(self):
        """不應出現不在知識庫中的法規名稱"""
        known_laws = {"公文程式條例", "行政程序法", "中央法規標準法"}
        draft_text = "依據《公文程式條例》及《行政程序法》辦理[^1][^2]。"

        # 提取書名號中的法規名稱
        cited_laws = set(re.findall(r"《(.+?)》", draft_text))
        unknown = cited_laws - known_laws
        assert not unknown, f"引用了未知法規：{unknown}"

    def test_skeleton_mode_on_no_evidence(self, mock_llm):
        """無 evidence 時應進入骨架模式（含警告標記）"""
        mock_kb = MagicMock()
        mock_kb.is_available = True
        # search_hybrid 回傳空結果
        mock_kb.search_hybrid.return_value = []

        writer = WriterAgent(mock_llm, mock_kb)
        requirement = PublicDocRequirement(
            doc_type="函",
            sender="測試",
            receiver="測試",
            subject="測試",
        )
        draft = writer.write_draft(requirement)

        assert "骨架模式" in draft
        assert "待補依據" in draft

    def test_skeleton_mode_warning_content(self, draft_skeleton_mode):
        """骨架模式草稿應包含適當警告"""
        assert "骨架模式" in draft_skeleton_mode
        assert "Level A" in draft_skeleton_mode


# ==================== TestFormatConsistency ====================

class TestFormatConsistency:
    """格式一致率：模板欄位完整性。"""

    def test_draft_has_required_sections(self, draft_with_citations):
        """草稿應包含主旨/說明/辦法等必要段落"""
        assert "### 主旨" in draft_with_citations
        assert "### 說明" in draft_with_citations
        assert "### 辦法" in draft_with_citations

    def test_reference_section_format(self, draft_with_citations):
        """參考來源段落格式正確"""
        assert "### 參考來源" in draft_with_citations
        ref_section = draft_with_citations.split("### 參考來源")[1]

        # 每個引用應符合格式
        ref_lines = [line for line in ref_section.strip().split("\n") if line.strip().startswith("[^")]
        assert len(ref_lines) >= 1

        for line in ref_lines:
            # 驗證格式：[^n]: [Level X] 標題 | URL: ... | Hash: ...
            assert re.match(r"\[\^\d+\]:\s*\[Level [AB]\]", line), f"引用格式錯誤: {line}"

    def test_reference_hash_format(self, draft_with_citations):
        """參考來源中的 Hash 格式正確"""
        ref_section = draft_with_citations.split("### 參考來源")[1]
        hash_entries = re.findall(r"Hash:\s*([a-f0-9]+)", ref_section)
        for h in hash_entries:
            assert len(h) == 16, f"Hash 長度應為 16: {h}"


# ==================== TestEvidencePresenceValidator ====================

class TestEvidencePresenceValidator:
    """check_evidence_presence 驗證器的單元測試。"""

    def test_detects_missing_reference_section(self):
        """無參考來源段落時應報錯"""
        registry = ValidatorRegistry()
        errors = registry.check_evidence_presence("### 主旨\n測試內容")
        assert any("參考來源" in e["description"] for e in errors)

    def test_detects_missing_citation_marks(self):
        """無引用標記時應報錯"""
        registry = ValidatorRegistry()
        draft = "### 主旨\n測試內容\n\n### 參考來源 (AI 引用追蹤)\n無引用"
        errors = registry.check_evidence_presence(draft)
        assert any("[^n]" in e["description"] for e in errors)

    def test_passes_with_valid_citations(self):
        """有引用標記和參考來源段落時應通過"""
        registry = ValidatorRegistry()
        draft = "依據法規辦理[^1]。\n\n### 參考來源 (AI 引用追蹤)\n[^1]: [Level A] 某法規"
        errors = registry.check_evidence_presence(draft)
        assert len(errors) == 0

    def test_detects_both_issues(self):
        """同時缺少參考來源和引用標記"""
        registry = ValidatorRegistry()
        errors = registry.check_evidence_presence("純文字草稿，無任何引用。")
        assert len(errors) == 2


# ==================== TestWriterAgentIntegration ====================

class TestWriterAgentIntegration:
    """WriterAgent 整合測試：content_hash 和 search_hybrid。"""

    def test_writer_includes_hash_in_references(self, mock_llm):
        """WriterAgent 生成的參考來源應包含 Hash"""
        mock_kb = MagicMock()
        mock_kb.is_available = True
        mock_kb.search_hybrid.return_value = [
            {
                "id": "doc-1",
                "content": "測試內容",
                "metadata": {
                    "title": "測試法規",
                    "source_level": "A",
                    "source_url": "https://law.moj.gov.tw/test",
                    "source": "全國法規資料庫",
                    "content_hash": "abcdef1234567890",
                },
                "distance": 0.1,
            },
        ]

        writer = WriterAgent(mock_llm, mock_kb)
        requirement = PublicDocRequirement(
            doc_type="函",
            sender="測試",
            receiver="測試",
            subject="測試",
        )
        draft = writer.write_draft(requirement)

        assert "Hash: abcdef1234567890" in draft

    def test_writer_calls_search_hybrid(self, mock_llm):
        """WriterAgent 應使用 search_hybrid 而非 search_examples"""
        mock_kb = MagicMock()
        mock_kb.is_available = True
        mock_kb.search_hybrid.return_value = []

        writer = WriterAgent(mock_llm, mock_kb)
        requirement = PublicDocRequirement(
            doc_type="函",
            sender="測試",
            receiver="測試",
            subject="測試",
        )
        writer.write_draft(requirement)

        # 應該呼叫了 search_hybrid
        assert mock_kb.search_hybrid.call_count >= 1


class TestCitationFormatterQuality:
    def test_meeting_context_normalizes_reference_title(self):
        draft = "本次會議通知請準時出席[^1]。"
        block = CitationFormatter.build_reference_block(
            draft,
            [{"index": 1, "title": "函復國家賠償請求案", "source_level": "A"}],
        )

        assert REFERENCE_SECTION_HEADING in block
        assert "會議通知行政範本" in block
        assert "函復國家賠償請求案" not in block
