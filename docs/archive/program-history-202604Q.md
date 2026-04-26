# Program History Archive — 202604Q

> 封存時間：2026-04-27 Copilot agent v8.11
> 原始來源：`program.md` v8.8（lines 48-88）+ v8.6 P0/P1/P2（lines 89-135）

---

> **v8.8 批次回合（2026-04-26 21:35 /pua 深度回顧；HEAD=39d1232 ≡ origin/main）**：
> - ✅ **HEAD = origin/main = 39d1232**（rev-list 0/0；工作樹 clean — 漂白第一型 4 輪後本輪終止 ✓）
> - ✅ **pytest -x = 3999 passed / 80.43s**（+12 vs v8.6 3987；soft 200s 守住）
> - ✅ **fat watch 收斂**：9 檔/max=323（v8.6）→ **6 檔/max=314**（v8.8）= T-FAT-WATCH-CUT-V4 收效
> - ⚠️ **runtime baseline 仍寫死 50.0s 第 3 輪**：T-RUNTIME-RATCHET-LIVE-MEASURE-v2 標 [x]；今日 cold 80.43s（+62%）也未自動 ratchet up = **漂白第十一型第 3 輪治本未真閉**；治本 = baseline 改「ceiling + tolerance」雙語意防 up-creep
> - ⚠️ **openspec 半殭屍 active dir**：active list 仍有 `18-multi-llm-provider-abstraction/`，archive + spec 已落 = active=1 假象；治本 = `git rm -rf` + commit
> - ⚠️ **epic 管線真空預警 + 第 5 輪「無下個 epic」**：候選 corpus 500 / engines hot-switch / KB recall@k；不開 = treadmill 預兆
> - ⚠️ **cli/ 三檔同模組 fat 邊緣 300-314**：`batch_tools 314 / config_tools 312 / lint_cmd 309` 同模組 ROI ×3 預抽

### P0（2026-04-26 21:35 /pua v8.8 深度回顧新增；本輪必動 — 半殭屍 active + baseline 寫死第 3 輪）

- [x] **T-OPENSPEC-18-ACTIVE-CLEANUP**（5 min；P0；ACL-free；最小修）— `git rm -rf openspec/changes/18-multi-llm-provider-abstraction/` + commit `chore(openspec): remove archived change-18 active dir`；archive 與 spec 已落保留；驗收：`spectra list` = `No active changes.` + `ls openspec/changes/` 僅剩 `archive/`。owner = auto-engineer。**不清 = `spectra list` 永遠騙人，active 名義 1 實際 0**。
- [x] **T-RUNTIME-BASELINE-TRUE-MEASURE-v3**（30 min；P0；ACL-free；漂白第十一型第 3 輪治本）— `scripts/sensor_refresh.py` 主路徑必跑 `--measure-runtime`（非 opt-in）；`scripts/runtime_baseline.json` 加 `ceiling_secs` + `tolerance_pct`（不只 floor）；新值 > ceiling × (1+tolerance) 即 sensor soft；80.43s 寫入 sensor.json 取代 50.0；補 `tests/test_sensor_refresh.py` ceiling/up-creep 2 cases。驗收：`sensor.json.pytest_cold_runtime_secs` ≠ 50.0 寫死 + sensor `--human` 顯示真值 + ceiling 違例可觸發 soft。

### P1（2026-04-26 21:35 /pua v8.8 新增；epic 管線突破 + cli fat 預治）

- [x] **T-OPENSPEC-EPIC-19-DISCOVERY**（30 min；P1；ACL-free；velocity 突破 — 第 5 輪預警）— 評估 3 候選：(a) **corpus 500 真語料 + recall@k 量測**（補 v7.5 凍結的 T5.2/T5.3）、(b) **engines hot-switch runtime API**（延伸 v8.7 engines API + WebSocket push）、(c) **KB recall validation pipeline**（embed/cite/rewrite 三段量化）；選 1 開 `openspec/changes/19-*/` proposal + tasks 骨架（≥5 sub-tasks）；目標 `spectra list` 真值 active=1。
- [x] **T-FAT-WATCH-CUT-V5-CLI-MODULE**（45 min；P1；ACL-free；3 檔同刀 ROI ×3）— `src/cli/batch_tools.py 314→260`（抽 `_batch_runner.py`）+ `src/cli/config_tools.py 312→260`（抽 `_config_io.py`）+ `src/cli/lint_cmd.py 309→260`（抽 `_lint_rules.py`）；驗收：`scripts/check_fat_files.py --watch-band 300-350` ≤ 3 檔 + 全量 pytest 不退。

### P2（2026-04-26 21:35 /pua v8.8 新增；engineer-log 預治）

- [x] **T-ENGINEER-LOG-ARCHIVE-202604N**（10 min；P2；ACL-free；soft 紅線預治）— engineer-log 目前 ≈ 297 行（本輪反思寫完）；下輪寫前必先把 v8.5/v8.6 兩段（line ~144-271）封存到 `docs/archive/engineer-log-202604N.md`；header pointer 補；主檔 ≤ 200 留下輪空間。

---

### P0（2026-04-26 20:30 /pua v8.6 深度回顧新增；本輪必動 — ACL 連 3 輪 + 散裝 13+5 + log hard cap）

- [ ] **T-GIT-ACL-PERMA-FIX**（host Admin gate；連 3 輪 P0 open；structural blocker）— host 啟動腳本永久清 `.git` DENY ACL：(a) `icacls "%REPO%/.git" /remove:d <SID>` + `/inheritance:e`；(b) keeper / supervise wrapper 改用 `env -i YOLO_MODE=on` 顯式繼承（非 subshell reset）；(c) 5+ 輪 0-residual 監測（`git status` clean × 5 輪）方算真閉。驗收：本 session approval=never 下 `git add` 0 retry 通過；`icacls .git` 無 `(DENY)(...)` ACE。owner = host Admin。**不解 = v8.5/v8.6 全部工作量歸零**。
- [x] **T-EPIC-18-COMMIT-FLUSH**（2026-04-26 閉；P0；ACL 自然解除）— 工作樹 13 mod + 5 untracked 拆語意 commit。驗收：`git status --short` = clean；`pytest tests/test_engines_api.py = 2 passed`。
- [x] **T-ENGINEER-LOG-ROTATE-v10**（2026-04-26 閉；P0；ACL-free；hard cap 治本）— v8.0-r5 深度回顧 + v8.1 反思 2 段（~75 行）封存到 `docs/archive/engineer-log-202604M.md`；主檔降至 276 行（≤ 300 hard cap ✓）。

### P1（2026-04-26 20:30 /pua v8.6 新增）

- [x] **T-MARKED-DONE-COMMIT-RATCHET**（2026-04-27 閉；P1；ACL-free）— `scripts/sensor_refresh.py` 新增 `marked_done_uncommitted` 欄位；8 unit tests；3998 passed ✓。
- [x] **T-RUNTIME-RATCHET-LIVE-MEASURE-v2**（2026-04-27 閉；P1；ACL-free）— `scripts/sensor_refresh.py` 改為主路徑自動跑 `pytest --collect-only`；ratchet down；`--no-measure` opt-out；33 passed ✓。
- [x] **T-FAT-WATCH-CUT-V4**（2026-04-27 閉；P1；ACL-free）— `_manager_hybrid.py` 323→247、`api/app.py` 319→226、`document/exporter/__init__.py` 319→243；3998 passed ✓。

### P2（2026-04-26 22:51 Copilot agent v8.9 新增）

- [x] **T-PROGRAM-MD-ARCHIVE-202604O**（10 min；P2；ACL-free；v8.9 新增）— program.md 285 行 > soft 250；封存 v8.1/v8.3/v8.4/v8.5 完成區塊（line 67-113）到 `docs/archive/program-history-202604O.md`；主檔降至 241 行（< 250 ✅）。
