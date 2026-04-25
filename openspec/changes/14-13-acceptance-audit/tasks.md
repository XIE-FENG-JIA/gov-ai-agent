# Tasks: 14-13-acceptance-audit

- [x] **T14.1** Document Gap 1 (`utils_io.py` 306 > 300) with `wc -l` evidence and routing options.
  Requirements:
  - Each gap has reproducible evidence and one or more remediation paths
  Validation: `rg "utils_io.py 306" docs/change-13-acceptance-audit.md` matches; remediation table lists revert vs amend-spec.
  Commit: included in T14.4 combined commit.

- [x] **T14.2** Document Gap 2 (T13.7 prematurely `[x]`) with HEAD SHA + spectra `[9/14]` evidence and decision required.
  Requirements:
  - Each gap has reproducible evidence and one or more remediation paths
  Validation: `rg "T13.7.*Track B" docs/change-13-acceptance-audit.md` matches; lists `79c9ac7` and decision options.
  Commit: included in T14.4 combined commit.

- [x] **T14.3** Document Gap 3 (sensor noise-filter cat-and-mouse) with the four observed wrapper-template generations + `_CHECKPOINT_NOISE_RE` escalation lineage.
  Requirements:
  - Each gap has reproducible evidence and one or more remediation paths
  Validation: `rg "_CHECKPOINT_NOISE_RE" docs/change-13-acceptance-audit.md` matches; v0 → v4 wrapper subject evolution table present.
  Commit: included in T14.4 combined commit.

- [x] **T14.4** Create `docs/change-13-acceptance-audit.md` capturing all three gaps + add red-line v8 entry to `docs/loop4-closure-report.md` (or new `docs/red-lines.md`).
  Requirements:
  - Each gap has reproducible evidence and one or more remediation paths
  - Wrapper template subjects MUST carry structural payload (task tag, module path, or verb-object); generic fallback aborts commit
  Validation: both docs exist; `wc -l docs/change-13-acceptance-audit.md` ≥ 80; red-line v8 wording covers task-tag / module-path / verb-object alternatives.
  Commit: `docs(governance): change-13 acceptance audit + red-line v8 — wrapper structural payload requirement`

- [x] **T14.5** Verify spectra validate on this change.
  Requirements:
  - Each gap has reproducible evidence and one or more remediation paths
  Validation: `spectra validate --changes 14-13-acceptance-audit` returns `valid`.
  Commit: included in T14.4 commit (validation runs as part of merge gate).
