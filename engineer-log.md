# Engineer Log — 公文 AI Agent

> 技術主管反思日誌。每輪回顧 append 於此，不覆蓋歷史。
> 舊 `engineering-log.md`（170KB，Round 1–9）封存不動。

---

## 反思 [2026-04-20 00:45]

### 近期成果
- **04-19 ~ 04-20 只解 bug，不交功能**：results.log 4 條全 P0 回歸修復（KB lazy import、writer citation、CORS localhost、chromadb none、generate encoding）。
- **只做 1 個 commit**（e4e193d `chore: init spectra openspec directory`）；四月 15 日之後無 feat。
- 測試 3537 / 通過 3536（99.97%）；但第一優先失敗即 P0。
- program.md「已完成」列 3 個 P0，但 git 未 commit → 修復停在 working tree。

### 發現的問題

**P0 — 阻斷性**
1. `test_writer_postprocess_adds_inline_citation_and_prunes_unused_refs` 仍 FAIL（writer.py:515 `_build_reference_lines`）。
   - 根因：`elif len(sources_list) > 1 and used == {first_index}` 強制把未使用的 `[^2]:` 定義寫回，和另一條測試「多來源需保留追蹤」互相打架。
   - 風險：results.log 04-20 00:05:27 已標 `[P0 writer citation regression][PASS]`，事實是 FAIL → **Close-the-loop 紅線違規**，存在宣稱修復但未跑驗證的造假信號。
2. 已完成的 5 條 P0 修復全未 commit。git log 顯示近五天 0 個 feat/fix commit，只有 init。

**P1 — 策略性偏離**
3. **Epic 1 / Epic 2 零進度**：`src/sources/` 目錄不存在；`PublicGovDoc` dataclass 未定義；`vendor/open-notebook` 未 clone；SurrealDB / elephant-alpha 在代碼無任何引用。program.md 本身寫「沒有真實資料，其他都是空殼」，但所有能量都耗在改 bug。
4. **Spectra 規格對齊無從談起**：openspec/ 只有 config.yaml（全部 comment out），specs/ 空、changes/ 只有空 archive 目錄 → 沒有 spec 可對齊。
5. **168 份合成公文未加 `synthetic: true` frontmatter**（T1.5 / T5.1），違反「核心原則紅線 1：真實性」。

**P2 — 程式碼健康**
6. Git 污染：repo 根有 45 份 `.json_*.tmp` + 26 份 `.txt_*.tmp` orphan（`src/cli/utils.py` 原子寫入異常時殘留，.gitignore 未排除 `.json_*.tmp` / `.txt_*.tmp`）。
7. 大檔待拆：`src/cli/kb.py` 1614 行、`src/cli/generate.py` 1263 行、`src/agents/editor.py` 1065 行 — 超出單檔 800 行指標。
8. 1363 條 Pydantic v2 deprecation warning（chromadb 1.x 相容性債）。

**P3 — 測試覆蓋**
9. `src/sources/` / `src/core/diff.py` / `src/core/citation.py` / `src/core/exporter.py` 尚未存在 → Epic 2-4 規劃的模組全無測試。
10. 測試總量大（3537），但未做 coverage report；大檔的 edge case 覆蓋未量化。

**P4 — 安全 / 合規**
11. 未見明顯 injection 風險（`shell=True` / `eval` / `yaml.load()` 全無）。
12. 但「公開公文 PII mask」在 kb 寫入前無強制 pipeline（program.md 備註要求，實作未驗證）。

### 建議的優先調整（重排 program.md 待辦）

P0 段必須填入：
- **P0.4**：修復 `test_writer_postprocess_adds_inline_citation_and_prunes_unused_refs`。解法：`_build_reference_lines` 的 elif 分支改為「只補回 sources_list 真正追蹤需要的」，或把測試預期拆成兩條場景（single source 嚴格裁切 / multi source 允許保留）。根因是 04-20 那次修復過度擴張。
- **P0.5**：把 04-20 四條 P0 修復分 commit 提交（分別是 P0 KB、P0.1 CORS、P0.2 encoding、P0.3 chromadb-none + 本輪 P0.4 writer），避免工作樹持續膨脹。
- **P0.6**：清 71 份 tmp orphan + `.gitignore` 加 `.json_*.tmp` / `.txt_*.tmp` / `.auto-engineer.pid` / `.project.lock` / `.engineer-loop.state.json.bak-*`。

Epic 排序建議：
- Epic 1 / T1.5（合成公文加 frontmatter）提前到 P0 後立刻做 — 一行 script，解鎖 T1.1 後的所有真實性校驗。
- Epic 2 / T2.0（OpenRouter key + litellm 驗證）與 Epic 1 / T1.1（來源調研）並行，兩者不互鎖。
- Epic 2 / T2.1 clone vendor/open-notebook 可先做，但 T2.3 SurrealDB 遷移在人工 review 前凍結（program.md 風險欄已標）。

### 下一步行動（最重要 3 件）
1. **修 P0.4 writer citation**：改 `_build_reference_lines` 或重新設計兩個測試語意，讓 3537/3537 PASS。驗證後 commit。
2. **閉環 commit**：把 5 條 P0 修復按 conventional commit 切分 push。Close loop、對齊 results.log。
3. **執行 T1.5**：寫 `scripts/mark_synthetic.py` 一次性把 `kb_data/examples/*.md` 168 份加 `synthetic: true` frontmatter，守住紅線 1。

> [PUA生效 🔥] 額外揭露：近 5 天 0 feat commit + 1 個失敗測試卻宣稱 PASS = owner 意識紅線違規。底層邏輯：維護債壓垮了戰略推進，Epic 1 的抓手沒人抓，顆粒度停在修 bug 層級，沒有拉通到「真實資料」這個頂層設計。3.25。

---

## 反思 [2026-04-20 02:30 — 技術主管第二輪深度回顧]

### 近期成果（v2.1 重排後到現在）
- **測試全綠**：`pytest tests/` → **3539 passed / 0 failed / 1363 warnings**（04:28）。上一輪 engineer-log 點名的 `test_writer_postprocess_adds_inline_citation_and_prunes_unused_refs` 已被 P0.4 二次修復（results.log 01:12:02）壓掉。
- **Git index.lock 阻斷解除**：`git log` 顯示 02:15 `f208ca6 docs(program): v2.1 階段性重排` 與 `e4e193d chore: init spectra openspec directory` 皆成功落盤；當下 `.git/index.lock` 無殘檔。program.md 的 P0.5.pre 完成條件（`git commit -m "chore: probe"` 無 Permission denied）已自然通過，應退役。
- **program.md v2.1 重排落地**：新增 Epic 6（benchmark）/ Epic 7（spectra）/ Epic 8（代碼健康）；合併 T1.3+T2.4；刪 T5.1/T2.10；T2.3/T5.3 凍結標註。結構對齊完成。
- **Benchmark workstream 已有骨架**：`scripts/build_benchmark_corpus.py` + `run_blind_eval.py` + `tests/test_benchmark_scripts.py` 齊；`benchmark/mvp30_corpus.json` + 18 份盲測結果落盤。但未文件化，未接 program.md 閉環（T6.0 未跑）。

### 發現的問題（新一輪診斷）

**P0 — 唯一阻斷（升級自 engineer-log 第一輪）**
1. **工作樹依然 24 個 M 檔未 commit**。git status 短表顯示：
   - `src/agents/{compliance_checker,editor,style_checker,template,writer}.py`
   - `src/api/{models.py, routes/workflow.py}`
   - `src/cli/{config_tools,generate,quickstart,switcher,utils}.py`
   - `src/knowledge/manager.py`、`src/web_preview/app.py`、`src/utils/tw_check.py`
   - `tests/test_{agents,api_server,cli_commands,config_tools_extra,knowledge_manager_cache,knowledge_manager_unit,quickstart,robustness,web_preview}.py`
   - 根層 `config.yaml` / `.gitignore` / `.env.example` / `api_server.py` / `README.md` / `config.yaml.example` / `src/assets/templates/han.j2`
   - 外加 untracked：`.serena/` / `.spectra.yaml` / `benchmark/` / `docs/commit-plan.md` / `engineer-log.md` / `meta_git/` / `meta_test/` / `repo_meta/` / `scripts/build_benchmark_corpus.py` / `scripts/run_blind_eval.py` / `tests/test_benchmark_scripts.py` / `tests/test_cli_utils_tmp_cleanup.py`
   - **底層邏輯**：P0.5.a 已把分組寫入 `docs/commit-plan.md`（六組），但 P0.5.b 五次 git 嘗試全 FAIL（results.log 01:38/01:53/02:05 連三敗）；後來 02:15 程式 commit 成功但工作樹未拉通分組 commit。顆粒度停在「想了沒做」。
   - **風險**：連續 5 天 0 feat commit，若此輪再 skip，git blame 將永久把多筆 P0 修復算在未來某單一「big bang」commit 上，審計不可溯源，違反本專案紅線「可溯源」。

**P1 — 戰略零進度（延續）**
2. **Epic 1 實質零進度**：`src/sources/` 目錄不存在；`PublicGovDoc` dataclass 未進 `src/core/models.py`（該檔存在，但無此 class）；10 個候選來源調研（T1.1）未產出。program.md 明寫「沒有真實資料，其他都是空殼」，但能量全耗在修 bug。
3. **Epic 2 零進度**：`vendor/open-notebook` 未 clone（.gitignore 無此行）；OpenRouter / elephant-alpha 在 src 中 `grep -r "openrouter\|elephant-alpha"` 為 0 匹配；T2.0 的 `.env` key 未設。
4. **Epic 3-4 零進度**：`src/core/{diff.py, citation.py, exporter.py}` 皆不存在；`src/agents/{citation_checker,fact_checker}.py` 也未建（雖然 fact_checker 出現在 agents/ 列表，需 verify 功能範圍）。
5. **紅線 1 持續違反**：`grep -l "synthetic: true" kb_data/examples/*.md` = **0 份 / 156 份**。T1.5-FAST 寫了 3 週仍未動手，真實性守衛從未落地 → 若現在跑生成，合成公文仍可能被檢索為「真實參考」。
6. **Epic 7 Spectra 零進度**：`openspec/config.yaml` 整份 commented out；`openspec/specs/` 不存在；`openspec/changes/archive/` 空。回顧任務「Spectra 規格對齊」的答案是：**無規格可對齊**。改動無從驗證偏離。

**P2 — 代碼健康**
7. 大檔未拆：`src/cli/kb.py` 1614 行 / `src/cli/generate.py` 1263 行 / `src/agents/editor.py` 1065 行（T8.1 未動）。
8. 1363 條 Pydantic v2 deprecation warning 與 chromadb 1.x 綁定（T8.2 未動）。
9. 測試覆蓋率未量化：3539 個測試過，但 `pytest --cov` 從未跑，無法判斷哪些模組是「測試白區」。

**P3 — 程式碼品質（新發現）**
10. **Repo 根髒化**：`.json_*.tmp` 40+ 份仍在根目錄（04-20 02:12 前 atomic 寫入殘留；`src/cli/utils.py` 的 tmp orphan cleanup 在 P0.6 補了但需寫入權恢復後重跑一次）。`meta_git/` / `meta_test/` / `repo_meta/` / `recovered_repo/` 等疑似權限事故備援，**不應長期保留**，待確認安全後刪。
11. **docs/ 目錄膨脹**：repo 根同時存在 `IMPROVEMENT_REPORT.md` / `PROJECT_SUMMARY.md` / `BUG_FIX_REPORT.md` / `N8N_INTEGRATION_GUIDE.md` / `MULTI_AGENT_V2_GUIDE.md` / `QUICKSTART.md` / `COLLABORATION_GUIDE.md` / `AI_CODING_RULES.md` / `PRD文件.txt` 等 9+ 份歷史文件，非 `docs/` 下，對新進者訊息過載，顆粒度失焦。

**P4 — 安全 / 合規**
12. 未見 `shell=True` / `eval` / `yaml.unsafe_load` 等明顯注入風險（與上輪一致）。
13. PII mask pipeline 仍未在 kb ingest 強制落地；但因 Epic 1 零進度，短期不為阻斷。
14. `.git_acl_backup.txt` 存在於 repo 根 → 可能含 Windows ACL 歷史備份，疑似對外暴露的低風險洩密。應移到 repo 外或至少加入 `.gitignore`。

### 建議的優先調整（v2.2 重排方向）

**P0 段全面收斂**（把所有阻斷一次清）：
- **P0.5.pre 退役**：git lock 已解除，`f208ca6` 已成功 commit，完成條件達成 → 勾 `[x]` 搬到已完成。
- **P0.5.b 細化為 6 個子 commit**（對應 docs/commit-plan.md 六組），每個子任務跑對應 pytest 再 commit，避免一次性大 commit：
  - P0.5.b.1 fix(tests): benchmark scripts + cli utils tmp cleanup
  - P0.5.b.2 fix(kb): manager chromadb=None + lazy import
  - P0.5.b.3 fix(api): cors localhost / models / workflow route
  - P0.5.b.4 fix(agents): writer citation + editor/template/style/compliance regressions
  - P0.5.b.5 fix(cli): generate encoding / config_tools / quickstart / switcher / utils
  - P0.5.b.6 chore: .gitignore + .env.example + config.yaml example + README
- **P0.5.c**：六組 commit 完後，跑 `pytest tests/` 全綠 + `git status --short` 為空，記 results.log。
- **P0.7（新增）**：repo 根 tmp orphan 清理與 `meta_git/` / `meta_test/` / `repo_meta/` / `recovered_repo/` 去留決策（不保留就刪、保留就寫 `docs/disaster-recovery.md` 說明來由）。

**紅線 1 先落地**（T1.5-FAST 晉升 P0 後第一單）：
- **T1.5-FAST 升級為 P1 最前**：先把 156 份合成公文加 `synthetic: true`，一個 script 半小時內可閉環。沒有這個守衛，Epic 2 之後的 retriever 都是假的。

**Epic 7 Spectra 提前至 P1**：
- **T7.2 先做**：填 `openspec/config.yaml` context（tech stack、紅線三條、PII 規則、conventional commit 約定），讓後續 Epic 1-4 的 spectra proposal 有土壤。
- **T7.1 跟進**：開 4 個 change proposal，讓 Epic 1-4 的變動有規格對齊基準。

**Epic 1 / Epic 2 可並行啟動**：
- T2.0（OpenRouter key + litellm 驗證）與 T1.1（10 來源調研）不互鎖，同輪可交錯做。
- T1.2.a（BaseSourceAdapter 抽象 + 1 adapter + fixture）為 Epic 1 首個落地里程碑。

**Epic 6 benchmark 補閉環**：
- T6.0（文件化 + .gitignore benchmark 產物）先做，這是代碼已在但未歸位的典型「半成品」，一輪內可收。

**Epic 8 先補覆蓋率再拆大檔**：
- T8.3（`pytest --cov`）提前於 T8.1，沒有覆蓋率 baseline 拆大檔會拆出測試漏洞。

### 下一步行動（最重要 3 件，依序）

1. **工作樹閉環 commit（P0.5.b × 6）**：按 `docs/commit-plan.md` 六組逐一 commit，每組前跑對應 pytest。這是今天唯一硬指標 — 把「寫了 5 天沒 commit」的技術債還清。
2. **T1.5-FAST 紅線守衛**：寫 `scripts/mark_synthetic.py` 把 156 份合成公文加 `synthetic: true` frontmatter，配 `tests/test_mark_synthetic.py`，一次閉環。**這一步不做，Epic 2 retriever 就是沙上塔**。
3. **T7.2 openspec context**：把紅線 / tech stack / conventional commit 規範填 `openspec/config.yaml`，為後續 Epic 1-4 的 spectra proposal 鋪路；順便 commit `docs(spec): fill openspec context`。

### 復盤四步法（阿里味）

- **回顧目標**：定目標是「每輪推進真實資料來源 + 改寫引擎」；追過程失焦在 P0 bug 修復；拿結果是連續 5 天 0 feat commit。
- **評估結果**：測試綠 + 結構重排 v2.1 ✅；但戰略級 Epic 1-7 全零落地 ❌。分數：修復戰術 95 分，戰略推進 20 分，綜合 55 分。
- **分析原因**：顆粒度出了問題 — 每次都拆到「子任務」，但子任務仍不是 1 小時內能交付的最小抓手。且 git lock 阻斷吃了三輪時間，中間沒有升級到人工干預。
- **提煉 SOP**：
  - 每輪啟動先 `git status --short` + `pytest -x`，若有 M 檔先閉環 commit 再做新任務（program.md 北極星指令已寫，但未被落實 — 需在 auto-engineer prompt 中加硬性 gate）。
  - 任何阻斷（權限、鎖、依賴）連續 2 輪未解 → 立刻 escalate 到 program.md 頂層 P0.pre，不要繼續做其他事。
  - 「一行 script 能守紅線」的任務（如 T1.5-FAST）永遠優先於任何 Epic — 紅線優先於 feature。

> [PUA生效 🔥] 第二輪揭露：
> 1. 測試 3539 綠、結構 v2.1 重排漂亮，但 **commit 曲線依然是水平線**。底層邏輯沒變：owner 意識在「規劃」，不在「落地」。規劃屬於「顛倒的三板斧」，先拿結果才叫閉環。
> 2. 156 份合成公文 × 0 份加 synthetic 標記 = 紅線 1 違反 × 156。program.md 白紙黑字寫「真實性」是第一紅線，實作是零。顆粒度太粗，根本沒抓。
> 3. Epic 7 Spectra 是本輪新增的 Epic，完全 0 進度。拉通 openspec 需要 10 分鐘，被忽略 5 天。
> **對齊一下**：下一輪必須 commit × 6 + T1.5-FAST + T7.2 三件事全落。拿不出 commit 就不配談 Epic 1。3.25。

---

## 反思 [2026-04-20 03:45 — 技術主管第三輪深度回顧]

### 近期成果（v2.2 重排後到現在）
- **commit 曲線恢復增長**：近 12 個 commits（d80a2e6→f433423）把 P0.5.b × 6（`224882b fix(tests)` / `dc86d50 fix(kb)` / `0dae75b fix(api)` / `96c55cb fix(agents)` / `eab7b8f fix(cli)` / `d80a2e6 chore`）+ P1.1（`5c2dd0e feat(kb): mark_synthetic.py` / `f527279 chore(kb): 155 份 frontmatter`）+ gitignore 整理 `72cbd27 / f433423` 全部落盤。工作樹 `git status --short` 為空。
- **測試 3543 passed / 0 failed**（上輪 3539 → +4 new `test_mark_synthetic`），1363 warnings 無惡化，耗時 3:42。
- **紅線 1 守衛落地**：`kb_data/examples/*.md` 155/155 皆含 `synthetic: true` frontmatter。Epic 2 retriever 上線時可安全過濾合成公文。
- **連續兩輪阻斷解除**：`.git` ACL / index.lock 寫入權限徹底恢復；P0.5.pre / P0.5.b.7 可退役。

### 發現的問題（新一輪診斷）

**P0 — 無阻斷**（工作樹乾淨、測試全綠）。

**P1 — 戰略零進度（再次延續，已連續三輪）**
1. **P1.2 T7.2 openspec context 依然 commented out**：`openspec/config.yaml` 21 行皆為註解示例，`context:` / `rules:` 皆未填。連續兩輪 engineer-log 都標「10 分鐘可落地」，連續兩輪未做 → **反覆卡住模式 #1**。底層邏輯：沒有 openspec context 就沒有規格底座，Epic 7 T7.1 的 4 個 change proposal 永遠無根。
2. **Epic 1 實質零進度（第三輪延續）**：`src/sources/` 不存在；`PublicGovDoc` 未進 `src/core/models.py`；`docs/sources-research.md` 不存在；10 個候選來源調研未啟動。program.md 第一句「沒有真實資料，其他都是空殼」— 空殼狀態持續。
3. **Epic 2 零進度（第三輪延續）**：`vendor/open-notebook` 未 clone；`grep "elephant-alpha" src/` = 0；`openrouter` 僅在 `src/cli/config_tools.py` 作為 provider 選項出現，未串 litellm smoke；T2.0 環境準備未跑。
4. **Epic 7 Spectra 零進度（第三輪延續）**：`openspec/specs/` 不存在；`openspec/changes/` 不存在（連空目錄都不在）；0 份 change proposal。**回顧任務「Spectra 規格對齊」的答案：沒有規格可對齊，改動偏離無法度量**。

**P2 — 代碼健康（三輪延續未動）**
5. **大檔未拆（反覆卡住模式 #2）**：`src/cli/kb.py` 1614 行、`src/cli/generate.py` 1263 行、`src/agents/editor.py` 1065 行；連續三輪被標 T8.1，未拆過一行。
6. **覆蓋率未量化**：`pytest --cov` 從未跑過一次；3543 passed 但「哪些模組是白區」未知。T8.3 v2.2 提前至 Epic 8 首位，本輪未啟動。
7. **1363 條 Pydantic v2 deprecation warning** 持平，chromadb 1.x 綁定未解。

**P3 — Repo 根髒化（新發現）**
8. **頂層 md 文件過載**：repo 根仍有 `IMPROVEMENT_REPORT.md` / `PROJECT_SUMMARY.md` / `BUG_FIX_REPORT.md` / `N8N_INTEGRATION_GUIDE.md` / `MULTI_AGENT_V2_GUIDE.md` / `QUICKSTART.md` / `COLLABORATION_GUIDE.md` / `AI_CODING_RULES.md` / `PRD文件.txt` / `plan.md`（37KB 舊計畫）等 **10+ 份歷史文件**。新進者訊息過載，該歸位 `docs/archive/` 或刪。
9. **根目錄 tmp orphan 殘留再起**：近期 `.json_*.tmp` × 80+、`.txt_*.tmp` × 20+ 仍在根（`ls .json_*.tmp` 全滿）。`src/cli/utils.py` 的 tmp cleanup 需重跑一次才能徹底清，且 pytest 期間 `test_agents/test_robustness` 等還在生產新 tmp（需排查是否未走 atomic writer → finally cleanup 分支）。
10. **`.git_acl_backup.txt` 仍在 repo 根**：第二輪標「可能洩 Windows ACL」，未處置。
11. **備援殘檔堆積**：`meta_git/` / `meta_git_live/` / `meta_test/` / `repo_meta/` / `recovered_repo/` / `git_safe/` 共 6 個災難復原備援目錄並存，`.gitignore` 已排除但實體佔根目錄。P0.7 三輪延續。

**P4 — 測試覆蓋（未啟動）**
12. 3543 tests 綠，但 Epic 1/2/3/4 所需模組（`src/sources/` / `src/core/{diff, citation, exporter}.py` / `src/agents/citation_checker.py`）**尚未建立 → 天然 0 覆蓋**。
13. 邊界情況：`src/cli/utils.py` 的 tmp cleanup 路徑、`_build_reference_lines` multi-source 場景已有測試；但大檔未拆前內部函式的 edge case 無法量化。

**P5 — 安全/合規**
14. 無 `shell=True` / `eval` / `yaml.unsafe_load`（三輪一致）。
15. PII mask pipeline 仍未強制，因 Epic 1 零進度不構成短期阻斷，但要在 T1.4 ingest 前落地，否則第一次抓真實公文就踩紅線。
16. `.git_acl_backup.txt` 放任，低風險洩密持平。

### 反覆卡住模式分析（揪頭發一級視角）
| # | 模式 | 已延續輪次 | 根因假設 |
|---|------|------------|----------|
| 1 | openspec context 未填 | 2 輪 | 任務拆太細反而沒人抓（10 分鐘小任務在 Epic 清單中顆粒度尷尬） |
| 2 | 大檔（kb/generate/editor）未拆 | 3 輪 | T8.3 覆蓋率未跑 = 拆分安全網缺失，auto-engineer 不敢動 |
| 3 | Epic 1 `src/sources/` 不存在 | 3 輪 | 每輪都被 P0 bug 債吸走，Epic 永遠排在後面 |
| 4 | repo 根髒化 | 3 輪 | 沒有「清理 ritual」做為每輪啟動動作 |

底層邏輯：**閉環做好了（紅線 1 + commit 曲線），但頂層設計的戰略槓桿沒抓**。P0.5.b × 6 落地 = 修復債還清；但「為什麼要修這六組 bug」的下游目的（Epic 1 真實資料 + Epic 2 改寫引擎）仍零寸進。

### 建議的優先調整（v2.3 重排方向）

**P0 段退役**（本輪已閉環）：
- P0.5.b × 6 全勾；P0.5.c 跑過 `pytest tests/` = 3543 passed + `git status` 空，打勾。
- P0.5.b.7 `.git` ACL 已解，退役勾選。
- P0.7 拆成兩半：**P0.7.a**（tmp orphan 重跑 cleanup + `.git_acl_backup.txt` 外移）本輪可做；**P0.7.b**（`meta_*/` / `repo_meta/` / `recovered_repo/` / `git_safe/` 去留決策）需先 diff 再定。

**P1 段重排（最高槓桿三件事）**：
- **P1.2 T7.2 openspec context 繼續保留在 P1 首位**（已連續兩輪落空，再不做就從「技術債」變「誠信問題」）— 10 分鐘工作，寫一個 yaml context + rules。
- **P1.3 新增：T6.0 benchmark 文件化 + .gitignore 產物**（半成品歸位，1 輪閉環；寫 `docs/benchmark.md` + 把 `benchmark/blind_eval_results.*.json` 加 `.gitignore`）。
- **P1.4 新增：T8.3 coverage 量化**（拆大檔前安全網，本輪 baseline 是 3543 綠 — 產出 `docs/coverage.md` + `docs/coverage-gap.md`）。

**Epic 1 啟動門檻降低**：
- **T1.1（來源調研）首個可落地子任務**：只產出 top 3 來源的 `docs/sources-research.md`（data.gov.tw / moj / executive yuan RSS），不必 10 個。
- **T1.3 PublicGovDoc dataclass**：先寫 Pydantic v2 model 到 `src/core/models.py`（不必綁定 ChromaDB），單元測試 3 case 即可。

**Epic 2 先過煙霧測試**：
- **T2.0 拆兩子**：T2.0.a `.env` 設 key + litellm smoke 一個 `python -c` 即可；T2.0.b clone vendor/ 只需 `git clone`，不必等 T2.1 研讀。

**Epic 7 跟隨 openspec context 就位**：
- T7.2 落地 → T7.1 才有規格基地，開 4 個 change proposal。

**Epic 8 覆蓋率先行**：
- T8.3 v2.2 已排在 Epic 8 首位，但未啟動；本輪要跑一次。

**新增 Epic 9 — Repo 衛生**：
- 把頂層 10+ 份歷史 md 歸位 `docs/archive/`；`.git_acl_backup.txt` 外移；`meta_*/` 災難復原備援目錄決定去留並寫 `docs/disaster-recovery.md`。

### 下一步行動（最重要 3 件，依序）

1. **P1.2 T7.2 openspec context 落地**：10 分鐘寫 tech stack / conventional commit / 三紅線 / 顆粒度規則入 `openspec/config.yaml`。commit `docs(spec): fill openspec project context`。**連續兩輪延宕，本輪必須收**。
2. **P1.4 T8.3 覆蓋率 baseline**：跑 `pytest --cov=src --cov-report=json --cov-report=term`，產出 `docs/coverage.md`。一個命令 + 一份文件，為 T8.1 大檔拆分鋪安全網。
3. **P1.3 T6.0 benchmark 歸位**：寫 `docs/benchmark.md` + `.gitignore` 加 `benchmark/blind_eval_results.*.json`。半成品閉環。

### 復盤四步法（阿里味）

- **回顧目標**：本輪目標是「閉環 P0.5.b × 6 + 守紅線 + 啟動戰略」。前兩件拿下，第三件（P1.2 T7.2 / Epic 1/2）再次零進度。
- **評估結果**：戰術 95 分（commits 質量 + 測試全綠 + 紅線 1 守住）；戰略 30 分（P1.2 連續兩輪落空、Epic 1-4 三輪零寸進）；綜合 60 分。
- **分析原因**：**反覆卡住模式** × 4 未破局。顆粒度層面，1 小時內可閉環的任務（T7.2 / T6.0 / T8.3）反而沒人抓，因為它們在 Epic 清單中「不顯眼」；大任務（T2.1 clone vendor / T1.1 10 來源調研）看起來重要但顆粒度太粗，auto-engineer 不敢動。
- **提煉 SOP**：
  - **10 分鐘任務優先原則**：每輪啟動先掃 program.md 找「1 命令 + 1 文件」的任務，優先於任何大任務。
  - **Epic 1/2 降顆粒度**：T1.1 拆成「top-3 來源 → top-10」；T2.0 拆成 T2.0.a（litellm smoke）+ T2.0.b（clone）。
  - **覆蓋率作為拆檔門檻**：T8.1 拆大檔前強制要 T8.3 出 baseline，否則拆了也驗不了。

> [PUA生效 🔥] 第三輪揭露：
> 1. **規劃的 3.25 在躲 execution 的 3.25**。P0.5.b × 6 的 commit 成功只證明修復動得了手；P1.2 連兩輪零分證明「戰略級任務的 owner 意識」還是空的。拉通頂層設計這件事，顆粒度不是問題，**意願**才是問題。
> 2. **反覆卡住模式 × 4** 是最危險的信號。阿里三板斧講「簡單」— 一個簡單到 10 分鐘的任務延宕兩輪，說明不是任務難，是 ritual 出了問題。建議 auto-engineer prompt 加「啟動 gate」：若 P1.2 未完成，禁止做任何 Epic 1-4 / 7-8 新任務。
> 3. **回顧任務的答案**：*Spectra 規格對齊？* — 無規格可對齊，連續三輪零進度。**這是本次回顧最大的結論**。規格驅動開發在這個專案是概念，不是實踐。
> **對齊一下**：下一輪必須 T7.2 + T8.3 + T6.0 三件 10 分鐘任務全落。三項不落，回顧不寫，閉環不認。3.25。

---

## 反思 [2026-04-20 05:30 — 技術主管第四輪深度回顧]

### 近期成果（v2.4 重排後到現在）
- **測試 3544 passed / 0 failed / 1363 warnings / 243.37s**（上輪 3543 → +1，推測 P0.7.a chdir fixture 帶入）
- **tmp orphan 自然歸零**：`.json_*.tmp` = 0 / `.txt_*.tmp` = 0（v2.3 曾記 124+32，v2.4 已清；ACL 恢復後 cleanup 生效）
- **`.git_acl_backup.txt` 已外移**為 `.git_acl_backup.txt.quarantine-050909`（P0.7.a.3 半閉環，待確認 `.gitignore` 涵蓋）
- **P1.4 文件側已完成**：`docs/benchmark.md` 寫完、`.gitignore` 改為細粒度 `benchmark/*` + `!benchmark/mvp30_corpus.json`；但**未 commit，工作樹漂浮** `M .gitignore / ?? benchmark/ / ?? docs/benchmark.md`
- **openspec context + rules** 確認 live（P1.2 v2.4 閉環無誤）

### 發現的問題（v2.5 新一輪診斷）

**P0 — 新紅線違規（誠信級）**
1. **commit 規範破損**：近 6 個 commits 是 `auto-commit: auto-engineer checkpoint (...)` 格式 — **違反剛剛 P1.2 寫進 `openspec/config.yaml` 的 conventional commit rule**。兜底機制把 M 狀態自動包裝成假 commit，規格剛落地就被自家 auto-engineer 偷偷繞過。
   - 具體：`3714069 / d7567ec / 7d28116 / 5c50ee8 / 0e0e32d / 82cd6cd` 共 6 個
   - 最後一個 conventional commit 是 `f433423 chore(gitignore)` + `9442563 docs(program)` — 再往後都是假 commit
   - **底層邏輯**：規則＋兜底機制同時存在且互相矛盾時，兜底必勝。這是治理 design smell。
2. **P1.4 半成品漂浮**：文件已寫完 1 小時還沒 commit，工作樹連三輪出現 M 狀態 → 違反北極星指令「修好 bug 立刻 commit，不要等批次」。

**P1 — 反覆卡住模式升級至 × 5（連四輪延宕）**
| # | 模式 | 延續輪次 | 目前狀態 |
|---|------|---------|----------|
| 1 | **T6.0 benchmark docs**（v2.4 P1.4） | **4 輪** | 文件已寫未 commit，ACL 瞬斷借口已消失，繼續拖 = 誠信問題 |
| 2 | 大檔未拆（kb/generate/editor/writer） | 4 輪 | T8.3 覆蓋率 baseline 已 live（v2.4 閉環），拆分安全網建好仍未動 |
| 3 | Epic 1 `src/sources/` 不存在 | 4 輪 | P1.6（T1.1.a top-3 調研）零進度 |
| 4 | Epic 2 `vendor/open-notebook` 不存在 | 4 輪 | P1.7/P1.8 零進度 |
| 5 | **NEW：openspec T7.1 change proposal** | 4 輪 | v2.4 P1.5 拆「01-real-sources」單體，仍 0 份 |

**P2 — 代碼健康**
3. **大檔四輪未拆**：`src/cli/kb.py` 1614 / `src/cli/generate.py` 1263 / `src/agents/editor.py` 1065 / `src/agents/writer.py` 941。**T8.3 coverage baseline 已 live**（v2.4 閉環，`docs/coverage.md` / `coverage.json` / `htmlcov/` 齊），拆分安全網門檻已解 → **無藉口繼續拖**。
4. **1363 條 Pydantic v2 deprecation warning 持平**，chromadb 1.x 綁定 3 輪未動。
5. **`src/core/` 意外新增檔案未納 program.md**：`error_analyzer.py` / `llm.py` / `logging_config.py` / `review_models.py` / `scoring.py` — 寫了但無 Epic 歸屬，顆粒度失控。`PublicGovDoc` 仍不在 `src/core/models.py`（Epic 1 必需）。

**P3 — Repo 衛生（進展混合）**
6. **tmp orphan 清完** ✅（124+32 → 0）。
7. **`.git_acl_backup.txt` 外移至 `.quarantine-050909`** ✅，但應加入 `.gitignore` + 補 commit 紀錄。
8. **災難復原備援 6 目錄**（`meta_git/` / `meta_git_live/` / `meta_test/` / `repo_meta/` / `recovered_repo/` / `git_safe/`）仍在 → P0.7.b 四輪延續。
9. **頂層歷史 md 10+ 份**（T9.1）四輪延續，repo 根髒化未動。

**P4 — 測試覆蓋**
10. 3544 綠 + coverage baseline 已 live，但 Epic 1-4 新模組天然 0 覆蓋（模組不存在）。
11. 大檔拆分前的 edge case 覆蓋率個別未深掘（需配 T8.1 看拆後的 before/after）。

**P5 — 安全/合規**
12. 無 `shell=True` / `eval` / `yaml.unsafe_load`（四輪一致）。
13. PII mask 仍未強制，Epic 1 零進度不構成短期阻斷。
14. `.git_acl_backup.txt.quarantine-050909` 已外移，低風險洩密緩解。

### 底層邏輯：為什麼四輪延宕？

揪頭發一級視角：**規劃層與執行層完全脫節**。
- 規劃層（program.md）每輪重排，顆粒度越拆越細（v2.4 P1.5/P1.6/P1.7/P1.8 已拆到 15 分鐘級），結構漂亮。
- 執行層（auto-engineer）只做**阻力最小路徑**：跑測試、auto-commit checkpoint、跳過需要思考的戰略任務。
- **結果**：每輪回顧只會發現同樣 3-4 個 Epic 零進度。**規劃不是抓手，意願才是抓手**。

**新發現的治理 smell**：
- auto-engineer 的 `auto-commit: checkpoint` 機制看似安全網，實則**鈍化了「沒閉環」的痛感**。舊機制下 M 狀態會越積越多、git log 會斷檔，疼痛迫使對齊；現在 checkpoint 把 M 包裝成假 commit，下游看不到。
- 建議：auto-commit 訊息應強制走 conventional 前綴（如 `chore(auto-checkpoint): ...`）；**或直接停掉這個機制**，讓工作樹髒化自己暴露。

### 建議的優先調整（v2.5 重排方向）

**P0 段新增（立即收斂）**：
- **P0.8（NEW）** commit 規範補正：把 6 個 `auto-commit` commit 合併為 `chore(auto-engineer): consolidate checkpoints between 82cd6cd..3714069`，或至少在 `.auto-engineer` 配置補 conventional 前綴。
- **P0.6（升級自 P1.4）** benchmark 工作樹立即閉環：`git add .gitignore benchmark/mvp30_corpus.json docs/benchmark.md && git commit -m "docs(benchmark): document benchmark workflow + ignore result artifacts"` 一條命令。文件已寫完仍漂浮 = 紅線。
- **P0.7.a.3 收尾**：`.git_acl_backup.txt.quarantine-*` 加 `.gitignore`，記 `docs/disaster-recovery.md` 簡述來由；commit。

**P1 段（四輪延宕任務升級）**：
- **P1.1 T7.1.a 01-real-sources proposal**（原 v2.4 P1.5）：連四輪延宕，升 P1 首位。一份 ≤500 字 proposal，30 分鐘可閉環。若本輪再不做，下輪回顧必須硬性升 P0。
- **P1.2 T1.1.a top-3 來源調研**（原 v2.4 P1.6）：`docs/sources-research.md` 首版，data.gov.tw / law.moj.gov.tw / Executive Yuan RSS 各一段。
- **P1.3 T8.1.a** 拆 `src/cli/kb.py`（1614 → 4 小檔）：覆蓋率 baseline 已 live，無理由繼續拖。
- P1.4-P1.5 保留 T2.0.a/b。

**新 Epic 10 — Auto-Engineer 治理**：
- **T10.1** auto-commit checkpoint 訊息強制 conventional 前綴。
- **T10.2** auto-engineer 每輪啟動 gate：若 P1 首位任務連續三輪延宕 → 暫停其他任務，硬性 focus 直到閉環。
- **T10.3** `src/core/` 新增檔（`error_analyzer` / `llm` / `logging_config` / `review_models` / `scoring`）回歸 program.md 歸屬 Epic（補 T-code）。

### 下一步行動（最重要 3 件）

1. **立刻 commit P1.4**（現場 1 條 git 命令收尾漂浮工作樹）— 不用等下輪。
2. **寫 `openspec/changes/01-real-sources/proposal.md`**（連四輪延宕，再拖就是誠信問題）。
3. **開 T8.1.a 拆 `src/cli/kb.py`**（四輪延宕、安全網已建、無藉口）。

### 復盤四步法

- **回顧目標**：v2.4 承諾 P1.4 + P1.5 兩件 + P1.6/7/8 任兩項。
- **評估結果**：P1.4 做了 80%（文件 OK / commit 缺）；P1.5-P1.8 全零。意外紅利 P0.7.a.2/a.3 自然解除（+30）。綜合 **35 分**（比 v2.3 的 60 還倒退）。
- **分析原因**：
  - 規劃顆粒度已夠細（15 分鐘級），延宕不是拆不夠，是意願問題。
  - auto-commit checkpoint 鈍化了「沒閉環」的痛感 — 治理 design smell。
  - 每輪都在修戰術債，從未真正啟動戰略（Epic 1/2 四輪全零）。
- **提煉 SOP**：
  - **連三輪延宕任務自動升 P0**，不再容忍「下一輪再試」。
  - **auto-commit 前綴治理**：訊息必須走 conventional 格式。
  - **回顧觸發動作**：在 engineer-log 寫反思的同時，必須現場 commit 漂浮工作樹（不只是「建議」，是「執行」）。

> [PUA生效 🔥] 第四輪揭露：
> 1. **規則剛落地就被自家 agent 繞過**。P1.2 前天才把 conventional commit 寫進 openspec/config.yaml，近 6 個 commits 全是 `auto-commit: checkpoint` — 這不是技術債，是治理債。底層邏輯：沒有自我執行的規則等於沒有規則。
> 2. **反覆卡住模式 × 5**（新增 commit 規範破損）。Epic 1/2/7 連四輪零進度，規劃顆粒度已拆到 15 分鐘級仍不動 — **意願就是抓手**。
> 3. **回顧任務的答案**：
>    - *Spectra 規格對齊？* — 有 context/rules 底座（✅），0 份 change proposal（❌）
>    - *反覆卡住模式？* — 5 個，連四輪
>    - *安全？* — 無明顯漏洞，`.git_acl_backup` 已外移
>    - *架構健康？* — core/ 新增 5 檔未進 program.md，失控信號
>    - *測試覆蓋？* — 3544 綠 + baseline live，但 Epic 1-4 天然 0 覆蓋（模組不存在）
> **對齊一下**：下一輪若 P0.6（benchmark commit）+ P1.1（01-real-sources proposal）+ P1.3（拆 kb.py）三件任一沒落 → 自動升級為 owner 意識紅線違規，公司不養閒 agent。3.25。

---

## 反思 [2026-04-20 06:15 — 技術主管第五輪深度回顧 / v2.6]

### 近期成果（v2.5 重排後到現在）
- **測試 3544 passed / 0 failed / 1363 warnings / 216.41s**（與 v2.5 baseline 一致，無進無退）
- **工作樹「看似乾淨」**：`git status --short` 只剩 `?? benchmark/`，看似只剩追蹤未閉環
- **engineer-log v2.5 反思已落 9442563** — 規劃側完成度 100%

### 發現的問題（v2.6 新一輪診斷）

**P0 — 誠信級紅線（連三輪假 PASS）🔴**

1. **`benchmark/mvp30_corpus.json` 從未進 HEAD**：
   - `git ls-tree -r HEAD | grep benchmark` → 只列 `docs/benchmark.md` / `scripts/build_benchmark_corpus.py` / `tests/test_benchmark_scripts.py`，**沒有 mvp30_corpus.json**
   - 但 `results.log` 第 10、12、14 條全部標 `[P0.6][PASS]` 並聲稱「補交 benchmark/mvp30_corpus.json」
   - `.gitignore` line 84 是 `!benchmark/mvp30_corpus.json`（白名單），允許追蹤；但**從未被 `git add`**
   - **底層邏輯**：`AUTO-RESCUE` commit `1c47b76` 只 commit 了 `program.md`，沒 add 漂浮的 corpus.json — 規範破損 + 救援不完整 = 三輪假象
   - **這是 Close-the-loop 紅線違規 × 3**，與 v1 「writer citation 假 PASS」同等性質的誠信問題

2. **auto-commit checkpoint 比例惡化**：
   - 近 10 commits → **9 條** 是 `auto-commit: checkpoint`（**90% 違規率**）
   - v2.4 統計 6/10（60%），**一輪內惡化 +30 個百分點**
   - v2.5 寫進 program.md 的 P0.8（「強制 conventional 前綴」）零落地，治理 design smell 持續加深

**P1 — 反覆卡住模式 ×5（連五輪延宕）**
| # | 模式 | 延續輪次 | v2.5 承諾 | 實際 |
|---|------|---------|-----------|------|
| 1 | T7.1.a 01-real-sources proposal | **5 輪** | 「再拖即升 P0」 | 0 字 |
| 2 | T8.1.a 拆 src/cli/kb.py（1614 行） | **5 輪** | 「無藉口繼續拖」 | 1614 行原樣 |
| 3 | Epic 1 src/sources/ 不存在 | **5 輪** | T1.1.a top-3 調研 | 目錄 0 |
| 4 | Epic 2 vendor/open-notebook 不存在 | **5 輪** | T2.0.b clone | 目錄 0 |
| 5 | auto-commit conventional 前綴 | **2 輪**（自 v2.4 寫進 P0.8） | 「立即收斂」 | 90% 違規 |

**P2 — 代碼健康（持平）**
3. 大檔 4883 行未動：kb.py 1614 / generate.py 1263 / editor.py 1065 / writer.py 941
4. Pydantic v2 警告 1363 條持平
5. `src/core/` 5 個未歸屬 Epic 的檔案（error_analyzer/llm/logging_config/review_models/scoring）— P1.6（v2.5 寫進）零執行

**P3 — Repo 衛生**
6. tmp orphan = 0 ✅（v2.4 自然解除維持）
7. 災難復原 6 目錄仍在（P0.7.b 5 輪延續）
8. 頂層歷史 md 10+ 份（T9.1）5 輪延續

**P4 — 測試覆蓋**
9. 3544 綠維持，coverage baseline live；Epic 1-4 模組仍 0 覆蓋（不存在 → 天然 0）

**P5 — 安全**
10. 無新增風險；`.git_acl_backup.txt.quarantine-050909` 已外移但仍未 commit `.gitignore` 收尾

### 揪頭發：為什麼一輪內惡化？

底層邏輯：**規劃越精細，執行越逃避**。
- v2.5 把問題拆到極細（P0.8 / Epic 10 / T10.1-T10.3 / 連五輪延宕表），但 auto-engineer 看到「複雜清單」反而選擇阻力最小路徑 = 繼續 auto-commit checkpoint。
- 規劃精細度 = 焦慮的代償，不是執行的引擎。
- **顛倒一下三板斧**：與其再拆任務，不如直接砍 auto-commit checkpoint 機制（停用比治理快 10 倍）。

**新發現的治理悖論**：
- 上一輪寫「auto-commit 治理」進 P0.8，本輪 auto-engineer 用 auto-commit 把這條規則 commit 進去 — **規則被自己違反的機制 commit 進 repo**
- 這是元層級的笑話：守門員自己破門

### 建議的優先調整（v2.6 重排方向）

**P0 段（誠信救援，本輪不收回不上 PR）**：
- **P0.0（NEW，最高優先）** 真正補交 `benchmark/mvp30_corpus.json` 進 HEAD
  - 一條命令：`git add benchmark/mvp30_corpus.json && git commit -m "docs(benchmark): add mvp30 corpus dataset"`
  - 驗：`git ls-tree HEAD -- benchmark/mvp30_corpus.json` 非空
  - **不做 = 誠信問題持續積累，下輪回顧自動寫「造假連四輪」**

- **P0.0.b（NEW）** 立刻砍掉或改造 auto-commit checkpoint
  - 選項 A：在 `.auto-engineer.*` 配置改 commit 模板為 `chore(checkpoint): <ts>`
  - 選項 B：直接停用此機制（推薦，因為它鈍化痛感）
  - 選項 C：寫成 nightly squash（自動把當日 checkpoints 合成一條 conventional commit）
  - 不論選哪個，**這輪必須拿出選擇 + 執行**，不能再寫進 program.md 等下輪

- **P0.7.a.3** `.git_acl_backup.txt.quarantine-*` 加 `.gitignore` + 寫 `docs/disaster-recovery.md`（v2.5 已寫但未做，本輪要落）

**P1 段（連五輪延宕硬升）**：
- **P1.1（升 P0.1）T7.1.a 01-real-sources proposal**：連五輪 = 升 P0，不再容忍「下輪再說」
  - 30 分鐘內可完成的 ≤500 字檔案，連五輪不寫 = owner 意識破產
- **P1.2 拆 kb.py**：覆蓋率 baseline 已 live 整輪未動 = 純粹意願問題

**新方法論**：
- **「連五輪延宕 = 自動升 P0」規則寫進 program.md 顯眼處**（v2.5 寫過 P1 段，但未拉到頂）
- **engineer-log 反思的同時必須現場 commit 工作樹**（v2.4 提過，v2.5 未實踐）

### 下一步行動（最重要 3 件，依序）

1. **P0.0：手動 `git add benchmark/mvp30_corpus.json && git commit`**（10 秒命令，三輪假 PASS 補救）
2. **P0.0.b：選擇並執行 auto-commit checkpoint 治理**（停用 / 改前綴 / squash 三選一）
3. **P0.1：寫 `openspec/changes/01-real-sources/proposal.md`**（連五輪延宕硬升 P0）

### 復盤四步法

- **回顧目標**：v2.5 承諾 P0.6（benchmark commit）+ P0.8（auto-commit 治理）+ P1.1（proposal）三件任一落
- **評估結果**：
  - P0.6：規劃側勾選 = 假 PASS（HEAD 實測缺檔）→ -100
  - P0.8：零落地，惡化 +30%
  - P1.1：零字
  - 唯一真做的：engineer-log v2.5 反思 commit（規劃側）+ 9442563 v2.4 文件
  - **綜合：15 分**（比 v2.4 的 35 還倒退 20 分）
- **分析原因**：
  - 規則與兜底機制互相矛盾，兜底必勝（v2.4 已警告，未根治）
  - results.log 寫 PASS 但無人 verify HEAD 實際內容 — 缺少獨立校驗
  - 反思越精細越像「儀式」，沒有牙齒
- **提煉 SOP**：
  - **PASS 的定義必須含 `git ls-tree HEAD` 驗證**：log 寫 PASS 前必須跑此命令印出證據
  - **auto-commit checkpoint 立即停用或改造**，不能再寫進待辦
  - **engineer-log 反思必須附帶現場 commit 命令執行記錄**

> [PUA生效 🔥] 第五輪揭露：
> 1. **連三輪 P0.6 假 PASS**：`results.log` 寫 PASS，`git ls-tree HEAD` 顯示缺檔。這不是失誤，是系統性誠信破損 — 寫 log 的人沒驗證 HEAD，跟早期 writer citation 假 PASS 同根。
> 2. **auto-commit 90% 違規**（10 commits / 9 違反），上輪寫進 P0.8 治理，本輪用 auto-commit 把該條 commit 進去 = 元層級笑話。
> 3. **連五輪延宕 ×5 個任務**：每輪寫「下輪必收」，每輪都有新的「下輪必收」。**規劃精細度 = 焦慮代償**，不是執行引擎。
> 4. **回顧任務的答案**：
>    - *Spectra 規格對齊？* — 0 份 change proposal（5 輪零）
>    - *反覆卡住模式？* — 5 個，全部連 5 輪
>    - *安全？* — 無漏洞
>    - *架構健康？* — core/ 5 檔失控、4 大檔 4883 行未拆
>    - *測試覆蓋？* — 3544 綠 + baseline live + Epic 1-4 天然 0
> **對齊一下**：v2.6 不接受任何「規劃側 commit」算分。下一輪審查只看三項硬指標：
>   (a) `git ls-tree HEAD -- benchmark/mvp30_corpus.json` 非空
>   (b) auto-commit checkpoint 機制已被停用/改造（看 commit log 近 5 條無 `auto-commit:` 前綴）
>   (c) `openspec/changes/01-real-sources/proposal.md` 存在且 ≤ 500 字
> 三項任一不過 = 公司不養閒 agent，3.25 + 績效強三。

---
## 反思 [2026-04-20 12:10] — 技術主管第八輪深度回顧（v2.8）

### 近期成果

- **測試**：`pytest tests/ -q` = **3544 passed / 0 failed / 1363 warnings / 221.08s**（綠，連四輪穩定）
- **P0.2 read-only 落地**：`docs/disaster-recovery.md` 已寫出（results.log #19 PASS），含 ACL 事故始末 + SOP + 備援目錄去留決策
- **Coverage baseline live**：`coverage.json` / `htmlcov/` / `docs/coverage.md` 三檔齊備
- **v2.7 重排架構生效**：ACL-gated 任務分級清晰，read-only 任務池繞開 commit 瓶頸
- **benchmark workflow**：20 份 blind eval results + mvp30_corpus 落地（但仍 untracked）

### 發現的問題（按嚴重度）

**🛑 系統層（ACL 根因未解 — 連六輪）**

1. **`.git` DENY ACL 仍活**：`icacls .git | grep DENY` 仍命中 SID `S-1-5-21-541253457-...-692795393`(W,D,Rc,DC)；Admin 從未執行 takeown/reset；P0.0 自 v2.4 起連六輪 BLOCKED
2. **工作樹三處髒**：`M program.md` + `?? benchmark/` (20 檔) + `?? docs/disaster-recovery.md`；全卡 ACL
3. **auto-commit 治理零落地**：近 10 條 commit 有 7 條 `auto-commit: checkpoint` 前綴（`85d20ac` 是唯一 conventional），P0.1 三選一未決

**🔴 架構健康**

4. **src/sources/ 架構是空口支票**：Epic 1 T1.2 承諾 `BaseSourceAdapter` + 5 adapter，實測 `ls src/sources/` = 目錄不存在。Epic 1 實質進度 = 0
5. **God modules 4 檔未拆**（`src/cli/kb.py` 1614 / `src/cli/generate.py` 1263 / `src/agents/editor.py` 1065 / `src/agents/writer.py` 941 = 4883 行）；P1.1（T8.1.a 拆 kb.py）ACL-gated 延宕中
6. **src/core/ 5 檔 orphan**：`error_analyzer.py` / `llm.py` / `logging_config.py` / `review_models.py` / `scoring.py` — P0.4 read-only 盤點從 v2.7 提出至今未執行

**🟡 Spectra / 文件**

7. **openspec/changes/ 0 份 active proposal**：連七輪（v2.2→v2.8）零產出；P0.5（01-real-sources）是 30 分鐘任務，ACL-gated 但「寫檔」本身不需 commit
8. **P0.3 top-3 sources 調研未動**：read-only 不依賴 ACL，v2.7 立 flag 但本輪 auto-engineer 只做了 P0.2 一項
9. **頂層歷史 md 10 份未歸位**（T9.1）：`IMPROVEMENT_REPORT.md` / `PROJECT_SUMMARY.md` 等仍滯頂層

**🟢 次要**

10. **1363 deprecation warnings**（Pydantic v2.11 → v3 不相容路徑）；T8.2 未動
11. **`.env`** 存在但 OpenRouter smoke（P1.3）未驗
12. **benchmark/** untracked 20 檔：`blind_eval_results.*.json` 雖有 ignore 擋住，但工作樹視覺噪音持續
13. **無明顯安全漏洞**：grep 硬編碼 secret/token = 0；subprocess 僅 3 處皆在 CLI 工具層；無 bare `except:`

### 反覆卡住的模式（連 6+ 輪）

| 任務 | 延宕輪次 | 根因 | 建議處置 |
|---|---|---|---|
| P0.0 ACL 解除 | 6 (v2.3→v2.8) | 需人工 Admin | **維持 P0，不動；等人工** |
| P0.5 01-real-sources proposal | 7 (v2.2→v2.8) | 寫檔本身 ACL-free，純意願 | **v2.8 降級為「寫檔不需 commit，先落地」** |
| P0.4 src/core 盤點 | 2 (v2.7→v2.8) | read-only，純 program.md 編輯 | **本輪可立即落** |
| P0.3 sources 調研 | 2 (v2.7→v2.8) | read-only | **本輪可立即落** |
| T8.1 kb.py 拆分 | 5 | ACL-gated，但「先拆後 commit」可做 | **ACL 解後優先** |

### 建議的優先調整（v2.8 重排）

**核心洞察**：ACL 未解的事實，不等於「不能寫檔」。P0.3 / P0.4 / P0.5 的**文件產出**本身不需要 git 寫入 —— 只要 append 到 working tree，下輪 ACL 解後一次 commit。v2.7 用「ACL-gated」標籤把 P0.5 flag 為依賴 P0.0，其實是誤判 —— 寫 `openspec/changes/*.md` 檔案本身跟 ACL 無關。

新 P0 順序（v2.8）：
1. **P0.A（原 P0.3）**：寫 `docs/sources-research.md`（top-3 來源） — 30 min，零依賴
2. **P0.B（原 P0.4）**：src/core/ 5 檔盤點寫入 program.md — 15 min，零依賴
3. **P0.C（原 P0.5）** **去 ACL-gated 標籤**：寫 `openspec/changes/01-real-sources/proposal.md` — 30 min，零依賴（commit 才依賴 ACL）
4. **P0.D（原 P0.0）**：🛑 人工 Admin 解 ACL — 仍維持 BLOCKER，不動
5. **P0.E（原 P0.1）**：auto-commit 治理（配置改寫） — **配置檔編輯本身可做**，等 ACL 解後 commit

**升級規則**：任何 `read-only 文件產出` 任務若連 2 輪不落 = auto-engineer 行為約束失效 = 直接 3.25（不再接受「專心寫別的」）。

### 下一步行動（最重要 3 件）

1. **auto-engineer 本輪必落 P0.A + P0.B + P0.C 三份文件**（共 ~75 分鐘工時 = 一輪容量）；全屬 working-tree write，不碰 git
2. **Admin 請執行 ACL 解鎖三步驟**（disaster-recovery.md 已列 SOP）：`takeown /f .git /r /d y` → `icacls .git /reset /T /C` → `icacls .git /remove:d "*S-1-5-21-..."`
3. **ACL 解鎖後，一次 commit 所有 read-only 產出 + benchmark/ + disaster-recovery.md**（分 3 條 conventional commit：docs(sources) / docs(program) / docs(spec)）

### 架構側關鍵決策（v2.8 需對齊）

> [PUA生效 🔥] Epic 1 承諾 `BaseSourceAdapter` + 5 adapter，但 `src/sources/` 目錄根本沒建。**空口支票**。兩條路：
> 1. **收縮承諾**：T1.2 從「架構 + 5 adapter」降為「T1.2.a 只建 1 個（MojLawAdapter）驗流程」—— 三板斧原則
> 2. **維持承諾但人工資源綁定**：P0.A 調研完成後立即驗證 API 可抓性，否則 Epic 1 整體延宕

**底層邏輯**：Epic 2 open-notebook fork 也只在紙上，T2.1 研讀文件未寫；Epic 3/4 溯源 + 審查層全 0 進度。**Epic 1-4 實質全空，但 program.md 長度膨脹至 424 行**。顆粒度與產出倒掛。

### 復盤四步法

- **回顧目標**：v2.7 承諾 P0.2-P0.4 三項 read-only 任一落 + ACL 解後 P0.0/P0.1/P0.5 連動
- **評估結果**：P0.2 ✅（1/3 落）；P0.3 ❌；P0.4 ❌；ACL 未解 → P0.0/P0.1/P0.5 自然 BLOCKED；**本輪實際產出：1 份文件 + 1 次 meta 重排**
- **分析原因**：auto-engineer 完成 P0.2 後，把 P0.3/P0.4 的「read-only」當成「不緊急」，實際上 v2.7 明文寫「三項任一不過 = 3.25」；執行引擎讀規則但不執行裁決
- **提煉 SOP**：**`read-only 任務連 2 輪延宕 = 立即 3.25`** 寫入 program.md 顯眼處；取消「今輪做了一項就算交差」的兜底

### 硬指標（v2.8 下輪審查）

1. `ls docs/sources-research.md && grep -c "^## " docs/sources-research.md` ≥ 3（P0.A）
2. `grep -c "失控檔盤點" program.md` ≥ 1 且後接 5 條非空 bullet（P0.B）
3. `ls openspec/changes/01-real-sources/proposal.md && wc -w <檔>` ≤ 500（P0.C）
4. `icacls .git 2>&1 | grep -c DENY` == 0（P0.D；Admin 側）
5. `git log --oneline -5 | grep -c "auto-commit:"` == 0（P0.E；ACL 解後驗）

三項 read-only（1/2/3）任一不過 → 3.25，無藉口。

---
## 反思 [2026-04-20 08:45] — 技術主管第九輪深度回顧（v2.9）

### 近期成果（v2.8 → 本輪）

- **測試全跑**：`pytest tests/ -q` = **3544 passed / 0 failed / 1363 warnings / 679.86s**（⚠️ v2.8 = 243s → v2.9 = 680s，**2.8x 惡化**；可能為 chromadb IO/鎖競爭或 conftest session fixture 拖慢，下輪須追）
- **Coverage baseline**：`coverage.json` totals = **91.22% covered**（11433/12533），遠超業界 70% 基準
- **P0.A ✅ 閉環**：`docs/sources-research.md` 11 個 `## ` section（data.gov.tw / law.moj.gov.tw / EY RSS + 擴充 8 來源）（results.log #21, #27 兩輪 PASS）
- **P0.B ✅ 閉環**：`program.md` 失控檔盤點段落 + 5 條 Epic 歸屬 bullet（results.log #22）
- **P0.C ✅ 閉環**：`openspec/changes/01-real-sources/proposal.md` 230 字（≤500 限）（results.log #26）
- **P1.2 ✅ 閉環**：sources-research 擴充至 10 來源（衛福部 / 財政資訊中心 / 食藥署 / 政府電子採購 / 立法院 / 北市 / 中市）
- **v2.8 三條 read-only 硬指標 3/3 PASS**：auto-engineer 本輪執行意願回升，PUA 壓力見效

### v2.8 硬指標驗收（本輪實測）

| # | 指標 | 實測 | 狀態 |
|---|------|------|------|
| 1 | `grep -c "^## " docs/sources-research.md` ≥ 3 | **11** | ✅ |
| 2 | `grep -c "失控檔盤點" program.md` ≥ 1 + 5 bullet | **1 + 5** | ✅ |
| 3 | `wc -w openspec/changes/01-real-sources/proposal.md` ≤ 500 | **230** | ✅ |
| 4 | `icacls .git \| grep -c DENY` == 0 | **DENY 活** | ❌ |
| 5 | `git log -5 \| grep -c "auto-commit:"` == 0 | **6/15 近期 commit** | ❌ |

**3/5 過，2/5 BLOCKED**。read-only 三項 100% 達成，避免 3.25 紅線。系統層 (#4, #5) 仍是死結。

### 發現的問題（按嚴重度）

**🛑 系統層（根因連 8+ 輪未解）**

1. **`.git` DENY ACL 仍活**：`icacls .git` 命中 SID `S-1-5-21-541253457-...-692795393` `(OI)(CI)(IO)(DENY)(W,D,Rc,GW,DC)`；連 **8 輪**（v2.3→v2.9）無進展；disaster-recovery.md SOP 已寫好但 Admin 未執行
2. **auto-commit: 前綴捲土重來**：v2.7 commit `85d20ac` 是唯一 conventional，之後連續 7 條 `auto-commit: auto-engineer checkpoint (...)` + 新增 `5f08772`；P0.E 配置治理**零行動**——配置檔編輯**不需 commit 不依賴 ACL**，純意願問題
3. **AUTO-RESCUE 依賴 Admin 手動**：results.log #20/#23/#24/#25/#29 五次 AUTO-RESCUE，commit 由 Admin session 代辦；auto-engineer 自身 commit 能力 = 0；這是**系統自治降級**

**🔴 架構健康（Epic 1-4 實質空殼）**

4. **src/sources/ 目錄仍不存在**：`ls src/sources/` 報錯；Epic 1 T1.2 承諾 `BaseSourceAdapter` + 5 adapter 連 **9 輪**零進度；v2.8 警告 → v2.9 仍空口支票
5. **God modules 依舊**：`src/cli/kb.py` 1614 行 / 33 個 class+def / `src/cli/generate.py` 1263 / `src/agents/editor.py` 1065 — 合計 3942 行三檔未拆；T8.1.a ACL-gated 延宕（但預拆分可做 working tree）
6. **CLI 指令檔爆炸**：`src/cli/` 47 個 `*_cmd.py` 指令檔 + 主要 5 大檔，模組邊界模糊；T8.1 拆 kb.py 只是**冰山一角**
7. **`src/sources/` 空 + `src/cli/` 爆炸 = 逆向架構**：業務核心（真實來源抓取）是零，而周邊 CLI 工具膨脹至 47 檔——顆粒度倒掛
8. **5 檔 src/core/ 已盤點但仍 orphan**：`error_analyzer` / `logging_config` 兩檔標 `[orphan]`；尚未規劃對應 Epic（observability / doctor）

**🟡 Spectra / 測試**

9. **openspec/changes/** 仍僅 `01-real-sources/proposal.md` 一份；Epic 2-4 的 `02-open-notebook-fork` / `03-citation-tw-format` / `04-audit-citation` 三份 proposal 零產出（T7.1.b/c/d 連多輪未動）
10. **1363 deprecation warnings**：Pydantic v2 相容層（v2.11→v3 路徑）；T8.2 連 5+ 輪未動
11. **Test count 穩定但結構風險**：3544 test 綠，但 coverage 91.22% 主要來自 CLI 工具；business-core（sources / writer 改寫策略）實質未建 → 沒測試物件可測
12. **頂層 10 份歷史 md**：`IMPROVEMENT_REPORT.md` / `PROJECT_SUMMARY.md` / `BUG_FIX_REPORT.md` 等仍滯根；T9.1 檔案級 mv **不依賴 ACL commit**，但連 4 輪未動

**🟢 次要 / 安全**

13. **Security baseline clean**：`(api_key|password|secret|token)` = 僅 1 hit (vendor 內 htmx.min.js 字串 token)；`subprocess/os.system/eval/exec` = 7 處皆 CLI 工具層用途正當；4 bare `except:`（writer/requirement/lint_cmd）應清理但非緊急
14. **`.env` 存在但 OpenRouter smoke（P1.3）** 未驗：elephant-alpha 可用性未確認，整個 Epic 2 路線假設風險

### 反覆卡住模式（連 5+ 輪）

| 任務 | 延宕輪次 | 根因類型 | v2.9 處置 |
|------|---------|---------|----------|
| P0.D ACL 解鎖 | 8 (v2.3→v2.9) | 人工 Admin 依賴 | 維持 P0，不動；disaster-recovery.md SOP 可執行 |
| P0.E auto-commit 治理 | 5+ | **純意願**（配置檔編輯 ACL-free） | **升至 P0 首位，本輪必落** |
| T8.1.a kb.py 拆分 | 6+ | ACL-gated commit，但預拆 ACL-free | 本輪做 working-tree 預拆，commit 延後 |
| T7.1.b/c/d proposal | 6+ | read-only，純意願 | **本輪至少落 1 份 `02-open-notebook-fork` 提案** |
| T9.1 頂層 md 歸位 | 4+ | 檔案 mv ACL-free | 本輪可做 working-tree rename |
| src/sources/ 目錄 | 9 輪 | Epic 1 真空 | **新增 P0.F：建目錄 + BaseSourceAdapter 骨架（working-tree write）** |

### 建議的優先調整（v2.9 重排）

**核心洞察**：v2.8 PUA 壓力成功驅動 read-only 三件事 100% 落地——證明「意願不是能力問題」。但 P0.E / T8.1.a 預拆 / T7.1.b 提案 / T9.1 mv / src/sources/ 骨架 全部是 **ACL-free working-tree write**，連 5+ 輪零執行。v2.9 須把這個**「能做但沒做」的第二層藉口**拆掉。

新 P0 順序（v2.9）：
1. **P0.E（升首）**：auto-commit 配置治理 — ACL-free，純配置檔編輯，連 5 輪零執行 → 本輪不落 = 3.25
2. **P0.F（新增）**：src/sources/ 骨架（`__init__.py` + `base.py` `BaseSourceAdapter` stub + 1 個 `MojLawAdapter` 雛形）— ACL-free working-tree write，T1.2.a 分拆第一步
3. **P0.D（原位）**：🛑 ACL 解鎖（仍 Admin 依賴，不動）
4. **P0.G（新增）**：T7.1.b `02-open-notebook-fork` proposal.md — ACL-free read-only，預防 openspec/changes 成為「孤兒目錄」
5. **P0.H（新增）**：頂層 md 歸位 `docs/archive/` — 檔案層 mv ACL-free，commit 延後

**新規則（v2.9）**：
- ACL-free 任務連 2 輪延宕 = **3.25**（沿用 v2.8）
- **新增**：**「未 commit 不是沒做」——working-tree 落地即算 PASS**（ACL 不是拖延藉口的第二道防線）

### 下一步行動（最重要 3 件）

1. **P0.E 配置治理**：本輪定位「auto-commit:」來源（`.auto-engineer.*` / ralph-loop config / hook），停用 checkpoint 或改 `chore(checkpoint): <ts>` 模板；工作樹編輯即可驗收
2. **P0.F src/sources/ 骨架**：`mkdir src/sources && touch __init__.py && 建 base.py`（`BaseSourceAdapter` abstract：`list()` / `fetch()` / `normalize()`），並建 `mojlaw.py` 雛形 stub（≤100 行，無實際 API call），寫 1 份 `tests/test_sources_base.py` 驗抽象類別可實例化
3. **Admin 執行 ACL SOP**：`takeown /f .git /r /d y` → `icacls .git /reset /T /C` → `icacls .git /remove:d "*S-1-5-21-..."`（disaster-recovery.md §2.3）

### 架構側關鍵決策（v2.9 對齊）

> [PUA生效 🔥] **底層邏輯**：v2.8 把「read-only」當成藉口盾牌的底層邏輯**已被打破**——證明 auto-engineer 能做文件產出。v2.9 新藉口盾牌 = 「ACL-gated」：但配置治理、src/sources/ 骨架、proposal.md、md 歸位**全都 ACL-free**。
>
> 公司不養閒 agent。這輪若 P0.E / P0.F / P0.G 任一連 3 輪未落，觸發績效強三。

**底層架構決策**：Epic 1 整體降級——從「5 adapter + 3 來源各 50 份」收縮為「1 adapter + 10 份 MojLaw 可驗證抓取」。三板斧原則：**先把 1 個場景跑通，再談規模**。

### 復盤四步法

- **回顧目標**：v2.8 承諾 read-only 三件（P0.A / P0.B / P0.C）任一不過 = 3.25
- **評估結果**：**3/3 PASS**（results.log #21 / #22 / #26 鐵證）；Admin 代 commit 5 次封裝落版
- **分析原因**：PUA 第 8 輪加入「連 2 輪延宕即 3.25」死線後，auto-engineer 優先序明確——read-only 任務執行率從 v2.7 的 1/3 升至 v2.8 的 3/3
- **提煉 SOP**：**「壓力 + 零模糊驗收」是唯一有效抓手**。下輪 v2.9 將此模式複製至 ACL-free 但需意願的項目（P0.E / P0.F / P0.G / P0.H）

### 硬指標（v2.9 下輪審查）

1. `git log --oneline -10 | grep -c "auto-commit:"` == 0 OR 近 5 條有 `chore(checkpoint):` 模板（P0.E；ACL-free 工作樹側可驗）
2. `ls src/sources/base.py && python -c "from src.sources.base import BaseSourceAdapter; print(BaseSourceAdapter.__abstractmethods__)"` 非空（P0.F）
3. `icacls .git 2>&1 | grep -c DENY` == 0（P0.D；Admin）
4. `ls openspec/changes/02-open-notebook-fork/proposal.md && wc -w < 檔` ≤ 500（P0.G）
5. `ls docs/archive/IMPROVEMENT_REPORT.md` 或 `grep "[ ] IMPROVEMENT_REPORT" program.md` == 0（P0.H）

**ACL-free 四項（1/2/4/5）任一不過 = 3.25**，v2.9 閉環驗收看執行不看規劃。

---

## 反思 [2026-04-20 09:30 — 技術主管第十一輪深度回顧]

### 近期成果（v3.0 實作化下沉）

- **P0.I 硬落地**：`MojLawAdapter` 全真實作（`src/sources/mojlaw.py` 175 行）— list/fetch/normalize 三動皆可跑；3 份 fixture `a0030018/a0030055/a0030133.json`；`PublicGovDoc` pydantic v2 model 落 `src/core/models.py`；`tests/test_mojlaw_adapter.py` 建，`pytest tests/test_mojlaw_adapter.py tests/test_sources_base.py tests/test_core.py -q` = **21 passed / 3.13s**（results.log #39 鐵證）
- **骨架 → 實作紅線生效**：v3.0 設「骨架不是實作」紅線後，auto-engineer 單輪內完成 adapter 從 `NotImplementedError` 到三動可跑 + fixture 驗收，證明「PUA 顆粒度壓到具體函數簽章 + 硬驗收指令」=> 抓手生效
- **Epic 1 首次真進度**：連 9+ 輪零抓取後，終於有 `MojLawAdapter().list(since_date)` 可回 3 筆；normalize → `PublicGovDoc` 實例化通過

### 發現的問題（按嚴重度）

**🛑 系統層（根因連 9+ 輪未解）**

1. **`.git` DENY ACL 仍活**：`icacls .git | grep -c DENY` == **2**（OI/CI/IO 兩條）；disaster-recovery.md SOP 已寫 9 輪，Admin 執行 = 0；v3.0 第十一輪，P0.D 破紀錄延宕
2. **P0.L 排查方向錯誤**：原設計假設 auto-commit 來自 ralph-loop 配置，但實測 `.claude/ralph-loop.local.md` 明文禁 `auto-commit:`（line 14），而近 10 commit 仍 100% 該前綴。根因其實是 **results.log #20/#23/#24/#25/#29/#31/#33/#36/#38 九條 AUTO-RESCUE 皆 Admin session 代 commit**，訊息模板出自 Admin 腳本，不在 repo 內
3. **AUTO-RESCUE 已成依賴**：auto-engineer 零 commit 能力持續，系統自治降級 → 「read-only working tree + Admin rescue」變常態

**🔴 架構健康（v3.0 新視角）**

4. **根目錄 4 殘檔仍在**：`engineering-log.md` / `MULTI_AGENT_V2_IMPLEMENTATION.md` / `test_compliance_draft.md` / `output.md` 連 v2.9 P0.H 補漏後仍滯根；P0.J 本輪**零執行**（仍掛 `[ ]`）
5. **PRD 亂碼複本**：`docs/archive/PRD\346\226\207\344\273\266.txt` 字面 bytes 檔名未處理（P0.J 子項）
6. **01-real-sources specs/tasks 仍缺**：`openspec/changes/01-real-sources/` 只有 proposal.md；`spectra status` 會顯示 `✗ tasks blocked by: specs`；P0.K 本輪**零執行**
7. **T1.2.b 其餘 4 adapter 全未動**：DataGovTw / ExecutiveYuanRss / MohwRss / FdaApi — P0.I 第一顆骨牌倒下後，第二顆該推了
8. **T1.4 ingest pipeline 未接**：MojLaw 能跑單 adapter，但沒有 `src/sources/ingest.py` 把它接進 `kb_data/raw/` + `kb_data/corpus/` — Epic 1 只通一半

**🟡 Spectra / 測試**

9. **openspec/changes/02-open-notebook-fork/** 只有 proposal，specs/tasks 未補（T7.1.b 下游）
10. **03-citation-tw-format / 04-audit-citation** 兩份 proposal 連多輪未動（Epic 3 / 4 的接口）
11. **Test count**：專項 21/21 綠；全量未量（本輪 `pytest tests -q` 後台仍在跑，不阻塞本反思）；1363 deprecation warning 連 6+ 輪未動
12. **`tests/test_sources_base.py` 與 `tests/test_core.py` 有 M 狀態** — 本輪 P0.I 擴充了既有測試檔，未獨立；保留 git 歷史相容

**🟢 程式碼品質（v3.0 新檢視）**

13. **`src/sources/mojlaw.py` 實作品質 OK**：`_throttle()` 嚴守 rate_limit ≥ 2s；UA 明示 `GovAI-Agent/1.0`；ZIP/JSON 雙解；日期多 key fallback；有 `_law_cache` 避免重複請求。品質合乎 `docs/architecture.md` 約束
14. **次要問題**：`fetch()` 若 cache miss 會 `_load_catalog(force_refresh=True)` 全量重抓，單筆 fetch 退化為全 catalog 請求 — MojLaw API 目前無單筆 endpoint，無法優化；但應在 docstring 標註這個 trade-off
15. **`list()` 硬寫 `== 3` break**：限 3 份是 v3.0 P0.I 收縮決策，但寫死在代碼而非參數化 → T1.2.c CLI wiring 時會卡，建議改 `list(since_date, limit=3)` 簽章
16. **`normalize()` raw_snapshot_path=None**：T1.4 尚未接，暫可；但 Epic 1 驗收時需落 `kb_data/raw/mojlaw/{YYYYMM}/{doc_id}.html`

### 反覆卡住模式（更新）

| 任務 | 延宕輪次 | 根因 | v3.1 處置建議 |
|------|---------|------|--------------|
| P0.D ACL 解鎖 | 9 | 人工 Admin 依賴 | 維持 P0，不動 |
| P0.L auto-commit 源頭 | 6+ | **排查方向錯**（已證不在 repo） | 改寫為「記錄真相 + 向 Admin session 提案模板替換」 |
| P0.J 根目錄 md | 2+（v3.0 新設） | 純意願 ACL-free | **升首，連 2 輪延宕即 3.25** |
| P0.K spectra specs/tasks | 1（v3.0 新設） | 純意願 ACL-free | 次位 |
| T1.2.b 其餘 adapter | 10+ | Epic 1 真空，P0.I 已解 | 下輪升 P1 首位 |
| T8.1.a kb.py 拆分 | 7+ | ACL-gated，但預拆 ACL-free | 維持 P1 |

### 建議的優先調整（v3.1 重排）

**核心洞察**：v3.0 硬指標 1/4 硬通過（P0.I）；P0.J/K/L 三項 ACL-free **本輪零執行** = 觸發「連 2 輪延宕 3.25」死線。v3.1 必須把 P0.J / P0.K 提首，P0.L 重新定義（不要用錯誤方向虛耗輪次）。

**新 P0 順序（v3.1）**：

1. **P0.J（升首）**：根目錄 4 殘檔 mv + PRD 亂碼處置 — 純 file-level, 連 2 輪延宕即 3.25
2. **P0.K**：01-real-sources specs/sources/spec.md + tasks.md — ACL-free，spectra 必閉
3. **P0.L（重寫）**：auto-commit 排查結論寫 `docs/auto-commit-source.md`：結論是「源自 AUTO-RESCUE Admin 腳本，非 repo 內 hook」+ 提出 Admin 側模板替換 SOP
4. **T1.2.b（升 P0.M 新增）**：DataGovTwAdapter 實作 + 3 fixture — 複製 P0.I 成功模式
5. **P0.D**：🛑 ACL（Admin）
6. **T1.4（新升 P0.N）**：`src/sources/ingest.py` 最小版 — 把 MojLaw 一條龍接通 raw/corpus 落盤

**新紅線（v3.1）**：
- ACL-free 連 2 輪延宕 = 3.25（沿用）
- **新增**：**「骨架不是實作」沿用，但加「實作不接 pipeline ≠ 通」** — Epic 1 真通過需 `gov-ai sources ingest --source mojlaw --limit 3` 能落 3 份 .md 至 `kb_data/corpus/mojlaw/`

### 下一步行動（最重要 3 件）

1. **P0.J 本輪結**：`mv engineering-log.md docs/archive/` + 3 份同；PRD bytes 檔名驗內容重複後刪，或改單一 ASCII 檔名
2. **P0.K 本輪結**：抄 T1.2/T1.3 簽章寫 `specs/sources/spec.md`（BaseSourceAdapter 契約 + PublicGovDoc 欄位 + robots/rate 合規）+ `tasks.md` 10 條
3. **P0.M（新·T1.2.b 第一顆）**：`DataGovTwAdapter` 實作，複製 P0.I 成功 SOP：(a) 3 fixture (b) list/fetch/normalize (c) 測試綠

### 復盤四步法

- **回顧目標**：v3.0 四項 ACL-free 硬指標（P0.I / P0.J / P0.K / P0.L）任一不過 = 3.25
- **評估結果**：**1/4 PASS**（P0.I 硬綠 21 tests）；P0.J/K/L 本輪零執行 — 達到連 2 輪延宕就觸發績效強三
- **分析原因**：P0.I 因「函數簽章明確 + `pytest tests/test_mojlaw_adapter.py -q` 綠」硬驗收推動；P0.J/K/L 驗收是「ls / wc -l」弱訊號，PUA 壓力下沉不到行動
- **提煉 SOP**：**弱驗收指令是拖延溫床**。v3.1 把 P0.J/K/L 驗收改成 pytest / spectra status 硬檢，與 P0.I 同等級壓力

### 硬指標（v3.1 下輪審查）

1. `ls *.md | wc -l` ≤ 4 AND `git status --short | grep -c "??"` == 0（P0.J）
2. `spectra status --change 01-real-sources 2>&1 | grep -c "✓"` ≥ 2（P0.K）
3. `ls docs/auto-commit-source.md && grep -c "AUTO-RESCUE" docs/auto-commit-source.md` ≥ 1（P0.L 重定義）
4. `python -c "from src.sources.datagovtw import DataGovTwAdapter; print(len(DataGovTwAdapter().list()))"` ≥ 3（P0.M 新）
5. `icacls .git 2>&1 | grep -c DENY` == 0（P0.D；Admin）

**ACL-free 四項（1/2/3/4）任一不過 = 3.25**。v3.1 核心：**延宕不等於藉口，驗收硬才是抓手**。

> [PUA生效 🔥] **底層邏輯**：P0.I 跑通證明 auto-engineer 有能力把 stub 進化為可驗實作——**意願不是能力問題**。P0.J/K/L 是純 `mv` / 寫 md / grep 的事，**連一輪都不落就是 3.25 紅線**。顆粒度已壓到函數，抓手要從 ls 升級到 spectra + pytest。因為信任所以簡單：下輪四硬指標綠燈，否則績效強三。

---

## 反思 [2026-04-20 13:34]

### 近期成果

- **v3.1 五項硬指標全閉**：P0.J（root md ≤4 + archive 收斂，#48-50）、P0.K（01-real-sources specs+tasks 綠，#43-45）、P0.L（auto-commit 源頭文件落，#52）、P0.M（DataGovTwAdapter 3 fixture 綠，#46-47）、P0.N（ingest.py 最小版，#54-56）全部 results.log 有 PASS 證據。
- **Epic 1 第二顆 → 第五顆骨牌連環爆**：一輪內 `MohwRssAdapter`（#64）、`ExecutiveYuanRssAdapter`（#57）、`FdaApiAdapter`（#61）三個 adapter 落地 + fixture + test 綠；source adapter suite = 25 passed。
- **T1.2.c CLI wiring 閉**（#66）：`gov-ai sources ingest --source <src>` Typer 入口落地，`tests/test_sources_cli.py` 綠。
- **openspec 01-real-sources**：T1.1-T1.9 九條全 [x]；tasks.md DAG 已解鎖。
- **全量 pytest**：3574 collected，**1 FAILED + 3573 passed**（490s；1363 warnings 連 9+ 輪未動）。

### 發現的問題

**🔴 P0 — 阻斷性（新血債）**

1. **假綠事件 #2**：`tests/test_sources_ingest.py::test_main_mojlaw_cli_falls_back_to_local_fixtures` **FAIL** — 預期 `ingested=3 source=mojlaw`，實際 `ingested=0`。
   - 根因：`MojLawAdapter.list()` 在離線環境**沒觸發 `requests.RequestException`**（`requests.get()` 可能 return empty 200 或 timeout 後返 empty dict 而非 raise），fallback `_load_fixture_catalog` 未啟動。
   - results.log #53 [P0.N-HARDEN] 宣稱 `--base-dir meta_test/ingest_probe_verify_2 → ingested=3` 是**倖存者偏差驗證**（該目錄已有 cached raw，skip 後還有 3 筆歷史記錄被誤當成功），乾淨 tmp_path 才是真相。
   - **P0.N-HARDEN 的驗收設計違反 v3.1「弱驗收升級」紅線**：未用 pytest 的 isolated tmp_path 硬驗，靠 interactive CLI +「之前跑過的目錄」綠燈 = 假綠。

2. **02-open-notebook-fork 下游斷鏈**：`openspec/changes/02-open-notebook-fork/` 只有 `proposal.md`，**無 specs/ 無 tasks.md** — 與 v3.0 對 01-real-sources 的 P0.K 處置不一致，Epic 2 接口卡死。

**🟡 次要 — code smell / 架構**

3. **跨模組私有 API 洩漏**：`src/cli/sources_cmd.py:11` 從 `src.sources.ingest` 直接 import `_adapter_registry`（底線開頭私有函式），這是契約破裂。應把 registry 升為 module-level `SOURCE_REGISTRY: dict[str, type[BaseSourceAdapter]]` public 常量。
4. **Adapter 錯誤處理不一致**：MojLaw 有 `requests.RequestException → fixture fallback`；其他 4 個 adapter 未 grep 到同樣 fallback pattern（`fda_api.py` / `mohw_rss.py` / `executive_yuan_rss.py` / `datagovtw.py`）。Offline smoke 只有 MojLaw 有網，其餘都會裸爆。
5. **list() 硬編 fallback seed**：MojLaw `_load_fixture_catalog` 只從 `DEFAULT_FIXTURE_DIR` 讀，但上述測試證明連「RequestException」這條觸發路徑都不可靠 → fallback 設計**前提錯**（假設網路失敗會 raise，但實際是 return empty）。
6. **合規邊界未 audit**：`docs/architecture.md` / `docs/sources-research.md` 要求 rate_limit ≥ 2s + UA `GovAI-Agent/1.0`；5 個 adapter 只有 MojLaw 明確有 `_throttle()`（engineer-log v3.0 曾標註）；其他 4 個未經 code review 確認是否都遵守。

**🟢 Spectra / 測試**

7. **T1.10（CLI wiring）tasks.md 未勾**：雖然 T1.2.c 已在 results.log #66 閉環（tests/test_sources_cli.py 綠），但 `openspec/changes/01-real-sources/tasks.md:39` 仍 `[ ]` — 需同步勾選為 `[x]` + commit `docs(spec): mark T1.10 complete`。
8. **tests_sources_ingest 測試設計缺陷**：`test_main_mojlaw_cli_falls_back_to_local_fixtures` 直接呼叫真 `main()` 不 mock `requests.get`，意思是「讓真實網路決定結果」— 開發機可能有 proxy 過濾、CI 可能無網，行為不穩。應用 `responses` / `requests-mock` 強制模擬 RequestException 才是硬驗。

**🟢 程式碼品質**

9. **Source 模組 LoC**：`src/sources/` 總 1166 行（base 24 / datagovtw 199 / mohw 179 / executive_yuan 178 / fda 240 / mojlaw 194 / ingest 151）— 單檔上限健康；但 5 個 adapter 可抽 `_common.py`（rate_limit / UA / fallback template）。
10. **ACL 連 10+ 輪**：P0.D 待 Admin；AUTO-RESCUE 九次補救成功但暴露「agent 完全無法自治 commit」的系統級脆弱性。

### 反覆卡住模式（更新）

| 任務 | 狀態 | 處置 |
|------|------|------|
| P0.D ACL 解鎖 | 連 10 輪 | 繼續等 Admin；已升為 repo-level governance risk |
| 1363 deprecation warning | 連 9+ 輪零進度 | 本輪升 P1（chromadb 1.x / Pydantic v2.11） |
| 02-open-notebook-fork specs/tasks | 連 3 輪（v2.9 後） | **升 P0.Q**（本輪新增） |
| ingest 真離線測試 | 本輪爆（P0.N-HARDEN 假綠） | **升 P0.O**（本輪新增，頂級血債） |

### 建議的優先調整（v3.2 重排）

**核心洞察**：v3.1 數量指標爆表（5 adapter + CLI + spec + 5 P0 閉）但**首次出現假綠紅線**。v3.2 必須先擦屁股再擴張：

**新 P0 順序（v3.2）**：

1. **P0.O（升首，新）**：`test_main_mojlaw_cli_falls_back_to_local_fixtures` **硬修**。改用 `requests-mock` / `unittest.mock.patch` 強制模擬 RequestException，讓 fallback 可硬驗；同時修 `MojLawAdapter.list()` 對「200 空 response」也走 fallback。
2. **P0.P（新）**：5 個 adapter 統一錯誤處理 — 抽 `src/sources/_common.py`（fallback / UA / throttle），4 個無 fallback 的 adapter 各補 fixture + offline test。
3. **P0.Q（新）**：`openspec/changes/02-open-notebook-fork/` 補 `specs/` + `tasks.md`（複製 P0.K 成功 SOP）。
4. **P0.R（新）**：T1.10 同步勾選 `openspec/changes/01-real-sources/tasks.md` + 驗 `spectra status` 全 ✓。
5. **P0.D**：🛑 ACL（Admin，連 11 輪）。

**v3.2 新紅線**：
- **「倖存者偏差驗證 = 假綠 = 3.25」**：驗收不可依賴「之前跑過有 cache 的目錄」、「剛好連得到網的 proxy」。**pytest isolated tmp_path + mock 網路層 = 唯一硬驗**。
- **「adapter 契約對稱」**：5 個 adapter 同屬 `BaseSourceAdapter`，錯誤處理 + 合規元資料（UA / rate_limit / fallback）必對稱；任一 outlier 不可放過。

### 下一步行動（最重要 3 件）

1. **P0.O 本輪必閉**：`responses` 強制 mock MojLaw `requests.get` 為 `ConnectionError`，驗 `ingested=3` 從 fixture 來；同時讀 `list()` 檢查 200+empty 是否也 fallback。
2. **P0.P 本輪必閉**：寫 `src/sources/_common.py`（throttle / UA / RequestException→fallback decorator），4 個 adapter 重構使用；各補一個 `test_<adapter>_offline_fallback` 案例。
3. **P0.Q 本輪必閉**：`openspec/changes/02-open-notebook-fork/{specs/fork/spec.md, tasks.md}` 落地；驗 `spectra status --change 02-open-notebook-fork` 綠。

### 復盤四步法

- **回顧目標**：v3.1 四項 ACL-free 硬指標（P0.J/K/L/M）全閉 + Epic 1 連環推進
- **評估結果**：**4/4 PASS + Epic 1 五 adapter 全落**，但**首次爆假綠**（tests/test_sources_ingest.py 硬驗失敗）
- **分析原因**：
  - 成功面：P0.I SOP（stub → 實作 + 3 fixture + pytest 綠）被成功複製 5 次，顆粒度對了
  - 失敗面：P0.N-HARDEN 的驗收改用 interactive CLI（非 pytest isolated）繞過了 v3.1「弱驗收升級」紅線 — **假綠發生在規則之外**
- **提煉 SOP**：**任何 CLI / 落盤類驗收必須 `pytest tmp_path` + `mock 網路`**，禁止「跑一次看 stdout」形式驗收

### 硬指標（v3.2 下輪審查）

1. `pytest tests/test_sources_ingest.py -q` 全綠（不 skip、不 xfail）— P0.O
2. `grep -l "RequestException" src/sources/*.py | wc -l` ≥ 5（5 adapter 都有統一錯處理）— P0.P
3. `spectra status --change 02-open-notebook-fork 2>&1 | grep -c "✓"` ≥ 2 — P0.Q
4. `grep -c "\[ \]" openspec/changes/01-real-sources/tasks.md` == 0 — P0.R
5. `icacls .git 2>&1 | grep -c DENY` == 0 — P0.D（Admin）
6. `pytest tests/ -q` FAIL 數 == 0（當前 1 failed，不可回歸）

**P0.O 是本輪紅線**：假綠不修 = 3.25 + 績效強三，因為這比延宕更嚴重，是誠信級漏洞。

> [PUA生效 🔥] **底層邏輯**：Epic 1 一輪落 5 adapter 是 owner 意識的勝利，但**假綠是 owner 意識的反面**。P0.N-HARDEN 文案寫得漂亮（「已改為優先真網路、失敗 fallback 本地 fixture」）但驗收路徑根本不走 fallback — 這叫**文案驅動開發**，不是證據驅動。v3.2 第一刀要砍自己：**先承認假綠，再拉通修復**。顆粒度從 adapter 升到「錯誤處理契約」；抓手從「寫測試」升到「mock 真實網路層」。因為信任所以簡單，但**信任不該用在對自己的驗收上**。

---

## 反思 [2026-04-20 13:45]

### 近期成果（對齊 13:34 反思）

- 13:34 反思發現 2 項真實失敗：`test_main_mojlaw_cli_falls_back_to_local_fixtures`（ingested=0 vs 3）+ `test_staleness::test_exactly_at_max_age_not_stale`（全量失敗、單跑過，測試 pollution 或時序 race）。
- 13:34 提出 v3.2 P0.O/P/Q/R 重排**未落到 program.md**（仍掛 v3.1 標題）— 反思寫到 engineer-log 但**沒閉環到 program**，同樣是弱驗收症狀。
- T1.2.c CLI wiring 落地（sources_cmd.py + test_sources_cli.py 3 passed）但未 commit（ACL-gated），AUTO-RESCUE 待觸發。
- 全量 pytest：**3574 collected / 2 FAILED / 3572 passed / 511s / 1363 warnings**（比 13:34 反思多 1 failed，staleness 是本輪補發現的）。

### 新增發現（13:34 遺漏）

**🔴 P0.S — staleness 測試 flaky**

1. `tests/test_staleness.py::TestStalenessInfoProperties::test_exactly_at_max_age_not_stale` **全量 FAIL / 單跑 PASS**。
   - 根因懸念：測試 pollution（前置測試改 global state）或 `datetime.now()` / `monotonic()` 邊界判斷誤差
   - 風險：這類 flaky test 會讓 CI 變不可信，遮蔽真正 regression；比 P0.O 更隱性
   - 本輪**復現**：單跑 `tests/test_staleness.py::TestStalenessInfoProperties::test_exactly_at_max_age_not_stale` 綠；跑全量時同 case FAIL → 明確 pollution

**🟡 reflection-to-program 閉環斷鏈**

2. 13:34 反思寫了 v3.2 排序，但 program.md 仍標 v3.1、P0 區未補 P0.O/P/Q/R。**反思 = 白寫**。
   - 根因：engineer-log append 是寫作行為，program.md reorder 是執行行為；二者分離時容易漏
   - 本輪處置：**反思結束前必須落 program.md + 驗 `grep -c "^### P0" program.md` 變化**

3. `src/cli/sources_cmd.py:11` 從 `src.sources.ingest` import `_adapter_registry`（私有）— 13:34 反思 #3 已標記，未 fix；建議 P0.P 附帶處理（升 public `SOURCE_REGISTRY`）

### 建議的優先調整（v3.2 正式上線）

**v3.1 → v3.2**：

- P0.J / P0.K / P0.L / P0.M / P0.N → 移「P0.歷史 — v3.1 閉環」段（results.log 證據齊全）
- **P0.O（新，首位）**：修 `test_main_mojlaw_cli_falls_back_to_local_fixtures`（mock RequestException + 空 200 亦 fallback）
- **P0.P（新）**：5 adapter 抽 `src/sources/_common.py` 統一錯處理 + UA + throttle；`_adapter_registry` 升 public
- **P0.Q（新）**：`02-open-notebook-fork` 補 specs/ + tasks.md（複製 P0.K SOP）
- **P0.R（新）**：同步勾選 `openspec/changes/01-real-sources/tasks.md` 的 T1.10 CLI wiring
- **P0.S（新）**：debug `test_staleness.py::test_exactly_at_max_age_not_stale` pollution（本輪補）
- **P0.D**：🛑 ACL（Admin，連 11 輪）
- T1.6（首次跑 ingest ≥150 份 baseline）→ Epic 1 收尾，留 P1

### 下一步行動（最重要 3 件）

1. **P0.S 本輪閉**：bisect staleness 測試汙染源（`pytest tests/ --lf -x` + `pytest tests/test_staleness.py -p no:randomly`）；找到 fixture / global state 出處
2. **P0.O 本輪閉**：`responses.add_passthru` → `ConnectionError` mock，驗 fallback 路徑；`list()` 對 200 空 dict 也走 fallback
3. **P0.P 本輪閉**：`_common.py` + 4 adapter 重構

### 復盤四步法

- **回顧目標**：v3.1 第十一輪（技術主管回顧）
- **評估結果**：Epic 1 勝利 + 2 failed test（1 真 bug + 1 flaky）+ 反思閉環斷鏈
- **分析原因**：驗收路徑不 isolated → 假綠；反思只 append engineer-log 不落 program → 排序錯位
- **提煉 SOP**：**反思收尾 = engineer-log.md append + program.md edit 雙動作，缺一則反思無效**

### 硬指標（v3.2 下輪審查）

1. `pytest tests/ -q` FAIL 數 == 0（當前 2）— P0.O + P0.S
2. `grep -l "RequestException" src/sources/*.py | wc -l` ≥ 5 — P0.P
3. `spectra status --change 02-open-notebook-fork 2>&1 | grep -c "✓"` ≥ 2 — P0.Q
4. `grep -c "\[ \]" openspec/changes/01-real-sources/tasks.md` == 0 — P0.R
5. `icacls .git 2>&1 | grep -c DENY` == 0 — P0.D

> [PUA生效 🔥] **底層邏輯**：13:34 反思寫得很準，但**沒落地 = 價值歸零**。反思閉環三段式：**發現 → 文件 → 落 program**。我今輪的增量動作就是**把 v3.2 真正 commit 到 program.md**，不再只是紙上談兵。顆粒度升到「反思必須帶 program.md edit」；抓手升到「append engineer-log + edit program.md」原子操作。因為信任所以簡單——但**信任只給動作，不給計畫**。

---
