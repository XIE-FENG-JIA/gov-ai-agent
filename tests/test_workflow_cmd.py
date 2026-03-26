"""workflow_cmd.py 路徑穿越防護 + 指令覆蓋率測試。"""
import json
import os
from unittest.mock import patch, MagicMock

import pytest
import typer
from typer.testing import CliRunner

from src.cli.workflow_cmd import _validate_workflow_name, _workflow_path

runner = CliRunner()


class TestValidateWorkflowName:
    """測試 _validate_workflow_name 驗證邏輯。"""

    @pytest.mark.parametrize(
        "name",
        [
            "my-workflow",
            "test_workflow",
            "Template1",
            "abc-123_DEF",
            "a",
            "A",
            "0",
        ],
    )
    def test_valid_names_pass(self, name: str):
        """合法名稱不應拋出例外。"""
        _validate_workflow_name(name)  # 不應 raise

    @pytest.mark.parametrize(
        "name",
        [
            "../etc/passwd",
            "..\\windows\\system32",
            "foo/../bar",
            "hello world",
            "name;rm -rf /",
            "workflow.json",
            "",
            "名稱",
            "test/path",
            "test\\path",
            ".hidden",
            "a b",
        ],
    )
    def test_malicious_names_rejected(self, name: str):
        """路徑穿越和其他不合法名稱應被拒絕。"""
        with pytest.raises(typer.BadParameter):
            _validate_workflow_name(name)


class TestWorkflowPath:
    """測試 _workflow_path 整合驗證。"""

    def test_valid_name_returns_path(self):
        """合法名稱應回傳正確路徑。"""
        result = _workflow_path("my-workflow")
        assert result.endswith("my-workflow.json")
        assert ".gov-ai-workflows" in result

    def test_path_traversal_blocked(self):
        """路徑穿越嘗試應被 _workflow_path 攔截。"""
        with pytest.raises(typer.BadParameter):
            _workflow_path("../../etc/passwd")

    def test_dot_dot_slash_blocked(self):
        """../攻擊應被攔截。"""
        with pytest.raises(typer.BadParameter):
            _workflow_path("../secret")

    def test_backslash_traversal_blocked(self):
        """反斜線路徑穿越應被攔截。"""
        with pytest.raises(typer.BadParameter):
            _workflow_path("..\\windows\\system32")


# ============================================================
# create 指令覆蓋率測試
# ============================================================

class TestWorkflowCreate:
    """測試 create 指令的各分支。"""

    def test_create_duplicate_name_rejected(self, tmp_path, monkeypatch):
        """重複名稱應被拒絕（lines 52-53）。"""
        from src.cli import workflow_cmd
        from src.cli.main import app

        wf_dir = str(tmp_path / "wf")
        monkeypatch.setattr(workflow_cmd, "_WORKFLOW_DIR", wf_dir)
        # 互動順序：公文類型, 跳過審查(n), convergence(n), 最大輪數, 輸出格式
        runner.invoke(app, ["workflow", "create", "dup"], input="函\nn\nn\n3\ndocx\n")
        # 第二次應失敗（重複名稱在互動前就被攔截）
        result = runner.invoke(app, ["workflow", "create", "dup"], input="函\nn\nn\n3\ndocx\n")
        assert result.exit_code == 1
        assert "已存在" in result.stdout

    def test_create_convergence_with_skip_info(self, tmp_path, monkeypatch):
        """convergence 模式下 skip_info 分支（line 63）。"""
        from src.cli import workflow_cmd
        from src.cli.main import app

        wf_dir = str(tmp_path / "wf")
        monkeypatch.setattr(workflow_cmd, "_WORKFLOW_DIR", wf_dir)
        # 輸入：公文類型=函, 跳過審查=n, convergence=y, skip_info=y, 輸出格式=docx
        result = runner.invoke(app, ["workflow", "create", "conv-wf"], input="函\nn\ny\ny\ndocx\n")
        assert result.exit_code == 0
        assert "已建立" in result.stdout
        # 驗證 JSON 內容
        with open(os.path.join(wf_dir, "conv-wf.json"), encoding="utf-8") as f:
            wf = json.load(f)
        assert wf["convergence"] is True
        assert wf["skip_info"] is True

    def test_create_invalid_output_format(self, tmp_path, monkeypatch):
        """無效輸出格式應報錯（lines 69-70）。"""
        from src.cli import workflow_cmd
        from src.cli.main import app

        wf_dir = str(tmp_path / "wf")
        monkeypatch.setattr(workflow_cmd, "_WORKFLOW_DIR", wf_dir)
        # 互動順序：公文類型, 跳過審查(n), convergence(n), 最大輪數, 輸出格式(pdf=無效)
        result = runner.invoke(app, ["workflow", "create", "bad-fmt"], input="函\nn\nn\n3\npdf\n")
        assert result.exit_code == 1
        assert "docx 或 markdown" in result.stdout


# ============================================================
# list verbose 讀取失敗 + show 不存在
# ============================================================

class TestWorkflowListVerboseError:
    """測試 list --verbose 的讀取失敗分支（lines 138-142）。"""

    def test_list_verbose_corrupted_json(self, tmp_path, monkeypatch):
        """損壞的 JSON 在 verbose 模式下應顯示讀取失敗。"""
        from src.cli import workflow_cmd
        from src.cli.main import app

        wf_dir = tmp_path / ".gov-ai-workflows"
        wf_dir.mkdir()
        monkeypatch.setattr(workflow_cmd, "_WORKFLOW_DIR", str(wf_dir))
        (wf_dir / "broken.json").write_text("{invalid json", encoding="utf-8")
        result = runner.invoke(app, ["workflow", "list", "--verbose"])
        assert result.exit_code == 0
        assert "讀取失敗" in result.stdout


class TestWorkflowShowNotFound:
    """測試 show 不存在範本（lines 156-157）。"""

    def test_show_not_found(self, tmp_path, monkeypatch):
        from src.cli import workflow_cmd
        from src.cli.main import app

        monkeypatch.setattr(workflow_cmd, "_WORKFLOW_DIR", str(tmp_path / "wf"))
        result = runner.invoke(app, ["workflow", "show", "ghost"])
        assert result.exit_code == 1
        assert "找不到" in result.stdout


# ============================================================
# run 指令（lines 189-222）
# ============================================================

class TestWorkflowRun:
    """測試 run 指令的各分支。"""

    def test_run_not_found(self, tmp_path, monkeypatch):
        """不存在的範本應報錯。"""
        from src.cli import workflow_cmd
        from src.cli.main import app

        monkeypatch.setattr(workflow_cmd, "_WORKFLOW_DIR", str(tmp_path / "wf"))
        result = runner.invoke(app, ["workflow", "run", "ghost", "--input", "測試"])
        assert result.exit_code == 1
        assert "找不到" in result.stdout

    def test_run_calls_generate(self, tmp_path, monkeypatch):
        """run 應讀取範本並呼叫 generate。"""
        from src.cli import workflow_cmd
        from src.cli.main import app

        wf_dir = tmp_path / "wf"
        wf_dir.mkdir()
        monkeypatch.setattr(workflow_cmd, "_WORKFLOW_DIR", str(wf_dir))
        wf = {
            "name": "test-run",
            "doc_type": "函",
            "skip_review": True,
            "max_rounds": 3,
            "convergence": False,
            "skip_info": False,
            "output_format": "docx",
        }
        (wf_dir / "test-run.json").write_text(json.dumps(wf), encoding="utf-8")

        # patch generate 函式（run 內部做 from src.cli.generate import generate as gen_fn）
        with patch("src.cli.generate.generate") as mock_gen:
            result = runner.invoke(app, ["workflow", "run", "test-run", "--input", "測試公文"])

        assert "執行指令" in result.stdout
        assert "--skip-review" in result.stdout
        mock_gen.assert_called_once()

    def test_run_with_convergence(self, tmp_path, monkeypatch):
        """convergence 模式下 run 應帶 --convergence 參數。"""
        from src.cli import workflow_cmd
        from src.cli.main import app

        wf_dir = tmp_path / "wf"
        wf_dir.mkdir()
        monkeypatch.setattr(workflow_cmd, "_WORKFLOW_DIR", str(wf_dir))
        wf = {
            "name": "conv-run",
            "doc_type": "函",
            "skip_review": False,
            "max_rounds": 3,
            "convergence": True,
            "skip_info": True,
            "output_format": "markdown",
        }
        (wf_dir / "conv-run.json").write_text(json.dumps(wf), encoding="utf-8")

        result = runner.invoke(app, ["workflow", "run", "conv-run", "--input", "測試"])
        assert "執行指令" in result.stdout
        assert "--convergence" in result.stdout
        assert "--skip-info" in result.stdout
        assert "--markdown" in result.stdout


# ============================================================
# validate 額外分支
# ============================================================

class TestWorkflowValidateExtra:
    """補齊 validate 指令未覆蓋分支。"""

    def test_validate_not_dict(self, tmp_path):
        """非字典 YAML 應報錯（line 352）。"""
        from src.cli.main import app

        wf = tmp_path / "list.yaml"
        wf.write_text("- item1\n- item2\n", encoding="utf-8")
        result = runner.invoke(app, ["workflow", "validate", str(wf)])
        assert result.exit_code == 1
        assert "映射" in result.stdout or "字典" in result.stdout

    def test_validate_missing_name(self, tmp_path):
        """缺少 name 欄位（line 355）。"""
        from src.cli.main import app

        wf = tmp_path / "no-name.yaml"
        wf.write_text("steps:\n  - name: 起草\n", encoding="utf-8")
        result = runner.invoke(app, ["workflow", "validate", str(wf)])
        assert result.exit_code == 1
        assert "name" in result.stdout

    def test_validate_steps_not_list(self, tmp_path):
        """steps 非列表（line 359）。"""
        from src.cli.main import app

        wf = tmp_path / "bad-steps.yaml"
        wf.write_text("name: 測試\nsteps: not-a-list\n", encoding="utf-8")
        result = runner.invoke(app, ["workflow", "validate", str(wf)])
        assert result.exit_code == 1
        assert "列表" in result.stdout

    def test_validate_step_missing_name(self, tmp_path):
        """步驟缺少 name 欄位（line 365）。"""
        from src.cli.main import app

        wf = tmp_path / "bad-step.yaml"
        wf.write_text("name: 測試\nsteps:\n  - action: 起草\n", encoding="utf-8")
        result = runner.invoke(app, ["workflow", "validate", str(wf)])
        assert result.exit_code == 1
        assert "name" in result.stdout
