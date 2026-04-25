from __future__ import annotations

from pathlib import Path

import yaml

from src.cli.verify_cmd import collect_citation_verification_checks
from src.document.exporter import DocxExporter
from src.knowledge.corpus_provenance import is_active_corpus_metadata


def _read_frontmatter(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    assert raw.startswith("---\n"), f"{path} missing frontmatter"
    parts = raw.split("---\n", 2)
    assert len(parts) >= 3, f"{path} has malformed frontmatter"
    meta = yaml.safe_load(parts[1]) or {}
    assert isinstance(meta, dict), f"{path} frontmatter must be a mapping"
    return meta


def test_corpus_provenance_guard() -> None:
    corpus_root = Path("kb_data") / "corpus"
    corpus_files = sorted(corpus_root.rglob("*.md"))

    if len(corpus_files) < 9:
        pytest.skip("corpus files not available in this environment (CI/CD)")

    assert len(corpus_files) >= 9, "expected at least 9 real corpus files"

    synthetic_paths: list[str] = []
    fixture_fallback_paths: list[str] = []

    for path in corpus_files:
        meta = _read_frontmatter(path)
        if bool(meta.get("synthetic")):
            synthetic_paths.append(path.as_posix())
        if bool(meta.get("fixture_fallback")):
            fixture_fallback_paths.append(path.as_posix())

    assert not synthetic_paths, f"synthetic corpus files found: {synthetic_paths}"
    assert not fixture_fallback_paths, f"fixture-backed corpus files found: {fixture_fallback_paths}"


def test_kb_rebuild_and_verify_provenance_rule_rejects_untrusted_metadata() -> None:
    assert is_active_corpus_metadata({"synthetic": False, "fixture_fallback": False}) is True
    assert is_active_corpus_metadata({"synthetic": True, "fixture_fallback": False}) is False
    assert is_active_corpus_metadata({"synthetic": False, "fixture_fallback": True}) is False
    assert is_active_corpus_metadata({"deprecated": True, "synthetic": False, "fixture_fallback": False}) is False


def test_only_real_rebuild_verification_rejects_fixture_backed_repo_evidence(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus" / "mojlaw"
    corpus_dir.mkdir(parents=True)
    (corpus_dir / "A0030055.md").write_text(
        "---\n"
        "title: 公文程式條例\n"
        "source_id: A0030055\n"
        "source_url: https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=A0030055\n"
        "synthetic: false\n"
        "fixture_fallback: true\n"
        "---\n"
        "# 公文程式條例\n",
        encoding="utf-8",
    )

    output = tmp_path / "fixture-fallback.docx"
    DocxExporter().export(
        """# 函

### 主旨
引用測試

### 說明
依據《公文程式條例》辦理[^1]。

### 參考來源 (AI 引用追蹤)
[^1]: [Level A] 公文程式條例 | URL: https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=A0030055 | Hash: a1b2c3d4
""",
        str(output),
        citation_metadata={
            "reviewed_sources": [
                {
                    "index": 1,
                    "title": "公文程式條例",
                    "source_level": "A",
                    "source_url": "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=A0030055",
                    "record_id": "A0030055",
                    "content_hash": "a1b2c3d4",
                }
            ],
            "engine": "openrouter/elephant-alpha",
            "ai_generated": True,
        },
    )

    checks = collect_citation_verification_checks(output, corpus_dir=tmp_path / "corpus")
    assert checks[-1][0] == "citation[1] A0030055"
    assert checks[-1][1] is False
    assert checks[-1][2] == "找不到對應 repo evidence"
