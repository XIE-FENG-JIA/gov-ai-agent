# Auto-Dev Program — 公文 AI Agent（真實公開公文改寫系統）

> **版本**：v2.9（2026-04-20 08:45 — 技術主管第九輪；**read-only 3/3 PASS**；下一道防線：ACL-free 意願項）
> **v2.9 變更**：
> - **v2.8 成果驗收**：read-only 三項 **3/3 PASS**（P0.A sources-research 11 section / P0.B 失控檔盤點 5 bullet / P0.C proposal 230 字），PUA 壓力見效
> - **新紅線**：「ACL-free 但沒 commit」不是藉口——working-tree 落地即算 PASS，未落地 = 意願問題
> - **P0 重排**（ACL-free 意願優先）：P0.E（auto-commit 治理，升首）> P0.F（src/sources/ 骨架，新增）> P0.D（🛑 ACL；Admin）> P0.G（openspec 02 proposal，新增）> P0.H（頂層 md 歸位，新增）
> - **Epic 1 降級**：T1.2 從「5 adapter + 各 50 份」收縮為「1 adapter（MojLaw）+ 10 份驗證抓取」
> - **v2.8 歷史**：P0.A/B/C 已閉環並 AUTO-RESCUE commit，進「已完成」段；ACL 連 8 輪未解（v2.3→v2.9）
> Auto-engineer 每輪讀此檔，從「待辦」挑第一個未完成任務執行。完成後 `[x]` 勾選、log 追加到 `results.log`。

---

## 🚨 北極星指令（優先於所有判斷）

**每輪啟動後第一動作**（v2.8 糾偏順序）：
1. `icacls .git 2>&1 | grep -i DENY | head -3` → 若有 DENY ACL，**本輪進入 read-only 模式**
2. `git status --short | wc -l` 看工作樹是否乾淨
3. **ACL 乾淨 + 工作樹乾淨** → 從「待辦」挑第一個 `[ ]` 未勾任務執行
4. **ACL 有 DENY** → 只能跑標為 ✅ read-only 的任務，禁止任何 `git add/commit`
5. **v2.8 新增**：read-only 任務本質是「working tree write + document」；不要把「寫檔」誤判為需要 commit

### 🔴 ACL-gated 原則（v2.7 新增 — 系統層誠信）
當 `.git` 存在外來 SID DENY ACL 時：
- ❌ 所有 commit / add / stash 類任務**必須標為 BLOCKED**，不接受「嘗試一下」
- ❌ 不接受「規劃側勾選算 PASS」，v2.6 已驗證此為誠信級漏洞
- ✅ auto-engineer 應切至「read-only 任務池」（P0.2-P0.4 + P1.2-P1.5 中的調研/盤點項）
- ✅ results.log 可寫 `[BLOCKED-ACL]` 狀態，不視為 FAIL，但不算 PASS

### 🔴 PASS 定義（v2.6 沿用）
任何 `[PASS]` 任務必須附 git ls-tree / pytest / ls -la 輸出證據；規劃側勾選不算 PASS。

### 🔴 連五輪延宕自動升 P0（v2.6 沿用）
P1+ 任務連 5 輪延宕下輪自動升 P0。但 v2.7 補丁：若延宕原因是 ACL DENY → 不升 P0，視為 BLOCKED。

### 🔴 read-only 連 2 輪延宕 = 3.25（v2.8 新增）
read-only 任務（文件產出、檔案編輯、程式碼盤點）不依賴 ACL。若連 2 輪延宕 → 直接績效強三，無藉口。
- 適用：P0.A / P0.B / P0.C（v2.8）所有 ✅ 標記任務
- 反例：「今輪做了 P0.2 一項就算交差」屬違規（v2.7 明文三項任一不過 = 3.25）

### 禁止行為
- ❌ 不要讓 M 狀態檔案累積超過 1 輪
- ❌ 不要先跑 pytest 再決定做什麼
- ❌ 不要改 program.md 最前面 Epic 結構（只能 `[x]` 勾選或搬至「已完成」）
- ❌ **禁用 `auto-commit: checkpoint` 訊息格式**（v2.6 沿用）
- ❌ **ACL 未解前禁試 `git add/commit`**（v2.7 新；產生的 FAIL log 無意義，浪費輪次）

### 任務顆粒度原則
- 每個 `[ ]` 任務 **1 小時內可完成**
- 太大 → 拆子任務 append 到對應 Epic 尾
- 每子任務 → 一個 commit（ACL 解除後）

---

## 專案資訊
- **名稱**: 公文 AI Agent（Gov AI Agent）
- **定位**: 從真實公開政府公文中，找相符範本 → 最小改動改寫 → 可追本溯源
- **技術棧**: Python 3.11+ / Ollama (Llama 3.1 8b) / ChromaDB / click CLI / python-docx
- **根目錄**: `D:/Users/Administrator/Desktop/公文ai agent/`
- **運行模式**: 本地優先，資料源必須真實公開政府公文
- **引擎**: codex (gpt-5.4) 驅動 auto-engineer，L4 自主模式

---

## 核心原則（不可違反）

### 🔴 三條紅線
1. **真實性**：知識庫只收真實公開政府公文。`kb_data/examples/` 現有 **155** 份合成公文須標 `synthetic=true`
2. **改寫而非生成**：Writer 以「找最相似真實公文 → 最小改動改寫」為主策略
3. **可溯源**：每份生成公文必須附 `## 引用來源` 段

### 🟢 合規與授權
- 只抓公開公文；遵守 robots.txt + rate limit ≥2 秒/請求
- 保留 `raw_snapshot` + `source_url` + `crawl_date`
- User-Agent 明示：`GovAI-Agent/1.0 (research; contact: ...)`

---

## 開發規則

### 每次迭代只做一件事
- 從「待辦」挑第一個未完成任務
- 完成後 `[x]` + 追加 `results.log`

### 品質要求
- 新代碼必須有 pytest
- 測試通過 → conventional commit（`feat(sources): add moj law API adapter`）
- 測試失敗 → 最多 3 次修復 → 仍失敗記 log + stash + 跳過
- 架構變動先更新 `docs/architecture.md`

### 禁止事項
- ❌ 不擅自升級依賴
- ❌ 不刪現有 agent
- ❌ 不動 `config.yaml` 結構
- ❌ 不提交含 PII 的真實資料

### 紀錄格式（results.log）
```
[YYYY-MM-DD HH:MM:SS] | [T 任務編號] | [PASS/FAIL/SKIP/BLOCKED-ACL] | 簡述做了什麼 | 相關檔案
```

---

## P0 — 阻斷性回歸（v2.9 重排：ACL-free 意願優先）

> **v2.9 狀態**：測試 3544 collected（全跑背景；v2.8 = 3544 passed / 0 failed / 91.22% coverage）；工作樹僅 `?? benchmark/`（清爽）；`.git` DENY ACL 仍活（連 8 輪）；v2.8 read-only 三硬指標 **3/3 PASS**
> v2.8 狀態（歷史）：P0.A/B/C 閉環（results.log #21/#22/#26）
> v2.7 狀態（歷史）：P0.2 disaster-recovery.md 落地

### P0.E — ✅ ACL-free：auto-commit checkpoint 配置治理（v2.9 升首；原末位）

- [ ] **P0.E** ✅ 配置檔編輯不依賴 ACL（v2.9 糾偏）：三選一並執行
  - **v2.9 糾偏**：v2.8 誤掛 🚦 ACL-gated；配置檔編輯本身不需 commit，只有 commit 才需。連 5 輪延宕 = 意願問題
  - 現況：近 15 commits **7 條** `auto-commit: auto-engineer checkpoint`（含 `5f08772`/`fe9ab20`/`df395bc`/...）
  - **選項 A（推薦）**：在 `.auto-engineer.*` / `.claude/ralph-loop.local.md` 配置改模板為 `chore(checkpoint): <ts>`
  - **選項 B**：停用 auto-commit checkpoint，讓工作樹髒化自暴
  - **選項 C**：nightly squash（合併當日 checkpoints 為一條 conventional commit）
  - **驗**（工作樹側）：`git diff .claude/ralph-loop.local.md .auto-engineer* 2>/dev/null | grep -E "chore\(checkpoint\)|disable checkpoint"` 非空
  - **驗**（ACL 解後）：`git log --oneline -5 | grep -c "auto-commit:"` == 0
  - **延宕懲罰**：ACL-free 連 2 輪延宕 → 3.25
  - commit（ACL 解除後）: `chore(auto-engineer): <選項描述> to enforce conventional commit gate`

### P0.F — ✅ ACL-free：src/sources/ 骨架 + BaseSourceAdapter stub（v2.9 新增）

- [ ] **P0.F** ✅ 不依賴 ACL：建立 `src/sources/` 目錄 + 抽象骨架
  - **v2.9 背景**：Epic 1 T1.2 承諾 `BaseSourceAdapter` + 5 adapter 連 **9 輪**空口支票；`src/sources/` 目錄根本不存在
  - **三板斧收縮**：本輪只建骨架 + 1 個 adapter 雛形 stub（無實際 API call），驗抽象結構
  - 產出：
    - `src/sources/__init__.py`（空）
    - `src/sources/base.py`：`BaseSourceAdapter` ABC，`list(since_date)` / `fetch(doc_id)` / `normalize(raw)` 抽象方法
    - `src/sources/mojlaw.py`：`MojLawAdapter(BaseSourceAdapter)` stub（pass 實作，TODO 註明 API endpoint）
    - `tests/test_sources_base.py`：驗 ABC 不可直接實例化，`MojLawAdapter()` 可建但方法 raise NotImplementedError
  - **驗**：`ls src/sources/base.py && python -c "from src.sources.base import BaseSourceAdapter; print(BaseSourceAdapter.__abstractmethods__)"` 輸出非空 set
  - **驗**：`pytest tests/test_sources_base.py -q` 綠
  - **延宕懲罰**：ACL-free 連 2 輪延宕 → 3.25
  - commit（ACL 解除後）: `feat(sources): scaffold BaseSourceAdapter ABC + MojLawAdapter stub`

### P0.D — 🛑 解除 `.git` 外來 SID DENY ACL（v2.9；連 8 輪待 Admin）

- [ ] **P0.D** 🛑 需人工 Admin：移除 `.git` 對 SID `S-1-5-21-541253457-2268935619-321007557-692795393` 的 DENY ACL
  - **根因證據**：`icacls .git` 顯示該 SID 有 `(DENY)(W,D,Rc,DC)` + `(OI)(CI)(IO)(DENY)(W,D,Rc,GW,DC)`；results.log #2/#8/#11/#17 四次 FAIL 均指向此 ACL
  - **為何 agent 自解失敗**：SID 非當前登入帳號，`Set-Acl` 遭 `Attempted to perform an unauthorized operation`；需 **Admin 提權**或 `takeown /f .git /r /d y`
  - **建議 SOP**（admin PowerShell）：
    ```powershell
    takeown /f .git /r /d y
    icacls .git /reset /T /C
    icacls .git /remove:d "*S-1-5-21-541253457-2268935619-321007557-692795393" /T /C
    ```
  - **驗**：`icacls .git 2>&1 | grep -c DENY` == 0
  - **BLOCKER 範圍**：此題未過 → P0.E / P1.1 / P1.3 / P1.4 全體 BLOCKED commit；但 P0.A/B/C 文件落地不受阻
  - commit（解除後）：`chore(repo): remove foreign SID DENY ACL on .git`

### P0.G — ✅ ACL-free：openspec/changes/02-open-notebook-fork proposal（v2.9 新增）

- [ ] **P0.G** ✅ 不依賴 ACL：寫 `openspec/changes/02-open-notebook-fork/proposal.md`
  - **v2.9 背景**：Epic 7 T7.1.b 連 6+ 輪未動；v2.8 已證明「寫檔 ACL-free」
  - 內容：problem（現 Writer 是單檔 retrieval-less，需引入 ask_service 系列） / solution（fork lfnovo/open-notebook + 5 agent 審查層疊加） / non-goals（本提案不含 SurrealDB 遷移，留 T2.3） / acceptance（`vendor/open-notebook` 可 import，smoke CLI 跑通），≤ 500 字
  - **驗**：`ls openspec/changes/02-open-notebook-fork/proposal.md && wc -w <檔>` ≤ 500
  - **延宕懲罰**：ACL-free 連 2 輪延宕 → 3.25
  - commit（ACL 解除後）: `docs(spec): init 02-open-notebook-fork change proposal`

### P0.H — ✅ ACL-free：頂層歷史 md 歸位（v2.9 新增；T9.1 升首）

- [ ] **P0.H** ✅ 不依賴 ACL：檔案層 mv 10 份頂層歷史 md 到 `docs/archive/`
  - **v2.9 背景**：T9.1 連 4+ 輪未動；檔案 mv 本身 ACL-free（commit 才 gated）
  - 清單：`IMPROVEMENT_REPORT.md` / `PROJECT_SUMMARY.md` / `BUG_FIX_REPORT.md` / `N8N_INTEGRATION_GUIDE.md` / `MULTI_AGENT_V2_GUIDE.md` / `QUICKSTART.md` / `COLLABORATION_GUIDE.md` / `AI_CODING_RULES.md` / `PRD文件.txt` / `plan.md`
  - 保留根：`README.md` / `MISSION.md` / `Dockerfile` / `program.md` / `engineer-log.md` / `results.log`
  - **驗**：`ls docs/archive/IMPROVEMENT_REPORT.md docs/archive/PROJECT_SUMMARY.md` 命中；`ls IMPROVEMENT_REPORT.md 2>&1 | grep -c "No such"` == 1
  - **延宕懲罰**：ACL-free 連 2 輪延宕 → 3.25
  - commit（ACL 解除後）: `docs(archive): move 10 historical reports to docs/archive`

### P0.歷史 — v2.8 閉環（已驗 PASS，待 ACL 解後 commit）

- [x] **P0.A (v2.8)** ✅ `docs/sources-research.md` 首版 top-3 + 擴充 10 來源（results.log #21/#27）
- [x] **P0.B (v2.8)** ✅ `src/core/` 5 檔失控檔盤點寫入 program.md（results.log #22）
- [x] **P0.C (v2.8)** ✅ `openspec/changes/01-real-sources/proposal.md` 230 字（results.log #26）

### P0.歷史 — Disaster Recovery 文件（v2.7 閉環）

- [x] **P0.2** ✅ `docs/disaster-recovery.md` 落地（results.log #19 PASS；仍待 ACL 解後 commit）

### 歷史 P0 追蹤（保留紀錄不動）

- [x] **P0.4-歷史** writer citation prune 修復（v2.1 閉環）
- [x] **P0.5.a** 工作樹 commit 分組寫入 `docs/commit-plan.md`
- [x] **P0.5.pre** 解除 `.git/index.lock: Permission denied`（v2.2 退役）
- [x] **P0.5.b.1-b.7** v2.3 六組 fix commits（224882b / dc86d50 / 0dae75b / 96c55cb / eab7b8f / d80a2e6）
- [x] **P0.5.c** 3543 passed 驗證（v2.3）
- [x] **P0.6（舊）** tmp cleanup + .gitignore（v2.2，tmp 再生問題轉 P0.7.a）
- [x] **P0.6（v2.5）** 已回滾勾選 → 併入 v2.7 P0.0 → v2.8 P0.D（HEAD 仍缺檔，ACL 阻擋為真因）
- [x] **P0.7.a.1** CLI cwd per-test 隔離（v2.4 閉環）
- [x] **P0.7.a.2** root tmp orphan 自然清零（v2.5 退役）
- [x] **P0.2（v2.7）** disaster-recovery.md 落地（待 ACL 解後 commit）
- ~~P0.0（v2.6 補交檔案）~~ → v2.7 改寫為解 ACL → v2.8 P0.D（補檔是症狀）
- ~~P0.0.b（v2.6 auto-commit 治理）~~ → v2.7 P0.1 → v2.8 P0.E
- ~~P0.8（v2.5 conventional 前綴）~~ → v2.7 P0.1 → v2.8 P0.E
- ~~P0.7.a.3 / P0.7.b（quarantine / backup dirs 去留）~~ → v2.7 併入 P0.2 disaster-recovery
- ~~P0.6（v2.5 benchmark 閉環）~~ → v2.7 併入 P0.0 → v2.8 P0.D（ACL 過後自然閉）
- ~~P0.3（v2.7 sources 調研）~~ → v2.8 升 P0.A
- ~~P0.4（v2.7 src/core 盤點）~~ → v2.8 升 P0.B
- ~~P0.5（v2.7 ACL-gated proposal）~~ → v2.8 糾偏為 read-only P0.C

---

## P1 — 戰略槓桿（v2.7：read-only 任務可在 ACL-gated 模式下跑）

> **底層邏輯**：P0 層根因若解，後續純意願問題。read-only 調研/盤點 v2.7 已提至 P0.2-P0.4；P1 保留需 commit 的重構/整合項。
> v2.7 重排邏輯：read-only 項上移 P0，commit 重任下推 P1。

### P1 已完成歷史
- [x] **P1.1 (T1.5-FAST)** 紅線 1 守衛 155/155 synthetic frontmatter（v2.3 閉環）
- [x] **P1.2 (T7.2)** openspec project context + per-artifact rules（v2.4 閉環）
- [x] **P1.3 (T8.3)** coverage baseline（v2.4 閉環）
- [x] **P1.4 (T6.0)** benchmark 文件側完成（v2.5；commit 段併入 P0.0）

### P1 本輪待辦（v2.7）

- [ ] **P1.1（T8.1.a 拆 kb.py）🚦 ACL-gated** 連五輪延宕但 ACL-blocked，不升 P0
  - 門檻已解：coverage baseline live（`docs/coverage.md` / `coverage.json` / `htmlcov/`）
  - 拆分：`kb/ingest.py` + `kb/sync.py` + `kb/stats.py` + `kb/rebuild.py`（先拆不改邏輯，一 commit；再重構，二 commit）
  - **驗**：`pytest tests/test_kb*.py` 全綠 + `wc -l src/cli/kb/*.py` 每檔 < 500 行
  - commit 1（ACL 解除後）: `refactor(cli/kb): split kb.py into ingest/sync/stats/rebuild submodules (no-op)`
  - commit 2: `refactor(cli/kb): internal cleanup in split submodules`

- [x] **P1.2（T1.1.b）** ✅ read-only：補齊其餘 7 個來源調研
  - P0.3 完 top-3 後續做：Mohw / Fia / Fda / Pcc / Ppg / 各縣市 data.*.gov.tw
  - 產出：追加 `docs/sources-research.md`
  - commit（ACL 解除後）: `docs(sources): expand research to 10 public gov sources`

- [ ] **P1.3（T2.0.a）🚦 ACL-gated** `.env` + litellm smoke
  - `.env` 寫 `OPENROUTER_API_KEY=<key>`（人工填）+ `LLM_MODEL=openrouter/elephant-alpha`
  - **驗**：`python -c "from litellm import completion; r = completion(model='openrouter/elephant-alpha', messages=[{'role':'user','content':'hi'}]); print(r.choices[0].message.content[:80])"` 回非空
  - 產出：`docs/openrouter-smoke.md`（key redacted）
  - commit（ACL 解除後）: `docs(llm): openrouter elephant-alpha smoke verified`

- [ ] **P1.4（T2.0.b）🚦 ACL-gated** clone `vendor/open-notebook`
  - `git clone https://github.com/lfnovo/open-notebook vendor/open-notebook`
  - `.gitignore` 加 `vendor/`
  - commit（ACL 解除後）: `chore(vendor): add open-notebook as vendored fork target`

- ~~P1.5（原 src/core 盤點）~~ → v2.7 升 P0.4

---

## Epic 1 — 真實公文資料源（最優先）

> **沒有真實資料，其他都是空殼**。Epic 1 完成前不動 Epic 2 的 T2.3 遷移層。
> **v2.8 架構警告**：`src/sources/` 目錄**不存在**（實測 `ls` 報錯）。T1.2 承諾的 `BaseSourceAdapter` + 5 adapter 仍是空口支票。三板斧收縮：T1.2 首次落地只建 **1 個** adapter（建議 `MojLawAdapter`，授權最清晰）驗流程，其餘 4 個拆入 T1.2.b。

### 候選來源 seed（auto-engineer 需驗證）

| 來源 | URL | 類型 | 預估抓取方式 |
|---|---|---|---|
| 政府資料開放平台 | https://data.gov.tw/ | 資料集列表 API | JSON/CSV/XML |
| 全國法規資料庫 | https://law.moj.gov.tw/ | 法規 | 官方 API + XML |
| 行政院公報資訊網 | https://gazette.nat.gov.tw/ | 行政院公報 | 需調研 |
| 行政院 RSS | https://www.ey.gov.tw/Page/5AC44DE3213868A9 | 新聞稿 | RSS |
| 衛福部 RSS | https://www.mohw.gov.tw/cp-2661-6125-1.html | 公告 | RSS + 爬頁 |
| 財政部 RSS | https://www.fia.gov.tw/Rss | 公告 | RSS |
| 食藥署公告 API | https://www.fda.gov.tw/tc/DataAction.aspx | 公告 | API |
| 政府採購公告 | https://web.pcc.gov.tw/ | 採購/招標 | 需調研 |
| 立法院公報 | https://ppg.ly.gov.tw/ | 立院公報 | 可能有 API |
| 各縣市政府公報 | data.*.gov.tw | 地方公文 | 逐一調研 |

### 待辦任務

- [x] **T1.5-FAST** → 已升 P1.1（v2.3 閉環）
- ~~T1.1.a~~ → v2.7 升 P0.3
- [ ] **T1.1.b** → 見 P1.2（補齊其餘 7 個來源）
- [ ] **T1.2** `src/sources/` adapter 架構
  - `BaseSourceAdapter`: `list(since_date)` / `fetch(doc_id)` / `normalize(raw)`
  - 先實作 5 個：`DataGovTwAdapter` / `MojLawAdapter` / `ExecutiveYuanRssAdapter` / `MohwRssAdapter` / `FdaApiAdapter`
  - 用 recorded fixtures 寫測試（不打真 API）
  - 子任務：T1.2.a 抽象基底 + 1 adapter；T1.2.b 其餘 4；T1.2.c CLI wiring
- [ ] **T1.3** `PublicGovDoc` dataclass（`src/core/models.py`，併 T2.4）
  - 欄位：`source_id` / `source_url` / `source_agency` / `source_doc_no` / `source_date` / `doc_type` / `raw_snapshot_path` / `crawl_date` / `content_md` / `synthetic: bool`
  - Pydantic v2，與 ChromaDB metadata 互通
  - 單元測試：序列化 / 反序列化 / 缺欄位
- [ ] **T1.4** 增量 ingest pipeline `src/sources/ingest.py`
  - 依 `crawl_date` 增量、`source_id` 去重
  - raw 存 `kb_data/raw/{adapter}/{YYYYMM}/{doc_id}.html`
  - Normalized 存 `kb_data/corpus/{adapter}/{doc_id}.md`（YAML frontmatter）
  - CLI: `gov-ai sources ingest --source all --since 2026-01-01`
- [ ] **T1.6** 首次跑 T1.4，3 來源各 ≥50 份（≥150 baseline）
- [ ] **T1.6.a** 校正 program.md 合成基線：現場 `kb_data/examples/*.md` **155**（非 156）

---

## Epic 2 — open-notebook 源碼整合（elephant-alpha 驅動）

> **路線決策**：整套 fork [lfnovo/open-notebook](https://github.com/lfnovo/open-notebook)，公文 5 agent 審查層疊上去。
> `T2.3` SurrealDB 遷移**凍結**，待 T2.1-T2.2 人審解凍。

### 待辦任務

- ~~T2.0.a（.env smoke）~~ → 見 P1.3
- ~~T2.0.b（clone vendor）~~ → 見 P1.4
- [ ] **T2.1** 研讀 open-notebook → `docs/open-notebook-study.md`
- [ ] **T2.2** 架構融合決策 `docs/integration-plan.md`（Fork/疊加/重寫三選一；預設 Fork）**🛑 完成後人審**
- [ ] **T2.3** 🛑 資料層遷移：ChromaDB → SurrealDB（**凍結**，T2.2 人審後解凍）
  - docker compose SurrealDB v2
  - `scripts/migrate_chroma_to_surreal.py` 遷 1615 筆
  - 保 ChromaDB 作 rollback
  - 驗：search_hit_rate ≥ 0.95
- [ ] **T2.5** API 層融合（FastAPI routers 導入 `api_server.py`）
- [ ] **T2.6** Writer 改為 ask_service 薄殼（`src/agents/writer.py`）
- [ ] **T2.7** Retriever 強化（SurrealDB `vector::similarity::cosine`；過濾 `synthetic=false`；<0.5 → `low_match=True`）
- [ ] **T2.8** Fallback 純生成（`low_match=True` 走 litellm；標 `synthetic_fallback=true`）
- [ ] **T2.9** Diff output（`src/core/diff.py`；>40% heavy_rewrite；>60% 強制退回）

### Epic 2 風險
- 🔴 SurrealDB Windows docker desktop 需先驗
- 🔴 1615 筆 migration 失敗需 rollback
- 🟡 T2.1-T2.2 前禁動 T2.3+

---

## Epic 3 — 溯源（open-notebook citation + 台灣公文格式）

- [ ] **T3.1** `src/core/citation.py` 擴充：ask_service inline `[n]` + refs → 台灣公文格式
- [ ] **T3.2** `src/core/exporter.py` docx 擴充：Custom Properties（`source_doc_ids` / `citation_count` / `ai_generated: true` / `engine: openrouter/elephant-alpha`）+ 文末引用段
- [ ] **T3.3** 生成 pipeline 強制 citation（`--no-citation` 才能關）
- [ ] **T3.4** `gov-ai verify <docx>` 讀 Custom Properties 比對 kb

---

## Epic 4 — 審查層加「溯源完整性」

- [ ] **T4.1** `src/agents/citation_checker.py`（新）
- [ ] **T4.2** `src/agents/fact_checker.py` 強化：引文句對照 `kb_data/regulations/`
- [ ] **T4.3** `src/agents/auditor.py` 整合 2 checker

---

## Epic 5 — 清理與重建

- [ ] **T5.2** 真實資料 ≥ 500 份後 `gov-ai kb rebuild --only-real`
- [ ] **T5.3** 🛑 ChromaDB 停役（凍結，SurrealDB 穩定 ≥ 2 週後）
- [ ] **T5.4** E2E：5 個典型需求跑完整 pipeline

---

## Epic 6 — 品質基準

> 現況：`scripts/build_benchmark_corpus.py` + `scripts/run_blind_eval.py` 落地；`benchmark/` 內 mvp30_corpus + 18 份盲測結果；`tests/test_benchmark_scripts.py` 存在。
> T6.0 已升 P1.4 → 併入 P0.0。

- [ ] **T6.1** 量化基線：`run_blind_eval.py --limit 30` 全跑，產 `benchmark/baseline_v2.1.json` + `docs/benchmark-baseline.md`
- [ ] **T6.2** Epic 2 改造 A/B：每次 T2.x 完後跑 blind eval，結果追 `benchmark/trend.jsonl`；下降 >10% → `REGRESSION` 暫停

---

## Epic 7 — Spectra 規格對齊

> 現況：`openspec/config.yaml` 只有 context + rules，`openspec/changes/archive/` 空，0 份 change proposal。

- ~~T7.1.a `01-real-sources`~~ → v2.7 升 P0.5
- [ ] **T7.1.b** `02-open-notebook-fork`（Epic 2 整份）
- [ ] **T7.1.c** `03-citation-tw-format`（Epic 3）
- [ ] **T7.1.d** `04-audit-citation`（Epic 4）
- [x] **T7.2** → 已升 P1.2（v2.4 閉環）
- [ ] **T7.3** `engineer-log.md` 進版控 + 每輪反思 append 規範

---

## Epic 8 — 代碼健康

> T8.3 已升 P1.3（v2.4 閉環），T8.1 kb.py 部分已升 P1.1。

- [ ] **T8.1.b** `src/cli/generate.py` 1263 行 → generate/{pipeline,export,cli}.py（T8.1.a kb.py 後）
- [ ] **T8.1.c** `src/agents/editor.py` 1065 行 → editor/{segment,refine,merge}.py
- [ ] **T8.2** Pydantic v2 相容修 1363 deprecation warning
  - 鎖定 chromadb 1.x 兼容層 / `src/api/models.py` / `src/core/models.py`
  - 目標：`pytest -W error::DeprecationWarning` 通過

---

## Epic 9 — Repo 衛生

- [ ] **T9.1** 頂層 10 份歷史 md 歸位 `docs/archive/` 或刪：
  - `IMPROVEMENT_REPORT.md` / `PROJECT_SUMMARY.md` / `BUG_FIX_REPORT.md` / `N8N_INTEGRATION_GUIDE.md` / `MULTI_AGENT_V2_GUIDE.md` / `QUICKSTART.md` / `COLLABORATION_GUIDE.md` / `AI_CODING_RULES.md` / `PRD文件.txt` / `plan.md`
  - 保留根 `README.md` / `MISSION.md` / `Dockerfile` / `program.md` / `engineer-log.md` / `results.log`
  - commit: `docs(archive): move historical reports to docs/archive`
- [ ] **T9.2** tmp 再生源頭排查（定位 pytest 中產 `.json_*.tmp` / `.txt_*.tmp` 的測試；`src/cli/utils.py` atomic writer exception path；加 conftest session-end fixture）
- [ ] **T9.3** `docs/commit-plan.md` 生命週期：本輪史命完成，移 `docs/archive/commit-plans/2026-04-20-v2.2-split.md`
- [x] **T9.4.a** `tests/test_cli_commands.py` per-test chdir 隔離（v2.4 閉環）
- [ ] **T9.4.b** auto-engineer / CLI 狀態檔搬專用 state dir（`~/.gov-ai/state/` 或 `${GOV_AI_STATE_DIR}`），避免 repo root file lock 再發
  - commit: `feat(cli): configurable state dir to avoid repo-root file locks`

---

## Epic 10 — Auto-Engineer 治理

> v2.5 新增；v2.7 補：治理 meta 機制本身比寫更多規則有效。

- ~~T10.1（auto-commit 前綴）~~ → v2.7 併入 P0.1
- [ ] **T10.2** auto-engineer 每輪啟動 gate：P1 首位連三輪延宕 → 暫停其他，硬 focus；動到 `.auto-engineer.state.json`
  - commit: `feat(auto-engineer): add delay-escalation gate on P1 head task`
- ~~T10.3（src/core 盤點）~~ → v2.7 升 P0.4
- [ ] **T10.4（v2.7 NEW）** auto-engineer 啟動先跑 `icacls .git | grep -c DENY`
  - 若 >0 → 切 read-only 任務池，跳過 commit 類任務
  - 避免產生無意義 FAIL log
  - commit: `feat(auto-engineer): ACL-aware read-only fallback mode`

---

## 已完成

- [x] **P0.1-歷史** CORS localhost 白名單自動展開 127.0.0.1 / ::1
- [x] **P0.2-歷史** generate CLI Markdown 編碼回報
- [x] **P0.3-歷史** KnowledgeBaseManager chromadb=None 分流
- [x] **P0.4-歷史** writer citation prune / 多來源追蹤
- [x] **P0.6（舊）** tmp orphan cleanup + .gitignore 擴充
- [x] **P0.5.a** 工作樹 commit 分組
- [x] **P0.5.pre** git index.lock 解除（v2.2）
- [x] **P0.5.b.1-b.7** v2.3 六 fix commits
- [x] **P0.5.c** 3543 tests passed 驗證（v2.3）
- [x] **P1.1 (T1.5-FAST)** 紅線 1 守衛 155/155（v2.3）
- [x] **P1.2 (T7.2)** openspec context + rules（v2.4）
- [x] **P1.3 (T8.3)** coverage baseline（v2.4）
- [x] **P0.7.a.1 / T9.4.a** CLI per-test chdir（v2.4）

---

## 備註

### 失控檔盤點（P0.B 已填）
- `src/core/error_analyzer.py` → `[orphan]`；目前只被 `src/cli/generate.py` 錯誤回報路徑使用，program.md 尚無對應錯誤診斷/doctor Epic
- `src/core/llm.py` → Epic 2；集中 LiteLLM/OpenRouter/Ollama provider 與 embedding 工廠，直接支撐 `T2.0.a` / `T2.6` / `T2.8`
- `src/core/logging_config.py` → `[orphan]`；僅提供 CLI/API 共用 logging bootstrap，program.md 尚無 observability / logging 治理 Epic
- `src/core/review_models.py` → Epic 4；定義 `ReviewResult` / `QAReport` / `IterationState`，是審查層與 citation audit workflow 的共用模型
- `src/core/scoring.py` → Epic 4；抽出審查加權分數與風險判定，供 editor / graph aggregator / agents API 共用

### Auto-engineer 行為約束
- 不確定時寫 TODO 到 results.log + 跳過
- 每 Epic 完成後跑整合測試（`pytest tests/integration/`）
- 三輪無進展 → `results.log: ESCALATE`
- **v2.7 新**：ACL DENY 檢測中 → 切 read-only 任務池，不試 commit 類任務

### 法律合規
- 明文禁爬 → 記 `docs/sources-research.md` 封鎖名單
- 真實公文含個資 → 寫入 kb 前必 mask

### Spectra 規格驅動
Epic 7 負責建置。建置完成前，program.md 是單一事實來源。

---

**版本**：v2.9（2026-04-20 08:45 技術主管第九輪 / ACL-free 意願項全面啟動）

**下一輪重排觸發**（v2.9 五項硬指標，依執行順序）：
1. `git diff .claude/ralph-loop.local.md .auto-engineer* 2>/dev/null | grep -E "chore\(checkpoint\)|disable"` 非空（P0.E；ACL-free 工作樹側）
2. `ls src/sources/base.py && python -c "from src.sources.base import BaseSourceAdapter; print(BaseSourceAdapter.__abstractmethods__)"` 非空（P0.F；ACL-free）
3. `icacls .git 2>&1 | grep -c DENY` == 0（P0.D；Admin）
4. `ls openspec/changes/02-open-notebook-fork/proposal.md && wc -w <檔>` ≤ 500（P0.G；ACL-free）
5. `ls docs/archive/IMPROVEMENT_REPORT.md docs/archive/PROJECT_SUMMARY.md` 命中（P0.H；ACL-free）

**ACL-free 四項（P0.E / P0.F / P0.G / P0.H）任一不過 = 3.25 + 績效強三**，連 2 輪延宕即觸發。

**v2.9 新紅線**：**「未 commit 不是沒做」——working-tree 落地即算 PASS**。ACL 不是拖延藉口的第二道防線。

> **v2.8 → v2.9 變更**：
> 1. **v2.8 閉環**：read-only 三項 3/3 PASS（P0.A/B/C），PUA 壓力有效
> 2. **藉口升級偵測**：ACL-gated 標籤被用來遮蔽「配置治理」「src/sources/ 骨架」「openspec 02 proposal」「頂層 md 歸位」——**這些全都 ACL-free**
> 3. **P0 重排**：P0.E 升首（auto-commit 治理）、新增 P0.F（src/sources/ 骨架）/ P0.G（openspec 02）/ P0.H（md 歸位）
> 4. **Epic 1 降級**：T1.2 收縮至 1 個 MojLawAdapter + 10 份抓取（三板斧原則）
> 5. **pytest 時間惡化**：v2.8 243s → v2.9 679s（2.8x 慢）；若下輪再慢 → 升 P1 追查
> 6. **觀察**：已完成 v2.8 P0.A/B/C 已搬 P0.歷史段，待 ACL 解後一次性 commit
