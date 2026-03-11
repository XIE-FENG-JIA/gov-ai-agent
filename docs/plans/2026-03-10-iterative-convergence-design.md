# 分層收斂迭代設計文件

**日期**: 2026-03-10
**狀態**: 已核准

## 概述

將現有的線性 review → refine 流程改為**分層收斂迭代**（Layered Convergence Iteration），按嚴重度分 Phase 逐層消除所有問題，直到零 error + 零 warning。

## 設計決策

| 決策 | 選擇 |
|------|------|
| 迭代模式 | 全自動（無人工介入） |
| 品質門檻 | 零錯誤制（消除所有 error + warning） |
| 修正策略 | 按嚴重度分層修正（error → warning → info） |
| 最大輪數 | 無硬上限（依收斂條件 + 安全上限 15 輪） |

## 架構

```
使用者輸入需求
    ↓
需求分析 → 範例檢索 → 草稿生成（不變）
    ↓
╔══════════════════════════════════════════╗
║  分層收斂迴圈 (Layered Convergence)      ║
╠══════════════════════════════════════════╣
║                                          ║
║  Phase 1: ERROR 消除                     ║
║  ┌─→ 審查（5 Agent 並行）               ║
║  │   篩出 error issues                   ║
║  │   有 error? ──NO──→ 進入 Phase 2     ║
║  │       ↓ YES                           ║
║  │   分層修正（只修 error）              ║
║  │   targeted 驗證                       ║
║  │   收斂? ──NO──→ 下一輪               ║
║  └───────────────┘                       ║
║                                          ║
║  Phase 2: WARNING 消除（同樣邏輯）       ║
║                                          ║
║  Phase 3: INFO 消除（可配置跳過）        ║
║                                          ║
╚══════════════════════════════════════════╝
    ↓
匯出完美公文 + 迭代報告
```

## 收斂保護

| 條件 | 觸發行為 |
|------|---------|
| 連續 2 輪同一 Phase 分數無改善 | 強制進入下一 Phase |
| 同一 issue 修了 3 次仍存在 | 標記 `unfixable`，跳過 |
| 總輪數達安全上限（預設 15） | 強制停止，輸出當前最佳版本 |
| 某輪修正後分數下降 | 回滾到修正前版本，嘗試替代 prompt |

## 修正與驗證機制

### 每輪內部流程

1. **分組**：按產出 Agent 分組當前 Phase 的 issues
2. **精準 Prompt**：只包含該 Phase 嚴重度的 issues + suggestion
3. **LLM 修正**
4. **Targeted 驗證**：只重跑「產出 issues 的 Agent」
5. **Diff 比對**：追蹤修好/未修好/新冒出的 issues
6. **判斷收斂**

### Targeted 驗證規則

- 每個 Phase **第一輪**跑全部 5 Agent（完整掃描）
- 後續輪次只跑產出 issues 的 Agent
- Phase 轉換時重跑全量

## 資料結構

### IssueTracker

追蹤每個 issue 的修正歷程。issue_id = hash(agent_name + category + location + description)。

### IterationState

管理迭代狀態：current_phase, round_number, best_draft, best_score, issue_tracker, unfixable_issues, history。

## 修改檔案

| 檔案 | 變更 |
|------|------|
| `src/core/review_models.py` | 新增 IssueTracker, IterationState |
| `src/core/constants.py` | 新增迭代相關常數 |
| `src/agents/editor.py` | 重寫 `_iterative_review`，新增 targeted 驗證、回滾、分層修正 |
| `src/cli/generate.py` | 更新 max_rounds 上限，新增 --skip-info 選項 |
| `api_server.py` | 更新 MeetingRequest max_rounds 上限 |

## 向後相容

- `review_and_refine()` 的介面不變（draft, doc_type, max_rounds）
- max_rounds 預設值從 3 改為 0（0 代表使用新的無上限模式）
- 傳入 1-5 的值仍然走舊邏輯（相容現有用法）
