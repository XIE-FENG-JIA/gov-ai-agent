#!/usr/bin/env bash
# 公文 AI Agent — 快速啟動腳本
# 用法：bash scripts/run_server.sh
set -e

cd "$(dirname "$0")/.."

# 1. 檢查 Python
if ! command -v python &>/dev/null && ! command -v python3 &>/dev/null; then
  echo "錯誤：找不到 Python，請先安裝 Python 3.11+"
  exit 1
fi
PY=$(command -v python3 || command -v python)
echo "使用 Python: $($PY --version)"

# 2. 建立虛擬環境（如不存在）
if [ ! -d ".venv" ]; then
  echo "建立虛擬環境 (.venv)..."
  $PY -m venv .venv
fi

# 3. 啟動虛擬環境
if [ -f ".venv/Scripts/activate" ]; then
  source .venv/Scripts/activate  # Windows (Git Bash)
else
  source .venv/bin/activate      # macOS / Linux
fi

# 4. 安裝依賴
echo "安裝依賴..."
pip install -q -e ".[dev]" 2>&1 | tail -1

# 5. 複製 .env（如不存在）
if [ ! -f ".env" ]; then
  echo "複製 .env.example → .env（請記得填入 API Key）"
  cp .env.example .env
fi

# 6. 啟動 API Server
HOST=${API_HOST:-0.0.0.0}
PORT=${API_PORT:-8000}
echo ""
echo "=========================================="
echo "  公文 AI Agent 啟動中..."
echo "  API:    http://localhost:${PORT}/docs"
echo "  Web UI: http://localhost:${PORT}/ui/"
echo "=========================================="
echo ""
uvicorn api_server:app --host "$HOST" --port "$PORT" --reload
