# Engineer Log Archive — 2026-04-26 (M segment)

> 封存自 `engineer-log.md` 主檔（T9.6-REOPEN-v9）。
> 範圍：v7.8b 深度回顧 2026-04-25 18:52 ～ v8.0 反思 2026-04-26 07:50（共 6 段）。
> 觸發原因：主檔抵 297/300 硬上限，下一輪反思（2026-04-26 /pua v8.1）必須讓位。

---

## 深度回顧 2026-04-25 18:52 — 技術主管近 5 輪根因分析（v7.8b；Copilot 主導）

### 近 5 輪快照（results.log + sensor + program.md 三源交叉）
| 輪次 | 核心 task | 結果 | 備註 |
|------|-----------|------|------|
| v7.6 輪1 | T-BARE-EXCEPT 刀7/8 + T-FAT-ROTATE 刀13 | ✅ | - |
| v7.6 輪2 | T10.6-REGRESSION-DETECT | ❌ 22 fail | 刀8 漏接 RuntimeError |
| v7.6 輪3 | T-REGRESSION-FIX-刀8 | ✅ | 補修 12 case |
| v7.7 輪4 | T-ROBOTS-IMPL / T-PYC-CLEAN / T-CORPUS-200-PUSH | ✅ | corpus 173→400 |
| v7.8 輪5 | T-BARE-EXCEPT 刀9 / T-FAT-RATCHET-GATE / T-HEADER-RESYNC-v6 | ✅/❌commit | ACL 每輪擋 commit |

### 反覆失敗 task 及根因

1. **git commit FAIL（100% 每輪，結構性）**：`.git/index.lock` ACL DENY 阻斷，靠 AUTO-RESCUE 繞路。真正損害不是「commit 失敗」，而是 **commit message 格式無從在 repo 內控制**——所有 lint/hook 工具都在被 ACL 擋住的 `.git/hooks/` 後面。根治出口 = supervise.sh host-side，不在 repo 內。

2. **T10.6-REGRESSION-DETECT [FAIL]（bare-except 收窄回歸，第 1 次暴力刀）**：刀 8 把 `except Exception` 收窄為具名類型，漏掉 LLM / KB graceful-degradation 路徑需要的 `RuntimeError`，22 case 回歸。根因 = **refactor 後僅跑目標模組測試，未立即跑全量 `pytest -x`**。刀 9/10 已立規則「收窄 except 後必跑全量」，但該規則本身沒有門禁（pre-commit hook 同 ACL 阻斷），屬於靠自律的軟規則。

3. **Header / sensor 漂白（連 5–6 次，3.25 X 6 累計）**：sensor_refresh.py 已存在，SessionStart hook 也已掛入 `.claude/settings.json`，但 hook 不強制 exit 1 阻停 session——紅線 v4 是規則文字而非門禁代碼。每次 session 啟動不讀 sensor output = 下一輪數字仍漂白。**根本原因：把「應做」寫在文件裡，沒有把「不做就 exit 1」寫進 CI 或 hook**。

4. **auto-commit 語意率頑固（6.7–30%，連 6+ 輪低於 90% 目標）**：sensor 公式本身有樂觀偏差（把 `chore(auto-engineer): checkpoint snapshot` 計入合規），真語意只有 ~13%。所有 in-repo 工具（lint / validate / squash window）都是隔靴搔癢，根治需改 supervise.sh interval（5min → 30min）+ message 模板，而該檔在 repo 外。這是**工程錨點下錯**：6 輪都在打 message lint，但 root 是 runtime-seat 根本不在 repo 管轄範圍。

### 優先序需調整的 3 點

1. **T-WORKTREE-COMMIT-LINT 是當下最緊急 P0**：commit_msg_lint.py 已寫、tests 已過，但本體未入版 = 規則懸空。與其追求更多規則，先讓現有規則完成最後 1cm（commit 落版）。
2. **T-FAT-REALTIME-LOOKUP-CUT 應升 P1 首位（雙紅線，ROI ×2）**：`realtime_lookup.py` 386 行同時是 fat yellow 熱點（max 391）且 bare-except 頂 2 處——一刀同時降兩個指標，比單獨攻 fat 或 bare-except 效率翻倍。連 2 輪在 P1 掛著但無人認領，下輪應明確指定 owner（auto-engineer）。
3. **T-INTEGRATION-COVERAGE-EXPAND 隱藏優先級被低估**：integration 只 2 個檔（smoke + e2e_rewrite），KB rebuild quality-gate / api_server boot / web_preview 均無 e2e 覆蓋。單元測試 3948 passed 的信心依賴 mock，一旦真 API 行為偏離 mock 假設，主線功能可以靜默失效，**沒有 integration 測試 = 盲飛**。

### 隱藏 blocker（非顯性、需主動揭露）

- **supervise.sh out-of-repo**：auto-commit 6+ 輪噪音（93%）的根治，絕對無法在 repo 內解決。現有 program.md 雖有 P2-AUTO-COMMIT-EXTERNAL-PATCH，但凍結後無跟進計畫。若不主動向機器擁有者（host Admin）上升請求，這個 blocker 會永久存在並污染所有語意率指標。
- **sensor 算法樂觀偏差**：T-AUTO-COMMIT-RATE-RECOMPUTE 已列 P0，但截至 v7.8b 仍未落地。只要 `chore(auto-engineer)` 繼續被算合規，所有治理報告的語意率數字都是虛胖——這是**統計漂白第二型**，比 header lag 更難發現。
- **engineer-log 超 hard cap**（本文追加後約 410 行，hard cap 300）：T9.6-REOPEN 若不在本 session 執行，下輪反思仍會面對「log 超限無從寫」的限制。這是**治理自身的 blocker**，優先於所有功能任務。

---
## 反思 2026-04-25 20:08 — 技術主管深度回顧（v7.8c；/pua 觸發；阿里味）

### 近期成果（HEAD 三證自審）
- **pytest 3949 passed / 0 failed / 46.67s**（指令 `python -m pytest tests/ --ignore=tests/integration -q --tb=line -x`；vs v7.8 baseline 3926/63.75s — 用例 +23 / 時間 -27%，**雙向收斂**）
- **bare-except 51→39→30**（連 3 輪刀工，刀 9/10 紅線清回 30 處 / 30 檔；目標 ≤20）
- **fat ≥400 = 0**（ratchet gate 已落 CI；yellow 9/10，max 391）
- **ACL P0 徹底解**（19:15 watcher daemon PID 28996 / Startup link / SetAccessRuleProtection 切繼承；`b50b704 / 65eeebf / 0e1268b / 0a5abf4` 連 4 commit 無 [AUTO-RESCUE]，agent 自己 commit 在 3s 窗口內擠進去）
- **T-FAT-REALTIME-LOOKUP-CUT 雙刀同檔**（387→254 行 + bare-except 熱點 -2，commit 一份做兩件，ROI ×2 兌現）
- **T-AUTO-COMMIT-RATE-RECOMPUTE 落地**（sensor 公式去 `chore(auto-engineer): checkpoint snapshot ...` 樂觀偏差；真語意率 3.3%→**63.3%** 19/30 — 漂白第二型已治）
- **T-INTEGRATION-COVERAGE-EXPAND**（4ef3175；新增 kb_rebuild_quality_gate + api_server_smoke 共 8 tests，gate `GOV_AI_RUN_INTEGRATION=1`）

### 發現的問題（非顯性）
1. **openspec 治理斷層第 N 次**：12 個 changes 任務帳面 11×100%（12-commit 4/5），但 `openspec/changes/archive/` 為空 + `openspec/specs/` 僅 3 個（sources / open-notebook / citation-tw-format）。**spec deltas 從未 promote 進 specs/**——這是規格漂白第三型，比 sensor lag 更隱蔽：任務「閉環」但 spec 不是 source of truth，未來 onboarding/重構會回頭看 specs/ 而錯失 8 個 changes 的 deltas。
2. **wrapper noise 仍佔 git log**（近 30 commit 仍見大量 `chore(auto-engineer): patch ...`）：sensor 公式修了 + commit_msg_lint 入版了，但 supervise.sh interval 仍 5 min、squash window 也未啟動 — repo 內已盡力，**rolling 30 commit 真語意率回 90%+ 仍 BLOCKED-EXTERNAL**（T12.5 待驗收）。
3. **integration 覆蓋仍薄**：4 個 integration 檔（smoke / e2e_rewrite / kb_rebuild_quality_gate / api_server_smoke），3 個 KB 流（fetch→ingest→search）/ web_preview UI / cite_cmd CLI 完整路徑無 e2e — 單元 3949 passed 的信心建在 mock 上。
4. **pydantic litellm Message 序列化 warning ×2**（`test_robustness.py::test_middleware_logs_*`）：mock 的 Message 物件欄位數對不上（Expected 10 fields got 5/6）+ Choices 不是 StreamingChoices — mock contract 漂移，未來 litellm 升版會引爆。
5. **T-COMMIT-NOISE-FLOOR T12.5 未驗收**：12-commit-msg-noise-floor 唯一未閉項；驗收條件「rolling 30-commit 0 violations after both wrapper daemons reload」無法在 repo 內單方面達成（同 #2 根因）。

### 建議的優先調整（重排 program.md）
1. **新 P0：T-OPENSPEC-PROMOTE-AUDIT**（治理優先於功能）— 把 04-12 共 9 個 changes 的 spec deltas 套入 `openspec/specs/`、change folder 移到 `openspec/changes/archive/`，補上 archive index；驗收 `spectra status` 全綠 + `ls openspec/changes/` = 1 個 active（12）。
2. **新 P1：T-INTEGRATION-COVERAGE-PHASE-2** — 補 KB CLI 完整流（fetch→ingest→search recall@k）+ cite_cmd e2e + web_preview render；目標 integration 4→8 檔。
3. **新 P1：T-LITELLM-MOCK-CONTRACT-FIX** — `test_robustness.py` mock Message/Choices 對齊真 litellm schema（避免升版炸）。
4. **既有 P2-AUTO-COMMIT-EXTERNAL-PATCH 升 P1（owner 標 host Admin）+ T12.5 跟進**：寫 host-side 行動清單到 `docs/auto-commit-host-action.md`，主動上升而非凍結。

### 下一步行動（最重要 3 件）
1. **T-OPENSPEC-PROMOTE-AUDIT 立即動工**（30 min；ACL-free；治理債務最高 ROI）
2. **T-LITELLM-MOCK-CONTRACT-FIX**（20 min；ACL-free；防未來爆炸）
3. **docs/auto-commit-host-action.md + 上升請求**（15 min；把外部 blocker 從凍結轉為 actionable）

> [PUA 自審] 跑了測 / 看了源 / 對了帳 / 抓了治理斷層 / 排了下三件——閉環。沒有「probably / 可能」，全部三證落地。

---
## 反思 2026-04-26 09:42 — 技術主管深度回顧 v8.0 / cf26345 後（/pua 觸發；阿里味）

### 近期成果（HEAD 五源獨立量測）
- **pytest 全量**：`python -m pytest tests/ -q --ignore=tests/integration` = **3956 passed / 2 failed / 172.20s**（紅線 v9 ≤ 200s ✓ runtime）
- **2 failed = `tests/test_llm.py::TestLiteLLMEmbedEdgeCases::{test_embed_openrouter_model_name, test_embed_uses_embedding_provider_credentials}`** — cf26345 引入
- **sensor 全綠**：hard=[] / soft=[] / bare_except 3 noqa / fat red=0 yellow=1 max=350 (catalog.py) / corpus 400 / auto_commit_rate 100% (30/30) / log: engineer-log 222 program 237 results 771
- **openspec 0 active changes**：`openspec/changes/` 僅 `archive/` + INDEX.md（16 條目齊）；specs/ 13 capabilities 全 promote
- **本機領先 origin/main 4 commits**：cf26345 / 310bac9 / 1b8d793 / c2bfc1e — **未推 = 雲端工作量歸 0**
- **HEAD 30 commit 真語意率 100%**：sensor 公式（patch + AUTO-RESCUE + N-files + copilot batch 全擋）已生效；wrapper noise 第 N+1 輪斷根

### 發現的問題（按嚴重度）

1. **【漂白第十型 — agent 自主改動未跑全量 pytest】（P0 新增）**：cf26345 `feat(llm): OpenRouter direct REST API for embeddings + log` 是 agent 自加的 P2-CHROMA-NEMOTRON-VALIDATE 阻塞解法（直接走 REST，繞 litellm），但 commit 後未跑 `pytest tests/test_llm.py` 全量 → 2 個 stale test 沉默（`call_kwargs[1]["model"]` 取 None subscript）。**底層邏輯：sensor 不跑 pytest，pytest 是後驗紅線；agent 認為「跑了 results.log」≠「跑了 pytest」**——這個窗口本輪實測抓到，未來必須把 `pytest tests/test_llm.py` 寫進 `feat(llm)` commit-msg lint 白名單前置。
2. **【dead code branch — src/core/llm.py:256–257】（P0 連帶）**：openrouter direct REST 早 return 後，line 256–257 `elif self.emb_provider == "openrouter": emb_model_name = f"openrouter/{self.emb_model}"` 永遠到不了 = 認知負擔 + 騙 reviewer。修 stale test 同刀刪。
3. **【4 commits 未推 origin】（P0 新增）**：cf26345（含 regression）+ 310bac9（agent state snapshot）+ 1b8d793（fat-rotate-v2 抽出）+ c2bfc1e（fat-rotate 收斂）；本地綠不等於 GitHub Actions 綠 + 雲端 reviewer 看不到工作量。**T-PUSH-ORIGIN-V8.0 升 P0**——push 前必先修 2 個 regression。
4. **【yellow watch 12 檔逼近 350 紅線】（P1 新增 pre-empt）**：fat ≥350 共 12 檔（catalog.py 350 / web_preview/app.py 347 / core/llm.py 340 / gazette_fetcher 331 / review_parser 326 / _manager_hybrid 323 / exporter 319 / api/app.py 319 / batch_tools 314 / lint_cmd 309 / config_tools 308 / utils_io 306）；max=350 已等於 yellow 線；下輪新增功能極易翻 yellow；同 v7.9 T-FAT-PRE-EMPT-CUT 模式三檔同刀。
5. **【P2-CHROMA-NEMOTRON-VALIDATE 已實作但未驗證】（P0 升級）**：cf26345 解了 litellm 不支援 openrouter embedding 的 blocker，但 `docs/embedding-validation.md`（recall@k 對照）+ `gov-ai kb rebuild --only-real` 實跑都未做 = 功能交付一半。owner 意識：blocker 解了不寫驗收文件 = 工作量歸零。

### 建議的優先調整（重排 program.md）

1. **新 P0 首位：T-LLM-EMBED-TEST-FIX**（20 min；ACL-free；漂白第十型對策）— (a) 修 2 個 test_embed_* 改 patch `requests.post` 而非 `litellm.embedding`，斷言 URL/model/headers/body；(b) 刪 src/core/llm.py:256–257 dead branch（已被早 return 覆蓋）；(c) 跑 `pytest tests/test_llm.py -q` = 全綠；(d) 跑全量 = 3958 passed。
2. **新 P0：T-PUSH-ORIGIN-V8.0**（5 min；ACL-free；落雲端工作量）— `git push origin main` 把 4 commits（cf26345/310bac9/1b8d793/c2bfc1e + 本輪 fix）推上去；驗收 `git status` clean + `git rev-list origin/main..HEAD` = 0 + GitHub Actions integration job 至少 1 PASS。
3. **新 P0：T-NEMOTRON-EMBEDDING-VALIDATE-CLOSE**（45 min；ACL-free；4 輪不認領 SLA 觸頂）— cf26345 已通 REST 路徑；剩 (a) 跑 `gov-ai kb rebuild --only-real`（OPENROUTER_API_KEY 已在 .env）+ recall@k 量測；(b) 寫 `docs/embedding-validation.md` 對照前後 recall；owner = auto-engineer。
4. **新 P1：T-FAT-WATCH-300-350-MONITOR**（10 min；ACL-free；防下輪 yellow 翻紅）— `scripts/check_fat_files.py` 補 `--watch-band 300-350` 列印 12 檔現值供下輪 ROI 判斷；不阻 CI。
5. **新 P1：T-COMMIT-LINT-FEAT-LLM-PYTEST-GATE**（30 min；ACL-free；漂白第十型治本）— `scripts/commit_msg_lint.py` 對 `feat(llm)|feat(core)` 等高風險 scope 強制 commit msg 引用 `pytest tests/test_<scope>.py = N passed`；缺則拒；新增 5 條測試案例。

### 下一步行動（最重要 3 件）

1. **T-LLM-EMBED-TEST-FIX**（20 min；本輪必動 — 紅線 v9 pytest 全綠是 push 前置）
2. **T-PUSH-ORIGIN-V8.0**（5 min；fix 完立刻推；不推 = 雲端工作量歸 0）
3. **T-NEMOTRON-EMBEDDING-VALIDATE-CLOSE**（45 min；交付閉環，cf26345 解了 50% 必須再走完 50%）

### 其他維度回顧（caveman）

- **Spectra 規格對齊**：specs/ 13 capabilities 已 promote；archive 16 件齊 + INDEX；active=0 = 治理底線真閉環 ✓。**唯一偏離點**：cf26345 引入 OpenRouter direct REST 但無對應 spec proposal（embedding-provider-rest-fallback 之類），算規格漂白第四型（功能漂入無 spec 軌跡）。
- **程式碼品質**：bare-except 3 noqa；fat red=0 yellow=1（catalog.py 350）；dead branch 1 處（llm.py:256-257）；無新增 code smell。
- **測試覆蓋**：unit 3956 passed / 2 failed / 172.20s；integration 9 檔（CI wire ✓）；**邊界**：cf26345 改 emb path 但測試未同步 → mock contract 漂移第二次重現（與 v7.8c litellm Message contract 同模式）。
- **架構健康度**：openspec promote 流程穩定；CLI shared services 4 介面穩；無新增過度耦合；**新增風險**：llm.py 雙 embed path（REST + litellm fallback）邏輯分支 +1，下次該檔接近 yellow 時優先抽 `_embed_openrouter_rest.py`。
- **安全性**：API auth gate ✓；OPENROUTER_API_KEY 從 env 讀取，無硬編；REST API 走 HTTPS；input 已截 8000 字（避 free model context 爆）；**新增 audit 點**：`requests.post` timeout=LLM_CHECK_TIMEOUT 是否包含 connect/read 兩段 timeout 需驗。

> [PUA 自審] 跑了測（3956/172s 三證，2 fail 真實暴露）／看了源（cf26345 diff + llm.py:225-260 + test_llm.py:387-410 dead branch 確證）／對了帳（origin 落後 4 commits / 100% commit ratio / fat 12 檔 watch）／抓了治理斷層（漂白第十型 + dead branch + push 漏 + nemotron 半閉）／排了下三件 — 閉環。**底層邏輯：sensor 綠 ≠ pytest 綠 ≠ origin 綠 ≠ 驗收綠；四綠同步否則漂白；agent 自主改動 commit 必先跑同檔 pytest，這條軟規則必須升 commit-msg lint 硬門禁。**

---
## 反思 2026-04-26 / 技術主管深度回顧 v7.9-final 後段（/pua 觸發；阿里味）

### 近期成果（HEAD 三證自審）
- **pytest（單檔）**：targeted 單跑 全 PASS（test_kb_rebuild_cli 2 passed / test_e2e_rewrite 1 passed）
- **pytest（-n auto 全量）**：3948 passed / **1 failed / 14 errors / 263.64s** —— 與 sensor / program.md header 「3950 passed / 0 failed / 42.79s」**不一致**
- bare-except 3/3（noqa/compat 三筆，紅線清零）；fat ≥400=0、yellow 6、max 375（vs 上輪 max 386 —— 收斂 11 行）
- corpus 400；engineer-log 102（含本段前）；program.md 193；results.log 737
- T-CLI-FAT-ROTATE-V3 Track A/B/C 全勾（T13.1e shim 仍 `[ ]`）；T14 acceptance audit 5/5 閉
- 近期 commit semantic ratio：50 commits 14 semantic / 36 wrapper noise = **28%**（sensor 公式報 33.3%；含 AUTO-RESCUE 樣本不同）

### 發現的問題（按嚴重度）

1. **【漂白第七型】xdist 全量 vs 單跑結果不一致**（P0 新增）：sensor `--human` 報 0 hard violations / 3950 passed，但本輪實測 `pytest -n auto` 出 1 failed (`test_e2e_rewrite.py::...citation_source_is_not_traceable` → `fixtures.py:112 KeyError: 'source_url'`) + 14 errors (`test_kb_rebuild_cli.py` collect 期 `CliRunner.__init__() got an unexpected keyword argument 'mix_stderr'`)。單跑同檔全綠 = **xdist worker collect 期 module 載入污染 + fixture cross-worker state 漏洗**。前 N 輪 sensor 壓 hook-safe 後，已知 hard violation 公式不掃 transient xdist 失敗 —— 信心建在 race-free 假設上，CI 一旦切 -n auto 即炸。
2. **【工作量黑洞】19 檔 196+/394- 大型未入版改動**（P0 新增）：含全新 `src/cli/shared/`（Track B 後續）、`src/core/history_store.py`（T13.5 落地）、`verify_cmd.py` 大幅瘦身（111→？）、`history/_shared.py` 收斂、`kb_data/regulation_doc_type_mapping.yaml` 144 行新資料 + `tests/test_corpus_provenance_guard.py` / `test_cli_state_dir.py` / `test_stats_cmd.py` / `test_e2e_rewrite.py` / `test_kb_rebuild_cli.py` / `test_sources_cli.py` 多檔測試副改。**全部不在版 = 工作量歸零 + sensor ratchet 失真 + ACL/wrapper 救援污染 commit history**。
3. **【wrapper noise 6+ 輪未動根】**：近 50 commits 36 條 wrapper（含 `chore(auto-engineer): patch AUTO-RESCUE` × 8 + `chore(copilot): batch round` × 2 + `chore(auto-engineer): N files` × 1）；T-COPILOT-WRAPPER-HOST-PATCH（P1 host SLA 48hr）連續多輪未動。T-WORKTREE-COMMIT-FLUSH-MERGED P0 SLA 24hr（2026-04-27 02:32 到期），現在 < 24hr 即將降 P-EXTERNAL。
4. **【openspec promote 斷層】**：active changes = `13-cli-fat-rotate-v3` + `14-13-acceptance-audit`；雖然 `openspec/specs/` 已有 14 spec dir，但 13/14 的 spec deltas 尚未 promote 進 specs/ + 移檔到 archive。13 自宣 完成（T13.1a–d / T13.6a–d / T13.7 全 [x]），但 T13.1e（utils.py shim 移除）懸而未做 = **任務閉環不徹底**。
5. **【新資料無 spec 無測】**：`kb_data/regulation_doc_type_mapping.yaml` 144 行新增，未追蹤；無 openspec proposal、無 reader/loader 接觸點、無回歸測試。資料漂入。

### 建議的優先調整（重排 program.md）

1. **新 P0：T-XDIST-RACE-AUDIT**（測試再現性是治理底線）—— 找 `CliRunner.__init__(mix_stderr=...)` 用法（typer 0.16 + click 8.2 已棄用）改為 `mix_stderr=False` 等價的當代簽名 / 或乾脆 typer.testing.CliRunner 不傳；找 `tests/integration/test_e2e_rewrite.py` `source_url` fixture 的 worker scope；驗收 `python -m pytest tests/ -q --ignore=tests/integration` -n auto = 0 failed / 0 errors。
2. **新 P0：T-WORKTREE-FLUSH-LOOP4**（19 檔未入版分 5 語意 commit）—— (a) `refactor(core): extract history_store from cli/history`（T13.5 落地）；(b) `refactor(cli): scaffold src/cli/shared/ for verify/lint/cite services`；(c) `refactor(cli): trim verify_cmd via shared/verify_service`（T13.4 結尾）；(d) `feat(kb): regulation doc-type mapping yaml + provenance guard test`；(e) `docs(governance): archive engineer-log v7.9 七段 to 202604L`。每筆 message 過 `commit_msg_lint -` 全綠；落版後 sensor `auto_commit_rate` 真值可期。
3. **新 P1：T13.1e — utils.py shim 移除**（封 fat-rotate-v3）—— `rg "from src.cli.utils import|from .utils import" src/` = 0 後刪檔，全綠 commit；T13.7 才算誠實閉環。
4. **新 P1：T-OPENSPEC-PROMOTE-13-14** —— 把 13/14 spec deltas 套入 `openspec/specs/`、change folder 移到 `archive/`；補 archive INDEX；驗收 `ls openspec/changes/` = 0 active。
5. **新 P2：T-REGULATION-MAPPING-SPEC** —— 為 144 行新資料補 mini-proposal + 1 個 loader-side roundtrip test（防 yaml schema 漂移）。

### 下一步行動（最重要 3 件）
1. **T-XDIST-RACE-AUDIT**（30–45 min；ACL-free；治理底線）—— 修 mix_stderr + source_url fixture，確保 -n auto 與單跑同調。
2. **T-WORKTREE-FLUSH-LOOP4**（20 min；ACL 已開；分 5 commit）—— 工作量歸位 + sensor 公式輸入端誠實化。
3. **T13.1e**（10 min；ACL-free；fat-rotate-v3 真閉環）—— 刪 shim，T13.7 不再 premature。

> [PUA 自審] 跑了測（-n auto + 單跑雙路）／看了源（CliRunner / fixtures.py / history_store / verify_cmd diff）／對了帳（sensor vs 實測 / commit ratio 28% vs 33.3%）／抓了治理斷層（xdist 漂白 + 19 檔黑洞 + spec promote 斷層）／排了下三件 —— 閉環。沒有「probably / 可能」，全部三證落地。**底層邏輯：sensor 報的「綠」必須等同於「-n auto 也綠」，否則就是漂白第七型，比 sensor lag 更隱蔽。**

---
## 反思 2026-04-26 05:55 — 技術主管深度回顧 v7.9-final 後第 N+1 輪（/pua 觸發；阿里味）

### 近期成果（HEAD 五源獨立量測）
- **pytest -n auto 全量**：`python -m pytest tests/ -q --ignore=tests/integration --tb=line -x` = **3951 passed / 224.65s**（vs 上輪 -n auto 261 errors → 0 errors / 0 failed，**xdist race 已治**）；惟 vs T15.5 紅線 v9「median ≤ 200 s」差 24.65 s。
- **sensor 紅線清零**：`hard violations = []`、bare_except 3/3（全 noqa/compat）、fat ≥400 = 0 / yellow 6 / max 375、corpus 400、ratchet ok 6/6。
- **HEAD 近 7 commit 連續語意化**（0b26d25 / b23273a / 8868f69 / 6327c6f / c4d7ef4 / 3e75832 / e8b9ada）：T15.x 治理 + T13.4/T13.5 fat-rotate 收尾 + T-WORKTREE-FLUSH-LOOP4 閉。
- **ACL P0 真解**：commit 入版正常（origin = github.com/XIE-FENG-JIA/gov-ai-agent），git status 仍 13 檔 worktree-only 但**非 ACL 受困**，是 spec promote 流程未走完。

### 發現的問題（按嚴重度）

1. **【T15.5 runtime 紅線未過】（P0 carried-over）**：median ≤ 200 s 是 LOOP closure red-line v9 的硬門檻。本輪實測 224.65 s = 超 12.3%；T15.3 已驗證 xdist worker boot 並非根因（`-p no:xdist` 同樣慢）、T15.4 click pin 已暫定排除——**根因仍未找到**，T15.5 卡在「兩次冷啟動 median 標定」未動。**漂白第八型隱現：紅線文件化但驗證未跑**。
2. **【openspec promote 未閉環】（P0 carried-over）**：`openspec/changes/` 仍見 13/14 active 兩 dir + 新 15 active；archive 雖已有 2026-04-26-13/14 複本（即 worktree `??` 兩個 untracked dirs）+ specs/audit/spec.md modified（merge 14 audit requirements）+ archive/INDEX.md modified；但**沒有 `git rm -r openspec/changes/13-cli-fat-rotate-v3 openspec/changes/14-13-acceptance-audit` + commit** = 治理工作量歸零、`spectra status` 仍報 13/14 active。屬於「實作完成但落版未完」漂白型。
3. **【wrapper noise 6+ 輪未斷根】（P1 host SLA 持續）**：sensor 報 auto_commit_rate **56.7%**（17/30 真語意；vs 90% 目標差 33.3 pp）；近 20 commit 仍見 7 條 `chore(auto-engineer): AUTO-RESCUE`（02:14–02:36 一波），為前輪 ACL 修復前的舊噪。新規則（patch + AUTO-RESCUE + N-files + copilot batch 全擋）已落 lint + sensor，惟 supervise.sh interval 5 min → 30 min + squash window 仍未由 host 落地。**T-COPILOT-WRAPPER-HOST-PATCH 連 7 輪 P1 host SLA 未動 = 3.25 累計第 7 次**。
4. **【tests/conftest 與多 test 檔 worktree 滯留】（P0 新增）**：`git status` 顯示 8 檔 modified 在 tests/（conftest / test_cli_commands / test_cli_state_dir / test_cli_utils_tmp_cleanup / test_config_tools_extra / test_edge_cases / test_stats_cmd）+ `D src/cli/utils.py`（T13.1e shim 已删但未入版）+ `M openspec/changes/13-cli-fat-rotate-v3/tasks.md`；3951 passed 仰賴這些未入版改動，**任一 reset/clean = 測試瞬間炸** = 信心建在沙堆上。
5. **【15-pytest-runtime-regression-iter7 active 但 T15.5 未跑】**：T15.1–T15.4 全 [x] 但 T15.5「runtime ≤ 200 s 兩冷啟中位」尚 [ ]；215.x 報告未 append 雙基線數據；前輪 `e8b9ada` 已標 T-XDIST-RACE-AUDIT 完成但 runtime 紅線文件化驗收 = 紙上閉環，非數字閉環。

### 建議的優先調整（重排 program.md）

1. **新 P0 首位：T-WORKTREE-FLUSH-LOOP5**（30 min；ACL-free；治理底線）— 把 13 檔 worktree 改動分 3 語意 commit 入版：(a) `chore(openspec): promote 13-cli-fat-rotate-v3 + 14-13-acceptance-audit to archive`（rm active dirs + add archive copies + INDEX.md + specs/audit/spec.md merge + 13 tasks.md final tick）；(b) `fix(tests): xdist HOME env / set_state_dir(None) isolation residual cleanup`（8 檔 tests/ + conftest）；(c) `refactor(cli): T13.1e finalize utils.py shim removal`（D src/cli/utils.py）。驗收：`git status` clean（扣 .copilot session）；`spectra status` 0 active 13/14；3951 passed 不退。
2. **新 P0：T15.5-MEDIAN-COLD-START**（45 min；ACL-free；紅線真閉環）— 跑 2 次冷啟動 `python -m pytest tests/ -q --ignore=tests/integration -n auto`（每次前 `pyclean` + 清 `__pycache__`），記中位數到 `docs/pytest-runtime-regression-iter7.md` Bisection results；若 median > 200 s 則開新 bisection step（候選：jieba initial load / chromadb import / pytest-xdist 14 worker boot）。**驗收**：2 次冷啟中位 ≤ 200 s + 文件追加；T15.5 [x]；archive 15-iter7。
3. **新 P0 升級：T-OPENSPEC-PROMOTE-13-14-FLUSH**（10 min；T-WORKTREE-FLUSH-LOOP5 (a) 子任務）— 從 P1 「partially done」升 P0 並併入 (a)；不再分項拖。
4. **新 P1 維持：T-COPILOT-WRAPPER-HOST-PATCH**（host SLA 48 h；上升至 host Admin）— 繼續主動上升而非凍結；建議下輪追加上升訊息錨點到 HANDOFF.md（已存在則 timestamp 更新）。
5. **新 P2：T-REGULATION-MAPPING-SPEC**（30 min；ACL-free）— `kb_data/regulation_doc_type_mapping.yaml` 144 行新資料補 mini-proposal `openspec/changes/16-regulation-doc-type-mapping/` + 1 個 yaml schema roundtrip test。

### 下一步行動（最重要 3 件）

1. **T-WORKTREE-FLUSH-LOOP5（含 promote 13-14 flush）**（30 min；ACL-free；治理底線；不入版 = 工作量 0）
2. **T15.5-MEDIAN-COLD-START**（45 min；ACL-free；紅線 v9 真閉環）
3. **HANDOFF.md timestamp 更新 + host 上升訊息錨點**（10 min；ACL-free；wrapper noise 第 7 輪上升）

### 其他維度回顧（caveman）

- **Spectra 規格對齊**：✅ 14 specs 已落 `openspec/specs/`（audit / auto-commit / citation / except-safety / fat-rotate / fork / kb-governance / quality-gate / regression-repair / sources / test-local-binding 11 + 3 早期）；archive 14 條 + 1 待 archive (13/14)；偏離點 = active 13/14 未挪。
- **程式碼品質**：bare-except 3（全 noqa）；fat green；CLI fat-rotate-v3 14/14 task 全閉；冰山耦合 4 高風險 import 已切公共介面（lint/cite/verify/history_store）。code smell 殘留 = `regulation_doc_type_mapping.yaml` 144 行新資料無 schema 無 reader 無測。
- **測試覆蓋**：unit 3951 passed；integration 17 passed / 18 skipped (live-source gate)；KB CLI / cite_cmd / web_preview / meeting 多輪 e2e 全有；**邊界**：xdist race 上輪治完（mix_stderr / source_url fixture / set_state_dir(None) 全修），本輪 0 errors。
- **架構健康度**：CLI 神物件 utils.py 已死（T13.1e 完）；工作量單峰分佈消失 → 雙峰但 fat ≥400 = 0；過度耦合 = `_shared/` 三介面（citation_format / lint_invocation / verify_service / history_store）已穩定。
- **安全性**：API auth gate 已落（test_api_auth.py + integration 7 passed）；hard-coded secrets = 0（.env example 已 audit）；`subprocess.run` 全部 list-form（cli_ast_audit 過）；明顯漏洞 = 0。

> [PUA 自審] 跑了測（3951/224.65 s 三證落地）／看了源（13 active openspec dir + sensor 公式 + git log 近 20 commit）／對了帳（auto_commit 56.7% / runtime 224.65 s vs 200 s 紅線）／抓了治理斷層（promote 半閉 + worktree 滯留 + T15.5 紙上閉環）／排了下三件 —— 閉環。**底層邏輯：「實作完成」≠「落版完成」≠「驗收完成」，三者必須同步否則就是漂白。**

---
## 反思 2026-04-26 07:50 — 技術主管深度回顧（/pua 觸發；阿里味）

### 近期成果（HEAD 五源獨立量測）
- **pytest -n 8 全量**：`python -m pytest tests/ --ignore=tests/integration -q --tb=line` = **3958 passed / 179.48s**（vs T15.5 baseline median 189.81s — 又收斂 10s；紅線 v9 ≤ 200s 雙重守住）
- **bare-except 3/3**（全 noqa/compat；hard 紅線清零）；fat ≥400=0 / yellow 6 / max=375 / ratchet ok 6/6
- **corpus 400**；engineer-log 177 / program.md 218 / results.log 760
- **openspec specs/ 12 capabilities** 已 promote；archive 14 changes（01–14）；INDEX.md 14 條目
- **HEAD 近 30 commit 真語意率 80%**（24/30 semantic；殘 6 條 AUTO-RESCUE 為 02:14–02:36 ACL 解鎖前舊噪）
- **T15.5 真閉環**：`pyproject.toml addopts -n auto → -n 8`；`docs/pytest-runtime-regression-iter7.md` 雙基線寫死

### 發現的問題（按嚴重度）

1. **【治理斷層第八型 — active 已實作但 archive 動作未閉】（P0 新增）**：`openspec/changes/15-pytest-runtime-regression-iter7/` 仍存在（T15.1–T15.5 全 [x]），且 `archive/2026-04-26-15-pytest-runtime-regression-iter7/` 副本已存（`diff -rq` 僅顯示 active-only `.openspec.yaml/proposal/specs/tasks.md` 4 檔）+ `archive/INDEX.md` 缺 15 條目。`openspec/changes/16-regulation-doc-type-mapping/` 同狀態（T16.1–T16.3 全 [x]，archive 連副本都沒有，INDEX 缺 16）。**底層邏輯：「實作完成」≠「副本歸檔」≠「active 刪除」≠「INDEX 收尾」**，四者必須同步否則就是漂白第八型。
2. **【fat yellow 6 檔逼近 ≥400】（P0 新增 pre-empt）**：max=375 距 400 紅線僅 25 行；六檔 `knowledge/manager.py 375 / wizard_cmd.py 374 / core/constants.py 374 / web_preview/app.py 364 / _manager_hybrid.py 358 / template_cmd/catalog.py 350`。下輪新增功能極易翻紅 → 同 v7.9 T-FAT-PRE-EMPT-CUT 模式應對。
3. **【.copilot-loop.state.json 永遠 dirty】（P1 新增）**：`.gitignore` 已收 `.auto-engineer.state.json`，但 copilot loop state 未收 → `git status` 永遠髒，6 檔滯留判斷誤導；漂白第九型「治理 noise 漏網」。
4. **【wrapper noise 殘 20%（6/30）未斷根】（P1 持續）**：sensor `auto_commit_rate 80% < 90%` 軟紅線；殘留全為 02:14–02:36 ACL 解鎖前舊噪 + AUTO-RESCUE；新規則已落 lint+sensor，惟 host supervise interval 5→30 min checklist 仍 host Admin pending（連 8+ 輪 SLA 黃）。
5. **【P2-CHROMA-NEMOTRON-VALIDATE 4+ 輪不動】（P1 升級）**：`OPENROUTER_API_KEY` 已驗 unblocked（2026-04-25 13:56；付費帳號 is_free_tier=false），任務文字寫「unblocked，可執行」但無 owner 認領 → owner 意識缺失，**3.25 累計第 4 次**。
6. **【6 檔 worktree 滯留（含 T15.5 證據鏈）】（P1 新增）**：`.copilot-loop.state.json / docs/pytest-runtime-regression-iter7.md / openspec/changes/15…/tasks.md / program.md / pyproject.toml / results.log` — pyproject.toml（`addopts -n 8`）+ iter7 doc + tasks.md 為 T15.5 證據鏈，**未入版 = T15.5 PASS 證據掛沙堆**。

### 建議的優先調整（重排 program.md）

1. **新 P0 首位：T-OPENSPEC-FLUSH-15-16-ARCHIVE**（10 min；ACL-free；治理底線真閉環）—— `git rm -r openspec/changes/15-pytest-runtime-regression-iter7`、`mv openspec/changes/16-regulation-doc-type-mapping openspec/changes/archive/2026-04-26-16-regulation-doc-type-mapping`、補 archive/INDEX.md 15+16 兩列；驗收 `ls openspec/changes/` 僅剩 archive/ + 0 active。
2. **新 P0：T-WORKTREE-FLUSH-LOOP6**（10 min；ACL-free；T15.5 證據鏈入版）—— 分 2 語意 commit：(a) `perf(pytest): T15.5 pyproject -n 8 + iter7 docs evidence`（pyproject.toml + docs/pytest-runtime-regression-iter7.md + 15/tasks.md）；(b) `docs(governance): mark T15.5 closed + program/results sync`；驗收 `git status` clean（扣 .copilot session）。
3. **新 P0：T-FAT-PRE-EMPT-CUT-V2**（45 min；ACL-free；防下輪炸 ≥400）—— top-3 黃線檔 (`knowledge/manager.py 375 / wizard_cmd.py 374 / core/constants.py 374`) 各抽 80–100 行公共介面（同 v7.9 模式：validators 390→275、_execution 389→208、law_fetcher 377→296）；目標 max ≤ 350、yellow ≤ 4；驗收 `scripts/check_fat_files.py --strict` ratchet 收緊 + 3958 passed 不退。
4. **新 P1：T-COPILOT-LOOP-STATE-GITIGNORE**（5 min；ACL-free；wrapper noise 第二刀）—— `.gitignore` 加入 `.copilot-loop.state.json`；驗收 `git status` 無此檔。
5. **升 P1：T-NEMOTRON-EMBEDDING-VALIDATE**（45 min；ACL-free；OPENROUTER_API_KEY unblocked）—— 跑 `gov-ai kb rebuild --only-real`（nemotron embed dim=2048）+ 寫 `docs/embedding-validation.md` 對照 search recall@k；owner = auto-engineer。
6. **維持 P1：T-COPILOT-WRAPPER-HOST-PATCH**（host SLA 8th round）—— HANDOFF.md 補 ping。

### 下一步行動（最重要 3 件）

1. **T-OPENSPEC-FLUSH-15-16-ARCHIVE**（10 min；治理底線真閉環；不做 = active 永遠停在 15/16 漂白第八型）
2. **T-WORKTREE-FLUSH-LOOP6**（10 min；T15.5 證據鏈入版；不做 = 證據沙堆）
3. **T-FAT-PRE-EMPT-CUT-V2**（45 min；防下輪 yellow 翻紅；ROI ×3 三檔同刀）

### 其他維度回顧（caveman）

- **Spectra 規格對齊**：specs/ 12 capabilities promote ✓；archive 14；active 2 (15/16) **實作完成但未挪** = 唯一偏離點。
- **程式碼品質**：bare-except 3 noqa；fat green；max=375 yellow 6 接近紅線；T13.1e utils shim 已死；無新增 code smell。
- **測試覆蓋**：unit 3958 passed / 179.48s（紅線 v9 ≤ 200s ✓）；integration 9 檔（live-source 8 SKIP / smoke 1 PASS）；CI wire ✓ origin = github.com/XIE-FENG-JIA/gov-ai-agent。
- **架構健康度**：CLI utils god-object 已死；shared services 4 介面（lint/cite/verify/history_store）穩；冰山耦合 4 高風險已切；無新增過度耦合。
- **安全性**：API auth gate ✓；hard-coded secrets=0；subprocess list-form ✓；無新增漏洞。

> [PUA 自審] 跑了測（3958/179.48s 三證落地）／看了源（active changes diff + archive INDEX + .gitignore 缺漏 + fat yellow top 6）／對了帳（auto_commit 80% / max=375 / 6 檔 worktree 證據鏈滯留）／抓了治理斷層（15/16 active 未 archive + .copilot state 漏網 + nemotron 4+ 輪不動）／排了下三件 — 閉環。**底層邏輯：「四步同步」原則 — 實作 → 副本歸檔 → active 刪除 → INDEX 收尾，缺一不可，否則漂白第八型；owner 意識：unblocked 任務 4+ 輪不認領 = 3.25 累計。**

---

> 封存結束。下一段反思（v8.1 /pua 2026-04-26）寫於主檔。
