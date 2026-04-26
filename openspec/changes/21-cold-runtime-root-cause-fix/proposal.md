# Proposal — Epic 21: Cold Runtime Root-Cause Fix

## Problem

Pytest cold-start runtime has been steadily increasing across recent batches with no
identified root cause:

- v8.8:  80.43s  (first measurement, LiteLLM lazy-load applied)
- v8.10: 158.43s (+97% in one batch)
- v8.11: ~146s   (partial recovery via xdist)

Epic 20 added a ceiling ratchet that *detects* regression but does not *prevent* it.
The sensor `pytest_runtime` field shows `status: "skip"` because `last_s=0.0`
(baseline only written by `--dry-run`; real measurement never recorded).

Key observations from engineer-log v8.10 / v8.14 reflections:
- `pytest_runtime_baseline.json` has `ceiling_s=0.0` (dry-run only) → ceiling guard
  is effectively disabled
- Top slowest tests were never profiled systematically
- Possible root causes: chromadb cold-cache per test, fixture accumulation, pytest
  collection overhead, or xdist worker startup overhead

## Goal

1. Record a real `last_s` in `pytest_runtime_baseline.json` (not dry-run) so the
   Epic 20 ceiling guard becomes active.
2. Profile the suite with `--durations=10` to identify the top-10 slowest tests.
3. Fix the top 3 slowest tests if they are due to chromadb cold-cache or fixture
   issues (same pattern as T-PYTEST-RUNTIME-FIX-v3 era fixes).
4. Achieve `pytest_runtime.status = "ok"` in sensor output.

## Design

```
scripts/
  measure_pytest_runtime.py   # existing; run WITHOUT --dry-run to record real last_s
  pytest_runtime_baseline.json  # update ceiling_s from real measurement
tests/
  test_pytest_runtime_guard.py  # existing; add test for real-measure path
docs/
  pytest-runtime-profile.md    # profiling results and fix rationale
```

Sensor integration: `check_pytest_runtime()` already implemented (Epic 20); this epic
activates it by providing a real `last_s` measurement.

## Acceptance Criteria

- `scripts/pytest_runtime_baseline.json` has non-zero `ceiling_s` and `last_s`
- `python scripts/sensor_refresh.py` shows `pytest_runtime.status = "ok"` (not "skip")
- `pytest --durations=10 --ignore=tests/integration -q` profile captured in
  `docs/pytest-runtime-profile.md`
- Top 3 slow tests addressed (patch or documented as intentional)
- `pytest tests/test_pytest_runtime_guard.py -q` = all passed
