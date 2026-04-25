# regression-repair Specification

## Purpose

TBD - created by archiving change '11-bare-except-iter6-regression'. Update Purpose after archive.

## Requirements

### Requirement: LLM/KB graceful-degradation contract restored without bypassing tests

Every site that previously caught a wide `except` over an LLM call (or KB
search, or local I/O the preferences path uses) MUST, after the iter6 sweep,
include in its typed bucket every concrete exception class the existing tests
inject — at minimum `RuntimeError`, `ConnectionError`, `TimeoutError`, and
`OSError` where upstream tests use them.

The repair MUST NOT modify any of the 22 failing tests to make them pass; the
production code is the bug.

#### Scenario: writer with mocked Connection timeout returns fallback draft

- **GIVEN** `writer.llm.generate.side_effect = RuntimeError("Connection timeout")`
- **WHEN** the writer pipeline runs through `_refine_query` (or the upstream
  caller that previously caught wide)
- **THEN** the run does not propagate the RuntimeError
- **AND** the writer emits a fallback draft built from the basic template
- **AND** at least one `logger.warning` records the exception text

#### Scenario: KB unavailable still produces empty search result

- **GIVEN** `kb_manager._available = False` or
  `search_hybrid` raises `RuntimeError("KB connection refused")`
- **WHEN** any agent calls into KB search through writer / editor / fact_checker
- **THEN** the agent receives an empty list (or fallback) and proceeds
- **AND** the typed bucket emits the appropriate logger.warning

#### Scenario: preferences save failure logs warning instead of raising

- **GIVEN** the preferences I/O layer raises `OSError("disk full")`
- **WHEN** `save_preferences` runs
- **THEN** the function returns gracefully (no propagation)
- **AND** a `logger.warning` records the error text


<!-- @trace
source: 11-bare-except-iter6-regression
updated: 2026-04-25
code:
  - engineer-log.md
  - results.log
  - program.md
-->

---
### Requirement: Single semantic commit landing iter6 sweep + repair, no broken intermediate on HEAD

The combined repair MUST land in **one** commit (or a tightly-paired pair
where neither lands without the other) so `git log --oneline` cannot show
HEAD passing through the broken intermediate state.

The commit subject MUST conform to T-COMMIT-SEMANTIC-GUARD v3 (passes
`scripts/commit_msg_lint.py`) and MUST reference both change 08 and change 11
in the body.

#### Scenario: regression check goes from 22 failed → 0 failed in one commit

- **GIVEN** HEAD before the repair commit shows 22 failed in the regression run
- **WHEN** the repair commit lands
- **THEN** the next `pytest -q --ignore=tests/integration` exits 0 with
  0 failed and runtime ≤ 200 s
- **AND** the commit subject is semantic and passes lint

<!-- @trace
source: 11-bare-except-iter6-regression
updated: 2026-04-25
code:
  - engineer-log.md
  - results.log
  - program.md
-->