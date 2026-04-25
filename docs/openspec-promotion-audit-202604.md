# OpenSpec Promotion Audit Report — 2026-04-25

## Summary

This report documents the spec-promotion audit completed on 2026-04-25. The audit addressed
"規格漂白第三型"（Spec Whitewash Type 3）— completed change specs were never promoted to the
canonical `openspec/specs/` directory, and 11 completed change folders were left active
alongside their archived counterparts.

## Before State

| Dimension | Before |
|-----------|--------|
| Active change folders | 12 (01–12) |
| Archive folders (`openspec/changes/archive/`) | 11 (01–11, date-prefixed copies) |
| `openspec/specs/` capability files | 14 spec files already promoted |
| `openspec/changes/archive/INDEX.md` | Absent |

The 11 changes (01–11) had been partially archived (archive copies existed) but the
original active folders were never removed, creating duplicate state.

## Actions Taken

### (a) Spec Promotion Verification

All 11 completed changes had their capability specs already promoted to `openspec/specs/`:

| Change | Capability | Main Spec |
|--------|-----------|-----------|
| 01-real-sources | sources | `openspec/specs/sources/spec.md` ✅ |
| 02-open-notebook-fork | fork | `openspec/specs/fork/spec.md` ✅ |
| 03-citation-tw-format | citation | `openspec/specs/citation/spec.md` ✅ |
| 04-audit-citation | audit | `openspec/specs/audit/spec.md` ✅ |
| 05-kb-governance | kb-governance | `openspec/specs/kb-governance/spec.md` ✅ |
| 06-live-ingest-quality-gate | quality-gate | `openspec/specs/quality-gate/spec.md` ✅ |
| 07-auto-commit-semantic-enforce | auto-commit | `openspec/specs/auto-commit/spec.md` ✅ |
| 08-bare-except-audit-iter6 | except-safety | `openspec/specs/except-safety/spec.md` ✅ |
| 09-fat-rotate-iter3 | fat-rotate | `openspec/specs/fat-rotate/spec.md` ✅ |
| 10-test-local-binding-audit-systematic | test-local-binding | `openspec/specs/test-local-binding/spec.md` ✅ |
| 11-bare-except-iter6-regression | regression-repair | `openspec/specs/regression-repair/spec.md` ✅ |

### (b) Change Folder Archival

Removed 11 duplicate active change folders from `openspec/changes/`. Archive copies
under `openspec/changes/archive/<date>-<id>/` already existed for all 11.

### (c) Archive INDEX.md Created

Created `openspec/changes/archive/INDEX.md` with complete entries for all 11 archived
changes (id / archived date / summary / task count / completion status).

### (d) .spectra.yaml

No structural changes required. The `.spectra.yaml` is configuration-only (no change
tracking state). The archive path follows the convention established by the archive
folder naming (`YYYY-MM-DD-<id>`).

## After State

| Dimension | After |
|-----------|-------|
| Active change folders | 1 (`12-commit-msg-noise-floor`, T12.5 pending) |
| Archive folders | 11 (complete, all 100%) |
| `openspec/specs/` capability files | 14 (unchanged — promotion was already done) |
| `openspec/changes/archive/INDEX.md` | ✅ Created |

## Acceptance Criteria Verification

- ✅ `ls openspec/changes/` 僅剩 1 active (`12-commit-msg-noise-floor`)
- ✅ `openspec/specs/` has 14 spec files (≥10 target met)
- ✅ `openspec/changes/archive/INDEX.md` exists with all 11 entries
- ⏳ `spectra status` — spectra CLI not installed; spec content verified manually

## Remaining Active Change

**12-commit-msg-noise-floor** — T12.5 (`Verify rolling 30-commit window has zero violations`)
awaits external wrapper daemon reload and 30-commit window roll-over before it can be
verified and archived.
