# CLI Output Audit — Epic 24

> 建立時間：2026-04-27（T24.1）
> 範圍：`lint`、`cite`、`verify`、`kb search` 四個高頻指令

---

## 1. `gov-ai lint`

### 現有輸出（`--format text`，預設）

| 情境 | 輸出格式 | 回傳欄位 |
|------|---------|---------|
| 無問題 | Rich 彩色文字 | `✓ 未發現問題` 訊息 |
| 有問題 | Rich Table | 行號、類別、說明；結尾「共 N 個問題」|
| 錯誤（找不到檔案）| Rich 紅字 | 錯誤訊息，exit 1 |

**回傳路徑**：`src/cli/_lint_rules.py → _run_lint(text)` → `list[dict]`
每個 issue dict 欄位：`{line: int, category: str, detail: str}`

### JSON 輸出（`--format json`）

```json
{
  "issues": [{"line": 0, "category": "缺少段落", "detail": "缺少「主旨」段落"}],
  "score": 0.9,
  "pass": false
}
```

- `score`：`max(0.0, 1.0 - issues_count × 0.1)`，最低 0.0
- `pass`：`issues_count == 0`
- 有問題時 exit 1，無問題 exit 0

---

## 2. `gov-ai cite`

### 現有輸出（`--format text`，預設；原 `rich`）

| 情境 | 輸出格式 | 回傳欄位 |
|------|---------|---------|
| 正常 | Rich Panel + Table | 公文類型、適用法規表格（名稱/PCode/說明/引用格式）、KB 語意結果 |
| 無適用法規 | Yellow 警告 | 未找到適用法規 |
| 錯誤 | Rich 紅字 | 錯誤訊息，exit 1 |

**回傳路徑**：
- 類型偵測：`_detect_doc_type(text)` → `str | None`
- 法規篩選：`_filter_applicable(regulations, doc_type)` → `list[dict]`
  - 欄位：`{name, pcode, description, source_level, cite_format}`
- KB 搜尋（可選）：`_try_kb_search(draft_text, doc_type, top_n)` → `list[dict]`
- 映射表來源：`kb_data/regulation_doc_type_mapping.yaml`

### JSON 輸出（`--format json`）

```json
{
  "citations": [
    {
      "name": "公文程式條例",
      "pcode": "A0040002",
      "description": "規範公文種類...",
      "source_level": "A",
      "cite_format": "依據《公文程式條例》"
    }
  ],
  "count": 1,
  "doc_type": "函"
}
```

- `kb_results` 欄位僅在 `--kb` 啟用時出現

---

## 3. `gov-ai verify`

### 現有輸出（`--format text`，預設）

| 情境 | 輸出格式 | 回傳欄位 |
|------|---------|---------|
| 正常 | Rich Table | 檢查項目、PASS/FAIL 狀態、說明；通過比例 |
| 全通過 | Rich Table + exit 0 | `passed/total` |
| 有失敗 | Rich Table + exit 1 | 同上 |
| 錯誤 | Rich 紅字 + exit 1 | 錯誤訊息 |

**回傳路徑**：
- `collect_citation_verification_checks(docx_path)` → `list[tuple[str, bool, str]]`
  - 每個 tuple：`(check_name: str, ok: bool, detail: str)`
- `render_citation_verification_results(checks)` → `(passed: int, total: int)`
- 檢查項目：`metadata.citation_count`、`metadata.source_doc_ids`、`metadata.engine`、各 `citation[N]` 溯源

### JSON 輸出（`--format json`）

```json
{
  "facts": [
    {"check": "metadata.citation_count", "ok": true, "detail": "2 vs 2"},
    {"check": "citation[1] doc-123", "ok": false, "detail": "找不到對應 repo evidence"}
  ],
  "verdict": "warn"
}
```

- `verdict`：
  - `"pass"` — 全部通過
  - `"warn"` — 部分通過
  - `"fail"` — 全部失敗
- 有失敗時 exit 1，全通過 exit 0

---

## 4. `gov-ai kb search`

### 現有輸出（`--format text`，預設）

| 情境 | 輸出格式 | 回傳欄位 |
|------|---------|---------|
| 有結果 | Rich Table | 相似度、等級(A/B)、類型、標題、摘要 |
| 無結果 | Yellow 警告 | 提示執行 kb ingest |
| KB 不可用 | Rich 紅字 + exit 1 | 錯誤訊息 |

**回傳路徑**：
- `kb.search_hybrid(query, n_results=limit)` → `list[dict]`
  - 每個 result：`{metadata: dict, content: str, distance: float | None}`
  - metadata 欄位：`title`、`doc_type`、`source_level`、`source_id`（可選）

### JSON 輸出（`--format json`）

```json
{
  "results": [
    {
      "doc_id": "公文程式條例",
      "score": 0.8,
      "snippet": "第一條 公文之種類如下：函、公告、書函..."
    }
  ],
  "count": 1
}
```

- `doc_id`：取自 `metadata.title` 或 `metadata.source_id`，優先 title
- `score`：`1.0 - distance`（distance=0 最相似；distance=1 最不相似）
- `snippet`：`content[:200]`，換行替換為空格

---

## 共同規範

| 規則 | 說明 |
|------|------|
| 預設格式 | `text`（人類可讀，Rich 終端機輸出） |
| JSON 格式 | `--format json`，純文字 stdout，適合 pipe / CI |
| 非法格式 | 不在 `{text, json}` 內 → exit 1 + 錯誤訊息 |
| 向後相容 | `--format text` 行為與既有測試完全一致 |
| cite 特例 | `--format rich` 仍視為 text（歷史相容） |

---

## 實作狀態

| 指令 | T24.1 稽核 | T24.2/T24.3/T24.4 實作 | T24.5 測試 |
|------|-----------|----------------------|-----------|
| `lint` | ✅ | ✅ | ✅ |
| `cite` | ✅ | ✅ | ✅ |
| `verify` | ✅ | ✅ | ✅ |
| `kb search` | ✅ | ✅ | ✅ |
