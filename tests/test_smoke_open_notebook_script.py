from __future__ import annotations

from pathlib import Path

from scripts.smoke_open_notebook import smoke_import


def test_smoke_import_reports_vendor_unready_for_git_stub(tmp_path: Path) -> None:
    vendor_path = tmp_path / "open-notebook"
    (vendor_path / ".git").mkdir(parents=True)

    report = smoke_import(vendor_path)

    assert report.status == "vendor-unready"
    assert "only .git metadata" in report.message


def test_smoke_import_reports_incomplete_git_checkout(tmp_path: Path) -> None:
    vendor_path = tmp_path / "open-notebook"
    git_dir = vendor_path / ".git"
    git_dir.mkdir(parents=True)
    (git_dir / "config.lock").write_text("", encoding="utf-8")
    (git_dir / "description").write_text("incomplete clone\n", encoding="utf-8")

    report = smoke_import(vendor_path)

    assert report.status == "vendor-incomplete"
    assert "vendor checkout is incomplete" in report.message
    assert "config.lock" in report.message


def test_smoke_import_supports_flat_package_layout(tmp_path: Path) -> None:
    vendor_path = tmp_path / "open-notebook"
    package_dir = vendor_path / "open_notebook"
    package_dir.mkdir(parents=True)
    (vendor_path / "pyproject.toml").write_text("[project]\nname='open-notebook'\n", encoding="utf-8")
    (package_dir / "__init__.py").write_text("__version__ = '1.2.3'\n", encoding="utf-8")

    report = smoke_import(vendor_path)

    assert report.status == "ok"
    assert report.version == "1.2.3"
    assert report.origin.endswith("__init__.py")


def test_smoke_import_supports_src_layout(tmp_path: Path) -> None:
    vendor_path = tmp_path / "open-notebook"
    package_dir = vendor_path / "src" / "open_notebook"
    package_dir.mkdir(parents=True)
    (vendor_path / "pyproject.toml").write_text("[project]\nname='open-notebook'\n", encoding="utf-8")
    (package_dir / "__init__.py").write_text("__version__ = '9.9.9'\n", encoding="utf-8")

    report = smoke_import(vendor_path)

    assert report.status == "ok"
    assert report.version == "9.9.9"


def test_smoke_import_reports_missing_dependency(tmp_path: Path) -> None:
    vendor_path = tmp_path / "open-notebook"
    package_dir = vendor_path / "open_notebook"
    package_dir.mkdir(parents=True)
    (vendor_path / "pyproject.toml").write_text("[project]\nname='open-notebook'\n", encoding="utf-8")
    (package_dir / "__init__.py").write_text("import nonexistent_dep_for_open_notebook\n", encoding="utf-8")

    report = smoke_import(vendor_path)

    assert report.status == "import-error"
    assert report.missing_modules == ["nonexistent_dep_for_open_notebook"]


def test_smoke_import_warns_when_vendor_head_drifted_from_pin(
    tmp_path: Path, monkeypatch
) -> None:
    vendor_path = tmp_path / "open-notebook"
    package_dir = vendor_path / "open_notebook"
    package_dir.mkdir(parents=True)
    (vendor_path / "pyproject.toml").write_text("[project]\nname='open-notebook'\n", encoding="utf-8")
    (package_dir / "__init__.py").write_text("__version__ = '1.2.3'\n", encoding="utf-8")
    (tmp_path / "open-notebook.pin").write_text(
        "commit=aaaaaaaaaaaa\nupstream=https://github.com/lfnovo/open-notebook.git\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "scripts.smoke_open_notebook._resolve_git_head",
        lambda vendor: "bbbbbbbbbbbb" if vendor == vendor_path else None,
    )

    report = smoke_import(vendor_path)

    assert report.status == "ok"
    assert report.pin_warning == "pinned aaaaaaaaaaaa but vendor HEAD is bbbbbbbbbbbb"
    assert "pin_warning=pinned aaaaaaaaaaaa but vendor HEAD is bbbbbbbbbbbb" in report.to_line()


def test_smoke_import_accepts_short_pinned_sha_prefix(
    tmp_path: Path, monkeypatch
) -> None:
    vendor_path = tmp_path / "open-notebook"
    package_dir = vendor_path / "open_notebook"
    package_dir.mkdir(parents=True)
    (vendor_path / "pyproject.toml").write_text("[project]\nname='open-notebook'\n", encoding="utf-8")
    (package_dir / "__init__.py").write_text("__version__ = '1.2.3'\n", encoding="utf-8")
    (tmp_path / "open-notebook.pin").write_text("commit=bbbbbbbbbbbb\n", encoding="utf-8")

    monkeypatch.setattr(
        "scripts.smoke_open_notebook._resolve_git_head",
        lambda vendor: "bbbbbbbbbbbb9999" if vendor == vendor_path else None,
    )

    report = smoke_import(vendor_path)

    assert report.status == "ok"
    assert report.pin_warning == ""
