# Tasks: 15-pytest-runtime-regression-iter7

- [x] **T15.1** Document run1 / run2 / run3 numbers + HEAD SHAs + candidate root causes in `docs/pytest-runtime-regression-iter7.md`.
  Requirements:
  - Two-baseline median 顯示且超 200 s acceptance 必文件化
  Validation: `wc -l docs/pytest-runtime-regression-iter7.md` ≥ 60; `rg "351.90|277.89" docs/pytest-runtime-regression-iter7.md` matches both runs.
  Commit: included in T15.5 batched commit.

- [x] **T15.2** Add red line v9 ("two-baseline median MUST be reported") to `docs/loop4-closure-report.md`.
  Requirements:
  - LOOP closure red-lines kept in single source
  Validation: `rg "v9" docs/loop4-closure-report.md` matches; wording covers cold-start + median requirement.
  Commit: included in T15.5.

- [ ] **T15.3** Bisection step 1 — `pytest -p no:xdist` on HEAD `e222a45`. If runtime drops ≤ 200 s, xdist worker boot is the root cause.
  Requirements:
  - Each candidate root cause has a reproducible bisection command
  Validation: append result line to `docs/pytest-runtime-regression-iter7.md` "Bisection results" section; runtime + verdict.
  Commit: `chore(governance): T15.3 xdist bisection result for runtime regression`

- [ ] **T15.4** Bisection step 2 — fresh venv `click==8.1.7` baseline. If runtime ≤ 180 s, click 8.2 import overhead is the root cause.
  Requirements:
  - Each candidate root cause has a reproducible bisection command
  Validation: append result line to `docs/pytest-runtime-regression-iter7.md`.
  Commit: `chore(governance): T15.4 click pin bisection result for runtime regression`

- [ ] **T15.5** Regression-clear gate. Two cold-start runs on a single HEAD with median ≤ 200 s.
  Requirements:
  - Two-baseline median 顯示且超 200 s acceptance 必文件化
  Validation: two pytest runs on the same HEAD logged in `docs/pytest-runtime-regression-iter7.md`; median ≤ 200 s.
  Commit: `chore(sensor): T15.5 — runtime regression cleared (median ≤ 200 s)`
