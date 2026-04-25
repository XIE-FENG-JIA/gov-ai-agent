# Spec: Change 13 Acceptance Audit + Red-Line v8

## Summary

Documents three governance gaps in `change 13-cli-fat-rotate-v3` that
auto-engineer-driven closure left implicit (`utils_io.py` 306 > 300,
`T13.7` checked off without Track B, sensor noise-filter cat-and-mouse).
Introduces red-line v8 — wrapper template subjects MUST carry structural
payload, not generic fallback shapes.

## ADDED Requirements

### Requirement: Each gap has reproducible evidence and one or more remediation paths

`docs/change-13-acceptance-audit.md` MUST list every gap with:

- the exact metric and its source (`wc -l`, `spectra list`, `git log`),
- the spec text the gap violates (verbatim quote),
- two or more remediation options (revert task `[x]`, amend spec, accept
  drift with rationale),
- the agent that introduced the drift (auto-engineer / copilot / session)
  and the commit SHA that landed it.

Documentation-only audit: do NOT mutate change 13 task statuses while
auto-engineer is still iterating on Track B.

#### Scenario: a future audit reproduces a gap from this document alone

- **GIVEN** a developer reads `docs/change-13-acceptance-audit.md`
- **WHEN** they run the cited commands (`wc -l src/cli/utils_io.py`,
  `spectra list`, `git log --oneline -5 origin/main`)
- **THEN** they reproduce the same numbers and SHAs (or see drift
  documented as expected)
- **AND** they can pick a remediation path without re-doing the audit

### Requirement: Wrapper template subjects MUST carry structural payload (task tag, module path, or verb-object); generic fallback aborts commit

Every commit subject emitted by the auto-engineer / copilot wrapper layer
MUST contain at least one of:

- explicit task tag (e.g. `T-LIQG-3`, `P0.1`, `EPIC6`, `AUTO-RESCUE` only
  when paired with a concrete file like `program` / `engineer-log`),
- concrete module / file path (e.g. `src/cli/utils_io.py`,
  `scripts/sensor_refresh.py`),
- meaningful verb-object pair (e.g. `rotate utils_io`,
  `align lint contract`, `restore index after race`).

If `results.log` parsing yields no task tag AND `git diff --cached`
produces no obvious top file, the wrapper MUST **abort the commit cycle**
rather than emit any `<verb> <count>` generic shape. Working-tree changes
remain uncommitted until a real task identifier arrives.

This breaks the cat-and-mouse where each wrapper template generation
becomes the next noise-filter target:

- v0 `auto-commit: checkpoint <ts>` — lint reject
- v1 `chore(auto-engineer): checkpoint snapshot <ts>` — noise reject
- v2/v3 `chore(auto-engineer): patch <task_id> <ts>` — noise reject
- v4 `chore(auto-engineer): <N> files (<basename>) <ts>` — noise reject
- **v5 (red-line v8 compliant)**: structural payload required, or abort

#### Scenario: wrapper without task tag aborts commit

- **GIVEN** wrapper cycle starts with no `[T-XXX]` / `[Pn.X]` /
  `[EPIC<N>]` / `[AUTO-RESCUE]` tag in `results.log` last entry
- **AND** no top changed file with a recognisable extension
- **WHEN** wrapper attempts to build a commit subject
- **THEN** wrapper MUST log `[skip] no structural payload available` and
  return without invoking `git commit`
- **AND** the working-tree changes persist for the next cycle

#### Scenario: wrapper with concrete module path passes red-line v8

- **GIVEN** wrapper detects `src/cli/utils_io.py` as the top changed file
- **WHEN** wrapper emits `chore(auto-engineer): rotate src/cli/utils_io @ <ts>`
- **THEN** the subject passes `commit_msg_lint.py` AND
  `_SEMANTIC_RE.match()` AND `not _CHECKPOINT_NOISE_RE.match()`
- **AND** sensor counts the commit as truly semantic
