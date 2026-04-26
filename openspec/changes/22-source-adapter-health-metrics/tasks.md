# Tasks — Epic 22: Source Adapter Health Metrics

Status legend: `[ ]` pending · `[~]` in-progress · `[x]` done

---

## T22.1 — Create `scripts/adapter_health.py` probe script

**Goal:** Lightweight dry-fetch (limit=3) for each adapter; write JSON report.

- [ ] Implement `AdapterHealthProbe` class with `run(dry_run=False)` method
- [ ] Support `--dry-run` flag (skip live fetch, write mock-zero report)
- [ ] Support `--human` flag (icon + adapter + latency_ms + count + status)
- [ ] Write `scripts/adapter_health_report.json` with per-adapter results
- [ ] Acceptance: `python scripts/adapter_health.py --dry-run` exits 0

---

## T22.2 — Sensor integration: `check_adapter_health()`

**Goal:** Add `adapter_health` field to `sensor_refresh.py`.

- [ ] Add `check_adapter_health()` in `scripts/sensor_refresh.py`
- [ ] Load `adapter_health_report.json` if present; skip gracefully if absent
- [ ] Yield soft violation when any adapter `count == 0` or `status == "error"`
- [ ] Include `adapter_health` key in sensor JSON output
- [ ] Acceptance: `python scripts/sensor_refresh.py` outputs `adapter_health` field

---

## T22.3 — Unit tests `tests/test_adapter_health.py`

**Goal:** ≥ 6 unit tests covering all probe paths (no live network calls).

- [ ] Test: dry-run writes report with all adapters present
- [ ] Test: mock adapter returning 0 records → status `"zero_records"`
- [ ] Test: mock adapter raising exception → status `"error"`
- [ ] Test: mock adapter returning 3 records → status `"ok"`
- [ ] Test: `--human` output contains adapter name + count
- [ ] Test: sensor `check_adapter_health()` fires soft violation on zero count
- [ ] Acceptance: all 6+ tests pass with no live calls

---

## T22.4 — Sensor violation wiring

**Goal:** Verify soft violation is wired end-to-end.

- [ ] Run `sensor_refresh.py` with mocked zero-count report → confirm soft violation
- [ ] Run `sensor_refresh.py` with mocked ok report → confirm no violation
- [ ] Add to `tests/test_sensor_refresh.py`: adapter_health soft violation case
- [ ] Acceptance: `python -m pytest tests/test_sensor_refresh.py -q` = all passed

---

## T22.5 — `--human` output and CONTRIBUTING docs

**Goal:** Human-readable summary + documentation.

- [ ] Verify `adapter_health.py --human` prints icon (✅/⚠️/❌) + adapter name
- [ ] Add "Adapter Health" section to `CONTRIBUTING.md`
- [ ] Document: when to run probe, how to interpret icons, how to add a new adapter
- [ ] Acceptance: `grep "Adapter Health" CONTRIBUTING.md` hits

---

## T22.6 — Full regression + commit

**Goal:** No regressions; commit all changes.

- [ ] Run `python -m pytest --ignore=tests/integration -q -x` = all passed
- [ ] Run targeted tests: `python -m pytest tests/test_adapter_health.py tests/test_sensor_refresh.py -q`
- [ ] Commit: `feat(sensor): epic 22 source adapter health metrics`
- [ ] Acceptance: full suite passed; `git rev-list HEAD..origin/main` = 0
