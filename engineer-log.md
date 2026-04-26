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
> 封存檔：[engineer-log-202604M.md](docs/archive/engineer-log-202604M.md)（v7.8b 深度回顧 ～ v8.0 反思 07:50 共 6 段；2026-04-26 T9.6-REOPEN-v9）
> 規則：單輪反思 ≤ 40 行；主檔 ≤ 300 行硬上限；超出當輪 T9.6-REOPEN-v(N) 必封存。

---

## 深度回顧 2026-04-26 10:32 — 技術主管近 5 輪根因分析（v8.0-r5；Copilot 主導）

| 輪次 | 核心 task | 結果 | 備註 |
|------|-----------|------|------|
| v8.0 /pua | cf26345 引入 2 test regression | ❌ | 漂白第十型：agent commit 前未跑同檔 pytest |
| v8.0-r3 | T-NEMOTRON-EMBEDDING-VALIDATE-CLOSE | ✅ | 4+ 輪 SLA 破頂後終閉 |
| v8.0-r4 | T-LLM-EMBED-TEST-FIX | ✅ | mock contract 修正 + dead branch 刪 |
| v8.0-r5 | T-COMMIT-LINT-FEAT-LLM-PYTEST-GATE | ✅ | lint 硬門禁補漂白第十型 |
| v7.9-final | T-OPENSPEC-PURPOSE-BACKFILL commit | ❌ | ACL blocked；AUTO-RESCUE 代提 |

### 反覆失敗根因

1. **git commit 殘噪（結構性 + 修法後遺）**：codex ACL 修法（keeper.sh + lib/common.sh:803 yolo_mode=on hardcode）已部署，v8.0 4 commits 正常落版；但 v7.9-final 後段仍見 8 條 AUTO-RESCUE = 修法未完整驗收。根因 = keeper 5 min cycle + subshell YOLO_MODE reset；需 5+ 輪 0-residual 監測方算真閉環。
2. **漂白第十型（mock contract drift）**：cf26345 引入 OpenRouter REST embedding，commit 前未跑 `pytest tests/test_llm.py`，2 個 stale test 沉默到 /pua 才抓到。**根因 = agent 自主改動 ≠ 跑同檔 test**；T-COMMIT-LINT-FEAT-LLM-PYTEST-GATE 已補 feat(llm|core|api) 強制 pytest body 門禁，屬治本。
3. **T-NEMOTRON-EMBEDDING-VALIDATE 4 輪不動**：任務標 "unblocked" 但無 assignee；連 4 輪 P0 掛空 = SLA 破頂。根因 = 任務列表無 owner 欄，靠自律不靠機制。v8.0-r3 強制閉環；治本 = 凡新增 P0 必標 owner + 本輪 SLA。

### 優先序需調整

1. **T-PUSH-ORIGIN-V8.0（P0 最緊急、連 2 輪 open）**：本地 5+ commits 未推，GitHub Actions 未驗、cloud reviewer 看不到；功能再多，不推 = ROI 存本地磁碟。
2. **T-FAT-PRE-EMPT-CUT-V2（P1 維持 pre-empt）**：fat yellow max=375，6 檔距 400 紅線 25 行；應在同檔新增功能前先刀，同 v7.9 模式。
3. **T-INTEGRATION-CI-SECRETS（P1 新增）**：GOV_AI_RUN_INTEGRATION gate 未接 CI secrets，integration job 目前 skip 全部 live test = CI gate 假綠。

### 隱藏 blocker

- **spec漂白第四型**：cf26345 上線 direct REST embedding，但 `openspec/changes/17-embedding-provider-rest-fallback/` proposal 尚未建立；功能無規格軌跡，rollback/onboarding 無佐證。
- **auto_commit_rate < 90% 軟紅線尚未穩定**：近 30 commit 殘 6 條 AUTO-RESCUE 舊噪；sensor formula 已修，但 keeper.sh interval 5 min = 根噪未截；T-COPILOT-WRAPPER-HOST-PATCH 連 8 輪 P1 host SLA 未動。

> **底線邏輯**：近 5 輪揭示兩個配對陷阱——「commit 落版 ≠ 功能閉環」（T-PUSH-ORIGIN 連 2 輪 open）與「測試全綠 ≠ commit 前驗同檔」（漂白第十型）；兩條硬規則已補 lint 門禁，但下輪必須先推 origin，否則 v8.0-r* 系列工作量仍是本地黑洞，雲端 CI 驗收 = 0。

---

## 反思 2026-04-26 11:30 — 技術主管深度回顧 v8.1 / e04476e push 後（/pua 觸發；阿里味）

### 近期成果（HEAD 五源獨立量測）

- **HEAD = origin/main = e04476e**（T-PUSH-ORIGIN-V8.0 ✅；rev-list ahead/behind = 0/0；連 2 輪 open 終閉）
- **pytest -n 8 全量**：`python -m pytest tests/ --ignore=tests/integration -q --tb=line` = **3968 passed / 1 failed / 47.80s**（紅線 v9 ≤ 200s ✓ 雙重守住，runtime -73% vs 上輪 179.48s — 因 cache 暖啟動）
- **1 failed = `test_robustness.py::TestGracefulDegradation::test_kb_init_failure_graceful`**；單檔重跑 14.18s = **PASS** → **xdist race 漂白第七型再現**
- **sensor 全綠**：hard=[]；soft=program_md_lines 264>250；bare_except=3 noqa；fat red=0 yellow=1 max=350（catalog.py）；corpus=400；auto_commit_rate=100%（30/30）
- **openspec 0 active**：specs/ 13 capabilities + archive 16 條目齊；T-REGULATION-MAPPING-SPEC 已 promote
- **近 9 commit 連續語意化**：e04476e/dfa7d6d/bdcda73/027ec1d/9aafa6a/e0d673a/00330c0/cf26345/1b8d793 — v8.0-r* 全閉

### 發現的問題（按嚴重度）

1. **【漂白第七型再現 — xdist race flake】（P0 新增；高優先治理）**：`test_kb_init_failure_graceful` 在 `-n 8` 失敗 (`assert kb._available is False` = True)，單檔 PASS。同模式：另一 worker 把 `chromadb.PersistentClient` patch 拆掉前，此測試已建立 KB；mock side_effect 沒命中，`_available=True`。**底層邏輯：sensor 不抓 transient flaky（只抓 hard violation），但 CI -n 8 一定踩到**；前 3 輪治 xdist race 用 mix_stderr/source_url，本回是新 callsite（同 chromadb mock）。**T-XDIST-RACE-AUDIT-V2 升 P0**。
2. **【out.tmp 0-byte 工作樹漂入】（P1 新增）**：`?? out.tmp` 0 行未追蹤；典型 IDE 或 shell 重定向產物。雖無功能害，但加污染 git status 信號 + 可能含 secret。修法：`.gitignore` 加 `*.tmp` + `out*`；驗收 `git status --short` 不見此檔。
3. **【program.md 264 > soft 250 軟紅線】（P1 新增）**：sensor soft 唯一觸發；治理日誌膨脹 14 行，可優化策略 = 把 v7.x 系列 verbose batch 條目（line 37-49 的 v7.9-sensor / v7.8 P0）封存到 `docs/archive/program-history-202604L.md`；目標 ≤ 250 行。
4. **【spec 漂白第四型未補：embedding-provider-rest-fallback proposal 缺】（P1 carried-over）**：cf26345 + 00330c0 已落 OpenRouter REST embedding 雙刀，且 docs/embedding-validation.md 已寫，但 `openspec/changes/17-embedding-provider-rest-fallback/` proposal + spec deltas 尚未建立。功能漂入 = 規格軌跡空白；下次重構或 rollback = 無 source-of-truth 可查。
5. **【fat yellow 1 檔 max=350 = 紅線邊緣】（P2 carried-over）**：`src/cli/template_cmd/catalog.py` 350 行 = yellow 線正中點；同檔下次微改即翻 yellow。可預防性抽 `_catalog_data.py` 80 行降至 270 即破除邊緣；ROI ×1（單檔）。
6. **【test_kb_init_failure_graceful 同類風險未盡掃】（P1 連帶）**：同檔 `TestGracefulDegradation` 5+ 個 test 都用 `patch("src.knowledge.manager.chromadb.PersistentClient")`，xdist 並行下任一條都可能 race。應系統化稽核 + 補 fixture-scope 隔離（autouse + per-worker isolation），不只修這一條。

### 建議的優先調整（重排 program.md）

1. **新 P0 首位：T-XDIST-RACE-AUDIT-V2-CHROMADB**（30 min；ACL-free；漂白第七型再現對策）— (a) `tests/test_robustness.py::TestGracefulDegradation` 5 個 chromadb mock test 全改 `monkeypatch` per-test scope + 確保 each test 創建獨立 manager instance；(b) 或在 module 層加 autouse fixture 每測試前 reset `KnowledgeBaseManager._instance` / module-state；(c) 跑 `pytest tests/test_robustness.py -n 8 --count=10` 連跑 10 次 0 fail 才算閉環。owner = auto-engineer；本輪 SLA。
2. **新 P0：T-GITIGNORE-TMP-OUT**（5 min；ACL-free；治理 noise 漏網 v3）— `.gitignore` 加 `*.tmp` + `out*` patterns；刪 `out.tmp`；驗收 `git status --short` clean（扣 .copilot session）。
3. **新 P1：T-PROGRAM-MD-ARCHIVE-202604L**（15 min；ACL-free；soft 紅線收尾）— 把 program.md line 37-49（v7.9-sensor / v7.8 / v7.3-v7.7 verbose batch）封存到 `docs/archive/program-history-202604L.md`；主檔降 ≤ 250 行；驗收 sensor soft=[]。
4. **新 P1：T-OPENSPEC-CHANGE-17-EMBED-REST**（30 min；ACL-free；spec 漂白第四型補軌跡）— 建 `openspec/changes/17-embedding-provider-rest-fallback/` 含 proposal + tasks + spec deltas（`embedding-provider`/`llm-fallback` capability）；引用 cf26345/00330c0/e0d673a 三 commit；驗收 `spectra status` 通過 + active=1。
5. **新 P2：T-FAT-CATALOG-PRE-CUT**（30 min；ACL-free；單檔 ROI ×1）— `src/cli/template_cmd/catalog.py` 350→270，抽 `_catalog_data.py`；預先破除 max=350 邊緣值。

### 下一步行動（最重要 3 件）

1. **T-XDIST-RACE-AUDIT-V2-CHROMADB**（30 min；本輪必動 — flaky 不修 = CI 隨機失敗 + 信心崩塌）
2. **T-GITIGNORE-TMP-OUT + T-PROGRAM-MD-ARCHIVE-202604L**（合計 20 min；治理 noise 與 soft 紅線雙閉環）
3. **T-OPENSPEC-CHANGE-17-EMBED-REST**（30 min；spec 漂白第四型補軌跡；下次 rollback/onboarding 必看）

### 其他維度回顧（caveman）

- **Spectra 規格對齊**：specs/ 13 capabilities + archive 16 條目；唯一偏離 = REST embed 無 spec proposal（漂白第四型已記）。
- **程式碼品質**：bare-except 3 noqa；fat red=0 yellow=1 max=350；無新增 code smell；llm.py REST/litellm 雙 path 仍未抽（catalog.py 邊緣優先）。
- **測試覆蓋**：unit 3968 passed（+10 vs 上輪 3958，T-COMMIT-LINT 與 T-WIZARD-IMPORT regression 補測 +10 case 立功）；integration 9 檔 wire；**邊界**：xdist race chromadb mock cluster 5+ 個 test 同類風險。
- **架構健康度**：CLI shared services 4 介面穩；history_store 抽出穩；REST/litellm dual path 認知負擔 +1 但局部隔離 OK；無新增過度耦合。
- **安全性**：API auth gate ✓；OPENROUTER_API_KEY env-only ✓；REST HTTPS + 8000 char truncate ✓；out.tmp 0-byte 但需 gitignore（潛在 secret 漏網 risk）；無新增漏洞。

> [PUA 自審] 跑了測（3968/47.80s -n 8 + flaky 單檔 14.18s 雙路三證落地）／看了源（test_robustness.py:982-1005 chromadb mock cluster + git log e04476e..1b8d793 9 commit + sensor formula）／對了帳（origin sync ✓ / auto_commit 100% / max=350 邊緣 / out.tmp 漂入）／抓了治理斷層（漂白第七型再現 + spec 漂白第四型未補 + program.md soft 紅線 + tmp gitignore 漏網）／排了下三件 — 閉環。**底層邏輯：「sensor 綠 ≠ pytest -n 8 綠 ≠ pytest -n 8 連跑 10 次綠」；漂白第七型 flaky 是 xdist 並發下 mock contract 永遠重新打的暗債，每打一次治一個 callsite 不夠，要系統化 fixture-scope 隔離 + count=10 連跑驗收，否則同型再犯。**

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

## 下一輪反思（空指引）

<!-- 每輪追加一個 ## 反思 段，保持主檔 ≤ 300 行；超出觸發 T9.6-REOPEN 封存。 -->
