from __future__ import annotations

from pathlib import Path

from scripts import find_auto_commit_source


def test_scan_paths_finds_exact_and_supporting_hits(tmp_path: Path) -> None:
    hooks_dir = tmp_path / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True)
    (hooks_dir / "rescue.ps1").write_text(
        "git commit -m \"auto-commit: auto-engineer checkpoint\"\n",
        encoding="utf-8",
    )
    (tmp_path / ".claude" / "scheduled_tasks.lock").write_text(
        "{\"sessionId\":\"abc\"}\n",
        encoding="utf-8",
    )

    hits = find_auto_commit_source.scan_paths([hooks_dir, tmp_path / ".claude" / "scheduled_tasks.lock"])

    assert any(hit.pattern == "auto-commit:" and hit.confidence == "high" for hit in hits)
    assert any(hit.path.endswith("scheduled_tasks.lock") and hit.confidence == "med" for hit in hits)


def test_probe_scheduler_reports_error_details() -> None:
    def fake_runner(_: list[str]):
        class Result:
            returncode = 1
            stdout = ""
            stderr = "ERROR: The system cannot find the path specified."

        return Result()

    probe = find_auto_commit_source.probe_scheduler(runner=fake_runner)

    assert probe.status == "unavailable"
    assert "cannot find the path specified" in probe.detail.lower()


def test_render_report_contains_required_sections(tmp_path: Path) -> None:
    output_path = tmp_path / "admin-rescue-template.md"
    hits = [
        find_auto_commit_source.CandidateHit(
            path="C:/Users/Administrator/.claude/hooks/rescue.ps1",
            line_no=12,
            pattern="auto-commit:",
            snippet='git commit -m "auto-commit: auto-engineer checkpoint"',
            confidence="high",
            rationale="exact rescue template token present",
        )
    ]
    scheduler = find_auto_commit_source.SchedulerProbe(
        command="schtasks.exe /query /fo CSV /v",
        status="candidate-found",
        detail="scheduler candidates found",
        matches=("Claude-Rescue => C:\\Users\\Administrator\\.claude\\rescue.bat",),
    )

    report = find_auto_commit_source.render_report(hits, scheduler, [Path("C:/Users/Administrator/.claude/hooks")])
    find_auto_commit_source.write_report(output_path, report)

    content = output_path.read_text(encoding="utf-8")
    assert "## §candidates" in content
    assert "## §template-diff" in content
    assert "## §admin-action" in content
    assert "## scheduler-probe" in content
    assert "chore(rescue): restore auto-engineer working tree" in content
