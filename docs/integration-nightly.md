# Nightly Integration Gate

## Purpose
This gate keeps the live-source path honest after the local corpus was promoted
to 9 real public documents.

The nightly job runs two checks behind the same entrypoint:

1. `tests/integration/test_sources_smoke.py`
2. `scripts/live_ingest.py --require-live`

Both commands run with `GOV_AI_RUN_INTEGRATION=1` so skipped smoke tests turn
into real network checks.

## Entrypoints
Linux / macOS / Git Bash:

```bash
bash scripts/run_nightly_integration.sh --dry-run
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_nightly_integration.ps1 --dry-run
```

Direct Python entry:

```bash
python scripts/run_nightly_integration.py --dry-run
```

## Default Behavior
Without flags, the runner executes:

```text
python -m pytest tests/integration/test_sources_smoke.py -q --no-header
python scripts/live_ingest.py --sources mojlaw,datagovtw,executive_yuan_rss,mohw,fda --limit 1 --report-path docs/live-ingest-report.md --require-live
```

Important details:

- `GOV_AI_RUN_INTEGRATION=1` is injected for both steps
- live ingest writes `docs/live-ingest-report.md`
- the runner exits on the first failing step
- `--dry-run` prints the exact commands and returns `0`

## Execution Frequency
Run this gate once per night and again before any release that changes:

- source adapters
- `scripts/live_ingest.py`
- fixture/live fallback behavior
- integration env wiring

Recommended schedule:

- daily at off-peak hours
- one extra manual run after source-adapter refactors

## Failure Notification
Treat any non-zero exit as an operator-visible failure.

Minimum notification payload:

- failing step name
- exit code
- command text
- timestamp

Recommended sinks:

- CI job failure
- chat webhook
- on-call email or incident board

## Recovery SOP
When the nightly gate fails:

1. rerun `--dry-run` first to verify the exact command plan
2. rerun the failing step alone from the printed command
3. inspect `docs/live-ingest-report.md` if the ingest step failed
4. check whether upstream public sites changed schema, rate-limit behavior, or availability
5. if the failure is adapter-specific, keep fixture fallback disabled until the root cause is understood

Do not mark the gate green by unsetting `GOV_AI_RUN_INTEGRATION`.
That would only re-hide skipped integration smoke.

## Local Overrides
Useful flags:

- `--skip-pytest`
- `--skip-live-ingest`
- `--sources mojlaw,datagovtw`
- `--limit 2`
- `--report-path output/nightly-live-ingest.md`
- `--python C:\Python311\python.exe`

These are for debugging only.
Nightly automation should keep the default two-step gate unless the program is
updated.
