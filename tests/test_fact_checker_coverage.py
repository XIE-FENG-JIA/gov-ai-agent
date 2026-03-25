"""FactChecker 覆蓋率補齊測試 — 涵蓋空草稿、mapping 載入、law_verifier 失敗、跨文件類型比對。"""

from unittest.mock import MagicMock, patch
from types import SimpleNamespace

import pytest

from src.agents.fact_checker import FactChecker, _load_regulation_doc_type_mapping
from src.core.review_models import ReviewResult


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.generate.return_value = '{"issues": [], "score": 0.9}'
    return llm


# ==================== _load_regulation_doc_type_mapping ====================


class TestLoadRegulationDocTypeMapping:
    def test_mapping_file_not_found(self, tmp_path):
        """映射檔不存在時回傳空字典"""
        with patch("src.agents.fact_checker._MAPPING_PATH", tmp_path / "nonexistent.yaml"):
            result = _load_regulation_doc_type_mapping()
        assert result == {}

    def test_mapping_file_valid(self, tmp_path):
        """正常 YAML 檔回傳 regulations 字典"""
        mapping_file = tmp_path / "mapping.yaml"
        mapping_file.write_text(
            "regulations:\n  行政程序法:\n    applicable_doc_types: [函, 令]\n",
            encoding="utf-8",
        )
        with patch("src.agents.fact_checker._MAPPING_PATH", mapping_file):
            result = _load_regulation_doc_type_mapping()
        assert "行政程序法" in result
        assert result["行政程序法"]["applicable_doc_types"] == ["函", "令"]

    def test_mapping_file_non_dict(self, tmp_path):
        """YAML 內容非字典時回傳空字典"""
        mapping_file = tmp_path / "mapping.yaml"
        mapping_file.write_text("- just\n- a\n- list\n", encoding="utf-8")
        with patch("src.agents.fact_checker._MAPPING_PATH", mapping_file):
            result = _load_regulation_doc_type_mapping()
        assert result == {}

    def test_mapping_file_parse_error(self, tmp_path):
        """YAML 解析失敗時回傳空字典"""
        mapping_file = tmp_path / "mapping.yaml"
        mapping_file.write_text("{{bad yaml", encoding="utf-8")
        with patch("src.agents.fact_checker._MAPPING_PATH", mapping_file):
            result = _load_regulation_doc_type_mapping()
        assert result == {}

    def test_mapping_file_no_regulations_key(self, tmp_path):
        """YAML 內無 regulations 鍵時回傳空字典"""
        mapping_file = tmp_path / "mapping.yaml"
        mapping_file.write_text("other_key: value\n", encoding="utf-8")
        with patch("src.agents.fact_checker._MAPPING_PATH", mapping_file):
            result = _load_regulation_doc_type_mapping()
        assert result == {}


# ==================== FactChecker.check ====================


class TestFactCheckerCheck:
    def test_empty_draft(self, mock_llm):
        """空草稿回傳預設結果，不呼叫 LLM"""
        fc = FactChecker(mock_llm)
        result = fc.check("", doc_type="函")
        assert isinstance(result, ReviewResult)
        assert result.agent_name == "Fact Checker"
        assert result.issues == []
        mock_llm.generate.assert_not_called()

    def test_whitespace_only_draft(self, mock_llm):
        """空白草稿回傳預設結果"""
        fc = FactChecker(mock_llm)
        result = fc.check("   \n  ", doc_type="函")
        assert result.issues == []
        mock_llm.generate.assert_not_called()

    def test_normal_draft_calls_llm(self, mock_llm):
        """正常草稿呼叫 LLM"""
        fc = FactChecker(mock_llm)
        result = fc.check("### 主旨\n依據行政程序法辦理。", doc_type="函")
        assert isinstance(result, ReviewResult)
        mock_llm.generate.assert_called_once()

    def test_llm_failure(self, mock_llm):
        """LLM 呼叫失敗回傳 confidence=0"""
        mock_llm.generate.side_effect = RuntimeError("timeout")
        fc = FactChecker(mock_llm)
        result = fc.check("### 主旨\n測試", doc_type="函")
        assert result.score == 0.0
        assert result.confidence == 0.0

    def test_long_draft_truncated(self, mock_llm):
        """超長草稿被截斷但不崩潰"""
        from src.core.constants import MAX_DRAFT_LENGTH
        fc = FactChecker(mock_llm)
        long_draft = "### 主旨\n" + "A" * (MAX_DRAFT_LENGTH + 100)
        result = fc.check(long_draft, doc_type="函")
        assert isinstance(result, ReviewResult)
        mock_llm.generate.assert_called_once()

    def test_with_law_verifier_success(self, mock_llm):
        """有 law_verifier 時使用即時驗證結果"""
        verifier = MagicMock()
        verifier.verify_citations.return_value = []
        fc = FactChecker(mock_llm, law_verifier=verifier)
        result = fc.check("依據行政程序法辦理。", doc_type="函")
        verifier.verify_citations.assert_called_once()
        assert isinstance(result, ReviewResult)

    def test_with_law_verifier_failure_degrades(self, mock_llm):
        """law_verifier 失敗時降級為純 LLM"""
        verifier = MagicMock()
        verifier.verify_citations.side_effect = RuntimeError("API down")
        fc = FactChecker(mock_llm, law_verifier=verifier)
        result = fc.check("依據行政程序法辦理。", doc_type="函")
        # 不應崩潰，仍然呼叫 LLM
        assert isinstance(result, ReviewResult)
        mock_llm.generate.assert_called_once()

    def test_no_doc_type(self, mock_llm):
        """不傳 doc_type 時不做跨文件類型比對"""
        fc = FactChecker(mock_llm)
        result = fc.check("### 主旨\n測試", doc_type=None)
        assert isinstance(result, ReviewResult)


# ==================== _cross_reference_doc_type ====================


class TestCrossReferenceDocType:
    def _make_check(self, law_name, law_exists=True):
        """建立模擬的 citation check 物件"""
        chk = SimpleNamespace()
        chk.law_exists = law_exists
        chk.citation = SimpleNamespace(law_name=law_name)
        return chk

    def test_law_not_exists_skipped(self, mock_llm):
        """不存在的法規不做交叉比對"""
        fc = FactChecker(mock_llm)
        fc._reg_doc_mapping = {"行政程序法": {"applicable_doc_types": ["函"]}}
        checks = [self._make_check("行政程序法", law_exists=False)]
        lines = fc._cross_reference_doc_type(checks, "函")
        assert lines == []

    def test_law_not_in_mapping_skipped(self, mock_llm):
        """不在映射表中的法規被跳過"""
        fc = FactChecker(mock_llm)
        fc._reg_doc_mapping = {}
        checks = [self._make_check("未知法規")]
        lines = fc._cross_reference_doc_type(checks, "函")
        assert lines == []

    def test_doc_type_in_not_applicable(self, mock_llm):
        """文件類型在明確排除清單中"""
        fc = FactChecker(mock_llm)
        fc._reg_doc_mapping = {
            "某法": {"applicable_doc_types": ["令"], "not_applicable": ["函"]},
        }
        checks = [self._make_check("某法")]
        lines = fc._cross_reference_doc_type(checks, "函")
        assert any("不適用" in l and "❌" in l for l in lines)

    def test_doc_type_not_in_applicable(self, mock_llm):
        """文件類型不在適用清單中（但未明確排除）"""
        fc = FactChecker(mock_llm)
        fc._reg_doc_mapping = {
            "某法": {"applicable_doc_types": ["令"], "not_applicable": []},
        }
        checks = [self._make_check("某法")]
        lines = fc._cross_reference_doc_type(checks, "函")
        assert any("⚠️" in l for l in lines)

    def test_doc_type_applicable_no_warning(self, mock_llm):
        """文件類型在適用清單中 — 無警告"""
        fc = FactChecker(mock_llm)
        fc._reg_doc_mapping = {
            "某法": {"applicable_doc_types": ["函", "令"], "not_applicable": []},
        }
        checks = [self._make_check("某法")]
        lines = fc._cross_reference_doc_type(checks, "函")
        assert lines == []

    def test_no_applicable_list_no_warning(self, mock_llm):
        """映射無 applicable_doc_types 時不產生警告"""
        fc = FactChecker(mock_llm)
        fc._reg_doc_mapping = {
            "某法": {"not_applicable": []},
        }
        checks = [self._make_check("某法")]
        lines = fc._cross_reference_doc_type(checks, "函")
        assert lines == []


# ==================== FactChecker with cross-ref in check() ====================


class TestFactCheckerWithCrossRef:
    def test_cross_ref_included_in_prompt(self, mock_llm):
        """有 law_verifier 回傳且有 mapping 時，prompt 中包含 cross-ref"""
        verifier = MagicMock()
        chk = SimpleNamespace(
            law_exists=True,
            actual_content="行政程序法條文內容",
            citation=SimpleNamespace(
                law_name="行政程序法",
                article_no="第1條",
                original_text="行政程序法",
            ),
        )
        verifier.verify_citations.return_value = [chk]

        fc = FactChecker(mock_llm, law_verifier=verifier)
        fc._reg_doc_mapping = {
            "行政程序法": {"applicable_doc_types": ["令"], "not_applicable": ["公告"]},
        }

        # format_verification_results 是在 check() 內部 local import，
        # 需要 patch 原始模組路徑
        with patch("src.knowledge.realtime_lookup.format_verification_results", return_value="mock-result"):
            fc.check("依據行政程序法辦理。", doc_type="公告")

        # 確認 LLM prompt 中包含 cross-ref 內容
        call_args = mock_llm.generate.call_args
        prompt = call_args[0][0]
        assert "Cross Reference" in prompt
        assert "不適用" in prompt
