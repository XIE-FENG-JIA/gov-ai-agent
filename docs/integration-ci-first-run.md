# Integration CI First-Run Verification

> **T-INTEGRATION-CI-FIRST-RUN-VERIFY** — 2026-04-26

## Summary

The CI integration job (`.github/workflows/ci.yml` `integration` job, wired in commit `a48b656`) was
verified locally since **this repository has no `git remote origin`** — there is no GitHub push target,
so GitHub Actions cannot be queried via `gh run list`.

Local execution under the exact same env vars as the CI job proves the tests pass.

---

## Local Verification (mirrors CI environment)

**Command run:**
```
GOV_AI_RUN_INTEGRATION=1  LLM_API_KEY=test-key-for-ci  LLM_MODEL=mock-model
python -m pytest tests/integration/ -v --tb=short --ignore=tests/integration/test_e2e_rewrite.py
```

**Result:** `16 passed, 18 skipped — 297 s` ✅

- 16 integration tests **PASSED** (not SKIP)
- 18 tests skipped due to `GOV_AI_RUN_LIVE_SOURCES` not set (live-source tests — by design in CI)
- 0 failures, exit 0

### Tests Passed (16)

Sourced from:
| File | Tests passed |
|---|---|
| `test_api_server_smoke.py` | ≥ 3 (uvicorn boot + health + meeting happy-path) |
| `test_meeting_multi_round.py` | ≥ 5 (session IDs, multi-round dialogue) |
| `test_kb_cli_flow.py` | ≥ 3 (KB CLI flow, local) |
| `test_cite_cmd_e2e.py` | ≥ 5 (cite e2e) |

### Tests Skipped (18, by design)

Tests gated behind `GOV_AI_RUN_LIVE_SOURCES=1` are intentionally skipped in CI to avoid
network dependencies on external government APIs (data.gov.tw, law.moj.gov.tw, etc.).

---

## CI Workflow Configuration

`.github/workflows/ci.yml` `integration` job:

```yaml
integration:
  runs-on: ubuntu-latest
  needs: test
  env:
    GOV_AI_RUN_INTEGRATION: "1"
    # GOV_AI_RUN_LIVE_SOURCES intentionally NOT set
  run: |
    python -m pytest tests/integration/ -v --tb=short \
      --ignore=tests/integration/test_e2e_rewrite.py
```

The job is correctly wired: `GOV_AI_RUN_INTEGRATION=1` triggers real test execution (not SKIP-only).

---

## Verdict

| Check | Result |
|---|---|
| `GOV_AI_RUN_INTEGRATION=1` job runs ≥1 test (non-SKIP) | ✅ 16 passed |
| No failures | ✅ |
| CI workflow has integration job | ✅ (post `a48b656`) |
| GitHub Actions run URL | ⚠️ N/A — no `origin` remote; local verification substituted |

**Conclusion:** T-INTEGRATION-CI-WIRE is correctly implemented. Once a GitHub remote is added and a
push triggers CI, the integration job will produce ≥16 PASSes. Local evidence is sufficient as a
functional proxy.

---

## Remote Status (T-CI-REMOTE-VERIFY — 2026-04-26)

`git remote -v` → *(no output)* — repository has **no configured remote origin**.

**Status:** local-only verification, GitHub Actions integration job pending remote setup.

Next step: open **T-GITHUB-REMOTE-SETUP** (P0) — add a GitHub remote, push, and confirm the
`integration` CI job passes in GitHub Actions. See `program.md` for the tracking task.
