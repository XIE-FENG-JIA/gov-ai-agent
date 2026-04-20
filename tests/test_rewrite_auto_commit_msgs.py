from __future__ import annotations

from pathlib import Path
import subprocess

from scripts import rewrite_auto_commit_msgs


def test_collect_suggestions_filters_auto_commit_and_inferrs_scope() -> None:
    stat_by_commit = {
        "aaa111": "src/cli/main.py | 2 ++\nprogram.md | 1 +\n",
        "bbb222": "tests/test_sources_ingest.py | 5 +++--\n",
        "ccc333": "docs/architecture.md | 3 ++-\n",
    }

    def fake_git(args: list[str]) -> str:
        if args[:2] == ["log", "--format=%H %s"]:
            return (
                "aaa111 auto-commit: auto-engineer checkpoint\n"
                "bbb222 auto-commit: auto-engineer checkpoint\n"
                "ccc333 docs(program): keep good commit\n"
            )
        if args[:3] == ["show", "--stat", "--format="]:
            return stat_by_commit[args[3]]
        raise AssertionError(args)

    suggestions = rewrite_auto_commit_msgs.collect_suggestions(limit=3, git_runner=fake_git)

    assert [item.commit_hash for item in suggestions] == ["aaa111", "bbb222"]
    assert suggestions[0].proposed_msg.startswith("feat(cli):")
    assert suggestions[0].confidence == "med"
    assert suggestions[1].proposed_msg.startswith("test(tests):")
    assert suggestions[1].files_top3 == "tests/test_sources_ingest.py"


def test_render_report_includes_markdown_table() -> None:
    report = rewrite_auto_commit_msgs.render_report(
        [
            rewrite_auto_commit_msgs.CommitSuggestion(
                commit_hash="abc123",
                current_msg="auto-commit: auto-engineer checkpoint",
                proposed_msg="docs(docs): sync docs progress",
                files_top3="program.md, results.log",
                confidence="high",
            )
        ],
        limit=40,
    )

    assert "# Rescue Commit Plan" in report
    assert "| commit_hash | current_msg | proposed_msg | files_top3 | confidence |" in report
    assert "rewrite_candidates: 1" in report


def test_apply_rewrites_runs_filter_branch_and_preserves_auto_rescue_token(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_command(args: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        captured["args"] = args
        captured["env"] = env
        return subprocess.CompletedProcess(args, 0, stdout="ok", stderr="")

    exit_code = rewrite_auto_commit_msgs.apply_rewrites(
        [
            rewrite_auto_commit_msgs.CommitSuggestion(
                commit_hash="abc123",
                current_msg="auto-commit: auto-engineer checkpoint",
                proposed_msg="feat(cli): sync cli changes",
                files_top3="src/cli/main.py",
                confidence="high",
            )
        ],
        "HEAD~5..HEAD",
        command_runner=fake_command,
    )

    assert exit_code == 0
    assert captured["args"] == [
        "git",
        "filter-branch",
        "-f",
        "--msg-filter",
        captured["args"][4],
        "HEAD~5..HEAD",
    ]
    env = captured["env"]
    assert isinstance(env, dict)
    assert "abc123" in env["GOV_AI_REWRITE_MAP"]
    assert rewrite_auto_commit_msgs.AUTO_RESCUE_TOKEN in env["GOV_AI_REWRITE_MAP"]


def test_main_apply_returns_blocked_when_acl_deny(tmp_path: Path, monkeypatch, capsys) -> None:
    output_path = tmp_path / "rescue-commit-plan.md"

    monkeypatch.setattr(
        rewrite_auto_commit_msgs,
        "collect_suggestions",
        lambda limit: [
            rewrite_auto_commit_msgs.CommitSuggestion(
                commit_hash="abc123",
                current_msg="auto-commit: auto-engineer checkpoint",
                proposed_msg="feat(cli): sync cli changes",
                files_top3="src/cli/main.py",
                confidence="high",
            )
        ],
    )
    monkeypatch.setattr(rewrite_auto_commit_msgs, "git_acl_has_deny", lambda: True)

    exit_code = rewrite_auto_commit_msgs.main(
        ["--limit", "12", "--output", str(output_path), "--apply", "--range", "HEAD~5..HEAD"]
    )

    assert exit_code == 2
    content = output_path.read_text(encoding="utf-8")
    assert "mode: apply-ready" in content
    stderr = capsys.readouterr().err
    assert "apply blocked" in stderr


def test_main_writes_report_file(tmp_path: Path, monkeypatch) -> None:
    output_path = tmp_path / "rescue-commit-plan.md"

    monkeypatch.setattr(
        rewrite_auto_commit_msgs,
        "collect_suggestions",
        lambda limit: [
            rewrite_auto_commit_msgs.CommitSuggestion(
                commit_hash="abc123",
                current_msg="auto-commit: auto-engineer checkpoint",
                proposed_msg="feat(cli): sync cli changes",
                files_top3="src/cli/main.py",
                confidence="high",
            )
        ],
    )

    exit_code = rewrite_auto_commit_msgs.main(["--limit", "12", "--output", str(output_path)])

    assert exit_code == 0
    content = output_path.read_text(encoding="utf-8")
    assert "rewrite_candidates: 1" in content
    assert "feat(cli): sync cli changes" in content
