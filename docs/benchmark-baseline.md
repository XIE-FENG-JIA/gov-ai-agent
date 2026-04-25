# Benchmark Baseline v2.1

公文 AI Agent 品質盲測基線文件。本文記錄截至 2026-04-26 的最新基線快照、趨勢演進、及後續完整評測的執行方式。

## 快速摘要

| 指標 | 值 |
|------|-----|
| 快照版本 | v2.1 (afterfix17, limit=2) |
| 評測日期 | 2026-04-25 |
| 總題數 | 2 / 30（全量需啟動 API server）|
| 文別 | 函（×2） |
| avg_score | **0.8766** |
| success_rate | 1.0（2/2 成功） |
| goal_met_rate | 0.0（score ≥ 0.95 尚未達成） |
| median 耗時 | 634 秒 / 題 |
| 主要問題類別 | fact（8）、style（5）、compliance（5）|

> **注意**：全量 30 題基線需啟動 API server（`uvicorn src.api.app:app`）後執行
> `python scripts/run_blind_eval.py --limit 30 --output benchmark/baseline_v2.1_full.json`

---

## 趨勢演進

下表列出 `benchmark/trend.jsonl` 前 8 筆歷史快照（每筆 limit=2）：

| 日期 | Run ID | avg_score | total | 備註 |
|------|--------|-----------|-------|------|
| 2026-04-20 | afterfix (limit1) | 0.598 | 1 | 初始修復後第一次評測 |
| 2026-04-21 | afterfix2 (limit2) | 0.8723 | 2 | 大幅改善 (+46%) |
| 2026-04-22 | afterfix4 | 0.8654 | 2 | 穩定 |
| 2026-04-23 | afterfix6 | 0.780 | 2 | 輕微下降（部分修改） |
| 2026-04-23 | afterfix9 | 0.6617 | 2 | 臨時性下降 |
| 2026-04-24 | afterfix12 | 0.8509 | 2 | 回升 |
| 2026-04-25 | afterfix14 | 0.8819 | 2 | 高峰 |
| 2026-04-25 | afterfix17 | **0.8766** | 2 | 當前基線快照 |

趨勢工具：`python scripts/benchmark_trend.py <result.json>` — 自動追加並偵測 >10% 跌幅。

---

## 現有快照詳情（afterfix17, limit=2）

### han-001：轉知淨零排放路徑推動方案

- **score**: 0.8448
- **risk**: High
- **rounds_used**: 4
- **主要問題**：fact ×5, compliance ×3, style ×2, format ×1

### han-002：召開數位政府推動委員會

- **score**: 0.9084
- **risk**: High
- **rounds_used**: 4
- **主要問題**：fact ×3, style ×3, consistency ×3, compliance ×2

---

## 完整基線執行步驟

**前置條件**：
1. API server 已啟動：`uvicorn src.api.app:app --host 0.0.0.0 --port 8000`
2. LLM API key 已設定（`config.yaml` 或環境變數）
3. KB 已 rebuild：`gov-ai kb rebuild --only-real`

**執行全量評測**：
```bash
python scripts/run_blind_eval.py \
  --corpus benchmark/mvp30_corpus.json \
  --limit 30 \
  --output benchmark/baseline_v2.1_full.json
```

**追加趨勢**：
```bash
python scripts/benchmark_trend.py benchmark/baseline_v2.1_full.json
```

---

## Regression Gate

- 工具：`scripts/benchmark_trend.py`
- 觸發條件：`avg_score` 跌幅 > 10%（相對前一次快照）
- Exit code 1 = regression；可接入 CI 管線

**建議使用時機**：每次 T2.x（模型/prompt 修改）、KB rebuild、或重大重構後執行。

---

## 目標

| 指標 | 現況 | 目標 |
|------|------|------|
| avg_score | 0.88 | ≥ 0.95 |
| goal_met_rate | 0.0 | ≥ 0.50 |
| success_rate | 1.0 | 維持 1.0 |
| median 耗時 | 634s | ≤ 300s |

---

*本文由 T6.1 task 建立。全量快照 `baseline_v2.1.json` 內含 2 題快照，30 題全量評測待 API server 可用後執行。*
