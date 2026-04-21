"""FactChecker 增強功能測試 — 虛假引用嚴重度、法規-文件類型交叉比對。"""
import json
import io
import zipfile
from unittest.mock import MagicMock, patch

import pytest

from src.knowledge.realtime_lookup import (
    Citation,
    CitationCheck,
    LawVerifier,
)
from src.agents.fact_checker import FactChecker, _load_regulation_doc_type_mapping


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_law_json(laws: list[dict]) -> bytes:
    payload = json.dumps({"Laws": laws}, ensure_ascii=False).encode("utf-8")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("ChLaw.json", payload)
    return buf.getvalue()


SAMPLE_LAWS = [
    {
        "PCode": "A0030055",
        "LawName": "行政程序法",
        "LawArticles": [
            {"ArticleNo": "第 1 條", "ArticleContent": "為使行政行為遵循公正、公開與民主之程序。"},
            {"ArticleNo": "第 100 條", "ArticleContent": "書面之行政處分自送達相對人及已知之利害關係人起。"},
        ],
    },
    {
        "PCode": "N0060001",
        "LawName": "廢棄物清理法",
        "LawArticles": [
            {"ArticleNo": "第 1 條", "ArticleContent": "為有效清除、處理廢棄物，改善環境衛生，維護國民健康。"},
            {"ArticleNo": "第 28 條", "ArticleContent": "事業廢棄物之清理，除再利用方式外。"},
        ],
    },
    {
        "PCode": "S0020001",
        "LawName": "公務人員任用法",
        "LawArticles": [
            {"ArticleNo": "第 1 條", "ArticleContent": "公務人員之任用，依本法行之。"},
        ],
    },
]


@pytest.fixture(autouse=True)
def _clear_caches():
    LawVerifier._cache = None
    yield
    LawVerifier._cache = None


# ===========================================================================
# 虛假引用必須標記為 error（非 warning） — CEO 品質紅線
# ===========================================================================

class TestFakeCitationSeverity:
    """驗證 FactChecker prompt 中虛假引用被標為 error。"""

    @patch("src.knowledge.realtime_lookup._request_with_retry")
    def test_nonexistent_law_flagged_as_error_in_prompt(self, mock_req):
        """虛構法規名稱 → prompt 指示標記為 error。"""
        mock_resp = MagicMock()
        mock_resp.content = _make_law_json(SAMPLE_LAWS)
        mock_req.return_value = mock_resp

        mock_llm = MagicMock()
        mock_llm.generate.return_value = json.dumps({
            "issues": [{
                "severity": "error",
                "location": "第 1 行",
                "description": "虛構法規：政府資訊安全管理辦法不存在於全國法規資料庫",
                "suggestion": "請確認正確法規名稱",
            }],
            "score": 0.3,
        })

        verifier = LawVerifier()
        checker = FactChecker(mock_llm, law_verifier=verifier)
        checker.check("依據政府資訊安全管理辦法第5條辦理。")

        # 確認 prompt 中包含「error」而非「warning」的虛假引用指示
        call_args = mock_llm.generate.call_args
        prompt = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
        assert "NEVER \"warning\"" in prompt or "severity=\"error\"" in prompt
        assert "quality red line" in prompt

    @patch("src.knowledge.realtime_lookup._request_with_retry")
    def test_wrong_article_number_flagged_as_error_in_prompt(self, mock_req):
        """法規存在但條文號不存在 → prompt 指示標記為 error。"""
        mock_resp = MagicMock()
        mock_resp.content = _make_law_json(SAMPLE_LAWS)
        mock_req.return_value = mock_resp

        mock_llm = MagicMock()
        mock_llm.generate.return_value = json.dumps({
            "issues": [{
                "severity": "error",
                "location": "第 1 行",
                "description": "行政程序法第999條不存在",
                "suggestion": "請確認正確條文號",
            }],
            "score": 0.4,
        })

        verifier = LawVerifier()
        checker = FactChecker(mock_llm, law_verifier=verifier)
        checker.check("依據行政程序法第999條辦理。")

        call_args = mock_llm.generate.call_args
        prompt = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
        # prompt 中應有 ❌ 標記（條文不存在）
        assert "❌" in prompt
        assert "第 999 條" in prompt or "999" in prompt

    @patch("src.knowledge.realtime_lookup._request_with_retry")
    def test_valid_citation_not_flagged(self, mock_req):
        """正確引用 → prompt 中出現 ✅。"""
        mock_resp = MagicMock()
        mock_resp.content = _make_law_json(SAMPLE_LAWS)
        mock_req.return_value = mock_resp

        mock_llm = MagicMock()
        mock_llm.generate.return_value = '{"issues": [], "score": 0.95}'

        verifier = LawVerifier()
        checker = FactChecker(mock_llm, law_verifier=verifier)
        checker.check("依據行政程序法第100條辦理。")

        call_args = mock_llm.generate.call_args
        prompt = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
        assert "✅" in prompt
        assert "行政程序法" in prompt

    @patch("src.knowledge.realtime_lookup._request_with_retry")
    def test_nonexistent_law_becomes_repo_owned_error(self, mock_req):
        """即使 LLM 漏報，repo-owned 檢查也要保留 error。"""
        mock_resp = MagicMock()
        mock_resp.content = _make_law_json(SAMPLE_LAWS)
        mock_req.return_value = mock_resp

        mock_llm = MagicMock()
        mock_llm.generate.return_value = '{"issues": [], "score": 0.98}'

        verifier = LawVerifier()
        checker = FactChecker(mock_llm, law_verifier=verifier)
        result = checker.check("依據政府資訊安全管理辦法第5條辦理。")

        assert any(
            issue.severity == "error" and "不存在於全國法規資料庫" in issue.description
            for issue in result.issues
        )

    @patch("src.knowledge.realtime_lookup._request_with_retry")
    def test_verified_law_without_reference_becomes_warning(self, mock_req):
        """有 realtime 驗證但沒有 repo evidence 時，不可靜默放過。"""
        mock_resp = MagicMock()
        mock_resp.content = _make_law_json(SAMPLE_LAWS)
        mock_req.return_value = mock_resp

        mock_llm = MagicMock()
        mock_llm.generate.return_value = '{"issues": [], "score": 0.98}'

        verifier = LawVerifier()
        checker = FactChecker(mock_llm, law_verifier=verifier)
        result = checker.check("依據行政程序法第100條辦理。")

        assert any(
            issue.severity == "warning" and "未在參考來源段落找到對應 repo 證據" in issue.description
            for issue in result.issues
        )

    @patch("src.knowledge.realtime_lookup._request_with_retry")
    def test_verified_law_with_reference_avoids_repo_warning(self, mock_req):
        """有對應 repo reference 時，不應多打一條未驗證引用。"""
        mock_resp = MagicMock()
        mock_resp.content = _make_law_json(SAMPLE_LAWS)
        mock_req.return_value = mock_resp

        mock_llm = MagicMock()
        mock_llm.generate.return_value = '{"issues": [], "score": 0.98}'

        verifier = LawVerifier()
        checker = FactChecker(mock_llm, law_verifier=verifier)
        draft = (
            "依據行政程序法第100條辦理。[^1]\n\n"
            "## 參考來源\n"
            "[^1]: [Level A] 行政程序法第100條 | URL: https://law.moj.gov.tw/example | Hash: abc123\n"
        )
        result = checker.check(draft)

        assert not any("未在參考來源段落找到對應 repo 證據" in issue.description for issue in result.issues)


# ===========================================================================
# 法規-文件類型交叉比對
# ===========================================================================

class TestDocTypeCrossReference:
    """驗證法規-文件類型映射表交叉比對功能。"""

    def test_load_mapping_yaml(self):
        """映射表 YAML 可正確載入。"""
        mapping = _load_regulation_doc_type_mapping()
        assert isinstance(mapping, dict)
        assert "公文程式條例" in mapping
        assert "廢棄物清理法" in mapping
        assert "applicable_doc_types" in mapping["公文程式條例"]

    @patch("src.knowledge.realtime_lookup._request_with_retry")
    def test_inappropriate_citation_detected(self, mock_req):
        """引用環保法規於人事令 → 交叉比對偵測到不適當。"""
        mock_resp = MagicMock()
        mock_resp.content = _make_law_json(SAMPLE_LAWS)
        mock_req.return_value = mock_resp

        mock_llm = MagicMock()
        mock_llm.generate.return_value = json.dumps({
            "issues": [{
                "severity": "error",
                "location": "第 1 行",
                "description": "廢棄物清理法不適用於人事令",
                "suggestion": "請使用適當的法規依據",
            }],
            "score": 0.3,
        })

        verifier = LawVerifier()
        checker = FactChecker(mock_llm, law_verifier=verifier)
        checker.check(
            "依據廢棄物清理法第28條辦理人事調動。",
            doc_type="人事令",
        )

        call_args = mock_llm.generate.call_args
        prompt = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
        assert "Cross Reference" in prompt
        assert "不適用" in prompt or "INAPPROPRIATE" in prompt

    @patch("src.knowledge.realtime_lookup._request_with_retry")
    def test_appropriate_citation_no_flag(self, mock_req):
        """引用環保法規於環保公告 → 無交叉比對警告。"""
        mock_resp = MagicMock()
        mock_resp.content = _make_law_json(SAMPLE_LAWS)
        mock_req.return_value = mock_resp

        mock_llm = MagicMock()
        mock_llm.generate.return_value = '{"issues": [], "score": 0.95}'

        verifier = LawVerifier()
        checker = FactChecker(mock_llm, law_verifier=verifier)
        checker.check(
            "依據廢棄物清理法第28條辦理。",
            doc_type="環保公告",
        )

        call_args = mock_llm.generate.call_args
        prompt = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
        # 環保公告引用環保法規，不應有交叉比對警告
        assert "不適用" not in prompt

    @patch("src.knowledge.realtime_lookup._request_with_retry")
    def test_universal_law_always_appropriate(self, mock_req):
        """公文程式條例適用於所有文件類型。"""
        mock_resp = MagicMock()
        # 加入公文程式條例到 SAMPLE_LAWS
        laws = SAMPLE_LAWS + [{
            "PCode": "A0030018",
            "LawName": "公文程式條例",
            "LawArticles": [
                {"ArticleNo": "第 1 條", "ArticleContent": "公文程式，依本條例之規定。"},
            ],
        }]
        mock_resp.content = _make_law_json(laws)
        mock_req.return_value = mock_resp

        mock_llm = MagicMock()
        mock_llm.generate.return_value = '{"issues": [], "score": 0.95}'

        verifier = LawVerifier()
        checker = FactChecker(mock_llm, law_verifier=verifier)

        # 各種文件類型都不應對公文程式條例發出交叉比對警告
        for dt in ["函", "公告", "人事令", "環保公告", "採購公告"]:
            checker.check("依據公文程式條例第1條辦理。", doc_type=dt)
            call_args = mock_llm.generate.call_args
            prompt = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
            assert "不適用" not in prompt, f"公文程式條例不應在 {dt} 中被標記為不適用"

    def test_no_doc_type_skips_cross_reference(self):
        """未提供 doc_type 時不做交叉比對。"""
        mock_llm = MagicMock()
        mock_llm.generate.return_value = '{"issues": [], "score": 0.9}'

        checker = FactChecker(mock_llm, law_verifier=None)
        checker.check("依據公文程式條例辦理。")

        call_args = mock_llm.generate.call_args
        prompt = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
        assert "Cross Reference" not in prompt


# ===========================================================================
# _cross_reference_doc_type 單元測試
# ===========================================================================

class TestCrossReferenceMethod:
    """直接測試 _cross_reference_doc_type 方法。"""

    def test_not_applicable_returns_error_marker(self):
        """明確排除的文件類型 → ❌ 標記。"""
        mock_llm = MagicMock()
        checker = FactChecker(mock_llm)

        checks = [
            CitationCheck(
                citation=Citation("廢棄物清理法", "28", "依據廢棄物清理法第28條", "第 1 行"),
                law_exists=True,
                article_exists=True,
                actual_content="事業廢棄物之清理...",
                pcode="N0060001",
                confidence=1.0,
            )
        ]

        lines = checker._cross_reference_doc_type(checks, "人事令")
        assert len(lines) == 1
        assert "❌" in lines[0]
        assert "不適用" in lines[0]

    def test_not_in_applicable_returns_warning_marker(self):
        """不在適用清單但也不在排除清單 → ⚠️ 標記。"""
        mock_llm = MagicMock()
        checker = FactChecker(mock_llm)

        checks = [
            CitationCheck(
                citation=Citation("廢棄物清理法", "28", "依據廢棄物清理法第28條", "第 1 行"),
                law_exists=True,
                article_exists=True,
                actual_content="事業廢棄物之清理...",
                pcode="N0060001",
                confidence=1.0,
            )
        ]

        lines = checker._cross_reference_doc_type(checks, "訴願決定書")
        assert len(lines) == 1
        assert "⚠️" in lines[0]

    def test_applicable_returns_empty(self):
        """適用的文件類型 → 不產生警告。"""
        mock_llm = MagicMock()
        checker = FactChecker(mock_llm)

        checks = [
            CitationCheck(
                citation=Citation("廢棄物清理法", "28", "依據廢棄物清理法第28條", "第 1 行"),
                law_exists=True,
                article_exists=True,
                actual_content="事業廢棄物之清理...",
                pcode="N0060001",
                confidence=1.0,
            )
        ]

        lines = checker._cross_reference_doc_type(checks, "環保公告")
        assert len(lines) == 0

    def test_unknown_law_skipped(self):
        """映射表中沒有的法規 → 不做比對。"""
        mock_llm = MagicMock()
        checker = FactChecker(mock_llm)

        checks = [
            CitationCheck(
                citation=Citation("某個未知法規", None, "依據某個未知法規", "第 1 行"),
                law_exists=True,
                article_exists=None,
                actual_content=None,
                pcode="X0000000",
                confidence=0.8,
            )
        ]

        lines = checker._cross_reference_doc_type(checks, "人事令")
        assert len(lines) == 0

    def test_nonexistent_law_skipped(self):
        """法規不存在時 → 不做交叉比對（由主驗證流程處理）。"""
        mock_llm = MagicMock()
        checker = FactChecker(mock_llm)

        checks = [
            CitationCheck(
                citation=Citation("廢棄物清理法", "28", "依據廢棄物清理法第28條", "第 1 行"),
                law_exists=False,
                article_exists=None,
                actual_content=None,
                pcode=None,
                confidence=0.0,
            )
        ]

        lines = checker._cross_reference_doc_type(checks, "人事令")
        assert len(lines) == 0


# ===========================================================================
# 語義相似度交叉比對
# ===========================================================================

class TestSemanticSimilarityCheck:
    """測試 _semantic_similarity_check 方法。"""

    def test_high_similarity_no_flag(self):
        """高相似度引用 → 不產生警告。"""
        mock_llm = MagicMock()
        # 模擬 embed 返回相同向量（完全相似）
        mock_llm.embed.return_value = [0.5] * 384
        checker = FactChecker(mock_llm)

        checks = [
            CitationCheck(
                citation=Citation("行政程序法", "1", "依據行政程序法第1條", "第 1 行"),
                law_exists=True,
                article_exists=True,
                actual_content="為使行政行為遵循公正、公開與民主之程序。",
                pcode="A0030055",
                confidence=1.0,
            )
        ]

        draft = "本案依據行政程序法第1條規定辦理。"
        lines = checker._semantic_similarity_check(checks, draft)
        assert len(lines) == 0

    def test_low_similarity_flagged(self):
        """低相似度引用 → 產生 ❌ 警告。"""
        mock_llm = MagicMock()
        # 模擬 embed 返回差異極大的向量
        call_count = [0]
        def mock_embed(text):
            call_count[0] += 1
            if call_count[0] % 2 == 1:
                return [1.0, 0.0, 0.0] * 128  # draft context
            else:
                return [0.0, 1.0, 0.0] * 128  # law content (orthogonal)
        mock_llm.embed.side_effect = mock_embed
        checker = FactChecker(mock_llm)

        checks = [
            CitationCheck(
                citation=Citation("廢棄物清理法", "28", "依據廢棄物清理法第28條", "第 3 行"),
                law_exists=True,
                article_exists=True,
                actual_content="事業廢棄物之清理，除再利用方式外。",
                pcode="N0060001",
                confidence=1.0,
            )
        ]

        draft = "本案依據廢棄物清理法第28條辦理人事異動。"
        lines = checker._semantic_similarity_check(checks, draft)
        assert len(lines) == 1
        assert "❌" in lines[0]
        assert "語義相似度" in lines[0]

    def test_no_article_content_skipped(self):
        """無條文內容時 → 跳過語義比對。"""
        mock_llm = MagicMock()
        checker = FactChecker(mock_llm)

        checks = [
            CitationCheck(
                citation=Citation("行政程序法", None, "依據行政程序法", "第 1 行"),
                law_exists=True,
                article_exists=None,
                actual_content=None,
                pcode="A0030055",
                confidence=1.0,
            )
        ]

        draft = "依據行政程序法辦理。"
        lines = checker._semantic_similarity_check(checks, draft)
        assert len(lines) == 0

    def test_embed_failure_gracefully_handled(self):
        """embedding 失敗時 → 優雅處理，不崩潰。"""
        mock_llm = MagicMock()
        mock_llm.embed.return_value = []  # 失敗
        checker = FactChecker(mock_llm)

        checks = [
            CitationCheck(
                citation=Citation("行政程序法", "1", "依據行政程序法第1條", "第 1 行"),
                law_exists=True,
                article_exists=True,
                actual_content="為使行政行為遵循公正、公開與民主之程序。",
                pcode="A0030055",
                confidence=1.0,
            )
        ]

        draft = "依據行政程序法第1條辦理。"
        lines = checker._semantic_similarity_check(checks, draft)
        assert len(lines) == 0

    def test_cosine_similarity_calculation(self):
        """測試 cosine similarity 計算正確性。"""
        assert FactChecker._cosine_similarity([1, 0], [1, 0]) == pytest.approx(1.0)
        assert FactChecker._cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)
        assert FactChecker._cosine_similarity([1, 0], [-1, 0]) == pytest.approx(-1.0)
        assert FactChecker._cosine_similarity([], []) == 0.0

    @patch("src.knowledge.realtime_lookup._request_with_retry")
    def test_semantic_check_in_full_pipeline(self, mock_req):
        """語義相似度檢查整合到完整 check() 流程。"""
        mock_resp = MagicMock()
        mock_resp.content = _make_law_json(SAMPLE_LAWS)
        mock_req.return_value = mock_resp

        mock_llm = MagicMock()
        # embed 返回正交向量以觸發低相似度
        call_count = [0]
        def mock_embed(text):
            call_count[0] += 1
            if call_count[0] % 2 == 1:
                return [1.0, 0.0, 0.0] * 128
            else:
                return [0.0, 1.0, 0.0] * 128
        mock_llm.embed.side_effect = mock_embed
        mock_llm.generate.return_value = '{"issues": [], "score": 0.9}'

        verifier = LawVerifier()
        checker = FactChecker(mock_llm, law_verifier=verifier)
        checker.check("依據行政程序法第100條辦理人事調動。")

        call_args = mock_llm.generate.call_args
        prompt = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
        assert "Semantic Similarity Check" in prompt
