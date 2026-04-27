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

| 指令 | 稽核 | 實作 | 測試 |
|------|-----|------|------|
| `lint` | ✅ | ✅ | ✅ |
| `cite` | ✅ | ✅ | ✅ |
| `verify` | ✅ | ✅ | ✅ |
| `kb search` | ✅ | ✅ | ✅ |
| `stats` | ✅ (T25.1) | ✅ (T25.2) | ✅ (T25.4) |
| `status` | ✅ (T25.1) | ✅ (T25.3) | ✅ (T25.4) |
| `rewrite` | ✅ (T26.1) | ✅ (T26.2) | ✅ (T26.4) |
| `generate` | ✅ (T26.1) | ✅ (T26.3) | ✅ (T26.4) |
| `validate` | ✅ (T27.1) | ✅ (T27.2) | ✅ (T27.5) |
| `summarize` | ✅ (T27.1) | ✅ (T27.3) | ✅ (T27.5) |
| `compare` | ✅ (T27.1) | ✅ (T27.4) | ✅ (T27.5) |

---

## 5. `gov-ai stats`

> 新增於 Epic 25（T25.1/T25.2）

### 現有輸出（`--format text`，預設）

| 情境 | 輸出格式 | 回傳欄位 |
|------|---------|---------|
| 無歷史 | Rich Panel + 提示文字 | 「尚無記錄」提示 |
| 有歷史 | Rich Panel + 統計文字 | 總計/成功/失敗/平均分數/類型分佈 |

**資料來源**：`.gov-ai-history.json`（JSONStore），每筆 record 欄位：`{status, doc_type, score, ...}`

### JSON 輸出（`--format json`）

```json
{
  "total": 5,
  "success": 4,
  "failed": 1,
  "type_counts": {"函": 3, "公告": 2},
  "avg_score": 0.87
}
```

- `avg_score`：`null` 當無任何 `score` 欄位
- `type_counts`：`{}` 當無歷史

---

## 6. `gov-ai status`

> 新增於 Epic 25（T25.1/T25.3）

### 現有輸出（`--format text`，預設）

| 情境 | 輸出格式 | 回傳欄位 |
|------|---------|---------|
| 無設定 | Rich Table（Panel）| 各項目顯示「✗ 未設定」 |
| 有設定 | Rich Table（Panel）| LLM 設定/生成記錄/回饋/使用者設定/別名數量 |

**資料來源**：`config.yaml`、`.gov-ai-history.json`、`.gov-ai-feedback.json`、`.gov-ai-profile.json`、`.gov-ai-aliases.json`

### JSON 輸出（`--format json`）

```json
{
  "config": {"llm": {"provider": "openai", "model": "gpt-4"}},
  "history_count": 10,
  "feedback_count": 3,
  "kb_status": "ok"
}
```

- `config`：`config.yaml` 原始內容（`{}`當檔案不存在或 YAML 解析失敗）
- `kb_status`：`"ok"` | `"missing"` | `"error"` | `"unknown"`

---

## 7. `gov-ai rewrite`

> 新增於 Epic 26（T26.1/T26.2）

### 現有輸出（`--format text`，預設）

| 情境 | 輸出格式 | 回傳欄位 |
|------|---------|---------|
| 正常 | Rich Panel（Markdown 渲染）| 改寫結果文字 |
| 對比模式 | Rich Columns（左原始/右改寫）| 兩欄對比 |
| 錯誤 | Rich 紅字 + exit 1 | 錯誤訊息 |

**資料來源**：`--file` 讀取文字檔；LLM `generate()` 產生改寫結果

### JSON 輸出（`--format json`）

```json
{
  "rewritten": "主旨：...\n說明：...",
  "doc_type": null,
  "score": null,
  "issues": []
}
```

- `rewritten`：改寫後全文字串
- `doc_type`：`null`（rewrite 不做類型偵測）
- `score`：`null`（rewrite 不執行 QA 評分）
- `issues`：`[]`（rewrite 不執行 lint）

---

## 8. `gov-ai generate`

> 新增於 Epic 26（T26.1/T26.3）

### 現有輸出（`--format text`，預設）

| 情境 | 輸出格式 | 回傳欄位 |
|------|---------|---------|
| 正常 | Rich Panel 摘要卡片 | 公文類型/QA 分數/輸出路徑/耗時 |
| 預覽模式 | Rich Panel 草稿全文 | 完整草稿文字 |
| 錯誤 | Rich 紅字 + exit 1 | 錯誤訊息 |

**資料來源**：`_run_core_pipeline()` 呼叫 LLM + QA Agent；`_export_document()` 輸出 .docx

### JSON 輸出（`--format json`）

```json
{
  "output": "output.docx",
  "doc_type": "函",
  "score": 0.92,
  "elapsed_sec": 12.345
}
```

- `output`：輸出 .docx 檔案路徑
- `doc_type`：偵測到的公文類型（如 `"函"` / `"公告"`）
- `score`：QA 報告整體分數（`null` 當 `skip_review=True`）
- `elapsed_sec`：生成總耗時（秒）

---

## 9. `gov-ai validate`

> 新增於 Epic 27（T27.1/T27.2）

### 現有輸出（`--format text`，預設）

| 情境 | 輸出格式 | 回傳欄位 |
|------|---------|---------|
| 正常 | Rich Table | 檢查項目/通過狀態/說明；通過比例 |
| 全通過 | Rich Table + exit 0 | 「所有檢查通過！」 |
| 部分失敗 | Rich Table + exit 0 | 「部分檢查未通過」 |
| 錯誤 | Rich 紅字 + exit 1 | 錯誤訊息 |

**回傳路徑**：5 個本機檢查（文件長度/公文類型/必要欄位/發文日期/發文字號）

### JSON 輸出（`--format json`）

```json
{
  "checks": [
    {"name": "文件長度", "passed": true, "message": "12 段"},
    {"name": "公文類型", "passed": false, "message": "無法識別公文類型"}
  ],
  "pass_count": 1,
  "total": 2,
  "passed": false
}
```

- `passed`：`pass_count == total`

---

## 10. `gov-ai summarize`

> 新增於 Epic 27（T27.1/T27.3）

### 現有輸出（`--format text`，預設）

| 情境 | 輸出格式 | 回傳欄位 |
|------|---------|---------|
| 正常 | Rich Panel | 主旨 + 說明摘要 |
| 無主旨/說明 | Rich Panel | 原始內容截斷 |
| 錯誤 | Rich 紅字 + exit 1 | 錯誤訊息 |

**回傳路徑**：逐行掃「主旨：/說明：」prefix；`content[:max_length]`

### JSON 輸出（`--format json`）

```json
{
  "title": "本件辦理完畢，查照。",
  "summary": "詳如附件。",
  "source_file": "output.txt",
  "max_length": 100
}
```

- `title`：「主旨：」後的文字，無法擷取時為 `""`
- `summary`：「說明：」後的文字（截至 `max_length`），無法擷取時為 `""`

---

## 11. `gov-ai compare`

> 新增於 Epic 27（T27.1/T27.4）

### 現有輸出（`--format text`，預設）

| 情境 | 輸出格式 | 回傳欄位 |
|------|---------|---------|
| 完全相同 | Rich Panel | 「兩個檔案內容完全相同」 |
| 有差異 | Rich diff Panel | 新增（綠）/刪除（紅）行；末尾統計 |
| `--stats-only` | Rich 文字 | `+N 行新增 / -M 行刪除` |
| 錯誤 | Rich 紅字 + exit 1 | 錯誤訊息 |

**回傳路徑**：`difflib.unified_diff()`；行數統計 `startswith(+/-)` 過濾 `+++/---`

### JSON 輸出（`--format json`）

```json
{
  "added": 3,
  "removed": 1,
  "identical": false,
  "diff_lines": [
    "--- a.txt",
    "+++ b.txt",
    "@@ -1,2 +1,3 @@",
    " 行一",
    "-行二",
    "+行三",
    "+行四"
  ]
}
```

- `identical`：`true` 當兩檔案完全相同（`diff_lines` 為 `[]`）
- `diff_lines`：`unified_diff` 原始輸出每行（已去除換行符）
