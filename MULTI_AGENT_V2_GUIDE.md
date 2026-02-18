# Multi-Agent 架構 2.0 強化功能

## 📚 概述

公文 AI Agent 已升級至 **Multi-Agent 2.0**，新增三大核心功能：

### ✨ 新增功能

1. **法規合規與政策一致性 Agent** (`ComplianceChecker`)
   - 檢查公文是否符合最新政策方針
   - 識別過時或不當的政策術語
   - 基於知識庫的智慧審查

2. **加權品質評分系統** (Weighted QA System)
   - 不同類別錯誤有不同權重
   - 更精準的風險評估
   - 優先處理高影響問題

3. **機構記憶 Agent** (`OrganizationalMemory`)
   - 學習各機關的使用偏好
   - 記錄常用詞彙和格式習慣
   - 自動套用機關特定風格

---

## 🎯 功能詳解

### 1. ComplianceChecker - 政策合規審查

**職責**：
- 檢查公文內容是否抵觸最新施政方針
- 驗證用詞是否符合當前政策風向
- 識別可能的政策不一致問題

**運作方式**：
```python
from src.agents.compliance_checker import ComplianceChecker

checker = ComplianceChecker(llm, kb_manager)
result = checker.check(draft_text)

# 輸出：ReviewResult
# - issues: 合規性問題列表
# - score: 合規分數 (0.0-1.0)
# - confidence: 信心度
```

**檢查項目**：
- ✅ 是否符合「淨零碳排」政策
- ✅ 是否遵循「資安即國安」原則
- ✅ 是否使用過時的政策術語
- ✅ 是否與上級機關方針一致

**範例**：
```markdown
# 錯誤案例
主旨：為推動垃圾焚化政策，擬增設焚化爐...

❌ Compliance Issue:
- 嚴重性: error
- 位置: 主旨
- 問題: 與「淨零轉型」、「循環經濟」政策方向不一致
- 建議: 改為推動「資源回收再利用」或「廢棄物減量」
```

---

### 2. Weighted QA System - 加權評分系統

**核心概念**：
不是所有錯誤都同等重要。格式錯誤比文風問題更嚴重。

**權重配置**：
```python
CATEGORY_WEIGHTS = {
    "format": 3.0,      # 格式錯誤（公文規範）
    "compliance": 2.5,  # 政策合規性（法規要求）
    "fact": 2.0,        # 事實正確性（資訊準確）
    "consistency": 1.5, # 一致性（邏輯連貫）
    "style": 1.0        # 文風（可讀性）
}
```

**計算方式**：
```
加權總分 = Σ (Agent分數 × 類別權重 × 信心度) / Σ (類別權重 × 信心度)
```

**風險評估**：
```
加權錯誤分數 = Σ (錯誤數 × 類別權重)

Critical: 加權錯誤分數 ≥ 3.0 (至少一個高權重錯誤)
High:     有任何錯誤 OR 加權警告 ≥ 3.0
Moderate: 有警告 OR 總分 < 0.9
Low:      總分 < 0.95
Safe:     總分 ≥ 0.95
```

**實際效果**：
```
案例1: 1個格式錯誤
- 簡單計分: 0.75 (3個Agent通過, 1個失敗)
- 加權計分: 0.45 (格式權重3.0x, 嚴重影響總分)
- 結果: Critical Risk ⚠️

案例2: 2個文風警告
- 簡單計分: 0.80
- 加權計分: 0.90 (文風權重1.0x, 影響較小)
- 結果: Moderate Risk ℹ️
```

---

### 3. OrganizationalMemory - 機構記憶系統

**職責**：
學習並記住各機關的使用習慣，提供個性化服務。

**儲存資訊**：
```json
{
  "臺北市政府環境保護局": {
    "formal_level": "formal",
    "preferred_terms": {
      "請": "惠請",
      "考慮": "酌情考量"
    },
    "signature_format": "局長 XXX",
    "usage_count": 42,
    "last_updated": "2024-01-15T10:30:00"
  }
}
```

**API 使用**：

#### 1. 取得機關偏好
```python
from src.agents.org_memory import OrganizationalMemory

org_mem = OrganizationalMemory()
profile = org_mem.get_agency_profile("臺北市環保局")
print(profile["formal_level"])  # "formal"
```

#### 2. 更新偏好
```python
org_mem.update_preference(
    "臺北市環保局",
    "preferred_terms",
    {"復": "敬復", "請": "惠請"}
)
```

#### 3. 學習使用者編輯
```python
# 當使用者手動修改公文時
org_mem.learn_from_edit(
    agency_name="市政府",
    original="請貴局協助辦理。",
    edited="惠請貴局鼎力協助辦理。"
)
```

#### 4. 取得寫作提示（供 WriterAgent 使用）
```python
hints = org_mem.get_writing_hints("臺北市環保局")
print(hints)
# 輸出：
#   - 使用較為正式的用語（如：惠請、敬請）
#   - 偏好詞彙：'請' → '惠請', '考慮' → '酌情考量'
#   - 署名格式：局長 XXX
```

#### 5. 匯出統計報告
```python
report = org_mem.export_report()
print(report)
```

---

## 🚀 使用指南

### 完整流程範例

```python
from src.core.llm import LLMProvider
from src.knowledge.manager import KnowledgeBaseManager
from src.agents.editor import EditorInChief
from src.agents.org_memory import OrganizationalMemory

# 1. 初始化
llm = LLMProvider()
kb_manager = KnowledgeBaseManager()
editor = EditorInChief(llm, kb_manager)
org_mem = OrganizationalMemory()

# 2. 取得機關偏好（可選）
agency = "臺北市政府環境保護局"
hints = org_mem.get_writing_hints(agency)
print(f"[寫作提示]\n{hints}")

# 3. 執行 Multi-Agent Review（包含 ComplianceChecker）
draft = "您的公文草稿..."
refined_draft, qa_report = editor.review_and_refine(draft, "letter")

# 4. 檢視加權評分結果
print(f"Overall Score (Weighted): {qa_report.overall_score:.2f}")
print(f"Risk Level: {qa_report.risk_summary}")
print(f"\n{qa_report.audit_log}")

# 5. （可選）記錄使用者的手動修改
if user_edited_draft:
    org_mem.learn_from_edit(agency, refined_draft, user_edited_draft)
```

---

## 📊 配置說明

### config.yaml 新增區塊

```yaml
# 機構記憶設定
organizational_memory:
  enabled: true
  storage_path: ./kb_data/agency_preferences.json
  
  # 預設機關偏好範例
  default_agencies:
    臺北市政府環境保護局:
      formal_level: formal  # formal / standard / concise
      preferred_terms:
        "請": "惠請"
        "考慮": "酌情考量"
      signature_format: "局長 XXX"
    
    行政院:
      formal_level: formal
      preferred_terms:
        "請": "敬請"
      signature_format: "院長 XXX"
```

**參數說明**：
- `formal_level`: 正式程度
  - `formal`: 使用正式用語（惠請、敬請、酌情考量）
  - `standard`: 標準用語（請、考慮）
  - `concise`: 簡潔用語（避免冗詞）

- `preferred_terms`: 詞彙偏好對照表
  - Key: 標準用詞
  - Value: 偏好用詞

- `signature_format`: 署名格式

---

## 🧪 測試

### 執行測試腳本

```powershell
cd "C:\Users\User\Desktop\公文ai agent"
.\test_multi_agent_v2.ps1
```

### 測試內容

1. **Phase 1**: ComplianceChecker 單元測試
2. **Phase 2**: OrganizationalMemory API 測試
3. **Phase 3**: 加權評分系統配置驗證
4. **Phase 4**: 完整流程整合測試

### 預期輸出

```
🚀 Multi-Agent Architecture Enhancement Test
=============================================

📋 Phase 1: 測試合規性檢查器 (Compliance Checker)
✓ 測試草稿已建立

📋 Phase 2: 測試機構記憶系統 (Organizational Memory)
=== 測試1: 取得臺北市環保局偏好 ===
正式程度: formal
✓ 機構記憶系統測試通過

📋 Phase 3: 測試加權評分系統
=== 類別權重配置 ===
format         : 3.0x
compliance     : 2.5x
fact           : 2.0x
consistency    : 1.5x
style          : 1.0x
✓ 加權評分系統配置正確

📋 Phase 4: 整合測試（完整流程）
=== 執行 Multi-Agent Review ===
Overall Score: 0.72
Risk Level: High
✓ QA Report 已儲存

🎉 所有測試完成！
```

---

## 📈 效益分析

### Before (Version 1.0)
```
問題1: 格式錯誤 → 扣25分
問題2: 文風不順 → 扣25分
總分: 50分 (平均)
```
❌ 兩者被視為同等嚴重

### After (Version 2.0)
```
問題1: 格式錯誤 (權重3.0) → 扣45分
問題2: 文風不順 (權重1.0) → 扣10分
加權總分: 31.4分
```
✅ 格式錯誤被正確識別為更嚴重的問題

### 實際案例

**場景**：某公文有1個格式錯誤、1個政策不一致、2個文風警告

| 評分方式 | 總分 | 風險等級 | 處理建議 |
|---------|------|---------|---------|
| 簡單平均 | 0.60 | High | 需修正 |
| 加權評分 | 0.42 | **Critical** | **立即修正** |

**差異**：加權評分正確識別出格式+合規問題的嚴重性，觸發Critical風險等級。

---

## 🔧 進階擴充

### 1. 加入自訂 Agent

```python
# src/agents/custom_checker.py
class CustomChecker:
    def check(self, draft: str) -> ReviewResult:
        # 你的檢查邏輯
        return ReviewResult(...)

# 在 editor.py 中註冊
self.custom_checker = CustomChecker(llm)
results.append(self.custom_checker.check(draft))
```

### 2. 調整權重配置

```python
# 修改 src/agents/editor.py
CATEGORY_WEIGHTS = {
    "format": 5.0,  # 提高格式權重
    "compliance": 3.0,
    # ...
}
```

### 3. 擴充機構記憶學習能力

```python
# 在 org_memory.py 的 learn_from_edit 中加入
def learn_from_edit(self, agency_name, original, edited):
    # 使用 difflib 分析差異
    import difflib
    diff = difflib.unified_diff(
        original.splitlines(),
        edited.splitlines()
    )
    # 提取常見替換模式
    # 更新 preferred_terms
```

---

## 📝 未來規劃

- [ ] **進階學習演算法**：使用機器學習分析編輯模式
- [ ] **即時建議系統**：在寫作時即時套用機關偏好
- [ ] **協作模式**：多人編輯時合併偏好設定
- [ ] **政策自動更新**：定期從政府網站抓取最新政策

---

## 💡 常見問題

### Q1: 如何停用 ComplianceChecker？
**A**: 在 `editor.py` 的 `review_and_refine` 方法中註釋掉該行：
```python
results = [
    # ...
    # self.compliance_checker.check(draft),  # 註釋此行
]
```

### Q2: 如何重設機構記憶？
**A**: 刪除 `kb_data/agency_preferences.json` 檔案。

### Q3: 加權評分是否可關閉？
**A**: 可以，將所有權重設為 1.0 即回到簡單平均模式。

### Q4: 如何新增自訂政策文件？
**A**: 將文件放入 `kb_data/policies/` 目錄，格式為 Markdown。

---

## 📞 支援

如有問題或建議，請參考：
- 主要文檔: `README.md`
- 快速開始: `QUICKSTART.md`
- 專案總結: `PROJECT_SUMMARY.md`
