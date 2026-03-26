"""workflow_cmd.py 路徑穿越防護測試。"""
import pytest
import typer

from src.cli.workflow_cmd import _validate_workflow_name, _workflow_path


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
