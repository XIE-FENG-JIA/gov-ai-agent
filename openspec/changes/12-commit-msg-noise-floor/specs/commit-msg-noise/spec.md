# Spec: Commit-Message Noise Floor

## Summary

Closes the gap that opened when T7.3 (change 07) routed wrapper subjects
through the conventional `chore(auto-engineer):` prefix but left the body
as `checkpoint snapshot` — semantically empty noise that satisfies the
prefix gate yet contributes nothing to `git log --grep`. Lint adds an
explicit reject pattern; wrapper template upgrades from `checkpoint
snapshot` to `patch <task_id|untagged>` so the body always carries a
correlatable identifier.

## ADDED Requirements

### Requirement: Pseudo-semantic checkpoint subjects rejected by the lint

`scripts/commit_msg_lint.py` MUST reject any commit subject of the shape
`chore(auto-engineer): checkpoint(\s+snapshot)?\s*...` regardless of what
comes after. The reject pattern lives in `_REJECT_PATTERNS` alongside the
existing `auto-commit:` / `copilot-auto:` / `<agent>-auto:` rules.

#### Scenario: pseudo-semantic checkpoint snapshot is rejected

- **GIVEN** the wrapper would emit
  `chore(auto-engineer): checkpoint snapshot (T-LIQG-3) @ 2026-04-25 18:19`
- **WHEN** the subject pipes through `commit_msg_lint.py -`
- **THEN** the lint exits 1
- **AND** the wrapper aborts the commit (T7.3 pre-validation hook)

#### Scenario: bare checkpoint without snapshot suffix also rejected

- **GIVEN** an alternate template emits
  `chore(auto-engineer): checkpoint @ 2026-04-25 18:19`
- **WHEN** the subject pipes through `commit_msg_lint.py -`
- **THEN** the lint still exits 1 (`checkpoint(?:\s+snapshot)?` matches both)

### Requirement: Wrapper template emits subjects that pass the lint

The two known auto-engineer-side wrappers MUST emit subjects whose body
identifies the change being committed:

- `gov-ai-auto-commit.sh`: `chore(auto-engineer): patch <task_id|untagged> @ <ts>`
- `copilot-engineer-loop.sh`: `chore(copilot): patch <tid|batch-<ROUND>> @ <time>`

`<task_id>` / `<tid>` come from `results.log` parse; `untagged` / `batch-<N>`
fallbacks are emitted when results.log carried no `[T-...]` tag and let the
sensor distinguish "no task captured" from "task patched".

#### Scenario: wrapper with results.log task_id passes lint

- **GIVEN** results.log latest entry has `[T-LIQG-3]`
- **WHEN** the wrapper builds `chore(auto-engineer): patch T-LIQG-3 @ <ts>`
- **THEN** `commit_msg_lint.py -` exits 0
- **AND** the wrapper proceeds to `git commit`

#### Scenario: wrapper without task_id falls back to untagged

- **GIVEN** results.log has no recent `[T-...]` tag
- **WHEN** the wrapper builds
  `chore(auto-engineer): patch untagged @ <ts>`
- **THEN** the lint exits 0 (still passes Conventional Commit + ≥ 10 char subject)
- **AND** sensor downstream can flag `untagged` rate as a quality signal

### Requirement: `auto_commit.rate_recent_30 ≥ 0.9` for Auto-Dev Engineer authored commits

After both wrapper daemons reload with the v2 template,
`scripts/sensor_refresh.py` MUST report `auto_commit.rate_recent_30 ≥ 0.9`
when measuring commits authored by `Auto-Dev Engineer`. The fallback paths
(`untagged`, `batch-<N>`) MUST count as semantic, since they pass the
Conventional Commit shape.

#### Scenario: 30-commit rolling window stays clean

- **GIVEN** the wrapper has emitted 30 commits since the v2 upgrade
- **WHEN** `python scripts/sensor_refresh.py` runs
- **THEN** `auto_commit.rate_recent_30 ≥ 0.9`
- **AND** `git log -n 30 --format=%s | grep -E "^auto-commit:|^copilot-auto:|^chore\\(auto-engineer\\):\\s*checkpoint"`
  returns 0 lines
