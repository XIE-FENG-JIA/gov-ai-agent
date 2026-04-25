# auto-commit Specification

## Purpose

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

## Requirements

### Requirement: Auto-engineer commit messages must conform to Conventional Commit

Commits authored by the auto-engineer runtime (identity
`Auto-Dev Engineer <engineer@auto-dev.local>`) MUST have a subject line that
passes `scripts/commit_msg_lint.py` before being committed.

Bare fallback subjects (`auto-commit: checkpoint (...) @ ...`, `WIP`, single
verbs such as `update` / `fix` / `tmp`) MUST be rejected. The conventional
shape is `chore(auto-engineer): <type>-<summary> @<timestamp>`, where
`<summary>` is at least 10 characters describing what changed and why.

#### Scenario: auto-engineer emitting a checkpoint fallback is rejected

- **GIVEN** the auto-engineer cycle is about to commit with subject
  `auto-commit: auto-engineer checkpoint (2026-04-25 03:22:00) @ 2026-04-25 03:22`
- **WHEN** the runtime calls `scripts/validate_auto_commit_msg.py`
- **THEN** the validator exits non-zero with a rejection envelope on stderr
- **AND** the commit does not land on the branch

#### Scenario: auto-engineer emitting a conformant subject is accepted

- **GIVEN** a commit subject
  `chore(auto-engineer): bare-except-iter6 sweep _manager_hybrid @2026-04-25T04:00Z`
- **WHEN** the runtime calls the validator
- **THEN** the validator exits 0
- **AND** the commit proceeds


<!-- @trace
source: 07-auto-commit-semantic-enforce
updated: 2026-04-25
code:
  - program.md
  - results.log
  - engineer-log.md
-->

---
### Requirement: Commit-message lint must run inside the auto-engineer runtime pre-commit path

Because `.git/hooks/commit-msg` cannot be installed under the current
`index.lock` posture (see `T-HOOK-INSTALL-BLOCKER` investigation), the
enforcement seat is the auto-engineer runtime itself — typically
`supervise.sh`, `auto-engineer-keeper.vbs`, or the commit-orchestration layer
used by the codex loop.

The validator MUST be invoked **before** `git commit` runs. The runtime MUST
treat a non-zero exit code from the validator as a **cycle abort**, not a
warning. The runtime SHOULD surface the rejection envelope (JSON) to the
cycle log so the next session can pick up context.

#### Scenario: runtime aborts the cycle on validator failure

- **GIVEN** the auto-engineer cycle produces a subject that fails the lint
- **WHEN** the runtime invokes the validator
- **THEN** the validator exits 1 with a JSON envelope describing the rule
  violated and a suggested conformant subject
- **AND** the runtime aborts the commit step, records the failure in
  `results.log`, and does not retry with the same subject

#### Scenario: sensor reports bad auto-engineer rate as a soft violation

- **GIVEN** 30 recent commits authored by `Auto-Dev Engineer` with fewer
  than 27 passing the lint
- **WHEN** `python scripts/sensor_refresh.py --human` runs
- **THEN** the report lists `auto_commit_rate < 0.9` as a soft violation
- **AND** the next loop starter sees it as a gating signal

<!-- @trace
source: 07-auto-commit-semantic-enforce
updated: 2026-04-25
code:
  - program.md
  - results.log
  - engineer-log.md
-->