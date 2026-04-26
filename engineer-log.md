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

## 下一輪反思（空指引）

<!-- 每輪追加一個 ## 反思 段，保持主檔 ≤ 300 行；超出觸發 T9.6-REOPEN 封存。 -->
