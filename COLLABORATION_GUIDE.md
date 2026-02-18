# Claude Code + Gemini CLI 協作指南

**概述**: 本指南說明如何在「真實公文 AI Agent」項目開發中充分利用 Claude Code 與 Gemini CLI 的協作優勢，既能享受快速迭代的便利，又能進行大規模代碼分析和架構設計。

---

## 1. 快速決策樹：何時使用 Gemini CLI？

```
你需要幫助嗎？
│
├─ 編寫或修改少於 10 個文件的代碼？
│  └─ 使用 Claude Code（快速迭代）
│
├─ 編寫或修改 10-100 個文件？
│  └─ 使用 Claude Code（主開發）+ Gemini CLI（審查）
│
├─ 需要分析整個項目架構？
│  └─ 使用 Gemini CLI（全局視圖）
│
├─ 需要優化性能或重構？
│  └─ 使用 Gemini CLI（分析） + Claude Code（實施）
│
└─ 在生產前進行最後檢查？
   └─ 使用 Gemini CLI（安全性、性能、最佳實踐）
```

---

## 2. 典型工作流程

### 工作流 A: 實施新 Agent（單個功能）

**時間**: 1-2 天
**工具**: 主要 Claude Code，可選 Gemini CLI

```mermaid
Claude Code (主要)
  │
  ├─ 1. 確認需求與設計 (1hr)
  ├─ 2. 生成代碼框架 (0.5hr)
  ├─ 3. 實現核心邏輯 (2-3hr)
  ├─ 4. 編寫單元測試 (1hr)
  └─ 5. 本地驗證 (0.5hr)

  需要設計驗證？→ 調用 Gemini CLI

Gemini CLI (可選)
  │
  ├─ 分析代碼結構和最佳實踐
  └─ 返回優化建議

Claude Code (改進)
  │
  └─ 根據建議優化代碼
```

**執行步驟**:

```bash
# 1. Claude Code：實現新 Agent
# 完成代碼編寫後...

# 2. (可選) 調用 Gemini 進行代碼審查
gemini analyze-code-quality \
  --files "src/agents/new_agent.py" \
  --report review_new_agent.json

# 3. Claude Code：根據建議改進
# 修改代碼...

# 4. 本地測試
pytest tests/test_new_agent.py -v
```

---

### 工作流 B: 完成 Phase 1（核心 Agent 實現）

**時間**: 2-3 週
**工具**: Claude Code（主），Gemini CLI（審查和優化）

```
周 1: Claude Code 實現基本功能
  ├─ 需求理解 Agent
  ├─ 範例檢索 Agent
  └─ 模板生成 Agent

周 1.5: Gemini CLI 質量檢查
  └─ 代碼品質、性能瓶頸分析

周 2: Claude Code 根據建議優化
  ├─ 優化向量檢索
  ├─ 改進錯誤處理
  └─ 添加缺失的類型提示

周 2.5: Gemini CLI 架構驗證
  └─ 確保 Agent 架構與系統匹配

周 3: Claude Code 完成迭代與測試
  ├─ 集成測試
  └─ 性能基準測試
```

**執行命令**:

```bash
# 周 1 末：代碼品質檢查
gemini analyze-code-quality \
  --files "src/agents/**/*.py" \
  --report phase1_quality.json

# 周 2 末：架構驗證
gemini review-architecture \
  --codebase src/ \
  --focus "agent-design,integration" \
  --output phase1_architecture.json

# 周 3 末：性能分析
gemini optimize-code \
  --codebase src/ \
  --focus "performance,memory" \
  --output phase1_optimizations.json
```

---

### 工作流 C: 知識庫建構與優化

**時間**: 1-2 週
**工具**: Claude Code（實施），Gemini CLI（大規模分析）

```
Claude Code (數據處理)
  │
  ├─ 爬取政府網站公文
  ├─ 解析和清洗數據
  └─ 構建向量索引

需要大規模分析？→ Gemini CLI

Gemini CLI (1M tokens 分析)
  │
  ├─ 分析數千份公文
  ├─ 提取通用模板模式
  ├─ 識別機關特色
  └─ 優化索引結構建議

Claude Code (優化實施)
  │
  ├─ 實現 Gemini 的優化方案
  ├─ 重構向量索引
  └─ 驗證檢索準確率
```

**執行命令**:

```bash
# Claude Code：爬取和初始化知識庫
python scripts/build_kb.py --source gov.tw

# Gemini CLI：大規模數據分析
gemini analyze-codebase "kb_data/" \
  --focus "data-structure,patterns,vectors" \
  --detailed \
  --output kb_analysis.json

# Claude Code：根據分析結果優化
# 修改知識庫結構...

# 驗證改進
python scripts/test_kb_retrieval.py --benchmark
```

---

## 3. Gemini CLI 命令速查表

### 最常用命令

| 命令 | 用途 | 應用場景 |
|------|------|--------|
| `analyze-codebase` | 代碼結構和模式分析 | Phase 1-4 結束時進行 |
| `review-architecture` | 架構設計審查 | 新 Agent/模塊完成後 |
| `analyze-code-quality` | 代碼品質和複雜度 | 每個 Phase 的質量檢查 |
| `optimize-code` | 性能優化建議 | 性能優化階段 |
| `audit-security` | 安全性審計 | Phase 4-5 安全檢查 |
| `suggest-refactoring` | 重構建議 | 技術債清理時 |

### 命令使用模板

```bash
# 1. 針對單個模塊的品質檢查
gemini analyze-code-quality \
  --files "src/agents/requirement_analyzer.py" \
  --report requirement_analyzer_review.json

# 2. 架構整體審查
gemini review-architecture \
  --codebase src/ \
  --focus "agent-design,communication-patterns" \
  --output architecture_review.json

# 3. 性能優化分析
gemini optimize-code \
  --codebase src/ \
  --focus "performance,memory-usage" \
  --output performance_recommendations.json

# 4. 安全性檢查
gemini audit-security \
  --codebase src/ \
  --output security_audit.json

# 5. 大規模知識庫分析
gemini analyze-codebase "kb_data/" \
  --focus "data-patterns,structure-optimization" \
  --detailed \
  --output kb_optimization.json
```

---

## 4. Claude Code 和 Gemini 的通訊模式

### Claude Code 發送任務到 Gemini

**格式**:
```json
{
  "task_type": "analyze_code_quality",
  "target": "src/agents/",
  "focus_areas": [
    "performance",
    "error_handling",
    "async_patterns"
  ],
  "output_format": "structured_report"
}
```

### Gemini 返回分析結果

**格式**:
```json
{
  "analysis_id": "analysis_20250101_001",
  "status": "completed",
  "summary": "代碼質量良好，但存在可優化的性能瓶頸",

  "findings": [
    {
      "category": "Performance",
      "severity": "medium",
      "location": "src/agents/example_retriever.py:45",
      "description": "向量檢索查詢缺少批量優化",
      "recommendation": "使用批量 API 調用減少網絡往返",
      "estimated_improvement": "40% 速度提升"
    }
  ],

  "overall_score": {
    "code_quality": 8.2,
    "performance": 7.1,
    "maintainability": 8.5,
    "security": 8.8
  }
}
```

---

## 5. 每個開發階段的協作檢查清單

### Phase 0: 基礎設施

- [ ] Claude Code：完成項目初始化
- [ ] Gemini CLI：`gemini review-architecture --codebase src/`
  - 驗證 LLM 提供者抽象設計
  - 檢查依賴管理
- [ ] Claude Code：根據反饋調整架構
- [ ] 運行本地測試通過

### Phase 1: 核心 Agent 實現

- [ ] Claude Code：完成 4 個 Agent 實現
- [ ] Gemini CLI：`gemini analyze-code-quality --files "src/agents/**/*.py"`
  - 檢查代碼複雜度
  - 評估向量檢索性能
- [ ] Gemini CLI：`gemini optimize-code --codebase src/ --focus performance`
  - RAG 檢索優化建議
- [ ] Claude Code：實施優化
- [ ] 運行集成測試

### Phase 2: 多 Agent 審查機制

- [ ] Claude Code：實現並行審查框架
- [ ] Gemini CLI：`gemini review-architecture --codebase src/`
  - 驗證並行設計
  - 檢查 Agent 間通訊
- [ ] Gemini CLI：`gemini audit-security --codebase src/`
  - 檢查錯誤處理和超時
- [ ] Claude Code：改進並行策略
- [ ] 性能基準測試

### Phase 3: 輸出與匯出

- [ ] Claude Code：實現文檔轉換邏輯
- [ ] Gemini CLI：`gemini analyze-code-quality --files "src/exporters/**/*.py"`
- [ ] Claude Code：修複發現的問題
- [ ] 功能測試（Word、Markdown 轉換）

### Phase 4: CLI 集成

- [ ] Claude Code：完成所有 CLI 命令
- [ ] Gemini CLI：`gemini review-architecture --codebase src/ --detailed`
  - 全局一致性檢查
  - API 設計驗證
- [ ] Claude Code：最後調整
- [ ] 集成測試覆蓋所有命令組合

### Phase 5: 生產前檢查

- [ ] Gemini CLI：`gemini audit-security --codebase src/`
- [ ] Gemini CLI：`gemini analyze-codebase src/ --detailed`
  - 完整代碼審查
  - 技術債評估
- [ ] Claude Code：修複所有高優先級問題
- [ ] 運行所有測試並驗證性能指標

---

## 6. 成本與效率分析

### Claude Code 的優勢
- ✅ 快速迭代（適合編寫和修改代碼）
- ✅ 實時交互反饋
- ✅ 本地測試驗證快速
- ✅ 不消耗 Gemini 配額

### Gemini CLI 的優勢
- ✅ 1M tokens 上下文（適合大規模分析）
- ✅ 全局視圖和最佳實踐建議
- ✅ 性能和安全審計
- ✅ 無 API 成本（通過 Claude Code 使用）

### 推薦的使用模式

```
日常開發（80% 時間）: Claude Code
  └─ 快速編碼、測試、迭代

定期檢查（20% 時間）: Gemini CLI
  └─ 架構審查、質量檢查、優化建議
```

---

## 7. 常見問題 (FAQ)

**Q: 何時應該調用 Gemini CLI？**

A: 當你的任務涉及：
- 分析 > 100 個源文件
- 進行架構設計或重大重構
- 性能或安全審計
- 大規模數據分析

**Q: Gemini CLI 的分析結果是否可信？**

A: 完全可信。Gemini 可以訪問整個項目的 1M tokens 上下文，能進行全局分析。建議在重要決策（架構、性能優化）前使用。

**Q: 如何整合 Gemini 的建議到 Claude Code 開發中？**

A:
1. 保存 Gemini 的 JSON 分析結果
2. 在 Claude Code 中讀取這個文件
3. 要求 Claude Code「根據 Gemini 的分析結果改進代碼」
4. Claude Code 會直接應用建議

**Q: 是否需要每個 Phase 都調用 Gemini？**

A: 不一定。根據需要調用：
- 完成重要功能後
- 遇到架構問題時
- 準備進入下一個 Phase 前

**Q: 如何避免重複工作？**

A:
- Gemini 負責分析和建議
- Claude Code 負責實施
- 清晰的分工可以避免重複

---

## 8. 最佳實踐

### Do's ✅

- ✅ 定期使用 Gemini CLI 審查（每個 Phase 結束）
- ✅ 保存 Gemini 的分析報告（用於複習和跟蹤）
- ✅ 在 Claude Code 中明確參考 Gemini 的建議
- ✅ 對複雜決策使用 Gemini 分析
- ✅ 自動化 Gemini 命令調用（通過腳本）

### Don'ts ❌

- ❌ 不要過度依賴 Gemini（日常開發應主要用 Claude Code）
- ❌ 不要忽視 Gemini 的警告（尤其是安全相關）
- ❌ 不要在小改動時調用 Gemini（浪費資源）
- ❌ 不要只讀 Gemini 建議而不實施（建議需要 Claude Code 實施）
- ❌ 不要修改 Gemini 無法訪問的文件後跳過重新分析

---

## 9. 自動化協作工作流（可選）

### 創建自動化腳本

```bash
#!/bin/bash
# auto_review.sh - 自動化 Gemini 審查工作流

PHASE=$1
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "开始 Phase $PHASE 审查..."

case $PHASE in
  0)
    gemini review-architecture --codebase src/ \
      --output reports/phase0_architecture_$TIMESTAMP.json
    ;;
  1)
    gemini analyze-code-quality --files "src/agents/**/*.py" \
      --report reports/phase1_quality_$TIMESTAMP.json
    gemini optimize-code --codebase src/ --focus performance \
      --output reports/phase1_optimization_$TIMESTAMP.json
    ;;
  2)
    gemini review-architecture --codebase src/ \
      --focus "concurrency,agent-communication" \
      --output reports/phase2_architecture_$TIMESTAMP.json
    ;;
  *)
    echo "未知的 Phase: $PHASE"
    ;;
esac

echo "审查完成！报告已保存到 reports/ 目录"
```

### 使用自動化腳本

```bash
# 周 1 末：Phase 1 質量檢查
./auto_review.sh 1

# 周 3 末：Phase 2 架構驗證
./auto_review.sh 2
```

---

## 10. 總結

### Claude Code + Gemini CLI 的黃金組合

| 階段 | Claude Code 角色 | Gemini CLI 角色 |
|------|-----------------|-----------------|
| **需求分析** | 與用戶討論需求 | 評估技術可行性 |
| **設計階段** | 設計架構框架 | 驗證設計最佳實踐 |
| **實施階段** | 快速編寫代碼 | 定期質量檢查 |
| **測試階段** | 執行測試 | 審計安全和性能 |
| **優化階段** | 實施改進 | 提供優化建議 |
| **發佈階段** | 最後調整 | 生產前檢查 |

這種協作模式充分發揮了兩種工具的優勢：
- **Claude Code**: 快速迭代、實時反饋、交互靈活
- **Gemini CLI**: 全局視圖、深度分析、最佳實踐

結果是更高效、更高質量的開發！

---

**Last Updated**: 2025-11-26
**Version**: 1.0
