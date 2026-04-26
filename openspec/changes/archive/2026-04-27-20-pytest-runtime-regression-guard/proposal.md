# Proposal — Epic 20: Pytest Runtime Regression Guard

## Problem

The pytest cold-start runtime has regressed repeatedly (v8.0: 167s → v8.8: 436s) with no
automated guard to detect or block regressions. The sensor records a `runtime_baseline` floor
but there is no ceiling-based ratchet that raises a soft violation when the test suite grows
significantly slower.

Key observations from engineer-log v8.8 / v8.10 reflections:
- `runtime_baseline.json` stores a floor (too-low = violation) but not a ceiling (too-high = regression)
- cold-start at 436s triggered no sensor violation despite being 2.6× above previous run
- The only guard was a hardcoded `50.0s` value in `sensor_refresh.py` that was never live-measured
- Epic 19 established recall-ratchet semantics (floor-only) — we need the inverse for runtime

## Goal

Add a sensor-integrated pytest runtime ceiling ratchet that:
1. Records the last-measured pytest runtime in a `scripts/pytest_runtime_baseline.json` file
2. Emits a sensor soft violation when current runtime exceeds `ceiling × (1 + tolerance)`
3. Updates the ceiling when a *faster* run is recorded (ratchet down = improvement)
4. Is fully testable without actually running pytest (inject mock timing)

## Design

```
scripts/
  pytest_runtime_baseline.json   # { "ceiling_s": <float>, "tolerance": 0.20 }
  measure_pytest_runtime.py      # standalone runner: time pytest, write baseline, exit 0/1
tests/
  test_pytest_runtime_guard.py   # unit tests (mock timing, no live pytest)
```

Sensor integration: new `check_pytest_runtime(repo)` function → populates
`sensor["pytest_runtime"]` with `{"ceiling_s", "last_s", "status"}`.

## Acceptance Criteria

- `python scripts/measure_pytest_runtime.py --dry-run` exits 0, writes `pytest_runtime_baseline.json`
- `sensor_refresh.py --human` shows `pytest_runtime` field
- Soft violation fires when injected time exceeds `ceiling × 1.20`
- `pytest tests/test_pytest_runtime_guard.py -q` = all passed, no live test run needed
