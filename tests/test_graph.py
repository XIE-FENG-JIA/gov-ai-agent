"""src/graph/ 基礎測試 — state, builder, routing, _execute_via_graph 萃取邏輯"""

import pytest
from unittest.mock import patch, MagicMock


class TestReviewNodeDecorator:
    """_review_node decorator 行為驗證"""

    def test_success_wraps_result_in_review_results(self):
        """成功時應將結果序列化並包在 review_results list 中"""
        from src.graph.nodes.reviewers import _review_node

        @_review_node("Test Agent")
        def dummy_reviewer(state):
            return {"agent_name": "Test Agent", "score": 0.95, "issues": []}

        result = dummy_reviewer({"draft": "test"})
        assert "review_results" in result
        assert len(result["review_results"]) == 1
        assert result["review_results"][0]["score"] == 0.95

    def test_success_with_pydantic_model(self):
        """回傳有 model_dump 的物件應正確序列化"""
        from src.graph.nodes.reviewers import _review_node

        class FakeModel:
            def model_dump(self):
                return {"agent_name": "Fake", "score": 0.8}

        @_review_node("Fake Agent")
        def dummy_reviewer(state):
            return FakeModel()

        result = dummy_reviewer({})
        assert result["review_results"][0]["score"] == 0.8

    def test_error_returns_degraded_result(self):
        """例外時應回傳降級結果，不中斷流程"""
        from src.graph.nodes.reviewers import _review_node

        @_review_node("Failing Agent")
        def broken_reviewer(state):
            raise RuntimeError("LLM 連線失敗")

        result = broken_reviewer({"draft": "test"})
        assert result["review_results"][0]["agent_name"] == "Failing Agent"
        assert result["review_results"][0]["score"] == 0.0
        assert "LLM 連線失敗" in result["review_results"][0]["error"]

    def test_preserves_function_name(self):
        """decorator 應保留原函式名稱（LangGraph 註冊用）"""
        from src.graph.nodes.reviewers import review_format, review_style
        assert review_format.__name__ == "review_format"
        assert review_style.__name__ == "review_style"


class TestReviewResultsReducer:
    """_review_results_reducer 行為驗證"""

    def test_empty_update_resets(self):
        """空 list update 應重設為 []（_init_review 的清空信號）"""
        from src.graph.state import _review_results_reducer
        existing = [{"agent_name": "A", "score": 0.9}]
        assert _review_results_reducer(existing, []) == []

    def test_non_empty_update_concatenates(self):
        """非空 update 應串接到現有 list"""
        from src.graph.state import _review_results_reducer
        existing = [{"agent_name": "A"}]
        update = [{"agent_name": "B"}]
        result = _review_results_reducer(existing, update)
        assert len(result) == 2
        assert result[0]["agent_name"] == "A"
        assert result[1]["agent_name"] == "B"

    def test_first_update_with_empty_current(self):
        """current 為空時應正確初始化"""
        from src.graph.state import _review_results_reducer
        result = _review_results_reducer([], [{"agent_name": "A"}])
        assert len(result) == 1

    def test_reset_then_add(self):
        """模擬精煉迴圈：先重設，再加入新結果"""
        from src.graph.state import _review_results_reducer
        round1 = [{"agent_name": "A", "round": 1}]
        # init_review 重設
        after_reset = _review_results_reducer(round1, [])
        assert after_reset == []
        # 新一輪審查結果
        round2_result = [{"agent_name": "A", "round": 2}]
        after_add = _review_results_reducer(after_reset, round2_result)
        assert len(after_add) == 1
        assert after_add[0]["round"] == 2

    def test_multiple_reviewers_accumulate(self):
        """並行審查：多個 reviewer 依序加入"""
        from src.graph.state import _review_results_reducer
        state = []
        state = _review_results_reducer(state, [{"agent_name": "Format"}])
        state = _review_results_reducer(state, [{"agent_name": "Style"}])
        state = _review_results_reducer(state, [{"agent_name": "Fact"}])
        assert len(state) == 3


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


class TestFanOutReviewers:
    """fan_out_reviewers 條件邊函式驗證"""

    def test_fan_out_normal(self):
        """正常情況：requirement 含 doc_type，回傳 Send 清單"""
        from src.graph.routing.conditions import fan_out_reviewers
        state = {"requirement": {"doc_type": "函"}, "draft": "測試草稿"}
        sends = fan_out_reviewers(state)
        assert isinstance(sends, list)
        assert len(sends) > 0

    def test_fan_out_missing_requirement_raises(self):
        """requirement 缺失時應 raise ValueError"""
        from src.graph.routing.conditions import fan_out_reviewers
        import pytest
        with pytest.raises(ValueError, match="缺少 requirement"):
            fan_out_reviewers({"draft": "測試草稿"})

    def test_fan_out_empty_requirement_raises(self):
        """requirement 為空 dict 時應 raise ValueError（空 dict 視為缺失）"""
        from src.graph.routing.conditions import fan_out_reviewers
        import pytest
        with pytest.raises(ValueError, match="缺少 requirement"):
            fan_out_reviewers({"requirement": {}})

    def test_fan_out_missing_doc_type_raises(self):
        """requirement 有其他欄位但缺少 doc_type 時應 raise ValueError"""
        from src.graph.routing.conditions import fan_out_reviewers
        import pytest
        with pytest.raises(ValueError, match="缺少 doc_type"):
            fan_out_reviewers({"requirement": {"sender": "臺北市政府"}})

    def test_fan_out_requirement_not_dict_raises(self):
        """requirement 非 dict 時應 raise ValueError"""
        from src.graph.routing.conditions import fan_out_reviewers
        import pytest
        with pytest.raises(ValueError, match="缺少 requirement"):
            fan_out_reviewers({"requirement": "not a dict"})


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


    @patch("src.api.routes.workflow._get_graph")
    def test_cleans_up_graph_temp_export(self, mock_get_graph, tmp_path):
        """graph 產生的臨時匯出檔應被 API 層清理"""
        from src.api.routes.workflow import _execute_via_graph

        # 模擬 graph 產生的臨時檔案
        temp_file = tmp_path / "gov_doc_tmp.docx"
        temp_file.write_text("temp")

        req_dict = self._make_valid_requirement_dict()
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "requirement": req_dict,
            "formatted_draft": "# 草稿",
            "phase": "exported",
            "output_path": str(temp_file),
        }
        mock_get_graph.return_value = mock_graph

        _execute_via_graph("測試輸��", "test-session", skip_review=True)

        # 臨時檔案應已被清理
        assert not temp_file.exists()


# ============================================================
# refine_draft / verify_refinement 單元測試
# ============================================================

class TestRefineDraft:
    """refine_draft 節點覆蓋所有分支。"""

    def _make_state(self, *, draft="測試草稿", issues=None, round_num=0):
        state = {
            "formatted_draft": draft,
            "refinement_round": round_num,
            "aggregated_report": {
                "agent_results": issues or [],
            },
        }
        return state

    @patch("src.api.dependencies.get_llm")
    def test_with_feedback_success(self, mock_get_llm):
        """有審查回饋且 LLM 回傳有效結果"""
        from src.graph.nodes.refiner import refine_draft

        mock_llm = MagicMock()
        mock_llm.generate.return_value = "修正後的草稿"
        mock_get_llm.return_value = mock_llm

        state = self._make_state(issues=[{
            "agent_name": "Auditor",
            "issues": [{"severity": "error", "description": "缺少主旨"}],
        }])
        result = refine_draft(state)
        assert result["refined_draft"] == "修正後的草稿"
        assert result["refinement_round"] == 1
        assert result["phase"] == "draft_refined"

    @patch("src.api.dependencies.get_llm")
    def test_no_feedback_keeps_draft(self, mock_get_llm):
        """無審查回饋時保留原始草稿"""
        from src.graph.nodes.refiner import refine_draft

        state = self._make_state(issues=[])
        result = refine_draft(state)
        assert result["refined_draft"] == "測試草稿"
        assert result["refinement_round"] == 1

    @patch("src.api.dependencies.get_llm")
    def test_llm_invalid_result(self, mock_get_llm):
        """LLM 回傳空字串或 Error 時保留原始草稿"""
        from src.graph.nodes.refiner import refine_draft

        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        for bad_result in ["", "   ", "Error: timeout", None]:
            mock_llm.generate.return_value = bad_result
            state = self._make_state(issues=[{
                "agent_name": "A",
                "issues": [{"severity": "warning", "description": "x"}],
            }])
            result = refine_draft(state)
            assert result["refined_draft"] == "測試草稿", f"bad_result={bad_result!r}"

    @patch("src.api.dependencies.get_llm")
    def test_feedback_truncation(self, mock_get_llm):
        """超長回饋被截斷"""
        from src.graph.nodes.refiner import refine_draft
        from src.core.constants import MAX_FEEDBACK_LENGTH

        mock_llm = MagicMock()
        mock_llm.generate.return_value = "OK"
        mock_get_llm.return_value = mock_llm

        # 產生超過 MAX_FEEDBACK_LENGTH 的回饋
        long_issues = [{
            "agent_name": "Agent",
            "issues": [{"severity": "error", "description": "x" * 500}]
        } for _ in range(100)]
        state = self._make_state(issues=long_issues)
        result = refine_draft(state)
        # 確認 prompt 中包含截斷標記
        call_args = mock_llm.generate.call_args[0][0]
        assert "已截斷" in call_args

    @patch("src.api.dependencies.get_llm")
    def test_draft_truncation(self, mock_get_llm):
        """超長草稿被截斷"""
        from src.graph.nodes.refiner import refine_draft
        from src.core.constants import MAX_DRAFT_LENGTH

        mock_llm = MagicMock()
        mock_llm.generate.return_value = "OK"
        mock_get_llm.return_value = mock_llm

        long_draft = "字" * (MAX_DRAFT_LENGTH + 1000)
        state = self._make_state(
            draft=long_draft,
            issues=[{"agent_name": "A", "issues": [{"severity": "error", "description": "x"}]}],
        )
        result = refine_draft(state)
        call_args = mock_llm.generate.call_args[0][0]
        assert "草稿已截斷" in call_args

    @patch("src.api.dependencies.get_llm", side_effect=RuntimeError("LLM init failed"))
    def test_exception_keeps_draft(self, mock_get_llm):
        """例外時不阻斷流程，保留現有草稿"""
        from src.graph.nodes.refiner import refine_draft

        # 必須有 issues 才能走到 get_llm() 觸發例外
        state = self._make_state(issues=[{
            "agent_name": "A",
            "issues": [{"severity": "error", "description": "x"}],
        }])
        result = refine_draft(state)
        assert result["refined_draft"] == "測試草稿"
        assert result["phase"] == "draft_refined"

    @patch("src.api.dependencies.get_llm")
    def test_refined_draft_priority(self, mock_get_llm):
        """refined_draft 優先於 formatted_draft"""
        from src.graph.nodes.refiner import refine_draft

        state = {
            "refined_draft": "第二版",
            "formatted_draft": "第一版",
            "refinement_round": 1,
            "aggregated_report": {"agent_results": []},
        }
        result = refine_draft(state)
        assert result["refined_draft"] == "第二版"

    @patch("src.api.dependencies.get_llm")
    def test_issue_suggestion_default(self, mock_get_llm):
        """issue 缺少 suggestion 時使用預設值"""
        from src.graph.nodes.refiner import refine_draft

        mock_llm = MagicMock()
        mock_llm.generate.return_value = "OK"
        mock_get_llm.return_value = mock_llm

        state = self._make_state(issues=[{
            "agent_name": "Checker",
            "issues": [{"severity": "info", "description": "小問題"}],
        }])
        refine_draft(state)
        call_args = mock_llm.generate.call_args[0][0]
        assert "請自行判斷修正方式" in call_args


class TestVerifyRefinement:
    """verify_refinement 節點覆蓋所有分支。"""

    def test_valid_draft_passes(self):
        """正常草稿通過驗證"""
        from src.graph.nodes.refiner import verify_refinement
        result = verify_refinement({"refined_draft": "這是一份正常的精煉草稿內容"})
        assert result["phase"] == "verification_passed"

    def test_empty_draft_warns(self):
        """空草稿觸發警告"""
        from src.graph.nodes.refiner import verify_refinement
        result = verify_refinement({"refined_draft": ""})
        assert result["phase"] == "verification_warning"

    def test_short_draft_warns(self):
        """過短草稿觸發警告"""
        from src.graph.nodes.refiner import verify_refinement
        result = verify_refinement({"refined_draft": "短"})
        assert result["phase"] == "verification_warning"

    def test_missing_draft_warns(self):
        """缺少 refined_draft 觸發警告"""
        from src.graph.nodes.refiner import verify_refinement
        result = verify_refinement({})
        assert result["phase"] == "verification_warning"

    def test_exception_returns_warning(self):
        """異常時回傳 verification_warning"""
        from src.graph.nodes.refiner import verify_refinement
        # state.get() 正常不會拋異常，用特殊物件觸發
        bad_state = MagicMock()
        bad_state.get.side_effect = RuntimeError("state broken")
        result = verify_refinement(bad_state)
        assert result["phase"] == "verification_warning"
