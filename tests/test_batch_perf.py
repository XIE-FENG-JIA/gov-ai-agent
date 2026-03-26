"""批次處理效能優化測試。

驗證：
1. _process_batch_item 成功/失敗路徑
2. _run_batch 共享初始化（ConfigManager/LLM/KB 只建一次）
3. --workers 並行模式（workers>1 使用 ThreadPoolExecutor）
4. workers=1 向後相容（序列模式）
"""
import json
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────

@pytest.fixture()
def mock_llm():
    llm = MagicMock()
    llm.generate.return_value = (
        "### 主旨\n測試主旨\n### 說明\n一、測試說明。\n### 辦法\n一、請辦理。"
    )
    return llm


@pytest.fixture()
def mock_kb():
    kb = MagicMock()
    kb.search.return_value = []
    return kb


@pytest.fixture()
def mock_requirement():
    req = MagicMock()
    req.doc_type = "函"
    return req


def _make_progress_mock():
    """建立 Rich Progress mock，console 屬性也是 mock。"""
    prog = MagicMock()
    prog.console = MagicMock()
    return prog


# ─────────────────────────────────────────────
# _process_batch_item 測試
# ─────────────────────────────────────────────

class TestProcessBatchItem:
    """驗證 _process_batch_item helper 的成功與失敗路徑。"""

    @patch("src.cli.generate.DocxExporter")
    @patch("src.cli.generate.EditorInChief")
    @patch("src.cli.generate.TemplateEngine")
    @patch("src.cli.generate.WriterAgent")
    @patch("src.cli.generate.RequirementAgent")
    def test_success_returns_true(
        self,
        MockReqAgent, MockWriter, MockTemplate, MockEditor, MockExporter,
        mock_llm, mock_kb, mock_requirement,
    ):
        """成功處理時 result["success"] 應為 True。"""
        from src.cli.generate import _process_batch_item

        MockReqAgent.return_value.analyze.return_value = mock_requirement
        MockWriter.return_value.write_draft.return_value = "### 主旨\n測試\n### 說明\n一、說明。"
        template = MagicMock()
        template.parse_draft.return_value = {}
        template.apply_template.return_value = "formatted"
        MockTemplate.return_value = template
        MockExporter.return_value.export.return_value = "/tmp/output.docx"

        progress = _make_progress_mock()
        item = {"input": "測試公文需求", "output": "test.docx"}

        result = _process_batch_item(
            item, 1, 1, mock_llm, mock_kb,
            skip_review=True, max_rounds=1, convergence=False, skip_info=False,
            progress=progress, task=MagicMock(),
        )

        assert result["success"] is True
        assert result["failed_item"] is None
        assert result["elapsed"] >= 0

    @patch("src.cli.generate.RequirementAgent")
    def test_failure_returns_false_with_failed_item(self, MockReqAgent, mock_llm, mock_kb):
        """LLM 拋例外時 result["success"] 為 False，且 failed_item 包含 error_type。"""
        from src.cli.generate import _process_batch_item

        MockReqAgent.return_value.analyze.side_effect = RuntimeError("LLM 連線逾時")

        progress = _make_progress_mock()
        item = {"input": "測試失敗需求", "output": "fail.docx"}

        result = _process_batch_item(
            item, 1, 1, mock_llm, mock_kb,
            skip_review=True, max_rounds=1, convergence=False, skip_info=False,
            progress=progress, task=MagicMock(),
        )

        assert result["success"] is False
        assert result["failed_item"] is not None
        assert "error_type" in result["failed_item"]
        assert result["elapsed"] >= 0

    @patch("src.cli.generate.DocxExporter")
    @patch("src.cli.generate.TemplateEngine")
    @patch("src.cli.generate.WriterAgent")
    @patch("src.cli.generate.RequirementAgent")
    def test_parallel_mode_skips_rule_print(
        self, MockReqAgent, MockWriter, MockTemplate, MockExporter,
        mock_llm, mock_kb, mock_requirement,
    ):
        """parallel=True 時不應呼叫 progress.console.rule（避免輸出混亂）。"""
        from src.cli.generate import _process_batch_item

        MockReqAgent.return_value.analyze.return_value = mock_requirement
        MockWriter.return_value.write_draft.return_value = "### 主旨\n測試\n### 說明\n一、說明。"
        template = MagicMock()
        template.parse_draft.return_value = {}
        template.apply_template.return_value = "formatted"
        MockTemplate.return_value = template
        MockExporter.return_value.export.return_value = "/tmp/output.docx"

        progress = _make_progress_mock()
        item = {"input": "並行測試", "output": "parallel.docx"}

        _process_batch_item(
            item, 1, 3, mock_llm, mock_kb,
            skip_review=True, max_rounds=1, convergence=False, skip_info=False,
            progress=progress, task=MagicMock(), parallel=True,
        )

        progress.console.rule.assert_not_called()


# ─────────────────────────────────────────────
# _run_batch 共享初始化測試
# ─────────────────────────────────────────────

class TestRunBatchSharedInit:
    """驗證共享初始化：N 筆資料只建一次 ConfigManager / LLM / KB。"""

    def _make_batch_json(self, tmp_path: Path, n: int) -> str:
        items = [{"input": f"需求 {i}", "output": f"out_{i}.docx"} for i in range(1, n + 1)]
        p = tmp_path / "batch.json"
        p.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        return str(p)

    @patch("src.cli.generate._process_batch_item")
    @patch("src.cli.generate.KnowledgeBaseManager")
    @patch("src.cli.generate.get_llm_factory")
    @patch("src.cli.generate.ConfigManager")
    def test_config_and_llm_initialized_once(
        self,
        MockConfig, MockLLMFactory, MockKB, MockProcessItem,
        tmp_path,
    ):
        """3 筆批次 → ConfigManager.__init__ 只呼叫 1 次（不是 3 次）。"""
        from src.cli.generate import _run_batch

        mock_cfg = MagicMock()
        mock_cfg.config = {
            "llm": {"provider": "mock"},
            "knowledge_base": {"path": "./kb_data"},
        }
        MockConfig.return_value = mock_cfg

        # _process_batch_item 回傳成功
        MockProcessItem.return_value = {"success": True, "failed_item": None, "elapsed": 0.1}

        batch_file = self._make_batch_json(tmp_path, 3)
        _run_batch(batch_file, skip_review=True, workers=1)

        assert MockConfig.call_count == 1, (
            f"ConfigManager 應只初始化 1 次，實際 {MockConfig.call_count} 次"
        )
        assert MockLLMFactory.call_count == 1
        assert MockKB.call_count == 1

    @patch("src.cli.generate._process_batch_item")
    @patch("src.cli.generate.KnowledgeBaseManager")
    @patch("src.cli.generate.get_llm_factory")
    @patch("src.cli.generate.ConfigManager")
    def test_all_items_processed_sequential(
        self,
        MockConfig, MockLLMFactory, MockKB, MockProcessItem,
        tmp_path,
    ):
        """workers=1 序列模式：N 筆全部呼叫 _process_batch_item。"""
        from src.cli.generate import _run_batch

        mock_cfg = MagicMock()
        mock_cfg.config = {
            "llm": {"provider": "mock"},
            "knowledge_base": {"path": "./kb_data"},
        }
        MockConfig.return_value = mock_cfg
        MockProcessItem.return_value = {"success": True, "failed_item": None, "elapsed": 0.05}

        batch_file = self._make_batch_json(tmp_path, 4)
        _run_batch(batch_file, skip_review=True, workers=1)

        assert MockProcessItem.call_count == 4


# ─────────────────────────────────────────────
# _run_batch 並行模式測試
# ─────────────────────────────────────────────

class TestRunBatchParallel:
    """驗證 --workers N 並行模式的正確性。"""

    def _make_batch_json(self, tmp_path: Path, n: int) -> str:
        items = [{"input": f"並行需求 {i}", "output": f"parallel_{i}.docx"} for i in range(1, n + 1)]
        p = tmp_path / "parallel_batch.json"
        p.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        return str(p)

    @patch("src.cli.generate._process_batch_item")
    @patch("src.cli.generate.KnowledgeBaseManager")
    @patch("src.cli.generate.get_llm_factory")
    @patch("src.cli.generate.ConfigManager")
    def test_parallel_processes_all_items(
        self,
        MockConfig, MockLLMFactory, MockKB, MockProcessItem,
        tmp_path,
    ):
        """workers=3 並行模式：5 筆全部呼叫 _process_batch_item。"""
        from src.cli.generate import _run_batch

        mock_cfg = MagicMock()
        mock_cfg.config = {
            "llm": {"provider": "mock"},
            "knowledge_base": {"path": "./kb_data"},
        }
        MockConfig.return_value = mock_cfg
        MockProcessItem.return_value = {"success": True, "failed_item": None, "elapsed": 0.05}

        batch_file = self._make_batch_json(tmp_path, 5)
        _run_batch(batch_file, skip_review=True, workers=3)

        assert MockProcessItem.call_count == 5

    @patch("src.cli.generate._process_batch_item")
    @patch("src.cli.generate.KnowledgeBaseManager")
    @patch("src.cli.generate.get_llm_factory")
    @patch("src.cli.generate.ConfigManager")
    def test_parallel_passes_parallel_flag_true(
        self,
        MockConfig, MockLLMFactory, MockKB, MockProcessItem,
        tmp_path,
    ):
        """workers>1 時 _process_batch_item 必須以 parallel=True 呼叫。"""
        from src.cli.generate import _run_batch

        mock_cfg = MagicMock()
        mock_cfg.config = {
            "llm": {"provider": "mock"},
            "knowledge_base": {"path": "./kb_data"},
        }
        MockConfig.return_value = mock_cfg
        MockProcessItem.return_value = {"success": True, "failed_item": None, "elapsed": 0.01}

        batch_file = self._make_batch_json(tmp_path, 2)
        _run_batch(batch_file, skip_review=True, workers=2)

        for c in MockProcessItem.call_args_list:
            # parallel 可能是 positional（args[-1]）或 keyword
            parallel_val = c.kwargs.get("parallel", c.args[-1] if c.args else None)
            assert parallel_val is True, (
                "並行模式下 _process_batch_item 應以 parallel=True 呼叫"
            )

    @patch("src.cli.generate._process_batch_item")
    @patch("src.cli.generate.KnowledgeBaseManager")
    @patch("src.cli.generate.get_llm_factory")
    @patch("src.cli.generate.ConfigManager")
    def test_sequential_passes_parallel_flag_false(
        self,
        MockConfig, MockLLMFactory, MockKB, MockProcessItem,
        tmp_path,
    ):
        """workers=1 時 _process_batch_item 以 parallel=False 呼叫。"""
        from src.cli.generate import _run_batch

        mock_cfg = MagicMock()
        mock_cfg.config = {
            "llm": {"provider": "mock"},
            "knowledge_base": {"path": "./kb_data"},
        }
        MockConfig.return_value = mock_cfg
        MockProcessItem.return_value = {"success": True, "failed_item": None, "elapsed": 0.01}

        batch_file = self._make_batch_json(tmp_path, 2)
        _run_batch(batch_file, skip_review=True, workers=1)

        for c in MockProcessItem.call_args_list:
            assert c.kwargs.get("parallel") is False or not c.kwargs.get("parallel", True), (
                "序列模式下 parallel 應為 False"
            )

    @patch("src.cli.generate._process_batch_item")
    @patch("src.cli.generate.KnowledgeBaseManager")
    @patch("src.cli.generate.get_llm_factory")
    @patch("src.cli.generate.ConfigManager")
    def test_failed_items_collected_in_parallel(
        self,
        MockConfig, MockLLMFactory, MockKB, MockProcessItem,
        tmp_path,
    ):
        """並行模式：部分失敗項目仍正確收集到 failed_items（寫 retry JSON）。"""
        from src.cli.generate import _run_batch

        mock_cfg = MagicMock()
        mock_cfg.config = {
            "llm": {"provider": "mock"},
            "knowledge_base": {"path": "./kb_data"},
        }
        MockConfig.return_value = mock_cfg

        failed_item_data = {"input": "失敗需求", "output": "fail.docx", "error_type": "LLMError", "suggestion": "重試"}
        MockProcessItem.side_effect = [
            {"success": True, "failed_item": None, "elapsed": 0.01},
            {"success": False, "failed_item": failed_item_data, "elapsed": 0.01},
            {"success": True, "failed_item": None, "elapsed": 0.01},
        ]

        batch_file = self._make_batch_json(tmp_path, 3)
        _run_batch(batch_file, skip_review=True, workers=3)

        # 確認 retry JSON 被寫出
        retry_file = Path(batch_file).parent / "parallel_batch_failed.json"
        assert retry_file.exists(), "失敗項目應產生 _failed.json"
        retry_data = json.loads(retry_file.read_text(encoding="utf-8"))
        assert len(retry_data) == 1
        assert retry_data[0]["error_type"] == "LLMError"
