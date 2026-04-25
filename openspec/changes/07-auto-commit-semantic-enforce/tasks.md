# Tasks: 07-auto-commit-semantic-enforce

- [x] **T7.1** Add `scripts/validate_auto_commit_msg.py` wrapping `commit_msg_lint.py` with structured rejection envelope.
  Requirements:
  - Auto-engineer commit messages must conform to Conventional Commit
  Validation: `python -m pytest tests/test_validate_auto_commit_msg.py -q` (≥ 8 tests covering accept / reject / envelope shape / empty / comment-only)
  Commit: `feat(governance): add validate_auto_commit_msg runtime wrapper`

- [x] **T7.2** Write `tests/test_validate_auto_commit_msg.py` with at least 8 cases (valid semantic / checkpoint rejection / WIP rejection / empty / stdin path / envelope structure / exit codes / unicode safety).
  Requirements:
  - Auto-engineer commit messages must conform to Conventional Commit
  Validation: `python -m pytest tests/test_validate_auto_commit_msg.py -q` all pass in < 5s
  Commit: `test(governance): cover validate_auto_commit_msg 8 cases`

- [ ] **T7.3 [BLOCKED-by-external-wrapper-not-in-repo]** Locate and document the auto-engineer commit-message call site (likely `supervise.sh` or `.auto-engineer/*` runtime) and route every subject through the validator.
  Refined finding (2026-04-25 15:30): `scripts/find_auto_commit_source.py` 跑出 5 targets / 2 hits / 0 direct template，repo 內**找不到** `auto-commit:` template 來源。`auto-engineer.sh:249` 用 `auto-engineer:` prefix（非違規來源）。違規 commit 來自 **external wrapper / AUTO-RESCUE 機制**（session-wrapper 或 Windows Task Scheduler 內），需要 admin 權限存取 repo 外位置才能修。`docs/admin-rescue-template.md` 57 行已含建議 diff（`auto-commit: → chore(rescue):`）。下一步：admin 識別並修改該 external wrapper formatter，然後在 repo 端跑 1 輪驗證 `git log --oneline -5` 0 violations。
  Requirements:
  - Commit-message lint must run inside the auto-engineer runtime pre-commit path
  Validation: inject a bad message in a fixture run and verify the cycle aborts with the rejection envelope; `git log -n 30 --format=%s` contains zero `auto-commit: checkpoint` strings among Auto-Dev Engineer commits on HEAD+30.
  Commit: `feat(governance): wire auto-engineer runtime to validate commit msg`

- [x] **T7.4** Update `docs/commit-plan.md` to v4 documenting runtime-seat enforcement, hook deprecation under current ACL, expected `chore(auto-engineer): <type>-<summary> @<timestamp>` shape.
  Requirements:
  - Non-semantic commits MUST fail the cycle, not log a warning
  Validation: `grep -n "v4" docs/commit-plan.md` present and `rg "chore\\(auto-engineer\\)" docs/commit-plan.md` hits the template.
  Commit: `docs(commit-plan): v4 — runtime-seat enforcement + hook deprecation`

- [x] **T7.5** Extend `scripts/sensor_refresh.py` with an `auto_commit.rate_recent_30` soft violation when < 0.9 for Auto-Dev Engineer authored commits only.
  Requirements:
  - Commit-message lint must run inside the auto-engineer runtime pre-commit path
  Validation: `python scripts/sensor_refresh.py --human` shows the new soft threshold in violations section when applicable; `pytest tests/test_sensor_refresh.py -q` still 12/12 (plus any new case).
  Commit: `refactor(governance): sensor tightens auto_commit_rate soft gate to 0.9`
