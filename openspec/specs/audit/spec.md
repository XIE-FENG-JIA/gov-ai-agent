# audit Specification

## Purpose

Epic 3 already fixed citation output and DOCX verification metadata, but the
review layer still has no approved contract for how citation traceability is
audited before export. Current behavior is spread across
`src/agents/fact_checker.py`, `src/agents/auditor.py`,
`src/agents/validators.py`, and `src/knowledge/realtime_lookup.py`:

- `FactChecker` mixes real-time law verification, document-type cross checks,
  and semantic similarity checks
- `FormatAuditor` runs citation-related validators, but only as part of a broad
  format audit path
- there is no repo-owned `citation_checker` seam that focuses on source
  traceability, orphan references, and missing evidence links as one review
  responsibility
- there is no approved failure matrix for cases where retrieval evidence,
  reference definitions, or law-verification data are missing

That gap blocks Epic 4. Without a change package, future audit work would keep
drifting between validators, LLM prompts, and export verification without one
stable definition of "citation audit passed".

## Requirements

### Requirement: Citation audit stays repo-owned and source-grounded

Gov AI Agent MUST keep citation-traceability review in repo-owned code rather
than hiding it inside generic prompts or export-only validation.

The protected repo-owned audit layers are:

- a dedicated citation-checker seam for traceability findings
- fact-checker use of repo evidence and law-verification state
- auditor/editor aggregation of citation findings into review output

#### Scenario: citation review runs through a dedicated seam

- **GIVEN** a generated draft with legal claims or source footnotes
- **WHEN** Epic 4 citation audit runs
- **THEN** citation-traceability findings are produced by a repo-owned review
  seam
- **AND** downstream audit output can distinguish citation failures from generic
  formatting advice


<!-- @trace
source: 04-audit-citation
updated: 2026-04-25
code:
  - engineer-log.md
  - results.log
  - program.md
-->

---
### Requirement: Citation audit uses repo evidence and verification state

Citation audit MUST combine repo evidence links with real-time verification
state when judging whether a legal claim is trustworthy.

The audit inputs MUST support:

- reference definitions or equivalent evidence links
- repo knowledge-base evidence identifiers when available
- `realtime_lookup` verification results for law and article existence

#### Scenario: legal claim is checked against evidence and verification data

- **GIVEN** a draft cites a law, article, or authority claim
- **WHEN** the citation audit evaluates that claim
- **THEN** it checks for evidence linkage and verification state
- **AND** unverifiable or ungrounded claims are surfaced as findings instead of
  being silently accepted


<!-- @trace
source: 04-audit-citation
updated: 2026-04-25
code:
  - engineer-log.md
  - results.log
  - program.md
-->

---
### Requirement: Citation audit failures fail loudly before export handoff

The review layer MUST fail loudly when citation traceability is missing or
degraded before the document is treated as audit-clean.

The required loud-failure cases include:

- orphan footnotes or missing reference definitions
- legal claims without evidence linkage
- regulations or article numbers that verification rejects
- degraded verification upstreams that remove confidence in citation review

#### Scenario: missing or degraded citation traceability blocks clean handoff

- **GIVEN** a generated draft contains one of the required loud-failure cases
- **WHEN** citation audit completes
- **THEN** the review output contains explicit citation-related findings
- **AND** downstream audit/export code does not treat the draft as citation-clean

<!-- @trace
source: 04-audit-citation
updated: 2026-04-25
code:
  - engineer-log.md
  - results.log
  - program.md
-->

---
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

<!-- @trace
source: 14-13-acceptance-audit
updated: 2026-04-26
code:
  - docs/change-13-acceptance-audit.md
  - docs/loop4-closure-report.md
  - scripts/commit_msg_lint.py
  - scripts/sensor_refresh.py
-->
