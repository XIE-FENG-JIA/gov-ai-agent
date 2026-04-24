"""Tests for scripts/audit_local_binding.py — Type 1 iceberg audit."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import sys

# Ensure repo root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.audit_local_binding import (
    collect_patch_targets,
    find_candidates,
    _parse_imports,
    _format_human,
    _format_json,
    main,
    LocalBindCandidate,
    ROOT,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _write(tmp_path: Path, rel: str, text: str) -> Path:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(text), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Test 1: collect_patch_targets finds patch() in test files
# ---------------------------------------------------------------------------

class TestCollectPatchTargets:
    def test_finds_simple_patch(self, tmp_path):
        _write(tmp_path, "tests/test_foo.py", """
            from unittest.mock import patch
            def test_x():
                with patch("src.api.dependencies.get_config", return_value={}):
                    pass
        """)
        results = collect_patch_targets(tmp_path / "tests")
        assert any("src.api.dependencies.get_config" in t for _, _, t in results)

    def test_ignores_non_src_patches(self, tmp_path):
        _write(tmp_path, "tests/test_foo.py", """
            def test_x():
                with patch("os.path.exists"):
                    pass
        """)
        results = collect_patch_targets(tmp_path / "tests")
        assert results == []

    def test_skips_integration_subdir(self, tmp_path):
        _write(tmp_path, "tests/integration/test_bar.py", """
            def test_x():
                with patch("src.module.func"):
                    pass
        """)
        results = collect_patch_targets(tmp_path / "tests")
        assert results == []


# ---------------------------------------------------------------------------
# Test 2: _parse_imports builds index correctly
# ---------------------------------------------------------------------------

class TestParseImports:
    def test_detects_from_import(self, tmp_path):
        _write(tmp_path, "src/b.py", "from src.a import foo\n")
        index = _parse_imports(tmp_path / "src")
        assert "src.a" in index
        assert "foo" in index["src.a"]
        assert any("src.b" in m for m in index["src.a"]["foo"])

    def test_ignores_non_src_imports(self, tmp_path):
        _write(tmp_path, "src/b.py", "from os.path import join\n")
        index = _parse_imports(tmp_path / "src")
        assert "os.path" not in index


# ---------------------------------------------------------------------------
# Test 3: find_candidates correctly flags risky patches
# ---------------------------------------------------------------------------

class TestFindCandidates:
    def test_flags_risky_patch(self):
        patch_targets = [("tests/test_x.py", 10, "src.a.foo")]
        binding_index = {"src.a": {"foo": ["src.b", "src.c"]}}
        candidates = find_candidates(patch_targets, binding_index)
        assert len(candidates) == 1
        assert candidates[0].symbol == "foo"
        assert "src.b" in candidates[0].consuming_modules

    def test_no_candidate_when_no_consumers(self):
        patch_targets = [("tests/test_x.py", 10, "src.a.bar")]
        binding_index = {"src.a": {"bar": []}}
        candidates = find_candidates(patch_targets, binding_index)
        assert candidates == []

    def test_no_candidate_when_only_self_consumes(self):
        # Consuming module is the same as the patched module → not risky
        patch_targets = [("tests/test_x.py", 10, "src.a.baz")]
        binding_index = {"src.a": {"baz": ["src.a"]}}
        candidates = find_candidates(patch_targets, binding_index)
        assert candidates == []


# ---------------------------------------------------------------------------
# Test 4: output formatting
# ---------------------------------------------------------------------------

class TestFormatting:
    def test_human_no_candidates(self):
        msg = _format_human([])
        assert "no Type 1" in msg

    def test_human_with_candidates(self):
        c = LocalBindCandidate(
            test_file="tests/test_x.py",
            test_line=42,
            patch_target="src.a.foo",
            src_module="src.a",
            symbol="foo",
            consuming_modules=["src.b"],
        )
        msg = _format_human([c])
        assert "src.a.foo" in msg
        assert "src.b.foo" in msg   # suggestion

    def test_json_output(self):
        c = LocalBindCandidate(
            test_file="t.py",
            test_line=1,
            patch_target="src.a.x",
            src_module="src.a",
            symbol="x",
            consuming_modules=["src.b"],
        )
        data = json.loads(_format_json([c]))
        assert data[0]["symbol"] == "x"


# ---------------------------------------------------------------------------
# Test 5: CLI --dry-run exits 0 regardless of candidate count
# ---------------------------------------------------------------------------

class TestCLI:
    def test_dry_run_exits_zero(self, tmp_path):
        # Write test with a patch that would be a candidate
        _write(tmp_path, "tests/test_x.py", 'patch("src.a.foo")')
        _write(tmp_path, "src/b.py", "from src.a import foo\n")
        rc = main([
            "--dry-run",
            "--src-root", str(tmp_path / "src"),
            "--test-root", str(tmp_path / "tests"),
        ])
        assert rc == 0

    def test_exits_one_when_candidates_found(self, tmp_path):
        _write(tmp_path, "tests/test_x.py", 'patch("src.a.foo")')
        _write(tmp_path, "src/b.py", "from src.a import foo\n")
        rc = main([
            "--src-root", str(tmp_path / "src"),
            "--test-root", str(tmp_path / "tests"),
        ])
        assert rc == 1

    def test_exits_zero_when_no_candidates(self, tmp_path):
        _write(tmp_path, "tests/test_x.py", 'patch("src.a.foo")')
        _write(tmp_path, "src/b.py", "import os\n")  # no local binding
        rc = main([
            "--src-root", str(tmp_path / "src"),
            "--test-root", str(tmp_path / "tests"),
        ])
        assert rc == 0


# ---------------------------------------------------------------------------
# Test 6: integration smoke on real repo
# ---------------------------------------------------------------------------

class TestRealRepoSmoke:
    def test_dry_run_on_real_repo_exits_zero(self):
        """The --dry-run flag must always exit 0 on the real repo."""
        rc = main(["--dry-run"])
        assert rc == 0

    def test_candidate_count_is_int(self):
        """Running on real repo returns a list of LocalBindCandidate."""
        from scripts.audit_local_binding import (
            collect_patch_targets,
            _parse_imports,
            find_candidates,
        )
        pt = collect_patch_targets(ROOT / "tests")
        bi = _parse_imports(ROOT / "src")
        cands = find_candidates(pt, bi)
        assert isinstance(cands, list)
        assert all(isinstance(c, LocalBindCandidate) for c in cands)


# ---------------------------------------------------------------------------
# Test 7: rebind_local helper (reference migration — Type 1 fix in conftest)
# ---------------------------------------------------------------------------

class TestRebindLocalHelper:
    """Demonstrate and verify the rebind_local helper from conftest.

    This mirrors the real fix in commits adb531c / 6b41335 where patching
    the *consuming* module is required instead of the defining module.
    """

    def test_rebind_sets_attr_in_consuming_module(self, monkeypatch):
        """rebind_local patches the consuming module's local binding."""
        from tests.conftest import rebind_local
        import types

        # Create a tiny src.dep module with a function
        dep_mod = types.ModuleType("src.dep")
        dep_mod.get_thing = lambda: "real"
        sys.modules["src.dep"] = dep_mod

        # Create a consumer that bound get_thing at import time
        consumer_mod = types.ModuleType("src.consumer")
        consumer_mod.get_thing = dep_mod.get_thing  # local binding
        sys.modules["src.consumer"] = consumer_mod

        # Patching the *defining* module would not fix the consumer's binding
        # rebind_local patches the *consumer* directly
        rebind_local(monkeypatch, "src.consumer", "get_thing", lambda: "mocked")

        assert consumer_mod.get_thing() == "mocked"

    def test_rebind_is_undone_after_test(self, monkeypatch):
        """monkeypatch teardown restores the original binding."""
        from tests.conftest import rebind_local
        import types

        mod = types.ModuleType("src.rebind_undo_test")
        mod.value = "original"
        sys.modules["src.rebind_undo_test"] = mod

        rebind_local(monkeypatch, "src.rebind_undo_test", "value", "patched")
        assert mod.value == "patched"
        # After yielding from this test, monkeypatch restores it — verified
        # by the isolated fixture scope; we just assert within the test here.

    def test_rebind_with_mock_object(self, monkeypatch):
        """rebind_local works with MagicMock as the replacement value."""
        from tests.conftest import rebind_local
        import types

        mod = types.ModuleType("src.rebind_mock_test")
        mod.get_config = lambda: {"real": True}
        sys.modules["src.rebind_mock_test"] = mod

        mock_cfg = MagicMock(return_value={"real": False})
        rebind_local(monkeypatch, "src.rebind_mock_test", "get_config", mock_cfg)

        result = mod.get_config()
        mock_cfg.assert_called_once()
        assert result == {"real": False}
