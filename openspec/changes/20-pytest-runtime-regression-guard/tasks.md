# Tasks — Epic 20: Pytest Runtime Regression Guard

Status legend: `[ ]` pending · `[~]` in-progress · `[x]` done

---

## T20.1 — Create `scripts/measure_pytest_runtime.py`

**Goal:** Standalone script that runs `pytest --ignore=tests/integration -q` with a timeout,
records elapsed time to `scripts/pytest_runtime_baseline.json`, exits 0 on success.

- [ ] Accept `--dry-run` flag (skip actual pytest; write last_s=0.0)
- [ ] Accept `--timeout` flag (default 600s)
- [ ] Write `{ "ceiling_s": <float>, "last_s": <float>, "tolerance": 0.20, "measured_at": <ISO> }`
- [ ] If `ceiling_s` not set yet, initialise to `last_s × 1.5` (buffer for first run)
- [ ] Ratchet-down: if `last_s < ceiling_s`, update ceiling to `last_s × 1.5`
- [ ] Acceptance: `python scripts/measure_pytest_runtime.py --dry-run` exits 0

---

## T20.2 — Sensor integration (`check_pytest_runtime`)

**Goal:** Wire the runtime ceiling ratchet into `scripts/sensor_refresh.py`.

- [ ] Add `check_pytest_runtime(repo)` function
- [ ] Load `scripts/pytest_runtime_baseline.json`; return `{"status": "skip"}` if absent
- [ ] Compare `last_s` to `ceiling_s × (1 + tolerance)`; emit `"pytest-runtime-regression"` soft violation if exceeded
- [ ] Populate `sensor["pytest_runtime"]` with `{ceiling_s, last_s, status}`
- [ ] Acceptance: unit test with mocked baseline triggers soft violation at ceiling × 1.21

---

## T20.3 — Unit tests: `tests/test_pytest_runtime_guard.py`

**Goal:** Full coverage without running live pytest.

- [ ] Test: dry-run creates baseline file with correct fields
- [ ] Test: ratchet-down updates ceiling when new run is faster
- [ ] Test: no ratchet-up when new run is slower (ceiling stays)
- [ ] Test: sensor soft violation fires at ceiling × 1.21
- [ ] Test: sensor returns `status: "ok"` when last_s ≤ ceiling
- [ ] Test: missing baseline file → sensor returns `status: "skip"` (no violation)
- [ ] Acceptance: `pytest tests/test_pytest_runtime_guard.py -q` = all passed

---

## T20.4 — Sensor human-readable output

**Goal:** `sensor_refresh.py --human` shows the pytest runtime field clearly.

- [ ] Add `pytest_runtime` section to `--human` markdown output
- [ ] Show `ceiling_s`, `last_s`, `status` in table row
- [ ] Acceptance: `python scripts/sensor_refresh.py --human` includes `pytest_runtime`

---

## T20.5 — Documentation update

**Goal:** Update `CONTRIBUTING.md` and `docs/` with runtime guard usage.

- [ ] Add section "Pytest Runtime Baseline" to `CONTRIBUTING.md`
- [ ] Describe `measure_pytest_runtime.py --dry-run` and `--timeout` flags
- [ ] Note the ratchet-down semantics (ceiling only improves, never worsens)
- [ ] Acceptance: `grep -n "pytest_runtime" CONTRIBUTING.md` shows entry
