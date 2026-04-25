# Auto-Commit Host Action

Date: 2026-04-25
Updated: 2026-04-26 (T-COPILOT-WRAPPER-HOST-PATCH — upgraded to actionable handoff)
Owner: host Admin
Scope: out-of-repo auto-engineer wrapper / scheduler / commit message template

## Problem

Repo-side commit lint is already stricter, but host-side wrapper commits still pollute the rolling 30-commit window with subjects such as:

- `chore(auto-engineer): patch ...`
- `chore(auto-engineer): checkpoint snapshot ...`
- `chore(copilot): batch ...`
- `[AUTO-RESCUE]` follow-up commits that hide the real task name

This blocks `openspec/changes/12-commit-msg-noise-floor/tasks.md` T12.5 because the repository cannot force the external wrapper to change its interval, squash behavior, or generated subject.

## Host Changes Requested

1. Change the auto-commit interval from 5 minutes to **30 minutes** for this repo.
2. Enable a squash window so one agent round produces one semantic commit when possible.
3. Replace generic wrapper subjects with the active task prefix and why-summary.
4. Reject fallback subjects matching any of the following before commit creation:
   - `chore(auto-engineer): patch`
   - `chore(auto-engineer): checkpoint snapshot`
   - `chore(auto-engineer): AUTO-RESCUE`
   - `chore(auto-engineer): N files`
   - `chore(copilot): batch`
5. Enforce commit subject type prefix from the allowed set: `feat|fix|refactor|docs|test|chore`. Pure bare-keyword subjects (no `(scope):` part) must be rejected.

Recommended subject template:

```text
<type>(<scope>): <task-id> <what changed> to <why>
```

Examples:

```text
fix(openspec): T-OPENSPEC-PROMOTE-AUDIT archive completed specs to stop drift
docs(ops): P1-AUTO-COMMIT-EXTERNAL-PATCH document host wrapper changes
test(robustness): T-LITELLM-MOCK-CONTRACT-FIX pin mock schema warnings
```

## Files To Check On Host

- `D:/Users/Administrator/Desktop/公司/auto-dev/lib/cmd/supervise.sh`
- `D:/Users/Administrator/Desktop/公司/auto-dev/scripts/gov-ai-auto-commit.sh`
- `D:/Users/Administrator/Desktop/公司/auto-dev/scripts/rescue-daemon.sh`
- Any Windows Startup task or `.vbs` wrapper that launches the above scripts

## Validation

Run after host daemons reload:

```bash
cd "/d/Users/Administrator/Desktop/公文ai agent"
git log -n 30 --format=%s
git log -n 30 --format=%s | grep -E '^(chore\(auto-engineer\): patch|chore\(auto-engineer\): checkpoint snapshot|chore\(copilot\): batch)' && exit 1 || true
git log -n 30 --format=%s | while IFS= read -r subject; do
  printf '%s\n' "$subject" | python scripts/commit_msg_lint.py - || exit 1
done
python scripts/sensor_refresh.py --json
```

Pass criteria:

- Rolling 30 contains no `chore(auto-engineer): patch` subject.
- Rolling 30 contains no `chore(auto-engineer): checkpoint snapshot` subject.
- Rolling 30 contains no `chore(auto-engineer): AUTO-RESCUE` subject.
- Rolling 30 contains no `chore(copilot): batch` subject.
- Every subject from `git log -n 30 --format=%s` passes `scripts/commit_msg_lint.py`.
- `scripts/sensor_refresh.py --json` reports `auto_commit_rate >= 0.70` within 48 hours of deployment.
- `openspec/changes/12-commit-msg-noise-floor/tasks.md` T12.5 remains green.

## Host Admin Checklist

- [ ] Increase interval: 5 min → 30 min.
- [ ] Enable squash window for one semantic commit per agent round.
- [ ] Deploy the semantic subject template.
- [ ] Add pre-commit rejection for known wrapper-noise subjects.
- [ ] Restart wrapper daemons.
- [ ] Run validation commands and paste output into `results.log`.
