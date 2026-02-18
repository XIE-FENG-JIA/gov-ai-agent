# 「真實公文 AI Agent」- 快速啟動指南

---

## 第一步：項目概覽

### 項目架構圖

```
┌─────────────────────────────────────────────────────────┐
│  真實公文 AI Agent 系統 - CLI-First Architecture        │
└─────────────────────────────────────────────────────────┘

  User Interface (最終使用者)
           ↓
┌──────────────────────────────────────────────────────────┐
│            Claude Code (交互層 & 實施層)                  │
│  • 與用戶對話                                             │
│  • 調用 CLI 命令                                          │
│  • 編寫和修改代碼                                         │
│  • 執行實時測試                                          │
└──────────────────────────────────────────────────────────┘
           ↓ (複雜分析)
┌──────────────────────────────────────────────────────────┐
│          Gemini CLI (戰略層 & 審查層)                    │
│  • 大規模代碼分析 (1M tokens)                            │
│  • 架構設計審查                                          │
│  • 最佳實踐建議                                          │
└──────────────────────────────────────────────────────────┘
           ↓
┌──────────────────────────────────────────────────────────┐
│            CLI Commands (命令層)                          │
│  ├─ 公文-ai generate      （一鍵生成）                   │
│  ├─ 公文-ai ask-requirements （需求分析）               │
│  ├─ 公文-ai search-examples  （範例檢索）               │
│  ├─ 公文-ai generate-skeleton （骨架生成）              │
│  ├─ 公文-ai review-multi    （多 Agent 審查）            │
│  └─ 公文-ai export         （文檔匯出）                  │
└──────────────────────────────────────────────────────────┘
           ↓
┌──────────────────────────────────────────────────────────┐
│          Core Agent System (Agent 層)                    │
│  ├─ Requirement Analyzer (需求理解)                     │
│  ├─ Example Retriever (範例檢索)                        │
│  ├─ Template Generator (模板生成)                       │
│  ├─ Content Generator (內容生成)                        │
│  ├─ Format Auditor (格式稽核)                          │
│  ├─ Language Checker (文風檢查)                         │
│  ├─ Fact Checker (事實驗證)                             │
│  ├─ Consistency Checker (一致性檢查)                    │
│  └─ Editor-in-Chief (總編輯)                            │
└──────────────────────────────────────────────────────────┘
           ↓
┌──────────────────────────────────────────────────────────┐
│        Infrastructure (基礎設施層)                        │
│  ├─ LLM Backend (Ollama / Gemini API)                   │
│  ├─ Knowledge Base (SQLite + Chroma Vector DB)          │
│  ├─ Document Processor (python-docx + markdown)         │
│  └─ Config Manager (YAML)                               │
└──────────────────────────────────────────────────────────┘
```

---

## 第二步：核心概念

### 什麼是「真實公文 AI Agent」？

這是一個 **CLI-First 的公文智能助手系統**，特點是：

1. **以真實公文為標準** - 所有範例來自實際政府公文
2. **多 Agent 互審機制** - 不是單一 AI，而是 9 個專責 Agent 協作
3. **可追溯來源** - 每個建議都能追到具體的法規或參考公文
4. **人機協作** - AI 提供草稿和建議，人類做最終決策

### 系統的 5 個核心 Agent

| Agent | 職責 | 輸入 | 輸出 |
|-------|------|------|------|
| **需求理解** | 通過對話確認公文要素 | 用戶需求 | 結構化需求表 |
| **範例檢索** | 從知識庫找相似範例 | 需求表 | 推薦的公文範例 |
| **骨架生成** | 按格式生成公文骨架 | 需求表 + 範例 | Markdown 骨架 |
| **內容生成** | 填充實際內容 | 骨架 + 範例 | 初稿 v0 |
| **多 Agent 審查** | 並行審查草稿 | 初稿 v0 | 審稿報告 + 最終稿 |

### 系統的 4 個審查 Agent

| Agent | 檢查項目 |
|-------|--------|
| **格式稽核** | 欄位完整性、序號、字數限制 |
| **文風檢查** | 用語正式度、口語檢測、副詞使用 |
| **事實驗證** | 法條存在性、機構名稱、日期合理性 |
| **一致性檢查** | 主旨與內容一致、前後不矛盾 |

---

## 第三步：安裝與配置

### 系統需求

```
Python: 3.11+
Memory: 4GB (基礎) / 8GB (推薦)
Storage: 10GB (含知識庫)
OS: Windows / macOS / Linux
```

### 快速安裝

```bash
# 1. 複製項目
git clone <repo-url>
cd public-doc-ai-agent

# 2. 創建虛擬環境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 安裝依賴
pip install -r requirements.txt

# 4. 初始化知識庫
公文-ai init-kb --mode hybrid --enable-online-sync

# 5. 配置 LLM 後端
公文-ai config set llm.provider ollama
公文-ai config set llm.model mistral-7b

# 6. 驗證安裝
公文-ai --version
公文-ai config show
```

### 配置 LLM 後端

#### 選項 A: 本地 Ollama（推薦用於離線開發）

```bash
# 安裝 Ollama
# Windows/macOS: https://ollama.ai
# Linux: curl https://ollama.ai/install.sh | sh

# 啟動 Ollama 服務
ollama serve

# 另開終端，下載模型
ollama pull mistral-7b

# 配置 Claude Code 使用
公文-ai config set llm.provider ollama
公文-ai config set llm.model mistral-7b
```

#### 選項 B: Gemini API（通過 Claude Code 調用）

```bash
# 配置 Gemini API 密鑰
公文-ai config set llm.provider gemini
公文-ai config set gemini.api-key $GEMINI_API_KEY
```

---

## 第四步：基本使用

### 方式 1: 一鍵生成（推薦新手）

```bash
# 最簡單的使用方式
公文-ai generate \
  --input 需求.txt \
  --output 最終稿.docx \
  --doc-type 函 \
  --org 臺北市政府
```

**輸入 `需求.txt` 範例**:
```
案由: 函轉行政院會議決議
對象: 各區公所
依據: 行政院 XX 政策
內容要點:
  1. 配合國家政策推動
  2. 請各區公所於 2025-02-28 前回報
附件: 附件1_決議文.pdf
```

**輸出 `最終稿.docx`**:
```
已格式化的完整公文，包含:
  ✓ 正確的主旨格式
  ✓ 結構化的說明段落
  ✓ 符合規範的附件欄位
  ✓ 審稿報告附錄
```

### 方式 2: 分步驟操作（適合複雜需求）

```bash
# 步驟 1: 分析需求
公文-ai ask-requirements --interactive > 需求.json

# 步驟 2: 搜索相似範例
公文-ai search-examples --requirement 需求.json --top-k 5 > 範例.json

# 步驟 3: 生成骨架
公文-ai generate-skeleton \
  --requirement 需求.json \
  --examples 範例.json > 骨架.md

# 步驟 4: 填充內容
公文-ai generate-content \
  --skeleton 骨架.md \
  --examples 範例.json > 草稿_v0.md

# 步驟 5: 多 Agent 審查
公文-ai review-multi \
  --draft 草稿_v0.md \
  --doc-type 函 \
  --org 臺北市政府 \
  --output 審稿報告.json \
  --final-draft 草稿_final.md

# 步驟 6: 匯出文檔
公文-ai export \
  --draft 草稿_final.md \
  --output 最終稿.docx \
  --format docx
```

### 方式 3: Unix 管道組合（進階用戶）

```bash
# 使用管道組合命令
cat 需求.txt | \
  公文-ai ask-requirements --json | \
  公文-ai search-examples --top-k 10 | \
  公文-ai generate-skeleton | \
  公文-ai generate-content | \
  公文-ai review-multi --doc-type 函 | \
  公文-ai export --format docx > 最終稿.docx
```

---

## 第五步：使用 Claude Code + Gemini CLI 協作

### 在 Claude Code 中開發

```bash
# Claude Code：編寫新功能
# 例如：實現新的 Agent

# 完成代碼後，調用 Gemini CLI 進行代碼審查
gemini analyze-code-quality \
  --files "src/agents/new_agent.py" \
  --report review_new_agent.json

# Claude Code：根據建議改進代碼
# ...編輯代碼...

# 驗證改進
pytest tests/test_new_agent.py -v
```

### Gemini CLI 在不同開發階段的使用

```bash
# Phase 0: 架構設計審查
gemini review-architecture --codebase src/ --output phase0_review.json

# Phase 1: 代碼品質檢查
gemini analyze-code-quality --files "src/agents/**/*.py" --report phase1_quality.json

# Phase 2: 並行設計驗證
gemini review-architecture --codebase src/ --focus "concurrency" --output phase2_review.json

# Phase 3-4: 最終全局審查
gemini analyze-codebase src/ --detailed --output final_review.json
```

詳見 `COLLABORATION_GUIDE.md`。

---

## 第六步：測試與驗證

### 運行測試

```bash
# 單元測試
pytest tests/unit/ -v

# 集成測試
pytest tests/integration/ -v

# 性能基準測試
pytest tests/performance/ -v --benchmark

# 全部測試
pytest tests/ -v
```

### 驗證公文生成質量

```bash
# 使用測試數據生成公文
公文-ai generate \
  --input tests/fixtures/sample_requirement.txt \
  --output test_output.docx

# 手動檢查輸出
# ✓ 檢查主旨格式是否正確
# ✓ 檢查說明段落結構
# ✓ 檢查附件欄位
# ✓ 檢查審稿報告內容
```

---

## 第七步：日常開發工作流

### 典型的一天

```
上午:
  □ 啟動 Claude Code
  □ 根據計劃實現新功能
  □ 運行本地測試驗證

中午:
  □ 完成功能後，保存代碼

下午:
  □ 調用 Gemini CLI 進行代碼審查
  □ 根據審查結果改進代碼
  □ 運行集成測試
  □ 準備下一個 Phase

周末:
  □ 運行全套測試
  □ 進行性能優化分析
  □ 更新知識庫
  □ 準備周一的工作計劃
```

### 推薦的開發時間安排

| 活動 | 耗時 | 頻率 |
|------|------|------|
| Claude Code 編碼 | 2-4 hrs | 每天 |
| 本地單元測試 | 0.5-1 hr | 每天 |
| Gemini CLI 審查 | 0.5-1 hr | 2-3 天一次 |
| 集成測試 | 1-2 hrs | 1 次/week |
| 性能優化 | 1-2 hrs | 1-2 次/month |

---

## 第八步：常見任務速查

### 添加新的公文類型

```bash
# 1. Claude Code：創建新的模板
# 編輯 src/templates/{新公文類型}.md

# 2. Claude Code：添加解析邏輯
# 編輯 src/document_type_handler.py

# 3. Gemini CLI：架構審查
gemini review-architecture --codebase src/ --output doctype_review.json

# 4. Claude Code：改進設計
# 根據審查結果調整...

# 5. 測試
pytest tests/test_new_doctype.py -v
```

### 優化知識庫檢索

```bash
# 1. Claude Code：分析當前檢索性能
python scripts/benchmark_kb_retrieval.py

# 2. Gemini CLI：優化建議
gemini optimize-code --codebase src/ --focus "vector-search" --output kb_optimization.json

# 3. Claude Code：實施優化
# 修改 src/knowledge_base/retriever.py

# 4. 驗證改進
python scripts/benchmark_kb_retrieval.py  # 應該看到性能提升
```

### 添加新機關的詞庫

```bash
# 1. Claude Code：建立新機關詞庫文件
# 編輯 kb_data/terminology/新機關.yaml

# 2. Claude Code：在系統中配置
# 編輯 src/config.yaml，添加新機關引用

# 3. 測試新機關設置
公文-ai generate \
  --input test_input.txt \
  --org 新機關名稱 \
  --output test_output.docx

# 4. 驗證文風匹配
# 手動檢查生成的公文是否符合機關用語風格
```

---

## 第九步：故障排查

### 常見問題

| 問題 | 原因 | 解決方案 |
|------|------|--------|
| 公文-ai 命令不找到 | 未正確安裝或激活虛擬環境 | 確保 pip install 完成，虛擬環境已激活 |
| 知識庫查詢很慢 | 向量索引未優化 | 運行 `公文-ai update-kb --optimize` |
| LLM 返回內容不穩定 | 溫度設置過高 | 在配置中調整 llm.temperature（推薦 0.3） |
| Word 轉換格式錯亂 | 樣板文件損壞 | 重置樣板：`公文-ai config reset-templates` |
| 多 Agent 審查超時 | Agent 響應慢或網絡問題 | 增加超時時限：`公文-ai config set agent.timeout 30` |

### 調試模式

```bash
# 啟用詳細日誌
公文-ai generate --debug --verbose \
  --input 需求.txt \
  --output 最終稿.docx

# 這會輸出每個 Agent 的詳細執行過程
```

---

## 第十步：後續資源

### 深入學習

- **架構設計**: 閱讀 `plan.md` 第 1-3 章
- **協作工作流**: 閱讀 `COLLABORATION_GUIDE.md`
- **API 文檔**: 見 `docs/api.md`
- **配置選項**: 見 `docs/config.md`
- **源代碼**: `src/` 目錄

### 獲取幫助

```bash
# 查看完整幫助
公文-ai --help

# 查看特定命令幫助
公文-ai generate --help
公文-ai review-multi --help

# 查看配置幫助
公文-ai config --help
```

### 報告問題

如遇到問題，請提供：
```
1. 完整的命令和輸出
2. 配置信息（公文-ai config show）
3. 系統信息（OS、Python 版本）
4. 知識庫狀態（公文-ai kb-info）
```

---

## 檢查清單：第一次使用

- [ ] 已安裝 Python 3.11+
- [ ] 已克隆項目並進入目錄
- [ ] 已創建虛擬環境並激活
- [ ] 已運行 `pip install -r requirements.txt`
- [ ] 已運行 `公文-ai init-kb`
- [ ] 已配置 LLM 後端（Ollama 或 Gemini）
- [ ] 已運行 `公文-ai --version` 驗證安裝
- [ ] 已使用示例運行 `公文-ai generate`
- [ ] 已檢查生成的公文格式
- [ ] 已閱讀 `COLLABORATION_GUIDE.md`

✅ 完成上述步驟後，您就可以開始開發了！

---

**Next Steps**:
1. 選擇一個簡單的任務開始開發
2. 適時調用 Gemini CLI 進行代碼審查
3. 參考 `plan.md` 的開發階段進度

**Need Help?** 查看 `COLLABORATION_GUIDE.md` 或項目的 GitHub Issues

**Last Updated**: 2025-11-26
