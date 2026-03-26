"""review_cmd.py 的單元測試。"""
from __future__ import annotations

import json
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
import typer
from rich.console import Console

from src.cli.review_cmd import _detect_doc_type, _render_apply_diff, review


# ─────────────────────────────────────────
# _detect_doc_type
# ─────────────────────────────────────────

class TestDetectDocType:
    """文件類型自動偵測邏輯。"""

    def test_detect_han(self):
        assert _detect_doc_type("主旨：請查照") == "函"

    def test_detect_gonggao(self):
        assert _detect_doc_type("公告\n主旨：") == "公告"

    def test_detect_meeting_minutes(self):
        assert _detect_doc_type("開會紀錄\n主席：") == "開會紀錄"

    def test_detect_shouling(self):
        assert _detect_doc_type("手令\n指示事項：") == "手令"

    def test_detect_jianjian(self):
        assert _detect_doc_type("箋函\n說明：") == "箋函"

    def test_fallback_to_han(self):
        assert _detect_doc_type("完全無法辨識的內容") == "函"

    def test_empty_content(self):
        assert _detect_doc_type("") == "函"


# ─────────────────────────────────────────
# review() — 基本使用路徑
# ─────────────────────────────────────────

def _make_qa_report(score: float = 0.85, risk: str = "Low") -> MagicMock:
    """建立模擬 QAReport。"""
    issue = MagicMock()
    issue.severity = "warning"
    issue.category = "style"
    issue.location = "說明段"
    issue.description = "使用口語化用語「幫我」"
    issue.suggestion = "將「幫我」改為「請」"

    agent_result = MagicMock()
    agent_result.agent_name = "Style Checker"
    agent_result.score = score
    agent_result.issues = [issue]
    agent_result.model_dump.return_value = {
        "agent_name": "Style Checker",
        "score": score,
        "issues": [
            {
                "severity": "warning",
                "category": "style",
                "location": "說明段",
                "description": "使用口語化用語「幫我」",
                "suggestion": "將「幫我」改為「請」",
            }
        ],
    }

    report = MagicMock()
    report.overall_score = score
    report.risk_summary = risk
    report.agent_results = [agent_result]
    return report


class TestReviewCommand:
    """review 指令主流程。"""

    def _call_review(self, tmp_path, **kwargs):
        """建立草稿檔並呼叫 review()，回傳 (draft_file, typer.Exit exception or None)。"""
        draft = tmp_path / "draft.md"
        draft.write_text("主旨：測試公文\n說明：內容。\n", encoding="utf-8")
        defaults = dict(
            draft_file=str(draft),
            doc_type=None,
            apply=False,
            output=None,
            max_rounds=1,
            json_output=False,
        )
        defaults.update(kwargs)
        return str(draft), defaults

    def test_review_only_success(self, tmp_path):
        """一般審查（不 apply）正常流程。"""
        draft = tmp_path / "draft.md"
        draft.write_text("主旨：測試公文\n說明：內容。\n", encoding="utf-8")
        report = _make_qa_report()

        mock_editor = MagicMock()
        mock_editor.__enter__ = MagicMock(return_value=mock_editor)
        mock_editor.__exit__ = MagicMock(return_value=False)
        mock_editor.run_review_only.return_value = report

        with patch("src.cli.review_cmd.get_llm", return_value=MagicMock()), \
             patch("src.cli.review_cmd.get_kb", return_value=MagicMock()), \
             patch("src.cli.review_cmd.EditorInChief", return_value=mock_editor), \
             patch("src.cli.review_cmd.console"):
            review(
                draft_file=str(draft),
                doc_type=None,
                apply=False,
                output=None,
                max_rounds=1,
                json_output=False,
            )

        mock_editor.run_review_only.assert_called_once()
        mock_editor.review_and_refine.assert_not_called()

    def test_review_with_apply(self, tmp_path):
        """--apply 時呼叫 review_and_refine，並寫出修正草稿。"""
        draft = tmp_path / "draft.md"
        draft.write_text("主旨：測試公文\n說明：需要修正。\n", encoding="utf-8")
        report = _make_qa_report()
        revised = "主旨：測試公文\n說明：修正後內容。\n"

        mock_editor = MagicMock()
        mock_editor.__enter__ = MagicMock(return_value=mock_editor)
        mock_editor.__exit__ = MagicMock(return_value=False)
        mock_editor.review_and_refine.return_value = (revised, report)

        output_path = str(tmp_path / "revised.md")

        with patch("src.cli.review_cmd.get_llm", return_value=MagicMock()), \
             patch("src.cli.review_cmd.get_kb", return_value=MagicMock()), \
             patch("src.cli.review_cmd.EditorInChief", return_value=mock_editor), \
             patch("src.cli.review_cmd.console"):
            review(
                draft_file=str(draft),
                doc_type="函",
                apply=True,
                output=output_path,
                max_rounds=1,
                json_output=False,
            )

        mock_editor.review_and_refine.assert_called_once()
        mock_editor.run_review_only.assert_not_called()
        assert (tmp_path / "revised.md").read_text(encoding="utf-8") == revised

    def test_apply_default_output_path(self, tmp_path):
        """--apply 但未指定 --output 時，使用 <原檔名>_revised.md。"""
        draft = tmp_path / "mydoc.md"
        draft.write_text("主旨：測試\n", encoding="utf-8")
        report = _make_qa_report()

        mock_editor = MagicMock()
        mock_editor.__enter__ = MagicMock(return_value=mock_editor)
        mock_editor.__exit__ = MagicMock(return_value=False)
        mock_editor.review_and_refine.return_value = ("修正後", report)

        with patch("src.cli.review_cmd.get_llm", return_value=MagicMock()), \
             patch("src.cli.review_cmd.get_kb", return_value=MagicMock()), \
             patch("src.cli.review_cmd.EditorInChief", return_value=mock_editor), \
             patch("src.cli.review_cmd.console"):
            review(
                draft_file=str(draft),
                doc_type=None,
                apply=True,
                output=None,  # 未指定
                max_rounds=1,
                json_output=False,
            )

        expected = tmp_path / "mydoc_revised.md"
        assert expected.exists()
        assert expected.read_text(encoding="utf-8") == "修正後"

    def test_json_output(self, tmp_path, capsys):
        """--json 時輸出合法 JSON，包含 suggestion 欄位。"""
        draft = tmp_path / "draft.md"
        draft.write_text("主旨：測試\n", encoding="utf-8")
        report = _make_qa_report()

        mock_editor = MagicMock()
        mock_editor.__enter__ = MagicMock(return_value=mock_editor)
        mock_editor.__exit__ = MagicMock(return_value=False)
        mock_editor.run_review_only.return_value = report

        with patch("src.cli.review_cmd.get_llm", return_value=MagicMock()), \
             patch("src.cli.review_cmd.get_kb", return_value=MagicMock()), \
             patch("src.cli.review_cmd.EditorInChief", return_value=mock_editor), \
             patch("src.cli.review_cmd.console"):
            review(
                draft_file=str(draft),
                doc_type="函",
                apply=False,
                output=None,
                max_rounds=1,
                json_output=True,
            )

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["doc_type"] == "函"
        assert data["overall_score"] == pytest.approx(0.85)
        issues = data["agent_results"][0]["issues"]
        assert len(issues) == 1
        assert issues[0]["suggestion"] == "將「幫我」改為「請」"

    def test_file_not_found(self, tmp_path):
        """檔案不存在時應以 Exit(1) 結束。"""
        with pytest.raises(typer.Exit):
            review(
                draft_file=str(tmp_path / "nonexistent.md"),
                doc_type=None,
                apply=False,
                output=None,
                max_rounds=1,
                json_output=False,
            )

    def test_empty_file(self, tmp_path):
        """空白檔案應以 Exit(1) 結束。"""
        draft = tmp_path / "empty.md"
        draft.write_text("   ", encoding="utf-8")
        with pytest.raises(typer.Exit):
            review(
                draft_file=str(draft),
                doc_type=None,
                apply=False,
                output=None,
                max_rounds=1,
                json_output=False,
            )

    def test_llm_init_failure(self, tmp_path):
        """LLM 初始化失敗時應以 Exit(1) 結束。"""
        draft = tmp_path / "draft.md"
        draft.write_text("主旨：測試\n", encoding="utf-8")

        with patch("src.cli.review_cmd.get_llm", side_effect=RuntimeError("連線失敗")), \
             patch("src.cli.review_cmd.console"), \
             pytest.raises(typer.Exit):
            review(
                draft_file=str(draft),
                doc_type=None,
                apply=False,
                output=None,
                max_rounds=1,
                json_output=False,
            )

    def test_doc_type_explicit_override(self, tmp_path):
        """明確指定 --doc-type 時，應使用指定值而非自動偵測。"""
        draft = tmp_path / "draft.md"
        draft.write_text("主旨：測試\n", encoding="utf-8")
        report = _make_qa_report()

        mock_editor = MagicMock()
        mock_editor.__enter__ = MagicMock(return_value=mock_editor)
        mock_editor.__exit__ = MagicMock(return_value=False)
        mock_editor.run_review_only.return_value = report

        with patch("src.cli.review_cmd.get_llm", return_value=MagicMock()), \
             patch("src.cli.review_cmd.get_kb", return_value=MagicMock()), \
             patch("src.cli.review_cmd.EditorInChief", return_value=mock_editor), \
             patch("src.cli.review_cmd.console"):
            review(
                draft_file=str(draft),
                doc_type="公告",  # 明確指定
                apply=False,
                output=None,
                max_rounds=1,
                json_output=False,
            )

        # run_review_only 的第二個參數應為「公告」
        call_args = mock_editor.run_review_only.call_args
        assert call_args[0][1] == "公告"


# ─────────────────────────────────────────
# EditorInChief.run_review_only — 整合驗證
# ─────────────────────────────────────────

class TestRunReviewOnly:
    """驗證 EditorInChief.run_review_only 回傳 QAReport 且不觸發修正。"""

    def test_returns_qa_report_without_refinement(self):
        """run_review_only 應回傳 QAReport，不呼叫 _iterative_review 或 _convergence_review。"""
        from src.core.review_models import ReviewResult, QAReport

        mock_result = ReviewResult(
            agent_name="Mock Agent", issues=[], score=1.0, confidence=1.0
        )

        with patch("src.agents.editor.EditorInChief._execute_review",
                   return_value=([mock_result], [])) as mock_exec, \
             patch("src.agents.editor.EditorInChief._iterative_review") as mock_iter, \
             patch("src.agents.editor.EditorInChief._convergence_review") as mock_conv, \
             patch("src.agents.editor.EditorInChief._print_report"), \
             patch("src.agents.editor.console"):

            from src.agents.editor import EditorInChief
            mock_llm = MagicMock()
            editor = EditorInChief.__new__(EditorInChief)
            editor.llm = mock_llm
            editor.kb_manager = None
            from concurrent.futures import ThreadPoolExecutor
            editor._executor = ThreadPoolExecutor(max_workers=1)
            editor.format_auditor = MagicMock()
            editor.format_auditor.audit.return_value = {"errors": [], "warnings": []}
            editor.style_checker = MagicMock()
            editor.fact_checker = MagicMock()
            editor.consistency_checker = MagicMock()
            editor.compliance_checker = MagicMock()

            report = editor.run_review_only("草稿內容", "函")

            assert isinstance(report, QAReport)
            mock_exec.assert_called_once_with("草稿內容", "函")
            mock_iter.assert_not_called()
            mock_conv.assert_not_called()

            editor._executor.shutdown(wait=False)


# ─────────────────────────────────────────
# _render_apply_diff — diff 顯示邏輯
# ─────────────────────────────────────────

class TestRenderApplyDiff:
    """驗證 --apply 後的 diff 顯示邏輯。"""

    def _capture(self, original: str, revised: str) -> str:
        """呼叫 _render_apply_diff 並捕捉輸出文字。"""
        buf = StringIO()
        test_console = Console(file=buf, force_terminal=False, highlight=False)
        with patch("src.cli.review_cmd.console", test_console):
            _render_apply_diff(original, revised)
        return buf.getvalue()

    def test_no_change_shows_notice(self):
        """原始與修正後相同時，應顯示「未產生任何變更」提示。"""
        text = "主旨：測試\n說明：內容。\n"
        output = self._capture(text, text)
        assert "未產生任何變更" in output

    def test_diff_shows_added_line(self):
        """修正後多一行時，diff 應包含 + 開頭的新增行。"""
        original = "主旨：測試\n"
        revised = "主旨：測試\n說明：新增段落。\n"
        output = self._capture(original, revised)
        assert "說明：新增段落" in output

    def test_diff_shows_removed_line(self):
        """修正後移除一行時，diff 應包含移除行的內容。"""
        original = "主旨：測試\n口語化用語：幫我\n"
        revised = "主旨：測試\n"
        output = self._capture(original, revised)
        assert "口語化用語" in output

    def test_apply_no_diff_flag_suppresses_output(self, tmp_path):
        """--no-diff 時，apply 後不應呼叫 _render_apply_diff。"""
        draft = tmp_path / "draft.md"
        draft.write_text("主旨：測試\n說明：需要修正。\n", encoding="utf-8")
        report = _make_qa_report()
        revised = "主旨：測試\n說明：修正後。\n"

        mock_editor = MagicMock()
        mock_editor.__enter__ = MagicMock(return_value=mock_editor)
        mock_editor.__exit__ = MagicMock(return_value=False)
        mock_editor.review_and_refine.return_value = (revised, report)

        with patch("src.cli.review_cmd.get_llm", return_value=MagicMock()), \
             patch("src.cli.review_cmd.get_kb", return_value=MagicMock()), \
             patch("src.cli.review_cmd.EditorInChief", return_value=mock_editor), \
             patch("src.cli.review_cmd._render_apply_diff") as mock_diff, \
             patch("src.cli.review_cmd.console"):
            review(
                draft_file=str(draft),
                doc_type="函",
                apply=True,
                output=str(tmp_path / "revised.md"),
                max_rounds=1,
                show_diff=False,
                json_output=False,
            )

        mock_diff.assert_not_called()

    def test_apply_with_diff_flag_calls_diff(self, tmp_path):
        """--diff（預設）時，apply 後應呼叫 _render_apply_diff。"""
        draft = tmp_path / "draft.md"
        original_text = "主旨：測試\n說明：需要修正。\n"
        draft.write_text(original_text, encoding="utf-8")
        report = _make_qa_report()
        revised = "主旨：測試\n說明：修正後。\n"

        mock_editor = MagicMock()
        mock_editor.__enter__ = MagicMock(return_value=mock_editor)
        mock_editor.__exit__ = MagicMock(return_value=False)
        mock_editor.review_and_refine.return_value = (revised, report)

        with patch("src.cli.review_cmd.get_llm", return_value=MagicMock()), \
             patch("src.cli.review_cmd.get_kb", return_value=MagicMock()), \
             patch("src.cli.review_cmd.EditorInChief", return_value=mock_editor), \
             patch("src.cli.review_cmd._render_apply_diff") as mock_diff, \
             patch("src.cli.review_cmd.console"):
            review(
                draft_file=str(draft),
                doc_type="函",
                apply=True,
                output=str(tmp_path / "revised.md"),
                max_rounds=1,
                show_diff=True,
                json_output=False,
            )

        mock_diff.assert_called_once_with(original_text, revised)
