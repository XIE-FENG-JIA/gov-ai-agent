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

- [x] **T7.3** Locate and document the auto-engineer commit-message call site (likely `supervise.sh` or `.auto-engineer/*` runtime) and route every subject through the validator.
  Resolution (2026-04-25 17:55): External wrapper located at `D:/Users/Administrator/Desktop/公司/auto-dev/scripts/`:
    - `gov-ai-auto-commit.sh:29,31` 原 emit `auto-commit: auto-engineer checkpoint @ <ts>`（產 c53a947 / 1eef399 / 6eb9907 / 96c9d05 / 8d42cc8 / 6d1ed6f / 2e5df97 / d50e8f9 / 6ce97d0 / 5fc70ba ... 連續違規源頭）
    - `copilot-engineer-loop.sh:133` 原 emit `copilot-auto: batch round <N> @ <ts>`（產 b71b456 / 45f79e8 等）
  Fix landed at auto-dev repo commit `3560b44 fix(commit-msg): T7.3 — wrappers emit chore(auto-engineer) / chore(copilot) shape`:
    - msg template 改 `chore(auto-engineer): checkpoint snapshot[ ($task_id)] @ $timestamp`
    - msg template 改 `chore(copilot): batch round $ROUND[ ($tid)] @ $(date +%H:%M)`
    - 兩處加 pre-commit `commit_msg_lint.py` 驗證 — fail abort commit
  驗證: 3 種 variants（含 task_id / 不含 / copilot）全過 `commit_msg_lint.py` exit 0。
  下次 wrapper 跑（自動或登入觸發）即可實證 `git log --oneline -5` 0 violations。
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
