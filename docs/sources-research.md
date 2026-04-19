# Top-3 公文來源調研

> 更新日期：2026-04-20
> 備註：本文件優先採官方網站資訊；若官方頁僅提供入口不直接列出 API path，會明示「依 repo 現有 fetcher / 官方 API 文件入口推定」。

## 1. 政府資料開放平臺 `data.gov.tw`

- API endpoint：
  - 官方 M2M 頁已公開多個 `api/front/*` 端點與 `全部資料集清單` 匯出入口。
  - 目前最適合本專案做來源探索的搜尋端點是 `https://data.gov.tw/api/front/dataset/list`（`POST`；依 repo 現有 `OpenDataFetcher` 與平臺 M2M 架構推定）。
  - 若只要全量 metadata，可用 `https://data.gov.tw/datasets/export/csv`。
- 資料格式：
  - 平臺層 metadata 以 JSON 為主。
  - 資料集本身常見 CSV / JSON / XML / ZIP / SHP。
- 授權條款：
  - 採「政府資料開放授權條款第1版」。
  - 可不限目的、時間及地域利用；可重製、改作、散布；但必須顯名標示來源。
- curl 範例：

```bash
curl -X POST "https://data.gov.tw/api/front/dataset/list" \
  -H "Content-Type: application/json" \
  -d '{
    "bool": [{"fulltext": {"value": "公文"}}],
    "filter": [],
    "page_num": 1,
    "page_limit": 10,
    "tids": [],
    "sort": "_score_desc"
  }'
```

- 資料量估計：
  - 平臺級資料量為數萬筆資料集 metadata。
  - 適合先抓 metadata，再二次篩出真正可用的公文/公告來源。
- 優先級：4/5
  - 優點：覆蓋面最廣、授權清楚、適合做來源發現。
  - 缺點：不是單一公文源，噪音高，需要後續清洗與白名單。

## 2. 全國法規資料庫 `law.moj.gov.tw`

- API endpoint：
  - 官方站已公開 API 文件入口：`https://law.moj.gov.tw/api/swagger`
  - repo 現有 fetcher 使用的全文端點：`https://law.moj.gov.tw/api/Ch/Law/json`
  - 若要 bulk XML，可用 `http://law.moj.gov.tw/PublicData/GetFile.ashx?DType=XML&AuData=CFM`
- 資料格式：
  - JSON API。
  - bulk ZIP + XML。
- 授權條款：
  - 全國法規資料庫站內「政府網站資料開放宣告」明示採政府資料開放授權條款第1版。
  - 可無償、非專屬、可再授權利用；使用時應註明出處。
- curl 範例：

```bash
curl "https://law.moj.gov.tw/api/Ch/Law/json"
```

- 資料量估計：
  - 中央法規、司法解釋、條約協定、兩岸協議、跨機關主管法規都在檢索範圍內。
  - 屬高權威、長尾穩定資料源；實際內容量至少是數千部法規、數萬條文級。
- 優先級：5/5
  - 優點：權威最高、更新規律清楚、內容結構相對穩。
  - 缺點：偏法規與規範，不等於一般行政公文；需和公告/新聞型來源互補。

## 3. 行政院 RSS `ey.gov.tw`

- API endpoint：
  - 官方 RSS 頻道頁：`https://www.ey.gov.tw/Page/5AC44DE3213868A9`
  - 站內可直接訂閱的 XML feed 例：
    - 本院新聞：`https://www.ey.gov.tw/RSS_Content.aspx?ModuleType=3`
    - 部會新聞：`https://www.ey.gov.tw/RSS_Content.aspx?ModuleType=4`
  - 適合作為最新公告/新聞稿增量入口。
- 資料格式：
  - RSS XML。
  - 內容通常再連回 HTML 內文頁。
- 授權條款：
  - 行政院全球資訊網「政府網站資料開放宣告」明示採政府資料開放授權條款第1版。
  - 可重製、改作、公開傳輸；須註明出處。
- curl 範例：

```bash
curl "https://www.ey.gov.tw/RSS_Content.aspx?ModuleType=3"
```

- 資料量估計：
  - 屬日更新聞流，年量級為數百到上千則。
  - 適合做「新鮮度高」的增量監看，不適合作為單一主知識庫。
- 優先級：3/5
  - 優點：更新快、增量抓取簡單、很適合做最新政策/新聞稿入口。
  - 缺點：文體偏新聞稿，格式不如法規穩定，需後續抽正文與去雜訊。

## 結論

1. 第一波實作建議先做 `law.moj.gov.tw`，因為權威最高、結構最穩、授權最清楚。
2. 第二波接 `ey.gov.tw RSS`，補最新政策與公告時效性。
3. `data.gov.tw` 不當主來源，改當「來源發現器」與資料集索引，用來擴充更多部會/地方政府公開資料源。
