#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "error: python executable not found: $PYTHON_BIN" >&2
  exit 1
fi

exec "$PYTHON_BIN" scripts/run_nightly_integration.py --python "$PYTHON_BIN" "$@"
