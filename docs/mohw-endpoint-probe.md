# MOHW RSS Endpoint Probe (P0.1-MOHW-LIVE-DIAG)

> 2026-04-24 — pua-loop session probe，借 FDA SOP 模板

## Endpoint

| 屬性 | 值 |
|---|---|
| URL | `https://www.mohw.gov.tw/rss-18-1.html` |
| Format | RSS 2.0（自定義 `RssPart` attribute） |
| Content-Type | `application/rss+xml; charset=utf-8` |
| Encoding | UTF-8（中英混合，特殊 entity 例：`&trade;` `&ndash;`） |
| TTL | 20 min（feed 自報） |

## Live Probe（2026-04-24 23:55 CST）

```
$ curl -sS --max-time 10 -o /tmp/mohw_probe.xml \
       -w "HTTP %{http_code} | size %{size_download} | time %{time_total}s\n" \
       https://www.mohw.gov.tw/rss-18-1.html
HTTP 200 | size 25511 | time 1.20s
```

| 指標 | 值 | 備註 |
|---|---|---|
| HTTP status | 200 | 健康 |
| Payload size | 25,511 bytes | 約 10 個 item，每個含 description HTML |
| Latency | 1.20s | 含 SSL handshake；後續請求應 < 0.5s |
| Item count | 10 | RSS 預設返回最近 10 條公告 |

## Adapter End-to-End

```python
from src.sources.mohw_rss import MohwRssAdapter

adapter = MohwRssAdapter()
records = list(adapter.list(limit=3))      # → 3 dict {id, title, date}
raw = adapter.fetch(records[0]["id"])      # → dict raw entry
doc = adapter.normalize(raw)               # → PublicGovDoc
```

驗證輸出：

```
agency  = '衛生福利部'
doc_no  = 'https://www.mohw.gov.tw/cp-18-86219-1.html'   ← 注意：URL fallback，非真發文字號
date    = datetime.date(2026, 4, 24)
url     = 'https://www.mohw.gov.tw/cp-18-86219-1.html'
content = 完整 description HTML（含內嵌 `<table>` `<style>`）
```

## 已知限制

### 1. `source_doc_no` = URL fallback

RSS feed 不包含 **機關發文字號**。MOHW 官方公告通常有「衛部XX字第YYY號」格式
但 RSS payload 沒帶。Adapter 用 entry URL 作 `source_doc_no` fallback，會在 03-citation-tw-format 的引用層出現「URL 當作公文字號」現象。

**建議跟進**：T-LIQG-2 給 mohw_rss 加 `expected_min_records=5` + 在 03-citation
spec 補一條「URL fallback 的格式化規則」。

### 2. Description HTML 含樣式塊

RSS description 直接夾入 `<style type="text/css">@media...</style>`、`<table>`、
`<img>`。`adapter.normalize()` 經 `_build_content_markdown` 轉 markdown，但內嵌
CSS 會被當文字保留，可能干擾下游 LLM 提示生成。

**建議跟進**：在 `_build_content_markdown` 加 `<style>` 過濾（或用 BeautifulSoup
`for s in soup(["style", "script"]): s.decompose()`）。

### 3. RSS TTL 20 min vs `freshness_window_days`

Feed 自報 TTL 20 分鐘 = 高頻更新源；對應 EPIC6 quality_config 應設
`freshness_window_days=14` 以容納節假日。

### 4. 沒有分頁 / 沒有歷史

Endpoint 永遠只返回最近 10 條。長期 ingest 必須每天定時拉，否則漏掉中間發布。
**建議跟進**：scheduler 設 `--limit 10 --schedule daily` 並用 `NewsID` 做去重 key。

## SOP（給操作者）

### 一鍵 health check

```bash
python scripts/check_mohw_health.py        # 待落地，T-LIQG-3 gate-check 後 alias
```

### 手動 probe

```bash
# Step 1: endpoint 是否活
curl -sS --max-time 10 -w "%{http_code} %{time_total}s\n" -o /dev/null \
     https://www.mohw.gov.tw/rss-18-1.html

# Step 2: feed parse
python -c "
from src.sources.mohw_rss import MohwRssAdapter
records = list(MohwRssAdapter().list(limit=10))
print(f'records: {len(records)}; expect ≥ 5')
print(records[0])
"

# Step 3: normalize round-trip
python -c "
from src.sources.mohw_rss import MohwRssAdapter
a = MohwRssAdapter()
for r in list(a.list(limit=3)):
    raw = a.fetch(r['id'])
    doc = a.normalize(raw)
    assert doc.source_url and doc.source_agency, 'missing provenance'
print('PASS')
"
```

### 失敗排查

| 症狀 | 原因 | 處理 |
|---|---|---|
| HTTP 200 但 0 item | RSS endpoint 模板渲染失敗 | 等 1 hr 重試；持續 4 hr 即上 Discord 報警 |
| HTTP 5xx | MOHW 後端 down | 切 fixture；通知 owner |
| `_request_feed` raise ConnectionError | DNS / 防火牆 | 檢查本機網路；確認 outbound HTTPS 通 |
| `normalize` raise pydantic ValidationError | RSS schema 改了 | rerun probe，把 raw payload 貼到 issue 比對 fixture |

## 結論

**MOHW endpoint live + adapter green**。P0.1-MOHW-LIVE-DIAG 五輪 0 動的 stale 標籤本輪解除。已知限制 (1)(2)(3)(4) 進 EPIC6 backlog 跟進。
