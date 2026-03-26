# MISSION — 公文 AI Agent

## 核心目標
台灣政府公文 AI 智慧助理 — 多 Agent 審查與自動生成系統。

## 使用者最需要
1. 快速產生符合格式的公文草稿
2. 自動引用正確的法規依據
3. 多層審查（合規性、用語、格式）
4. 知識庫持續更新

## 功能缺口（優先開發）
- ~~公文範本庫擴充（更多類型）~~ ✅ Round 73 完成（箋函/手令/開會紀錄各 3 種範本）
- ~~審查意見的具體修改建議（不只指出問題）~~ ✅ Round 75 完成（review_cmd --apply + diff 輸出）
- ~~批次處理效能優化~~ ✅ Round 76 完成（共享初始化 + --workers 並行 worker）
- ~~知識庫冪等索引~~ ✅ Round 78 完成（kb sync 增量同步 + upsert 防重複）
- ~~法規自動更新機制~~ ✅ Round 1 完成（staleness check + auto-update CLI）
