# Auto-Dev Program — 公文 AI Agent（真實公開公文改寫系統）

> **版本**：v2.3（2026-04-20 03:45 — 技術主管第三輪回顧重排；P0.5.b × 6 + P1.1 全退役、P1 新增 T6.0 + T8.3 前置、Epic 1/2 顆粒度降粗、新增 Epic 9 Repo 衛生）
> **v2.2**（2026-04-20 02:30 — 第二輪）：P0.5.pre 退役、P0.5.b 拆 6 子 commit、T1.5-FAST / T7.2 升 P1 最前、Epic 8 覆蓋率先行
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

> v2.3 狀態：**工作樹乾淨（git status=0）、測試 3543 綠、P0.5.b × 6 + P1.1 全 commit 落盤**。P0 全退役，進入 P1 高槓桿執行階段。
> v2.2 狀態（歷史）：git 寫入權限已恢復（02:15 `f208ca6` commit 成功）；當時工作樹仍 24 M + 多項 untracked → v2.3 已全部閉環。

### P0.7 — Repo 根災後清理（v2.2 新增；v2.3 拆兩子）

- [ ] **P0.7.a** `.json_*.tmp` × 80+ / `.txt_*.tmp` × 20+ 根目錄 orphan 重跑 cleanup + `.git_acl_backup.txt` 外移（v2.3 本輪可落地）
  - 症狀：pytest 期間仍持續產生新 tmp（需排查 `src/cli/utils.py` 是否未走 atomic writer → finally cleanup 分支）
  - 步驟：
    1. `python -c "from src.cli.utils import cleanup_orphan_tmps; cleanup_orphan_tmps()"`（或等效命令）一次清根目錄
    2. grep 定位 pytest 中仍產 tmp 的 test，檢查 atomic writer 的 finally 分支
    3. `.git_acl_backup.txt` → 移至 `D:/Users/Administrator/Desktop/公文ai agent/../_archive/git-acl/` 或加入 `.gitignore`（**不能留根**，低風險 Windows ACL 洩密）
  - commit: `chore: cleanup repo root tmp orphans + move acl backup offsite`

- [ ] **P0.7.b** 災難復原備援目錄去留決策（需先 diff 再定）
  - 範圍：`meta_git/` / `meta_git_live/` / `meta_test/` / `repo_meta/` / `recovered_repo/` / `git_safe/` 共 6 個
  - 步驟：
    1. 對 `.git/` 與每個 meta 目錄做 `git diff` 或 `dircmp`，確認無獨特內容
    2. 有獨特內容 → 寫 `docs/disaster-recovery.md` 記錄
    3. 無獨特內容 → 刪；保留的路徑仍必須在 `.gitignore`（已在）
  - commit: `chore: decommission disaster recovery backup dirs + add disaster-recovery doc`

### 歷史 P0 追蹤（保留紀錄不動）

- [x] **P0.4** 修復 `test_writer_postprocess_adds_inline_citation_and_prunes_unused_refs` 回歸（results.log 01:12:02 二次修復）
- [x] **P0.5.a** 工作樹分組寫入 `docs/commit-plan.md`
- [x] **P0.5.pre** 解除 `.git/index.lock: Permission denied`（v2.2 退役；02:15 `f208ca6` commit 自然驗證）
- [x] **P0.5.b.1** `fix(tests)` 224882b（v2.3 閉環）
- [x] **P0.5.b.2** `fix(kb)` dc86d50（v2.3 閉環）
- [x] **P0.5.b.3** `fix(api)` 0dae75b（v2.3 閉環）
- [x] **P0.5.b.4** `fix(agents)` 96c55cb（v2.3 閉環）
- [x] **P0.5.b.5** `fix(cli)` eab7b8f（v2.3 閉環）
- [x] **P0.5.b.6** `chore` d80a2e6（v2.3 閉環）
- [x] **P0.5.b.7** `.git` ACL foreign deny 解除（v2.3 退役；commits 已落盤即為完成條件達成）
- [x] **P0.5.c** `git status --short` 空 + `pytest tests/` 3543 passed（v2.3 本輪驗證）
- [x] **P0.6** 清 repo tmp orphan + 擴充 `.gitignore`（部分，tmp 仍再生 → 見 P0.7.a）

---

## P1 — 紅線守衛 + Spectra 底座 + 覆蓋率 + Benchmark（v2.3 擴增至 4 項）

> **底層邏輯**：P0 全清完，下一件事必須守紅線（已落）+ 建規格底座 + 拉覆蓋率安全網 + 歸位 benchmark 半成品。四項皆 10-30 分鐘可閉環的「高槓桿」任務，全部解鎖後才有資格大舉推進 Epic 1-4。
> **連續兩輪卡點提醒**：P1.2（T7.2）engineer-log 連續兩輪標「10 分鐘可落地」，連續兩輪落空 → **本輪必須首先收**，不做不准動任何 Epic 新任務。

### 新排序（依槓桿 × 延宕輪次）

- [x] **P1.1（原 T1.5-FAST）** 紅線 1 守衛 — `kb_data/examples/*.md` 155/155 已含 `synthetic: true`（v2.3 閉環；commits `5c2dd0e feat(kb): mark_synthetic.py` + `f527279 chore(kb): 155 份 frontmatter`）

- [x] **P1.2（原 T7.2）** `openspec/config.yaml` 填 project context（**v2.3：連續兩輪延宕，本輪首位**）
  - 現狀：21 行整份 commented out（包含 schema 一行 + 20 行範例），`context:` / `rules:` 皆未填
  - 填入：
    - `context:`（多行字串）
      - 專案定位：真實公開政府公文改寫系統（Gov AI Agent）
      - Tech stack：Python 3.11+ / Ollama (Llama 3.1 8b) / ChromaDB / click CLI / python-docx / Pydantic v2 / litellm
      - Conventions：conventional commits（feat/fix/chore/docs/refactor/test）/ pytest required for new code / 顆粒度：1 小時內可閉環
      - PII 規則：抓回真實公文 commit 前必遮罩（身分證、電話、姓名）
      - 三紅線：真實性（合成 example 必標 `synthetic: true`）/ 改寫而非生成（writer 以「找最相似真實公文 → 最小改動」為主策略）/ 可溯源（每份生成附引用來源段）
    - `rules:`（per-artifact）
      - `proposal`：含 problem / solution / non-goals / acceptance criteria；每份 ≤ 500 字
      - `tasks`：顆粒度 ≤ 2 小時；每任務綁定 commit
  - 驗證：`cat openspec/config.yaml | grep -v "^#" | grep -v "^$" | wc -l ≥ 15`（非註解非空白行 ≥ 15）
  - commit: `docs(spec): fill openspec project context + per-artifact rules`
  - **為何最前**：沒規格底座，Epic 7 T7.1 的 4 個 change proposal 無根基；auto-engineer prompt 也無法注入紅線；連兩輪延宕 = 從技術債升級為誠信問題

- [ ] **P1.3（原 T8.3）** 測試覆蓋率 baseline（**v2.3 從 Epic 8 升 P1**，T8.1 大檔拆分前安全網）
  - `pip install pytest-cov`（若未裝）
  - 跑 `pytest --cov=src --cov-report=json:coverage.json --cov-report=term --cov-report=html:htmlcov`
  - 產出：
    - `docs/coverage.md`：總覆蓋率 / 每個模組覆蓋率 / < 60% 的模組列表 / 建議補測優先級
    - `coverage.json` 入 `.gitignore`；`htmlcov/` 入 `.gitignore`
  - commit: `docs(coverage): quantify baseline coverage + gap analysis`
  - **為何提前**：大檔（`src/cli/kb.py` 1614 / `src/cli/generate.py` 1263 / `src/agents/editor.py` 1065）拆分前必須有 baseline，否則拆完驗不了退化

- [ ] **P1.4（原 T6.0）** Benchmark workstream 歸位（**v2.3 從 Epic 6 升 P1**，半成品收尾）
  - 現況：`scripts/build_benchmark_corpus.py` + `run_blind_eval.py` + `tests/test_benchmark_scripts.py` 齊；`benchmark/mvp30_corpus.json` + 18 份盲測結果落盤但未文件化
  - 產出：
    - `docs/benchmark.md` 說明：工作流 / 輸入 schema / 輸出 schema / 執行命令（`python scripts/run_blind_eval.py --limit 30`）/ 結果解讀
    - `.gitignore` 新增：`benchmark/blind_eval_results.*.json`（產物）；保留 `benchmark/mvp30_corpus.json`（輸入語料需版控）
  - commit: `docs(benchmark): document benchmark workflow + ignore result artifacts`
  - **為何提前**：半成品躺 3 週沒閉環，違反「完成一件事再做下件」原則

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

- [ ] **T1.1.a**（v2.3 降顆粒度）先調研 top-3 來源，產出 `docs/sources-research.md` 首版：`data.gov.tw` / `law.moj.gov.tw` / Executive Yuan RSS。每個含：API endpoint / 資料格式 / 授權條款 / 取得範例 / 資料量估計 / 優先級（1-5）
- [ ] **T1.1.b** 補齊其餘 7 個來源至 10 份（Mohw / Fia / Fda / Pcc / Ppg / 各縣市）— T1.1.a 綠後再做

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
- [ ] **T1.6.a** 校正 `program.md` 合成範例基線數量（現場 `kb_data/examples/*.md` 為 155，不是 156）

---

## Epic 2 — open-notebook 源碼整合（全抄路線，elephant-alpha 驅動）

> **路線決策**：整套 fork [lfnovo/open-notebook](https://github.com/lfnovo/open-notebook) 源碼進本專案，作為改寫引擎骨幹。公文 AI 的 5 agent 審查層保留，疊在 open-notebook 之上。
> v2.1 變更：刪除 `T2.4`（合入 T1.3）；**`T2.3` SurrealDB 遷移凍結**（待 T2.1-T2.2 人工 review 後解凍）；刪除 `T2.10`（upstream sync 等第一階段完成再談）。

### 待辦任務

- [ ] **T2.0.a**（v2.3 拆兩子）`.env` + litellm smoke
  - `.env` 設 `OPENROUTER_API_KEY=<key>`（人工填）+ `LLM_MODEL=openrouter/elephant-alpha`
  - 驗：`python -c "from litellm import completion; r = completion(model='openrouter/elephant-alpha', messages=[{'role':'user','content':'hi'}]); print(r.choices[0].message.content[:80])"` 回非空
  - 產出：`docs/openrouter-smoke.md` 貼命令 + 輸出；commit: `docs(llm): openrouter elephant-alpha smoke verified`

- [ ] **T2.0.b**（v2.3 拆兩子）clone vendor/
  - `git clone https://github.com/lfnovo/open-notebook vendor/open-notebook`
  - `.gitignore` 加 `vendor/`
  - commit: `chore(vendor): add open-notebook as vendored fork target`

- [ ] **T2.1** 研讀 open-notebook 產出 `docs/open-notebook-study.md`：FastAPI routers 地圖 / SurrealDB schema / ask_service 路徑 / 融合切點

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

- [x] **T6.0** → **已升級為 P1.4**（v2.3 升 P1 最前段）；Epic 6 內保留勾選記錄

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

- [x] **T8.3** → **已升級為 P1.3**（v2.3 升 P1 最前段）；Epic 8 內保留勾選記錄以維結構一致

- [ ] **T8.1** 大檔拆分（任一檔超過 800 行即拆，T8.3 完成後才動）
  - `src/cli/kb.py` 1614 行 → 拆成 kb/{ingest,sync,stats,rebuild}.py
  - `src/cli/generate.py` 1263 行 → 拆成 generate/{pipeline,export,cli}.py
  - `src/agents/editor.py` 1065 行 → 拆成 editor/{segment,refine,merge}.py
  - 拆分原則：先拆不改邏輯，commit；再重構，commit

- [ ] **T8.2** Pydantic v2 相容修 1363 條 deprecation warning
  - 鎖定 chromadb 1.x 兼容層 / `src/api/models.py` / `src/core/models.py`
  - 目標：`pytest -W error::DeprecationWarning` 通過

---

## Epic 9 — Repo 衛生（v2.3 新增）

> **底層邏輯**：repo 根 10+ 份頂層歷史 md + 6 個災難復原備援目錄 + 持續再生的 tmp orphan，三輪回顧三次標註，未被任何 Epic 吸收 → 獨立 Epic 管理。

- [ ] **T9.1** 頂層歷史 md 歸位
  - 將以下 10 份移至 `docs/archive/` 或刪（逐一決策）：
    - `IMPROVEMENT_REPORT.md` / `PROJECT_SUMMARY.md` / `BUG_FIX_REPORT.md` / `N8N_INTEGRATION_GUIDE.md` / `MULTI_AGENT_V2_GUIDE.md` / `QUICKSTART.md` / `COLLABORATION_GUIDE.md` / `AI_CODING_RULES.md` / `PRD文件.txt` / `plan.md`（37KB 舊規劃）
  - 保留根目錄僅 `README.md` / `MISSION.md` / `Dockerfile` / `program.md` / `engineer-log.md` / `results.log` / `docs/commit-plan.md`（已在 docs/）
  - commit: `docs(archive): move historical reports to docs/archive + shrink repo root`

- [ ] **T9.2** tmp 再生源頭排查（P0.7.a 後續）
  - 定位 pytest 中持續產 `.json_*.tmp` / `.txt_*.tmp` 的測試路徑
  - 檢查 `src/cli/utils.py` 的 atomic writer finally 分支是否在 exception path 漏清
  - 加 `tests/conftest.py` session-end fixture 自動清 repo 根殘留
  - commit: `fix(utils): close atomic writer cleanup leak in exception paths`

- [ ] **T9.3** `docs/commit-plan.md` 生命週期決策
  - 本輪 v2.2→v2.3 六組 commit 已全部落地，該檔史命完成
  - 選項：移至 `docs/archive/commit-plans/2026-04-20-v2.2-split.md` 保留歷史
  - commit: `docs(archive): commit-plan.md fulfilled history`

---

## 已完成

- [x] **P0.1** CORS localhost 白名單自動展開 127.0.0.1 / ::1（`api_server.py`）
- [x] **P0.2** generate CLI Markdown 編碼回報（`src/cli/generate.py`）
- [x] **P0.3** KnowledgeBaseManager chromadb=None 分流（`src/knowledge/manager.py`）
- [x] **P0.4** writer citation prune / 多來源追蹤語意拆分（`src/agents/writer.py`）
- [x] **P0.6** tmp orphan cleanup + .gitignore 擴充（`src/cli/utils.py` / `tests/test_cli_utils_tmp_cleanup.py`）
- [x] **P0.5.a** 工作樹 commit 分組（`docs/commit-plan.md`）
- [x] **P0.5.pre** git 寫入權限阻斷解除（v2.2 退役；02:15 `f208ca6` commit 自然驗證）
- [x] **P0.5.b.1** `fix(tests)` 224882b — benchmark scripts + cli utils tmp cleanup 測試（v2.3 閉環）
- [x] **P0.5.b.2** `fix(kb)` dc86d50 — chromadb=None + lazy import（v2.3 閉環）
- [x] **P0.5.b.3** `fix(api)` 0dae75b — CORS loopback / workflow route / web preview（v2.3 閉環）
- [x] **P0.5.b.4** `fix(agents)` 96c55cb — writer postprocess / template / editor / style / compliance（v2.3 閉環）
- [x] **P0.5.b.5** `fix(cli)` eab7b8f — minimax provider / config guard / encoding / tmp cleanup（v2.3 閉環）
- [x] **P0.5.b.6** `chore` d80a2e6 — program v2.1 + engineer-log + commit-plan + gitignore（v2.3 閉環）
- [x] **P0.5.b.7** `.git` ACL foreign deny 已解（v2.3 退役；commits 全落盤即完成條件）
- [x] **P0.5.c** 工作樹空 + 3543 tests passed（v2.3 本輪驗證通過）
- [x] **P1.1 (T1.5-FAST)** 紅線 1 守衛 155/155 synthetic frontmatter（`5c2dd0e` + `f527279`，v2.3 閉環）
- [x] **P1.2 (T7.2)** openspec project context + per-artifact rules 已填入 `openspec/config.yaml`（v2.3 閉環）

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

**版本**：v2.3（2026-04-20 03:45 技術主管第三輪回顧重排）| **下一次重排觸發**：P1.2 (T7.2) + P1.3 (T8.3) + P1.4 (T6.0) 三件 10-30 分鐘任務全落，且 Epic 1 `T1.1.a` + Epic 2 `T2.0.a` 任一啟動
