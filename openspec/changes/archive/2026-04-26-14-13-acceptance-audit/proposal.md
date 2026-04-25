## Problem

LOOP5 audit (2026-04-26 03:30) finds three governance gaps in
`change 13-cli-fat-rotate-v3` that the auto-engineer-driven closure
overlooked:

**Gap 1 — `utils_io.py` exceeds spec acceptance**
- `change 13` T13.1b spec says "every importer that used `from src.cli.utils
  import <io-fn>` now imports from `utils_io`" with the broader Track A
  acceptance "no module larger than 300 lines after rotation".
- Current state: `wc -l src/cli/utils_io.py` = **306 lines** (6 lines over the
  300-line cap), yet T13.1b is marked `[x]` and the regression gate T13.7
  was checked off downstream.
- Risk: silent acceptance drift normalises "close enough" — same anti-pattern
  that produced T9.5's 440 s vs 200 s gap before LOOP4 caught it.

**Gap 2 — T13.7 regression gate marked `[x]` while Track B still empty**
- T13.7 spec opens with "Full regression check **after all track A/B/C
  tasks complete**".
- Track B (T13.2 / T13.3 / T13.4 / T13.5 — iceberg cross-command coupling
  fix) is **0/4 done**; HEAD `79c9ac7 refactor(cli): complete T13.6b/c/d
  micro-merges + T13.7 regression gate + fix ruff` flipped T13.7 to `[x]`
  prematurely.
- Risk: regression-gate semantic dilution — future audits cannot trust
  T13.7 `[x]` to imply Track B is safe.

**Gap 3 — sensor `_CHECKPOINT_NOISE_RE` escalation outpaces wrapper template
versions, producing a cat-and-mouse contract**
- v0 wrapper subject (`auto-commit: checkpoint <ts>`) → lint reject pattern
  added.
- v1 (`chore(auto-engineer): checkpoint snapshot <ts>`) → noise pattern
  `checkpoint(?:\s+snapshot)?` added.
- v2/v3 (`chore(auto-engineer): patch <task_id> @ <ts>`) → noise pattern
  `patch|batch` added.
- v4 (`chore(auto-engineer): <N> files (<basename>) @ <ts>`) → noise pattern
  `AUTO-RESCUE|\d+\s*files` added (sensor working tree, observed
  2026-04-26 03:30).
- Each cycle treats the new fallback shape as the next generation of noise.
- Real root: when the wrapper has no genuine task identifier, **any
  generic fallback is noise by definition**. Successive escalations only
  defer the problem.

## Solution

This change does not patch the gaps directly (Track B is auto-engineer's
hot zone; touching `utils_io.py` while the daemon edits it courts a race).
It documents the gaps + sensor escalation history + introduces a fourth
red-line into governance:

1. **Gap 1 doc**: log the `utils_io.py 306 > 300` overflow and the
   acceptance routing decision (revert T13.1b vs amend Track A spec to
   accept 5 % overflow).
2. **Gap 2 doc**: revert T13.7 to `[INCOMPLETE-TRACK-B-PENDING]` (or
   accept a softer "Track A/C only" gate semantics) so the regression seal
   is honest.
3. **Gap 3 contract**: introduce **red line v8 — wrapper template
   structural payload requirement**. Every wrapper-emitted commit subject
   MUST include at least one of:
   - explicit task tag (`T-XXX` / `Pn.X` / `EPIC<N>` from results.log
     parsed via the v3 grep filter),
   - or concrete module / file path (`src/path/to/module.py`),
   - or a meaningful verb-object pair (e.g. `rotate utils_io`,
     `align lint contract`).

   When neither is available, the wrapper MUST **abort the commit** rather
   than emit any generic shape. Working-tree changes accumulate until a
   real task tag arrives, breaking the cat-and-mouse.

## Non-Goals

- No direct edit to `src/cli/utils_io.py` or `T13.1b`/`T13.7` task status
  in this change (auto-engineer is mid-flight in change 13; the audit is
  documentation-only).
- No revision of `commit_msg_lint.py` or `_CHECKPOINT_NOISE_RE`. The
  contract escalation continues until red-line v8 lands; that lands as a
  separate follow-up change.
- No history rewrite of pre-v5 violation commits. Legacy frozen under
  `P0.S-REBASE-APPLY`.

## Acceptance Criteria

1. `docs/change-13-acceptance-audit.md` exists and lists Gap 1 / Gap 2 /
   Gap 3 with current evidence (wc / git log SHAs / sensor rate).
2. `red-line v8` documented either in `docs/loop4-closure-report.md` or a
   new `docs/red-lines.md` entry; the sensor or commit_msg_lint module
   carries a TODO comment pointing at it.
3. `spectra validate --changes 14-13-acceptance-audit` returns `valid`.
4. Sensor rate cat-and-mouse pattern is named in the audit doc with the
   four observed wrapper-template generations and the corresponding
   `_CHECKPOINT_NOISE_RE` escalations.
