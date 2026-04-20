# 公開公文來源調研

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

## 4. 衛福部 RSS `mohw.gov.tw`

- API endpoint：
  - 官方 RSS 頁面：`https://www.mohw.gov.tw/lp-16-1.html`
  - 常用 feed 類型包含最新消息與公告；實際 feed URL 由頁面產生。
- 資料格式：
  - RSS XML。
  - 條目通常再連回 HTML 內文頁與附件。
- 授權條款：
  - 衛福部網站的「政府網站資料開放宣告」採政府資料開放授權條款第 1 版。
  - 可重製、改作、散布；須註明來源。
- curl 範例：

```bash
curl "https://www.mohw.gov.tw/lp-16-1.html"
```

- 資料量估計：
  - 部會公告與新聞年量級通常為數百到上千則。
  - 適合補政策公告、函釋新聞與衛政措施。
- 優先級：3/5
  - 優點：部會層級高、更新快、與民生政策高度相關。
  - 缺點：需先從 RSS/列表頁抽取穩定 feed 與正文。

## 5. 財政資訊中心 RSS `fia.gov.tw`

- API endpoint：
  - 官方 RSS 入口：`https://www.fia.gov.tw/WEB/fia/ias/isa/isa1100w`
  - 主要作為財政部財政資訊中心公告、新聞與系統維運資訊增量入口。
- 資料格式：
  - RSS XML。
  - 條目通常回連 HTML 公告頁。
- 授權條款：
  - 財政資訊中心網站公開之政府網站資料開放宣告，原則上沿用政府資料開放授權條款第 1 版。
  - 使用時仍需保留出處與抓取日期。
- curl 範例：

```bash
curl "https://www.fia.gov.tw/WEB/fia/ias/isa/isa1100w"
```

- 資料量估計：
  - 年量級通常為數十到數百則。
  - 適合補財稅系統公告與行政資訊。
- 優先級：2/5
  - 優點：財政體系公告具專業性，可覆蓋稅務/系統維運文體。
  - 缺點：量較小，且正文格式需再探。

## 6. 食藥署公告 `fda.gov.tw`

- API endpoint：
  - repo 既有候選入口：`https://www.fda.gov.tw/tc/DataAction.aspx`
  - 官方站常以 querystring 型式提供公告、新聞與資料集查詢；需逐項確認可公開取用參數。
- 資料格式：
  - HTML / JSON 混合。
  - 部分頁面為列表查詢後再連回公告頁。
- 授權條款：
  - 食藥署網站政府網站資料開放宣告採政府資料開放授權條款第 1 版。
  - 可利用公開內容，但需保留來源。
- curl 範例：

```bash
curl "https://www.fda.gov.tw/tc/DataAction.aspx"
```

- 資料量估計：
  - 食安、藥政、醫材公告量高，年量級可達數百到上千則。
  - 適合補公告、函釋、新聞稿類型語料。
- 優先級：3/5
  - 優點：公告量大，文體接近正式行政通知。
  - 缺點：端點結構較碎，需先做參數盤點再實作 adapter。

## 7. 政府電子採購網 `web.pcc.gov.tw`

- API endpoint：
  - 官方網站入口：`https://web.pcc.gov.tw/`
  - 目前未確認穩定、官方公開的 JSON API；現有 repo `ProcurementFetcher` 使用的是社群維護的 `https://pcc-api.openfun.app`，只能當研究參考，不應直接視為官方主來源。
- 資料格式：
  - 官方站以 HTML 查詢頁為主。
  - 非官方社群鏡像可回 JSON。
- 授權條款：
  - 官方站公開資訊可供檢索，但 API 授權邊界需再做法遵確認。
  - 若採社群鏡像，須另列「非官方衍生來源」標籤。
- curl 範例：

```bash
curl "https://web.pcc.gov.tw/"
```

- 資料量估計：
  - 招標、決標、更正公告量極高，日量級可達數百以上。
  - 若能合法穩定抓取，對正式公告文體價值很高。
- 優先級：2/5
  - 優點：採購公告格式制式，適合模板學習。
  - 缺點：官方可抓取接口與授權界線仍不清，先做法遵再做技術。

## 8. 立法院開放資料 / 公報 `data.ly.gov.tw`

- API endpoint：
  - repo 既有官方開放資料端點：`http://data.ly.gov.tw/odw/openDatasetJson.action`
  - 另有社群整理 API：`https://v2.ly.govapi.tw`，但正式 ingest 應以官方端點為主。
- 資料格式：
  - JSON。
  - 部分資料集再回連立法院公報、議事錄與附件。
- 授權條款：
  - 立法院開放資料與網站公開資料原則上採政府資料開放授權條款體系。
  - 使用時需註明資料來源與資料集名稱。
- curl 範例：

```bash
curl "http://data.ly.gov.tw/odw/openDatasetJson.action?id=2"
```

- 資料量估計：
  - 議事錄、公報、法案與委員會資料量大，長期可達數萬筆。
  - 很適合補充公報、審議與政策說明類文體。
- 優先級：4/5
  - 優點：官方結構化資料入口已存在，覆蓋公報與立法過程文本。
  - 缺點：資料集 schema 較多，需要先挑最接近公文語體的資料集。

## 9. 臺北市開放資料 `data.taipei`

- API endpoint：
  - 入口頁：`https://data.taipei/`
  - 各資料集可直接提供 JSON/CSV/XML API 與下載鏈結。
- 資料格式：
  - JSON / CSV / XML。
  - 依資料集而異，通常可直接 machine-to-machine 取用。
- 授權條款：
  - 採政府資料開放授權條款第 1 版。
  - 地方政府資料可作為地方公告、公報與自治法規擴充來源。
- curl 範例：

```bash
curl "https://data.taipei/"
```

- 資料量估計：
  - 都市型地方政府資料集數量通常上千，公告/公報/自治資訊子集可再篩。
  - 適合作為地方政府來源模板。
- 優先級：3/5
  - 優點：地方層級代表性高，接口通常乾淨。
  - 缺點：要先挑出真正接近公文正文的資料集，噪音不少。

## 10. 臺中市政府資料開放平臺 `opendata.taichung.gov.tw`

- API endpoint：
  - 官方入口：`https://opendata.taichung.gov.tw/`
  - 各資料集頁面通常直接附 API / 檔案下載入口。
- 資料格式：
  - JSON / CSV / XML。
  - 依資料集內容與局處提供格式而定。
- 授權條款：
  - 採政府資料開放授權條款第 1 版。
  - 可作為第二個地方政府樣板，避免實作只綁單一縣市。
- curl 範例：

```bash
curl "https://opendata.taichung.gov.tw/"
```

- 資料量估計：
  - 平臺級資料集數量通常為數百到上千。
  - 可優先搜尋公報、公告、自治條例、採購或局處新聞稿。
- 優先級：3/5
  - 優點：可驗證地方政府資料源抽象層是否通用。
  - 缺點：資料集分散，前期仍需白名單清洗。

## 結論

1. 第一波實作仍建議先做 `law.moj.gov.tw`，因為權威最高、結構最穩、授權最清楚。
2. 第二波建議在中央公告流中二選一：`ey.gov.tw RSS` 或 `mohw.gov.tw RSS`，先驗證 RSS-to-HTML 增量管線。
3. 第三波優先接 `data.ly.gov.tw`，因為官方開放資料端點已明確，且可補公報/議事文本。
4. `data.gov.tw` 與地方政府 open data 平臺適合當來源發現器，不適合作為單一主來源。
5. `web.pcc.gov.tw` 先列法遵待確認來源；若要做，必須把官方站與社群鏡像明確分層。
