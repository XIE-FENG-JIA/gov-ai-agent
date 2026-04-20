# 公文 AI Agent (Gov AI Agent)

台灣政府公文改寫系統。核心策略不是從零生成，而是用真實公開公文做檢索、最小改寫、審查、匯出，並保留來源。

## 現況
- Local-first Python 3.11 應用，主入口是 `gov-ai` CLI、FastAPI API、Jinja2 + HTMX Web UI。
- 生成流程仍由 repo 自有 writer + review graph 負責。
- 公開來源 ingest 已有 5 個 adapter。
- Epic 2 已落 `src/integrations/open_notebook/` seam，但正式 writer cutover 還沒開。
- 詳細架構看 `docs/architecture.md`，整合決策看 `docs/integration-plan.md`。

## 核心能力
- 需求解析：把自然語言需求轉成結構化公文需求。
- 檢索改寫：從知識庫找相似公文與規範，走最小改寫。
- 多 agent 審查：格式、事實、一致性、合規、稽核並行檢查。
- 公開來源 ingest：把公開政府資料正規化到 `kb_data/raw/` 和 `kb_data/corpus/`。
- DOCX 匯出：輸出標準 Word 公文。

## 快速開始

### 1. 安裝
```bash
pip install .
cp .env.example .env
```

如需本地模型：

```bash
ollama pull llama3.1:8b
```

### 2. 基本生成
```bash
gov-ai generate -i "發一份函給各區公所，關於春節垃圾清運時間調整" -o 春節公告.docx
```

### 3. 匯入本地知識庫
```bash
gov-ai kb ingest
gov-ai kb search "資源回收"
```

## 公開資料來源

目前 `src/sources/` 內建 5 個 adapter：

| Source key | Adapter | Upstream | 用途 |
|---|---|---|---|
| `mojlaw` | `MojLawAdapter` | JSON API | 法規與法律文本 |
| `datagovtw` | `DataGovTwAdapter` | JSON API | 開放資料集 metadata |
| `executiveyuanrss` / `executive_yuan_rss` | `ExecutiveYuanRssAdapter` | RSS / XML | 行政院公告 |
| `mohw` | `MohwRssAdapter` | RSS / XML | 衛福部公告 |
| `fda` | `FdaApiAdapter` | JSON / HTML | 食藥署公告 |

常用來源命令：

```bash
gov-ai sources ingest --source mojlaw --limit 3
gov-ai sources ingest --source datagovtw --limit 3 --since 2026-01-01
gov-ai sources status --base-dir kb_data
gov-ai sources stats --base-dir kb_data
gov-ai sources stats --adapter mojlaw --base-dir kb_data
```

若要驗真實 upstream，不接受 fixture fallback：

```bash
gov-ai sources ingest --source mojlaw --limit 3 --require-live
python scripts/live_ingest.py --sources mojlaw,datagovtw,executive_yuan_rss --limit 3
```

## Open Notebook Seam

Epic 2 目前採 repo-owned seam，不直接把 vendor import 散進 `src/agents/`：

- `src/integrations/open_notebook/`：mode config、adapter factory、off/smoke/writer 邊界。
- `src/cli/open_notebook_cmd.py`：smoke CLI。
- `GOV_AI_OPEN_NOTEBOOK_MODE=off|smoke|writer`：明確切換，不做 silent auto-detect。

Smoke path 範例：

```bash
$env:GOV_AI_OPEN_NOTEBOOK_MODE="smoke"
python -m src.cli.main open-notebook smoke --question "hi" --doc "first evidence"
python scripts/smoke_open_notebook.py
```

## 其他常用命令

### 組態
```bash
gov-ai config show
gov-ai config validate
gov-ai config validate --test-llm
gov-ai switch ollama
gov-ai switch openrouter
```

### API
```bash
uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
```

| 端點 | 方法 | 說明 |
|---|---|---|
| `/api/v1/health` | GET | 健康檢查 |
| `/api/v1/agent/requirement` | POST | 需求分析 |
| `/api/v1/agent/writer` | POST | 草稿撰寫 |
| `/api/v1/agent/review/parallel` | POST | 並行審查 |
| `/api/v1/agent/refine` | POST | 自動修正 |
| `/api/v1/agent/meeting` | POST | 完整流程 |
| `/api/v1/batch` | POST | 批次處理 |
| `/api/v1/download/{filename}` | GET | 下載 DOCX |

### Web UI

啟動 API 後開 `http://localhost:8000/ui/`。

## 測試

最新全量回歸：

```bash
pytest tests/ -q
```

2026-04-20 實跑結果：`3625 passed / 10 skipped / 0 failed`。

## Repo 導覽
- `src/agents/`: requirement / writer / review / refine。
- `src/sources/`: 公開來源 adapter 與 ingest pipeline。
- `src/integrations/`: Epic 2 repo-owned integration seam。
- `src/knowledge/`: ChromaDB-based retrieval 與索引管理。
- `src/document/`: DOCX 匯出。
- `src/cli/`: Typer CLI 指令。
- `src/api/`: FastAPI 路由與相依。
- `src/web_preview/`: 伺服器端 UI。
- `kb_data/`: raw snapshot、corpus、examples。
- `tests/`: 回歸測試。

## 參考文件
- `docs/architecture.md`
- `docs/integration-plan.md`
- `docs/llm-providers.md`
