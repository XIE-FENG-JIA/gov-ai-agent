"""formatter.py / memory.py / aggregator.py graph node 邊界測試。"""
from unittest.mock import patch, MagicMock

import pytest


class TestFormatDocument:
    """format_document node 測試。"""

    def test_missing_draft(self):
        from src.graph.nodes.formatter import format_document
        result = format_document({"requirement": {"doc_type": "函"}})
        assert result["phase"] == "failed"
        assert "草稿" in result["error"]

    def test_missing_requirement(self):
        from src.graph.nodes.formatter import format_document
        result = format_document({"draft": "主旨：測試"})
        assert result["phase"] == "failed"
        assert "需求" in result["error"]

    def test_exception_handling(self):
        from src.graph.nodes.formatter import format_document
        # requirement_dict 不是合法的 PublicDocRequirement → 觸發異常
        result = format_document({"draft": "主旨：測試", "requirement": {"bad": "data"}})
        assert result["phase"] == "failed"
        assert "失敗" in result["error"]

    def test_success_path(self):
        from src.graph.nodes.formatter import format_document
        with patch("src.agents.template.TemplateEngine") as MockTE:
            MockTE.return_value.parse_draft.return_value = {"主旨": "測試"}
            MockTE.return_value.apply_template.return_value = "格式化後的公文"
            result = format_document({
                "draft": "主旨：測試",
                "requirement": {
                    "doc_type": "函", "subject": "測試", "sender": "A",
                    "receiver": "B", "urgency": "普通件",
                },
            })
        assert result["phase"] == "document_formatted"
        assert result["formatted_draft"] == "格式化後的公文"


class TestFetchOrgMemory:
    """fetch_org_memory node 測試。"""

    def test_no_sender(self):
        from src.graph.nodes.memory import fetch_org_memory
        with patch("src.api.dependencies.get_org_memory", return_value=None):
            result = fetch_org_memory({"requirement": {}})
        assert result["phase"] == "memory_fetched"
        assert result["org_hints"] == ""

    def test_with_sender_and_memory(self):
        from src.graph.nodes.memory import fetch_org_memory
        mock_mem = MagicMock()
        mock_mem.get_writing_hints.return_value = "用語正式"
        with patch("src.api.dependencies.get_org_memory", return_value=mock_mem):
            result = fetch_org_memory({"requirement": {"sender": "台北市政府"}})
        assert result["org_hints"] == "用語正式"

    def test_exception_does_not_block(self):
        from src.graph.nodes.memory import fetch_org_memory
        with patch("src.api.dependencies.get_org_memory", side_effect=RuntimeError("DB down")):
            result = fetch_org_memory({"requirement": {"sender": "X"}})
        assert result["phase"] == "memory_fetched"
        assert result["org_hints"] == ""


class TestGetOrgMemorySentinel:
    """get_org_memory() sentinel 行為：停用時只取鎖一次。"""

    def test_disabled_returns_none_without_repeated_locking(self):
        """org_memory 停用時，第二次呼叫不應再取鎖讀 config。"""
        import src.api.dependencies as deps
        original = deps._org_memory
        try:
            deps._org_memory = deps._UNINITIALIZED
            config = {"organizational_memory": {"enabled": False}}
            with patch.object(deps, "get_config", return_value=config) as mock_gc:
                # 第一次呼叫：應取鎖讀 config，回傳 None
                result1 = deps.get_org_memory()
                assert result1 is None
                assert mock_gc.call_count == 1
                # 第二次呼叫：sentinel 已被替換為 None，不應再取鎖
                result2 = deps.get_org_memory()
                assert result2 is None
                assert mock_gc.call_count == 1  # 不應增加
        finally:
            deps._org_memory = original

    def test_enabled_returns_instance(self):
        """org_memory 啟用時，應回傳 OrganizationalMemory 實例。"""
        import src.api.dependencies as deps
        original = deps._org_memory
        try:
            deps._org_memory = deps._UNINITIALIZED
            config = {
                "organizational_memory": {
                    "enabled": True,
                    "storage_path": "./kb_data/test_prefs.json",
                }
            }
            with patch.object(deps, "get_config", return_value=config), \
                 patch("src.api.dependencies.OrganizationalMemory") as MockOM:
                MockOM.return_value = MagicMock()
                result = deps.get_org_memory()
                assert result is not None
                MockOM.assert_called_once_with(storage_path="./kb_data/test_prefs.json")
        finally:
            deps._org_memory = original


class TestAggregateReviews:
    """aggregate_reviews node 測試——驗證委派 scoring.py 共用函式。"""

    def test_empty_results_returns_safe(self):
        from src.graph.nodes.aggregator import aggregate_reviews
        result = aggregate_reviews({"review_results": []})
        report = result["aggregated_report"]
        assert report["risk_summary"] == "Safe"
        assert report["overall_score"] == 1.0
        assert report["error_count"] == 0

    def test_single_perfect_result(self):
        from src.graph.nodes.aggregator import aggregate_reviews
        result = aggregate_reviews({"review_results": [
            {
                "agent_name": "Format Auditor",
                "issues": [],
                "score": 1.0,
                "confidence": 1.0,
            }
        ]})
        report = result["aggregated_report"]
        assert report["overall_score"] == 1.0
        assert report["risk_summary"] == "Safe"
        assert result["phase"] == "reviews_aggregated"

    def test_errors_affect_risk(self):
        from src.graph.nodes.aggregator import aggregate_reviews
        result = aggregate_reviews({"review_results": [
            {
                "agent_name": "Format Auditor",
                "issues": [{
                    "category": "format",
                    "severity": "error",
                    "risk_level": "high",
                    "location": "主旨",
                    "description": "缺少主旨",
                }],
                "score": 0.5,
                "confidence": 1.0,
            }
        ]})
        report = result["aggregated_report"]
        assert report["error_count"] == 1
        assert report["risk_summary"] != "Safe"

    def test_warnings_counted(self):
        from src.graph.nodes.aggregator import aggregate_reviews
        result = aggregate_reviews({"review_results": [
            {
                "agent_name": "Style Checker",
                "issues": [{
                    "category": "style",
                    "severity": "warning",
                    "risk_level": "low",
                    "location": "說明",
                    "description": "口語化",
                }],
                "score": 0.8,
                "confidence": 1.0,
            }
        ]})
        report = result["aggregated_report"]
        assert report["warning_count"] == 1
        assert report["error_count"] == 0

    def test_multiple_agents_weighted(self):
        """驗證不同類別的 agent 使用不同權重（format > style）。"""
        from src.graph.nodes.aggregator import aggregate_reviews
        result = aggregate_reviews({"review_results": [
            {
                "agent_name": "Format Auditor",
                "issues": [],
                "score": 0.5,
                "confidence": 1.0,
            },
            {
                "agent_name": "Style Checker",
                "issues": [],
                "score": 1.0,
                "confidence": 1.0,
            },
        ]})
        report = result["aggregated_report"]
        # format weight=3.0, style weight=1.0 → avg = (0.5*3 + 1.0*1) / (3+1) = 2.5/4 = 0.625
        assert report["overall_score"] == pytest.approx(0.625, abs=0.001)

    def test_scoring_consistency_with_core_module(self):
        """確保 aggregator 使用的評分邏輯與 scoring.py 一致。"""
        from src.graph.nodes.aggregator import aggregate_reviews, _dicts_to_review_results
        from src.core.scoring import calculate_weighted_scores, calculate_risk_scores

        raw = [
            {
                "agent_name": "Fact Checker",
                "issues": [{
                    "category": "fact",
                    "severity": "error",
                    "risk_level": "high",
                    "location": "依據",
                    "description": "法規不存在",
                }],
                "score": 0.3,
                "confidence": 0.9,
            },
        ]
        # 直接呼叫 scoring.py 計算
        models = _dicts_to_review_results(raw)
        expected_ws, expected_tw = calculate_weighted_scores(models)
        expected_es, expected_wws = calculate_risk_scores(models)

        # 透過 aggregator 計算
        result = aggregate_reviews({"review_results": raw})
        report = result["aggregated_report"]

        expected_avg = expected_ws / expected_tw if expected_tw > 0 else 0.0
        assert report["overall_score"] == pytest.approx(round(expected_avg, 4), abs=0.0001)
        assert report["weighted_error_score"] == pytest.approx(round(expected_es, 2), abs=0.01)

    def test_malformed_issue_dict_handled_gracefully(self):
        """格式不完整的 issue dict 不應阻斷流程。"""
        from src.graph.nodes.aggregator import aggregate_reviews
        result = aggregate_reviews({"review_results": [
            {
                "agent_name": "Unknown Agent",
                "issues": [{"bad_key": "value"}],  # 缺少必要欄位
                "score": 0.5,
                "confidence": 1.0,
            }
        ]})
        # 轉換失敗時 issue 被跳過，但不應 crash
        report = result["aggregated_report"]
        assert result["phase"] == "reviews_aggregated"
        assert report["error_count"] == 0

    def test_exception_returns_critical(self):
        """aggregator 內部例外時回傳 Critical 報告。"""
        from src.graph.nodes.aggregator import aggregate_reviews
        with patch(
            "src.graph.nodes.aggregator.calculate_weighted_scores",
            side_effect=RuntimeError("boom"),
        ):
            result = aggregate_reviews({"review_results": [
                {"agent_name": "X", "issues": [], "score": 1.0, "confidence": 1.0}
            ]})
        assert result["aggregated_report"]["risk_summary"] == "Critical"
        assert result["phase"] == "failed"
