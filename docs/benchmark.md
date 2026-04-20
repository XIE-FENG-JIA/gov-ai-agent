# Benchmark Workflow

`benchmark/mvp30_corpus.json` 是目前的固定題庫。來源由 `kb_data/examples/*.md` 抽樣而來，預設收 `函 / 公告 / 簽` 各 10 題，供 API meeting 端點做盲測。

## Workflow

1. 建題庫：`python scripts/build_benchmark_corpus.py`
2. 啟 API：預設打 `http://127.0.0.1:8000/api/v1/meeting`
3. 跑盲測：`python scripts/run_blind_eval.py --limit 30`
4. 讀結果：看 `summary`、各題 `results`、以及 `top_issue_categories`

若 `config.yaml` 內有 `api.api_keys`，`run_blind_eval.py` 會自動帶第一把 Bearer token。若沒有，則以無認證請求執行。

## Corpus Schema

題庫 JSON 頂層欄位：

- `name`: 題庫名稱
- `doc_types`: 納入的文別列表
- `per_type`: 每種文別抽樣數
- `total_items`: 總題數
- `strict_mode_defaults`: 預設嚴格模式參數
- `items`: 題目清單

每個 `items[]` 物件欄位：

- `id`: 題號，格式如 `han-001`
- `doc_type`: 文別，例如 `函`
- `title`: 題目標題
- `source_file`: 對應範本路徑
- `user_input`: 送給 meeting API 的自然語言需求
- `reference`: `sender` / `receiver` / `subject` / `basis` / `source_level`
- `strict_request`: 直接 merge 到 API payload 的嚴格模式參數

目前 `strict_request` 預設為：

```json
{
  "skip_review": false,
  "ralph_loop": true,
  "ralph_max_cycles": 2,
  "ralph_target_score": 1.0,
  "use_graph": false,
  "max_rounds": 2,
  "output_docx": false
}
```

## Result Schema

`run_blind_eval.py` 輸出 JSON 頂層欄位：

- `corpus`: 題庫路徑
- `api_base`: API base URL
- `timeout_sec`: 單題 timeout
- `headers_used`: 是否自動載入 Bearer token
- `summary`: 聚合結果
- `results`: 單題明細

`summary` 目前包含：

- `total`
- `success_count` / `success_rate`
- `goal_met_count` / `goal_met_rate`
- `avg_score`
- `median_duration_sec`
- `by_doc_type`
- `top_issue_categories`

每個 `results[]` 物件欄位：

- `id`
- `doc_type`
- `status_code`
- `success`
- `goal_met`
- `duration_sec`
- `score`
- `risk`
- `rounds_used`
- `error`
- `error_code`
- `issue_stats`: `severity` / `category` / `total`

`goal_met` 的判定很嚴：API `success=true`、`overall_score >= ralph_target_score`、`risk == "Safe"`、而且 issue 數量必須是 0。

## Commands

重建 30 題題庫：

```bash
python scripts/build_benchmark_corpus.py
```

只跑前 30 題盲測：

```bash
python scripts/run_blind_eval.py --limit 30
```

指定輸出檔與 API：

```bash
python scripts/run_blind_eval.py --api-base http://127.0.0.1:8000 --output benchmark/blind_eval_results.local.json --limit 30
```

## How To Read Results

- 先看 `goal_met_rate`：這是最終通關率，比單純 `success_rate` 更嚴格。
- 再看 `avg_score` 與 `by_doc_type`：判斷哪種文別最弱。
- 最後看 `top_issue_categories`：這是下一輪修復的優先序。
- 若 `duration_sec` 明顯飆高，代表 RALPH 迴圈或 API latency 有退化。

## Artifact Policy

- 題庫基線：`benchmark/mvp30_corpus.json`
- 忽略產物：`benchmark/blind_eval_results*.json`、`benchmark/baseline_*.json`、`benchmark/trend.jsonl`
- ACL-deny 臨時策略：`benchmark/` 先全忽略，避免未提交 corpus 長期污染 `git status`；待 `P0.D` 解除後，恢復 `benchmark/mvp30_corpus.json` 版控並補 commit

這樣做的原因：題庫是基準線，結果檔是每輪執行產物，不該污染工作樹。
