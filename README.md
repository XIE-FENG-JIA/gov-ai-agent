# 公文 AI Agent (Gov AI Agent)

## 專案簡介
這是一個專為台灣政府機關設計的 AI 公文撰寫輔助系統。採用 **Local-First** 架構，結合 **Ollama (Llama 3.1)** 與 **RAG (Retrieval-Augmented Generation)** 技術，能根據使用者的一句話需求，自動檢索範例、生成符合《文書處理手冊》規範的公文草稿，並匯出為標準 Word 格式。

## 核心功能
- **需求分析**: 自動解析自然語言，識別發文機關、受文者與主旨。
- **智慧檢索**: 使用本地向量資料庫 (ChromaDB) 搜尋相似過往公文。
- **自動撰寫**: 參考範例與規範，生成「主旨、說明、辦法」完整內容。
- **格式審查**: 自動檢查是否缺少必要欄位。
- **標準匯出**: 一鍵產出排版完美的 `.docx` 檔案。

## 快速開始

### 1. 環境準備
- 安裝 Python 3.11+
- 安裝 [Ollama](https://ollama.com/) 並下載模型：
  ```bash
  ollama pull llama3.1:8b
  ```

### 2. 安裝依賴
```bash
pip install .
```

### 3. 匯入知識庫 (首次使用)
將您的公文範例 (.md) 放入 `kb_data/examples/`，然後執行：
```bash
$env:OLLAMA_MODELS="D:\OllamaModels" # 設定模型路徑
python -m src.cli.main kb ingest
```

### 4. 生成公文
```bash
python -m src.cli.main generate --input "發一份函給各區公所，關於春節垃圾清運時間調整" --output "春節公告.docx"
```

## 測試
本專案包含完整的自動化測試套件：
```powershell
.\run_all_tests.ps1
```

## 專案結構
- `src/`: 核心源碼
  - `agents/`: AI 邏輯 (Requirement, Writer, Auditor)
  - `knowledge/`: RAG 知識庫管理
  - `document/`: Word 匯出引擎
  - `cli/`: 命令行介面
- `tests/`: 自動化測試
- `.spec/`: 開發規範 (Spec Kit)