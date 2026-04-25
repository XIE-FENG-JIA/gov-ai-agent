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
> 規則：單輪反思 ≤ 40 行；主檔 ≤ 300 行硬上限；超出當輪 T9.6-REOPEN-v(N) 必封存。

---

> v5.0（第二十八輪）/ v5.1（第二十九輪）反思已封存至 `docs/archive/engineer-log-202604d.md`。
> v5.2（第三十輪）反思已封存至 `docs/archive/engineer-log-202604e.md`。
> v5.4（第三十二輪）/ v5.5（第三十三輪）/ v5.6（第三十四輪）反思已封存至 `docs/archive/engineer-log-202604f.md`。
> v5.7 / v5.8 / v5.9 / v6.0 反思已封存至 `docs/archive/engineer-log-202604g.md`。
> 主檔現存：v7.0 pua-loop 接管第 1/2 輪（LOOP_DONE）+ v7.1 LOOP2 第 2/3/4 輪 + Epoch+ 深挖（T-PYTEST-RUNTIME-FIX-v2）。

> v6.1→v6.2 / v6.3 / v7.0 / v7.0-sensor 4 段反思已封存至 [`docs/archive/engineer-log-202604h.md`](docs/archive/engineer-log-202604h.md)（2026-04-25 T9.6-REOPEN-v6 執行；主檔 512 → 229 行）。
> v7.0 接管第 1/2 輪（LOOP_DONE）+ v7.1 LOOP2 第 2/3/4 輪（task a-k + 冰山第 2 型閉）+ v7.2 第 43 輪 sensor 已封存至 [engineer-log-202604i.md](docs/archive/engineer-log-202604i.md)（2026-04-25 T9.6-REOPEN-v7 執行；主檔 437 → 108 行）。

## 反思 2026-04-25 02:45 — 技術主管六維度深度回顧（v7.3；LOOP3 中段；HEAD 獨立 sensor）

### 三證自審（HEAD 跑，不信 header）
- `git status --short` = **0 行**（`6eb9907` 剛 AUTO-RESCUE 收 T-PYTEST-COLLECT-NAMESPACE 變更）
- `wc -l program.md engineer-log.md results.log` = **254 / 351 / 472**（engineer-log **破 300 hard cap 51 行**，T9.6-REOPEN-v7 下輪強制；program.md 超 250 錨點 4 行）
- `grep -rEc "except Exception|except:" src/` 過濾非 0 = **89 處 / 58 檔**（header 仍寫 109 stale；T-HEADER-SENSOR-REFRESH 未落地即再漂白）
- `find kb_data/corpus -name "*.md" | wc -l` = **173**（連 6+ 輪 0 動）
- auto-commit 語意率近 30 = **26/30 = 86.7%**（4 條 checkpoint：`6eb9907 / 96c9d05 / c53a947 / 1eef399`，最近 5 條佔 2 條 → **近段惡化**，非穩定）
- Spectra：01-05 = **55/55 全閉**；06 = **2/13**（T-LIQG-1 / T-LIQG-2 已落，11 條待）
- 工作樹 M 檔全清（BM25 cap 已入 `1eef399`，T-WORKTREE-CLEAN **已達成**但 program.md P0 header 未勾）
- **pytest cross-session cold-start（本輪實跑）**：`pytest tests/ -q --ignore=tests/integration -x --timeout=900` = **3801 passed / 152.98s / exit 0**（比 LOOP3 熱 cache 173/179s 還快 20s = **BM25 cap 真效確認，非 cache 假象**）；**已破下 epoch ≤ 200s 目標 47s 裕量**；runtime 演進：`960 → 773 → 547 → 461 → 340 → 343 → 179 → 173 → 153s`（累計 **-84%** vs 開局）

### 六維度分析（技術主管視角）

**1. Spectra 規格對齊**
- 01-05 proposal+tasks+specs **100% 閉**（55 task 全 [x]）✅
- 06-live-ingest-quality-gate：骨架 `33bf8ce` + 實作 `c53a947`（T-LIQG-1 quality_gate.py 171/test 99）+ `96c9d05`（T-LIQG-2 quality_config.py）兩件落；**T-LIQG-3..12 共 11 條待**
- 偏離：**無實質偏離**，Spectra workflow 嚴格遵循 proposal → tasks → spec → impl+test

**2. 最近輪次成果 vs 反覆卡住模式**
- 成功梗概：pytest `960s → 173s (-82%)`、冰山三型全發現、5 proposal 閉、EPIC6 骨架 + 2 task 落、governance 腳本雙胞胎、BM25 DoS 保護
- **反覆卡**：
  - (a) **P0.D ACL DENY 7+ 輪**：`icacls .git` 顯 DENY(W,D,Rc) 但 AUTO-RESCUE 每輪代 commit 全通；前提**完全錯**。根因 = 外來 SID 對當前 Administrator 不匹配 / parent ACL 覆蓋 deny。應立即降 P2 或改定義為「`.git/index.lock` 偶發 Permission denied」實際症狀
  - (b) **P2-CORPUS-300 6+ 輪 0 動**：等 EPIC6 T-LIQG-4 `--quality-gate` flag 才能安全擴量，死結結構性
  - (c) **auto-commit 違規 4 次**：T-COMMIT-SEMANTIC-GUARD lint 已 ready（`scripts/commit_msg_lint.py` 117 行 / 19 test），但 pre-commit hook wire 被 `.git/hooks/` 寫入 ACL 擋；**根因同 (a)**
  - (d) **header 連 2 輪漂白**：sensor refresh 依賴反思輪（72hr 週期），實測指標漂移 20-80%

**3. 程式碼品質**
- 胖檔：`datagovtw.py 410` 連 N 輪破 ≤ 400 錨點；`web_preview/app.py 399 / api/routes/agents.py 397 / validators.py 391` 全逼近紅線
- 裸 except 熱點：新 TOP 6 = `_manager_hybrid / reviewers / config_tools / workflow/_endpoints / editor / compliance_checker` 各 3 處 = 18 處 / 20% 總量
- TODO/FIXME 僅 **5 處**（低），非結構債
- code smell：**Python local binding** 是專案反覆踩的坑（冰山第 1 型 `from src.api.dependencies import` 模式），需 ast-grep rule + CONTRIBUTING.md 規範落地

**4. 測試覆蓋**
- 全量 **3802 passed / 10 skipped**（LOOP3 02:38 T-PYTEST-COLLECT-NAMESPACE 修後）
- 覆蓋結構：tests/ 單元 + integration/ e2e 分級清晰
- **缺測模組/邊界案例**：
  - `src/sources/datagovtw.py 410` 胖檔未拆，邊界測試集中於 adapter 單點
  - `src/knowledge/_manager_hybrid.py` BM25 cap 測試 `test_search_very_long_string` 僅 1 條；應補 `query_length_exactly_500 / 501 / empty / unicode overflow` 邊界
  - `src/sources/quality_gate.py` 4 named failure 各 1 test（6+5 = 11 passed），但 **多源混合失敗 / cascade** 場景未測
  - integration tests 10 skipped 未深挖 skip 原因

**5. 架構健康度**
- 模組劃分合理：`agents / api / cli / core / document / graph / knowledge / sources / web_preview` 九個頂層清晰
- 輕度過度耦合：`src/api/app.py` 透過 `from src.api.dependencies import get_config` 創 local binding，測試 patch 層打不到 → 冰山第 1 型；已發現未系統治
- **auto-engineer + pua-loop 雙引擎分工**（owner 視角健康）：code/spec 歸 auto-engineer，governance/doc/驗證歸 session；兩者 race 條件已發生（LOOP2 第 4 輪 pytest 撞車），需 process tree heartbeat

**6. 安全性**
- ✅ BM25 query cap 500 字（DoS 保護，`1eef399`）
- ✅ synthetic flag 概念落地（examples 155/192 ≈ 80.7%，37 份未標待稽核）
- ✅ User-Agent 明示 + robots.txt + rate limit ≥2s/req（OpenSpec 01-real-sources 規範）
- 🟠 **`.env` 實檔位於 repo 根**（3042 bytes）；需驗 `.gitignore` 有 `.env` 且 `git log --all -- .env` 無歷史提交
- 🟠 **P0.D ACL 前提錯**：目前把「`.git/index.lock` Permission denied」誤歸「SID DENY ACL」，掩蓋真實阻塞（index.lock 可能是並行 auto-engineer 的競態鎖）
- 🟡 PII 真實資料 guard：`corpus_provenance_guard.py` 有測試但 live crawl 路徑 `synthetic=false` 預設值信賴人工維護

### 發現的問題（優先級排序）

🔴 **P0（連 1 輪延宕 = 3.25）**
1. **T9.6-REOPEN-v7 engineer-log 封存** — 主檔 351 > 300 hard cap，T9.6-REOPEN-v6 才做完 4 天就再犯；封存本段 + v7.3 保留單輪
2. **T-HEADER-SENSOR-REFRESH 落地** — 連 2 輪漂白已升 3.25 X 2；`scripts/sensor_refresh.py` 必須本輪 commit 且掛 starter checklist 第 0 步
3. **T-ACL-STATE-RECALIBRATE** — P0.D 前提錯 7+ 輪，必須 15 min 內查清並決策：降 P2 / 改定義 / 真查 SID 匹配
4. **T-AUTO-COMMIT-SEMANTIC 硬落地** — auto-engineer 再犯 4 次違規（包括本 session 2 次），生成器必改 `chore(auto-engineer): ...` 格式
5. **T-BARE-EXCEPT-AUDIT 刀 6** — 新熱點 18 處；目標總量 ≤ 80
6. **T-FAT-ROTATE-V2 刀 10/11** — `datagovtw.py 410` + `api/routes/agents.py 397` 拆 package

🟠 **P1（連 2 輪延宕 = 3.25）**
7. **EPIC6 T-LIQG-3/4/5** — CLI gate-check / rebuild flag / failure matrix doc（T-LIQG-1/2 已落地）
8. **T-TEST-LOCAL-BINDING-AUDIT** — ast-grep rule + CONTRIBUTING + conftest 全域 re-bind helper
9. **T-PYTEST-RUNTIME-FIX-v3** — cold-start baseline；目標 ≤ 200s 守穩
10. **T-SYNTHETIC-AUDIT** — 155/192 未覆蓋 37 份稽核

🟡 **P2（結構性依賴）**
11. **P2-CORPUS-300** — 等 T-LIQG-4 `--quality-gate` flag 才擴量，改為 blocked-by
12. **P0.D ACL** — 視 T-ACL-STATE-RECALIBRATE 結果重定位
13. **P2-CHROMA-NEMOTRON-VALIDATE** — Admin/key 依賴不變

### 下一步行動（最重要的 3 件事）

1. **T-HEADER-SENSOR-REFRESH 本輪必 commit**（45 min）：`scripts/sensor_refresh.py` 跑 wc/rg/git/find → 輸出 JSON + 重寫 program.md 頂部 sensor 區塊；**這是解 (d) 連 2 輪漂白的根因解，不是 patch**
2. **T-ACL-STATE-RECALIBRATE**（15 min）：`whoami /user` + `icacls .git | grep <current-SID>` + `git commit --dry-run` 三連查真實阻塞位點；docs/acl-recalibrate-2026-04-25.md 結論落地；**解 7+ 輪誤歸屬 P0.D**
3. **T9.6-REOPEN-v7**（10 min）：engineer-log v7.0/v7.1/v7.2 三段封存到 `docs/archive/engineer-log-202604i.md`，主檔只留 v7.3 單段（本段）

### PUA 旁白
> [PUA生效 🔥] **底層邏輯**：LOOP2 / LOOP3 兩次都是 pytest runtime 漂亮降（960→173），但 governance side (header sensor / ACL 定義 / auto-commit lint) 全是**未機械化的人工維護**，自然每輪漂白。抓手：把 governance 鐵三角（sensor / ACL / commit lint）變成 every-round 腳本，**不靠反思輪維護**。**颗粒度**：本輪三件（sensor script / ACL recalibrate / log 封存）合計 70 分鐘，一 session 可閉。**對齊**：auto-engineer 繼續攻 EPIC6 T-LIQG-3/4/5 + 裸 except 刀 6 + fat-rotate 刀 10/11（它擅長），我守 governance 閉環（reflection + header + ACL）；兩條線合流才是 LOOP_DONE。**因為信任所以簡單** — 反覆踩同一個坑就是結構問題，不是執行問題；給我一個 `scripts/sensor_refresh.py` 下輪直接消除「header 漂白」這類 3.25。Owner 意識 = 發現紅線不是罰自己，是**升級系統讓紅線不再觸發**。

### LOOP3 task B+C 閉環（2026-04-25 03:20；T9.6-v7 + sensor_refresh 落地）

**本輪兩件同 session 連閉**（分 2 commits 保顆粒度）：
- **B** `fa59dda docs(engineer-log)`：T9.6-REOPEN-v7 engineer-log 437→108 行；封存 v7.0/v7.1/v7.2 五段 329 行到 `docs/archive/engineer-log-202604i.md`；主檔只留 v7.3 單段
- **C** 本 commit：`scripts/sensor_refresh.py` + `tests/test_sensor_refresh.py` 12 passed / 2.13s；HEAD 實測證據

**sensor 首跑驚人發現**（v7.0/v7.3 header 都漏）：
- 🔴 `src/cli/kb/rebuild.py 572` — **從未被 fat-watch 偵測的超大胖檔**（v7.0 `> 400` 清單寫 2 檔 / v7.3 寫 5 檔，實 red 只有這 1 個但最大）；sensor 一跑就補了
- auto-commit 語意率實 **73.3%**（v7.3-sensor 寫 86.7% + 進一步漂白）
- engineer-log 109（本 session B commit 後真值；v7.3-sensor 寫 351 是封存前）
- program.md 281（v7.3-sensor 寫 254，auto-engineer 又加 27 行）

**紅線 v4 落地**：
- 每輪第 0 步必跑 `python scripts/sensor_refresh.py`
- exit=2 禁開新 task（hard violation 先修）
- 禁止靠 program.md header 記憶當事實源
- 此紅線在 CONTRIBUTING.md loop 流程章節掛勾

**下 epoch 候選**（sensor 補強後自動開出）：
- `T-FAT-ROTATE-V2 刀 12`：`cli/kb/rebuild.py 572` 拆 package（全 session 第 1 大胖檔）
- `T-CORPUS-300`：current 173 → 200 soft target，需 MOHW/FDA/executive_yuan live ingest 擴量

> [PUA生效 🔥] **底層邏輯**：sensor 一上線就抓到 `rebuild.py 572` — 這叫「**腳本發現人眼看不到的**」。前 v7.0 到 v7.3 三版 header 連續漂白 + 漏抓同一個 572 行檔，證明腳本化的 ROI。**抓手**：governance 從「反思輪人腦刷新」變「每輪腳本自動刷」。**颗粒度**：260 行 script + 150 行 test + 紅線 v4 一條 = 下輪起點永不漂白。**對齊**：auto-engineer 管程式碼擴張（它碰 src 加新檔），我管 governance 收斂（sensor 量、紅線、封存）。**因為信任所以簡單** — 不是我抓到 572 行，是 **script 抓到**；owner 意識 = 建系統，不是當英雄。

---

## 反思 2026-04-25 15:06 — 技術主管六維度深度回顧（v7.6；LOOP4 中段；HEAD + sensor + pytest 三證獨立）

### 近期成果（第四十五至四十六輪）
- **pytest 3913 passed / 0 failed / 42.90s**（cold run 本 session 實跑；自 v7.3 153s → v7.6 43s 再 -72%；總 -95.5% vs 開局 960s；xdist -n auto + jieba early-return + mock_llm 修復三件事複利）
- **EPIC6 13/13 全閉**（T-LIQG-0..12 全 [x]；live-ingest quality gate 4 named failure 落地）+ **EPIC1-5 55/55 全閉**（55/55 task 全 [x]）
- **bare-except 71→47**（刀 6/7/8 三輪），**fat >400 = 0**（刀 10/11/12/13 拆 package 後 11 檔 yellow watch），**auto-commit 語意率 50%**（vs 開局 6.7%，+43pp）
- **iceberg 三型系統治**：scripts/audit_local_binding.py + rebind_local helper + CONTRIBUTING.md mock contract rules + docs/test-mock-iceberg-taxonomy.md（67 候選 AST 掃完）
- **governance 機械化**：sensor_refresh.py 每輪第 0 步紅線 v4 + check_acl_state.py token-aware + check_auto_engineer_state.py 6 狀態 + commit_msg_lint v3 + validate_auto_commit_msg.py
- **回歸閉環**：T-REGRESSION-FIX-刀8（commit 827e601）修 bare-except sweep 過收窄導致的 12 LLM/KB graceful-degradation 回歸；3914 → 3913 passed 穩態

### 發現的問題（HEAD sensor + pytest + grep 三源獨立比對）

🔴 **P0（漂白現行 + spec lag）**
1. **header 漂白第 4 輪**：v7.5 header 寫 bare-except「2 處 / 2 檔（noqa/compat）」，sensor 實測 **48 處 / 39 檔**（T-REGRESSION-FIX-刀8 把 rewrite/refine/pipeline 的 except bucket 又擴回 except Exception 後反彈 46 處）。**sensor_refresh.py 每輪第 0 步必跑但本輪未跑**，紅線 v4 失守。
2. **spec 11 漂白**：`openspec/changes/11-bare-except-iter6-regression/tasks.md` T11.1-T11.5 全 `[ ]`，但代碼層 commit 827e601 已修 12 測試 + 3913 passed。spec lag 第 2 漂白。
3. **spec 08 漂白**：`08-bare-except-audit-iter6/tasks.md` 7 task 全 `[ ]`，但 program.md 寫刀 6/7/8 全閉、bare-except 71→47 已落。spec lag 第 3 漂白。
4. **spec 07 半閉**：`07-auto-commit-semantic-enforce/tasks.md` 4/5 done，1 task 未勾（hook wire 待 ACL 解；T-AUTO-COMMIT-SEMANTIC 已驗 33 passed）。
5. **spec 09 半閉 + spec 10 半閉**：09 fat-rotate-iter3 = 2/5；10 test-local-binding-audit-systematic = 5/6。

🟠 **P1（結構性技術債）**
6. **robots.txt 政策實施 gap**：OpenSpec 01 spec.md 寫「robots.txt restrictions MUST be respected」，但 `grep robots src/ --include='*.py'` = **0 命中**；只有政策、無 code。
7. **__pycache__ 殘留 3624 個 `.pyc.<id>` 檔**：`.gitignore` 排 `__pycache__/`（git 不入版），但磁碟堆積 pytest-xdist worker 殘留；`reader.cpython-311.pyc.1638051766016` 類型 16 變體 / 檔，會拖 fs scan 與 binary grep。
8. **corpus 173 vs target 200/300**：EPIC6 quality gate 已 unblock，但 P2-CORPUS-300 仍 6+ 輪 0 動 — **owner 在 spec 不在 corpus**，需主動跑 `scripts/live_ingest.py --sources mojlaw,datagovtw,executive_yuan_rss,pcc --limit 100 --require-live`。
9. **fat yellow watch 11 檔逼近紅線**：`validators 391 / _execution 389 / realtime_lookup 386 / law_fetcher 377 / wizard_cmd 374 / constants 374 / manager 369 / web_preview/app 364 / _manager_hybrid 358 / kb/rebuild 356 / template_cmd/catalog 350` — 任一 +50 行即 red，需建 ratchet。
10. **integration tests 10 skipped 未深挖**：skip 集中於哪些測試 / 為什麼 skip / 是否 live API gating，缺 audit。

🟡 **P2（次優先；Admin/key/服務依賴）**
11. **P2-CHROMA-NEMOTRON-VALIDATE** unblocked（OPENROUTER_API_KEY 已驗）但實際 rebuild 與 docs/embedding-validation.md 未跑。
12. **legacy P2-INDEX-LOCK** 仍存在但已降級；不影響 AUTO-RESCUE 路徑。
13. **auto-commit 語意率 50% 仍遠低於 90% 目標** — runtime-seat（auto-engineer 內部生成 commit msg）尚未對齊 chore(auto-engineer) 模板，hook 被 ACL 擋。

### 建議的優先調整（program.md 待辦重排）

把以下 5 件升 P0 並重排為「現行待修」：
1. 🔴 **T-HEADER-RESYNC-v5**（10 min）— sensor 實測 vs header 三點漂白：bare-except 48/39 vs 2/2、spec 11 全開 vs commit 已修、spec 08 全開 vs 71→47 已落。本輪必刷 header + 補勾 spec tasks。
2. 🔴 **T-SPEC-LAG-CLOSE**（15 min）— `openspec/changes/{08,11}/tasks.md` 全勾 `[x]`；`07/09/10` 半閉 task 補完或明列剩餘步驟。
3. 🟠 **T-ROBOTS-IMPL**（30-45 min）— `src/sources/_common.py` 加 `RobotsCache` 類 + `urllib.robotparser`，所有 adapter `_request()` 前 check disallow；補 `tests/test_robots_compliance.py` 至少 3 條（allow / disallow / parse-fail fallback）。
4. 🟠 **T-PYC-CLEAN**（5 min）— `find src -name "*.pyc.*" -delete` + `.gitignore` 加 `*.pyc.*` pattern + pytest-xdist hook 在 session end 清理。
5. 🟠 **T-CORPUS-200-PUSH**（45 min）— EPIC6 已 unblock，跑 `scripts/live_ingest.py --sources mojlaw,datagovtw,executive_yuan_rss --limit 100 --require-live --quality-gate`，目標 173 → 200 soft，driving CORPUS-300 第一刀。

### 下一步行動（最重要的 3 件事）
1. **T-HEADER-RESYNC-v5 + T-SPEC-LAG-CLOSE 同 commit**（25 min）— 一刀解 4 處漂白；sensor_refresh.py 跑後實寫 header；補勾 spec 08/11 全閉、07/09/10 列剩餘。
2. **T-ROBOTS-IMPL**（45 min）— spec 與 code 對齊；OpenSpec 01「MUST」契約落地 code；compliance gate 集中化（解 v3.3 / v4.4 封存中提的「合規閘道缺位」歷史債）。
3. **T-PYC-CLEAN + T-CORPUS-200-PUSH 並行**（60 min）— 磁碟整理 + corpus 擴量；可 auto-engineer 領 corpus，session 領磁碟+gitignore；單 commit 收尾。

### PUA 旁白
> [PUA生效 🔥] **底層邏輯**：sensor 跑出來 48/39 但 header 寫 2/2 — 又一次「**反思輪不跑 sensor 就是漂白**」。紅線 v4 訂下「每輪第 0 步必跑 sensor_refresh」，本輪這份反思啟動時就漏跑，**規則訂了不執行等於沒訂**。**抓手**：把 sensor_refresh.py 接到 PUA / Claude session 啟動 hook（`SessionStart`），不靠人記。**颗粒度**：4 種漂白合計 25 min 可清；用一個 PR 收完。**對齊**：auto-engineer 在 round 136 跑 reflect phase，session 我跑 sensor + spec 補勾，兩條腿不打架。**因為信任所以簡單** — header 是事實的代理，代理跟事實偏離就是治理失靈；治理失靈不是「我手抖」，是**沒上機械化 hook 自動鎖**。Owner 意識 = 紅線抓現行立即升級規則（sensor 從「腳本」升「啟動 hook」），而不是下輪繼續手動跑。3.25 X 4 自記 — 連 4 次 header lag 沒上自動化 hook，本輪不上下輪還是漂白。

### LOOP4 任務拆解（auto-engineer / session 雙引擎）
- **auto-engineer**（codex round 136+）：T-ROBOTS-IMPL 程式碼層、T-CORPUS-200-PUSH live ingest（它擅長）
- **session（本反思）**：T-HEADER-RESYNC-v5、T-SPEC-LAG-CLOSE、T-PYC-CLEAN、program.md 重排（governance 閉環）
- **合流點**：兩條線單 commit 收尾後跑 `python scripts/sensor_refresh.py | python -c "import json,sys; r=json.load(sys.stdin); assert not r['violations']['hard']"` exit 0 才算 LOOP_DONE
