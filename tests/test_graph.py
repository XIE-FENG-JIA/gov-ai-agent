"""src/graph/ 基礎測試 — state, builder, routing"""

import pytest


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
