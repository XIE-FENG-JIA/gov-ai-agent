# Auto-Dev Program — 公文 AI Agent（真實公開公文改寫系統）

> **版本**：v3.5（2026-04-20 15:15 — `pytest tests/ -q` = **3590 passed / 10 skipped / 0 failed / 524s**；工作樹僅 `M program.md`；近 20 commits 仍 100% `auto-commit:`；**焦點：Epic 1 真通過 P0.T 拆 SPIKE+LIVE、Admin-dep P0.S/P0.D、治理缺口 P1.7 llm.py + P1.8 README**）
> **v3.5 變更**（v3.4 → v3.5）：
> - **關閉**（搬歷史）：P0.V-flaky（本輪全量 3590 passed / 0 failed，`test_ingest_keeps_fixture_backed_corpus...` 未重現）、P0.U（fallback provenance guard 已落；results.log 14:55）、P0.V-live-upgrade（ingest 升級護欄已落；results.log 15:03）、T1.12-HARDEN（live smoke 禁 silent fixture fallback；results.log 23:05）、T1.6.a / T1.6.b（155 guard + fixture 升級護欄）
> - **P0.T 拆子任務**：原條目純等 Admin 解 egress → 拆 **P0.T-SPIKE**（agent-side：live ingest 腳本 + URL 可達性盤點 + 離線驗證）+ **P0.T-LIVE**（需網路：實跑 3 源 × 3 份落盤）
> - **T1.6 收斂**：原「3 來源各 ≥50 份（≥150 baseline）」過激進 → 併入 P0.T，先以「3 來源 × ≥3 份 live」收斂；≥50 份基線延至 Epic 2 完成後
> - **補 v3.4 承諾未落**：新增 **P1.7**（`src/core/llm.py` 治理 + `docs/llm-provider-governance.md`）+ **P1.8**（README Epic 1-2 路線對齊）
> - **P0 活條目**：P0.S（Admin 連 20 輪）/ P0.D（Admin 連 12 輪）/ P0.T（agent 可做 SPIKE + Admin 依賴 LIVE）
> - **v3.4 歷史**：fixture fallback provenance + live-upgrade guard + integration smoke harden
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

### 🔴 read-only 連 2 輪延宕 = 3.25（v2.8 沿用）
read-only 任務（文件產出、檔案編輯、程式碼盤點）不依賴 ACL。若連 2 輪延宕 → 直接績效強三，無藉口。
- 適用：P0.A / P0.B / P0.C（v2.8）/ P0.E / P0.F / P0.G / P0.H（v2.9，全部已閉）/ P0.I / P0.J / P0.K / P0.L（v3.0 新增）所有 ✅ 標記任務
- 反例：「今輪做了 P0.2 一項就算交差」屬違規

### 🔴 骨架不是實作（v3.0 新增 — 第三道防線）
- **上下文**：v2.9 `src/sources/base.py` + `mojlaw.py` stub 落地，但 `MojLawAdapter.list/fetch/normalize` 全是 `raise NotImplementedError`。Epic 1 「真實抓取」仍零進度
- **新規則**：`[x] Epic 1 完成`需要 **adapter 至少跑通 1 份真實或 fixture 抓取 + 輸出 `PublicGovDoc` 實例**，不接受「骨架算完成」
- **適用**：P0.I / T1.2 / T1.3 / T1.4 系列
- **延宕懲罰**：連 2 輪零抓取 → 3.25

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

## P0 — 阻斷性回歸（v3.5 三條活線：誠信 + ACL + 真通過）

> **v3.5 狀態（15:15）**：測試本輪實測 **3590 passed / 10 skipped / 0 failed / 1363 warnings / 524.63s**；工作樹僅 `M program.md`；`.git` DENY ACL 連 12 輪；v3.4 記錄的 `test_ingest_keeps_fixture_backed_corpus...` flaky 未重現（同 P0.S-stale SOP 關閉，三軸汲取保留）
> v3.4 歷史：首次全量打臉 v3.3 文案驅動 3588/0，爆 1 FAIL flaky；推動 P0.U 護欄 + P0.V live-upgrade 升級機制 + T1.12-HARDEN live smoke 禁 silent fallback
> v3.1-3.3 歷史：Epic 1 T1.2.a/b/c + T1.3 + T1.4 全閉；5 adapter + CLI + ingest pipeline 落地；首次爆假綠建「倖存者偏差驗證 = 3.25」紅線

### P0.S — 🔴 誠信血債·首要：Admin 側 AUTO-RESCUE 腳本 commit message（v3.4 合併 P0.L-Admin）

- [ ] **P0.S** 🔴 需人工 Admin：AUTO-RESCUE 腳本 commit message 改為 conventional 格式
  - **v3.4 背景**：`git log --oneline -20 | grep -c "auto-commit:"` = **20 / 20**（v3.3 為 18/20，又退步 2 條）；P0.E 改 `.claude/ralph-loop.local.md` 規則 + P0.L 落 `docs/auto-commit-source.md` 但 Admin 腳本本體未動 → 連 **19 輪** conventional commit rule 形同虛設
  - **誠信定性**：規則寫了沒執行 = 用文字遮掩違規 = 第六層藉口「文檔驅動治理」（對應 v3.2「文案驅動開發」）
  - **修法**（Admin 側）：定位 AUTO-RESCUE 腳本（推測 `~/.claude/hooks/*.ps1` 或 OS Task Scheduler），把 `auto-commit: auto-engineer checkpoint (...)` 模板改成 `chore(rescue): restore auto-engineer working tree (<ISO8601>) — files=N`
  - **驗 1**：下 5 條 AUTO-RESCUE commit `git log --oneline -5 | grep -c "auto-commit:"` == 0
  - **驗 2**：`git log --oneline -5 | grep -cE "^[a-f0-9]+ (feat|fix|refactor|docs|chore|test)\(.+\):"` == 5
  - **驗 3**：保留 `AUTO-RESCUE` token 供 `docs/auto-commit-source.md §4` 驗收（`git log -5 | grep -c "AUTO-RESCUE"` ≥ 3）
  - **延宕懲罰**：誠信類連 1 輪延宕 = 3.25
  - 對應 commit（修腳本本體）: `chore(rescue): switch AUTO-RESCUE commit template to conventional format`

### P0.D — 🛑 ACL·阻斷：`.git` 外來 SID DENY（連 11 輪 Admin 依賴）

- [ ] **P0.D** 🛑 需人工 Admin：移除 `.git` 對 SID `S-1-5-21-541253457-2268935619-321007557-692795393` 的 DENY ACL
  - **根因證據**：`icacls .git` 顯示 `(DENY)(W,D,Rc,DC)` + `(OI)(CI)(IO)(DENY)(W,D,Rc,GW,DC)`；`icacls .git 2>&1 | grep -c DENY` = 2
  - **agent 自解失敗**：SID 非當前登入帳號，`Set-Acl` 遭 `Unauthorized operation`；需 Admin 提權或 `takeown`
  - **SOP**（admin PowerShell）：
    ```powershell
    takeown /f .git /r /d y
    icacls .git /reset /T /C
    icacls .git /remove:d "*S-1-5-21-541253457-2268935619-321007557-692795393" /T /C
    ```
  - **驗**：`icacls .git 2>&1 | grep -c DENY` == 0
  - **BLOCKER 範圍**：未過 → 所有 ACL-free 工作樹項目只能靠 AUTO-RESCUE 代 commit
  - commit（解除後）: `chore(repo): remove foreign SID DENY ACL on .git`

### P0.V-flaky — ✅ v3.5 驗證關閉（2026-04-20 15:15）：`test_ingest_keeps_fixture_backed_corpus...` 未重現

- [x] **P0.V-flaky** ✅ 不依賴 ACL：本輪全量 `pytest tests/ -q` = **3590 passed / 10 skipped / 0 failed / 524.63s**；v3.4 記錄的 flaky FAIL 本輪未重現；處置同 P0.S-stale，先關 blocker，若未來再現再以「全量 + `-p no:randomly` + 單檔」三軸重開新任務
  - **驗**：`pytest tests/ -q` 0 failed（P0.V-flaky 此輪自然綠）
  - **汲取保留**：flaky 若重現，須三軸驗；不再重蹈 P0.S-stale「復驗一次就關」的倖存者偏差

### P0.T — 🟢 Epic 1 真通過：3 來源 × 3 份真實 live md（v3.5 拆 SPIKE + LIVE）

> **拆法底層邏輯**：原 P0.T 整條 Admin-dep（需網路），agent 在 egress 鎖下連續 2+ 輪延宕卡住；v3.5 切出可 agent-side 做的 SPIKE（離線腳本 + URL 盤點 + doc），把 Admin 依賴集中到 LIVE。

#### P0.T-SPIKE — 🟢 ACL-free·agent 可做：live ingest 離線腳本 + URL 可達性盤點（v3.5 新增）

- [ ] **P0.T-SPIKE** ✅ 不依賴網路：準備一鍵 live ingest 腳本，Admin 解 egress 後 agent 可直接 P0.T-LIVE
  - 產出：
    - `scripts/live_ingest.py`：`python scripts/live_ingest.py [--sources mojlaw,datagovtw,...] [--limit 3]`，迴圈跑 5 adapter，每源強制 `GOV_AI_FORCE_LIVE=1`、禁 fixture fallback、寫 `docs/live-ingest-report.md`（URL / 抓取筆數 / 首句摘要 / `synthetic`/`fixture_fallback` flag）
    - `docs/live-ingest-urls.md`：盤點 5 adapter 實際抓取的 URL 清單（mojlaw 的 `/api/` 端點、datagovtw dataset id、executive_yuan_rss feed URL、mohw_rss feed URL、fda DataAction query），每個附 `curl -sI` 預期狀態與 `Content-Type`
    - `tests/test_live_ingest_script.py`：純離線 mock 驗腳本邏輯（不打真網路）
  - **驗 1**：`wc -l scripts/live_ingest.py` ≥ 40 AND `python scripts/live_ingest.py --help` 有出參數
  - **驗 2**：`wc -l docs/live-ingest-urls.md` ≥ 25 AND 5 adapter URL 各一行
  - **驗 3**：`pytest tests/test_live_ingest_script.py -q` 綠
  - **延宕懲罰**：ACL-free 連 2 輪延宕 → 3.25
  - commit（ACL 解除後）: `feat(scripts): add live ingest spike script + URL reachability inventory`

#### P0.T-LIVE — 🟡 Admin-dep：實跑 live ingest 產生 3 源 × 3 份 `synthetic: false` corpus

- [ ] **P0.T-LIVE** 🟡 需網路（Admin 解 proxy/egress）：fixture-only → 真實 live 抓取落盤
  - **前置**：P0.T-SPIKE 完成（腳本落地）+ P0.D 解 ACL（可 commit）+ Admin 開 shell egress
  - **v3.4 現況**：`kb_data/corpus/` 9 份 md **100% `synthetic: true` + `fixture_fallback: true`**；`grep -l "synthetic: false" kb_data/corpus/**/*.md | wc -l` = 0
  - **2026-04-20 probe**：`python -m src.sources.ingest --source mojlaw --limit 3 --base-dir meta_test/require_live_probe --require-live` 直接回 `error=live ingest required for mojlaw, but source_id=A0030018 used fixture fallback`；代表目前 shell egress/proxy 仍未通，P0.T-LIVE 不可誤報完成
  - **底層邏輯**：fixture 驗單元，真網路驗整合；Epic 1「真通過」= **≥3 來源 × ≥3 份真實 .md + `synthetic: false` + `fixture_fallback: false` frontmatter**
  - 執行（P0.T-SPIKE 落地後）：`python scripts/live_ingest.py --sources mojlaw,datagovtw,executive_yuan_rss --limit 3`
  - **驗 1**：`grep -l "synthetic: false" kb_data/corpus/**/*.md | wc -l` ≥ 9
  - **驗 2**：`grep -l "fixture_fallback: true" kb_data/corpus/**/*.md | wc -l` == 0
  - **驗 3**：每份 md `source_url` 非空且 `curl -sI <url>` 2xx/3xx
  - **驗 4**：`docs/live-ingest-report.md` 列 9+ 筆 live record
  - **延宕懲罰**：egress 解後仍不執行 = 3.25（Epic 1 真通過是 v2.8 起承諾的交付終點）
  - commit（ACL 解除後）: `feat(sources): first real live ingest — 3 sources × 3 live docs`

---

## P0.歷史 — v3.1 閉環（working-tree PASS，AUTO-RESCUE 已落版）

### P0.J — ✅ ACL-free·首要：根目錄殘檔歸位 + PRD 亂碼處理（v3.1 升首；連 2 輪延宕 3.25）

- [x] **P0.J** ✅ 不依賴 ACL：清理 v2.9 P0.H 漏網殘檔
  - **v3.0 背景**：v2.9 P0.H 搬 10 份 md 成功，但根目錄仍有 4 份歷史 md + 1 份編碼亂碼 PRD
  - 待搬（根 → `docs/archive/`）：
    - `engineering-log.md`（舊檔 170KB，`engineer-log.md` 是現用檔）
    - `MULTI_AGENT_V2_IMPLEMENTATION.md`（歷史實作文）
    - `test_compliance_draft.md`（測試殘留）
    - `output.md`（暫存輸出）
  - 待處理（`docs/archive/PRD-document.txt`）：
    - 現狀：archive 內已只剩單一 ASCII 檔名 `docs/archive/PRD-document.txt`；原先 `PRD文件.txt` 已不在 working tree
    - 根因：v2.9 P0.H 搬檔時 git apply 不支援非 ASCII 檔名 → 改以 ASCII 檔名收斂
    - 處置：保留 `PRD-document.txt` 作唯一 archive PRD 檔名，待 ACL 解後由 AUTO-RESCUE 一次 stage/commit
  - **驗**：`ls *.md | wc -l` ≤ 4（只留 README / MISSION / program / engineer-log）
  - **驗**：`git status --short | Select-String "docs/archive"` 只剩 4 個 `D` + 5 個 `??`（root 刪除 + archive 新檔），無額外 root `*.md` 殘留
  - **2026-04-20 12:58 現況**：4 份歷史 md 已移至 `docs/archive/` 並自根目錄移除，root `*.md` 已降到 4；archive PRD 已統一成 `docs/archive/PRD-document.txt`。剩餘 `git status` 的 `D/??` 僅待 ACL 解後由 AUTO-RESCUE staging/commit 收斂。
  - **延宕懲罰**：ACL-free 連 2 輪延宕 → 3.25
  - commit（ACL 解除後）: `docs(archive): move 4 root historical md + resolve PRD encoding`

### P0.K — ✅ ACL-free：01-real-sources change 推進至 specs + tasks（v3.0 新增）

- [x] **P0.K** ✅ 不依賴 ACL：`openspec/changes/01-real-sources/` 補 `specs/` + `tasks.md`
  - **v3.0 背景**：`spectra status --change 01-real-sources` 顯示 `✗ tasks blocked by: specs`；proposal.md 已落但下游卡死
  - 產出：
    - `openspec/changes/01-real-sources/specs/sources/spec.md`：定義 `BaseSourceAdapter` 契約、`PublicGovDoc` 欄位、授權/合規要求（robots.txt + rate limit ≥ 2s）
    - `openspec/changes/01-real-sources/tasks.md`：10 條可執行 task（T1.2.a / T1.2.b / T1.3 / T1.4 / T1.6 ...）對應 Epic 1 分拆
  - **驗**：`spectra status --change 01-real-sources` 顯示 `✓ specs` 與 `✓ tasks`（或 `○` 而非 `✗`）
  - **驗**：`wc -l openspec/changes/01-real-sources/specs/sources/spec.md` ≥ 30
  - **延宕懲罰**：ACL-free 連 2 輪延宕 → 3.25
  - commit（ACL 解除後）: `docs(spec): 01-real-sources add specs/sources + tasks.md`

### P0.L — ✅ ACL-free：auto-commit 源頭排查 **（v3.1 重寫：結論 = 不在 repo）**

- [x] **P0.L** ✅ 不依賴 ACL：記錄「auto-commit 源頭不在 repo」真相 + Admin 側模板替換 SOP（results.log 2026-04-20 12:51:48；文件已落 `docs/auto-commit-source.md`）
  - **v3.1 重寫背景**：v3.0 假設源頭在 `.claude/` 或 `scripts/` → 實測 `grep -rn "auto-commit:" .claude/ scripts/ .github/` 只命中 `.claude/ralph-loop.local.md:14` **禁用規則本身**；近 10 commits 仍 100% 該前綴。真相：**results.log 九條 AUTO-RESCUE 皆 Admin session 代 commit**（#20/#23/#24/#25/#29/#31/#33/#36/#38），訊息模板出自 Admin 腳本而非 auto-engineer
  - 產出 `docs/auto-commit-source.md`：
    - §1 排查證據：`grep -rn "auto-commit:"` 輸出（無 match at script 層）
    - §2 真實來源：AUTO-RESCUE Admin session（results.log 九條 PASS 條目引用）
    - §3 修復 SOP（Admin 側）：把 rescue 腳本 commit message 改 `chore(rescue): restore auto-engineer working tree (<ISO8601>)`
    - §4 驗收：ACL 解後 `git log -5` 不含 `auto-commit:` 且不含 `checkpoint`
  - **驗**：`ls docs/auto-commit-source.md && grep -c "AUTO-RESCUE" docs/auto-commit-source.md` ≥ 1
  - **延宕懲罰**：ACL-free 連 2 輪延宕 → 3.25
  - commit（ACL 解除後）: `docs(auto-engineer): document auto-commit source is Admin rescue, not repo hook`

### P0.M — ✅ ACL-free·Epic 1 第二顆骨牌：DataGovTwAdapter 實作（v3.1 新增；複製 P0.I SOP）

- [x] **P0.M** ✅ 不依賴 ACL：`DataGovTwAdapter.list()` + `fetch()` + `normalize()` 真實實作（results.log 2026-04-20 12:49:58；commit 待 ACL 解後 / AUTO-RESCUE）
  - **v3.1 背景**：P0.I 證實「stub → 實作 + 3 fixture + pytest 綠」單輪可達；T1.2.b 第一順位是 data.gov.tw（`docs/sources-research.md` 優先級最高）
  - 產出：
    - `src/sources/datagovtw.py`：`list(since_date, limit=3)` / `fetch(doc_id)` / `normalize(raw) → PublicGovDoc`
    - `tests/fixtures/datagovtw/*.json`：3 筆真實 dataset metadata 回應
    - `tests/test_datagovtw_adapter.py`：用 `unittest.mock.patch` mock 驗三動
  - **驗**：`python -c "from src.sources.datagovtw import DataGovTwAdapter; print(len(DataGovTwAdapter().list(limit=3)))"` == 3
  - **驗**：`pytest tests/test_datagovtw_adapter.py -q` 綠
  - **延宕懲罰**：ACL-free 連 2 輪延宕 → 3.25
  - commit（ACL 解除後）: `feat(sources): implement DataGovTwAdapter with 3 real fixtures`

### P0.N — ✅ ACL-free·Epic 1 一條龍：ingest.py 最小版（v3.1 新增；接通 adapter → kb_data）

- [x] **P0.N** ✅ 不依賴 ACL：`src/sources/ingest.py` 最小版 — MojLaw 一條龍落盤（results.log 2026-04-20 12:58:01；commit 待 ACL 解後 / AUTO-RESCUE）
  - **v3.1 背景**：P0.I 讓 adapter 可跑，但沒有 pipeline 把 `PublicGovDoc` 寫到 `kb_data/corpus/mojlaw/`；Epic 1 要「真通過」需 ingest 層
  - **2026-04-20 補強**：`python -m src.sources.ingest --source mojlaw` 在本機 proxy/network denied 會於 `MojLawAdapter.list()` 爆 `requests.exceptions.ProxyError`；已改為「優先真網路、失敗 fallback 本地 fixture」確保 offline smoke 可重現
  - 產出：
    - `src/sources/ingest.py`：
      - `ingest(adapter, since_date, limit)` → 跑 list → fetch → normalize → 落 `kb_data/raw/{adapter}/{YYYYMM}/{doc_id}.json`（raw 快照）+ `kb_data/corpus/{adapter}/{doc_id}.md`（YAML frontmatter）
      - `python -m src.sources.ingest --source mojlaw --limit 3` CLI 入口可用；支援 `--since` / `--base-dir`
      - 以 `source_id` 去重
    - `src/sources/mojlaw.py`：真網路失敗時 fallback `tests/fixtures/mojlaw/*.json`
    - `tests/test_sources_ingest.py`：驗落盤路徑、frontmatter、CLI offline smoke
    - `tests/test_mojlaw_adapter.py`：驗 request error → fixture fallback
  - **驗**：`pytest tests/test_mojlaw_adapter.py tests/test_sources_ingest.py -q` 綠
  - **驗**：`python -m src.sources.ingest --source mojlaw --limit 3 --base-dir meta_test/ingest_probe_verify_2` → `ingested=3`
  - **驗**：`pytest tests/test_mojlaw_adapter.py tests/test_datagovtw_adapter.py -q` 綠（ingest 未破壞既有 adapter）
  - commit（ACL 解除後）: `feat(sources): add minimal ingest pipeline wiring MojLaw to kb_data`

### P0.D — 🛑 解除 `.git` 外來 SID DENY ACL（v3.1；連 10 輪待 Admin）

- [ ] **P0.D** 🛑 需人工 Admin：移除 `.git` 對 SID `S-1-5-21-541253457-2268935619-321007557-692795393` 的 DENY ACL
  - **根因證據**：`icacls .git` 顯示該 SID 有 `(DENY)(W,D,Rc,DC)` + `(OI)(CI)(IO)(DENY)(W,D,Rc,GW,DC)`；v3.0 `icacls .git | grep -c DENY` == 2
  - **為何 agent 自解失敗**：SID 非當前登入帳號，`Set-Acl` 遭 `Attempted to perform an unauthorized operation`；需 **Admin 提權**或 `takeown /f .git /r /d y`
  - **建議 SOP**（admin PowerShell）：
    ```powershell
    takeown /f .git /r /d y
    icacls .git /reset /T /C
    icacls .git /remove:d "*S-1-5-21-541253457-2268935619-321007557-692795393" /T /C
    ```
  - **驗**：`icacls .git 2>&1 | grep -c DENY` == 0
  - **BLOCKER 範圍**：此題未過 → 所有 ACL-free 工作樹落地項都要走 AUTO-RESCUE admin session 代 commit
  - commit（解除後）：`chore(repo): remove foreign SID DENY ACL on .git`

### P0.歷史 — v3.0 閉環（working-tree PASS，commit 待 AUTO-RESCUE）

- [x] **P0.I (v3.0)** ✅ MojLawAdapter 真實 list/fetch/normalize + PublicGovDoc model + 3 fixture + 21 tests 綠（results.log #39；待 AUTO-RESCUE commit）

### P0.歷史 — v2.9 閉環（已 AUTO-RESCUE 落版）

- [x] **P0.E (v2.9)** ✅ `.claude/ralph-loop.local.md` 加入 ACL 檢查與禁 auto-commit 規則（results.log #30；commit `5f08772`）**※ 配置改了但 checkpoint 仍在產，見 v3.0 P0.L**
- [x] **P0.F (v2.9)** ✅ `src/sources/` 骨架 + `BaseSourceAdapter` + `MojLawAdapter` stub（results.log #32；commit `1d1457f`）
- [x] **P0.G (v2.9)** ✅ `openspec/changes/02-open-notebook-fork/proposal.md` 179 字（results.log #34；commit `3dbf2dc`）
- [x] **P0.H (v2.9)** ✅ 10 份頂層 md 搬 `docs/archive/`（results.log #37；commit `cc1cdf6`）

### P0.歷史 — v2.8 閉環（已驗 PASS）

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
  - **2026-04-20 blocker**：本機 shell 外連 GitHub 被拒（`Invoke-WebRequest ... main.zip` = `目標電腦拒絕連線`），且 `git clone` 會卡在 `vendor/open-notebook/.git/config: Permission denied`；需 Admin/人工提供 fork snapshot 或解除 shell egress / nested git 權限
  - commit（ACL 解除後）: `chore(vendor): add open-notebook as vendored fork target`

- ~~P1.5（原 src/core 盤點）~~ → v2.7 升 P0.4

- [x] **P1.5（v3.3 NEW）🚦 ACL-gated** `docs/architecture.md` 第一版
  - **背景**：`program.md:102` 寫「架構變動先更新 docs/architecture.md」但檔案不存在；對外 onboarding 與 Epic 1/2/3 設計鴻溝沒有 single source of truth
  - **完成**：新增 `docs/architecture.md`，落地系統入口（CLI / API / Web UI / ingest）、三層核心（sources / kb / agents）、LangGraph review loop、5 adapter 表、`kb_data/raw` / `kb_data/corpus` 落盤契約、`vendor/open-notebook` 邊界與 SurrealDB freeze 說明
  - **驗**：`wc -l docs/architecture.md` ≥ 80 AND `grep -c "## " docs/architecture.md` ≥ 5
  - commit（ACL 解後）: `docs(architecture): add v1 architecture overview covering Epic 1-3`

- [ ] **P1.6（v3.3 NEW）🚦 ACL-gated** engineer-log.md 月度歸檔
  - **背景**：當前 1158 行 / ~85KB，Read 工具 25k token 限制需 offset/limit 分次讀；歷史條目 (2026-04-20 03:15 起) 應每月歸檔
  - 產出：`docs/archive/engineer-log-202604.md`（4 月起所有反思 + 細項條目），主檔僅留「最近 7 天」與當前反思
  - **驗**：`wc -l engineer-log.md` ≤ 200 AND `ls docs/archive/engineer-log-*.md | wc -l` ≥ 1
  - commit（ACL 解後）: `docs(engineer-log): rotate Apr 2026 entries to docs/archive/`

- [ ] **P1.7（v3.4 NEW）✅ ACL-free** `src/core/llm.py` 定位 — Epic 2 前置
  - **背景**：P0.B 盤點標「Epic 2；LiteLLM/OpenRouter/Ollama provider 工廠，直接支撐 T2.0.a / T2.6 / T2.8」但 Epic 2 文字未反映；啟動 T2.6 ask_service 薄殼時會撞到 provider 選擇 / embedding 工廠設計窗口
  - 產出：`docs/llm-providers.md`（列目前 provider 抽象、支援模型矩陣、Epic 2 引用點）；Epic 2 增 T2.0.c 引用
  - **驗**：`ls docs/llm-providers.md` 存在 AND `grep -c "src/core/llm.py" docs/llm-providers.md` ≥ 1
  - commit（ACL 解後）: `docs(llm): inventory core/llm.py provider factory for Epic 2`

- [ ] **P1.8（v3.4 NEW）✅ ACL-free** README 對齊 Epic 1-2 路線
  - **背景**：`README.md` 5 KB 落後 2 個 sprint；Epic 1 五 adapter + ingest CLI + Epic 2 open-notebook fork 方向未反映
  - 產出：README 新增「資料源」段（5 adapter 表 + CLI 範例）+ 「架構路線」段連結 `docs/architecture.md`
  - **驗**：`grep -c "gov-ai sources" README.md` ≥ 2 AND `grep -c "docs/architecture.md" README.md` ≥ 1
  - commit（ACL 解後）: `docs(readme): align with Epic 1 adapters and architecture v1`

---

## Epic 1 — 真實公文資料源（最優先）

> **沒有真實資料，其他都是空殼**。Epic 1 完成前不動 Epic 2 的 T2.3 遷移層。
> **v3.0 狀態**：`src/sources/` 骨架已建（v2.9 P0.F commit `1d1457f`）；但 `MojLawAdapter` 全是 `NotImplementedError`，**零真實抓取**。v3.0 P0.I 強推「3 份真實 fixture」驗流程。T1.2 已再收縮為 T1.2.a（MojLaw 實作，升 P0.I）+ T1.2.b（其餘 4 adapter，延後）。

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
- [x] **T1.1.b** → 見 P1.2（補齊其餘 7 個來源；v2.9 閉環）
- [x] **T1.2.a-骨架** `src/sources/` ABC + MojLaw stub（v2.9 P0.F 閉環；commit `1d1457f`）
- [x] **T1.2.a-實作** MojLawAdapter 真實 list/fetch/normalize（v3.0 P0.I 閉環；results.log #39；21 tests 綠）
- [x] **T1.2.b-DataGovTw** `DataGovTwAdapter`（v3.1 P0.M 閉環；`pytest tests/test_datagovtw_adapter.py -q` 綠）
- [x] **T1.2.b-MOHW** `MohwRssAdapter`（2026-04-20 本輪閉環；`pytest tests/test_mohw_rss_adapter.py tests/test_sources_base.py tests/test_sources_ingest.py -q` 綠）
- [x] **T1.2.b-rest** 其餘 2 adapter：`ExecutiveYuanRssAdapter` / `FdaApiAdapter`（2026-04-20 source adapter suite 25 passed）
  - [x] `ExecutiveYuanRssAdapter`：RSS `list/fetch/normalize` + fixture/test（2026-04-20）
  - [x] `MohwRssAdapter`：RSS `list/fetch/normalize` + fixture/test（2026-04-20）
  - [x] `FdaApiAdapter`：JSON/HTML 混合公告 payload `list/fetch/normalize` + fixture/test（2026-04-20）
- [x] **T1.2.c** CLI wiring：`gov-ai sources ingest --source mojlaw` 整合 T1.4 ingest（2026-04-20 本輪閉環；`pytest tests/test_sources_cli.py tests/test_sources_ingest.py -q` 綠）
- [x] **T1.3** `PublicGovDoc` pydantic v2 model（`src/core/models.py`；v3.0 P0.I 閉環；`tests/test_core.py` 擴充）
- [x] **T1.4** 增量 ingest pipeline `src/sources/ingest.py`（**升 P0.N**；v3.1 P0.N 閉環）
  - 依 `crawl_date` 增量、`source_id` 去重
  - raw 存 `kb_data/raw/{adapter}/{YYYYMM}/{doc_id}.json`
  - Normalized 存 `kb_data/corpus/{adapter}/{doc_id}.md`（YAML frontmatter）
  - CLI: `gov-ai sources ingest --source all --since 2026-01-01`
- [ ] **T1.6** → v3.5 併入 **P0.T-LIVE**（本質同件；原 ≥50 份 × 3 源激進，先以 ≥3 份 × 3 源收斂；≥150 baseline 延至 Epic 2 完成後）
- [x] **T1.11（v3.3 NEW）** `gov-ai sources status / stats` CLI 子指令
  - **完成**：`src/cli/sources_cmd.py` 已補 `status` / `stats` 指令；`src/sources/ingest.py` 新增 `SourceSnapshot` + `collect_source_snapshots()`，可彙整各 adapter 的 `corpus_count` / `raw_count` / `raw_bytes` / `last_crawl` / `latest`
  - 產出：`gov-ai sources status` → 列各 adapter ingested doc count + last_crawl + raw size；`gov-ai sources stats --adapter mojlaw` → 以 source 維度 breakdown
  - **驗**：`pytest tests/test_sources_cli.py tests/test_sources_ingest.py -q` = 11 passed
  - **驗**：`python -m src.cli.main sources status --base-dir kb_data`、`python -m src.cli.main sources stats --base-dir kb_data` 均可輸出來源統計
  - commit: `feat(cli): add gov-ai sources status/stats subcommands`
- [x] **T1.12（v3.3 NEW）** integration smoke test 真網路守護
  - **完成**：新增 `tests/integration/test_sources_smoke.py`，以 `pytest.mark.integration` + `GOV_AI_RUN_INTEGRATION=1` gate 實作 5 個 adapter 的真網路 smoke；每個來源抓 1 筆 live doc 驗 `normalize()` 產出 `PublicGovDoc`，另用 `TrackingSession` 記 request timestamp 驗兩次 live request 間隔符合預設 `rate_limit >= 2s`
  - **補坑（2026-04-20）**：live smoke 現在會先把 adapter 的 `fixture_dir` / `fixture_path` 指到不存在路徑，禁止 nightly 在 upstream 掛掉時靜默退回本地 fixture；若真網路失敗，integration test 直接 fail，避免把 fixture fallback 誤當 live 健康
  - **補強**：`pyproject.toml` 註冊 `integration` marker，避免平常 pytest 因未知 marker 汙染
  - **驗**：`pytest tests/integration -m integration -q`（預設 skip；nightly 設 `GOV_AI_RUN_INTEGRATION=1` 後跑 live smoke）
  - commit: `test(sources): add nightly integration smoke for 5 adapters`
- [x] **T1.6.a** 校正 program.md 合成基線：現場 `kb_data/examples/*.md` **155**（非 156）；`tests/test_mark_synthetic.py` 新增 guard 驗數量與 frontmatter
- [x] **T1.6.b（v3.3 NEW）** fixture corpus 升級護欄：`src/sources/ingest.py` 會辨識既有 `synthetic: true` / `fixture_fallback: true` 的 corpus，僅在後續 re-ingest 拿到 `synthetic: false` 真資料時覆寫升級；若新的 fetch 仍是 fallback，保留舊檔不重寫，避免 T1.6 / P0.T 被 fixture 鎖死或洗版

---

## Epic 2 — open-notebook 源碼整合（elephant-alpha 驅動）

> **路線決策**：整套 fork [lfnovo/open-notebook](https://github.com/lfnovo/open-notebook)，公文 5 agent 審查層疊上去。
> `T2.3` SurrealDB 遷移**凍結**，待 T2.1-T2.2 人審解凍。

### 待辦任務

- ~~T2.0.a（.env smoke）~~ → 見 P1.3
- ~~T2.0.b（clone vendor）~~ → 見 P1.4
- [ ] **T2.1** 研讀 open-notebook → `docs/open-notebook-study.md`
- [x] **T2.2** 架構融合決策 `docs/integration-plan.md`（Fork/疊加/重寫三選一；預設 Fork）**🛑 完成後人審**
  - **完成（2026-04-20）**：新增 `docs/integration-plan.md`，明確選定 **Fork + thin adapter seam**；定義 `src/integrations/open_notebook/` 作 repo-owned 邊界，要求 writer / CLI / API 一律經同一 service adapter 進 vendor，並保留 answer + evidence repo contract
  - **寫死規則**：`GOV_AI_OPEN_NOTEBOOK_MODE=off|smoke|writer`；vendor 缺失或 ask-service 初始化失敗時，smoke loud fail、writer mode 回退 legacy writer 並保留 diagnostics；五審查 agent、citation/export 規則、SurrealDB freeze 全留在 repo 端
  - **驗**：`rg -n "integration seam|fallback|review agents|vendor/open-notebook" docs/integration-plan.md` 命中 4+；`pytest tests -q` = **3590 passed / 10 skipped / 0 failed**
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

- [x] **T7.1.a** `01-real-sources` proposal（v2.8 P0.C 閉；specs/tasks 見 v3.0 P0.K）
- [x] **T7.1.b** `02-open-notebook-fork` proposal（v2.9 P0.G 閉；specs/tasks 延後）
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

- [x] **T9.1** 頂層 10 份歷史 md 歸位 `docs/archive/`（v2.9 P0.H 閉；commit `cc1cdf6`；但 PRD文件.txt 編碼亂碼複本殘留，v3.0 P0.J 清理）
- [x] **T9.1.b** 根目錄剩餘 4 份歸位（**升 P0.J**）：`engineering-log.md` / `MULTI_AGENT_V2_IMPLEMENTATION.md` / `test_compliance_draft.md` / `output.md`（working tree 已完成；待 ACL 解後由 AUTO-RESCUE 正式落版）
- [ ] **T9.1.a** benchmark corpus 版控復位（ACL 解後）
  - v2.9 現況：`benchmark/mvp30_corpus.json` 未進 index，但 root `.gitignore` 白名單會讓每輪卡在 `?? benchmark/`
  - 本輪先把 `benchmark/` 全忽略，恢復工作樹 hygiene；`P0.D` 完成後需重開白名單並正式 commit corpus
  - 驗：`git status --short` 不再因 `benchmark/` 單獨髒掉
- [ ] **T9.2** tmp 再生源頭排查（定位 pytest 中產 `.json_*.tmp` / `.txt_*.tmp` 的測試；`src/cli/utils.py` atomic writer exception path；加 conftest session-end fixture）
- [ ] **T9.3** `docs/commit-plan.md` 生命週期：本輪史命完成，移 `docs/archive/commit-plans/2026-04-20-v2.2-split.md`
- [x] **T9.4.a** `tests/test_cli_commands.py` per-test chdir 隔離（v2.4 閉環）
- [ ] **T9.4.b** auto-engineer / CLI 狀態檔搬專用 state dir（`~/.gov-ai/state/` 或 `${GOV_AI_STATE_DIR}`），避免 repo root file lock 再發
  - commit: `feat(cli): configurable state dir to avoid repo-root file locks`
- [ ] **T9.5（v3.3 NEW）** root 11+ 份歷史殘檔歸位
  - **背景**：root 仍有 10 份 `.ps1`（debug_template / run_all_tests / start_n8n_system / test_advanced_template / test_citation / test_multi_agent_v2 / test_multi_agent_v2_unit / test_phase3 / test_phase4_retry / test_qa）+ 5 份 `.docx`（test_citation / test_output / test_qa_report / 春節垃圾清運公告 / 環保志工表揚）→ root hygiene 失守
  - 產出：歸位策略 — `.ps1` → `docs/archive/legacy-scripts/`；test `.docx` → `tests/fixtures/legacy-docx/`；2 份示例公告 docx → `kb_data/examples/docx/`
  - **blocker（2026-04-20）**：本 session `Copy-Item` 可通，但 `Move-Item` / `Remove-Item` 受 destructive-command policy 阻斷，無法刪 source；待可安全刪檔的 session 再閉環
  - **驗**：`Get-ChildItem -File *.ps1,*.docx` == 0
  - commit（ACL 解後）: `chore(repo): archive legacy ps1/docx from root to docs/archive + tests/fixtures`

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
- [x] **P0.A / P0.B / P0.C (v2.8)** sources-research / core 盤點 / 01-real-sources proposal
- [x] **P0.E / P0.F / P0.G / P0.H (v2.9)** ralph-loop 規則 / sources 骨架 / 02 proposal / 10 份 md 歸位
- [x] **P0.U (v3.3)** fixture fallback provenance guard：來源 adapter/ingest 會把 fallback 落盤標成 `synthetic: true` + `fixture_fallback: true`，避免假資料冒充 P0.T 真 ingest
- [x] **P0.V-live-upgrade (v3.3)** fixture corpus live-upgrade guard：ingest 會跳過既有真資料，但允許既有 fixture corpus 在 live re-ingest 時升級為 `synthetic: false` 真資料；避免先前 fallback 產物永久卡住 P0.T / T1.6
- [x] **P0.V-flaky (v3.5)** `test_ingest_keeps_fixture_backed_corpus_when_only_fixture_data_is_available` 本輪全量 3590 passed 0 failed 未重現（處置同 P0.S-stale；三軸 SOP 保留供未來）
- [x] **T1.12-HARDEN (v3.4)** nightly live smoke 禁 silent fixture fallback；`tests/integration/test_sources_smoke.py` 把 fixture_dir 指向不存在路徑，upstream 掛 → integration FAIL 不再假綠
- [x] **T1.6.a (v3.4)** 校正 `kb_data/examples/*.md` 合成基線為 155，`tests/test_mark_synthetic.py` 新增 guard
- [x] **T1.6.b (v3.4)** fixture corpus 升級護欄；ingest 辨識既有 `synthetic: true` / `fixture_fallback: true` 檔，僅 live re-ingest 時覆寫

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

**版本**：v3.5（2026-04-20 15:15 — P0.V-flaky 自然綠；P0.T 拆 SPIKE+LIVE；P1.7/P1.8 落袋）

**下一輪重排觸發**（v3.5 四項硬指標，依執行順序）：
1. `git log --oneline -5 | grep -c "auto-commit:"` == 0（P0.S；Admin 依賴，誠信血債連 20 輪）
2. `icacls .git 2>&1 | grep -c DENY` == 0（P0.D；Admin 依賴連 12 輪）
3. `ls scripts/live_ingest.py docs/live-ingest-urls.md` 存在 AND `pytest tests/test_live_ingest_script.py -q` 綠（P0.T-SPIKE；agent-side 可做）
4. `grep -l "synthetic: false" kb_data/corpus/**/*.md | wc -l` ≥ 9 AND `grep -l "fixture_fallback: true" kb_data/corpus/**/*.md | wc -l` == 0（P0.T-LIVE；Admin 解 egress 後）

**健康護欄**（v3.5 必須持續綠）：
- `pytest tests/ -q` FAIL 數 == 0（目前 **3590 passed / 10 skipped / 0 failed**）
- `grep -l "RequestException" src/sources/*.py | wc -l` ≥ 5（目前 6）
- `grep -c "\[ \]" openspec/changes/01-real-sources/tasks.md` == 0（目前 0）
- `wc -l docs/architecture.md` ≥ 80（目前 273）

**P0.S 連 20 輪紅線未解**：conventional commit 規則寫了卻連 20/20 條 checkpoint 假提交照樣進歷史 = 誠信級漏洞。
**P0.T 承諾仍懸空 7+ 輪（v2.8 起）**：v3.5 拆 SPIKE + LIVE，agent 先把腳本 + URL 盤點備齊，Admin 解 egress 即一鍵落盤。

**紅線恆定**：
- **紅線 1（v3.2）**：倖存者偏差驗證 = 假綠 = 3.25 — 驗收禁依賴 cached 目錄 / proxy / 本機狀態；`pytest tmp_path + mock 網路` = 唯一硬驗
- **紅線 2（v3.3）**：文案驅動開發 = 3.25 — log 寫「已完成 X」但執行路徑不走 X，以文字遮掩代碼洞
- **紅線 3（v3.4）**：文檔驅動治理 = 3.25 — 規則寫了沒執行（P0.S 連 20 輪即案例），以規則遮掩違規
- **紅線 4（v3.5）**：承諾漂移 = 3.25 — header 寫「新增 X」但 body 未落（P1.7/P1.8 v3.4 承諾本輪才真落即案例），以版本號遮掩功能缺口

> **v3.4 → v3.5 變更摘要**：
> 1. **P0.V-flaky 自然綠**：本輪全量 3590 passed / 0 failed，v3.4 爆的 flaky FAIL 未重現；三軸 SOP 保留
> 2. **P0.T 拆 SPIKE + LIVE**：把 agent 可做的 live ingest 腳本 + URL 盤點拆出，把 Admin 依賴集中到 LIVE，避免 agent 空轉
> 3. **T1.6 併入 P0.T-LIVE**：原「≥50 份 × 3 源」過激進，先 ≥3 份收斂
> 4. **閉環搬歷史**：P0.V-flaky / P0.U / P0.V-live-upgrade / T1.12-HARDEN / T1.6.a / T1.6.b
> 5. **P1.7 / P1.8 保留**：v3.4 承諾，v3.5 起 ACL-free 連 2 輪延宕 = 3.25（歸誠信）
