# Pytest Runtime Regression Iter 7 — LOOP5 Audit

> Spectra change: `15-pytest-runtime-regression-iter7`
> HEAD at audit: `e222a45 fix(tests): drop CliRunner(mix_stderr=) ctor arg — click 8.2 incompat after cb6f64f dep upgrade`
> Auditor: pua-loop session under Administrator shell
> Date: 2026-04-26

## Numbers

| run | HEAD | runtime | passed | failed | source log |
|-----|------|---------|--------|--------|------------|
| LOOP4 cold-start | (LOOP4 closure) | 153 s | 3801 | 0 | `docs/loop4-closure-report.md` |
| LOOP4 final | (xdist + cache hot) | 69.51 s | 3919 | 0 | LOOP4 final |
| LOOP5 run1 | `484a24c` | **351.90 s** | 3951 | 0 | `/tmp/pytest_loop5_run1.out` |
| LOOP5 run2 | `484a24c` | 132 s | — | 18 errors | `/tmp/pytest_loop5_run2.out` (click 8.2 incompat, fixed by `e222a45`) |
| LOOP5 run3 | `e222a45` | **277.89 s** | 3951 | 0 | `/tmp/pytest_loop5_run3.out` |

**Median valid runs (run1 + run3)** = **314.9 s** ≈ **315 s**.

vs acceptance **200 s**: **+57 % over budget**.
vs LOOP4 cold-start **153 s**: **+81 % retreat**.

0 failed → not a 22-fail-style functional regression. Pure runtime drift.

## Candidate root causes + bisection commands

### Candidate 1 — Change 13 cli rotation dispersal

Track A split `utils.py` (310 lines) into 4 modules
(`utils.py / utils_io.py / utils_display.py / utils_text.py`); Track C
merged 3 micro-files. Each `from src.cli import <X>` now resolves through
more `__init__.py` layers, inflating collection / import overhead.

Bisection command:

```bash
git stash
git checkout 65eeebf  # last commit before change 13 cli rotation
python -m pytest -q --ignore=tests/integration --tb=no --no-header
git checkout main
git stash pop
```

### Candidate 2 — `click==8.2` import overhead

`cb6f64f fix(ci): add pytest-asyncio + anyio` triggered pip resolver to
lift click to 8.2.1 (the same upgrade that produced run2's 18 errors).
8.2 deprecates several internals; we may pay for compat shims on every
import.

Bisection command:

```bash
python -m venv /tmp/click81-venv
/tmp/click81-venv/Scripts/pip install -e .  # or recreate dev deps
/tmp/click81-venv/Scripts/pip install 'click==8.1.7'
/tmp/click81-venv/Scripts/python -m pytest -q --ignore=tests/integration
```

### Candidate 3 — Track B iceberg coupling unresolved

Change 13 T13.2-T13.5 still `[ ]`. `generate/export.py → lint_cmd._run_lint`
and 3 other private crossings still alive. Some test fixtures may exercise
the slow private path.

Bisection: not a single command — would require Track B to land then
re-baseline. Captured here as "wait-and-see" once 13 closes.

### Candidate 4 — xdist worker startup overhead

run1 351 s / run3 277 s with 14 workers each — 27 % spread across two
cold-start runs hints at noisy worker boot (Windows fork emulation).

Bisection command:

```bash
python -m pytest -q --ignore=tests/integration -p no:xdist --no-header
```

## Bisection results

(populated by T15.3 / T15.4 / T15.5 commits)

| candidate | command run | runtime | verdict |
|-----------|------------|---------|---------|
| C4 — xdist | `pytest -p no:xdist --override-ini="addopts=-q"` HEAD `8868f69` | **589.4 s** | **RULED OUT** — removing xdist is 2.8× *slower* (589 s vs 214 s). xdist provides genuine parallel speedup; not a boot-overhead sink. |
| C2 — click | (T15.4 pending) | — | — |
| C1 — dispersal | (deferred until 13 closes) | — | — |

## Red line v9

> Two-baseline median MUST be reported, not single-run readings. Any
> cross-session run > 200 s triggers a Spectra change documenting both
> runs and a bisection plan.

Added to `docs/loop4-closure-report.md` red-line ledger.
