# 公文 AI Agent — Session Handoff

**日期**：2026-04-21  
**狀態**：🟢 E2E 已通過，進入 Phase A/B（擴大真實公文 + 向量化）  
**累計**：127 完成 / 36 待辦 / v5.6 USER OVERRIDE 鎖

---

## 🎯 產品核心（一句話）
從**真實公開政府公文**找相似範本 → **最小改動改寫** → 產 docx + **可追本溯源**。

---

## ✅ 關鍵里程碑

| 里程碑 | 狀態 | 位置 |
|---|---|---|
| **T5.4 E2E 5 需求測試** | ✅ PASS @ 2026-04-21 05:08 | `tests/integration/test_e2e_rewrite.py` + `scripts/run_e2e.py` |
| **Live Ingest 60 份真實資料** | ✅ baseline | `kb_data/corpus/{mojlaw,datagovtw,executiveyuanrss}/` |
| **Embedding 切 nemotron** | ✅ config | `config.yaml` → `nvidia/llama-nemotron-embed-vl-1b-v2:free`（dim 2048，免費）|
| **pytest 全綠** | ✅ 3686 passed | `pytest tests/ --ignore=tests/integration` |
| **Spectra openspec** | ✅ 初始化 | `openspec/changes/{01-real-sources,02-open-notebook-fork,03-citation-tw-format}/` |

---

## 🏃 運作中的系統（4 活躍 loop）

| Loop | PID file | 週期 | 職責 |
|---|---|---|---|
| `gov-ai-push-loop` | `~/.gov-ai-push-loop.pid` | 30 min | Discord LBbot channel 1494779722314285179 進度推送 |
| `rescue-daemon` | `~/.rescue-daemon.pid` | ACL 30s / commit 10 min | 救火 auto-engineer 的 ACL 阻塞 commit + reconcile |
| `auto-engineer-keeper` | `~/.auto-engineer-keeper.pid` | 5 min | auto-engineer 掛了自動 respawn（1hr 3 次 thrash 保護） |
| `auto-engineer` | `公文ai agent/.auto-engineer.pid` | 自己迴圈 | 主 agent 實際執行 program.md task |

**暫停的 loop**：
- `copilot-engineer-loop`（PID file 已清）— `scripts/copilot-engineer-loop.sh`，Startup `.vbs.disabled`。隨時可重啟。

---

## 📍 目前 USER OVERRIDE v5.6（program.md 頂部）

```
P0.1 修 live_ingest dispatcher bug（fda/mohw 不認）
P0.2 datagovtw 改抓真公文（非 metadata）
P0.3 擴大 live_ingest 到 ≥ 300 份
P1   新 PccAdapter（政府採購網）
P2   ChromaDB 向量化驗證（nemotron dim=2048 全量重建）
```
禁區：`gazette.nat.gov.tw`（robots `Disallow: /`）

Anti-bloat guard：待辦 > 20 禁新增，待辦 > 80 進化輪 skip（`auto-engineer.sh` hard-coded）

---

## 🔴 已知阻塞 / 風險

### 1. `.git` ACL DENY（rescue-daemon 緩解中）
- 2 組 foreign ORPHAN SID 的 explicit DENY
- Nuclear 清（takeown + icacls reset）ms 級重生 — 未找到 re-apply source
- Windows Defender CFA 已 disabled，排除
- **workaround**：rescue-daemon 每 10 min Admin session 代 commit
- 備援路徑：`docs/troubleshooting-acl.md` 含 8 步遷移 checklist（已試 C: 遷移失敗，rollback）

### 2. Copilot CLI 1.0.34 whitelist 限制
- API 有 `sonnet-4.5` / `gpt-5.4` / `opus-4.5`，**CLI `--model` 不認**
- 目前能用：`gpt-4.1` / `gpt-5-mini` / `gpt-5.2` / `gpt-5.2-codex` / `gpt-5.3-codex` / `gpt-5.4-mini` / `claude-haiku-4.5`
- 若需 sonnet-4.5：等 CLI 升級或走 `api.githubcopilot.com` curl 直呼

### 3. Codex service_tier 教訓
- **絕對不要設 `flex`**（24/7 workload 大量 429/503）
- 目前 `fast`（實測穩定）
- 省 quota 改 `model_reasoning_effort medium` / `cooldown 延長` 不動 tier

### 4. auto-engineer keeper 誤判 stale（已於 2026-04-22 熱修）
- 根因 1：`scripts/auto-engineer-keeper.sh` 原本只看「最後 log / state 更新」，base stale threshold 只有 600s；但 `codex` 一輪常跑 20-45 分，健康中的 round 會被誤判成 dead
- 根因 2：keeper 若被 `C:\Windows\System32\bash.exe`（WSL bash）拉起，讀不到 Windows 專案路徑，`state` 解析會失敗並 fallback 成 epoch 0，直接出現超大 age（例：`1776798967s`）
- 症狀：同一專案同時出現多條 `auto-engineer.sh "D:/.../公文ai agent"`；`program.md` 被多 worker 輪流重排，剩餘任務數會假性卡住或回彈
- 已套修補：
  - `D:/Users/Administrator/Desktop/公司/auto-dev/auto-engineer.sh` 新增輪內 heartbeat（`reflect/evolve/execute` 每 60s 刷新 `.auto-engineer.state.json`）
  - `D:/Users/Administrator/Desktop/公司/auto-dev/scripts/auto-engineer-keeper.sh` 改為優先讀 `state` heartbeat，並對 `codex` 套 `project cooldown + 1800s` grace
  - keeper log 會輸出 `source=state|log` 與 `threshold=`，方便直接看判活依據
- 修後觀察：round 106-110 正常推進，剩餘任務 `30 -> 27 -> 26 -> 24 -> 23`；keeper 已能寫出 `alive (age=359s, source=state, threshold=2700s)`
- 2026-04-22 03:48 驗證摘要：
  - 舊主 worker `PID 71760` 已在 round 111 實質收尾後受控停下，新主 worker `PID 54596` 已平滑接手
  - 新 worker 啟動時另踩到 `auto-engineer.sh` 的 `TASK_APPEND_THRESHOLD` 未預設 bug；已修成「prompt 展開前先給預設值」，否則 `set -u` 會讓新 worker 秒退
  - 新 heartbeat 已實測生效：`.auto-engineer.state.json` 在同一個 `phase=reflect` 內從 `2026-04-22T03:48:33+08:00` 刷到 `2026-04-22T03:49:35+08:00`
  - keeper 判活已回到正常：`alive (age=27s, source=state, threshold=2700s)`、`alive (age=59s, source=state, threshold=2700s)`
  - 新增 `D:/Users/Administrator/Desktop/公司/auto-dev/scripts/start-auto-engineer-keeper.ps1`；`-Restart` 已實測強制走 `C:\Program Files\Git\bin\bash.exe`，不再掉到 WSL `C:\Windows\System32\bash.exe`
  - 舊 round 111 內部實際工作已完成：`src/knowledge/manager.py` 例外降級修補 + `python -m pytest tests/ -q --ignore=tests/integration -x` = `3745 passed`；結果已寫回 `results.log`

---

## 🛠 關鍵檔案路徑

```
專案根：D:/Users/Administrator/Desktop/公文ai agent/
  program.md                       ← v5.6 USER OVERRIDE + Epic 1-5
  results.log                      ← auto-engineer 原始紀錄
  results-reconciled.log           ← reconcile 後真實狀態（BLOCKED-ACL→PASS 映射）
  engineer-log.md                  ← 反思輪深度回顧
  .auto-engineer.state.json        ← round / PASS / FAIL / IDLE 計數
  HANDOFF.md                       ← 本檔

  kb_data/corpus/                  ← 真實公文（60 份 baseline）
  kb_data/examples/                ← 合成公文 156 份（synthetic: true）
  vendor/open-notebook/            ← .git stub only（整合暫停）
  tests/integration/test_e2e_rewrite.py  ← E2E 核心測試
  scripts/run_e2e.py                ← E2E 入口
  scripts/live_ingest.py            ← 真實公文爬蟲主腳本

auto-dev 工具：D:/Users/Administrator/Desktop/公司/auto-dev/
  auto-engineer.sh                 ← 主 loop（IDLE/FAIL 分離 + anti-bloat guard）
                                    2026-04-22 hotfix：輪內 heartbeat（避免 keeper 誤判）
                                    2026-04-22 hotfix：TASK_APPEND_THRESHOLD 預設值前置（避免新 worker 秒退）
  scripts/rescue-daemon.sh         ← 通用 ACL 救火 + watcher
  scripts/gov-ai-auto-commit.sh    ← Admin 代 commit
  scripts/reconcile-results.sh     ← BLOCKED-ACL → PASS-RESCUED 對帳
  scripts/auto-engineer-keeper.sh  ← auto-engineer liveness 守護
                                    2026-04-22 hotfix：state heartbeat 優先 + codex 長輪 grace
  scripts/start-auto-engineer-keeper.ps1 ← Windows 啟動入口；強制 Git Bash，不碰 WSL bash.exe
  scripts/copilot-engineer-loop.sh ← Copilot 批次 agent（暫停）
  docs/troubleshooting-acl.md      ← ACL 手冊
  watchdog.conf                    ← 3 專案監控清單（gov-ai 在列）
  lib/cmd/core.sh                  ← ad start pre-flight ACL check
  lib/cmd/supervise.sh:679         ← audit-rotate repair fix

Copilot 配置：C:/Users/Administrator/.codex/config.toml
  model = "gpt-5.4"
  service_tier = "fast"  ← 絕對不要改 flex
  model_reasoning_effort = "xhigh"

Embedding：config.yaml
  embedding_provider: openrouter
  embedding_model: nvidia/llama-nemotron-embed-vl-1b-v2:free
  embedding_base_url: https://openrouter.ai/api/v1

Discord push：reuse LP bot
  token 從 C:/Users/Administrator/AppData/Roaming/lobsterpulse/config.json 的 appearance.discord.bot_token
  channel_id: 1494779722314285179
```

---

## 🚨 緊急操作 SOP

### Loop 全掛重啟
```bash
cd /d/Users/Administrator/Desktop/公司/auto-dev
nohup bash scripts/rescue-daemon.sh >/dev/null 2>&1 & disown
nohup bash scripts/auto-engineer-keeper.sh >/dev/null 2>&1 & disown
nohup bash scripts/gov-ai-status-loop.sh >/dev/null 2>&1 & disown
# auto-engineer 由 keeper 自動 respawn
```

### keeper / duplicate worker 受控清場
```powershell
$state = Get-Content 'D:\Users\Administrator\Desktop\公文ai agent\.auto-engineer.state.json' | ConvertFrom-Json
$keepPid = [int]$state.pid

# 清掉同專案的舊 auto-engineer，只保留 state 指向的主進程
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -like '*auto-engineer.sh*公文ai agent*' } |
  ForEach-Object {
    if ($_.ProcessId -ne $keepPid) { cmd /c "taskkill /PID $($_.ProcessId) /T /F" }
  }

# keeper 重啟入口（會強制 Git Bash，不碰 WSL bash.exe）
& 'D:\Users\Administrator\Desktop\公司\auto-dev\scripts\start-auto-engineer-keeper.ps1' -Restart
```

### ACL 一次清（Admin bash elevated 才能）
```bash
cd "/d/Users/Administrator/Desktop/公文ai agent"
MSYS2_ARG_CONV_EXCL='*' takeown /F .git /R /D Y
MSYS2_ARG_CONV_EXCL='*' icacls .git /reset /T /C
MSYS2_ARG_CONV_EXCL='*' icacls .git /reset   # 關鍵第 2 次（/T 不處理 target 本身）
```

### 看進度 + 救火數據
```bash
# 任務進度
cd "/d/Users/Administrator/Desktop/公文ai agent"
echo "完成 $(rg -c '^- \[x\]' program.md) / 待辦 $(rg -c '^- \[ \]' program.md)"

# reconciled 真實成果
bash /d/Users/Administrator/Desktop/公司/auto-dev/scripts/reconcile-results.sh

# Live ingest 擴大
python scripts/live_ingest.py --sources datagovtw,mojlaw,executive_yuan_rss --limit 100 --require-live --report-path /tmp/ingest.md
```

### Copilot loop 重啟（當前暫停）
```bash
mv "<Startup>/copilot-engineer-loop.vbs.disabled" "<Startup>/copilot-engineer-loop.vbs"
nohup bash /d/Users/Administrator/Desktop/公司/auto-dev/scripts/copilot-engineer-loop.sh >/dev/null 2>&1 & disown
```

---

## 📚 相關 MEMORY

下次 session grep 這些 memory 就能接手：
- `gov-ai-bootstrap-20260420.md` — 專案啟動、方向翻轉脈絡
- `gov-ai-acl-rescue-20260420.md` — ACL 問題 + 三 loop 架構
- `gov-ai-git-migration-20260420.md` — .git 遷移實驗（已 rollback）
- `auto-dev-audit-rotate-bug-20260420.md` — audit-rotate fix
- `auto-dev-discord-lbbot-push.md` — Discord 推送配置
- `feedback_codex_service_tier_flex.md` — tier=flex 禁忌教訓

---

## 🎯 下一階段路線圖

1. **立即**（~1 hr）：auto-engineer 按 v5.6 執行 P0.1/P0.2/P0.3
2. **本日**：live_ingest 擴到 300+ 份真實資料
3. **本週**：新 PccAdapter、nemotron 全量重建、E2E 改用真實資料
4. **未解**：CLI 升級後恢復 Copilot loop、ACL 根因深挖（procmon 監測 re-apply）

---

**備註**：若 context 滿需開新 session，直接 Read 此檔 + 相關 memory 即可接手。當前 3 loop 24/7 跑，不需手動介入直到下次觀察點。
