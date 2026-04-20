# Tasks: 03-citation-tw-format

- [x] **T3.0** Finalize the citation-format change package with proposal, tasks,
  and spec coverage for Taiwan public-document output.
  Requirements:
  - Citation output uses one canonical section marker
  Validation: `spectra analyze 03-citation-tw-format`
  Commit: `docs(spec): bootstrap citation format change`
  - **完成（2026-04-21 01:47）**：`openspec/changes/03-citation-tw-format/{proposal.md,tasks.md,specs/citation/spec.md}` 已齊，且 `spectra analyze 03-citation-tw-format` = 0 findings；change package 現在具備 proposal/spec/tasks coverage，可作為 Epic 3 後續 formatter/exporter/verify 實作的唯一契約來源。

- [x] **T3.1** Add a repo-owned citation formatter seam that can assemble the
  canonical `## 引用來源` block from reviewed evidence.
  Requirements:
  - Citation output uses one canonical section marker
  - Citation metadata survives across generation and export
  Validation: `pytest tests/test_citation_level.py tests/test_citation_quality.py -q`
  Commit: `feat(citation): add citation formatter seam`
  - **完成（2026-04-20 21:37）**：新增 `src/document/citation_formatter.py`，把引用段 heading 與 line/block 組裝集中到 repo-owned seam；`src/agents/writer/cite.py` 改為委派此 formatter，保留現行輸出契約並讓後續 markdown / DOCX export 共用同一組 citation 組裝邏輯。驗證 `pytest tests/test_citation_level.py tests/test_citation_quality.py -q` = 48 passed，另 `pytest tests/test_writer_agent.py tests/test_agents.py -q` = 58 passed

- [x] **T3.2** Wire markdown and DOCX export paths so the same reviewed citation
  payload populates `## 引用來源` and document metadata.
  Requirements:
  - Citation metadata survives across generation and export
  - DOCX export preserves citation verification metadata
  Validation: `pytest tests/test_document.py tests/test_exporter_extended.py -q`
  Commit: `feat(exporter): preserve citation metadata in docx export`
  - **完成（2026-04-21 01:33）**：`DocxExporter` 新增 citation export metadata 組裝與 DOCX custom properties 寫入，落地 `source_doc_ids` / `citation_count` / `ai_generated` / `engine`，並附帶 `citation_sources_json` 供後續 verify flow 讀取；`generate` 匯出路徑同步傳入 reviewed source list 與 engine，讓同一批 reviewed evidence 同時落在 markdown 引用段與 docx metadata。驗證 `pytest tests/test_export_citation_metadata.py tests/test_document.py tests/test_exporter_extended.py -q` = 78 passed

- [x] **T3.3** Define and implement exported metadata keys
  `source_doc_ids`, `citation_count`, `ai_generated`, and `engine`.
  Requirements:
  - Citation metadata survives across generation and export
  - DOCX export preserves citation verification metadata
  Validation: `pytest tests/test_document.py tests/test_cli_commands.py -q -k "stamp or verify"`
  Commit: `feat(document): record citation metadata fields`
  - **完成（2026-04-21 01:40）**：新增 `src/document/citation_metadata.py`，把 citation export metadata keys、reference parsing、reviewed-source matching 與 DOCX custom-properties readback 收斂成 repo-owned schema；`DocxExporter` 改委派同一套 builder，讓後續 verify flow 可直接讀取 `source_doc_ids` / `citation_count` / `ai_generated` / `engine` / `citation_sources_json`。驗證 `pytest tests/test_document.py tests/test_cli_commands.py -q -k "stamp or verify"` = 11 passed，另 `pytest tests/test_export_citation_metadata.py tests/test_document.py tests/test_exporter_extended.py -q` = 79 passed

- [x] **T3.4** Add a repo-owned `gov-ai verify <docx>` path that checks exported
  citation metadata and source references against repo evidence.
  Requirements:
  - Verify flow compares exported docx state against knowledge-base evidence
  Validation: `pytest tests/test_cli_commands.py -q -k verify`
  Commit: `feat(cli): add exported docx citation verification`
  - **完成（2026-04-21 01:43）**：新增 `src/cli/verify_cmd.py`，讀取 DOCX custom properties 的 citation metadata，並掃描 `kb_data/corpus/**/*.md` frontmatter，依 `source_doc_id` / `source_url` / `title` 比對 repo evidence；缺 metadata 或找不到 corpus 對應時明確 FAIL。驗證 `pytest tests/test_cli_commands.py -q -k verify` 通過

- [x] **T3.5** Requirement coverage: Citation output uses one canonical section
  marker is satisfied by `T3.0`, `T3.1`, and `T3.2`.
  Validation: `spectra analyze 03-citation-tw-format`
  - **完成（2026-04-21 01:47）**：`spectra analyze 03-citation-tw-format` = 0 findings，確認 canonical `## 引用來源` requirement 已由 `T3.0` / `T3.1` / `T3.2` 完整覆蓋，無缺口與模糊 requirement 漏洞。

- [x] **T3.6** Requirement coverage: Citation metadata survives across
  generation and export is satisfied by `T3.1`, `T3.2`, and `T3.3`.
  Validation: `spectra analyze 03-citation-tw-format`
  - **完成（2026-04-21 01:47）**：`spectra analyze 03-citation-tw-format` = 0 findings，確認 citation metadata persistence requirement 已由 formatter / exporter / metadata readback 三段 seam 對齊。

- [x] **T3.7** Requirement coverage: DOCX export preserves citation verification
  metadata is satisfied by `T3.2` and `T3.3`.
  Validation: `spectra analyze 03-citation-tw-format`
  - **完成（2026-04-21 01:47）**：`spectra analyze 03-citation-tw-format` = 0 findings，確認 DOCX custom-properties verification metadata requirement 已被 `T3.2` / `T3.3` 收斂，不再需要額外 spec 補洞。

- [x] **T3.8** Requirement coverage: Verify flow compares exported docx state
  against knowledge-base evidence is satisfied by `T3.3` and `T3.4`.
  Validation: `spectra analyze 03-citation-tw-format`
  - **完成（2026-04-21 01:47）**：`spectra analyze 03-citation-tw-format` = 0 findings，確認 `gov-ai verify <docx>` 與 exported metadata readback 已覆蓋 verify-vs-repo-evidence requirement。

## Requirement Mapping

- Requirement: Citation output uses one canonical section marker
  Tasks: `T3.0`, `T3.1`, `T3.2`, `T3.5`

- Requirement: Citation metadata survives across generation and export
  Tasks: `T3.1`, `T3.2`, `T3.3`, `T3.6`

- Requirement: DOCX export preserves citation verification metadata
  Tasks: `T3.2`, `T3.3`, `T3.7`

- Requirement: Verify flow compares exported docx state against knowledge-base evidence
  Tasks: `T3.3`, `T3.4`, `T3.8`
