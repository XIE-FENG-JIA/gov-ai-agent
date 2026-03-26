"""reporter.py build_report() 單元測試。"""
from src.graph.nodes.reporter import build_report


class TestBuildReport:
    """測試 build_report 的各種輸入情境。"""

    def _make_state(self, **overrides):
        base = {
            "aggregated_report": {
                "overall_score": 0.85,
                "risk_summary": "低風險",
                "error_count": 1,
                "warning_count": 2,
                "agent_results": [],
            },
            "refinement_round": 1,
        }
        base["aggregated_report"].update(overrides)
        return base

    def test_basic_report_structure(self):
        """基本報告應包含所有必要區塊。"""
        result = build_report(self._make_state())
        assert result["phase"] == "report_built"
        report = result["report"]
        assert "品質保證報告" in report
        assert "0.85" in report
        assert "低風險" in report
        assert "精煉輪次" in report

    def test_agent_with_no_issues(self):
        """agent 無問題時應顯示「通過」。"""
        result = build_report(self._make_state(
            agent_results=[{"agent_name": "Style Checker", "score": 1.0, "issues": []}]
        ))
        assert "通過" in result["report"]
        assert "Style Checker" in result["report"]

    def test_agent_with_issues_and_suggestion(self):
        """issue 有 suggestion 時應顯示「建議」。"""
        result = build_report(self._make_state(
            agent_results=[{
                "agent_name": "Format Auditor",
                "score": 0.5,
                "issues": [{
                    "severity": "error",
                    "location": "主旨段",
                    "description": "缺少主旨",
                    "suggestion": "請加入「主旨：」段落",
                }],
            }]
        ))
        report = result["report"]
        assert "[E]" in report
        assert "主旨段" in report
        assert "缺少主旨" in report
        assert "*建議*" in report
        assert "請加入「主旨：」段落" in report

    def test_agent_issue_without_suggestion(self):
        """issue 沒有 suggestion 時不應出現「建議」行。"""
        result = build_report(self._make_state(
            agent_results=[{
                "agent_name": "Compliance",
                "score": 0.7,
                "issues": [{
                    "severity": "warning",
                    "location": "說明段",
                    "description": "用語不夠正式",
                }],
            }]
        ))
        report = result["report"]
        assert "[W]" in report
        assert "用語不夠正式" in report
        assert "*建議*" not in report

    def test_info_severity_icon(self):
        """info 級別應顯示 [I] 圖示。"""
        result = build_report(self._make_state(
            agent_results=[{
                "agent_name": "Test",
                "score": 0.9,
                "issues": [{"severity": "info", "location": "格式", "description": "提示"}],
            }]
        ))
        assert "[I]" in result["report"]

    def test_empty_state(self):
        """完全空的 state 不應崩潰。"""
        result = build_report({})
        assert result["phase"] == "report_built"
        assert "品質保證報告" in result["report"]

    def test_exception_handling(self):
        """aggregated_report 為非 dict 時應走異常路徑。"""
        # 觸發 TypeError: 'NoneType' 不支援 .get()
        # 但 state.get("aggregated_report", {}) 有預設值，所以需要更極端的情境
        # 模擬 agent_results 中元素非 dict 導致 .get() 失敗
        result = build_report({
            "aggregated_report": {
                "overall_score": 0.5,
                "risk_summary": "高風險",
                "error_count": 0,
                "warning_count": 0,
                "agent_results": [None],  # None 不支援 .get()
            },
            "refinement_round": 0,
        })
        assert result["phase"] == "report_built"
        assert "失敗" in result["report"]

    def test_multiple_agents(self):
        """多個 agent 結果應全部顯示。"""
        result = build_report(self._make_state(
            agent_results=[
                {"agent_name": "Agent1", "score": 0.8, "issues": []},
                {"agent_name": "Agent2", "score": 0.6, "issues": [
                    {"severity": "error", "location": "L1", "description": "D1", "suggestion": "S1"},
                    {"severity": "warning", "location": "L2", "description": "D2"},
                ]},
            ]
        ))
        report = result["report"]
        assert "Agent1" in report
        assert "Agent2" in report
        assert "D1" in report
        assert "S1" in report
