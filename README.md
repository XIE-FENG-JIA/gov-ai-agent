# 公文 AI Agent (Gov AI Agent)

## 專案簡介
這是一個專為台灣政府機關設計的 AI 公文撰寫輔助系統。採用 **Local-First** 架構，結合 **Ollama (Llama 3.1)** 與 **RAG (Retrieval-Augmented Generation)** 技術，能根據使用者的一句話需求，自動檢索範例、生成符合《文書處理手冊》規範的公文草稿，並匯出為標準 Word 格式。

## 核心功能
- **需求分析**: 自動解析自然語言，識別發文機關、受文者與主旨。
- **智慧檢索**: 使用本地向量資料庫 (ChromaDB) 搜尋相似過往公文。
- **自動撰寫**: 參考範例與規範，生成「主旨、說明、辦法」完整內容。
- **多 Agent 審查**: 格式、文風、事實、一致性、合規性五大面向並行審查。
- **自動修正**: 根據審查結果自動修正草稿。
- **標準匯出**: 一鍵產出排版完美的 `.docx` 檔案。
- **機構記憶**: 學習並記住各機關的用詞習慣和簽名格式。

## 快速開始

### 1. 環境準備
- 安裝 Python 3.11+
- 安裝 [Ollama](https://ollama.com/) 並下載模型：
  ```bash
  ollama pull llama3.1:8b
  ```
- 複製環境變數範本並填入設定（API Key 等）：
  ```bash
  cp .env.example .env
  # 編輯 .env 填入您的 API Key 與相關設定
  ```

### 2. 安裝依賴
```bash
pip install .
```

### 3. 匯入知識庫 (首次使用)
將您的公文範例 (.md) 放入 `kb_data/examples/`，然後執行：
```bash
python -m src.cli.main kb ingest
```

### 4. 生成公文
```bash
python -m src.cli.main generate -i "發一份函給各區公所，關於春節垃圾清運時間調整" -o "春節公告.docx"
```

## CLI 命令

### 公文生成
```bash
# 基本生成
gov-ai generate -i "台北市環保局發給各學校，加強資源回收"

# 指定輸出路徑
gov-ai generate -i "內政部公告修正建築法施行細則" -o 公告.docx

# 跳過多 Agent 審查
gov-ai generate -i "簽請同意出差計畫" --skip-review

# 批次處理（從 JSON 檔案讀取多筆需求）
gov-ai generate --batch batch.json
gov-ai generate -b batch.json --skip-review
```

#### 批次處理 JSON 格式
```json
[
  {"input": "台北市環保局發給各學校，加強資源回收", "output": "環保函.docx"},
  {"input": "內政部公告修正建築法施行細則", "output": "公告.docx"}
]
```

### 知識庫管理
```bash
gov-ai kb ingest                        # 匯入本地範例
gov-ai kb list                          # 列出知識庫統計
gov-ai kb search "資源回收"              # 語意搜尋知識庫
gov-ai kb fetch-laws --ingest           # 擷取法規並匯入（Level A）
gov-ai kb fetch-gazette --ingest        # 擷取公報並匯入（Level A）
gov-ai kb fetch-opendata --ingest       # 擷取開放資料（Level B）
gov-ai kb fetch-npa --ingest            # 擷取警政署資料（Level B）
```

### 組態管理
```bash
gov-ai config show                      # 顯示目前設定
gov-ai config validate                  # 驗證設定完整性
gov-ai config validate --test-llm       # 驗證設定並測試 LLM 連線
gov-ai config fetch-models              # 擷取可用免費模型
gov-ai config fetch-models -u           # 自動更新最佳模型
```

### LLM 切換
```bash
gov-ai switch ollama                    # 切換至本地 Ollama
gov-ai switch openrouter                # 切換至 OpenRouter

# 啟用詳細日誌
gov-ai --verbose generate -i "..."      # 顯示 DEBUG 層級日誌
```

## API Server (n8n 整合)
```bash
uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
```

| 端點 | 方法 | 說明 |
|------|------|------|
| `/api/v1/health` | GET | 健康檢查 |
| `/api/v1/agent/requirement` | POST | 需求分析 |
| `/api/v1/agent/writer` | POST | 草稿撰寫 |
| `/api/v1/agent/review/parallel` | POST | 並行審查 |
| `/api/v1/agent/refine` | POST | 自動修正 |
| `/api/v1/agent/meeting` | POST | 完整工作流 |
| `/api/v1/batch` | POST | 批次處理多筆公文 |
| `/api/v1/download/{filename}` | GET | 下載 DOCX |

## Web UI

啟動 API Server 後，瀏覽器開啟 `http://localhost:8000/ui/` 即可使用 Web 介面。

| 頁面 | 路徑 | 說明 |
|------|------|------|
| 首頁 | `/ui/` | 輸入需求描述，一鍵生成公文 |
| 知識庫 | `/ui/kb` | 檢視知識庫狀態與統計 |
| 設定 | `/ui/config` | 檢視系統設定與 LLM 狀態 |

Web UI 使用 Jinja2 模板 + HTMX，無需 Node.js 或前端建構工具。

## 測試
本專案包含 1197 個自動化測試，覆蓋所有核心功能：
```bash
pytest tests/ -v
```

## 專案結構
- `src/`: 核心源碼
  - `agents/`: AI 代理（需求分析、撰寫、審查、修正、機構記憶）
  - `knowledge/`: RAG 知識庫管理 + 資料擷取器
  - `document/`: Word 匯出引擎
  - `cli/`: 命令行介面
  - `core/`: 配置、模型、常數、LLM 提供者
  - `web_preview/`: Web UI（Jinja2 + HTMX）
- `api_server.py`: FastAPI 伺服器
- `tests/`: 自動化測試（1197 個測試）
- `kb_data/`: 知識庫資料（範例、法規、政策、術語）
