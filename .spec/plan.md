# Technical Plan: 公文 AI Agent

## 1. Architecture
採用 **CLI-First** 與 **Multi-Agent** 架構，透過 Python 作為膠水語言串接各個模組。

### Core Components
1.  **CLI Interface (Typer)**: 統一的命令入口 (`gov-ai`)，負責參數解析與流程控制。
2.  **Agent Orchestrator (LangChain/Custom)**: 管理 Agent 的生命週期與訊息傳遞。
3.  **Knowledge Base (ChromaDB)**: 本地向量資料庫，儲存公文範例與法規。
4.  **Document Engine (python-docx)**: 負責最終的格式排版與輸出。

## 2. Technology Stack
- **Language**: Python 3.11+
- **CLI Framework**: `typer` (Rich for UI)
- **LLM Interface**: `litellm` (兼容 OpenAI/Gemini/Ollama)
- **Vector DB**: `chromadb` (Local)
- **Document Processing**: `python-docx`, `markdown`
- **Testing**: `pytest`

## 3. Data Models
- **PublicDocRequirement**: 定義公文需求的 Pydantic Model。
- **PublicDocExample**: 定義範例公文的結構。
- **ReviewReport**: 定義多 Agent 審查結果的結構。

## 4. Directory Structure
```text
src/
  cli/          # CLI 命令實作
  agents/       # Agent 邏輯 (Requirement, Writer, Reviewer)
  core/         # 核心工具 (LLM, Config, Logging)
  knowledge/    # RAG 與向量資料庫操作
  document/     # Word/PDF 轉換引擎
tests/          # 單元與整合測試
.spec/          # GitHub Spec Kit 文件
```
