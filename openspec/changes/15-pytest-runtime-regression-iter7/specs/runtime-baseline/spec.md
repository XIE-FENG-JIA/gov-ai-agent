# Spec: Pytest Runtime Regression Iter 7 (LOOP5 Baseline Drift)

## Summary

LOOP5 cross-session dual baseline showed pytest runtime regressed from
LOOP4 cold-start 153 s to a 351 + 277 (median 315) s window — +57 % over
the 200 s acceptance and +81 % over LOOP4. 0 failed; pure runtime drift.
This change documents the regression, four candidate root causes, and a
bisection plan; introduces red-line v9 (two-baseline median requirement).

## ADDED Requirements

### Requirement: Two-baseline median 顯示且超 200 s acceptance 必文件化

Whenever the cross-session dual baseline median for `pytest -q
--ignore=tests/integration` exceeds 200 s on the master branch, the
governance layer MUST:

1. Open a Spectra change (or extend an existing one) capturing both runs'
   runtime, HEAD SHA, passed/failed counts, and a candidate root cause
   list.
2. Block the next "ratchet down" of the runtime soft target until the
   regression clears (median back ≤ 200 s for two cold-start runs on the
   same HEAD).
3. Add the change reference to `docs/loop4-closure-report.md` red-line
   ledger.

#### Scenario: dual-baseline 351 + 277 = 315 median triggers spec change

- **GIVEN** LOOP5 run1 = 351.90 s, run2 = click incompat, run3 = 277.89 s
- **WHEN** governance computes median of valid runs (run1, run3) = 315 s
- **THEN** Spectra change `15-pytest-runtime-regression-iter7` opens
- **AND** `docs/pytest-runtime-regression-iter7.md` is created with the
  numbers and bisection plan

### Requirement: Each candidate root cause has a reproducible bisection command

Every candidate root cause in `docs/pytest-runtime-regression-iter7.md`
MUST cite a runnable bisection command (single shell line). The command
output is appended back to the doc under "Bisection results" so future
audits do not re-derive.

#### Scenario: xdist worker bisection runs cleanly

- **GIVEN** the audit doc lists "Candidate 4 — xdist worker startup"
- **WHEN** an operator runs `pytest -q --ignore=tests/integration -p
  no:xdist` and pastes the runtime back
- **THEN** the doc records `runtime = X s; xdist_root_cause = Y/N`
- **AND** the verdict is propagated to T15.3 commit

### Requirement: LOOP closure red-lines kept in single source

`docs/loop4-closure-report.md` (or its successor) is the single source of
truth for LOOP-level red lines. New red lines (e.g., v9 "two-baseline
median MUST be reported") MUST land there, with a short reference back to
the originating Spectra change.

#### Scenario: red line v9 appears in closure report

- **WHEN** a developer reads `docs/loop4-closure-report.md`
- **THEN** red-line v9 is listed with its trigger condition
  (cross-session median > 200 s) and a pointer to change 15
- **AND** the wording matches `red-line v9 — two-baseline median MUST be
  reported, not single-run readings`
