# CI Secrets Setup SOP

This document describes how to configure the required GitHub Actions secrets for the
`gov-ai-agent` repository so that the **integration** job runs correctly.

---

## Required Secrets

| Secret name           | Purpose                                                    |
|-----------------------|------------------------------------------------------------|
| `OPENROUTER_API_KEY`  | Enables the `integration` CI job (OpenRouter REST calls)   |

If `OPENROUTER_API_KEY` is absent the integration job is **skipped** (not failed):

```yaml
# .github/workflows/ci.yml — integration job condition
if: ${{ secrets.OPENROUTER_API_KEY != '' }}
```

The `GOV_AI_RUN_INTEGRATION` env var is set to `"1"` when the key is present,
otherwise it is empty and all integration tests self-skip via the pytest gate:

```python
# tests/integration/conftest.py
if os.getenv("GOV_AI_RUN_INTEGRATION") != "1":
    pytest.skip("GOV_AI_RUN_INTEGRATION not set")
```

---

## Setup Steps

### 1. Navigate to Repository Settings

1. Open the repository on GitHub.
2. Go to **Settings → Secrets and variables → Actions**.

### 2. Add `OPENROUTER_API_KEY`

1. Click **New repository secret**.
2. Name: `OPENROUTER_API_KEY`
3. Value: your OpenRouter API key (obtainable from <https://openrouter.ai/keys>).
4. Click **Add secret**.

### 3. Verify the Key is Valid

Run locally before adding to GitHub:

```bash
curl -s https://openrouter.ai/api/v1/auth/key \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" | python -m json.tool
```

Expected response contains `"is_free_tier": false` and `"limit": null` for paid accounts.

---

## Expected CI Behaviour

| `OPENROUTER_API_KEY` set? | Integration job outcome                                |
|---------------------------|--------------------------------------------------------|
| ❌ Not set                 | Job **skipped** (condition `false`; no 401 errors)     |
| ✅ Set (valid key)         | Job **runs**; expect ≥ 17 passed / ≤ 18 skipped        |

> **Note:** `GOV_AI_RUN_LIVE_SOURCES` is intentionally **not** set in CI.
> Live-source tests (`test_sources_smoke`, `test_kb_rebuild_quality_gate`,
> `test_kb_cli_flow`) therefore self-skip; only pure-local integration tests run.

---

## Troubleshooting

| Symptom                            | Likely cause                              | Fix                                |
|------------------------------------|-------------------------------------------|------------------------------------|
| Job skipped unexpectedly           | Secret not added or empty value           | Re-add the secret                  |
| `401 Unauthorized` in CI logs      | Old/revoked API key                       | Rotate key on OpenRouter dashboard |
| `17 skipped, 0 passed` locally     | `GOV_AI_RUN_INTEGRATION` not set          | `export GOV_AI_RUN_INTEGRATION=1`  |
| Integration job runs even w/o key | `if:` condition removed from `ci.yml`     | Restore the gate condition         |

---

_Last updated: 2026-04-26 by auto-engineer (T-INTEGRATION-CI-SECRETS-PROMOTE)_
