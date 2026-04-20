# Live Ingest URLs

`scripts/live_ingest.py` 會用 `require_live=True` 走這批 endpoint。現在先把 URL 與預期 response 寫死，Admin 開 egress 後直接驗。

| source | purpose | method | URL / template | expected status | expected content-type |
| --- | --- | --- | --- | --- | --- |
| `mojlaw` | catalog feed | `GET` | `https://law.moj.gov.tw/api/Ch/Law/json` | `200` | `application/json` or zip payload |
| `mojlaw` | detail page | `GET` | `https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode={pcode}` | `200` | `text/html; charset=utf-8` |
| `datagovtw` | dataset search | `POST` | `https://data.gov.tw/api/front/dataset/list` | `200` | `application/json` |
| `datagovtw` | dataset detail | `GET` | `https://data.gov.tw/dataset/{dataset_id}` | `200` | `text/html; charset=utf-8` |
| `executiveyuanrss` | RSS feed | `GET` | `https://www.ey.gov.tw/RSS_Content.aspx?ModuleType=3` | `200` | `application/rss+xml` or `application/xml` |
| `executiveyuanrss` | item detail | `GET` | item `link` from RSS payload | `200` | `text/html; charset=utf-8` |
| `mohw` | RSS feed | `GET` | `https://www.mohw.gov.tw/rss-18-1.html` | `200` | `application/rss+xml` or `application/xml` |
| `mohw` | item detail | `GET` | item `link` from RSS payload | `200` | `text/html; charset=utf-8` |
| `fda` | notice listing | `GET` | `https://www.fda.gov.tw/tc/DataAction.aspx` | `200` | `application/json` or `text/plain` JSON |
| `fda` | notice detail | `GET` | item `Link/Url/DetailUrl/Href` resolved against `https://www.fda.gov.tw/tc/DataAction.aspx` | `200` | `text/html; charset=utf-8` |

## Curl Checks

```bash
curl -sI https://law.moj.gov.tw/api/Ch/Law/json
curl -sI "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=A0030018"
curl -sI https://data.gov.tw/api/front/dataset/list
curl -sI https://data.gov.tw/dataset/1001
curl -sI "https://www.ey.gov.tw/RSS_Content.aspx?ModuleType=3"
curl -sI https://www.mohw.gov.tw/rss-18-1.html
curl -sI https://www.fda.gov.tw/tc/DataAction.aspx
```

## Source Mapping

- `mojlaw` uses `src/sources/mojlaw.py` and `LAW_API_URL` / `LAW_DETAIL_URL`.
- `datagovtw` uses `src/sources/datagovtw.py` and `SEARCH_URL` / `OPENDATA_DETAIL_URL`.
- `executiveyuanrss` uses `src/sources/executive_yuan_rss.py` and reads item links from the RSS feed.
- `mohw` uses `src/sources/mohw_rss.py` and reads item links from the RSS feed.
- `fda` uses `src/sources/fda_api.py` and resolves detail URLs from listing payload fields.
