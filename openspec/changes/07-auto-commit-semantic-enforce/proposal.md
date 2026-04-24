## Problem

Auto-engineer commit message generator has a fallback path that emits bare
`auto-commit: auto-engineer checkpoint (timestamp) @ timestamp` strings whenever
its semantic path fails or is not invoked. The repo captured **7 violations in
48 hours** (`c53a947 / 1eef399 / 6eb9907 / 96c9d05 / 8d42cc8 / 6d1ed6f /
2e5df97`) despite `scripts/commit_msg_lint.py` being in place since
`T-COMMIT-SEMANTIC-GUARD` (commit `2678b10`, 2026-04-24).

`commit_msg_lint.py` exists but is **not wired** into the auto-engineer
commit path. Only the session-driven pua-loop honors it. `git log --grep` is
therefore unreliable on the auto-engineer half of history, and the sensor
(`scripts/sensor_refresh.py`) reports the semantic rate drifting from 86.7% →
73.3% within a single session.

The `.git/hooks/commit-msg` path is blocked: `index.lock` permission issues
(recorded in `T-ACL-STATE-RECALIBRATE`, commit `6d1ed6f?`) prevent installing
a native hook. Enforcement must live in the auto-engineer runtime layer, not
the git layer.

## Solution

Ship a runtime validator that sits inside the auto-engineer commit path,
rejects non-semantic subjects, and forces the generator to emit the
conventional `chore(auto-engineer): <type>-<summary> @<timestamp>` format.

Scope:

1. Add `scripts/validate_auto_commit_msg.py` — wraps `commit_msg_lint.py` with
   extra context (short SHA, files changed, task hint) and prints a structured
   rejection envelope when the lint fails.
2. Refactor the auto-engineer commit-message generator (location to be
   identified: likely `supervise.sh` / `auto-engineer-keeper.vbs` call chain)
   to route every subject through the validator, abort the cycle on failure,
   and log the rejection.
3. Bump `docs/commit-plan.md` to **v4** documenting: (a) the auto-engineer
   runtime path is now the only enforcement seat, (b) `.git/hooks` is
   explicitly deprecated under the current ACL / index.lock posture, (c) the
   new expected subject shape.
4. Extend `scripts/sensor_refresh.py` to flag `auto_commit_rate < 0.9` as a
   soft violation specifically for auto-engineer authored commits.

## Non-Goals

- No rewrite / rebase of the 7 existing violation commits (they stay as
  historical evidence under `P0.S-REBASE-APPLY`, which is legacy-frozen).
- No `.git/hooks/commit-msg` install attempt under current `index.lock`
  posture (`T-HOOK-INSTALL-BLOCKER` is a separate investigation).
- No change to pua-loop session-driven commits (already conform).
- No audit of non-`auto-engineer` authored commits.

## Acceptance Criteria

1. `scripts/validate_auto_commit_msg.py` exists with unit tests and exits 0 on
   conforming messages, 1 on rejections with a structured JSON envelope.
2. Auto-engineer runtime path invokes the validator and aborts its cycle when
   a message fails — verified by inducing a bad message in a fixture run.
3. `python scripts/sensor_refresh.py` reports `auto_commit.rate_recent_30
   ≥ 0.9` (27/30 semantic) for the 30 commits after this change lands.
4. `git log -n 30 --format=%s` contains zero `auto-commit: checkpoint`
   bare-format subjects among commits authored by `Auto-Dev Engineer`.
5. `docs/commit-plan.md` v4 is committed and referenced from the change
   archive folder after merge.
