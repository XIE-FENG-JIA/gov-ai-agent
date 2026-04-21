# Program History Archive — 202604g

封存時間：2026-04-21

用途：
- 保留從 `program.md` 移出的舊 review header、舊 P0/P1 bundle、早期完成清單。
- 主檔改成「現況 + 活任務」後，這裡承接歷史脈絡。
- 需要逐字原貌時，請再配合 git history；本檔以可讀摘要為主。

## 封存範圍

- `v5.4`、`v5.3`、`v5.2`、`v5.1`
- `v4.9`、`v4.8`、`v4.7`、`v4.6`、`v4.4`、`v4.3`
- 舊 P0/P1 bundle：client auth、Epic 4 proposal、fat-file rotate 舊輪次、log archive 舊輪次、Epic 8 KB split、integration gate、writer failure matrix、FF hotfix、Epic 2 finish、full pytest、console import、rebase/admin ACL、live-ingest/corpus cleanup、Epic 3 proposal、Windows gotchas、早期 P0.J/P0.K/P0.L/P0.M/P0.N 與 `P0.歷史` 段。

## 歷史快照

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

- **API 安全**：`T-CLIENT-AUTH` 已落 bearer API key 到寫入端點。
- **Citation / Audit**：Epic 3、Epic 4 規格與實作已閉，含 citation metadata、verify flow、citation checker、fact checker、auditor aggregation。
- **KB 治理**：Epic 5 proposal / tasks / specs 齊，`corpus_provenance`、only-real rebuild、post-rebuild verify 已落。
- **胖檔治理**：已完成多輪 split，包含 `config_tools`、`realtime_lookup`、`e2e_rewrite`、`agents route`、`middleware`。
- **資料源**：`FDA` live 修復、`PCC` adapter 落地、`datagovtw` 改抓真實公文、corpus 擴到 173。

## 導覽

- 目前活任務：`program.md`
- 逐輪事實：`results.log`
- 早期反思封存：`docs/archive/engineer-log-202604*.md`
