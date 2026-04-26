# Program History — 202604M（v8.0 ~ v8.3 批次回合封存）

> 封存自 program.md；主檔降線 ≤ 220 行（T-PROGRAM-MD-ARCHIVE-202604M，2026-04-26）

---

## v8.3 批次回合（2026-04-26 14:30 /pua 深度回顧；ea22663 push 後）

- ✅ **HEAD = origin/main = ea22663**（afcc254 + ea22663 + 1ad2432 三連推；rev-list 0/0）
- ⚠️ **pytest -n 8 cold runtime 暴增**：`python -m pytest tests/ --ignore=tests/integration -q --tb=line -x` = **3969 passed / 0 failed / 436.19s**；vs v8.0 cold 167s = **2.6x 暴增**，**soft 200s 紅線 2.18x 破**；T-PYTEST-RUNTIME-REGRESSION-ITER8 升 P0
- ✅ **sensor hard=[] / soft=[]**：bare_except=3 noqa / fat red=0 yellow=0 / corpus=400 / auto_commit=100% (30/30) / program.md=222 / engineer-log=99
- ✅ **openspec 0 active / 14 specs / 17 archive INDEX 齊**
- ⚠️ **watch 300-400 = 12 檔**：top 4 全 320+（web_preview 347 / llm 343 / gazette_fetcher 331 / review_parser 326）；fat 邊緣值 — 預抽 ROI ×3

---

## v8.2 批次回合（2026-04-26 14:02 Copilot agent；1ad2432 push 後）

- ✅ **HEAD = origin/main = 1ad2432**（T9.1.a + T-CORPUS-PROVENANCE-PYTEST-IMPORT + P2-Legacy-INDEX-LOCK 三任務同 commit 推送；rev-list 0/0）
- ✅ **T-XDIST-VERIFY-V8.2**：`python -m pytest tests/test_robustness.py -n 8 -q` × 2 輪 = 299 passed ×2；TestGracefulDegradation::test_kb_init_failure_graceful 穩定 ✅（xdist race 漂白第七型確認根治）
- ✅ **sensor 全綠**：hard=[] / soft=[] / bare_except=3 noqa / fat red=0 yellow=0 / corpus=400 / auto_commit_rate=100% (30/30) / program.md=216 / engineer-log=99
- ✅ **T9.1.a + T-CORPUS-PROVENANCE-PYTEST-IMPORT + P2-Legacy-INDEX-LOCK**：前輪已驗證代碼，本輪 .git ACL 已解，成功 commit 1ad2432 + push

---

## v8.1 批次回合（2026-04-26 11:30 /pua 深度回顧；e04476e push 後）

- ✅ **HEAD = origin/main = e04476e**（T-PUSH-ORIGIN-V8.0 連 2 輪 open 終閉；rev-list ahead/behind = 0/0；9 commits 全推）
- ⚠️ **pytest -n 8 全量 1 flaky**：`python -m pytest tests/ --ignore=tests/integration -q --tb=line` = **3968 passed / 1 failed / 47.80s**；flaky = `tests/test_robustness.py::TestGracefulDegradation::test_kb_init_failure_graceful`（單檔重跑 14.18s = PASS → **xdist race 漂白第七型再現**，新 callsite chromadb mock cluster）
- ✅ **sensor 全綠**：hard=[] / bare_except=3 noqa / fat red=0 yellow=1 max=350 / corpus=400 / auto_commit_rate=100% (30/30) / soft=program_md_lines 264>250
- ⚠️ **T-GITIGNORE-TMP-OUT 部分緩解**：`.gitignore` 加 `*.tmp` / `out*`，`out.tmp` 已變 ignored；刪除被 Windows ACL/鎖拒絕；spec 漂白第四型未補（embedding-provider-rest-fallback proposal 缺）；engineer-log 297→寫前 rotate 至 [202604M.md](docs/archive/engineer-log-202604M.md)

---

## v8.0-r5 批次回合（2026-04-26 T-COMMIT-LINT-FEAT-LLM-PYTEST-GATE 完成）

- ✅ **T-COMMIT-LINT-FEAT-LLM-PYTEST-GATE**：`scripts/commit_msg_lint.py` 對 `feat(llm|core|api)` 強制 commit body 含同 scope pytest 證據（如 `pytest tests/test_llm.py = N passed`）；新增正反向測試 8 條；驗證 `python -m pytest tests/test_commit_msg_lint.py -q` = 32 passed。

---

## v8.0-r4 批次回合（2026-04-26 T-LLM-EMBED-TEST-FIX 完成）

- ✅ **T-LLM-EMBED-TEST-FIX**：`tests/test_llm.py` OpenRouter embedding 測試改 mock `src.core.llm._requests.post`，斷言 REST URL / Bearer header / JSON body；刪 `src/core/llm.py` unreachable openrouter litellm branch；驗證 `python -m pytest tests/test_llm.py -q` = 52 passed，`python -m pytest tests/ -q --ignore=tests/integration` = 3958 passed。

---

## v8.0-r3 批次回合（2026-04-26 09:50 T-NEMOTRON-EMBEDDING-VALIDATE-CLOSE 完成）

- ✅ **T-NEMOTRON-EMBEDDING-VALIDATE-CLOSE**：config.yaml `embedding_api_key` 修正；llm.py OpenRouter 直連 REST API（繞 litellm）+ 8000 char 截斷；ChromaDB `_type` schema 修正；KB 重建 400 docs（100 regulations + 300 policies）；Recall@5 = 5/5 = 100%；docs/embedding-validation.md 新增；pytest 3958 passed ✅

---

## v8.0-r2 批次回合（2026-04-26 09:42 /pua 深度回顧；cf26345 後 regression + 4 commits 未推 origin）

- ⚠️ **pytest 全量 regression**：`python -m pytest tests/ -q --ignore=tests/integration` = **3956 passed / 2 failed / 172.20s**；2 failed = `tests/test_llm.py::TestLiteLLMEmbedEdgeCases::{test_embed_openrouter_model_name, test_embed_uses_embedding_provider_credentials}` — cf26345 `feat(llm): OpenRouter direct REST API` 引入；agent 未跑同檔 pytest = **漂白第十型**
- ⚠️ **dead branch**：`src/core/llm.py:256-257` openrouter elif 永遠到不了（早 return 覆蓋）→ 需與 stale test 同刀刪
- ⚠️ **本機領先 origin/main 4 commits**：cf26345 / 310bac9 / 1b8d793 / c2bfc1e 未推 = 雲端工作量歸 0；T-PUSH-ORIGIN-V8.0 升 P0
- ✅ **sensor hard=[] / soft=[]**：bare_except=3 noqa；fat red=0 yellow=1 max=350（catalog.py）；corpus 400；auto_commit_rate **100%**（30/30，wrapper noise 真斷根）
- ✅ **openspec 0 active**：archive 16 條目齊 + specs/ 13 capabilities promote

---

## v8.0 批次回合（2026-04-26 08:10 /pua；T15.5 commit + openspec 15/16 promote/archive + sensor + pytest -n 8 驗收）

- ✅ **T15.5 commit 62b2d85**：`pyproject.toml addopts` `-n auto → -n 8`（NTFS/import I/O 飽和修正）；Gate C 183.98s / Gate D 195.64s；median 189.81s ≤ 200s ✅
- ✅ **openspec changes 15/16 全部 promote → archive**：`openspec/changes/` 僅剩 `archive`（0 active changes）；`openspec/specs/runtime-baseline/` 新建；INDEX.md 補 15/16 條目（共 16 條）
- ✅ **pytest -n 8 全量**：`python -m pytest tests/ -q --ignore=tests/integration` = **3958 passed / 0 failed / 167.13s**（< 200s 目標 ✅）
- ✅ **sensor hard=[]**：bare_except=3（全 noqa/compat）；fat red=0 / yellow=6 / ratchet OK；corpus=400；program.md 223
- ⚠️ **auto_commit_rate 83.3%**（25/30）< 90% target（soft only）
