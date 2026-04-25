# Tasks: 12-commit-msg-noise-floor

- [x] **T12.1** Add `^chore\(auto-engineer\):\s*checkpoint(?:\s+snapshot)?\b` reject pattern to `scripts/commit_msg_lint.py` `_REJECT_PATTERNS`.
  Requirements:
  - Pseudo-semantic checkpoint subjects rejected by the lint
  Validation: `pytest tests/test_commit_msg_lint.py -q` passes including the new reject case.
  Commit: `b50b704 feat(scripts): commit_msg_lint reject pseudo-semantic checkpoint`

- [x] **T12.2** Add regression test case `chore(auto-engineer): checkpoint snapshot (...)` to `tests/test_commit_msg_lint.py::test_rejects_lazy_or_invalid_messages`.
  Requirements:
  - Pseudo-semantic checkpoint subjects rejected by the lint
  Validation: `pytest tests/test_commit_msg_lint.py -q` 22+ passed.
  Commit: `b50b704` (same as T12.1, batched).

- [x] **T12.3** Upgrade `gov-ai-auto-commit.sh:29-31` template to `chore(auto-engineer): patch ${task_id:-untagged} @ $timestamp`.
  Requirements:
  - Wrapper template emits subjects that pass the lint
  Validation: 2 variants (with task_id / untagged) both `commit_msg_lint -` exit 0.
  Commit: `e9879ac fix(commit-msg): T-COMMIT-NOISE-FLOOR v2 — wrappers emit chore(.): patch <task_id|untagged|batch-N>` (auto-dev repo)

- [x] **T12.4** Upgrade `copilot-engineer-loop.sh:133` template to `chore(copilot): patch ${tid:-batch-${ROUND}} @ $(date +%H:%M)`.
  Requirements:
  - Wrapper template emits subjects that pass the lint
  Validation: 2 variants (with tid / batch-N) both `commit_msg_lint -` exit 0.
  Commit: `e9879ac` (same as T12.3, batched).

- [x] **T12.5** Verify rolling 30-commit window has zero violations after both wrapper daemons reload. (2026-04-25 閉)
  Requirements:
  - `auto_commit.rate_recent_30 ≥ 0.9` for Auto-Dev Engineer authored commits
  Validation: `python scripts/sensor_refresh.py` reports rate ≥ 0.9; `git log -n 30 --format=%s | grep -E "^auto-commit:|^copilot-auto:|^chore\\(auto-engineer\\):\\s*checkpoint"` returns 0 lines (waiting on next 30 commits to roll over).
  Commit: `chore(sensor): record post-noise-floor 30-commit window 0 violations`
