"""Tests for scripts/squash_checkpoint_window.py (T-COMMIT-NOISE-FLOOR b)."""

from __future__ import annotations

from datetime import datetime, timezone

from scripts import squash_checkpoint_window


# --------------------------------------------------------------------------- helpers


def _make_fake_git(log_output: str, stats_by_hash: dict[str, str] | None = None):
    """Return a fake git runner for unit tests."""
    stats = stats_by_hash or {}

    def fake_git(args: list[str]) -> str:
        if args[:1] == ["log"]:
            return log_output
        if args[:3] == ["show", "--stat", "--format="]:
            return stats.get(args[3], "")
        raise AssertionError(f"unexpected git call: {args}")

    return fake_git


# --------------------------------------------------------------------------- unit tests


def test_is_checkpoint_detects_all_patterns() -> None:
    assert squash_checkpoint_window.is_checkpoint("auto-commit: checkpoint")
    assert squash_checkpoint_window.is_checkpoint("chore(auto-engineer): checkpoint snapshot")
    assert squash_checkpoint_window.is_checkpoint("copilot-auto: batch round 9")
    assert not squash_checkpoint_window.is_checkpoint("feat(cli): add kb rebuild")
    assert not squash_checkpoint_window.is_checkpoint("docs(spec): update tasks")
    assert not squash_checkpoint_window.is_checkpoint("chore(test): post-commit hook trigger")


def test_list_commits_with_timestamps_parses_correctly() -> None:
    log_output = (
        "aaa111 1714000000 auto-commit: checkpoint\n"
        "bbb222 1714000060 feat(cli): real change\n"
    )
    fake = _make_fake_git(log_output)
    commits = squash_checkpoint_window.list_commits_with_timestamps(2, git_runner=fake)
    assert len(commits) == 2
    assert commits[0].hash == "aaa111"
    assert commits[0].timestamp == 1714000000
    assert commits[1].hash == "bbb222"
    assert commits[1].subject == "feat(cli): real change"


def test_list_commits_skips_malformed_lines() -> None:
    log_output = "aaa111 notanumber subject\nbbb222 1714000000 good\n"
    fake = _make_fake_git(log_output)
    commits = squash_checkpoint_window.list_commits_with_timestamps(2, git_runner=fake)
    assert len(commits) == 1
    assert commits[0].hash == "bbb222"


def test_list_commits_handles_empty_output() -> None:
    fake = _make_fake_git("")
    commits = squash_checkpoint_window.list_commits_with_timestamps(5, git_runner=fake)
    assert commits == []


def test_read_changed_files_extracts_paths() -> None:
    stat = "src/cli/main.py | 3 +++\ntests/test_kb.py | 2 --\n 2 files changed, 3 insertions\n"
    fake = _make_fake_git("", {"abc123": stat})
    files = squash_checkpoint_window.read_changed_files("abc123", git_runner=fake)
    assert files == ["src/cli/main.py", "tests/test_kb.py"]


def test_classify_scope_single_area() -> None:
    assert squash_checkpoint_window._classify_scope(["src/cli/main.py", "src/cli/utils.py"]) == "cli"
    assert squash_checkpoint_window._classify_scope(["tests/test_foo.py"]) == "tests"
    assert squash_checkpoint_window._classify_scope(["program.md", "results.log"]) == "docs"
    assert squash_checkpoint_window._classify_scope([]) == "repo"


def test_classify_scope_mixed_returns_repo() -> None:
    result = squash_checkpoint_window._classify_scope(["src/cli/main.py", "tests/test_kb.py"])
    assert result == "repo"


def test_group_checkpoint_commits_groups_within_window() -> None:
    log = (
        "aaa111 1714000000 auto-commit: checkpoint\n"
        "bbb222 1714000120 auto-commit: checkpoint\n"
        "ccc333 1714000240 auto-commit: checkpoint\n"
        "ddd444 1714001000 feat(cli): semantic commit\n"
        "eee555 1714009999 auto-commit: checkpoint\n"
    )
    stats = {
        "aaa111": "src/cli/main.py | 1 +\n",
        "bbb222": "src/cli/main.py | 2 ++\n",
        "ccc333": "tests/test_cli.py | 3 +++\n",
        "eee555": "docs/readme.md | 1 +\n",
    }
    fake = _make_fake_git(log, stats)
    commits = squash_checkpoint_window.list_commits_with_timestamps(5, git_runner=fake)
    groups = squash_checkpoint_window.group_checkpoint_commits(
        commits, window_secs=300, git_runner=fake
    )
    # aaa+bbb+ccc are within 240s — one group; eee is isolated — no group
    assert len(groups) == 1
    assert len(groups[0].commits) == 3
    assert "chore(" in groups[0].proposed_msg
    assert "3" in groups[0].proposed_msg


def test_group_checkpoint_commits_returns_empty_if_no_checkpoints() -> None:
    log = "aaa111 1714000000 feat(api): real work\nbbb222 1714000060 docs(spec): update\n"
    fake = _make_fake_git(log)
    commits = squash_checkpoint_window.list_commits_with_timestamps(2, git_runner=fake)
    groups = squash_checkpoint_window.group_checkpoint_commits(
        commits, window_secs=300, git_runner=fake
    )
    assert groups == []


def test_group_checkpoint_commits_no_group_if_all_singletons() -> None:
    """Commits spaced far apart should not form groups (need >= 2 for a group)."""
    log = (
        "aaa111 1714000000 auto-commit: checkpoint\n"
        "bbb222 1714009999 auto-commit: checkpoint\n"
    )
    stats = {
        "aaa111": "src/cli/main.py | 1 +\n",
        "bbb222": "src/cli/main.py | 1 +\n",
    }
    fake = _make_fake_git(log, stats)
    commits = squash_checkpoint_window.list_commits_with_timestamps(2, git_runner=fake)
    groups = squash_checkpoint_window.group_checkpoint_commits(
        commits, window_secs=300, git_runner=fake
    )
    assert groups == []


def test_render_plan_includes_squash_fields() -> None:
    group = squash_checkpoint_window.SquashGroup(
        commits=[
            squash_checkpoint_window.CommitInfo("aaa111aaa111", 1714000000, "auto-commit: checkpoint"),
            squash_checkpoint_window.CommitInfo("bbb222bbb222", 1714000120, "auto-commit: checkpoint"),
        ],
        proposed_msg="chore(repo): squash 2 checkpoint snapshots",
        window_start=datetime.fromtimestamp(1714000000, tz=timezone.utc),
        window_end=datetime.fromtimestamp(1714000120, tz=timezone.utc),
    )
    plan = squash_checkpoint_window.render_plan([group], 2, 5, 300)
    assert "# Checkpoint Squash Plan" in plan
    assert "squash 2 checkpoint snapshots" in plan
    assert "rebase_cmd" in plan
    assert "aaa111aaa111" in plan
    assert "commits_reducible: 1" in plan


def test_render_plan_no_groups_message() -> None:
    plan = squash_checkpoint_window.render_plan([], 0, 10, 300)
    assert "No squashable checkpoint groups found." in plan
    assert "squashable_groups: 0" in plan


def test_propose_squash_msg_format() -> None:
    commits = [
        squash_checkpoint_window.CommitInfo("abc", 100, "auto-commit:", files=["src/cli/main.py"]),
        squash_checkpoint_window.CommitInfo("def", 200, "auto-commit:", files=["src/cli/utils.py"]),
    ]
    msg = squash_checkpoint_window._propose_squash_msg(commits)
    assert msg.startswith("chore(cli):")
    assert "2" in msg
    assert "checkpoint" in msg
