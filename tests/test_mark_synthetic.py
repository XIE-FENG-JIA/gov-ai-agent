from pathlib import Path

from scripts.mark_synthetic import ensure_synthetic_frontmatter, run


def test_ensure_synthetic_frontmatter_adds_frontmatter_when_missing():
    updated, changed, had_frontmatter = ensure_synthetic_frontmatter("內文第一行\n第二行\n")

    assert changed is True
    assert had_frontmatter is False
    assert updated.startswith("---\nsynthetic: true\n---\n")
    assert updated.endswith("內文第一行\n第二行\n")


def test_ensure_synthetic_frontmatter_appends_flag_to_existing_frontmatter():
    raw = "\n".join(
        [
            "---",
            'title: "測試"',
            'doc_type: "函"',
            "---",
            "本文",
            "",
        ]
    )

    updated, changed, had_frontmatter = ensure_synthetic_frontmatter(raw)

    assert changed is True
    assert had_frontmatter is True
    assert 'title: "測試"\ndoc_type: "函"\nsynthetic: true' in updated


def test_ensure_synthetic_frontmatter_keeps_existing_true_flag():
    raw = "\n".join(
        [
            "---",
            'title: "測試"',
            "synthetic: true",
            "---",
            "本文",
            "",
        ]
    )

    updated, changed, had_frontmatter = ensure_synthetic_frontmatter(raw)

    assert updated == raw
    assert changed is False
    assert had_frontmatter is True


def test_run_marks_all_markdown_files_in_directory(tmp_path: Path):
    first = tmp_path / "a.md"
    second = tmp_path / "b.md"
    ignored = tmp_path / "note.txt"
    first.write_text("---\ntitle: one\n---\nbody\n", encoding="utf-8")
    second.write_text("plain body\n", encoding="utf-8")
    ignored.write_text("skip\n", encoding="utf-8")

    changed, total = run(tmp_path)

    assert total == 2
    assert changed == 2
    assert "synthetic: true" in first.read_text(encoding="utf-8")
    assert second.read_text(encoding="utf-8").startswith("---\nsynthetic: true\n---\n")
