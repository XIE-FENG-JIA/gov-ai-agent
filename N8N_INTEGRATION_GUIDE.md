# n8n 整合指南

本指南說明如何使用 n8n 本地端來控制公文 AI Agent 的開會流程。

## 📦 安裝需求

### 1. Python 依賴

```bash
# 安裝 FastAPI 相關套件
pip install fastapi uvicorn --break-system-packages
```

### 2. n8n 本地端安裝

```bash
# 使用 npm
npm install n8n -g

# 或使用 Docker
docker run -it --rm \
  --name n8n \
  -p 5678:5678 \
  -v ~/.n8n:/home/node/.n8n \
  n8nio/n8n
```

---

## 🚀 快速啟動

### Step 1: 啟動 API Server

```bash
cd "C:\Users\User\Desktop\公文ai agent"

# 開發模式（自動重載）
uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload

# 或生產模式
python api_server.py
```

啟動後可訪問：
- API 文件：http://localhost:8000/docs
- ReDoc：http://localhost:8000/redoc

### Step 2: 啟動 n8n

```bash
n8n start
```

訪問：http://localhost:5678

### Step 3: 匯入 Workflow

1. 在 n8n 介面點擊「Import from file」
2. 選擇 `n8n_workflow_meeting.json`
3. 點擊「Save」

---

## 📡 API Endpoints

### 基礎端點

| Endpoint | Method | 說明 |
|----------|--------|------|
| `/` | GET | 健康檢查 |
| `/api/v1/health` | GET | 詳細狀態 |

### Agent 端點

| Endpoint | Method | 說明 |
|----------|--------|------|
| `/api/v1/agent/requirement` | POST | 需求分析 |
| `/api/v1/agent/writer` | POST | 撰寫草稿 |
| `/api/v1/agent/review/format` | POST | 格式審查 |
| `/api/v1/agent/review/style` | POST | 文風審查 |
| `/api/v1/agent/review/fact` | POST | 事實審查 |
| `/api/v1/agent/review/consistency` | POST | 一致性審查 |
| `/api/v1/agent/review/compliance` | POST | 政策合規審查 |
| `/api/v1/agent/review/parallel` | POST | 並行審查（全部） |
| `/api/v1/agent/refine` | POST | 修改草稿 |

### 完整流程端點

| Endpoint | Method | 說明 |
|----------|--------|------|
| `/api/v1/meeting` | POST | 完整開會流程 |

---

## 📝 使用範例

### 1. 直接呼叫完整流程

```bash
curl -X POST http://localhost:8000/api/v1/meeting \
  -H "Content-Type: application/json" \
  -d '{
    "user_input": "幫我寫一份函，台北市環保局要發給各學校，關於加強資源回收",
    "max_rounds": 3,
    "output_docx": true
  }'
```

### 2. 透過 n8n Webhook 呼叫

```bash
# n8n workflow 啟動後的 Webhook URL
curl -X POST http://localhost:5678/webhook/gov-doc-meeting \
  -H "Content-Type: application/json" \
  -d '{
    "user_input": "幫我寫一份公告，臺北市政府要公告垃圾清運時間調整",
    "max_rounds": 2
  }'
```

### 3. 分步驟呼叫（適合 n8n 自訂流程）

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"

# Step 1: 需求分析
req_resp = requests.post(f"{BASE_URL}/agent/requirement", json={
    "user_input": "幫我寫一份函，台北市環保局發給各學校，關於資源回收"
})
requirement = req_resp.json()["requirement"]

# Step 2: 撰寫草稿
writer_resp = requests.post(f"{BASE_URL}/agent/writer", json={
    "requirement": requirement
})
draft = writer_resp.json()["formatted_draft"]

# Step 3: 並行審查
review_resp = requests.post(f"{BASE_URL}/agent/review/parallel", json={
    "draft": draft,
    "doc_type": requirement["doc_type"],
    "agents": ["format", "style", "fact", "consistency", "compliance"]
})
review_result = review_resp.json()

# Step 4: 如果需要修改
if review_result["risk_summary"] not in ["Safe", "Low"]:
    feedback = [
        {"agent_name": name, "issues": result["issues"]}
        for name, result in review_result["results"].items()
        if result["issues"]
    ]
    
    refine_resp = requests.post(f"{BASE_URL}/agent/refine", json={
        "draft": draft,
        "feedback": feedback
    })
    final_draft = refine_resp.json()["refined_draft"]
```

---

## 🔄 n8n Workflow 架構

```
┌─────────────┐
│  Webhook    │ ← 接收請求
└──────┬──────┘
       ↓
┌─────────────┐
│  需求分析   │ ← /api/v1/agent/requirement
└──────┬──────┘
       ↓
┌─────────────┐
│  撰寫草稿   │ ← /api/v1/agent/writer
└──────┬──────┘
       ↓
┌─────────────┐
│  並行審查   │ ← /api/v1/agent/review/parallel
└──────┬──────┘     (format, style, fact, consistency, compliance)
       ↓
   ┌───┴───┐
   │需要修改?│
   └───┬───┘
  Yes  │  No
   ↓   └──────→ ┌─────────────┐
┌─────────────┐ │  回傳結果   │
│ Editor修改  │ └─────────────┘
└──────┬──────┘
       ↓
  (回到並行審查，最多 3 輪)
```

---

## ⚙️ 進階設定

### 自訂 LLM Provider

編輯 `config.yaml`：

```yaml
llm:
  provider: openrouter  # 或 ollama, gemini
  model: anthropic/claude-3.5-sonnet
  api_key: ${LLM_API_KEY}
```

### 調整審查權重

在 `api_server.py` 中修改：

```python
CATEGORY_WEIGHTS = {
    "format": 3.0,      # 格式最重要
    "compliance": 2.5,  # 政策合規次之
    "fact": 2.0,        # 事實正確
    "consistency": 1.5, # 一致性
    "style": 1.0        # 文風
}
```

### n8n 環境變數

```bash
# 設定執行超時（預設 300 秒）
export N8N_EXECUTIONS_TIMEOUT=600

# 啟用 Webhook 測試模式
export N8N_ENDPOINTS_WEBHOOK_TEST=webhook-test
```

---

## 🐛 除錯

### 檢查 API Server

```bash
# 健康檢查
curl http://localhost:8000/api/v1/health

# 查看 API 文件
open http://localhost:8000/docs
```

### 檢查 n8n 執行日誌

n8n 介面 → Executions → 點擊執行記錄查看詳情

### 常見問題

1. **Connection Refused**
   - 確認 API Server 正在執行
   - 確認 port 8000 沒有被佔用

2. **LLM 回應緩慢**
   - 考慮使用本地 Ollama
   - 調整 `timeout` 設定

3. **n8n Workflow 超時**
   - 增加 `N8N_EXECUTIONS_TIMEOUT`
   - 減少 `max_rounds` 參數

---

## 📚 相關資源

- [n8n 官方文件](https://docs.n8n.io/)
- [FastAPI 官方文件](https://fastapi.tiangolo.com/)
- [公文 AI Agent 主文件](./README.md)
- [Multi-Agent V2 指南](./MULTI_AGENT_V2_GUIDE.md)
