"""src/graph/ 基礎測試 — state, builder, routing, _execute_via_graph 萃取邏輯"""

import pytest
from unittest.mock import patch, MagicMock


class TestGovDocState:
    """GovDocState TypedDict 結構驗證"""

    def test_state_importable(self):
        from src.graph.state import GovDocState
        assert GovDocState is not None

    def test_state_partial_init(self):
        from src.graph.state import GovDocState
        state: GovDocState = {"user_input": "測試"}
        assert state["user_input"] == "測試"

    def test_state_has_review_results(self):
        """review_results 應存在且為 Annotated list（用於 reducer）"""
        from src.graph.state import GovDocState
        import typing
        hints = typing.get_type_hints(GovDocState, include_extras=True)
        assert "review_results" in hints


class TestBuildGraph:
    """build_graph() 功能驗證"""

    def test_build_graph_returns_compiled(self):
        from src.graph.builder import build_graph
        g = build_graph()
        assert hasattr(g, "invoke")
        assert hasattr(g, "nodes")

    def test_graph_has_expected_nodes(self):
        from src.graph.builder import build_graph
        g = build_graph()
        expected = [
            "parse_requirement", "fetch_org_memory", "write_draft",
            "format_document", "init_review", "aggregate_reviews",
            "build_report", "export_docx",
        ]
        for name in expected:
            assert name in g.nodes, f"缺少 node: {name}"

    def test_graph_has_review_nodes(self):
        from src.graph.builder import build_graph
        g = build_graph()
        review_nodes = [n for n in g.nodes if n.startswith("review_")]
        assert len(review_nodes) == 5

    def test_graph_node_count(self):
        from src.graph.builder import build_graph
        g = build_graph()
        # __start__ + 14 custom nodes = 15
        assert len(g.nodes) >= 14


class TestReviewSelector:
    """select_review_agents() 邏輯驗證"""

    def test_default_selects_all_five(self):
        from src.graph.routing.review_selector import select_review_agents
        result = select_review_agents("函")
        assert len(result) == 5

    def test_skip_compliance(self):
        from src.graph.routing.review_selector import select_review_agents
        result = select_review_agents("函", skip_compliance=True)
        assert "review_compliance" not in result
        assert len(result) == 4

    def test_enabled_agents_whitelist(self):
        from src.graph.routing.review_selector import select_review_agents
        result = select_review_agents("函", enabled_agents=["review_format", "review_style"])
        assert set(result) == {"review_format", "review_style"}

    def test_sorted_by_priority(self):
        from src.graph.routing.review_selector import select_review_agents
        result = select_review_agents("函")
        assert result[0] == "review_format"  # priority 1
        assert result[-1] == "review_compliance"  # priority 5


class TestConditions:
    """routing conditions 驗證"""

    def test_should_review_skip(self):
        from src.graph.routing.conditions import should_review
        state = {"config": {"review_requested": False}}
        result = should_review(state)
        # 不審查時應回傳 export 或 init_review（由條件判斷）
        assert isinstance(result, str)

    def test_should_review_do_review(self):
        from src.graph.routing.conditions import should_review
        state = {"config": {"review_requested": True}}
        result = should_review(state)
        assert "review" in str(result).lower() or "init" in str(result).lower()


class TestScoring:
    """src/core/scoring.py 純函式驗證"""

    def test_calculate_weighted_scores_empty(self):
        from src.core.scoring import calculate_weighted_scores
        score, weight = calculate_weighted_scores([])
        assert score == 0.0
        assert weight == 0.0

    def test_calculate_weighted_scores_with_data(self):
        from types import SimpleNamespace
        from src.core.scoring import calculate_weighted_scores
        results = [
            SimpleNamespace(agent_name="Format Auditor", score=0.9, confidence=1.0),
            SimpleNamespace(agent_name="Style Checker", score=0.8, confidence=1.0),
        ]
        score, weight = calculate_weighted_scores(results)
        assert score > 0
        assert weight > 0

    def test_calculate_risk_scores_empty(self):
        from src.core.scoring import calculate_risk_scores
        error, warning = calculate_risk_scores([])
        assert error == 0.0
        assert warning == 0.0


# ============================================================
# KR3: _execute_via_graph 萃取邏輯驗證
# ============================================================


class TestExecuteViaGraphExtraction:
    """驗證 _execute_via_graph 從 final_state 萃取 requirement / draft 的邏輯"""

    def _make_valid_requirement_dict(self) -> dict:
        """回傳一個合法的 PublicDocRequirement dict"""
        return {
            "doc_type": "函",
            "urgency": "普通",
            "sender": "測試機關",
            "receiver": "測試單位",
            "subject": "測試主旨",
            "reason": "測試說明",
            "action_items": [],
            "attachments": [],
        }

    @patch("src.api.routes.workflow._get_graph")
    def test_extracts_requirement_from_graph_state(self, mock_get_graph):
        """正常情境：requirement dict 正確映射為 PublicDocRequirement"""
        from src.api.routes.workflow import _execute_via_graph
        from src.core.models import PublicDocRequirement

        req_dict = self._make_valid_requirement_dict()
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "requirement": req_dict,
            "formatted_draft": "# 公文草稿",
            "phase": "document_formatted",
            "review_requested": False,
        }
        mock_get_graph.return_value = mock_graph

        requirement, final_draft, qa_report, output_filename, rounds_used = (
            _execute_via_graph("測試輸入", "test-session", skip_review=True)
        )

        assert isinstance(requirement, PublicDocRequirement)
        assert requirement.doc_type == "函"
        assert requirement.sender == "測試機關"
        assert final_draft == "# 公文草稿"
        assert qa_report is None
        assert rounds_used == 0

    @patch("src.api.routes.workflow._get_graph")
    def test_raises_when_requirement_is_empty(self, mock_get_graph):
        """requirement 為空 dict 時應拋出 ValueError"""
        from src.api.routes.workflow import _execute_via_graph

        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "requirement": {},
            "formatted_draft": "# 草稿",
            "phase": "failed",
            "error": "需求分析失敗",
        }
        mock_get_graph.return_value = mock_graph

        with pytest.raises(ValueError, match="需求分析失敗"):
            _execute_via_graph("測試輸入", "test-session")

    @patch("src.api.routes.workflow._get_graph")
    def test_raises_when_requirement_is_none(self, mock_get_graph):
        """requirement 為 None 時應拋出 ValueError"""
        from src.api.routes.workflow import _execute_via_graph

        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "phase": "failed",
            "error": "某步驟失敗",
        }
        mock_get_graph.return_value = mock_graph

        with pytest.raises(ValueError, match="需求分析失敗"):
            _execute_via_graph("測試輸入", "test-session")

    @patch("src.api.routes.workflow._get_graph")
    def test_draft_priority_refined_over_formatted(self, mock_get_graph):
        """refined_draft 優先於 formatted_draft"""
        from src.api.routes.workflow import _execute_via_graph

        req_dict = self._make_valid_requirement_dict()
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "requirement": req_dict,
            "draft": "原始草稿",
            "formatted_draft": "格式化草稿",
            "refined_draft": "精煉草稿",
            "review_requested": False,
        }
        mock_get_graph.return_value = mock_graph

        _, final_draft, _, _, _ = _execute_via_graph(
            "測試輸入", "test-session", skip_review=True,
        )
        assert final_draft == "精煉草稿"

    @patch("src.api.routes.workflow._get_graph")
    def test_draft_fallback_to_formatted(self, mock_get_graph):
        """無 refined_draft 時回退至 formatted_draft"""
        from src.api.routes.workflow import _execute_via_graph

        req_dict = self._make_valid_requirement_dict()
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "requirement": req_dict,
            "draft": "原始草稿",
            "formatted_draft": "格式化草稿",
            "review_requested": False,
        }
        mock_get_graph.return_value = mock_graph

        _, final_draft, _, _, _ = _execute_via_graph(
            "測試輸入", "test-session", skip_review=True,
        )
        assert final_draft == "格式化草稿"

    @patch("src.api.routes.workflow._get_graph")
    def test_draft_fallback_to_raw_draft(self, mock_get_graph):
        """無 refined_draft 和 formatted_draft 時回退至 draft"""
        from src.api.routes.workflow import _execute_via_graph

        req_dict = self._make_valid_requirement_dict()
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "requirement": req_dict,
            "draft": "原始草稿",
            "review_requested": False,
        }
        mock_get_graph.return_value = mock_graph

        _, final_draft, _, _, _ = _execute_via_graph(
            "測試輸入", "test-session", skip_review=True,
        )
        assert final_draft == "原始草稿"

    @patch("src.api.routes.workflow._get_graph")
    def test_qa_report_constructed_from_aggregated(self, mock_get_graph):
        """有 aggregated_report 且未跳過審查時應建構 qa_report"""
        from src.api.routes.workflow import _execute_via_graph

        req_dict = self._make_valid_requirement_dict()
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "requirement": req_dict,
            "formatted_draft": "格式化草稿",
            "aggregated_report": {
                "overall_score": 0.85,
                "risk_summary": "Low",
                "error_count": 1,
                "warning_count": 2,
                "agent_results": [{"agent_name": "Format Auditor", "score": 0.9}],
            },
            "report": "# 品質報告",
            "refinement_round": 1,
            "review_requested": True,
        }
        mock_get_graph.return_value = mock_graph

        _, _, qa_report, _, rounds_used = _execute_via_graph(
            "測試輸入", "test-session", skip_review=False,
        )

        assert qa_report is not None
        assert qa_report.overall_score == 0.85
        assert qa_report.rounds_used == 1
        dump = qa_report.model_dump()
        assert dump["risk_summary"] == "Low"
        assert dump["error_count"] == 1
