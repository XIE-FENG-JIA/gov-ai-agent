## Problem

T7.3 (change 07) closed by fixing the external wrapper at
`D:/Users/Administrator/Desktop/公司/auto-dev/scripts/gov-ai-auto-commit.sh`
to emit `chore(auto-engineer): checkpoint snapshot @ <ts>` instead of the
bare `auto-commit:` prefix. That patch landed at auto-dev `3560b44` and
gov-ai `0e18bec` — and lint accepted the new shape, so 4 commits
(`d2db288 / 1cf654e / 482727b / 37cd069`) landed cleanly.

But the new shape is **semantic-looking noise**: it carries the conventional
`chore(auto-engineer):` prefix yet the subject body (`checkpoint snapshot`)
contributes zero information about what changed. Every checkpoint commit
collides with every other checkpoint commit in `git log --grep` — the same
problem `T-COMMIT-SEMANTIC-GUARD` v3 was meant to solve, just dressed up.

`commit_msg_lint.py` was extended on the gov-ai side to reject this exact
pattern (`b50b704 feat(scripts): commit_msg_lint reject pseudo-semantic
checkpoint`). The wrapper template, however, was unchanged — so the wrapper
would now `exit 1` on every cycle until the template was upgraded.

## Solution

Tighten the contract in two coordinated commits:

1. **Lint** (gov-ai repo, `b50b704`, already landed): add reject pattern
   `^chore\(auto-engineer\):\s*checkpoint(?:\s+snapshot)?\b` to
   `_REJECT_PATTERNS` plus a regression case in
   `tests/test_commit_msg_lint.py`.
2. **Wrapper template v2** (auto-dev repo, `e9879ac`, already landed): emit
   `chore(auto-engineer): patch <task_id|untagged> @ <ts>` and
   `chore(copilot): patch <tid|batch-<ROUND>> @ <time>`. Fallbacks
   (`untagged`, `batch-N`) carry semantic content and let the sensor
   distinguish "results.log gave no task" from "real task patched".

Reload the in-memory daemon copy (`PID 68696` was already reloaded in this
session via Startup-folder vbs trigger) so cached function bodies do not
override the new template after a script edit.

## Non-Goals

- No rewrite of the 4 historical `checkpoint snapshot` commits
  (`d2db288 / 1cf654e / 482727b / 37cd069`). They stay as evidence under
  `P0.S-REBASE-APPLY` (legacy frozen).
- No introduction of file-level diff summary inside the wrapper. The
  `<task_id>` slot already provides the meaningful identifier; embedding
  filenames adds parse complexity for marginal value.
- No change to `commit_msg_lint.py` beyond the new reject pattern. Existing
  Conventional Commit acceptance stays identical.
- No change to validate_auto_commit_msg.py strict schema (T7.1) — wrapper
  template need only pass the looser `commit_msg_lint.py` gate; strict
  schema reserved for future T7.x tightening.

## Acceptance Criteria

1. `commit_msg_lint.py` rejects every `chore(auto-engineer):` subject whose
   body starts with `checkpoint` or `checkpoint snapshot`. Verified by
   `tests/test_commit_msg_lint.py::test_rejects_lazy_or_invalid_messages`.
2. The wrapper templates emit subjects that pass the lint:
   - `chore(auto-engineer): patch <task_id|untagged> @ <ts>` (gov-ai-auto-commit.sh)
   - `chore(copilot): patch <tid|batch-<ROUND>> @ <time>` (copilot-engineer-loop.sh)
3. `git log --oneline -30` after the wrapper runs shows zero subjects
   matching either `^auto-commit:`, `^copilot-auto:`, or
   `^chore\(auto-engineer\):\s*checkpoint`.
4. `python scripts/sensor_refresh.py` reports `auto_commit.rate_recent_30
   ≥ 0.9` for Auto-Dev Engineer authored commits over the next 30-commit
   window after merge.
5. `spectra validate --changes 12-commit-msg-noise-floor` returns `valid`.
