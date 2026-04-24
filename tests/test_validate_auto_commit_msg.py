"""Tests for scripts/validate_auto_commit_msg.py"""
import subprocess
import sys
from pathlib import Path

import pytest

# Import the module under test
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from validate_auto_commit_msg import validate, main  # noqa: E402


# ------------------------------------------------------------------ validate()

class TestValidateGoodMessages:
    @pytest.mark.parametrize("msg", [
        "chore(auto-engineer): feat-add-kb-index @2026-04-25",
        "chore(auto-engineer): fix-llm-timeout @2026-04-25",
        "chore(auto-engineer): refactor-manager-split @20260425",
        "chore(auto-engineer): test-quality-gate @2026-04-25T12:00:00",
        "chore(auto-engineer): docs-update-readme @2026-04-25T12:00:00Z",
        "chore(auto-engineer): chore-cleanup-logs @2026-04-25T12:00:00+08:00",
        "chore(auto-engineer): add-bm25-cap @2026-04-25",
        "chore(auto-engineer): remove-dead-code @2026-04-25",
        "chore(auto-engineer): impl-sensor-refresh @2026-04-25",
        "chore(auto-engineer): patch-acl-state @2026-04-25",
        "chore(auto-engineer): perf-index-speed @20260425T120000",
        "chore(auto-engineer): build-docker-update @2026-04-25",
        "chore(auto-engineer): ci-workflow-fix @2026-04-25",
        "chore(auto-engineer): revert-bad-change @2026-04-25",
    ])
    def test_valid(self, msg):
        ok, reason = validate(msg)
        assert ok, f"Should PASS but got: {reason!r}"


class TestValidateBadMessages:
    @pytest.mark.parametrize("msg,expect_fragment", [
        # Original violation patterns
        ("auto-commit: checkpoint", "chore(auto-engineer)"),
        ("auto-commit: BM25 cap", "chore(auto-engineer)"),
        # Wrong scope
        ("chore(engineer): feat-add-kb @2026-04-25", "chore(auto-engineer)"),
        # Missing timestamp
        ("chore(auto-engineer): feat-add-kb", "timestamp"),
        # Missing summary
        ("chore(auto-engineer): feat- @2026-04-25", "does not match"),
        # Unknown type
        ("chore(auto-engineer): unknown-foo @2026-04-25", "does not match"),
        # WIP naked
        ("WIP", "chore(auto-engineer)"),
        # Summary too short
        ("chore(auto-engineer): fix-ab @2026-04-25", "too short"),
        # No separator
        ("chore(auto-engineer): feataddkb @2026-04-25", "does not match"),
        # Missing @
        ("chore(auto-engineer): feat-add-kb 2026-04-25", "does not match"),
    ])
    def test_invalid(self, msg, expect_fragment):
        ok, reason = validate(msg)
        assert not ok, f"Should FAIL but was accepted"
        assert expect_fragment.lower() in reason.lower(), (
            f"Expected fragment {expect_fragment!r} in reason: {reason!r}"
        )


# ------------------------------------------------------------------ main()

class TestMainCLI:
    def test_main_valid_arg(self):
        rc = main(["chore(auto-engineer): feat-add-kb-index @2026-04-25"])
        assert rc == 0

    def test_main_invalid_arg(self):
        rc = main(["auto-commit: checkpoint"])
        assert rc == 1

    def test_main_no_args(self):
        rc = main([])
        assert rc == 1

    def test_main_file_flag(self, tmp_path):
        f = tmp_path / "msg.txt"
        f.write_text("chore(auto-engineer): fix-timeout @2026-04-25\n")
        rc = main(["--file", str(f)])
        assert rc == 0

    def test_main_file_flag_missing_path(self):
        rc = main(["--file"])
        assert rc == 1

    def test_main_stdin(self, monkeypatch, capsys):
        import io
        monkeypatch.setattr("sys.stdin", io.StringIO("chore(auto-engineer): feat-foo @2026-04-25\n"))
        rc = main(["-"])
        assert rc == 0

    def test_main_stdin_invalid(self, monkeypatch, capsys):
        import io
        monkeypatch.setattr("sys.stdin", io.StringIO("WIP\n"))
        rc = main(["-"])
        assert rc == 1


# ------------------------------------------------------------------ subprocess CLI

class TestCLISubprocess:
    """Smoke-test the script as a real subprocess."""

    script = Path(__file__).parent.parent / "scripts" / "validate_auto_commit_msg.py"

    def test_valid_message(self):
        result = subprocess.run(
            [sys.executable, str(self.script),
             "chore(auto-engineer): feat-add-index @2026-04-25"],
            capture_output=True, text=True
        )
        assert result.returncode == 0

    def test_invalid_message(self):
        result = subprocess.run(
            [sys.executable, str(self.script), "auto-commit: checkpoint"],
            capture_output=True, text=True
        )
        assert result.returncode == 1
        assert "REJECT" in result.stderr
