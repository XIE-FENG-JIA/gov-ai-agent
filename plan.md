# 真實公文 AI Agent 系統 - 實施計劃

**版本**: v1.0
**日期**: 2025-11-26
**模式**: CLI-First 架構（組合式工具鏈）
**目標**: MVP 支援「函、公告、簽」三種公文類型

---

## 0. 技術架構概覽

### 系統設計原則
- **Claude Code + Gemini CLI 協作**: Claude Code 作為交互層和協調者，Gemini CLI 進行大規模代碼分析和戰略規劃
- **CLI-First**: 所有功能通過命令行暴露，支援 Unix 管道組合
- **模塊化 Agent**: 每個專責 Agent 獨立運行，通過 JSON/Markdown 通訊
- **本地優先**: 知識庫、模型、配置都優先使用本地資源
- **零 API 調用成本**: Gemini CLI 用於戰略規劃，Claude Code 用於實施和交互

### 核心技術棧

| 組件 | 技術選型 | 說明 |
|------|--------|------|
| **CLI 框架** | Python 3.11+ + Click/Typer | 輕量級、跨平台、易擴展 |
| **LLM 後端** | Ollama（本地）+ Gemini API（通過 Claude Code 調用） | 靈活配置，支援離線模式 |
| **知識庫** | SQLite + Chroma（向量化） | 輕量級、易部署、支援本地 RAG |
| **異步執行** | asyncio + concurrent.futures | 並行 Agent 審查 |
| **文檔處理** | python-docx + markdown | 支援 .docx 和純文本 |
| **配置管理** | YAML（本地配置文件） | 方便機關自訂 |
| **協作工作流** | Claude Code + Gemini CLI | Claude 交互，Gemini 大規模分析 |

### Claude Code + Gemini CLI 協作架構

```
User Request
    ↓
Claude Code (交互層)
    ├─ 解析用戶需求
    ├─ 調用 CLI 命令執行具體任務
    └─ 收集結果並展示

    ↓ (複雜分析任務)

Gemini CLI (戰略層)
    ├─ 大規模代碼分析 (1M tokens)
    ├─ 架構審查與優化建議
    ├─ 設計驗證與風險評估
    └─ 返回結構化建議

    ↓ (反饋循環)

Claude Code 實施
    ├─ 根據 Gemini 建議改進代碼
    ├─ 執行更新後的 CLI 命令
    └─ 驗證結果
```

---

## 0.1 Claude Code + Gemini CLI 協作工作流

### 協作模式詳解

#### 角色分工

| 工具 | 角色 | 職責 |
|------|------|------|
| **Claude Code** | 交互層 & 實施層 | • 與使用者對話<br>• 調用 CLI 命令<br>• 編寫和修改代碼<br>• 執行實時測試<br>• 呈現結果 |
| **Gemini CLI** | 戰略層 & 審查層 | • 大規模代碼分析<br>• 架構設計審查<br>• 最佳實踐建議<br>• 風險評估<br>• 全局優化方案 |

#### 典型協作場景

**場景 1: 實施新功能（Requirement → Implementation）**

```
User: "實現需求理解 Agent"
  ↓
Claude Code:
  1. 解析需求，確認設計規格
  2. 生成代碼框架
  3. 實現核心邏輯

  需要複雜設計？→ 調用 Gemini CLI

Gemini CLI:
  1. 分析現有 Agent 架構 (1M tokens)
  2. 評估新 Agent 與系統的整合方式
  3. 提出優化建議（並行度、超時處理、錯誤恢復）
  4. 返回結構化設計文檔

Claude Code:
  1. 根據 Gemini 建議調整設計
  2. 完成代碼實現
  3. 執行集成測試
  4. 更新文檔
```

**場景 2: 代碼審查與最佳實踐（Quality Assurance）**

```
Claude Code:
  1. 完成功能實現
  2. 執行單元測試

  需要全局代碼審查？→ 調用 Gemini CLI

Gemini CLI:
  1. 掃描整個項目代碼 (1M tokens)
  2. 檢查代碼品質、性能、安全性
  3. 提出重構建議
  4. 識別技術債
  5. 生成審查報告

Claude Code:
  1. 根據審查報告進行改進
  2. 優化性能瓶頸
  3. 修復潛在問題
  4. 執行回歸測試
```

**場景 3: 大規模知識庫集成（Knowledge Base Management）**

```
Claude Code:
  1. 準備爬取政府網站的腳本
  2. 處理爬取到的公文數據

  需要大規模數據分析？→ 調用 Gemini CLI

Gemini CLI:
  1. 分析數千份公文範例 (1M tokens)
  2. 提取通用模板和模式
  3. 識別機關差異化特徵
  4. 生成向量化索引優化方案
  5. 推薦詞庫分類結構

Claude Code:
  1. 實現 Gemini 推薦的數據結構
  2. 構建優化後的向量索引
  3. 驗證檢索準確率
```

#### 調用 Gemini CLI 的時機

✅ **應該使用 Gemini CLI 的場景**:
- 需要分析 > 100 個源文件的代碼
- 進行大規模架構設計或重構
- 評估新功能對整個系統的影響
- 優化性能或資源使用
- 安全性和合規性審查
- 知識庫質量分析和優化
- 批量數據處理和分析

❌ **不需要使用 Gemini CLI 的場景**:
- 編寫單個 Agent 或功能模塊
- 修複小規模 Bug
- 添加簡單配置
- 實時交互測試
- 單個文件的快速編輯

### 協作命令模式

#### 在 Claude Code 中調用 Gemini CLI

```bash
# 1. 大規模代碼分析
gemini analyze-codebase "src/" --detailed --output analysis.json

# 2. 架構審查
gemini review-architecture --codebase src/ --output architecture_review.md

# 3. 代碼品質檢查
gemini analyze-code-quality --files "src/**/*.py" --report quality_report.json

# 4. 性能優化建議
gemini optimize-code --codebase src/ --focus performance --output optimizations.md

# 5. 安全性審計
gemini audit-security --codebase src/ --output security_report.md

# 6. 重構規劃
gemini suggest-refactoring --codebase src/ --output refactor_plan.md

# 7. 知識庫分析（自定義）
gemini analyze-codebase "kb_data/" --focus "data-structure,patterns" --output kb_analysis.json
```

#### Claude Code 與 Gemini 的通訊格式

**Claude Code 發送給 Gemini**:
```json
{
  "task": "analyze_knowledge_base",
  "codebase_path": "src/",
  "focus_areas": [
    "agent_architecture",
    "llm_provider_abstraction",
    "async_patterns"
  ],
  "output_format": "structured_recommendations"
}
```

**Gemini 返回給 Claude Code**:
```json
{
  "analysis_id": "gemin_20250101_001",
  "summary": "系統架構良好，但 Agent 通訊方式可優化",
  "recommendations": [
    {
      "category": "Architecture",
      "priority": "high",
      "suggestion": "實現統一的 Agent 消息隊列",
      "impact": "提升系統可擴展性和可維護性"
    },
    {
      "category": "Performance",
      "priority": "medium",
      "suggestion": "優化向量化索引的查詢速度",
      "impact": "減少響應延遲 20-30%"
    }
  ],
  "estimated_effort": "3-5 days"
}
```

---

## 1. 核心 Agent 設計

### Agent 角色與職責

#### 1.1 需求理解 Agent (Requirement Analyzer)
**輸入**: 用戶自然語言描述
**輸出**: 結構化公文需求規格（JSON）
**職責**:
- 通過對話式問答引導用戶明確需求
- 確定公文類型、發文機關、收文對象、案由、依據、附件等
- 生成標準化的「公文需求表單」

**技術實現**:
```python
# 偽代碼
def analyze_requirements(user_input: str) -> PublicDocRequirement:
    # 使用 LLM 進行多輪對話
    # 每輪提取一個字段，直到完整
    # 輸出 JSON 格式的需求規格
```

#### 1.2 範例檢索 Agent (Example Retriever)
**輸入**: 公文需求規格（JSON）
**輸出**: 相似公文範例清單 + 推薦的 3 篇核心範例
**職責**:
- 從本地知識庫與在線來源檢索相似公文
- 使用 RAG（向量化檢索）找出最相關的範例
- 標註每篇範例的機關、日期、類型、相似度

**技術實現**:
```python
def search_examples(requirement: PublicDocRequirement) -> List[PublicDocExample]:
    # 1. 將需求轉換為檢索查詢
    query = build_search_query(requirement)

    # 2. 本地向量搜索（Chroma）
    local_results = vector_db.search(query, k=10)

    # 3. 可選：在線爬取政府網站
    if config.enable_online_search:
        online_results = scrape_gov_websites(query)

    # 4. 合併與排序
    return rank_and_select_examples(local_results + online_results)
```

#### 1.3 模板與骨架生成 Agent (Template Generator)
**輸入**: 公文需求規格 + 選定的參考範例
**輸出**: 公文骨架（Markdown 格式）
**職責**:
- 根據公文類型選用合適模板
- 填入必要欄位框架（主旨、說明、附件、發文字號等）
- 預埋必要的格式標記（用於後續 Word 轉換）

**公文模板結構**:
```markdown
# [公文類型] - [發文機關]

## 頭部信息
- 發文字號: [自動生成或待填]
- 發文日期: [YYYY-MM-DD]
- 密等: 普通
- 速別: [一般/急件/最速件]

## 正文
### 主旨
[主旨內容]

### 說明
1. [說明第一點]
2. [說明第二點]
...

### 辦法
[辦理方式或要點]

### 附件
- [附件1]
- [附件2]

## 承辦資訊
- 簽名欄位
- 機關戳記
```

#### 1.4 內容草稿生成 Agent (Content Generator)
**輸入**: 公文骨架 + 參考範例 + 機關詞庫
**輸出**: 完整草稿（Markdown）
**職責**:
- 在骨架上填入實際內容
- 模仿參考範例的文風與措辭
- 自動引用法規條文與相關依據
- 生成內容時保持邏輯連貫與格式一致

**實現要點**:
```python
def generate_content(skeleton: str, examples: List[str], style_guide: str) -> str:
    # 1. 使用 Few-shot 提示，讓 LLM 模仿範例風格
    prompt = build_prompt(skeleton, examples, style_guide)

    # 2. 調用 LLM（本地或 API）
    draft = llm.generate(prompt, temperature=0.3)  # 低溫度保證一致性

    # 3. 嵌入來源追蹤信息
    draft_with_sources = add_source_markers(draft, examples)

    return draft_with_sources
```

### 1.5 並行審查 Agent（核心創新）

多個專責 Agent **同時** 審查 v0 草稿，返回結構化審查意見：

#### 1.5.1 格式稽核 Agent (Format Auditor)
**檢查項目**:
- ✓ 欄位完整性（主旨、說明、附件、速別、密等等）
- ✓ 條列序號與層級是否符合《文書處理手冊》
- ✓ 主旨字數限制（通常 ≤ 100 字）
- ✓ 是否包含必要的公文要素

**輸出**:
```json
{
  "agent": "format_auditor",
  "issues": [
    {
      "severity": "error",
      "location": "主旨",
      "problem": "主旨超過 100 字",
      "suggestion": "建議縮短為：[建議文本]"
    }
  ],
  "score": 0.85
}
```

#### 1.5.2 文風與用語 Agent (Language Checker)
**檢查項目**:
- ✓ 是否使用正式公文用語
- ✓ 是否出現口語、情感化字眼
- ✓ 程度副詞（應、得、不得）使用是否恰當
- ✓ 是否符合指定機關的慣用文風

**輸出**:
```json
{
  "agent": "language_checker",
  "issues": [
    {
      "location": "說明第2點",
      "problem": "使用口語『超級好用』",
      "suggestion": "改為：相當便利或更具成效"
    }
  ],
  "style_match_score": 0.78
}
```

#### 1.5.3 事實與法規檢查 Agent (Fact Checker)
**檢查項目**:
- ✓ 引用的法條是否存在且未過期
- ✓ 提及的機構名稱、職稱是否正確
- ✓ 日期、金額、數字是否合理
- ✓ 標出可能有風險的敘述

**輸出**:
```json
{
  "agent": "fact_checker",
  "risks": [
    {
      "location": "說明第1點",
      "risk": "引用『文書處理手冊第5章』，但該章節已於2023年修正",
      "action": "建議更新參考版本或確認內容仍適用",
      "severity": "warning"
    }
  ],
  "confidence": 0.82
}
```

#### 1.5.4 一致性與邏輯 Agent (Consistency Checker)
**檢查項目**:
- ✓ 主旨、說明、辦法三者邏輯是否一致
- ✓ 同一內容在文中是否有矛盾
- ✓ 程序順序是否正確
- ✓ 承諾與交付是否一致

**輸出**:
```json
{
  "agent": "consistency_checker",
  "issues": [
    {
      "problem": "主旨提到『補助 500 萬元』，但說明第3點寫『最多 300 萬』",
      "suggestion": "統一補助額度"
    }
  ]
}
```

#### 1.5.5 總編 Agent (Editor-in-Chief)
**職責**:
- 收集上述 4 個 Agent 的審查意見
- 根據優先級（Error > Warning > Info）進行修訂
- 生成最終草稿 v_final
- 生成「審核報告」，記錄每項修改的理由與來源 Agent

**實現流程**:
```python
async def multi_agent_review(draft_v0: str) -> Tuple[str, ReviewReport]:
    # 1. 並行調用 4 個審查 Agent
    results = await asyncio.gather(
        format_auditor_review(draft_v0),
        language_checker_review(draft_v0),
        fact_checker_review(draft_v0),
        consistency_checker_review(draft_v0)
    )

    # 2. 合併審查意見（按優先級排序）
    merged_issues = merge_review_results(results)

    # 3. 使用 LLM 生成修訂建議
    draft_v_final = apply_revisions(draft_v0, merged_issues)

    # 4. 生成審核報告
    report = generate_review_report(merged_issues, draft_v0, draft_v_final)

    return draft_v_final, report
```

---

## 2. CLI 命令架構

### 設計原則
- **一鍵生成**: `公文-ai generate` 執行完整流程
- **模塊化調用**: 支援分步驟調用，結合 Unix 管道
- **JSON 作為中間格式**: 各步驟之間通過 JSON 通訊

### 完整命令集

```bash
# ============ 主要命令：一鍵生成 ============
公文-ai generate \
  --input 需求.txt \
  --output 草稿.docx \
  --doc-type 函 \
  --org 臺北市政府 \
  --verbose

# ============ 分步驟命令 ============

# 1. 分析需求
公文-ai ask-requirements --interactive

# 2. 搜索範例
公文-ai search-examples --requirement 需求.json --top-k 5

# 3. 生成骨架
公文-ai generate-skeleton --requirement 需求.json --examples 範例.json

# 4. 填充內容
公文-ai generate-content --skeleton 骨架.md --examples 範例.json

# 5. 多 Agent 審查
公文-ai review-multi --draft 草稿.md --doc-type 函 --org 臺北市政府

# 6. 匯出文檔
公文-ai export --draft 草稿.md --output 草稿.docx --format docx

# ============ 輔助命令 ============

# 初始化本地知識庫
公文-ai init-kb --source local --path ./kb_data

# 配置 LLM 後端
公文-ai config set llm.provider ollama
公文-ai config set llm.model mistral-7b

# 查看配置
公文-ai config show

# 更新知識庫
公文-ai update-kb --online-sync

# 幫助與版本
公文-ai --help
公文-ai --version
```

### 命令的組合使用方式

```bash
# 方式 1: 純管道組合（Unix 哲學）
cat 需求.txt | 公文-ai ask-requirements --json \
  | 公文-ai search-examples --top-k 10 \
  | 公文-ai generate-skeleton \
  | 公文-ai generate-content \
  | 公文-ai review-multi --doc-type 函 \
  | 公文-ai export --format docx > 最終稿.docx

# 方式 2: 中間結果保存
公文-ai ask-requirements --input 需求.txt --output 需求.json
公文-ai search-examples --requirement 需求.json --output 範例.json
公文-ai generate-skeleton --requirement 需求.json --examples 範例.json --output 骨架.md
公文-ai generate-content --skeleton 骨架.md --examples 範例.json --output 草稿_v0.md
公文-ai review-multi --draft 草稿_v0.md --output 審稿報告.json --final-draft 草稿_final.md
公文-ai export --draft 草稿_final.md --output 最終稿.docx
```

---

## 3. 數據模型與契約定義

### 3.1 核心數據結構

#### PublicDocRequirement（公文需求規格）
```json
{
  "id": "req_20250101_001",
  "created_at": "2025-01-01T10:00:00Z",
  "doc_type": "函",  // 函、公告、簽、報告、開會通知單
  "urgency": "一般",  // 一般、急件、最速件
  "classification": "普通",  // 普通、機密(X密)

  // 發送方信息
  "sending_agency": "臺北市政府民政局",
  "sender_title": "局長",
  "sender_name": "王小明",

  // 接收方信息
  "recipient_agency": "各區公所",
  "recipient_type": "機關",  // 機關、民眾、企業

  // 內容要點
  "subject": "函轉行政院…會議決議",
  "reason": "為配合推動…計畫",
  "basis": [
    {
      "type": "law",
      "name": "文書處理手冊",
      "article": "第2章"
    },
    {
      "type": "order",
      "name": "行政院 2024 年度政策",
      "reference": "公告編號 0001"
    }
  ],

  // 相關資訊
  "related_cases": ["案號001", "案號002"],
  "attachments": ["附件1_清單.xlsx", "附件2_規定.pdf"],
  "action_items": [
    "轉知各區公所辦理",
    "請於 2025-02-28 前回報執行情況"
  ],

  // 額外需求
  "special_requirements": "請按機關慣例填寫簽核欄位",
  "reference_style": "臺北市政府"
}
```

#### PublicDocExample（公文範例）
```json
{
  "id": "example_20250101_001",
  "title": "函轉教育部…會議決議",
  "source_url": "https://www.taipei.gov.tw/...",
  "source_agency": "臺北市政府",
  "issue_date": "2024-12-15",
  "doc_type": "函",
  "doc_number": "府民字第 1234567 號",

  // 完整公文內容
  "content": "---\n主旨：函轉教育部...\n說明：...",

  // 結構化提取
  "structure": {
    "subject": "函轉教育部…會議決議",
    "body_points": ["第一點...", "第二點..."],
    "measures": "請遵照辦理",
    "attachments": []
  },

  // 風格指標
  "style_features": {
    "word_count": 450,
    "formal_score": 0.95,
    "terminology": ["函轉", "配合", "惠請"]
  },

  // 相似度評分
  "similarity_to_requirement": 0.87
}
```

#### PublicDocSkeleton（公文骨架）
```markdown
# 函 - 臺北市政府民政局

## 頭部
- 發文字號: 府民字第 ______ 號
- 發文日期: 2025-01-XX
- 密等: 普通
- 速別: 一般

## 公文內容

### 主旨
[待填充]

### 說明
1. [說明第一點]
2. [說明第二點]
3. [說明第三點]

### 辦法
[待填充]

### 附件
- [附件1]
- [附件2]

---

## 格式備註
- [格式標記：本文使用黑體、12pt、行距固定20pt]
- [標題使用明體、14pt、粗體]
```

#### ReviewReport（審稿報告）
```json
{
  "report_id": "review_20250101_001",
  "timestamp": "2025-01-01T10:30:00Z",
  "draft_version": "v0",

  "format_audit": {
    "status": "warning",
    "issues": [
      {
        "severity": "error",
        "item": "主旨",
        "problem": "超過字數限制",
        "original": "函轉行政院…會議決議及相關要點…",
        "suggestion": "函轉行政院會議決議"
      }
    ]
  },

  "language_check": {
    "status": "pass",
    "issues": [],
    "style_score": 0.92
  },

  "fact_check": {
    "status": "warning",
    "issues": [
      {
        "location": "說明第2點",
        "risk_level": "warning",
        "problem": "引用『文書處理手冊 2023 版』，但未確認是否為最新版本",
        "suggestion": "建議確認版本號"
      }
    ]
  },

  "consistency_check": {
    "status": "pass",
    "issues": []
  },

  // 整合結果
  "overall_status": "ready_with_minor_fixes",
  "overall_score": 0.89,
  "recommended_fixes": [
    "修正主旨字數",
    "確認法規版本"
  ]
}
```

---

## 4. 知識庫建構方案

### 4.1 本地知識庫結構

```
./kb_data/
├── templates/                 # 公文模板庫
│   ├── 函.md
│   ├── 公告.md
│   ├── 簽.md
│   ├── 報告.md
│   └── 開會通知單.md
│
├── examples/                  # 真實公文範例
│   ├── 函/
│   │   ├── example_001.md
│   │   ├── example_002.md
│   │   └── ...
│   ├── 公告/
│   └── 簽/
│
├── regulations/               # 法規與規範
│   ├── 文書處理手冊.md
│   ├── 政府文書格式參考規範.md
│   └── 相關法律條文.db
│
├── terminology/               # 機關詞庫
│   ├── 通用詞庫.yaml
│   ├── 臺北市政府.yaml
│   ├── 經濟部.yaml
│   └── ...
│
├── embeddings/                # 向量化索引
│   ├── examples.chroma/       # Chroma 向量數據庫
│   ├── templates.chroma/
│   └── regulations.chroma/
│
└── metadata.json              # 知識庫元數據
```

### 4.2 初始化與更新流程

#### 初始化（首次運行）
```bash
公文-ai init-kb \
  --mode hybrid \
  --local-seed ./initial_data \
  --enable-online-sync \
  --gov-sites "ndc.gov.tw,taipei.gov.tw,bsmi.gov.tw"
```

**實現步驟**:
1. 複製預置種子數據到本地
2. 構建向量索引（使用 Chroma）
3. 可選：爬取指定政府網站的公文範本
4. 生成元數據檔案（版本、更新時間等）

#### 定期更新
```bash
# 手動更新
公文-ai update-kb --online-sync

# 自動定期更新（通過 cron 或系統任務排程）
# 每週一上午 02:00 執行更新
0 2 * * 1 公文-ai update-kb --online-sync --background
```

### 4.3 向量化索引設計

使用 **Chroma** 作為輕量級向量數據庫：

```python
from chroma_client import Client

# 初始化 Chroma
client = Client()
examples_collection = client.get_or_create_collection(
    name="public_doc_examples",
    metadata={"hnsw:space": "cosine"}
)

# 添加公文範例到索引
for example in examples:
    examples_collection.add(
        ids=[example.id],
        embeddings=[embed_text(example.content)],  # 使用本地模型或 API
        documents=[example.content],
        metadatas=[{
            "doc_type": example.doc_type,
            "agency": example.source_agency,
            "date": example.issue_date,
            "similarity_score": example.similarity_to_requirement
        }]
    )

# 檢索相似文檔
results = examples_collection.query(
    query_embeddings=[embed_text(search_query)],
    n_results=10
)
```

### 4.4 機關詞庫管理

```yaml
# 臺北市政府.yaml
---
agency_name: "臺北市政府"
formal_terms:
  - ["好用", "便利高效"]
  - ["超好", "相當優良"]
  - ["如上", "如前述"]

common_phrases:
  - "函轉行政院…會議決議"
  - "配合上級指示"
  - "惠請參考辦理"

forbidden_words:
  - "超級"
  - "超棒"
  - "咱們"

abbreviations:
  - ["民政局": "民政局"]
  - ["環保局": "環境保護局"]

style_guidelines:
  formal_score: 0.95
  formality_level: "高度正式"
  recommended_tone: "穩重、規范、專業"
```

---

## 5. 開發階段與里程碑

### Phase 0: 基礎設施搭建（週 1-2）

**成果物**:
- [ ] 項目骨架與依賴管理
- [ ] CLI 框架搭建（Click/Typer）
- [ ] LLM 後端適配層（支援 Ollama + Gemini API）
- [ ] 基礎配置管理系統
- [ ] 單元測試框架
- [ ] Gemini CLI 集成接口

**關鍵任務**:
```
1. 初始化 Python 項目，配置 pyproject.toml
2. 實現 LLM 提供者抽象層（Provider Interface）
   - 本地 Ollama 支援
   - Gemini API 支援（通過 Claude Code 調用）
3. 開發配置讀寫模塊
4. 編寫基礎 CLI 命令框架
5. 創建 Mock LLM 用於離線開發測試
6. 實現 Gemini CLI 調用接口（JSON 輸入輸出）

✨ Gemini CLI 應用場景:
   → 架構設計審查（確保 Agent 設計合理）
```

### Phase 1: 核心 Agent 實現（週 3-6）

**成果物**:
- [ ] 需求理解 Agent
- [ ] 範例檢索 Agent + 本地知識庫初版
- [ ] 模板與骨架生成 Agent
- [ ] 內容草稿生成 Agent
- [ ] 集成測試與範例測試

**關鍵任務**:
```
1. 實現公文需求規格的數據模型與驗證
2. 開發多輪對話邏輯（需求 Agent）
3. 構建本地知識庫（種子數據 + 向量索引）
4. 實現 RAG 檢索邏輯
5. 設計與實現公文模板庫
6. 開發內容生成 Agent（使用 Few-shot 提示）
7. 端對端測試（從需求到初稿）

✨ Gemini CLI 應用場景:
   → 代碼品質檢查（確保 Agent 實現符合最佳實踐）
   → 性能優化分析（向量索引和 RAG 效率）
```

### Phase 2: 多 Agent 審查機制（週 7-10）

**成果物**:
- [ ] 格式稽核 Agent
- [ ] 文風與用語檢查 Agent
- [ ] 事實與法規檢查 Agent
- [ ] 一致性檢查 Agent
- [ ] 總編 Agent + 審核報告生成
- [ ] 並行審查框架與優化

**關鍵任務**:
```
1. 實現 4 個專責審查 Agent
2. 開發並行執行框架（asyncio）
3. 設計審查意見的合併與優先級排序算法
4. 實現修訂建議應用邏輯
5. 生成結構化審核報告
6. 性能測試與優化（並行度、超時處理）
7. 用戶體驗測試（報告清晰度）

✨ Gemini CLI 應用場景:
   → 架構審查（確保並行審查設計可靠）
   → 性能基準測試（多 Agent 並行度優化）
```

### Phase 3: 輸出與匯出（週 11-12）

**成果物**:
- [ ] Word (.docx) 匯出模塊
- [ ] 純文本 (.txt) 匯出模塊
- [ ] PDF 預覽（可選）
- [ ] 樣板應用系統

**關鍵任務**:
```
1. 實現 Markdown 轉 Word 轉換器
   - 標題、正文、表格、列表格式化
   - 分頁符、頁邊距、字體設置
2. 機關樣板管理與應用
3. 支援自訂頁眉、頁腳、印章位置
4. 匯出質量測試

✨ Gemini CLI 應用場景:
   → 代碼審查（Word 轉換邏輯的正確性）
```

### Phase 4: CLI 集成與測試（週 13）

**成果物**:
- [ ] 完整 CLI 命令集
- [ ] 分步驟與一鍵生成流程
- [ ] 管道化使用支援
- [ ] 完整文檔與使用示例

**關鍵任務**:
```
1. 設計 CLI 命令架構
2. 實現一鍵生成流程（generate 命令）
3. 支援分步驟調用與管道組合
4. 集成測試覆蓋主要使用場景
5. 編寫用戶文檔與示例
6. 性能基準測試

✨ Gemini CLI 應用場景:
   → 全局代碼審查（整個 CLI 系統的一致性）
   → 集成測試分析（所有命令流的正確性）
```

### Phase 5: MVP 試運行與迭代（週 14+）

**成果物**:
- [ ] 與試用機關的合作測試
- [ ] 反饋收集與優化
- [ ] 生產環境部署指南

**關鍵任務**:
```
1. 部署到試用環境
2. 真實公文案例測試
3. 收集試用機關反饋
4. 迭代優化 Agent 邏輯
5. 擴展知識庫（新增機關詞庫等）
```

---

## 5.1 Claude Code + Gemini CLI 開發工作流詳解

### 每個階段的協作模式

#### Phase 0 開發工作流

```
Claude Code 開發者:
  1. 初始化項目結構
  2. 配置 pyproject.toml
  3. 搭建 CLI 框架
  ✓ 完成初版代碼

  需要設計審查？→ 調用 Gemini CLI

Gemini CLI 分析:
  gemini analyze-codebase "src/" \
    --focus "architecture,dependencies" \
    --output phase0_review.json

  返回建議:
  {
    "architecture": {
      "status": "good",
      "suggestions": [
        "LLM Provider 抽象層設計合理",
        "建議添加 async/await 支援"
      ]
    }
  }

Claude Code 調整:
  1. 根據建議改進代碼
  2. 添加異步支援
  3. 完善錯誤處理
```

#### Phase 1 開發工作流

```
Claude Code 開發者:
  1. 實現需求理解 Agent
  2. 實現範例檢索 Agent
  3. 構建知識庫索引
  4. 進行基本測試

  需要代碼品質檢查？→ 調用 Gemini CLI

Gemini CLI 分析:
  gemini analyze-code-quality \
    --files "src/agents/**/*.py" \
    --report quality_phase1.json

  1M tokens 級別的詳細分析:
  - 代碼複雜度
  - 性能瓶頸（特別是向量檢索）
  - 測試覆蓋率
  - 文檔完整性

Claude Code 優化:
  1. 優化向量檢索性能
  2. 添加缺失的類型提示
  3. 改進錯誤處理
  4. 增加單元測試
```

#### Phase 2 開發工作流

```
Claude Code 開發者:
  1. 實現 4 個審查 Agent
  2. 構建並行執行框架
  3. 測試 Agent 間通訊
  4. 性能測試

  需要架構驗證？→ 調用 Gemini CLI

Gemini CLI 分析:
  gemini review-architecture \
    --codebase src/ \
    --focus "concurrency,agent-communication" \
    --output phase2_architecture.json

  關鍵分析:
  - 並行度是否最優（目標：4 個 Agent 并行）
  - Agent 間通訊是否可靠
  - 超時處理是否完善
  - 內存效率是否符合目標

Claude Code 優化:
  1. 調整並行策略
  2. 添加監控和日誌
  3. 優化超時處理
  4. 壓力測試驗證
```

### Gemini CLI 命令在各階段的應用速查表

| Phase | 主要 Gemini 命令 | 目的 |
|-------|-----------------|------|
| **Phase 0** | `review-architecture` | 驗證基礎設施設計 |
| **Phase 1** | `analyze-code-quality`, `optimize-code` | 檢查代碼品質和性能 |
| **Phase 2** | `review-architecture`, `audit-security` | 驗證並行設計和錯誤處理 |
| **Phase 3** | `analyze-code-quality` | 檢查文檔轉換邏輯 |
| **Phase 4** | `review-architecture`, `analyze-codebase --detailed` | 全局一致性檢查 |
| **Phase 5** | `audit-security`, `analyze-codebase --detailed` | 生產環境準備檢查 |

---

## 6. 技術細節與關鍵決策

### 6.1 並行 Agent 審查的實現

**問題**: 如何確保多個 Agent 的審查結果可靠、不互相干擾？

**解決方案**:
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

class MultiAgentReviewer:
    def __init__(self, llm_provider):
        self.format_agent = FormatAuditor(llm_provider)
        self.language_agent = LanguageChecker(llm_provider)
        self.fact_agent = FactChecker(llm_provider, kb_client)
        self.consistency_agent = ConsistencyChecker(llm_provider)

    async def review_draft(self, draft: str) -> ReviewReport:
        # 並行執行 4 個審查任務
        tasks = [
            self.format_agent.audit(draft),
            self.language_agent.check(draft),
            self.fact_agent.verify(draft),
            self.consistency_agent.check(draft)
        ]

        results = await asyncio.gather(*tasks)

        # 合併意見
        merged = self._merge_opinions(results)

        # 生成修訂建議
        revisions = self._generate_revisions(draft, merged)

        return revisions

    def _merge_opinions(self, results: List[ReviewResult]) -> Dict:
        """按優先級合併多個 Agent 的審查結果"""
        merged = {
            "errors": [],
            "warnings": [],
            "info": []
        }

        for result in results:
            for issue in result.issues:
                if issue.severity == "error":
                    merged["errors"].append(issue)
                elif issue.severity == "warning":
                    merged["warnings"].append(issue)
                else:
                    merged["info"].append(issue)

        return merged
```

### 6.2 LLM 後端的抽象設計

**目標**: 支援多個 LLM 後端（本地 Ollama、OpenAI API 等），無需修改業務邏輯

**實現**:
```python
from abc import ABC, abstractmethod

class LLMProvider(ABC):
    """LLM 提供者的抽象接口"""

    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> str:
        pass

    @abstractmethod
    async def embed_text(self, text: str) -> List[float]:
        pass

class OllamaProvider(LLMProvider):
    """本地 Ollama 實現"""
    async def generate(self, prompt: str, **kwargs) -> str:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": self.model, "prompt": prompt, ...}
        )
        return response.json()["response"]

class OpenAIProvider(LLMProvider):
    """OpenAI API 實現"""
    async def generate(self, prompt: str, **kwargs) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            ...
        )
        return response.choices[0].message.content

# 使用時根據配置選擇提供者
def get_llm_provider(config: Dict) -> LLMProvider:
    if config["llm"]["provider"] == "ollama":
        return OllamaProvider(model=config["llm"]["model"])
    elif config["llm"]["provider"] == "openai":
        return OpenAIProvider(api_key=config["llm"]["api_key"])
```

### 6.3 向量化索引的更新策略

**挑戰**: 知識庫中的公文與法規可能過時，需要定期更新，但又要保持系統穩定性

**解決方案**:
```python
class KnowledgeBaseManager:
    def __init__(self, kb_path: str):
        self.kb_path = kb_path
        self.chroma_client = Client(persist_directory=kb_path)

    def update_kb(self, online_sync: bool = False):
        """更新知識庫"""

        # 1. 備份舊索引
        backup_path = self._backup_current_index()

        try:
            # 2. 如果啟用在線同步，爬取新範例
            if online_sync:
                new_examples = self._scrape_gov_websites()
                self._add_examples_to_index(new_examples)

            # 3. 重建向量索引
            self._rebuild_embeddings()

            # 4. 驗證索引質量
            if not self._validate_index():
                raise ValueError("索引驗證失敗")

            # 5. 刪除備份
            self._cleanup_backup(backup_path)

        except Exception as e:
            # 失敗時自動回滾
            self._restore_from_backup(backup_path)
            logger.error(f"知識庫更新失敗: {e}")
            raise
```

### 6.4 文檔格式化與樣板應用

**需求**: 將 Markdown 格式的公文轉換為標準 Word 文檔，同時應用機關的樣板設置

**實現**:
```python
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

class DocxExporter:
    def __init__(self, template_path: str = None):
        if template_path:
            self.doc = Document(template_path)
        else:
            self.doc = Document()

    def add_public_doc_content(self, content: str, style_config: Dict):
        """將 Markdown 內容轉換為 Word 文檔格式"""

        # 解析 Markdown
        lines = content.split('\n')

        for line in lines:
            if line.startswith('# '):
                # 標題
                p = self.doc.add_paragraph(line[2:], style='Heading 1')
                self._apply_style(p, style_config['heading1'])

            elif line.startswith('### '):
                # 三級標題
                p = self.doc.add_paragraph(line[4:], style='Heading 3')
                self._apply_style(p, style_config['heading3'])

            elif line.startswith('- '):
                # 列表項
                p = self.doc.add_paragraph(line[2:], style='List Bullet')

            else:
                # 正文
                p = self.doc.add_paragraph(line)
                self._apply_style(p, style_config['normal'])

    def _apply_style(self, paragraph, style_config: Dict):
        """應用文字樣式"""
        for run in paragraph.runs:
            if 'font_name' in style_config:
                run.font.name = style_config['font_name']
            if 'font_size' in style_config:
                run.font.size = Pt(style_config['font_size'])
            if 'bold' in style_config:
                run.font.bold = style_config['bold']

    def save(self, path: str):
        self.doc.save(path)
```

---

## 7. 成功指標與驗收標準

### 功能驗收標準

| 功能模塊 | 驗收標準 |
|---------|--------|
| **需求理解 Agent** | ✓ 能準確提取 80% 以上的關鍵信息（公文類型、機構、案由等）|
| **範例檢索 Agent** | ✓ 檢索精度 > 85%（相關度評分） |
| **模板生成 Agent** | ✓ 生成的骨架符合公文格式要求 100% |
| **內容生成 Agent** | ✓ 生成內容文風評分 > 0.8（與參考範例的相似度） |
| **多 Agent 審查** | ✓ 發現 90% 以上的格式和明顯的文風問題 |
| **匯出模塊** | ✓ Word 文檔格式完整、可編輯，純文本無亂碼 |

### 效能指標

| 指標 | 目標值 | 備註 |
|------|-------|------|
| **單份公文完整流程耗時** | < 60 秒 | 包含所有 5 個 Agent 審查 |
| **並行 Agent 審查加速比** | > 2.5x | 相比順序執行 |
| **知識庫查詢延遲** | < 2 秒 | Top-10 相似文檔 |
| **內存佔用** | < 2GB | 運行完整系統 |
| **模型首次加載時間** | < 30 秒 | Ollama 本地加載 |

### 品質指標

| 指標 | 目標值 |
|------|-------|
| **格式錯誤率** | ≤ 5% |
| **文風一致性評分** | ≥ 0.85 |
| **法規引用誤率** | ≤ 3% |
| **邏輯一致性評分** | ≥ 0.9 |

---

## 8. 風險與應對方案

| 風險 | 概率 | 影響 | 應對方案 |
|------|------|------|--------|
| LLM 幻覺導致法規引用錯誤 | 高 | 高 | 加強 Fact Checker Agent 驗證；提供風險告警機制 |
| 知識庫更新延遲導致信息過時 | 中 | 中 | 實現自動化定期更新；版本控制 |
| 並行 Agent 執行超時 | 中 | 中 | 設置合理超時時限；異步錯誤處理；回退方案 |
| 機關詞庫不完整導致文風不符 | 中 | 中 | 提供詞庫編輯工具；收集用戶反饋迭代 |
| 本地 LLM 性能不足（CPU 環境） | 低 | 中 | 提供 API 後端選項；推薦最低硬體規格 |

---

## 9. 後續擴展與長期規劃

### v1.1 計畫（1-2 個月後）
- [ ] 支援機關自訂模板與詞庫編輯界面
- [ ] 支援更多公文類型（報告、決定書等）
- [ ] 支援公文版本控制與歷史對比
- [ ] 集成更多知識庫來源（各部會網站）

### v2.0 計畫（3-6 個月後）
- [ ] Web UI 界面（保留 CLI 作為核心）
- [ ] 與電子公文系統 API 對接（SPEED 等）
- [ ] 機構性能自訂學習（Fine-tuning）
- [ ] 公文批量處理模式

### 長期願景
- [ ] AI-Agent 團隊自主審查與迭代優化
- [ ] 跨機關公文規範統一與智能建議
- [ ] 公文發文效能統計與優化建議

---

## 10. 部署與運維指南

### 本地開發環境
```bash
# 系統需求
Python 3.11+
4GB RAM (本地 LLM) / 8GB RAM (推薦)
10GB 磁盤空間 (知識庫)

# 依賴安裝
git clone <repo-url>
cd public-doc-ai-agent
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 初始化知識庫
python -m public_doc_ai init-kb --mode hybrid

# 配置 LLM 後端
公文-ai config set llm.provider ollama
公文-ai config set llm.model mistral-7b

# 運行測試
pytest tests/ -v

# 啟動本地開發服務
公文-ai --help
```

### 機構部署
1. 提供 Docker 容器化部署
2. 支援本地知識庫初始化與備份
3. 提供運維文檔與故障排查指南

---

