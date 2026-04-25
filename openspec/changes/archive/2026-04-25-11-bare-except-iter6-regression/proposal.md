## Problem

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

## Solution

1. Audit every site touched by the in-flight iter6 sweep that handles an
   LLM / KB call (`writer/strategy.py`, `writer/rewrite.py`, editor refine
   path, fact_checker pipeline, robustness graceful-degradation seams) and
   ensure the typed bucket includes `RuntimeError` and any concrete subclass
   the upstream callers can raise (`ConnectionError`, `TimeoutError`,
   `OSError` for KB / preferences I/O).
2. For each rewritten site, add or update a test that injects
   `RuntimeError("Connection timeout")` and asserts the fallback path runs
   (matches the existing `test_writer_llm_exception_uses_fallback` shape).
3. Re-run full pytest until 0 failed, and capture the runtime to confirm
   T10.6 ≤ 200 s budget is still satisfied.
4. Commit iter6 sweep + this regression repair as **one** semantic commit
   (or a tightly-paired pair) so HEAD never carries the broken intermediate
   state again.

## Non-Goals

- No expansion of iter6's file scope; this change only repairs the seven
  files iter6 already touches (`compliance_checker / editor / workflow
  endpoints / config_tools / reviewers / _manager_hybrid` plus whichever
  caller in the writer chain regressed `_refine_query` clients).
- No revert of iter6 in working tree — the typed-bucket direction is
  correct, only the catch list is wrong.
- No change to `commit_msg_lint.py`, `validate_auto_commit_msg.py`, or any
  governance script.
- No automatic rewrite of any of the 22 failing tests; tests are the
  contract, the production code is the bug.

## Acceptance Criteria

1. `pytest -q --ignore=tests/integration` exits 0 with **0 failed**, **3891
   passed** (or higher; auto-engineer may add more), runtime ≤ 200 s.
2. `python scripts/sensor_refresh.py` continues to report
   `bare_except.total ≤ 80` (iter6's own gate stays met).
3. The 22 originally-failing tests are not modified to bypass the contract;
   each still injects the same exception class it did before.
4. A single (or paired) semantic commit lands the iter6 sweep + repair so
   `git log --oneline` after merge shows no in-flight broken intermediate.
5. `spectra validate --changes 11-bare-except-iter6-regression` returns
   `valid`.
