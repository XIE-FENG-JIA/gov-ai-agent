## Problem

LOOP5 cross-session dual baseline (red line v5) measures pytest runtime
regression vs LOOP4 closure baseline:

| run | runtime | passed | failed | source |
|-----|---------|--------|--------|--------|
| LOOP4 closure (cold-start) | 153 s | 3801 | 0 | `docs/loop4-closure-report.md` |
| LOOP4 final (xdist + cache) | 69.51 s | 3919 | 0 | post-meeting_exporter fix |
| **LOOP5 run1** (HEAD `484a24c`) | **351.90 s** | 3951 | 0 | `/tmp/pytest_loop5_run1.out` |
| LOOP5 run2 (HEAD `484a24c`) | 132 s | — | 18 errors | click 8.2 incompat (e222a45 fixed) |
| **LOOP5 run3** (HEAD `e222a45`) | **277.89 s** | 3951 | 0 | `/tmp/pytest_loop5_run3.out` |

**Median (run1 + run3)** = **315 s** vs acceptance **200 s** = **+57 % over budget**.
vs LOOP4 cold-start 153 s = **+81 % retreat**.

0 failed → not a 22-fail-style functional regression. Pure runtime drift.

## Candidate root causes

1. **Change 13 cli rotation dispersal**. Track A split `utils.py` (310 lines)
   into `utils_io / utils_display / utils_text` (4 modules) and Track C merged
   3 micro-files (`highlight_cmd / number_cmd / replace_cmd`). Each `from
   src.cli import <X>` now resolves through more `__init__.py` layers,
   inflating collection / import overhead.
2. **Dependency upgrade side-effect**. `cb6f64f fix(ci): add pytest-asyncio
   + anyio to dev deps` triggered pip resolver to lift `click` to 8.2.1 (the
   incompat that produced run2's 18 errors). 8.2 deprecates several
   internals; we pay for compat shims on every import.
3. **Track B iceberg coupling unresolved**. Change 13 T13.2-T13.5 still `[ ]`
   — `generate/export.py → lint_cmd._run_lint` (and 3 other private
   crossings) still alive. Some test fixtures may exercise the slow private
   path.
4. **xdist worker startup variance**. run1 351 s / run3 277 s with 14
   workers each — 27 % spread across two cold-start runs hints at noisy
   worker boot (Windows fork overhead).

## Solution

Change 15 is **observation + bisection plan**, not direct optimisation. The
auto-engineer is mid-flight in change 13 Track B; touching the cli layer or
dependency stack here courts a race. Land a documented bisection plan that
the next governance window (after 13 closes) can execute:

1. **Bisect dispersal vs xdist**. Run `pytest -q --ignore=tests/integration -p
   no:xdist` once on HEAD `e222a45` → if runtime drops to ≤ 200 s, root
   cause is xdist worker boot, not dispersal.
2. **Bisect dependency layer**. Pin `click==8.1.7` in a fresh venv and run
   the same command → if runtime returns to LOOP4 cold-start ~150 s, root
   cause is click 8.2 import overhead.
3. **Bisect change 13**. Checkout HEAD before `79c9ac7`, run the suite, and
   compare. If pre-79c9ac7 ≤ 200 s and post > 200 s, root cause is the cli
   dispersal landed in 79c9ac7.
4. **Document the canonical baseline command**. Once root cause is named,
   write `docs/pytest-baseline-command.md` recording the exact invocation,
   environment fingerprint, expected runtime, and `red line v9` —
   "two-baseline median MUST be reported, not single-run readings".

## Non-Goals

- No revert of change 13 work in this proposal. The 14-13-acceptance-audit
  already documented Track B as `[ ]`; this change does not touch task
  state.
- No dependency downgrade in this proposal. The bisection step 2 records
  the option; the actual pin (if needed) lands in a follow-up change.
- No change to `commit_msg_lint.py` or sensor noise filter.

## Acceptance Criteria

1. `docs/pytest-runtime-regression-iter7.md` exists and lists:
   - run1 / run2 / run3 numbers with HEAD SHAs
   - the four candidate root causes with bisection commands
   - the two-baseline median methodology
2. Red line v9 ("two-baseline median MUST be reported") added to
   `docs/loop4-closure-report.md` red-line list.
3. `spectra validate --changes 15-pytest-runtime-regression-iter7` returns
   `valid`.
4. Task `T15.5` (regression-clear gate) blocked until median ≤ 200 s on a
   single HEAD across two cold-start runs.
