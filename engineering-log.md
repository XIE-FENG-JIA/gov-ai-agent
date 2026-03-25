# Engineering Log

> 這是自主工程師的工作日誌。每次改善都會記錄思考過程和結果。

## 改善紀錄

### [2026-03-26] Round 1 — 補齊缺失依賴 python-multipart
**角度**: Bug（依賴宣告缺失）
**為什麼**: `test_api_server.py` 全部 217 個測試因 `python-multipart` 未安裝而在 setup 階段 error，FastAPI form data 功能在生產環境也會出問題。這是影響面最大的單一問題。
**做了什麼**:
- `pyproject.toml` 新增 `python-multipart>=0.0.7,<1.0.0`
- `requirements.txt` 同步新增
- 同時安裝了已宣告但未安裝的 `defusedxml` 和 `langgraph`
**結果**: PASS
- 修復前：122 failed + 245 errors = 367 個問題，2271 passed
- 修復後：70 failed + 0 errors = 70 個問題，2424 passed（+153）
- 改善率：81%
**下一步可能**:
- 剩餘 70 個失敗分析：test_fetchers(22) 多為網路/SSL 相關、test_e2e(21) 需完整環境、test_stress(9) 為壓測
- 加入 CI 的 `pip install -e .[dev]` 確保依賴完整性
- 考慮 `pytest-asyncio` 配置優化（有 4 warnings）

