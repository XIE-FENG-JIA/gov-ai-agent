from __future__ import annotations

from pathlib import Path

from scripts import run_nightly_integration


def test_build_plan_includes_pytest_and_live_ingest() -> None:
    plan = run_nightly_integration.build_plan(
        python_executable="python",
        pytest_target="tests/integration/test_sources_smoke.py",
        sources="mojlaw,datagovtw",
        limit=2,
        report_path="docs/live-ingest-report.md",
        skip_pytest=False,
        skip_live_ingest=False,
    )

    assert [step.label for step in plan] == [
        "pytest live source smoke",
        "live ingest health report",
    ]
    assert plan[0].argv[:3] == ("python", "-m", "pytest")
    assert plan[0].env_overrides["GOV_AI_RUN_INTEGRATION"] == "1"
    assert plan[1].argv[-1] == "--require-live"


def test_run_plan_dry_run_prints_commands(capsys) -> None:
    plan = run_nightly_integration.build_plan(
        python_executable="python",
        pytest_target="tests/integration/test_sources_smoke.py",
        sources="mojlaw",
        limit=1,
        report_path="docs/live-ingest-report.md",
        skip_pytest=False,
        skip_live_ingest=True,
    )

    rc = run_nightly_integration.run_plan(plan, dry_run=True)

    captured = capsys.readouterr()
    assert rc == 0
    assert "GOV_AI_RUN_INTEGRATION=1 python -m pytest" in captured.out
    assert "[nightly] PASS" in captured.out


def test_run_plan_executes_with_integration_env(monkeypatch) -> None:
    plan = run_nightly_integration.build_plan(
        python_executable="python",
        pytest_target="tests/integration/test_sources_smoke.py",
        sources="mojlaw",
        limit=1,
        report_path="docs/live-ingest-report.md",
        skip_pytest=True,
        skip_live_ingest=False,
    )
    recorded: list[tuple[tuple[str, ...], str | None]] = []

    def fake_run(argv, cwd, env, check):
        recorded.append((tuple(argv), env.get("GOV_AI_RUN_INTEGRATION")))

        class Completed:
            returncode = 0

        return Completed()

    monkeypatch.setattr(run_nightly_integration.subprocess, "run", fake_run)

    rc = run_nightly_integration.run_plan(plan, dry_run=False)

    assert rc == 0
    assert recorded == [
        (
            (
                "python",
                "scripts/live_ingest.py",
                "--sources",
                "mojlaw",
                "--limit",
                "1",
                "--report-path",
                "docs/live-ingest-report.md",
                "--require-live",
            ),
            "1",
        )
    ]


def test_wrapper_scripts_delegate_to_python_runner() -> None:
    shell_text = Path("scripts/run_nightly_integration.sh").read_text(encoding="utf-8")
    ps_text = Path("scripts/run_nightly_integration.ps1").read_text(encoding="utf-8")

    assert "scripts/run_nightly_integration.py" in shell_text
    assert "scripts/run_nightly_integration.py" in ps_text
