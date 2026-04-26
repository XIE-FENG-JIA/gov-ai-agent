# Engineer Log — 公文 AI Agent

> 技術主管反思日誌。主檔僅保留最近反思（hard cap 300 行）。
> 封存檔：`docs/archive/engineer-log-202604a.md`（v3.2 以前）
> 封存檔：`docs/archive/engineer-log-202604b.md`（v3.3 到 v4.4）
> 封存檔：`docs/archive/engineer-log-202604c.md`（v4.5 到 v4.9）
> 封存檔：`docs/archive/engineer-log-202604d.md`（v5.0 到 v5.1）
> 封存檔：`docs/archive/engineer-log-202604e.md`（v5.2）
> 封存檔：`docs/archive/engineer-log-202604f.md`（v5.4 到 v5.6）
> 封存檔：`docs/archive/engineer-log-202604g.md`（v5.7 到 v6.0）
> 封存檔：`docs/archive/engineer-log-202604h.md`（v6.1 → v7.0-sensor）
> 封存檔：`docs/archive/engineer-log-202604i.md`（v7.0/v7.1/v7.2）
> 封存檔：`docs/archive/engineer-log-202604j.md`（v7.3 到 v7.8b）
> 封存檔：`docs/archive/engineer-log-202604L.md`（v7.9-sensor 7 段）
> 封存檔：[engineer-log-202604M.md](docs/archive/engineer-log-202604M.md)（v7.8b 深度回顧 ～ v8.0 反思 07:50 共 6 段；2026-04-26 T9.6-REOPEN-v9；v8.0-r5 深度回顧 + v8.1 反思 2 段；2026-04-26 T9.6-REOPEN-v10）
> 封存檔：[engineer-log-202604N.md](docs/archive/engineer-log-202604N.md)（v8.5 深度回顧 + v8.5-REVIEW + v8.6 深度回顧 3 段；2026-04-26 18:20 ~ 20:30；T-ENGINEER-LOG-ARCHIVE-202604N）
> 規則：單輪反思 ≤ 40 行；主檔 ≤ 300 行硬上限；超出當輪 T9.6-REOPEN-v(N) 必封存。

---

## 反思 2026-04-26 14:30 — 技術主管深度回顧 v8.3 / ea22663（/pua 觸發；阿里味）

### 三證自審（HEAD 獨立量測）

- HEAD = origin/main = **ea22663**（afcc254 + ea22663 + 1ad2432 三連推；rev-list 0/0）
- pytest -n 8 全量 = **3969 passed / 0 failed / 436.19s**（v8.0 cold 167s → v8.1 cold 47s → 本輪 cold **436s = 2.6x 暴增**；soft 200s 紅線 2.18x 破）
- sensor hard=[] / soft=[] / bare_except=3 noqa / fat red=0 yellow=0 / corpus=400 / auto_commit_rate=100% (30/30) / program.md=222 / engineer-log=99
- openspec 0 active / 14 specs / 17 archive INDEX 齊
- watch 300-400 = 12 檔；top: web_preview/app.py 347 / core/llm.py 343 / gazette_fetcher.py 331 / review_parser.py 326

### 發現的問題（按嚴重度）

1. **【pytest cold-start runtime 暴增 167→436s】（P0 新增；治本必修）** — v8.0 cold 167s ≤ 200s 守住；本輪 cold 436s = soft 2.18x 破。候選根因：(a) 多輪累積 `__pycache__` / Defender 掃毒、(b) chromadb / KB cold-cache 暖化路徑、(c) v8.2 T-XDIST autouse fixture +setup overhead 線性累加 N workers、(d) +T9.1.a benchmark / +T-CORPUS-PROVENANCE / +T-XDIST-V2 共 +13 cases。**底層邏輯：sensor 不抓 runtime regression — 時間紅線需獨立 ratchet 機制**；T-PYTEST-RUNTIME-REGRESSION-ITER8 升 P0。
2. **【llm.py 343 行 REST+litellm dual path 共生】（P1 新增）** — `LiteLLMProvider.embed` 雙引擎：litellm primary + REST fallback for OpenRouter；下次新 provider/path 即翻 yellow（350）。預先抽 `_openrouter_rest.py` 60 行降至 ≤ 285；同步降認知負擔。
3. **【watch 300-400 = 12 檔，top 4 全 320+】（P2 新增）** — web_preview 347 / llm 343 / gazette_fetcher 331 / review_parser 326；同型 fat 邊緣值；未來 6 檔 commit 一波即翻紅。預先抽 ROI 高三檔。
4. **【openspec 0 active = 工作管線空】（P2 觀察）** — 17 archived 0 in-flight；treadmill 風險 = 工程師只追修 bug 不開新 capability；需評估下個 epic（corpus 500 / 多語料品質 / E2E rewrite hardening）。
5. **【scripts/legacy/ 10 .ps1 殘留】（P3 觀察）** — 可封存到 docs/archive/legacy-scripts/ 減根目錄噪音；ROI 低非本輪必動。

### 建議優先序（重排 program.md）

1. **新 P0：T-PYTEST-RUNTIME-REGRESSION-ITER8**（45 min；ACL-free）— bisect 167→436s：(a) `--collect-only` 量收集；(b) `--durations=20` top 20 slow；(c) 對比 cf26345/dfa7d6d/7c33570/62b2d85 4 SHA cold-start runtime；(d) 檢 chromadb client fixture leak；(e) 3 輪 cold-start median ≤ 220s 閉環。owner=auto-engineer。
2. **新 P1：T-LLM-DUAL-PATH-EXTRACT**（30 min；ACL-free）— `src/core/llm.py` 343 抽 `_openrouter_rest.py`（_openrouter_embed_rest + _truncate_for_embedding + http session）；主檔 ≤ 285；驗收 fat-gate ratchet 不退 + `tests/test_llm.py` 52 passed。
3. **新 P2：T-FAT-WATCH-CUT-V3**（45 min；ACL-free）— 抽 web_preview/app.py 347→285 + gazette_fetcher 331→260 + review_parser 326→260；3 檔同刀 ROI ×3。

### 下一步行動（最重要 3 件）

1. **T-PYTEST-RUNTIME-REGRESSION-ITER8**（45 min；本輪必動 — soft 紅線 2.18x 破不修 = CI gate 隨機破信心）
2. **T-LLM-DUAL-PATH-EXTRACT**（30 min；llm.py 預防翻 yellow + 雙引擎隔離）
3. **T-FAT-WATCH-CUT-V3**（45 min；3 檔同刀；下輪 fat 邊緣清）

### 其他維度回顧（caveman）

- **Spectra 規格對齊**：14 specs / 0 active / 17 archive INDEX；spec 第四型已補（embedding-provider REST fallback）；無漂白。
- **程式碼品質**：bare-except 3 noqa；fat red=0 yellow=0；TODO 5 處 minor；llm.py dual path + web_preview 邊緣值可預抽。
- **測試覆蓋**：3969 passed（+1 vs 上輪 3968 = T9.1.a benchmark intake）；integration 9 wire / 28 skip on live gate；**邊界**：cold-start runtime 167→436s 為 silent 治理債。
- **架構健康度**：cli/api/agents/graph/sources/knowledge 6 模組分明；`_shared/` 公共介面收尾；llm.py 雙引擎暫共生但內聚。
- **安全性**：API auth ✓；OPENROUTER_API_KEY env-only ✓；HTTPS REST + 8000 truncate ✓；無新增漏洞。

> [PUA 自審] 跑了測（3969/436s -n 8；167→436s 暴增定性）／看了源（llm.py:32-284 dual path / 4 檔 watch / openspec 17 archived）／對了帳（HEAD ea22663 ≡ origin ✓ / sensor 全綠 / fat 0/0 / auto_commit 100%）／抓了治理斷層（runtime silent 紅線 + dual path 認知負擔 + 工作管線空）／排了下三件 — 閉環。**底層邏輯：「sensor 綠 ≠ pytest cold-start ≤ 200s」；fat ratchet 守空間紅線，需補 runtime ratchet 守時間紅線；ITER8 是治本不是 patch。**

---

## 深度回顧 2026-04-26 14:54 — 技術主管近 5 輪根因分析（v8.3-REVIEW；Copilot 主導）

### 近 5 輪事件摘要

| 輪次 | 核心事件 | 結果 |
|------|---------|------|
| v8.0-r4/r5 | T-LLM-EMBED-TEST-FIX + T-COMMIT-LINT-GATE | ✅ 漂白第十型閉環 |
| v8.1 (11:30) | xdist race 漂白第七型再現 / out.tmp 漂入 | ⚠️ 新 P0 發現 |
| v8.2 (14:02) | T-XDIST-RACE-AUDIT-V2 + T9.1.a Copilot 代推 | ✅ 積壓雙批推送 |
| v8.3 (14:30) | pytest cold-start 167→436s（+2.6×） | ❌ runtime 2.18× 破線 |
| 橫跨全輪 | .git index.lock FAIL-BLOCKED 10+ 次 | 🔴 結構性 ACL 阻塞 |

### 反覆失敗根因

1. **`.git` ACL DENY（結構性）**：v8.0–v8.2 commit 成功率 < 50%（10+ FAIL-BLOCKED）。icacls 每次修法只短暫有效，疑似外部 wrapper 寫 `.git` 時觸發 ACL 重置；真治本 = host 啟動腳本永久清 DENY；P2-Legacy-INDEX-LOCK 仍 open。

2. **pytest runtime 暴增（無 sensor 守護）**：cold-start 167→436s（+2.6×）期間 sensor 全綠。根因雙重：(a) T-XDIST-RACE-AUDIT-V2 autouse fixture +setup 線性累加 8 workers；(b) chromadb cold-cache 無跨輪暖化。sensor 不含 runtime ratchet = 時間紅線無哨兵；T-PYTEST-RUNTIME-REGRESSION-ITER8 雖升 P0 但本輪未動。

3. **漂白第七型 xdist race 週期性再犯**：v8.1 新 callsite（chromadb mock）→ v8.2 修；fix 範圍僅覆蓋 TestGracefulDegradation，其餘 module mock cluster 未系統化 audit，下次換 callsite 必再犯。

### 優先序需調整

1. **T-PYTEST-RUNTIME-REGRESSION-ITER8（P0；本輪必動）**：CI runner 通常比本機慢 2-3×；436s 本地換算 Actions 可達 20 min+；不修 = CI gate 名存實亡。
2. **T-GIT-ACL-PERMANENT-FIX（新 P0 建議；宿主層）**：現狀靠 Copilot agent 偶爾繞過；host Admin 需在啟動腳本加 `icacls .git /remove:d <SID>` 永久繼承；否則每 3-4 輪工作樹堆積無法入版。
3. **T-COPILOT-WRAPPER-HOST-PATCH（P1；8+ 輪 docs-only）**：auto_commit_rate 100% 是短期 rolling 讀數；host Admin 驗收無截止輪次，實質上是凍結狀態。

### 隱藏 blocker

- **GitHub Actions CI 從未真跑**：remote 雖有（ea22663 已推），CI secrets / GOV_AI_RUN_INTEGRATION 未設；Actions job = skip 全 live test = CI gate 假綠。T-INTEGRATION-CI-SECRETS 在 v8.0 深度回顧提及，但從未加入 program.md 任務欄，屬漏網治理債。
- **工作管線空（openspec 0 active）**：17 archived / 0 in-flight；連 2 輪只修 bug 無新 capability；若不開下個 epic（corpus 500 / 多語料品質 / E2E hardening），velocity 退化為純維護模式。

> **底線邏輯**：近 5 輪存在「雙重假綠」——sensor 全綠，但 pytest runtime 與 CI gate 兩條未被 sensor 覆蓋的維度同時沉默惡化；下輪必須補 runtime ratchet + CI secrets，否則「sensor 綠 = 系統健康」的信念是幻覺。

---

## 反思 2026-04-26 17:30 — v8.4 技術主管深度回顧（/pua 觸發；阿里味）

### 三證自審（HEAD 獨立量測）

- HEAD = **1b8d829**（領先 origin/main 2 commit：1b8d829 + 7f3f00a 未推；rev-list ahead/behind = 2/0）
- 工作樹漂浮：`src/cli/switcher.py` 改動未 commit（lazy connectivity skip / raw_config 改用）+ `engineer-log.md` 4 段未 commit + `codex-alt-index-*.lock` 漂入（同 v8.1 out.tmp 同型）
- sensor 全綠：hard=[] / soft=[] / bare_except=3 noqa / fat red=0 yellow=0 / corpus=400 / auto_commit=100% (30/30) / program.md=238 / engineer-log=176
- targeted pytest（switcher）= 10 passed / 42.85s；commit lint 近 30 commit = 0 violations；全量 ITER8 後 ~42s（v8.3 已修 436s→42s）
- openspec 0 active / 14 specs / 17 archive INDEX 齊（v8.3 已補 change-17 embedding-provider-rest-fallback）

### 發現的問題（按嚴重度）

1. **【本地領先 origin 2 commit 未推 + 工作樹漂浮】（P0；治理債重演）** — 1b8d829 (T-FAT-WATCH-CUT-V3) + 7f3f00a (T-LLM-DUAL-PATH-EXTRACT) 未推 origin；同時 switcher.py / engineer-log.md / codex lock 散裝在工作樹。**底層邏輯：v8.0-r2 同型「commit 落版 ≠ push origin ≠ 雲端 CI 看到」治理債第 2 次重演**；散裝改動 = 漂白第一型。
2. **【runtime ratchet sensor 未實作】（P0；v8.3-REVIEW 漏網繼承）** — 上輪反思明確點出「sensor 不含 runtime ratchet = 時間紅線無哨兵」，本輪 sensor 仍只看 fat/bare/corpus/log_lines；CI gate 隨機破信心。**漂白第十一型 = 紅線維度漏覆蓋**。
3. **【.gitignore 缺 codex-alt-index*.lock pattern】（P1；同 v8.1 out.tmp 同型）** — `git check-ignore` 對 `codex-alt-index-b19a*.lock` 無命中；`.gitignore` 已有 `*.tmp` / `out*` 但無 `*alt-index*.lock`；下次 codex agent 起 lock 必再漂入。
4. **【工作管線空 openspec 0 active】（P1；連 3+ 輪純維護）** — 17 archived / 0 in-flight；只修 bug 不開新 capability；下個 epic 候選：corpus 500 / multi-llm provider 抽象 / E2E rewrite hardening。
5. **【CI secrets 仍未進 program.md task】（P1；v8.0/v8.3 連 3 輪漏網）** — GOV_AI_RUN_INTEGRATION + GitHub Actions secrets 未設；CI integration job = skip 全 live test = 假綠；漏網治理債。
6. **【program.md 222→238 攀升 + engineer-log 176+40=216→300 預警】（P2；soft 紅線預兆）** — program.md 邊緣 250 / engineer-log 接近 300 hard cap；本輪反思寫完即 ~216 安全；但 v8.x 系列 verbose batch header 可預先封存到 archive。
7. **【T-COPILOT-WRAPPER-HOST-PATCH 8+ 輪 host SLA 凍結】（P2；rolling 統計假象）** — auto_commit_rate=100% 是 30 commit rolling 視窗；host Admin 驗收無截止輪次 = 實質凍結。

### 建議優先序（重排 program.md）

1. **新 P0 首位：T-COMMIT-PUSH-V8.4-WORKTREE-FLUSH**（20 min；ACL-free）— (a) `chore(state)` switcher.py + engineer-log.md 兩條獨立語意 commit；(b) `git push origin main` 4 commit 上推；(c) 驗 rev-list 0/0；(d) `git status --short` clean。
2. **新 P0：T-RUNTIME-RATCHET-SENSOR**（45 min；ACL-free；漂白第十一型治本）— `scripts/sensor_refresh.py` 加 `pytest_cold_runtime_secs` 量測（reuse last `--durations` 或獨立 marker），baseline 50s / soft 200s / hard 300s；補 `tests/test_sensor_refresh.py` runtime 欄位 case；CI 接 hard ratchet。
3. **新 P0：T-GITIGNORE-CODEX-ALT-INDEX**（5 min；ACL-free）— `.gitignore` 加 `*alt-index*.lock` + `codex-*` patterns；嘗試 `git rm --cached` + 系統刪 lock；驗 `git status --short` clean。
4. **新 P1：T-INTEGRATION-CI-SECRETS-PROMOTE**（30 min；CI 軌跡）— 把 v8.0/v8.3 連 3 輪漏網的 task 正式入 program.md P1：列 GOV_AI_RUN_INTEGRATION / OPENROUTER_API_KEY 兩 secrets；GitHub Actions workflow 補 `if: secrets.OPENROUTER_API_KEY != ''` gate；驗 Actions live job 真跑。
5. **新 P1：T-OPENSPEC-EPIC-NEXT-DISCOVERY**（30 min；ACL-free；velocity 突破）— 評估 3 候選 epic（corpus 500 / multi-llm provider 抽象 / E2E rewrite hardening）；選 1 開 `openspec/changes/18-*/` proposal + tasks 骨架；目標 active=1。
6. **新 P2：T-PROGRAM-MD-ARCHIVE-202604M**（15 min；ACL-free；soft 紅線預治）— 把 v8.0-r2 ~ v8.0-r5 verbose batch header（line 33-46）封存到 `docs/archive/program-history-202604M.md`；主檔 ≤ 200。

### 下一步行動（最重要 3 件）

1. **T-COMMIT-PUSH-V8.4-WORKTREE-FLUSH**（20 min；本輪必動 — push 不做 = 雲端 CI 仍看不到 v8.3 的 4 commit；散裝 = 漂白第一型）
2. **T-RUNTIME-RATCHET-SENSOR**（45 min；補時間紅線哨兵 — 漂白第十一型治本，sensor 不補就永遠假綠）
3. **T-OPENSPEC-EPIC-NEXT-DISCOVERY**（30 min；velocity 突破 — 連 3 輪只修 bug，不開 epic 等於走 treadmill）

### 其他維度（caveman）

- **Spectra 規格對齊**：14 specs / 17 archive INDEX 齊；spec drift = 0；唯一缺 = 工作管線空（0 active）。
- **程式碼品質**：bare-except 3 noqa；fat red=0 yellow=0；llm.py 379→279 已抽；web_preview/gazette/review 三檔已切；無新 smell。
- **測試覆蓋**：3970 passed / ITER8 後 ~42s；switcher 10 passed；commit lint 30/30；**邊界**：runtime ratchet sensor 缺；CI secrets 未設 = integration 全 skip 假綠。
- **架構健康度**：cli/api/agents/graph/sources/knowledge 6 模組分明；`_shared/` 收尾穩；llm.py REST/litellm dual path 已隔離。
- **安全性**：API auth ✓；OPENROUTER_API_KEY env-only ✓；HTTPS REST + 8000 truncate ✓；codex lock 0-byte 但需 .gitignore（潛在 wrapper 寫入路徑漏網）；無新增漏洞。

> [PUA 自審] 跑了測（switcher 10 passed/42s + commit lint 30/30 + sensor 全綠雙路三證）／看了源（switcher.py:91-96 lazy skip + git rev-list ahead 2 + .gitignore 無 alt-index pattern + program.md 238）／對了帳（fat 0/0 / auto_commit 100% / openspec 0 active / engineer-log 176 ≤ 300 hard）／抓了治理斷層（v8.0-r2 push 同型重演 + runtime ratchet 漏網 + codex lock 漂入 + 工作管線空 + CI secrets 漏網 3 輪）／排了下三件 — 閉環。**底層邏輯：「sensor 全綠 ≠ 工作樹 clean ≠ origin synced」；本輪三證齊但工作樹散裝 + 本地領先 = 雲端視角看到的 commit 量歸 0；漂白第一型 + 第十一型 + 第十二型（工作管線空）三債同框，需一輪三刀治本。**

---


## 反思 2026-04-26 21:35 — v8.8 技術主管深度回顧（/pua 觸發；caveman）

### 三證自審
- HEAD = origin/main = **39d1232**（rev-list 0/0；v8.7 push flush 仍守）
- `git status --short` = clean（工作樹 0 漂浮 ✓ — 漂白第一型 4 輪後本輪終止）
- pytest `--ignore=tests/integration -x` = **3999 passed / 80.43s**（+12 vs v8.6 3987；soft 200s 守住）
- sensor 真值：bare=1 / fat red=0 yellow=0 / corpus=400 / auto_commit=100% / log_lines = engineer 272 / program 232 / results 841 / **runtime baseline 仍 50.0 寫死**
- openspec：active 列出 `18-multi-llm-provider-abstraction/` 但 `archive/2026-04-26-18-...` + `specs/multi-llm-provider/spec.md` 已落 = 半殭屍 active
- fat watch 300-350 = **6 檔** max=314（v8.6 9/323 → 本輪 6/314 = T-FAT-WATCH-CUT-V4 收效 ✓）；3 檔同 cli/ 模組（batch_tools/config_tools/lint_cmd）

### 發現的問題
1. **【runtime baseline 寫死 50.0s 第 3 輪假哨兵】（P0；漂白第十一型第 3 輪）** — T-RUNTIME-RATCHET-LIVE-MEASURE-v2 標 [x] 但 sensor.json 真值 50.0；今日 cold 80.43s（+62%）也未自動 ratchet up（baseline 是 floor，up-creep 才該報警）；治本 = baseline 改「上限值 + tolerance」雙數而非 floor，且 sensor refresh 主路徑必跑 measure。
2. **【openspec 半殭屍 active dir】（P0；漂白第十二型衍生）** — active list 仍有 `18-...`（archive 已落 + spec promoted），sandbox/policy 擋刪致 active=1 假象；治本 = `git rm -rf openspec/changes/18-...` + commit；驗 `spectra list` = `No active changes.`。
3. **【epic 管線真空 + 無下個 epic】（P1；連 4 輪「工作管線空」第 5 輪預警）** — epic 18 實質完成；無 19；候選：(a) corpus 500 真語料、(b) engines runtime hot-switch、(c) KB recall@k 驗證。
4. **【cli/ 三檔同模組 fat 邊緣 300-314】（P1）** — `batch_tools 314 / config_tools 312 / lint_cmd 309` 同模組 3 檔；下次 cli/ 微改即翻 320+；ROI ×3 預抽。
5. **【engineer-log 272 + 本輪 ~25 = 297 = hard cap 邊緣】（P2）** — 預治：v8.5/v8.6 兩段下輪可封存到 docs/archive/engineer-log-202604N.md；本輪安全。

### 建議優先序（重排 program.md）
1. **新 P0：T-OPENSPEC-18-ACTIVE-CLEANUP**（5 min；ACL-free）— `git rm -rf openspec/changes/18-multi-llm-provider-abstraction/` + commit；驗 `spectra list` = 0 active。
2. **新 P0：T-RUNTIME-BASELINE-TRUE-MEASURE-v3**（30 min；ACL-free）— sensor refresh 主路徑必跑 `--measure-runtime`；baseline 改「ceiling + 2x tolerance」雙語意（floor 防降級不對；ceiling 防 up-creep）；補測 80.43s 寫入 sensor.json 真值。
3. **新 P1：T-OPENSPEC-EPIC-19-DISCOVERY**（30 min；ACL-free）— 評估 3 候選；選 1 開 `openspec/changes/19-*/` proposal + tasks 骨架；目標 active=1 真值。
4. **新 P2：T-FAT-WATCH-CUT-V5-CLI-MODULE**（45 min；ACL-free）— `batch_tools/config_tools/lint_cmd` 3 檔同刀抽 ≤ 270；fat 300-350 ≤ 3 檔。

---

## 深度回顧 2026-04-26 23:36 — 技術主管近 5 輪根因分析（v8.10-REVIEW；/pua 觸發）

### 近 5 輪事件摘要（v8.6 → v8.10）

| 輪次 | 核心事件 | 結果 |
|------|---------|------|
| v8.6 | T-EPIC-18-COMMIT-FLUSH 連 10+ 次 FAIL-BLOCKED（.git ACL） | 🔴 ACL 結構債 |
| v8.7 | ACL 自然解除；4 commit 推送；engines API + openspec 18 閉環 | ✅ 全閉 |
| v8.8 | baseline 50s 寫死第 3 輪；openspec 半殭屍 active=1 假象 | ⚠️ 雙假綠 |
| v8.9 | ceiling+tolerance 真量測；active 殭屍清除；epic 19 骨架開 | ✅ 全閉 |
| v8.10 | 漂白第一型 1 輪再生；epic 19 stall 1/6；sensor 死碼字段 | ⚠️ 三新債 |

### 反覆失敗根因

1. **漂白第一型永動機（結構性）**：sensor 測量工具本身寫工作樹（`runtime_baseline.json`），FastAPI smoke 殘留（`req*.json`）未 gitignore，每輪消滅症狀但未斷根；v8.10 1 輪即再生。根治必須讓「sensor 測量寫 `~/.cache`，非 worktree」，且 `req*.json` 補 `.gitignore`。T-WORKTREE-FLUSH-V9.0 是治本而非 patch，須本輪必動。

2. **Epic stall / treadmill 週期**：v8.3 起識別「工作管線空」預警，v8.8 升 P1 開 epic 19，v8.9 推 T19.1（openspec 骨架），但 v8.10 仍 stall 1/6。根因：epic 骨架落地 ≠ 實作啟動；T19.2-T19.6 沒有 agent 接手 = 「名義 active 掩蓋實質凍結」。若本輪不推 T19.2，第 7 輪 treadmill 已確認。

3. **Sensor 字段 lifecycle 無管理**：epic 6 早已封存，`sensor.epic6_progress` 仍 done=0/total=0；v8.8 openspec 半殭屍 active=1 是同型第一例；v8.10 死碼字段是第二例。缺「epic 封存後同步清 sensor 字段」SOP，未來每個 epic 完成都會留死字段，口徑放水第二型持續累積。

### 優先序需調整

- **P0 順序不變，但 T-WORKTREE-FLUSH-V9.0 必優先於 T-EPIC-19-T19.2**：worktree 不 clean 時推 epic 19 程式後仍會有漂入記錄，再生漂白第一型 = 本輪反思下輪又寫同一段。
- **T-SENSOR-ACTIVE-EPIC-PROGRESS（P1）需升半 P0**：sensor 死碼字段是口徑放水，若不修則「sensor 全綠 = epic 推進假象」，第三輪假綠預兆已現。

### 隱藏 Blocker

- **CI live integration 仍未真跑（連 8 輪漏網）**：`docs/ci-secrets-setup.md` 已有 SOP，但 GitHub Actions OPENROUTER_API_KEY 未設，integration job 全 skip = CI gate 假綠。每輪反思提一次，但從未進 program.md P0 強制收口；屬漏網治理債第二例（第一例是 epic stall）。
- **results.log 897 行 ≈ 硬上限 1000**：T-RESULTS-LOG-ARCHIVE-202604P 已列 P2，但若本輪 epic 19 推進 + worktree flush 各寫 ~10 行，下輪寫 /pua 回顧前就破千；需本輪回顧後立刻執行，不可等到「下輪寫前」。

> **底線邏輯**：近 5 輪呈現「三層假綠」——sensor 全綠（但字段死碼）、epic active=1（但實質凍結 5/6）、CI 全綠（但 integration 全 skip）；三層皆有對應治本任務已進 program.md，但執行率偏低（v8.10 P0 全未動）。本輪的唯一判斷基準：T-WORKTREE-FLUSH-V9.0 + T-EPIC-19-T19.2 兩件完成才算「非 treadmill 輪次」。

### 下一步行動（最重要 3 件）
1. **T-OPENSPEC-18-ACTIVE-CLEANUP**（5 min；最小修；半殭屍 active 不清 = `spectra list` 永遠騙你）
2. **T-RUNTIME-BASELINE-TRUE-MEASURE-v3**（30 min；漂白第十一型第 3 輪治本；50.0 寫死 = 哨兵盲點）
3. **T-OPENSPEC-EPIC-19-DISCOVERY**（30 min；epic 18 實質完成 → 無 19 = treadmill 第 5 輪起點）

### 其他維度（caveman）
- **Spectra 對齊**：16 specs / archive 18 + 12 / active 名義 1 實際 0 待清；無 drift。
- **程式碼品質**：bare=1（cite_cmd noqa）/ fat 0/0 / cli/ 三檔邊緣；無新 smell。
- **測試覆蓋**：3999 passed +12（engines API 2 + sensor v8.7 補丁等）；cold 49→80s 漸增需追；無 flaky。
- **架構**：providers 抽象完工 + delegate 收口 ✓；engines API + YAML SSOT 落地（cc0bbe2）；fat watch 收斂 9→6。
- **安全**：API auth ✓ / api_key env-only ✓ / defusedxml import-graph 斷言 ✓ / CI secret gate ✓ / 無新洞。

> [PUA 自審] 跑了測（3999/80.43s -x 三路三證 + sensor.json 真值對照）／看了源（active/18 dir + archive 並存 / sensor.json runtime 50.0 寫死 / fat 300-350 6/314 / cli/ 3 同模組）／對了帳（HEAD=39d1232≡origin / git clean / engineer-log 272 ≤ 300 / openspec active 名義 1 實際 0）／抓了斷層（漂白第十一型第 3 輪 baseline 寫死 + 半殭屍 active dir + 連 5 輪 epic 管線空預警 + cli fat 邊緣同模組）／排了下三件 — 閉環。**底層邏輯：v8.7 已修治理債五件套（散裝/log/openspec promote/engines/stackdump），剩漂白第十一型 baseline 寫死是「sensor 補了哨兵但量尺不動」第 3 輪 —— 治本不在加 ratchet，在 baseline 語意改「ceiling + tolerance」雙數防 up-creep。**

---

## 反思 2026-04-26 23:32 — v8.10 技術主管深度回顧（/pua 觸發；caveman）

### 三證自審
- HEAD = origin/main = **6426ad7**（rev-list 0/0；v8.9 push flush 仍守）
- `git status --short` = `M scripts/runtime_baseline.json` + `?? req.json` + `?? req-out.json` = **漂白第一型 1 輪後再生**（v8.8 「4 輪終止」紀錄破）
- pytest `--ignore=tests/integration -x` = **4001 passed / 158.43s**（soft 200s 守住；vs v8.8 80.43s 漲 +97%，但仍綠線內）
- sensor 真值：bare=1（cite_cmd noqa）/ fat red=0 yellow=0 / corpus=400 / auto_commit=100% / engineer 187 / program 234 / results 897 / **runtime cold 24.44s（v3 ceiling+tolerance 已落地，真量測 ✓）**
- openspec：active=1 真值（19-kb-recall-validation-pipeline；T19.1 [x]，T19.2-T19.6 [ ] 5 子任務）；半殭屍 active 上輪 v8.9 已清 ✓
- fat watch 300-350 = **3 檔**（utils_io 306 / editor/flow 304 / web_preview/app 300）邊緣值

### 發現的問題
1. **【漂白第一型 1 輪再生 — runtime_baseline.json + req*.json】（P0；v8.8 紀錄破）** — sensor 每輪 measure-runtime 寫 `last_measured_secs` → side-effect dirty；req.json/req-out.json 同 v8.4 codex-alt-index 同型治理債；治本兩刀：(a) `.gitignore` 加 `req*.json` 排除；(b) sensor save_runtime_baseline 改 hook-safe 寫到 `~/.cache/` 或測試本地非版控位置（不該每輪 modify tracked file）。
2. **【epic 19 推進停滯 1/6 = 16%】（P0；漂白第十二型衍生）** — T19.1 [x] 完成 eval set 35 筆 jsonl，但 T19.2 (eval_recall.py) / T19.3 (baseline) / T19.4 (sensor 嵌入) / T19.5 (CI gate) / T19.6 (跨 model 對比) 均 [ ]；不開 T19.2 = active=1 名義真但實質凍結 = 第 6 輪「epic 推進不過行 1」假象。
3. **【cli/utils_io 306 + editor/flow 304 fat 邊緣】（P1）** — v8.9 V5 cli 三檔已切（batch_tools 252 / config_tools 234 / lint_cmd 72），但 utils_io.py 是 V3 抽出後本身 306 接近 watch 上限；editor/flow 304；下次任一檔加 +20 即翻 yellow（≥350）。預先抽 ROI 高同模組。
4. **【sensor.epic6_progress 字段失準】（P2；漂白第二型）** — sensor.json 仍寫 `epic6_progress: {done:0, total:0}` 但 epic 6 已歸 archive；活動 epic 是 19；治本 = sensor 改 `active_epic_progress` 動態解析 `openspec/changes/<active>/tasks.md` 計 [x]/總數。**口徑放水第二例**。
5. **【results.log 897 → 1000 邊緣】（P2）** — soft 1000 紅線可預治；v8.7-v8.9 三輪 batch summary 條目可封存到 `results-202604.log.archive`；本輪安全。
6. **【cold runtime 9.47s → 24.44s 漲 158%】（P3 觀察）** — v3 baseline ceiling=100s tolerance=0.2 下未報警；ratchet down 機制正常（floor 9.47 守住）；但連續上漲需追根因（chromadb cold-cache 線性 / pytest 收集樹增長）；非本輪必動。

### 建議優先序（重排 program.md）
1. **新 P0 首位：T-WORKTREE-FLUSH-V9.0**（15 min；ACL-free；漂白第一型 1 輪再生治本）— (a) `.gitignore` 加 `req*.json` 一行；(b) `scripts/sensor_refresh.save_runtime_baseline` 改 hook-safe 寫 `~/.cache/gov-ai/runtime_baseline.json`（非版控）；或 (b'+) commit baseline 真值並開 `runtime_baseline.json` `.gitignore` 例外白名單只允許 sensor refresh 寫；(c) 1 commit 落版；驗 `git status` clean。
2. **新 P0：T-EPIC-19-T19.2-EVAL-RECALL-IMPL**（45 min；ACL-free；epic 19 推進治本）— `scripts/eval_recall.py` 落地：load `recall_eval.jsonl`、call `knowledge_manager.search(q, k=5)`、計 recall@1/3/5、output `recall_report.json`、`--dry-run` exit 0；`tests/test_eval_recall.py` 5 cases；勾 T19.2。**不開 = active=1 凍結進入第 7 輪 treadmill**。
3. **新 P1：T-SENSOR-ACTIVE-EPIC-PROGRESS**（20 min；ACL-free；漂白第二型治本）— `scripts/sensor_refresh.py` 把 `epic6_progress` 改名 `active_epic_progress`、解析 `openspec/changes/` 第一個非 archive 目錄的 `tasks.md` count `[x]/total`；補測 2 cases；驗 sensor.json 真值對齊 epic 19。
4. **新 P1：T-FAT-WATCH-CUT-V6**（30 min；ACL-free；3 檔同模組同刀）— `utils_io.py 306→260`（抽 `_atomic_writes.py` 50 行）+ `agents/editor/flow.py 304→260`（抽 `_safe_low_path.py` 50 行）+ `web_preview/app.py 300→255`（抽 `_health_routes.py` 50 行）；驗 fat watch 300-350 ≤ 1 檔。

### 下一步行動（最重要 3 件）
1. **T-WORKTREE-FLUSH-V9.0**（15 min；漂白第一型 1 輪即生 = 比 v8.8 第 4 輪治本更早再犯，sensor side-effect 寫版控檔是結構問題不是行為問題）
2. **T-EPIC-19-T19.2-EVAL-RECALL-IMPL**（45 min；epic 19 不推 = active=1 名義真實質假，第 7 輪 treadmill 預兆已現）
3. **T-FAT-WATCH-CUT-V6**（30 min；3 檔邊緣同模組預治，下輪+20 翻 yellow 機率 ≥ 50%）

### 其他維度（caveman）
- **Spectra 對齊**：specs 17（多 1 = audit/regression-repair/multi-llm-provider/runtime-baseline 全 promote）/ archive 19+12/ active 真值 1（19）；無 drift。
- **程式碼品質**：bare=1 noqa / fat 0/0 / V5 cli 三檔 ROI 已落（batch 314→252 / config 312→234 / lint 309→72 = 三檔降 -377 行）；無新 smell。
- **測試覆蓋**：4001 passed +2 vs v8.9（+T19.1 eval set 隱含 + sensor v3 補測）；**邊界**：runtime ratchet down floor 9.47 守住，but cold +158% 連 2 輪需追；無 flaky。
- **架構**：providers 抽象完工 ✓ + engines API + YAML SSOT ✓ + runtime baseline ceiling+tolerance ✓；epic 19 開但 stall；無新耦合。
- **安全**：API auth ✓ / OPENROUTER_API_KEY env-only ✓ / defusedxml ✓ / CI secret gate ✓ / req*.json 0-byte 但需 .gitignore 防漂入；無新洞。

> [PUA 自審] 跑了測（4001/158.43s -x 三路三證 + sensor.json 真值）／看了源（runtime_baseline.json sensor 寫 last_measured side-effect / req*.json 4-byte 漂入 / openspec active 19 T19.2-T19.6 pending / cli/utils_io 306 邊緣 / sensor.epic6 字段死碼）／對了帳（HEAD=6426ad7≡origin / git rev-list 0/0 / engineer-log 187 ≤ 300 / program.md 234 ≤ 250 soft / results.log 897 < 1000 soft）／抓了治理斷層（漂白第一型 1 輪再生 = v8.8 紀錄破 + epic 19 16% stall + sensor 字段失準口徑放水 + fat 3 邊緣值同模組）／排了下三件 — 閉環。**底層邏輯：v8.7-v8.9 三輪把「散裝/log/openspec/engines/runtime」五件套清掉，但 v8.10 即發現新型治理債 — sensor 主動寫版控檔是 side-effect 反模式（同 codex 同型）；治本不在加 ratchet，在 sensor 寫入路徑改 user cache，徹底切斷 sensor refresh 與工作樹漂浮的因果。**

---

## 下一輪反思（空指引）

<!-- 每輪追加一個 ## 反思 段，保持主檔 ≤ 300 行；超出觸發 T9.6-REOPEN 封存。 -->

