# Live Ingest Debug

- timestamp: 2026-04-20 17:30:11
- task: `P0.CC`
- source: `mojlaw`
- conclusion: `P0.T-LIVE` was blocked by intermittent upstream `HTTP 500`, not by shell egress.

## Repro

1. `python scripts/live_ingest.py --sources mojlaw --limit 1 --require-live`
   - before fix: CLI itself rejected `--require-live` because the script hard-coded live mode but did not expose the flag.
2. `python -m src.sources.ingest --source mojlaw --limit 1 --base-dir .\\meta_test\\live_ingest_debug_ingest --require-live`
   - one run returned `ingested=0 source=mojlaw`
   - a direct isolated run raised `FixtureFallbackError: live ingest required for mojlaw, but source_id=A0030018 used fixture fallback`
3. Direct adapter probe:
   - first attempt: `HTTPError 500 Server Error for url: https://law.moj.gov.tw/api/Ch/Law/json`
   - later attempts: live payload OK (`1343` laws parsed)

## Classification

- upstream URL/path: not the issue
  - same endpoint later returned `200` with a valid zip payload
- egress/proxy: not the primary blocker
  - `request_with_proxy_bypass()` succeeded and flipped `session.trust_env` to `False`
- require-live logic: partially affected
  - the CLI contract was misleading because `scripts/live_ingest.py` already enforced live mode but did not accept the documented flag
- root cause: transient upstream `HTTP 500` on the MojLaw catalog endpoint caused immediate fixture fallback

## Fix

- `src/sources/mojlaw.py`
  - retry one time on transient `HTTP 5xx` before dropping to fixtures
  - send `Accept-Language: zh-TW,zh;q=0.9,en;q=0.8` with the catalog request
- `scripts/live_ingest.py`
  - accept `--require-live` / `--no-require-live` so the debug SOP matches the actual CLI

## Expected Follow-up

- rerun `python scripts/live_ingest.py --sources mojlaw --limit 1 --require-live`
- if MojLaw stays green, expand to `datagovtw,executive_yuan_rss` and push `synthetic: false` corpus into `kb_data/corpus/`
