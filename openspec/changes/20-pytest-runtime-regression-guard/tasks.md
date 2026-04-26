# Tasks — Epic 20: Pytest Runtime Regression Guard

Status legend: `[ ]` pending · `[~]` in-progress · `[x]` done

---

## T20.1 — Create `scripts/measure_pytest_runtime.py`

**Goal:** Standalone script that runs `pytest --ignore=tests/integration -q` with a timeout,
records elapsed time to `scripts/pytest_runtime_baseline.json`, exits 0 on success.

- [x] Accept `--dry-run` flag (skip actual pytest; write last_s=0.0)
- [x] Accept `--timeout` flag (default 600s)
- [x] Write `{ "ceiling_s": <float>, "last_s": <float>, "tolerance": 0.20, "measured_at": <ISO> }`
- [x] If `ceiling_s` not set yet, initialise to `last_s × 1.5` (buffer for first run)
- [x] Ratchet-down: if `last_s < ceiling_s`, update ceiling to `last_s × 1.5`
- [x] Acceptance: `python scripts/measure_pytest_runtime.py --dry-run` exits 0

---

## T20.2 — Sensor integration (`check_pytest_runtime`)

**Goal:** Wire the runtime ceiling ratchet into `scripts/sensor_refresh.py`.

- [x] Add `check_pytest_runtime(repo)` function
- [x] Load `scripts/pytest_runtime_baseline.json`; return `{"status": "skip"}` if absent
- [x] Compare `last_s` to `ceiling_s × (1 + tolerance)`; emit `"pytest-runtime-regression"` soft violation if exceeded
- [x] Populate `sensor["pytest_runtime"]` with `{ceiling_s, last_s, status}`
- [x] Acceptance: unit test with mocked baseline triggers soft violation at ceiling × 1.21

---

## T20.3 — Unit tests: `tests/test_pytest_runtime_guard.py`

**Goal:** Full coverage without running live pytest.

- [x] Test: dry-run creates baseline file with correct fields
- [x] Test: ratchet-down updates ceiling when new run is faster
- [x] Test: no ratchet-up when new run is slower (ceiling stays)
- [x] Test: sensor soft violation fires at ceiling × 1.21
- [x] Test: sensor returns `status: "ok"` when last_s ≤ ceiling
- [x] Test: missing baseline file → sensor returns `status: "skip"` (no violation)
- [x] Acceptance: `pytest tests/test_pytest_runtime_guard.py -q` = all passed

---

## T20.4 — Sensor human-readable output

**Goal:** `sensor_refresh.py --human` shows the pytest runtime field clearly.

- [x] Add `pytest_runtime` section to `--human` markdown output
- [x] Show `ceiling_s`, `last_s`, `status` in table row
- [x] Acceptance: `python scripts/sensor_refresh.py --human` includes `pytest_runtime`

---

## T20.5 — Documentation update

**Goal:** Update `CONTRIBUTING.md` and `docs/` with runtime guard usage.

- [x] Add section "Pytest Runtime Baseline" to `CONTRIBUTING.md`
- [x] Describe `measure_pytest_runtime.py --dry-run` and `--timeout` flags
- [x] Note the ratchet-down semantics (ceiling only improves, never worsens)
- [x] Acceptance: `grep -n "pytest_runtime" CONTRIBUTING.md` shows entry
