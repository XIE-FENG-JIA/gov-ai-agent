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
