# Tasks — Epic 21: Cold Runtime Root-Cause Fix

Status legend: `[ ]` pending · `[~]` in-progress · `[x]` done

---

## T21.1 — Record real pytest runtime baseline

**Goal:** Run `measure_pytest_runtime.py` without `--dry-run` to write a real
`ceiling_s` and `last_s` into `scripts/pytest_runtime_baseline.json`.

- [ ] Run `python scripts/measure_pytest_runtime.py --timeout 600`
- [ ] Verify `pytest_runtime_baseline.json` has non-zero `ceiling_s` and `last_s`
- [ ] Run `python scripts/sensor_refresh.py` — confirm `pytest_runtime.status != "skip"`
- [ ] Acceptance: sensor `pytest_runtime.status` is `"ok"` or `"violation"`

---

## T21.2 — Profile suite: identify top-10 slowest tests

**Goal:** Run `pytest --durations=10` and capture results in a doc.

- [ ] Run `python -m pytest --ignore=tests/integration -q --durations=10 --no-header`
- [ ] Write `docs/pytest-runtime-profile.md` with top-10 table (test name / duration)
- [ ] Classify each slow test: chromadb cold-cache / fixture / LLM call / other
- [ ] Acceptance: `docs/pytest-runtime-profile.md` exists and lists ≥ 10 entries

---

## T21.3 — Fix top 3 slowest tests

**Goal:** Apply targeted patches to the top 3 slowest tests using the same
strategies proven in T-PYTEST-RUNTIME-FIX-v3 (mock bypass, early-return, fixture).

- [ ] Fix slow test #1: apply mock/fixture patch, verify test still green
- [ ] Fix slow test #2: apply mock/fixture patch, verify test still green
- [ ] Fix slow test #3: apply mock/fixture patch, verify test still green
- [ ] Run targeted tests: all 3 must still pass
- [ ] Acceptance: 3 targeted tests pass; total runtime improves ≥ 10%

---

## T21.4 — Validate sensor ceiling activation

**Goal:** Confirm the Epic 20 ceiling guard is now active with a real baseline.

- [ ] Re-run `python scripts/measure_pytest_runtime.py` after fixes
- [ ] Verify `ceiling_s > 0` and `last_s > 0` in `pytest_runtime_baseline.json`
- [ ] Run `python scripts/sensor_refresh.py --human` — `pytest_runtime` row shows real values
- [ ] Acceptance: `sensor["pytest_runtime"]["status"]` = `"ok"`

---

## T21.5 — Full regression test + commit

**Goal:** Verify no test regressions from patches; commit all changes.

- [ ] Run `python -m pytest --ignore=tests/integration -q -x` = all passed
- [ ] Run `python -m pytest tests/test_pytest_runtime_guard.py tests/test_sensor_refresh.py -q`
- [ ] Commit: `perf(tests): epic 21 cold runtime root-cause fix + profile`
- [ ] Acceptance: full suite passed; `git rev-list HEAD..origin/main` = 0
