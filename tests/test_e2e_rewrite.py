from __future__ import annotations

from pathlib import Path

import pytest

import src.e2e_rewrite as e2e_rewrite


def test_load_real_corpus_skips_synthetic_and_assigns_source_levels(tmp_path: Path) -> None:
    mojlaw_dir = tmp_path / "mojlaw"
    datagov_dir = tmp_path / "datagovtw"
    mojlaw_dir.mkdir(parents=True)
    datagov_dir.mkdir(parents=True)

    (mojlaw_dir / "real.md").write_text(
        "---\n"
        "title: 公文程式條例\n"
        "source_id: A0030055\n"
        "source_url: https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=A0030055\n"
        "doc_type: law\n"
        "synthetic: false\n"
        "---\n"
        "法規內容\n",
        encoding="utf-8",
    )
    (datagov_dir / "real.md").write_text(
        "---\n"
        "title: 政府開放資料\n"
        "source_doc_no: 162455\n"
        "source_url: https://data.gov.tw/dataset/162455\n"
        "doc_type: dataset\n"
        "synthetic: false\n"
        "---\n"
        "資料內容\n",
        encoding="utf-8",
    )
    (datagov_dir / "synthetic.md").write_text(
        "---\n"
        "title: fake\n"
        "source_id: SYN001\n"
        "synthetic: true\n"
        "---\n"
        "假資料\n",
        encoding="utf-8",
    )
    (datagov_dir / "fixture-fallback.md").write_text(
        "---\n"
        "title: fixture fallback\n"
        "source_id: FIX001\n"
        "synthetic: false\n"
        "fixture_fallback: true\n"
        "---\n"
        "假來源\n",
        encoding="utf-8",
    )

    corpus = e2e_rewrite.load_real_corpus(tmp_path)

    assert sorted(corpus) == ["162455", "A0030055"]
    assert corpus["A0030055"]["source_level"] == "A"
    assert corpus["162455"]["source_level"] == "B"
    assert "SYN001" not in corpus
    assert "FIX001" not in corpus


def test_find_scenario_supports_tagged_prompt_and_rejects_unknown() -> None:
    scenario = e2e_rewrite.SCENARIOS[0]
    prompt = (
        "<requirement-data>\n"
        f"- Subject: {scenario.requirement['subject']}\n"
        "</requirement-data>\n"
        "<user-input>\n"
        "irrelevant wrapper text\n"
        "</user-input>\n"
    )

    matched = e2e_rewrite._find_scenario(prompt)

    assert matched.slug == scenario.slug

    with pytest.raises(ValueError, match="unable to match scenario"):
        e2e_rewrite._find_scenario("totally unknown prompt")


def test_run_rewrite_e2e_fails_when_citation_source_is_not_traceable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenario = e2e_rewrite.SCENARIOS[0]
    corpus = e2e_rewrite.load_real_corpus()

    monkeypatch.setattr(e2e_rewrite, "SCENARIOS", (scenario,))
    monkeypatch.setattr(
        e2e_rewrite,
        "read_docx_citation_metadata",
        lambda _: {
            "citation_count": 1,
            "source_doc_ids": [scenario.source_ids[0]],
            "citation_sources_json": [
                {
                    "source_doc_id": scenario.source_ids[0],
                    "title": "known",
                },
                {
                    "source_doc_id": "UNKNOWN-SOURCE",
                    "title": "unknown",
                },
            ],
        },
    )

    with pytest.raises(AssertionError, match="not traceable"):
        e2e_rewrite.run_rewrite_e2e(tmp_path / "out")

    assert scenario.source_ids[0] in corpus


def test_write_e2e_report_creates_parent_directory(tmp_path: Path) -> None:
    report_path = tmp_path / "nested" / "e2e-report.md"
    e2e_rewrite.write_e2e_report(
        [
            {
                "doc_type": "函",
                "output_path": str(tmp_path / "han.docx"),
                "citation_count": 2,
                "source_doc_ids": ["A0030055", "162455"],
                "traced_paths": ["kb_data/corpus/mojlaw/a.md"],
                "audit_errors": 0,
                "audit_warnings": 1,
                "user_input": "請寫一份函",
            }
        ],
        report_path,
    )

    content = report_path.read_text(encoding="utf-8")
    assert report_path.exists()
    assert "# E2E Rewrite Report" in content
    assert "## Traceability" in content
    assert "kb_data/corpus/mojlaw/a.md" in content
