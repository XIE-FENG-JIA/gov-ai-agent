# Tasks — Epic 22: Source Adapter Health Metrics

Status legend: `[ ]` pending · `[~]` in-progress · `[x]` done

---

## T22.1 — Create `scripts/adapter_health.py` probe script

**Goal:** Lightweight dry-fetch (limit=3) for each adapter; write JSON report.

- [x] Implement `AdapterHealthProbe` class with `run(dry_run=False)` method
- [x] Support `--dry-run` flag (skip live fetch, write mock-zero report)
- [x] Support `--human` flag (icon + adapter + latency_ms + count + status)
- [x] Write `scripts/adapter_health_report.json` with per-adapter results
- [x] Acceptance: `python scripts/adapter_health.py --dry-run` exits 0

---

## T22.2 — Sensor integration: `check_adapter_health()`

**Goal:** Add `adapter_health` field to `sensor_refresh.py`.

- [x] Add `check_adapter_health()` in `scripts/sensor_refresh.py`
- [x] Load `adapter_health_report.json` if present; skip gracefully if absent
- [x] Yield soft violation when any adapter `count == 0` or `status == "error"`
- [x] Include `adapter_health` key in sensor JSON output
- [x] Acceptance: `python scripts/sensor_refresh.py` outputs `adapter_health` field

---

## T22.3 — Unit tests `tests/test_adapter_health.py`

**Goal:** ≥ 6 unit tests covering all probe paths (no live network calls).

- [x] Test: dry-run writes report with all adapters present
- [x] Test: mock adapter returning 0 records → status `"zero_records"`
- [x] Test: mock adapter raising exception → status `"error"`
- [x] Test: mock adapter returning 3 records → status `"ok"`
- [x] Test: `--human` output contains adapter name + count
- [x] Test: sensor `check_adapter_health()` fires soft violation on zero count
- [x] Acceptance: all 6+ tests pass with no live calls

---

## T22.4 — Sensor violation wiring

**Goal:** Verify soft violation is wired end-to-end.

- [x] Run `sensor_refresh.py` with mocked zero-count report → confirm soft violation
- [x] Run `sensor_refresh.py` with mocked ok report → confirm no violation
- [x] Add to `tests/test_sensor_refresh.py`: adapter_health soft violation case
- [x] Acceptance: `python -m pytest tests/test_sensor_refresh.py -q` = all passed

---

## T22.5 — `--human` output and CONTRIBUTING docs

**Goal:** Human-readable summary + documentation.

- [x] Verify `adapter_health.py --human` prints icon + adapter name
- [x] Add "Adapter Health" section to `CONTRIBUTING.md`
- [x] Document: when to run probe, how to interpret icons, how to add a new adapter
- [x] Acceptance: `grep "Adapter Health" CONTRIBUTING.md` hits

---

## T22.6 — Full regression + commit

**Goal:** No regressions; commit all changes.

- [x] Run `python -m pytest --ignore=tests/integration -q -x` = all passed
- [x] Run targeted tests: `python -m pytest tests/test_adapter_health.py tests/test_sensor_refresh.py -q`
- [x] Commit: `feat(sensor): epic 22 source adapter health metrics`
- [x] Acceptance: full suite passed; `git rev-list HEAD..origin/main` = 0
