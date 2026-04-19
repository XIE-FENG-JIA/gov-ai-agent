import json
from pathlib import Path

from scripts.build_benchmark_corpus import build_corpus
from scripts.run_blind_eval import summarize_results


def _write_example(path: Path, *, title: str, doc_type: str, sender: str, receiver: str, subject: str):
    path.write_text(
        "\n".join(
            [
                "---",
                f'title: "{title}"',
                f'doc_type: "{doc_type}"',
                "---",
                "",
                f"**機關**：{sender}",
                f"**受文者**：{receiver}",
                f"**主旨**：{subject}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_build_corpus_mvp_minimal(tmp_path: Path):
    _write_example(
        tmp_path / "han_01_test.md",
        title="函測試",
        doc_type="函",
        sender="甲機關",
        receiver="乙機關",
        subject="函主旨",
    )
    _write_example(
        tmp_path / "announcement_01_test.md",
        title="公告測試",
        doc_type="公告",
        sender="甲部會",
        receiver="民眾",
        subject="公告主旨",
    )
    _write_example(
        tmp_path / "sign_01_test.md",
        title="簽測試",
        doc_type="簽",
        sender="丙機關",
        receiver="主管",
        subject="簽主旨",
    )

    corpus = build_corpus(tmp_path, ["函", "公告", "簽"], per_type=1)
    assert corpus["total_items"] == 3
    assert len(corpus["items"]) == 3

    by_type = {item["doc_type"]: item for item in corpus["items"]}
    assert by_type["函"]["strict_request"]["ralph_loop"] is True
    assert by_type["函"]["strict_request"]["ralph_target_score"] == 1.0
    assert "請撰寫一份函" in by_type["函"]["user_input"]
    assert by_type["公告"]["reference"]["subject"] == "公告主旨"
    assert by_type["簽"]["source_file"].endswith("sign_01_test.md")


def test_summarize_results_basic():
    results = [
        {
            "id": "han-001",
            "doc_type": "函",
            "success": True,
            "goal_met": False,
            "score": 0.82,
            "risk": "Moderate",
            "duration_sec": 12.3,
            "issue_stats": {"category": {"format": 2, "style": 1}},
        },
        {
            "id": "han-002",
            "doc_type": "函",
            "success": True,
            "goal_met": True,
            "score": 1.0,
            "risk": "Safe",
            "duration_sec": 10.8,
            "issue_stats": {"category": {}},
        },
        {
            "id": "ann-001",
            "doc_type": "公告",
            "success": False,
            "goal_met": False,
            "score": None,
            "risk": None,
            "duration_sec": 8.2,
            "issue_stats": {"category": {"fact": 3}},
        },
    ]

    summary = summarize_results(results)
    assert summary["total"] == 3
    assert summary["success_count"] == 2
    assert summary["goal_met_count"] == 1
    assert summary["avg_score"] == 0.91
    assert summary["by_doc_type"]["函"]["total"] == 2
    top = summary["top_issue_categories"]
    assert top[0]["category"] in {"fact", "format"}
    assert top[0]["count"] >= 2
