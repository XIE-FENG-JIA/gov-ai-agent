# Graph Workflow 整合說明

> 本文件供 Engineer 1 完成 `src/graph/` 框架後，Engineer 2 整合至 API 層時參考。

## 1. `_execute_document_workflow` 現況分析

### 1.1 函式簽名

```python
def _execute_document_workflow(
    user_input: str,
    llm,
    kb,
    session_id: str,
    skip_review: bool = False,
    max_rounds: int = 3,
    output_docx: bool = False,
    output_filename_hint: str | None = None,
    agency: str | None = None,
    convergence: bool = False,
    skip_info: bool = False,
) -> tuple:
```

**回傳值**：`(requirement, final_draft, qa_report, output_filename, rounds_used)`

- `requirement`: `PublicDocRequirement` (Pydantic model)
- `final_draft`: `str` (最終公文草稿 markdown)
- `qa_report`: `QAReport | None` (品質報告；skip_review=True 時為 None)
- `output_filename`: `str | None` (DOCX 檔名；output_docx=False 時為 None)
- `rounds_used`: `int` (實際審查輪數；skip_review=True 時為 0)

### 1.2 呼叫端

`run_meeting` 端點（`POST /api/v1/meeting`）透過 `run_in_executor` 在執行緒池中呼叫：

```python
requirement, final_draft, qa_report, output_filename, rounds_used = (
    await run_in_executor(
        lambda: _execute_document_workflow(...),
        timeout=MEETING_TIMEOUT,
    )
)
```

`run_batch` 端點（`POST /api/v1/batch`）以相同方式呼叫，每個 batch item 各自呼叫一次。

### 1.3 內部步驟與各 Agent 呼叫方式

| 步驟 | 行號 (約) | Agent / 元件 | 呼叫方式 |
|------|-----------|-------------|---------|
| 1. 需求分析 | 85-86 | `RequirementAgent(llm).analyze(user_input)` | 同步 |
| 1.5 機構記憶 | 88-104 | `get_org_memory().get_writing_hints(agency)` | 同步 |
| 2. 撰寫草稿 | 97-105 | `WriterAgent(llm, kb).write_draft(requirement)` | 同步 |
| 3. 套用模板 | 108-111 | `TemplateEngine().parse_draft()` + `.apply_template()` | 同步，無 LLM |
| 4. 審查修正 | 117-123 | `EditorInChief(llm, kb).review_and_refine(...)` | 同步（內部並行） |
| 5. 匯出 DOCX | 128-140 | `DocxExporter().export(...)` | 同步，無 LLM |

---

## 2. 需要替換的行範圍

整合時 **替換 `_execute_document_workflow` 函式的步驟 1~4**（第 84~124 行），步驟 5（匯出）保留不變。

具體而言：

### 2.1 要移除/替換的程式碼

```python
# 步驟 1: 需求分析
req_agent = RequirementAgent(llm)
requirement = req_agent.analyze(user_input)

# 步驟 1.5: 取得機構記憶偏好（若有啟用）
writing_hints = ""
org_mem = get_org_memory()
resolved_agency = agency or requirement.sender
if org_mem and resolved_agency:
    writing_hints = org_mem.get_writing_hints(resolved_agency)

# 步驟 2: 撰寫草稿（注入機構偏好）
writer = WriterAgent(llm, kb)
if writing_hints:
    original_reason = requirement.reason or ""
    requirement.reason = (
        f"{original_reason}\n\n"
        f"【機構寫作偏好】\n{writing_hints}"
    ).strip()
raw_draft = writer.write_draft(requirement)

# 步驟 3: 套用模板
template_engine = TemplateEngine()
sections = template_engine.parse_draft(raw_draft)
formatted_draft = template_engine.apply_template(requirement, sections)

final_draft = formatted_draft
qa_report = None
rounds_used = 0

# 步驟 4: 審查
if not skip_review:
    editor = EditorInChief(llm, kb)
    final_draft, qa_report = editor.review_and_refine(
        final_draft, requirement.doc_type, max_rounds=max_rounds,
        convergence=convergence, skip_info=skip_info,
        show_rounds=False,
    )
    rounds_used = qa_report.rounds_used
```

### 2.2 替換為 graph.invoke 呼叫

```python
from src.graph.document_graph import build_document_graph

# 建構 graph（可快取為模組級單例）
graph = build_document_graph(llm, kb)

# 組裝初始狀態
initial_state = {
    "user_input": user_input,
    "agency": agency,
    "skip_review": skip_review,
    "max_rounds": max_rounds,
    "convergence": convergence,
    "skip_info": skip_info,
}

# 執行 graph
final_state = graph.invoke(initial_state)

# 從 final_state 取出結果
requirement = final_state["requirement"]
final_draft = final_state["final_draft"]
qa_report = final_state.get("qa_report")
rounds_used = final_state.get("rounds_used", 0)
```

---

## 3. 回傳值轉換

### 3.1 Graph State -> API Response 對應

| Graph State Key | 原始回傳位置 | 型別 | 備註 |
|----------------|-------------|------|------|
| `requirement` | `tuple[0]` | `PublicDocRequirement` | graph 節點 1 產出 |
| `final_draft` | `tuple[1]` | `str` | graph 最終節點產出 |
| `qa_report` | `tuple[2]` | `QAReport \| None` | 審查節點產出；skip_review 時為 None |
| `rounds_used` | `tuple[4]` | `int` | `qa_report.rounds_used` 或 0 |

### 3.2 步驟 5（匯出）不需改動

匯出邏輯直接使用 `requirement`、`final_draft`、`qa_report` 三個變數，
只要 graph 的回傳值型別與原始一致，匯出程式碼完全不動。

### 3.3 向後相容保障

- `_execute_document_workflow` 的 **函式簽名不變**
- **回傳值 tuple 結構不變**：`(requirement, final_draft, qa_report, output_filename, rounds_used)`
- `run_meeting` 和 `run_batch` **完全不需修改**
- 唯一變動在 `_execute_document_workflow` 函式體內部

---

## 4. Scoring 模組已獨立

加權分數計算和風險判定邏輯已抽至 `src/core/scoring.py`：

- `calculate_weighted_scores(results)` — 加權品質分數
- `calculate_risk_scores(results)` — 加權風險分數
- `get_agent_category(agent_name)` — Agent 類別推斷
- `assess_risk_level(...)` — 風險等級判定（重新匯出自 constants）
- `CATEGORY_WEIGHTS` — 類別權重常數（重新匯出自 constants）

Graph 的審查節點可直接 `from src.core.scoring import ...` 使用這些純函式，
無需實例化 EditorInChief。

---

## 5. 整合注意事項

1. **同步 vs 非同步**：`_execute_document_workflow` 是同步函式，在 `run_in_executor` 中以執行緒池執行。若 `graph.invoke` 是同步呼叫，可直接替換；若是 `async`，需改用 `await graph.ainvoke()`，並將 `_execute_document_workflow` 改為 `async def`。

2. **錯誤處理**：目前 workflow 的異常由 `run_meeting` 的 try/except 統一捕獲。Graph 內部節點的異常應向上傳播，不要在節點內部靜默吞掉。

3. **機構記憶注入**：步驟 1.5 的 `writing_hints` 注入目前是修改 `requirement.reason`。Graph 版本建議改為在 state 中傳遞 `writing_hints`，由 writer 節點自行合併，避免 mutation side effect。

4. **測試策略**：整合後應確保 `POST /api/v1/meeting` 的 response schema 不變，可用現有的 integration test 直接驗證。
