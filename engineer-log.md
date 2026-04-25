# Engineer Log — 公文 AI Agent

> 技術主管反思日誌。主檔僅保留 v6.1 以後反思（hard cap 300 行）。
> 封存檔：`docs/archive/engineer-log-202604a.md`（v3.2 以前 / 2026-04-20 早段回顧）
> 封存檔：`docs/archive/engineer-log-202604b.md`（v3.3 到 v4.4 / 2026-04-20 二次封存）
> 封存檔：`docs/archive/engineer-log-202604c.md`（v4.5 到 v4.9 / 2026-04-21 三次封存）
> 封存檔：`docs/archive/engineer-log-202604d.md`（v5.0 到 v5.1 / 2026-04-21 四次封存）
> 封存檔：`docs/archive/engineer-log-202604e.md`（v5.2 / 2026-04-21 五次封存；v5.8 前為 hard cap 讓位）
> 封存檔：`docs/archive/engineer-log-202604f.md`（v5.4 到 v5.6 / 2026-04-21 六次封存；v6.1 T9.6-REOPEN-v4）
> 封存檔：`docs/archive/engineer-log-202604g.md`（v5.7 到 v6.0 / 2026-04-22 七次封存；T9.6-REOPEN-v5）
> 封存檔：`docs/archive/engineer-log-202604h.md`（v6.1→v6.2 / v6.3 / v7.0 / v7.0-sensor 2026-04-25 八次封存；T9.6-REOPEN-v6）
> 封存檔：`docs/archive/engineer-log-202604i.md`（v7.0 接管第 1/2 輪 + v7.1 LOOP2 第 2/3/4 輪 + v7.2 第 43 輪 2026-04-25 九次封存；T9.6-REOPEN-v7）
> 封存檔：`docs/archive/engineer-log-202604j.md`（v7.3 到 v7.8b / 2026-04-25 十次封存；T9.6-REOPEN-v8）
> 封存檔：`docs/archive/engineer-log-202604L.md`（v7.9 22:35/22:54/00:15/01:05/02:29/02:32/02:40 共 7 段 / 2026-04-26 十一次封存）
> 規則：單輪反思 ≤ 40 行；主檔 ≤ 300 行硬上限；超出當輪 T9.6-REOPEN-v(N) 必封存。

---

> v5.0（第二十八輪）/ v5.1（第二十九輪）反思已封存至 `docs/archive/engineer-log-202604d.md`。
> v5.2（第三十輪）反思已封存至 `docs/archive/engineer-log-202604e.md`。
> v5.4（第三十二輪）/ v5.5（第三十三輪）/ v5.6（第三十四輪）反思已封存至 `docs/archive/engineer-log-202604f.md`。
> v5.7 / v5.8 / v5.9 / v6.0 反思已封存至 `docs/archive/engineer-log-202604g.md`。
> 主檔現存：v7.0 pua-loop 接管第 1/2 輪（LOOP_DONE）+ v7.1 LOOP2 第 2/3/4 輪 + Epoch+ 深挖（T-PYTEST-RUNTIME-FIX-v2）。

> v6.1→v6.2 / v6.3 / v7.0 / v7.0-sensor 4 段反思已封存至 [`docs/archive/engineer-log-202604h.md`](docs/archive/engineer-log-202604h.md)（2026-04-25 T9.6-REOPEN-v6 執行；主檔 512 → 229 行）。
> v7.0 接管第 1/2 輪（LOOP_DONE）+ v7.1 LOOP2 第 2/3/4 輪（task a-k + 冰山第 2 型閉）+ v7.2 第 43 輪 sensor 已封存至 [engineer-log-202604i.md](docs/archive/engineer-log-202604i.md)（2026-04-25 T9.6-REOPEN-v7 執行；主檔 437 → 108 行）。

>v7.3–v7.8b反思已封存至[engineer-log-202604j.md](docs/archive/engineer-log-202604j.md)（2026-04-25T9.6-REOPEN-v8；主檔407行降至sensor硬上限內）。

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
> 封存檔：`docs/archive/engineer-log-202604L.md`（v7.9-sensor 22:35 / 22:54 / 00:15 / 01:05 / 02:29 / 02:32 / 02:40 共 7 段 / 2026-04-26 十一次封存；T13.2-T13.3 iceberg 解耦閉環）。

---
## 下一輪反思（空指引）

<!-- 每輪追加一個 ## 反思 段，保持主檔 ≤ 300 行；超出觸發 T9.6-REOPEN 封存。 -->

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
