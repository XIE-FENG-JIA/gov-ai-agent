# regression-repair Specification

## Purpose

T10.6 (change 10) regression check ran a full pytest baseline against HEAD
after `03ebca6` (T7.5 + T10.3) and surfaced **22 failed / 3891 passed /
136.90 s** — runtime budget held but the LLM/KB graceful-degradation contract
broke. All 22 failures cluster on the same theme:

- `test_*_llm_exception_*` — writer / editor / fact_checker / robustness
- `test_*_kb_failure_*` / `test_kb_unavailable_*` / `test_kb_init_failure_*`
- `test_verification_degraded_becomes_repo_owned_error`
- `test_save_preferences_failure_logs_warning`
- `test_generic_exception_returns_default_score`
- `test_scenario_long_requirement` / `test_scenario_malicious_input`
  (e2e fallout from the same root)

Bare-except iteration 6 (change 08) is **partially landed in working tree
but not yet committed** — sensor shows `bare_except.total` dropped from 89
→ 47 (across 38 files) without a corresponding commit on HEAD. Some sites
on the swept files now use a **typed bucket that does not include
`RuntimeError`** (the exception class injected by the failing tests'
mocks), so the rewrite turned a previously-handled timeout-style failure
into an unhandled propagation.

Symptom traceback (representative case):

```
tests/test_robustness.py::TestWriterAgentLLMException::test_writer_llm_exception_uses_fallback
RuntimeError: Connection timeout
src\agents\writer\strategy.py:102: in _refine_query
    refined = self.llm.generate(prompt, temperature=LLM_TEMPERATURE_PRECISE)
```

The inner `_refine_query` already has `try / except Exception`, so the
escape path is upstream — a caller in the writer / editor / fact_checker
chain that previously caught a wide `except` and now uses a typed bucket
missing `RuntimeError`.

This violates change 08's own acceptance criterion #1 ("rewrite MUST stay
contract-safe") and blocks T10.6's pytest-green requirement.

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