# Auto-Dev Program — 公文 AI Agent（真實公開公文改寫系統）

> **版本**：v2.2（2026-04-20 02:30 — 技術主管第二輪回顧重排；P0.5.pre 退役、P0.5.b 拆 6 子 commit、T1.5-FAST / T7.2 升 P1 最前、Epic 8 覆蓋率先行）
> Auto-engineer 每輪讀此檔，從「待辦」挑第一個未完成任務執行。完成後 `[x]` 勾選、log 追加到 `results.log`。

---

## 🚨 北極星指令（優先於所有判斷）

**每輪啟動後第一動作**：
1. `git status --short | wc -l` 看工作樹是否乾淨
2. **若 > 0 → 當輪唯一目標是分類 commit，直到 `git status` 乾淨**
3. 工作樹乾淨後，才從「待辦」挑第一個 `[ ]` 未勾任務執行

### 禁止行為
- ❌ 不要讓 M 狀態檔案累積超過 1 輪（修好 bug 立刻 commit，不要等「批次」）
- ❌ 不要先跑 pytest 再決定做什麼（該跑 pytest 是**任務 deliverable 的一部分**，不是啟動 ritual）
- ❌ 不要改這份 program.md 最前面的 Epic 結構（只能 `[x]` 勾選、搬到「已完成」區、或在待辦清單尾端新增已拆細的子任務）

### 任務顆粒度原則
- 每個 `[ ]` 任務必須 **1 小時內可完成**（讀檔 + 改 1-3 個檔 + pytest + commit）
- 若某任務太大 → **拆成 T1.2.a / T1.2.b / T1.2.c 子任務** append 到對應 Epic 尾，原任務保留但移到最後做
- 每完成一子任務 → 一個 commit（不要累積）

---

## 專案資訊
- **名稱**: 公文 AI Agent（Gov AI Agent）
- **定位**: 從真實公開的政府公文中，找相符範本 → 最小改動改寫 → 可追本溯源
- **技術棧**: Python 3.11+ / Ollama (Llama 3.1 8b) / ChromaDB / click CLI / python-docx
- **根目錄**: `D:/Users/Administrator/Desktop/公文ai agent/`
- **運行模式**: 本地優先（Local-First），但資料源必須是公開真實政府公文
- **引擎**: codex (gpt-5.4) 驅動 auto-engineer，L4 自主模式

---

## 核心原則（不可違反）

### 🔴 三條紅線
1. **真實性**：知識庫只收真實公開政府公文。`kb_data/examples/` 現有 **156** 份合成公文須標記 `synthetic=true`，生成時排除為主要參考
2. **改寫而非生成**：Writer 必須以「找到一份最相似真實公文 → 最小改動改寫」為主策略，純生成僅限找不到相似文件時的 fallback
3. **可溯源**：每份生成公文必須附 `## 引用來源` 段，列出：機關、發文字號、發文日期、原文 URL、相似度分數

### 🟢 合規與授權
- 只抓**公開公文**（政府資料開放平台、各部會公告頁、公報系統、法規資料庫）
- 遵守 robots.txt + rate limit（建議 ≥2 秒/請求）
- 每份抓回的公文保留 `raw_snapshot`（原始 HTML/PDF）+ `source_url` + `crawl_date`
- User-Agent 明示：`GovAI-Agent/1.0 (research; contact: ...)`

---

## 開發規則

### 每次迭代只做一件事
- 從「待辦」挑第一個未完成任務
- 完成後 `[x]` 勾選 + 追加紀錄到 `results.log`
- 大任務自行拆小步驟，但 **program.md 的勾選只在完整 Epic task 完成後打勾**

### 品質要求
- 新代碼必須有 pytest（`pytest tests/`）
- 測試通過 → `git add` + `git commit`（conventional commit: `feat(sources): add moj law API adapter`）
- 測試失敗 → 最多 3 次修復 → 仍失敗則記 `results.log` + `git stash` 還原 + 跳過
- 架構變動必須先更新 `docs/architecture.md`

### 禁止事項
- ❌ 不要擅自升級依賴版本（除非任務明確要求）
- ❌ 不要刪除現有 agent（保留漸進改造路線）
- ❌ 不要動 `config.yaml` 結構（加欄位 OK，刪改舊欄位要先通知）
- ❌ 不要提交包含真人姓名/身分證/電話的實際抓回資料（PII 須遮罩後才能 commit 範例）

### 紀錄格式（results.log）
```
[YYYY-MM-DD HH:MM:SS] | [T 任務編號] | [PASS/FAIL/SKIP] | 簡述做了什麼 | 相關檔案
```

---

## P0 — 阻斷性回歸（最優先，按順序執行）

> v2.2 狀態：git 寫入權限已恢復（02:15 `f208ca6` commit 成功；`.git/index.lock` 無殘檔）。
> 當下阻斷：**工作樹仍 24 M + 多項 untracked 未 commit，連續 5 天 0 feat commit**。必須先清工作樹，才能動 Epic。

### P0.5.b — 依 commit-plan 分 6 組 commit（當下唯一 P0 阻斷）

> 前置：`docs/commit-plan.md` 已寫入分組；git 寫入權已恢復。每組 commit 前跑對應 pytest。

- [ ] **P0.5.b.1** `fix(tests)`：benchmark scripts + cli utils tmp cleanup + knowledge manager/quickstart/web_preview/robustness/api_server/cli_commands/config_tools_extra 回歸測試更新
  - `git add tests/test_benchmark_scripts.py tests/test_cli_utils_tmp_cleanup.py tests/test_knowledge_manager_cache.py tests/test_knowledge_manager_unit.py tests/test_quickstart.py tests/test_web_preview.py tests/test_robustness.py tests/test_api_server.py tests/test_cli_commands.py tests/test_config_tools_extra.py tests/test_agents.py`
  - 前置：`pytest tests/test_benchmark_scripts.py tests/test_cli_utils_tmp_cleanup.py` 綠
  - commit: `fix(tests): regression coverage for benchmark scripts, tmp cleanup, km lazy import`

- [ ] **P0.5.b.2** `fix(kb)`：KnowledgeBaseManager chromadb=None + lazy import 修復
  - `git add src/knowledge/manager.py`
  - 前置：`pytest tests/test_knowledge_manager_unit.py tests/test_knowledge_manager_cache.py` 綠
  - commit: `fix(kb): chromadb=None detection + reload-aware lazy import`

- [ ] **P0.5.b.3** `fix(api)`：CORS localhost 白名單 + models + workflow route
  - `git add api_server.py src/api/models.py src/api/routes/workflow.py`
  - 前置：`pytest tests/test_api_server.py` 綠
  - commit: `fix(api): cors localhost auto-expand 127.0.0.1/::1 + workflow route fixes`

- [ ] **P0.5.b.4** `fix(agents)`：writer citation + editor/template/style/compliance regressions
  - `git add src/agents/writer.py src/agents/editor.py src/agents/template.py src/agents/style_checker.py src/agents/compliance_checker.py src/assets/templates/han.j2`
  - 前置：`pytest tests/test_agents.py` 綠
  - commit: `fix(agents): writer citation prune + editor/template/style/compliance regressions`

- [ ] **P0.5.b.5** `fix(cli)`：generate encoding + config_tools/quickstart/switcher/utils
  - `git add src/cli/generate.py src/cli/config_tools.py src/cli/quickstart.py src/cli/switcher.py src/cli/utils.py src/web_preview/app.py src/web_preview/templates/config.html src/web_preview/templates/index.html src/utils/tw_check.py`
  - 前置：`pytest tests/test_cli_commands.py tests/test_config_tools_extra.py tests/test_quickstart.py tests/test_web_preview.py` 綠
  - commit: `fix(cli): markdown encoding report + tmp cleanup + wizard/switcher polish`

- [ ] **P0.5.b.6** `chore`：config.yaml / .env.example / .gitignore / README / config.yaml.example 調整 + 新增 scripts + engineer-log.md + docs/commit-plan.md 入版控
  - `git add config.yaml config.yaml.example .env.example .gitignore README.md scripts/build_benchmark_corpus.py scripts/run_blind_eval.py docs/commit-plan.md engineer-log.md`
  - commit: `chore: sync config/env examples, ignore tmp artifacts, add benchmark scripts & engineer-log`
  - 注意：`.serena/` / `benchmark/` 產物 / `.spectra.yaml` / `.json_*.tmp` / `meta_git/` / `meta_test/` / `repo_meta/` / `recovered_repo/` / `.git_acl_backup.txt` 皆走 `.gitignore`，不入 commit

- [ ] **P0.5.b.7** 修復 `.git` ACL foreign deny 汙染（v2.2 新發現 blocker）
  - 症狀：`git add -n ...` 與 `New-Item .git\codex_probe.lock -Force` 皆 `Permission denied`
  - 根因假設：`.git` / `.git\index` 含兩組 unresolved SID 的 explicit deny ACE，直接阻斷 index lock 建立
  - 已試失敗：`icacls /remove:d`、`Set-Acl`、`icacls /reset`
  - 完成條件：`New-Item .git\codex_probe.lock -Force` 可成功建立再刪除，且 `git add -n docs/commit-plan.md` 不再報 `index.lock` denied

- [ ] **P0.5.c** 最終確認 `git status --short` 為空，跑全量 `pytest tests/`，產出 `results.log: P0.5 closed` 完成記錄

### P0.7 — Repo 根災後清理（v2.2 新增）

- [ ] **P0.7** 清理權限事故備援殘檔 + `.json_*.tmp` 40+ 份 orphan
  - 先 diff `meta_git/` / `meta_test/` / `repo_meta/` / `recovered_repo/` 與 `.git/` / `tests/` 差異，確認無獨特內容後刪除；若有獨特內容，寫 `docs/disaster-recovery.md` 記錄
  - 重跑 `src/cli/utils.py` 的 tmp orphan cleanup（現在 git 寫入權恢復，應能清乾淨）
  - `.git_acl_backup.txt` 移至 repo 外或 `.gitignore`，避免權限備份外洩
  - commit: `chore: cleanup recovery artifacts & tmp orphans`

### 歷史 P0 追蹤（保留紀錄不動）

- [x] **P0.4** 修復 `test_writer_postprocess_adds_inline_citation_and_prunes_unused_refs` 回歸（results.log 01:12:02 二次修復）
- [x] **P0.5.a** 工作樹分組寫入 `docs/commit-plan.md`，列各檔屬 fix(api) / fix(cli) / fix(agents) / fix(kb) / fix(tests) / chore
- [x] **P0.5.pre** 解除 `.git/index.lock: Permission denied`（v2.2 退役；02:15 `f208ca6` commit 自然驗證完成條件）
- [x] **P0.6** 清 repo tmp orphan + 擴充 `.gitignore`

---

## P1 — 紅線守衛 + Spectra 底座（v2.2 提前至 P0 之後）

> **底層邏輯**：P0 清完後，下一件事必須守紅線 + 建規格底座，才有資格動 Epic 1-4。
> 兩項都是 1 小時內可閉環的「高槓桿」任務 — 一個 script、一份 config，解鎖後續所有戰略推進。

- [ ] **P1.1（原 T1.5-FAST）** 紅線 1 守衛 — 156 份合成公文加 `synthetic: true` frontmatter
  - 寫 `scripts/mark_synthetic.py`：遍歷 `kb_data/examples/*.md`，若無 frontmatter 則補；若已 frontmatter 則補上 `synthetic: true`
  - 驗證：`grep -L "synthetic: true" kb_data/examples/*.md` 回空（當前 0/156）
  - 寫 `tests/test_mark_synthetic.py`（至少 3 case：無 frontmatter / 有但缺 synthetic / 已正確）
  - commit: `chore(kb): mark 156 synthetic examples with frontmatter flag`
  - **為何提前**：沒這個守衛，Epic 2 retriever 會把合成公文當真實參考，紅線 1 違反 × 156

- [ ] **P1.2（原 T7.2）** `openspec/config.yaml` 填 project context
  - 現狀：整份 commented out，零規格底座
  - 填入：tech stack（Python 3.11+ / Ollama / ChromaDB / click / python-docx）/ conventions（conventional commit / pytest required）/ PII 遮罩規則 / 紅線三條 / 顆粒度原則（1 小時內可完成）
  - commit: `docs(spec): fill openspec project context`
  - **為何提前**：沒規格底座，Epic 7 T7.1 的 4 個 change proposal 無根基；auto-engineer prompt 也無法注入紅線

---

## Epic 1 — 真實公文資料源（最優先）

> **沒有真實資料，其他都是空殼**。此 Epic 完成前不動 Epic 2 的 T2.3 遷移層。
> v2.1 變更：合併 `T1.3` + `T2.4`（PublicGovDoc schema 重複）；刪除 `T5.1`（與 T1.5-FAST 重複）。

### 候選來源（seed list，auto-engineer 需驗證可用性）

| 來源 | URL | 類型 | 預估抓取方式 |
|---|---|---|---|
| 政府資料開放平台 | https://data.gov.tw/ | 資料集列表 API | JSON/CSV/XML export |
| 全國法規資料庫 | https://law.moj.gov.tw/ | 法規（非公文本身，為引據） | 官方有 API 與 XML 下載 |
| 行政院公報資訊網 | https://gazette.nat.gov.tw/ | 行政院公報 | 可能需爬（需調研 API 是否存在） |
| 行政院 RSS | https://www.ey.gov.tw/Page/5AC44DE3213868A9 | 新聞稿 / 公告 | RSS feed |
| 衛福部 RSS | https://www.mohw.gov.tw/cp-2661-6125-1.html | 各類公告 | RSS + 爬頁 |
| 財政部 RSS | https://www.fia.gov.tw/Rss | 公告 | RSS |
| 食藥署公告 API | https://www.fda.gov.tw/tc/DataAction.aspx | 公告 | 官方 API |
| 政府採購公告 | https://web.pcc.gov.tw/ | 採購/招標公告 | 需調研 |
| 立法院公報 | https://ppg.ly.gov.tw/ | 立院公報 | 可能有 API |
| 各縣市政府公報 | 各縣市 data.*.gov.tw | 地方公文 | 逐一調研 |

### 待辦任務

- [x] **T1.5-FAST** → **已升級為 P1.1**（見上方 P1 段）；Epic 1 內保留勾選記錄以維結構一致

- [ ] **T1.1** 調研 10 個候選來源，產出 `docs/sources-research.md`，每個來源含：API endpoint / 資料格式 / 授權條款 / 取得範例 / 資料量估計 / 優先級（1-5）

- [ ] **T1.2** 在 `src/sources/` 建 adapter 架構
  - 抽象基底 `BaseSourceAdapter`：`list(since_date)` / `fetch(doc_id)` / `normalize(raw)`
  - 先實作 5 個優先級最高：`DataGovTwAdapter` / `MojLawAdapter` / `ExecutiveYuanRssAdapter` / `MohwRssAdapter` / `FdaApiAdapter`
  - 用 recorded fixtures 寫測試（不打真 API）
  - 子任務（auto-engineer 自行拆）：
    - T1.2.a `BaseSourceAdapter` 抽象 + 1 個 adapter + fixture
    - T1.2.b 其餘 4 個 adapter
    - T1.2.c CLI wiring（接到 ingest pipeline）

- [ ] **T1.3** `PublicGovDoc` dataclass（`src/core/models.py`）— 合併原 T2.4
  - 欄位：`source_id` / `source_url` / `source_agency` / `source_doc_no` / `source_date` / `doc_type` / `raw_snapshot_path` / `crawl_date` / `content_md` / `synthetic: bool`
  - Pydantic v2 model，與 ChromaDB metadata 互通（先不碰 SurrealDB）
  - 單元測試：序列化 / 反序列化 / 缺欄位行為

- [ ] **T1.4** 增量 ingest pipeline `src/sources/ingest.py`
  - 依 `crawl_date` 增量、依 `source_id` 去重
  - 原始快照存 `kb_data/raw/{adapter}/{YYYYMM}/{doc_id}.html`
  - Normalized 存 `kb_data/corpus/{adapter}/{doc_id}.md`（YAML frontmatter 裝 metadata）
  - CLI: `gov-ai sources ingest --source all --since 2026-01-01`

- [ ] **T1.6** 首次跑 T1.4 ingest，至少從 3 個來源各抓 ≥50 份真實公文（≥150 份 baseline）

---

## Epic 2 — open-notebook 源碼整合（全抄路線，elephant-alpha 驅動）

> **路線決策**：整套 fork [lfnovo/open-notebook](https://github.com/lfnovo/open-notebook) 源碼進本專案，作為改寫引擎骨幹。公文 AI 的 5 agent 審查層保留，疊在 open-notebook 之上。
> v2.1 變更：刪除 `T2.4`（合入 T1.3）；**`T2.3` SurrealDB 遷移凍結**（待 T2.1-T2.2 人工 review 後解凍）；刪除 `T2.10`（upstream sync 等第一階段完成再談）。

### 待辦任務

- [ ] **T2.0** Provider + 環境準備
  - `.env` 設 `OPENROUTER_API_KEY=<key>`（人工填）+ `LLM_MODEL=openrouter/elephant-alpha`
  - 驗：`python -c "from litellm import completion; completion(model='openrouter/elephant-alpha', messages=[{'role':'user','content':'hi'}])"`
  - `config.yaml` 確認 LLM provider 可切 OpenRouter

- [ ] **T2.1** Clone + 研讀
  - `git clone https://github.com/lfnovo/open-notebook vendor/open-notebook`（.gitignore 加 `vendor/`）
  - 產出 `docs/open-notebook-study.md`：FastAPI routers 地圖 / SurrealDB schema / ask_service 路徑 / 融合切點

- [ ] **T2.2** 架構融合決策 `docs/integration-plan.md`
  - 對比 Fork / 疊加 / 重寫三種融合方式
  - 預設 Fork 模式，T2.1 若發現阻礙再重議
  - **此任務完成後需 🛑 人工 review**，通過才能解凍 T2.3

- [ ] **T2.3** 🛑 資料層遷移：ChromaDB → SurrealDB（**凍結中**，T2.2 人審後解凍）
  - docker compose 起 SurrealDB v2
  - `scripts/migrate_chroma_to_surreal.py`：遷移現有 1615 筆索引
  - 保留 ChromaDB 作 rollback 備援
  - 驗收：search_hit_rate ≥ 0.95

- [ ] **T2.5** API 層融合
  - open-notebook FastAPI routers 導入 `api_server.py`
  - 原 `src/api/routes/` agents / knowledge / health 路由保留
  - Port 衝突檢查（open-notebook 預設 8000）

- [ ] **T2.6** Writer 改為 open-notebook `ask_service` 薄殼
  - `src/agents/writer.py` 只組 prompt 和轉回 pipeline
  - 真正 source-grounded 改寫由 `ask_service.ask()` 執行
  - 輸入：retriever 回 top-K `synthetic=false` docs + 需求
  - 輸出：改寫 content + inline citations + change_log

- [ ] **T2.7** Retriever 強化
  - `src/knowledge/retriever.py`：SurrealDB `vector::similarity::cosine()` 替代 Chroma
  - 過濾 `synthetic=false`，回 top_k + `similarity_score`
  - 若最高 similarity < 0.5 → flag `low_match=True`，走 fallback

- [ ] **T2.8** Fallback 純生成（安全網）
  - `low_match=True` 或 ask_service 不可用時
  - writer.py 直呼 litellm（elephant-alpha），prompt 標 `synthetic_fallback=true`
  - 引用段留空並標示「本稿為純生成」

- [ ] **T2.9** Diff output
  - `src/core/diff.py`：`diff_real_vs_draft(real_doc, draft)` 輸出 unified diff
  - 修改比例 > 40% → `heavy_rewrite=true`，警示人審
  - 修改比例 > 60% → **強制退回**，要求重選基底公文

### Epic 2 風險
- 🔴 SurrealDB 部署：Windows docker desktop 需先驗證 → T2.3 凍結中
- 🔴 1615 筆 migration：失敗需 rollback
- 🟡 T2.1-T2.2 完成前禁止動 T2.3 以後任務

---

## Epic 3 — 溯源（可追本，open-notebook citation + 台灣公文格式）

- [ ] **T3.1** `src/core/citation.py` 擴充 open-notebook citation
  - 接收 ask_service inline `[n]` + refs list
  - 映射為台灣公文格式（機關 / 發文字號 / 發文日期 / 原文 URL / 相似度 / 修改比例）
  - 單元測試：5 組 mock data

- [ ] **T3.2** `src/core/exporter.py` docx 匯出擴充
  - Word Custom Properties 寫 `source_doc_ids` / `citation_count` / `ai_generated: true` / `engine: openrouter/elephant-alpha`
  - 文末加 `引用來源` 段（獨立章節，不用 footnote）

- [ ] **T3.3** 生成 pipeline 強制 citation
  - 每份輸出**必含**引用來源段（`--no-citation` 才能關，預設 on）
  - `synthetic_fallback=true` → 標示「本稿為純生成」且要求人審

- [ ] **T3.4** 溯源驗證工具
  - `gov-ai verify <docx>`：讀 docx Custom Properties，比對 kb 中 source_doc_ids / URL 健康
  - 產出 `verify_report.json`

---

## Epic 4 — 審查層加「溯源完整性」

- [ ] **T4.1** `src/agents/citation_checker.py`（新 agent）
  - 檢查 draft 是否含 citation section
  - 檢查 citation `source_doc_no` 是否在 kb 真實存在
  - 修改比例 > 60% → 警示「偏離來源」

- [ ] **T4.2** `src/agents/fact_checker.py` 強化
  - 引文句（「依據 ○○ 法第 N 條」）對照 `kb_data/regulations/` 實條文
  - 抓不到 → 標 `citation_unverified=true`

- [ ] **T4.3** `src/agents/auditor.py` 整合上述 2 checker 到 pipeline

---

## Epic 5 — 清理與重建

> v2.1 變更：刪除 `T5.1`（與 `T1.5-FAST` 重複）；`T5.3` 需 `T5.2` 完成才解凍。

- [ ] **T5.2** 真實資料 ≥ 500 份後，`gov-ai kb rebuild --only-real` 重建索引
- [ ] **T5.3** 🛑 ChromaDB 停役（凍結中）：SurrealDB 穩定 ≥ 2 週後 archive `kb_data/chroma.sqlite3`
- [ ] **T5.4** E2E 測試：5 個典型需求跑完整 pipeline，驗：改寫基於真實公文 / 引用來源完整 / docx 屬性正確 / 修改比例 < 40%

---

## Epic 6 — 品質基準（v2.1 新增，承接現有 benchmark/）

> 現況：`scripts/build_benchmark_corpus.py` + `scripts/run_blind_eval.py` 已落地；`benchmark/` 內有 `mvp30_corpus.json` + 18 份盲測結果但未進 program.md 的閉環；`tests/test_benchmark_scripts.py` 已存在。

- [ ] **T6.0** Benchmark workstream 歸位
  - 把 `scripts/build_benchmark_corpus.py` / `run_blind_eval.py` 文件化：寫 `docs/benchmark.md` 說明用法 / 輸入 / 輸出 schema
  - `benchmark/blind_eval_results.*.json` 加入 `.gitignore`（產物），但保留 `mvp30_corpus.json`（輸入語料，需 commit）
  - commit: `docs(benchmark): document benchmark workflow + ignore result artifacts`

- [ ] **T6.1** 量化當前基線
  - 用 `run_blind_eval.py --limit 30` 跑 full corpus，產出 `benchmark/baseline_v2.1.json`
  - 寫 `docs/benchmark-baseline.md` 列 pass rate / 平均分 / typical failure categories
  - 這是後續 Epic 2 改造後的 before/after 對照

- [ ] **T6.2** Epic 2 改造 A/B 基準
  - 每次 T2.x 完成後，跑一次 blind eval，結果追加到 `benchmark/trend.jsonl`
  - auto-engineer 檢測到平均分下降 > 10% → `results.log: REGRESSION` 並暫停

---

## Epic 7 — Spectra 規格對齊（v2.1 新增）

> 現況：`openspec/` 只有 config.yaml（全 comment out），`openspec/changes/archive/` 空，`spectra status` 回「No active changes」。規格沒建，對齊無從談起。

- [ ] **T7.1** 把現有 Epic 1~4 的核心任務寫成 spectra change proposal
  - `spectra new change 01-real-sources` / `02-open-notebook-fork` / `03-citation-tw-format` / `04-audit-citation`
  - 每個 proposal 含 problem / solution / non-goals / acceptance criteria
  - commit: `docs(spec): init core epic proposals`

- [x] **T7.2** → **已升級為 P1.2**（見上方 P1 段）；Epic 7 內保留勾選記錄

- [ ] **T7.3** `engineer-log.md` 進版控 + 每輪反思 append 規範
  - 從 `.gitignore` 白名單中明確保留
  - commit: `docs: start tracking engineer-log`

---

## Epic 8 — 代碼健康（v2.1 新增）

> 現況：engineer-log 標出的 P2 債務，獨立 Epic 管理，避免混進 feature 任務而被跳過。
> v2.2 變更：T8.3（覆蓋率）提前至 Epic 8 首位 — 沒 baseline 拆大檔會拆出測試漏洞。

- [ ] **T8.3** 測試覆蓋率量化（v2.2 提前至首位）
  - 跑 `pytest --cov=src --cov-report=json --cov-report=term`
  - 寫 `docs/coverage.md`，列 < 60% 覆蓋的模組，優先補測試
  - commit: `docs(coverage): quantify baseline coverage + gap analysis`
  - **必須先做**：T8.1 拆大檔前的安全網

- [ ] **T8.1** 大檔拆分（任一檔超過 800 行即拆，T8.3 完成後才動）
  - `src/cli/kb.py` 1614 行 → 拆成 kb/{ingest,sync,stats,rebuild}.py
  - `src/cli/generate.py` 1263 行 → 拆成 generate/{pipeline,export,cli}.py
  - `src/agents/editor.py` 1065 行 → 拆成 editor/{segment,refine,merge}.py
  - 拆分原則：先拆不改邏輯，commit；再重構，commit

- [ ] **T8.2** Pydantic v2 相容修 1363 條 deprecation warning
  - 鎖定 chromadb 1.x 兼容層 / `src/api/models.py` / `src/core/models.py`
  - 目標：`pytest -W error::DeprecationWarning` 通過

---

## 已完成

- [x] **P0.1** CORS localhost 白名單自動展開 127.0.0.1 / ::1（`api_server.py`）
- [x] **P0.2** generate CLI Markdown 編碼回報（`src/cli/generate.py`）
- [x] **P0.3** KnowledgeBaseManager chromadb=None 分流（`src/knowledge/manager.py`）
- [x] **P0.4** writer citation prune / 多來源追蹤語意拆分（`src/agents/writer.py`）
- [x] **P0.6** tmp orphan cleanup + .gitignore 擴充（`src/cli/utils.py` / `tests/test_cli_utils_tmp_cleanup.py`）
- [x] **P0.5.a** 工作樹 commit 分組（`docs/commit-plan.md`）
- [x] **P0.5.pre** git 寫入權限阻斷解除（v2.2 退役；02:15 `f208ca6` commit 成功自然驗證完成條件）

（auto-engineer 會把勾選的任務搬到這裡）

---

## 備註

### Auto-engineer 行為約束
- **不確定時寫 TODO 到 results.log 並跳過**，不要亂猜 API endpoint
- **每個 Epic 完成後跑一次整合測試**（`pytest tests/integration/`）
- **三輪內沒進展要求 program.md 人審**（寫 `results.log: ESCALATE`）

### 法律合規提醒
- 某來源明文禁止爬取 → 不抓，記 `docs/sources-research.md` 封鎖名單
- 公文內含個資（身分證、電話）→ 寫入 kb 前必 mask

### Spectra 規格驅動
Epic 7 負責建置。建置完成前，program.md 是單一事實來源。

---

**版本**：v2.2（2026-04-20 02:30 技術主管第二輪回顧重排）| **下一次重排觸發**：P0.5.b × 6 + P1.1 + P1.2 全綠 + Epic 6 T6.1 baseline 跑完
