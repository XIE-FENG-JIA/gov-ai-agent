from __future__ import annotations

from pathlib import Path

from scripts import dedupe_results_log


def test_dedupe_lines_collapses_same_root_cause_across_tasks() -> None:
    lines = [
        "[2026-04-20 08:20:05] | [P1.2-COMMIT] | [BLOCKED-ACL] | `.git` 仍有外來 SID DENY ACL；依 ACL-gated 原則不嘗試 `git add/commit`，A 變更保留 working tree 待 Admin / AUTO-RESCUE 落版 | a.py",
        "[2026-04-20 08:21:06] | [P0.W-COMMIT] | [BLOCKED-ACL] | `.git` 仍有外來 SID DENY ACL；依 ACL-gated 原則不嘗試 `git add/commit`，B 變更保留 working tree 待 Admin / AUTO-RESCUE 落版 | b.py",
        "[2026-04-20 08:29:00] | [T7.4-COMMIT] | [BLOCKED-ACL] | `.git` 仍有外來 SID DENY ACL；依 ACL-gated 原則不嘗試 `git add/commit`，C 變更保留 working tree 待 Admin / AUTO-RESCUE 落版 | c.py",
        "[2026-04-21 08:29:00] | [P1.2-COMMIT] | [BLOCKED-ACL] | same reason text | d.py",
    ]

    deduped, removed = dedupe_results_log.dedupe_lines(lines)

    assert removed == 2
    assert len(deduped) == 2
    assert "count=3 (first=08:20:05 last=08:29:00)" in deduped[0]
    assert "2026-04-21 08:29:00" in deduped[1]


def test_dedupe_lines_strict_mode_keeps_different_tasks_separate() -> None:
    lines = [
        "[2026-04-20 08:20:05] | [P1.2-COMMIT] | [BLOCKED-ACL] | `.git` 仍有外來 SID DENY ACL；依 ACL-gated 原則不嘗試 `git add/commit`，A 變更保留 working tree 待 Admin / AUTO-RESCUE 落版 | a.py",
        "[2026-04-20 08:21:06] | [P0.W-COMMIT] | [BLOCKED-ACL] | `.git` 仍有外來 SID DENY ACL；依 ACL-gated 原則不嘗試 `git add/commit`，B 變更保留 working tree 待 Admin / AUTO-RESCUE 落版 | b.py",
    ]

    deduped, removed = dedupe_results_log.dedupe_lines(lines, strict_task_key=True)

    assert removed == 0
    assert deduped == lines


def test_dedupe_lines_leaves_non_target_statuses_unchanged() -> None:
    lines = [
        "[2026-04-20 08:20:05] | [P1.2] | [PASS] | same reason text | a.py",
        "[2026-04-20 08:21:06] | [P1.2] | [PASS] | same reason text | b.py",
    ]

    deduped, removed = dedupe_results_log.dedupe_lines(lines)

    assert removed == 0
    assert deduped == lines


def test_main_writes_sidecar_and_stdout(tmp_path: Path, capsys) -> None:
    log_path = tmp_path / "results.log"
    log_path.write_text(
        "\n".join(
            [
                "[2026-04-20 08:20:05] | [P1.2-COMMIT] | [BLOCKED-ACL] | `.git` 仍有外來 SID DENY ACL；依 ACL-gated 原則不嘗試 `git add/commit`，A 變更保留 working tree 待 Admin / AUTO-RESCUE 落版 | a.py",
                "[2026-04-20 08:21:06] | [P0.W-COMMIT] | [BLOCKED-ACL] | `.git` 仍有外來 SID DENY ACL；依 ACL-gated 原則不嘗試 `git add/commit`，B 變更保留 working tree 待 Admin / AUTO-RESCUE 落版 | b.py",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = dedupe_results_log.main([str(log_path)])

    assert exit_code == 0
    written = (tmp_path / "results.log.dedup").read_text(encoding="utf-8")
    assert "count=2 (first=08:20:05 last=08:21:06)" in written
    assert log_path.read_text(encoding="utf-8").count("BLOCKED-ACL") == 2

    captured = capsys.readouterr()
    stdout = captured.out
    assert "A 變更保留 working tree" in stdout
    assert "# dedupe-summary removed=1" in captured.err


def test_main_in_place_overwrites_input(tmp_path: Path) -> None:
    log_path = tmp_path / "results.log"
    log_path.write_text(
        "\n".join(
            [
                "[2026-04-20 08:20:05] | [P1.2-COMMIT] | [BLOCKED-ACL] | `.git` 仍有外來 SID DENY ACL；依 ACL-gated 原則不嘗試 `git add/commit`，A 變更保留 working tree 待 Admin / AUTO-RESCUE 落版 | a.py",
                "[2026-04-20 08:21:06] | [P0.W-COMMIT] | [BLOCKED-ACL] | `.git` 仍有外來 SID DENY ACL；依 ACL-gated 原則不嘗試 `git add/commit`，B 變更保留 working tree 待 Admin / AUTO-RESCUE 落版 | b.py",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = dedupe_results_log.main([str(log_path), "--in-place"])

    assert exit_code == 0
    assert "count=2 (first=08:20:05 last=08:21:06)" in log_path.read_text(encoding="utf-8")
    assert not (tmp_path / "results.log.dedup").exists()
