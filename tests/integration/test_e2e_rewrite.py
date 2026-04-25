from pathlib import Path

import pytest

from src.e2e_rewrite import run_rewrite_e2e

_CORPUS_PATH = Path("kb_data/corpus")


def test_rewrite_pipeline_generates_five_traceable_docx(tmp_path: Path) -> None:
    if not _CORPUS_PATH.exists() or not any(_CORPUS_PATH.rglob("*.md")):
        pytest.skip(
            f"corpus not found at {_CORPUS_PATH} — populate kb_data/corpus to enable this test"
        )
    report_path = tmp_path / "e2e-report.md"
    results = run_rewrite_e2e(tmp_path, report_path=report_path)

    assert len(results) == 5
    assert {item["doc_type"] for item in results} == {"函", "公告", "簽", "令", "開會通知單"}
    assert report_path.exists()

    for item in results:
        assert Path(item["output_path"]).exists()
        assert item["citation_count"] > 0
        assert item["source_doc_ids"]
        assert item["traced_paths"]
