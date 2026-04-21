# Program History Archive — 202604g

封存時間：2026-04-21

用途：
- 保留從 `program.md` 移出的舊 review header、舊 P0/P1 bundle、早期完成清單。
- 主檔改成「現況 + 活任務」後，這裡承接歷史脈絡。
- 需要逐字原貌時，請再配合 git history；本檔以可讀摘要為主。

## 封存範圍

- `v6.4`、`v6.3`、`v6.1`、`v5.9`、`v5.8`、`v5.7`、`v5.6 USER OVERRIDE`、`v5.5 USER OVERRIDE`
- `v5.4`、`v5.3`、`v5.2`、`v5.1`
- `v4.9`、`v4.8`、`v4.7`、`v4.6`、`v4.4`、`v4.3`
- 舊 P0/P1 bundle：client auth、Epic 4 proposal、fat-file rotate 舊輪次、log archive 舊輪次、Epic 8 KB split、integration gate、writer failure matrix、FF hotfix、Epic 2 finish、full pytest、console import、rebase/admin ACL、live-ingest/corpus cleanup、Epic 3 proposal、Windows gotchas、早期 P0.J/P0.K/P0.L/P0.M/P0.N 與 `P0.歷史` 段。

## 歷史快照

### v6.4（2026-04-21 23:50 → 2026-04-22 架構師第四十輪）
- 主張 `program.md` 自身 1912 行 → ≤ 1000；engineer-log 333；pytest runtime 772s 新 blocker。
- P0：`T-PROGRAM-MD-ARCHIVE`、`T9.6-REOPEN-v5`（engineer-log v5.7/v5.8 封存）、`T-PYTEST-PROFILE`、`T-FAT-ROTATE-V2` 刀 6（`api/models.py 461`）。
- 硬指標：program.md ≤ 1000、engineer-log ≤ 300、pytest ≤ 500s、`src/api/models.py` 或拆後每檔 ≤ 400。

### v6.3（2026-04-21 21:09 單刀值班）
- `T-BARE-EXCEPT-AUDIT` 刀 2 閉（`src/api/routes/agents.py` 9 處 → 0）。
- pytest 3739/0/515s；胖檔剩 6 檔 > 400。
- 建議下輪轉鎖 middleware / api-models。

### v6.1（2026-04-21 19:15 架構師第三十九輪）
- Spectra 4/5 80% → **5/5 100%**（首度達成）；Epic 5 三刀連閉（T5.1/T5.2/T5.3）。
- 問題：`engineer-log` 再破 300；`src/e2e_rewrite.py 474` 單檔未拆。
- P0：T9.6-REOPEN-v4、T-FAT-ROTATE-V2 刀 3、T-BARE-EXCEPT-AUDIT 刀 2。

### v5.9（2026-04-21 15:10）
- corpus 9 → **173**（19x）；FDA live endpoint 修復；PCC adapter 落地。
- `realtime_lookup 520` 拆為 `realtime_lookup 386 + _laws 107 + _policy 31`。
- Spectra 3/5 → 4/5 = 80%（Epic 4 proposal 落地）。

### v5.8（2026-04-21 13:20）
- `config_tools 585` 拆為 `config_tools 257 + _mutations_impl 225 + _fetch_impl 96`。
- pytest 3727/0；header drift 第五次校準。
- Epic 5 proposal 落地。

### v5.7（2026-04-21 09:45 OVERRIDE 解鎖）
- T5.4 E2E PASS（5/5 docx / citation_count=2 / source 可溯）。
- 明列「T-CLIENT-AUTH 實質已閉」事實校準；避免 header 持續列假血債。

### v5.6 USER OVERRIDE（2026-04-21）
- 人工解鎖 Phase A+B；P0.1 FDA/MOHW 真因定位。
- 禁爬清單（`gazette.nat.gov.tw` robots.txt Disallow）確認。
- 切換至 `nvidia/llama-nemotron-embed-vl-1b-v2:free` embedding（dim=2048）。

### v5.5 USER OVERRIDE（2026-04-21）
- 人工鎖：禁新增 Epic / 禁架構師重排 / 禁新 spec / 胖檔 split deprioritize。
- 強制聚焦 Epic 5 T5.4 E2E；通過後才解鎖，v5.7 解除。

### v5.4
- workflow router、app factory、history split、exporter split 轉綠。
- Spectra 當時仍卡 Epic 4 proposal。
- engineer-log 已壓回 hard cap。

### v5.3
- manager split、persist split 已做。
- workflow/history/exporter/api_server 仍是主胖檔。
- `engineer-log` 封存 drift 開始暴露。

### v5.2
- 第一次明確把 `engineer-log` 與胖檔反向生長列成同輪血債。
- 啟動 `P0.LOGARCHIVE-V3` 與 `P0.ARCH-DEBT-ROTATE`。
- `verify-docx-schema` 與 litellm teardown noise 在此階段補齊。

### v5.1
- 紅線壓縮成「核心 3 + 紅線 X」。
- `citation-tw-format` baseline promote。
- `docs/arch-split-sop.md` 落地。

### v4.9
- Epic 2 首次收官。
- Epic 3 citation spec / metadata / verify flow 成形。
- writer split、engineer-log 封存、canonical heading 一輪多破。

### v4.8
- `T2.9` freeze 與 `P0.EPIC3-PROPOSAL` 開始補齊。
- 實測修正 header 與 HEAD 漂移。

### v4.7
- 正式承認 `P0.S-REBASE-APPLY` 是 Admin 依賴，不再假裝 agent 可直接解。
- 對 v4.6 的 order 做 surgical 校準。

### v4.6
- 把 Epic 2 收尾、writer split、Epic 3 proposal、engineer-log 封存列成主線。
- 全量 pytest 回到綠。

### v4.4
- `smoke_open_notebook.py` 的 `status` 初始化 bug 讓 focused smoke 假綠破功。
- 「focused smoke 偷換全綠」成為明確紅線案例。

### v4.3
- `KnowledgeBaseManager` deprecation suppress hotfix 回綠。
- editor split、rebase apply、Epic 3 proposal、Windows gotchas 首次被拉成主線。

## 關鍵閉環摘要

- **API 安全**：`T-CLIENT-AUTH` 已落 bearer API key 到寫入端點；rate-limit / CORS / body limit / metrics 全綠。
- **Citation / Audit**：Epic 3、Epic 4 規格與實作已閉，含 citation metadata、verify flow、citation checker、fact checker、auditor aggregation。
- **KB 治理**：Epic 5 proposal / tasks / specs 齊，`corpus_provenance`、only-real rebuild、post-rebuild verify 已落。
- **胖檔治理**：已完成多輪 split，包含 `config_tools`、`realtime_lookup`、`e2e_rewrite`、`agents route`、`middleware`、`generate/export`；v6.4 後 `src/` 無 Python 檔 > 400 以上的 god-file cluster 已從 8 檔收斂至 4 檔。
- **資料源**：`FDA` live 修復、`PCC` adapter 落地、`datagovtw` 改抓真實公文、corpus 擴到 173。
- **Spectra**: 5/5 Epic proposal / tasks / specs 全齊（2026-04-21 達成首度 100% 覆蓋）。

## 導覽

- 目前活任務：`program.md`
- 逐輪事實：`results.log`
- 早期反思封存：`docs/archive/engineer-log-202604*.md`
