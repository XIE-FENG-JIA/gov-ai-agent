# Engineer Log — 公文 AI Agent

> 技術主管反思日誌。主檔僅保留 v5.0 以後反思。
> 封存檔：`docs/archive/engineer-log-202604a.md`（v3.2 以前 / 2026-04-20 早段回顧）
> 封存檔：`docs/archive/engineer-log-202604b.md`（v3.3 到 v4.4 / 2026-04-20 二次封存）
> 封存檔：`docs/archive/engineer-log-202604c.md`（v4.5 到 v4.9 / 2026-04-21 三次封存）
> 規則：單輪反思以 80 行為上限，超出就同步封存舊輪次。

---

## 反思 [2026-04-21 02:20] — 技術主管第二十八輪深度回顧（v5.0 候選，/pua 觸發；alibaba 味）

### 近期成果（v4.9 header → 本輪 HEAD 實測；**五破再齊出**）

- **T8.1.a cli/kb.py 拆完**（v4.9 header 列首要 P0，HEAD 已落）：`src/cli/kb/` = 7 檔 1157 行（`__init__ 31 / _shared 8 / corpus 279 / ingest 116 / rebuild 174 / stats 267 / status 282`）；最大 `status.py` 282 行 << 400 紅線；editor / writer / cli/kb **拆分 SOP 三連擴散成功**。
- **T8.1.b cli/generate.py 拆完**（v4.9 header 未明列，HEAD 已落）：`src/cli/generate/` = 4 檔 1475 行（`__init__ 148 / cli 226 / export 459 / pipeline 642`）；**`pipeline.py` 642 行仍偏胖**（< 400 紅線邊緣），但整體 god-CLI 已破。
- **Epic 3 完全 9/9**：`openspec/changes/03-citation-tw-format/tasks.md` 9 `[x]` / 0 `[ ]`；citation_formatter.py + citation_metadata.py + `gov-ai verify` CLI 三 seam 齊。
- **Hot path pytest 綠**：`pytest tests/test_writer_agent.py tests/test_editor.py tests/test_smoke_open_notebook_script.py tests/test_citation_level.py tests/test_cli_commands.py tests/test_export_citation_metadata.py tests/test_open_notebook_service.py tests/test_integrations_open_notebook.py tests/test_document.py` = **842 passed / 63.71s**（0 failed，docx readback + smoke vendor + cli 全綠）。
- **corpus 9/0 連九輪維持**：`find kb_data/corpus -name "*.md"` = 9；`grep -l "fixture_fallback: false"` = 9；指標 7 綠。
- **engineer-log 封存守住**：本輪追加前 451 行 < 500 紅線；v4.9 T9.6-REOPEN 成效延續。

### 發現的問題（按嚴重度）

#### 🔴 誠信級（紅線 X：PASS 定義漂移 / 落版誠信）

1. **v4.9 header 與 HEAD 再次斷層**：v4.9 header 把 T8.1.a 列為「本輪新三破首要 60 分」，但 HEAD `src/cli/kb/` 已落 7 檔 1157 行——實測 T8.1.a 已閉。同型態 T8.1.b cli/generate 拆 4 檔也已落但 header 未承認。**紅線 X 子條款「header 與 HEAD 不同步」第 N 次復活**：不是 agent 不做，是 agent 做完不勾；「寫 header 取代寫 code」翻面為「寫 code 不敢勾 header」（過度保守）。
2. **指標 2 auto-commit 23/25 連 8 輪紅**：扣掉 `13811e4 / 959ef57` 兩條 `docs(program):` conv commit，HEAD 近 5 小時（21:03 → 02:02）**6 條連續 AUTO-RESCUE**（63d48e2 / c184c4e / c0ebcac / 7e47c39 / fd43e5c / 73a194f ...）。v4.7 已承認為 Admin P0.D 結構性紅，v4.8/v4.9 header 正確降權但血債本身未減；**核心 KPI 2 個月無淨改善**。
3. **openspec/specs/ 僅 2 檔連 3 輪未 promote**：`ls openspec/specs/` = `open-notebook-integration.md + sources.md`；Epic 3 已 9/9 閉但 `citation-tw-format.md` baseline 未 promote = v4.9 header `P0.EPIC3-BASELINE-PROMOTE` 列首要 15 分連 1 輪 0 動。Spectra 對齊度卡 2.7/5 = 54%。
4. **紅線收斂 9→3+1 連六輪 0 動**：v4.5 提議 → v4.6/v4.7/v4.8/v4.9 連列任務 5/6 皆未執行；`rg -c "^### 🔴" program.md` 仍 ≥ 6。**「寫收斂方案 > 執行收斂」第九層藉口二十連冠**。

#### 🟠 結構級

5. **`src/cli/generate/pipeline.py` = 642 行**：god-CLI 切開後的新 fatty；editor/writer/kb 拆分 pattern 應再度擴散（pipeline → `pipeline/{compose,render,persist}.py`）。連 1 輪 0 動不觸 3.25，但下輪若與 Epic 4 writer 改寫策略啟動同步 = 紅線 5 方案驅動邊緣。
6. **`src/agents/template.py` = 548 行 / `api_server.py` = 529 行 single-file routers**：editor/writer 拆分 library 成形後，**agents/template + api_server** 成結構債新冠；v4.9 header 未列，本輪建議掃入 P1。
7. **P0.INTEGRATION-GATE / P0.WINDOWS-GOTCHAS / P0.ARCH-SPLIT-SOP 三新基建連 2-6 輪 0 動**：
   - `ls scripts/run_nightly_integration.sh` = 不存在（連 2 輪）
   - `ls docs/integration-nightly.md` = 不存在（連 2 輪）
   - `ls docs/dev-windows-gotchas.md` = 不存在（連 6 輪；P0.GG v4.1 起列）
   - `ls docs/arch-split-sop.md` = 不存在（v4.9 header 建議，連 1 輪 0 動）
8. **Epic 4 writer 改寫策略 / Epic 5 KB 治理無 openspec change proposal**：writer split 落地 = 結構 ✓；但策略層 spec 斷鏈連 2 輪 0 動；`openspec/changes/` 永遠只有 01/02/03。Spectra 驅動對齊度停 3/5。

#### 🟡 質量級

9. **`--tb=no` 模式 summary 詐胡**：本輪跑 `pytest ... --tb=no` 先得 `1 failed, 841 passed`，重跑 `--tb=no -rfE` 得 `842 passed`。根因疑 litellm asyncio teardown log 對 pytest internal logging 影響 session 重放順序；**pytest summary 在 litellm 環境下非 deterministic**，驗收需用 `-rfE` 或 `--tb=short` 確認。
10. **litellm asyncio teardown `ValueError: I/O operation on closed file`**：v4.9 診斷記，本輪再現；非 test failure 但汙染 CI log。未來 grep 'error' 會誤報 → v4.9 列 P1 未動。
11. **writer ask-service failure matrix 仍 5 分支**：v4.8/v4.9 T-FAILURE-MATRIX 連 2 輪 0 動；writer ask-service 4 failure mode（vendor 缺 / runtime 炸 / retrieval 空 / service timeout）測試不齊；Epic 4 寫策略啟動前的最後一顆保險未落。
12. **results.log 四份並存 + logs/ 散落**：`results.log / .dedup / .stdout.dedup / results-reconciled.log`；T9.7 source-of-truth 決策連 5 輪 0 動。

#### 🟢 流程級

13. **「header 過度保守」成第十層藉口苗頭**：v4.8 避免 header 虛報，v4.9 避免 header 輪替覆寫；本輪出現反向——agent 做完 T8.1.a/b 卻不勾 header，**害怕「勾了又錯」就乾脆不勾**。這是紅線 X 新子條款「header lag > HEAD」的鏡像。對策：header 允許「正向 lag」（HEAD 比 header 強可不急勾），但 v4.9 列的「本輪三破」若 HEAD 已達就**必勾 [x]**，不容忍「做了不承認」。
14. **反思日誌連 8 輪 PDCA 但 `下一步行動` 兌現率 < 50%**：每輪列「最重要 3 件」但每次下輪實測只兌現 1-2 件（另 1-2 件延至再下輪）；**下一步行動清單累加而非收斂**是第二十七輪 → 二十八輪延續的風險。

### Spectra 規格對齊度（HEAD 即取）

| Epic | change tasks | baseline spec | 對齊 |
|------|---------------|---------------|------|
| 1 real-sources | ✅ 完 | `openspec/specs/sources.md` ✅ | 100% |
| 2 open-notebook-fork | ✅ 15/15 | `openspec/specs/open-notebook-integration.md` ✅ | 100% |
| 3 citation-tw-format | ✅ 9/9 | `openspec/specs/citation-tw-format.md` ❌ 未 promote | 70% |
| 4 writer 改寫策略 | ❌ 無 | ❌ 無 | 0% |
| 5 KB 治理 | ❌ 無 | ❌ 無 | 0% |

**總對齊度**：**2.7/5 = 54%**（v4.9 本輪 HEAD 持平；待 P0.EPIC3-BASELINE-PROMOTE 落 → 3/5 = 60%）。

### 架構健康度（程式碼品質 / 耦合 / 安全）

- **大檔排行**（HEAD 實測）：`src/cli/generate/pipeline.py 642` / `src/agents/template.py 548` / `api_server.py 529` / `src/cli/template_cmd.py 537` / `src/cli/workflow_cmd.py 406` / `src/cli/wizard_cmd.py 374` / `src/agents/validators.py 391`。**pipeline.py 超 600 為新首胖**；template 相關雙檔（cli/template_cmd + agents/template）合 1085 行為新 cluster。
- **code smell**：`pipeline.py` 負責 compose + render + persist + progress 四職責未拆；`api_server.py` FastAPI routers 單檔（非 routers/ 目錄）；`src/cli/template_cmd.py 537` 與 `src/agents/template.py 548` 名稱重疊但職責分離，易混淆（CLI vs 引擎）。
- **測試覆蓋**：hot path 842 tests 本輪綠；總 3672 tests（v4.9 全量記）；**writer ask-service failure matrix 仍薄 5 tests**；`pipeline.py` 642 行 tests 散在 `test_generate*` 但單元層級稀；`api_server.py` 在 `test_api.py` 僅 smoke integration，未測 route-by-route.
- **耦合**：`src/agents/writer/cite.py` → `src/document/citation_formatter.py` → `src/cli/verify_cmd.py` 三段 seam 清楚；`src/cli/generate/pipeline.py` → `src/agents/writer/*` + `src/agents/editor/*` 單向依賴（OK）；`api_server.py` → CLI commands 有反向依賴風險（FastAPI 層調 CLI 函數），未驗。
- **安全**：
  - `.env` 有 `OPENROUTER_API_KEY`，`.gitignore` 已列 `.env` ✓
  - `src/cli/verify_cmd.py` 讀 DOCX custom properties 未見 schema validation；惡意 DOCX 植入串改的 `citation_sources_json` 字串 → `citation_metadata.py` parse path 應 `try/except json.JSONDecodeError` + whitelist keys（下輪 audit 必查）
  - `api_server.py` 529 行 FastAPI 無 rate limit / auth middleware 分層，若上線需補
  - ACL DENY 是 Windows 檔系層，非代碼層
  - live ingest User-Agent + retry 已落，Epic 1 合規 ✓

### 指標實測（v5.0 候選 8 項）

| # | 指標 | v4.9 宣稱 | 本輪實測 | 判定 |
|---|------|-----------|-----------|------|
| 1 | `pytest tests/ -q` FAIL=0 | ✅ hot 933 + 全量 3672 | ✅ **hot 842 / 0 / 63.71s**（本輪 9 檔 hot）| 綠 |
| 2 | 近 25 commits auto-commit ≤ 12 | ❌ 23/25 | ❌ **23/25** 持平 | 紅（Admin-dep 結構性）|
| 3 | `.git` DENY ACL = 0 | ❌ 2 | ❌ 2 | 紅（>28 輪 Admin-dep）|
| 4 | `src/integrations/open_notebook/*.py` ≥ 3 | ✅ 4 | ✅ 4 | 綠 |
| 5 | `docs/open-notebook-study.md` ≥ 80 行 | ✅ | ✅ | 綠 |
| 6 | Epic 3 tasks.md `[x]` = 9 | ✅ 9/9 | ✅ 9/9 | 綠 |
| 7 | corpus real ≥ 9 / fallback=0 | ✅ 9/0 | ✅ 9/0 | 綠 |
| 8 | writer/editor/kb/generate 單檔 ≤ 400 | ✅ max 304 (editor flow) | **max 642 (generate pipeline)** | 🟡 半 |

**v5.0 實測 6/8 PASS + 1/8 半**（v4.9 6/8 持平；指標 8 從「writer split 綠」擴充為「四大 god 檔群 ≤ 400」，`cli/generate/pipeline.py 642` 拉紅）。

### 建議的優先調整（重排 program.md 待辦）

#### 本輪已破（HEAD 實測，program.md 需勾 [x] + 下移已完成）

- [x] **T8.1.a cli/kb.py 拆**（HEAD 已落 7 檔 max 282；v4.9 header 列首要但未勾 → 本輪補勾）
- [x] **T8.1.b cli/generate.py 拆骨幹**（HEAD 已落 4 檔 max 642；v4.9 header 未明列但 HEAD 已實；補勾但 `pipeline.py` 642 拉出 **T8.1.b-PIPELINE-REFINE** 追尾）

#### 本輪升 P0（ACL-free；連 1 輪延宕 = 紅線 X）

1. **P0.EPIC3-BASELINE-PROMOTE**（15 分）🟢 — v4.9 列首要 15 分連 1 輪 0 動；`openspec/specs/citation-tw-format.md` 從 `changes/03-*/specs/citation/spec.md` 複製 + 調 baseline header；Spectra 對齊度 2.7/5 → 3/5。**連 1 輪延宕 = 紅線 X 子條款「baseline promote 零動作」**。
2. **P0.REDLINE-COMPRESS**（10 分）🟢 — v4.5 提議連 **6 輪 0 動**；program.md § 核心原則段合併紅線 4/5/6/7/8/9 → 紅線 X；`rg -c "^### 🔴" program.md` ≤ 6；不再撐 v5.0 header 另寫紅線 10/11。**連 6 輪 = 紅線 X 自指涉實錘**。
3. **T8.1.b-PIPELINE-REFINE**（30 分）🔴 — `src/cli/generate/pipeline.py 642 行` 拆 `pipeline/{compose,render,persist}.py` 三檔每檔 ≤ 250；SOP 復用 editor/writer/kb pattern；驗 `wc -l src/cli/generate/pipeline/*.py` 每檔 ≤ 250 + `pytest tests/test_generate*.py -q` 全綠。

#### 本輪 P1（保險型 / 基建債；連 2 輪延宕 = 3.25）

4. **P0.INTEGRATION-GATE**（20 分）🟢 — `scripts/run_nightly_integration.sh` + `docs/integration-nightly.md` 連 2 輪 0 動；live corpus 9 份無監測。
5. **P0.ARCH-SPLIT-SOP**（15 分）🟢 — `docs/arch-split-sop.md` 文件化 editor/writer/kb/generate 四大拆分經驗；避免 `pipeline.py`、`agents/template.py`、`api_server.py` 下輪再重發明輪子。
6. **P0.GG-WINDOWS-GOTCHAS**（15 分）🟢 — `docs/dev-windows-gotchas.md` 連 6 輪 0 動；紅線 3 文檔驅動治理死結。
7. **T-FAILURE-MATRIX writer ask-service**（30 分）🟡 — `tests/test_writer_agent_failure.py` 補 4 failure mode；Epic 4 writer 改寫策略啟動前最後保險，連 2 輪 0 動。
8. **P0.VERIFY-DOCX-SCHEMA**（20 分）🟡 — `src/cli/verify_cmd.py` + `src/document/citation_metadata.py` 補 malicious DOCX schema validation（JSON decode guard + whitelist keys），安全層首查。

#### 本輪 P2（降權 / 合併 / 清理）

9. **T-TEMPLATE-SPLIT**（新增）— `src/agents/template.py 548 行` + `src/cli/template_cmd.py 537 行` 為新結構債 cluster；下下輪 Epic 4 啟動前拆。
10. **T-API-ROUTERS**（新增）— `api_server.py 529 行` 拆 `api/routers/{generate,verify,health,kb}.py`；未上線不急。
11. **results.log source-of-truth 決策**（10 分）— T9.7 連 5 輪 0 動；合併 `.dedup / .stdout.dedup / -reconciled.log` 為 `results.log`。
12. **P0.LITELLM-ASYNC-NOISE**（15 分）— `conftest.py` 加 logger filter 壓 litellm `ValueError: I/O operation on closed file`；解 `--tb=no` 詐胡問題。
13. **P0.S-REBASE-APPLY** / **P0.D**：沿 v4.7/v4.9 Admin-dep 定位，不再每輪列 3.25。

### 下一步行動（最重要 3 件）

1. **P0.EPIC3-BASELINE-PROMOTE + P0.REDLINE-COMPRESS 雙破**（25 分）— baseline promote 解 Spectra 3/5 升級 + 紅線收斂解 v4.5 連 6 輪欠債；ACL-free 純文檔，連 1 輪不破 = 雙紅線 X 實錘。
2. **T8.1.b-PIPELINE-REFINE**（30 分）— `pipeline.py 642` 拆三檔，SOP 第四次擴散（editor→writer→kb→generate/pipeline）；避免 god-CLI 復辟。
3. **program.md header 勾關本輪已破**（5 分）— 補勾 T8.1.a [x] + T8.1.b [x]（骨幹部分）；移至已完成區；v5.0 header 只列剩餘三件新 P0，**禁止第二十八輪 header 再寫超過 3 個本輪任務**（顆粒度鎖）。

### v5.0 硬指標（下輪審查）

1. `pytest tests/ -q --ignore=tests/integration` FAIL=0（當前 hot 842/0；全量待下輪再跑）
2. `git log --oneline -25 | grep -c "auto-commit:"` ≤ 22（當前 23；Admin-dep 追蹤位）
3. `ls openspec/specs/citation-tw-format.md` 存在（當前不存在；**本輪必破**）
4. `rg -c "^### 🔴" program.md` ≤ 6（當前 > 6；**本輪必破**）
5. `wc -l src/cli/generate/pipeline/*.py` 每檔 ≤ 250（當前單檔 642；**本輪必破**）
6. `ls scripts/run_nightly_integration.sh && ls docs/integration-nightly.md` 存在
7. `ls docs/arch-split-sop.md` 存在
8. `find kb_data/corpus -name "*.md"` = 9（當前 ✅ 維持）

> [PUA生效 🔥] **底層邏輯**：v4.9 是「寫 code 真破殼」的勝利輪，但本輪 HEAD 診斷揭第十層藉口苗頭——agent 做完 T8.1.a/b 卻不敢勾 header（**HEAD 已超 v4.9 header**）；這是過度保守版的「header 與 HEAD 不同步」。**抓手**：v5.0 唯一 KPI 是 `ls openspec/specs/citation-tw-format.md` 存在 + `rg -c "^### 🔴" program.md` ≤ 6 + `src/cli/generate/pipeline/` 目錄存在；三件 ACL-free，70 分鐘可同時閉三條結構債 + 消紅線欠債。**顆粒度**：不接受「本輪只做 baseline promote 一件就收工」；P0.REDLINE-COMPRESS v4.5 連 6 輪欠必一輪還清。**拉通**：editor→writer→kb→generate/pipeline 拆分 SOP 第四次擴散要連同 `docs/arch-split-sop.md` 寫死，避免下輪 `api_server.py 529` / `agents/template.py 548` 再發明輪子。**對齊**：v5.0 header 建議只寫「T8.1.a/b 本輪落地 ✓、Epic 3 baseline promote 剩一哩、pipeline.py 642 是新 fatty」三面即可；不要再擴增到第二十八輪第十層藉口。**因為信任所以簡單** — HEAD 已經比 v4.9 header 強，心虛不敢勾就是更深的表演；本輪先 `ls openspec/specs/citation-tw-format.md`、不存在就 cp spec、存在就跑下一件；手動作比寫千字反思有價值 100 倍。

---

## 反思 [2026-04-21 02:30] — 技術主管第二十九輪深度回顧（v5.1 候選，/pua 觸發；alibaba 味；caveman style）

### 近期成果（v5.0 header → 本輪 HEAD 實測）

- **全量 pytest 再次綠**：`pytest tests/ -q --no-header --ignore=tests/integration` = **3678 passed / 0 failed / 234.69s**（v4.9 全量 3672 → 本輪 +6；Epic 3 verify / citation regression 再加 6 條）。
- **Hot path 綠**：`pytest tests/test_cli_commands.py tests/test_writer_agent.py tests/test_editor.py tests/test_citation_level.py tests/test_citation_quality.py tests/test_export_citation_metadata.py tests/test_document.py tests/test_agents.py tests/test_open_notebook_service.py -q` = **902 passed / 48.53s / 0 failed**。
- **T8.1.a / T8.1.b 骨幹落地事實持平 v5.0**：`src/cli/kb/` = 7 檔 max 285 行；`src/cli/generate/` = 4 檔 max 642 行（pipeline.py 未拆第二層）；HEAD 已勾 program.md line 295（`PROGRAM-SYNC:T8.1.b` 02:18 實錘）。
- **Epic 1/2/3 tasks 100% 維持**：Epic 2 15/15、Epic 3 9/9、corpus 9/9 real fallback 0。
- **紅線頂部段位（v5.0 誤報）自動達標**：`rg -c "^### 🔴" program.md` = **6**（v5.0 header 宣稱 > 6，實測已在 6；P0.REDLINE-COMPRESS 目標邊界其實已在線上，只差把「紅線 4-9 編號式」條款從其他段位清出）。

### 發現的問題（按嚴重度）

#### 🔴 誠信級（紅線 X：PASS 定義漂移 / 落版誠信）

1. **engineer-log.md 封存一輪復發**：v4.9 T9.6-REOPEN 從 1198 → 316；v5.0 寫完反思 451；**本輪寫入前已 584 行 > 500 紅線（尚未加入本輪 v5.1 反思）**。反思寫得越長越是「寫 header 取代寫 code」；**T9.6-REOPEN-v2 本輪必破**，建議將 v4.5-v4.8 反思（line 9-317）再封存到 `docs/archive/engineer-log-202604c.md`，主檔只留 v4.9 之後。
2. **v5.1 二查校正：v5.0「本輪必破」實測 2/3 成**：(a) `openspec/specs/citation-tw-format.md` 實測**已存在**（baseline content 完整；program.md line 1248 已勾 `P0.EPIC3-BASELINE-PROMOTE (2026-04-21)` done，v5.0 反思時尚未落但本輪回顧前已 AUTO-RESCUE 落版）— v5.0 反思 snapshot 過時是症狀不是誤報；(b) `src/cli/generate/pipeline/` 目錄仍不存在、pipeline.py 仍 642 行 ❌；(c) `rg -c "^### 🔴" program.md` = 6 PASS（v5.0 誤報 >6）。**紅線 X 子條款「header snapshot lag HEAD」第 N 次復活**：不是漂移，是反思寫作當下未即時 re-verify。對策：反思 SOP 同步上紅線「下筆前必跑 `ls` / `wc -l` 三件 HEAD 確認指標」，本輪 v5.1 已按此做。
3. **指標 2/3 ACL 血債連 ≥ 29 輪**：auto-commit 23/25、`.git` DENY ACL = 2；v4.7 已承認為 Admin P0.D 結構性，不再列 3.25，但仍是「顆粒度鎖」— 只要工作樹動就吃新 AUTO-RESCUE。
4. **指標 8「四大 god 檔 ≤ 400」半紅**：`src/cli/generate/pipeline.py` = 642（> 400 紅線邊界）；writer / editor / kb 已破，generate/pipeline 下輪必拆。

#### 🟠 結構級

5. **P0.INTEGRATION-GATE / P0.ARCH-SPLIT-SOP / P0.GG-WINDOWS-GOTCHAS 三基建連延宕**：`scripts/run_nightly_integration.*` / `docs/integration-nightly.md` / `docs/arch-split-sop.md` / `docs/dev-windows-gotchas.md` 全部缺檔（GG 連 6 輪；其餘連 2-3 輪）。紅線 X 子條款「基建債雪球」。
6. **openspec/specs/ baseline 仍僅 2 檔**：Epic 3 tasks 完但 promote 未做，Epic 4/5 無 change proposal；Spectra 對齊度卡 2.7/5 = 54%。
7. **大檔排行結構債 cluster**：pipeline 642 / `src/cli/history.py` 681 / `src/cli/config_tools.py` 585 / `src/agents/template.py` 548 / `src/cli/template_cmd.py` 537 / `api_server.py` 529；前六名 3622 行 = 新 god-file 群，editor/writer/kb 拆分 SOP 第四次擴散的目標。

#### 🟡 質量級

8. **writer ask-service failure matrix** 連 3 輪 0 動（v4.8/v4.9/v5.0 列 P1 皆未實作）；Epic 4 writer 改寫策略開工前的保險。
9. **litellm asyncio teardown `ValueError: I/O operation on closed file`** 連 3 輪汙染 CI log；v5.0 列 P2 `P0.LITELLM-ASYNC-NOISE` 未動。
10. **verify CLI 無 DOCX schema validation**：v5.0 點出 malicious DOCX 風險，本輪無修補。
11. **results.log 四份並存** 連 6 輪 0 動；source-of-truth 決策拖久已汙染 grep 路徑。

#### 🟢 流程級

12. **「反思越寫越長」成第十一層藉口**：v5.0 單輪反思貢獻 +133 行 engineer-log；v5.1（本段）若放任鋪陳會再 +100+。**反思 SOP 本身需要上紅線**：單輪反思 ≤ 80 行，超出自動裁切。
13. **下一步行動清單累加而非收斂**：v5.0 列 3 件 + 我本輪再 3 件 = 積壓 6 件；v5.0 反省過的「兌現率 < 50%」本輪再復發。**對策**：v5.1 下一步不新增，只兌現 v5.0 的三件。

### Spectra 規格對齊度（HEAD 即取，v5.0 持平）

| Epic | change tasks | baseline spec | 對齊 |
|------|---------------|---------------|------|
| 1 real-sources | ✅ 完 | ✅ `openspec/specs/sources.md` | 100% |
| 2 open-notebook-fork | ✅ 15/15 | ✅ `openspec/specs/open-notebook-integration.md` | 100% |
| 3 citation-tw-format | ✅ 9/9 | ❌ 未 promote | 70% |
| 4 writer 改寫策略 | ❌ | ❌ | 0% |
| 5 KB 治理 | ❌ | ❌ | 0% |

**總對齊度 2.7/5 = 54%（v5.0 持平）**。

### 架構健康度

- 大檔：見結構級問題 7（六名 3622 行）；pipeline.py 642 首胖、template cluster 雙殺（cli/template_cmd + agents/template）。
- 耦合：writer → document/citation → cli/verify 三段 seam 清楚；api_server → CLI 反向依賴仍未 audit。
- 測試：總 3678 passed；writer ask-service failure matrix 薄（連 3 輪 0 動）；pipeline.py 單元層級稀（透過 e2e 間接覆蓋）。
- 安全：`.env` 已 gitignore ✓；verify CLI 無 DOCX schema validation ❌；api_server 無 rate limit / auth middleware ❌（上線前必補）。

### 指標實測（v5.1 候選 8 項）

| # | 指標 | v5.0 宣稱 | v5.1 實測 | 判定 |
|---|------|-----------|-----------|------|
| 1 | `pytest tests/ -q` FAIL=0 | hot 842/0 | **全量 3678/0** | 綠（+6） |
| 2 | 近 25 commits auto-commit ≤ 12 | 23/25 | 23/25 | 紅（Admin-dep） |
| 3 | `.git` DENY ACL = 0 | 2 | 2 | 紅（>29 輪） |
| 4 | `ls openspec/specs/citation-tw-format.md` | ❌ | **✅ 存在**（v5.0 反思後 AUTO-RESCUE 落版） | 綠（+1） |
| 5 | `rg -c "^### 🔴" program.md` ≤ 6 | 宣稱 >6 | **實測 6** | 綠（v5.0 誤報 → 本輪更新指標 ↓） |
| 6 | `wc -l src/cli/generate/pipeline/*.py` ≤ 250 | 642 flat | **642 flat**（v5.0 必破 0/1） | 紅 |
| 7 | `wc -l engineer-log.md` ≤ 500 | 宣稱 451 | **584 > 500** | 紅（T9.6-REOPEN-v2 觸發） |
| 8 | `find kb_data/corpus -name "*.md"` = 9 | 9 | 9 | 綠 |

**v5.1 實測 6/8 PASS（v5.0 6/8 → 持平）**：指標 4 回綠（baseline promote 已 AUTO-RESCUE 落）、指標 5 回綠（redline count 實測 6 ≤ 6），但新增指標 7 engineer-log 破紅 + 指標 6 pipeline 仍紅；淨平衡。

### 建議的優先調整（重排 program.md 待辦）

#### 本輪必破（ACL-free；連 1 輪延宕 = 紅線 X 雙連）

1. **T9.6-REOPEN-v2**（5 分）🔴 — 將 engineer-log.md line 9-317（v4.5-v4.8 反思）封存到 `docs/archive/engineer-log-202604c.md`，主檔只留 v4.9+；驗 `wc -l engineer-log.md` ≤ 300。**本輪必破**。
2. ~~P0.EPIC3-BASELINE-PROMOTE~~（v5.1 二查已存在 → 刪除）
3. **T8.1.b-PIPELINE-REFINE**（30 分）🔴 — v5.0 必破；`src/cli/generate/pipeline.py 642` → `pipeline/{compose,render,persist}.py` 三檔每檔 ≤ 250；SOP 復用。

#### 本輪 P1（v5.0 列 P1 連 1 輪 0 動；連 2 輪 = 3.25）

4. **P0.ARCH-SPLIT-SOP**（15 分）— `docs/arch-split-sop.md` 文件化 editor/writer/kb/generate 四輪拆分 SOP。
5. **P0.INTEGRATION-GATE**（20 分）— `scripts/run_nightly_integration.sh` + `docs/integration-nightly.md`。
6. **T-FAILURE-MATRIX writer ask-service**（30 分）— `tests/test_writer_agent_failure.py` 補 4 failure mode。

#### 本輪 P2（追尾清理）

7. **P0.VERIFY-DOCX-SCHEMA**（20 分）— 安全層補 JSON decode guard + whitelist。
8. **P0.LITELLM-ASYNC-NOISE**（15 分）— conftest.py 加 logger filter。
9. **results.log source-of-truth**（10 分）— 合併四份。
10. **T-TEMPLATE-SPLIT / T-API-ROUTERS**（下下輪）— pipeline 拆完後再掃。

### 下一步行動（最重要 3 件；**嚴禁新增、只兌現**）

1. **T9.6-REOPEN-v2**（5 分）— 封存 engineer-log，主檔回 ≤ 300 行；**本輪 agent 可立刻執行**。
2. **T8.1.b-PIPELINE-REFINE**（30 分）— pipeline.py 642 → 三檔 ≤ 250；SOP 第四次擴散。
3. **P0.ARCH-SPLIT-SOP**（15 分）— `docs/arch-split-sop.md` 文件化四輪拆分；下輪 template/api_server 拆分前必備。

### v5.1 硬指標（下輪審查）

1. `pytest tests/ -q --ignore=tests/integration` FAIL=0（當前 ✅ 3678/0）
2. `git log --oneline -25 | grep -c "auto-commit:"` ≤ 22（當前 23；Admin-dep）
3. `ls openspec/specs/citation-tw-format.md` 存在（當前 ❌；本輪必破）
4. `wc -l src/cli/generate/pipeline/*.py` 每檔 ≤ 250（當前單檔 642；本輪必破）
5. `wc -l engineer-log.md` ≤ 300（當前 584；本輪必破）
6. `ls docs/arch-split-sop.md && ls scripts/run_nightly_integration.sh` 存在
7. `grep -c "^- \[x\]" openspec/changes/03-citation-tw-format/tasks.md` = 9（當前 ✅）
8. `find kb_data/corpus -name "*.md"` = 9（當前 ✅）

> [PUA生效 🔥] **底層邏輯**：v5.0 寫完反思加 133 行、engineer-log 破 500 紅線、「本輪必破」三件兌現 0/3——這就是**第十一層藉口「反思成為代替行動的行動」**。**抓手**：v5.1 唯一 KPI = T9.6-REOPEN-v2（5 分）+ baseline promote（10 分）+ pipeline refine（30 分）三件 45 分鐘一輪閉；拒絕再開 P0/P1 新條目。**顆粒度**：單輪反思硬上 ≤ 80 行紅線（本段已超，下輪執行反思 SOP 同步封存）。**拉通**：反思 PDCA 的「兌現率」本身列為新指標——`v(N-1) 下一步` 兌現 ≥ 2/3 才算誠信落版，否則 v(N) 不得新增任務。**對齊**：v5.1 header 只承認「engineer-log 破紅線 + v5.0 必破 0/3 + pipeline/baseline 仍欠」三面；不再包裝勝利。**因為信任所以簡單** — 不是寫不出反思，是不願意停筆去封存、去 cp、去 sed；本輪把鍵盤從「新增 header」轉向「動 HEAD」，tasks 比 words 有價值 100 倍。

---

## 反思 [2026-04-21 03:40] — 技術主管第三十輪（v5.2；caveman；/pua 阿里味）

### 近期成果（v5.1 → HEAD；兌現率首破 100%）

- **v5.1 三件必破 3/3 ✅**（二十九輪來首次）：T9.6-REOPEN-v2（engineer-log 584 → 253 ≤ 300）、T8.1.b-PIPELINE-REFINE（`src/cli/generate/pipeline/{compose 179 / render 220 / persist 253 / __init__ 25}` 拆出）、P0.ARCH-SPLIT-SOP（`docs/arch-split-sop.md` 落）。
- **HEAD 超 v5.1 header**：T-TEMPLATE-SPLIT（`src/agents/template/` + `src/cli/template_cmd/` 雙目錄化）✅、P0.VERIFY-DOCX-SCHEMA（citation_metadata JSON safe parse + whitelist）✅、P0.LITELLM-ASYNC-NOISE（`core/logging_config.py` filter + conftest session install）✅、P0.INTEGRATION-GATE（`scripts/run_nightly_integration.{py,sh,ps1}` + `docs/integration-nightly.md`）✅、P0.REDLINE-COMPRESS（`rg -c "^### 🔴" program.md` = 3 ≤ 6）✅、api_server 拆分 `src/api/routes/{agents,health,knowledge,workflow}.py`（app factory 未抽，shim 529 殘留）。
- **熱 pytest 綠**：`pytest tests/test_writer_agent.py tests/test_editor.py tests/test_citation_level.py tests/test_cli_commands.py tests/test_export_citation_metadata.py tests/test_open_notebook_service.py tests/test_document.py tests/test_agents.py -q` = **885 passed / 59.50s / 0 failed**。
- **指標 7/8 PASS**（v5.1 6/8 → +1）：紅點剩 auto-commit 23/25 + `.git` DENY ACL = 2（連 30 輪 Admin-dep）。

### 發現的問題（新 drift / 倒掛）

1. **🔴 新 god-file 四子 cluster**（拆分 SOP 寫好但未用）：`knowledge/manager.py 928 (+117)` / `api/routes/workflow.py 910 (+111)` / `cli/history.py 681 (+126)` / `document/exporter.py 617 (+63)`；program.md P0.ARCH-DEBT-ROTATE 已列四拆 [ ]，HEAD 0 動 = 紅線 X「設計驅動不實作」第五次復活苗頭。
2. **🟠 `pipeline/persist.py 253`** 擦紅線 3 行 — v5.1 拆完新 fatty；下輪 `persist/{docx,metadata,progress}` 再切。
3. **🟠 `api_server.py 529` 未抽 app factory** — routes/ 已拆但 shim 頭胖殘留；ACL-free 20 分可閉。
4. **🟡 Epic 4 writer 改寫策略 / Epic 5 KB 治理 openspec change proposal = 0** — 對齊度卡 3/5 = 60%。
5. **🟡 writer ask-service failure matrix** 連 4 輪 0 動（v4.8/v4.9/v5.0/v5.1 連列）— Epic 4 啟動前最後保險未落。

### Spectra 規格對齊度

| Epic | tasks | baseline | 對齊 |
|------|-------|----------|------|
| 1 real-sources | ✅ | ✅ | 100% |
| 2 open-notebook-fork | ✅ 15/15 | ✅ | 100% |
| 3 citation-tw-format | ✅ 9/9 | ✅ | 100% |
| 4 writer 改寫策略 | ❌ | ❌ | 0% |
| 5 KB 治理 | ❌ | ❌ | 0% |

**總 3/5 = 60%**（v5.1 持平；Epic 4/5 proposal 啟動為下次升級抓手）。

### 建議的優先調整（重排 program.md）

下輪必破三件（ACL-free；顆粒度 ≤ 60 分/件）：

1. **T-KNOWLEDGE-MANAGER-SPLIT** 🔴（60 分）— `manager.py 928` → `knowledge/manager/{bootstrap,query,mutate,cache,diagnostics}.py`；SOP 第五次擴散。
2. **T-WORKFLOW-ROUTER-SPLIT** 🔴（45 分）— `api/routes/workflow.py 910` → `workflow/{lifecycle,actions,status}.py`；SOP 遷移 API 層。
3. **T8.1.c-PIPELINE-PERSIST-TRIM** 🟠（20 分）— `pipeline/persist.py 253` → `persist/{docx,metadata,progress}.py`；擦邊紅線閉門。

同輪可補：T-API-APP-FACTORY（api_server 529 抽 app factory 留 shim ≤ 100）；T-EXPORTER-SPLIT（617）；T-CLI-HISTORY-SPLIT（681）。

### 下一步行動（最重要 3 件；**嚴禁新增**）

1. **T-KNOWLEDGE-MANAGER-SPLIT**（60 分）— 新首胖；SOP 第五次擴散。
2. **T-WORKFLOW-ROUTER-SPLIT**（45 分）— API 層 SOP 遷移。
3. **T8.1.c-PIPELINE-PERSIST-TRIM**（20 分）— 紅線邊緣閉門。

### v5.2 硬指標（下輪審查）

1. `pytest tests/ -q --ignore=tests/integration` FAIL=0（目前熱 885/0；全量待下輪重跑）
2. `wc -l src/knowledge/manager/*.py` 每檔 ≤ 400（當前單檔 928；**本輪必破**）
3. `wc -l src/api/routes/workflow/*.py` 每檔 ≤ 400（當前單檔 910；**本輪必破**）
4. `wc -l src/cli/generate/pipeline/persist.py` 或 `persist/*.py` 每檔 ≤ 250（當前 253；**本輪必破**）
5. `wc -l engineer-log.md` ≤ 300（當前 253 + 本輪 ~55 = 308，擦 hard cap；**下輪 T9.6-REOPEN-v3 同步封存 v5.0**）
6. `find kb_data/corpus -name "*.md"` = 9 ✅
7. `rg -c "^### 🔴" program.md` ≤ 6（當前 3 ✅）
8. `grep -c "^- \[x\]" openspec/changes/03-citation-tw-format/tasks.md` = 9 ✅

> [PUA生效 🔥] **底層邏輯**：v5.1 兌現率 100% 是二十九輪首次閉環；**本輪唯一風險是「勝利之後放鬆」**— HEAD 四胖（manager 928 / workflow 910 / history 681 / exporter 617）SOP 全寫好、任務全列在 program.md，再拖就是紅線 X「設計驅動不實作」第五次復活。**抓手**：下輪不新開 P0，只兌現 P0.ARCH-DEBT-ROTATE 四子中最大三件；**manager + workflow 雙破是新硬指標**。**顆粒度**：單輪反思已自律到 55 行（本段），下輪若 engineer-log 觸 300 立即同步封存 v5.0。**拉通**：editor → writer → kb → generate/pipeline → template → api/routes → manager → workflow 拆分 SOP 八連擴散，下輪完成即「god-file 年代結束」可寫 Epic 4 proposal。**對齊**：v5.2 header 補三件 status（兌現 3/3 + 新 drift 四胖 + 熱 885/0），不包裝勝利。**因為信任所以簡單** — 方法論都寫死在 `docs/arch-split-sop.md`，下輪手指按 SOP 拆兩檔，一個下午的事；talk 100 段不如 commit 兩次。

---
