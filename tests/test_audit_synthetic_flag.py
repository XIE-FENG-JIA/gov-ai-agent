"""Tests for scripts/audit_synthetic_flag.py"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from audit_synthetic_flag import _has_synthetic_tag, audit_directory, main  # noqa: E402


# ------------------------------------------------------------------ unit helpers

class TestHasSyntheticTag:
    def test_tagged_true(self):
        text = "---\ntitle: foo\nsynthetic: true\n---\nBody"
        assert _has_synthetic_tag(text) is True

    def test_tagged_false(self):
        text = "---\ntitle: foo\nsynthetic: false\n---\nBody"
        assert _has_synthetic_tag(text) is True  # key present, value irrelevant

    def test_tagged_quoted(self):
        text = '---\ntitle: foo\nsynthetic: "true"\n---\nBody'
        assert _has_synthetic_tag(text) is True

    def test_no_frontmatter(self):
        text = "# Just a heading\nsome content"
        assert _has_synthetic_tag(text) is False

    def test_missing_key(self):
        text = "---\ntitle: foo\ndoc_type: bar\n---\nBody"
        assert _has_synthetic_tag(text) is False

    def test_synthetic_not_in_frontmatter(self):
        # synthetic: appears only in body, not in frontmatter
        text = "---\ntitle: foo\n---\nThis document is synthetic: true in content"
        assert _has_synthetic_tag(text) is False


# ------------------------------------------------------------------ audit_directory

class TestAuditDirectory:
    def test_all_tagged(self, tmp_path):
        for i in range(3):
            (tmp_path / f"doc{i}.md").write_text(
                f"---\ntitle: doc{i}\nsynthetic: true\n---\nContent {i}"
            )
        tagged, untagged = audit_directory(tmp_path)
        assert len(tagged) == 3
        assert len(untagged) == 0

    def test_some_untagged(self, tmp_path):
        (tmp_path / "tagged.md").write_text("---\ntitle: t\nsynthetic: true\n---\nok")
        (tmp_path / "untagged.md").write_text("---\ntitle: u\n---\nmissing")
        tagged, untagged = audit_directory(tmp_path)
        assert len(tagged) == 1
        assert len(untagged) == 1

    def test_non_md_files_ignored(self, tmp_path):
        (tmp_path / "readme.txt").write_text("no frontmatter at all")
        (tmp_path / "data.json").write_text('{"key":"value"}')
        (tmp_path / "doc.md").write_text("---\ntitle: t\nsynthetic: true\n---\nok")
        tagged, untagged = audit_directory(tmp_path)
        assert len(tagged) == 1
        assert len(untagged) == 0

    def test_nested_directories(self, tmp_path):
        sub = tmp_path / "subdir"
        sub.mkdir()
        (tmp_path / "root.md").write_text("---\ntitle: r\nsynthetic: true\n---\nok")
        (sub / "nested.md").write_text("---\ntitle: n\nsynthetic: true\n---\nok")
        tagged, untagged = audit_directory(tmp_path)
        assert len(tagged) == 2
        assert len(untagged) == 0

    def test_empty_directory(self, tmp_path):
        tagged, untagged = audit_directory(tmp_path)
        assert tagged == []
        assert untagged == []


# ------------------------------------------------------------------ main()

class TestMain:
    def test_report_mode_all_tagged(self, tmp_path, capsys):
        for i in range(2):
            (tmp_path / f"doc{i}.md").write_text(f"---\nsynthetic: true\n---\nok")
        rc = main(["--path", str(tmp_path)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "2/2 tagged" in out

    def test_report_mode_some_untagged(self, tmp_path, capsys):
        (tmp_path / "ok.md").write_text("---\nsynthetic: true\n---\nok")
        (tmp_path / "bad.md").write_text("---\ntitle: missing\n---\nbody")
        rc = main(["--path", str(tmp_path)])
        assert rc == 0  # no --strict, so exit 0
        out = capsys.readouterr().out
        assert "1/2 tagged" in out

    def test_strict_mode_all_tagged(self, tmp_path):
        (tmp_path / "ok.md").write_text("---\nsynthetic: true\n---\nok")
        rc = main(["--path", str(tmp_path), "--strict"])
        assert rc == 0

    def test_strict_mode_untagged(self, tmp_path):
        (tmp_path / "bad.md").write_text("---\ntitle: missing\n---\nbody")
        rc = main(["--path", str(tmp_path), "--strict"])
        assert rc == 1

    def test_invalid_path(self, tmp_path, capsys):
        rc = main(["--path", str(tmp_path / "nonexistent")])
        assert rc == 2

    def test_quiet_suppresses_per_file(self, tmp_path, capsys):
        (tmp_path / "bad.md").write_text("---\ntitle: missing\n---\nbody")
        main(["--path", str(tmp_path), "--quiet"])
        out = capsys.readouterr().out
        assert "MISSING" not in out

    def test_real_kb_data(self):
        """Smoke test: kb_data/examples must be scannable without crash."""
        kb = Path("kb_data/examples")
        if not kb.is_dir():
            pytest.skip("kb_data/examples not found")
        tagged, untagged = audit_directory(kb)
        total = len(tagged) + len(untagged)
        assert total > 0, "kb_data/examples should contain .md files"
        # All synthetic must be tagged; untagged files are reported separately
        assert len(tagged) > 0, "Expected at least some tagged files"
