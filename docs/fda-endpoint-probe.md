# FDA Endpoint Probe

- Date: 2026-04-21
- Scope: `P0.1-FDA-LIVE-DIAG`

## Findings

1. `https://www.fda.gov.tw/tc/DataAction.aspx` is no longer the JSON feed used by `FdaApiAdapter`.
   It returns an HTML API-document page, not notice records.
2. The live notice feed is `https://www.fda.gov.tw/DataAction`.
   In this environment it returns `200 text/plain; charset=utf-8` with a JSON array.
3. The live payload schema changed.
   Current keys are `標題 / 內容 / 附檔連結 / 發布日期`; legacy `Id / Link / Title` keys are not present.
4. After proxy bypass, FDA HTTPS requests still fail certificate verification in local `requests`.
   `request_with_proxy_bypass(..., allow_ssl_fallback=True)` is required to avoid forced fixture fallback for this source.

## Decision

- Update `FdaApiAdapter.API_URL` to `https://www.fda.gov.tw/DataAction`.
- Accept both legacy and current schemas.
- Generate a stable `source_id` from `發布日期 + 標題` when the live payload has no explicit ID.
- Build a traceable query URL from `keyword + startdate + enddate` when no detail link is present.
- Keep SSL fallback scoped to FDA only; do not change other government-source callers.
