# Tasks: 03-citation-tw-format

- [ ] **T3.0** Finalize the citation-format change package with proposal, tasks,
  and spec coverage for Taiwan public-document output.
  Requirements:
  - Citation output uses one canonical section marker
  Validation: `spectra analyze 03-citation-tw-format`
  Commit: `docs(spec): bootstrap citation format change`

- [ ] **T3.1** Add a repo-owned citation formatter seam that can assemble the
  canonical `## 引用來源` block from reviewed evidence.
  Requirements:
  - Citation output uses one canonical section marker
  - Citation metadata survives across generation and export
  Validation: `pytest tests/test_citation_level.py tests/test_citation_quality.py -q`
  Commit: `feat(citation): add citation formatter seam`

- [ ] **T3.2** Wire markdown and DOCX export paths so the same reviewed citation
  payload populates `## 引用來源` and document metadata.
  Requirements:
  - Citation metadata survives across generation and export
  - DOCX export preserves citation verification metadata
  Validation: `pytest tests/test_document.py tests/test_exporter_extended.py -q`
  Commit: `feat(exporter): preserve citation metadata in docx export`

- [ ] **T3.3** Define and implement exported metadata keys
  `source_doc_ids`, `citation_count`, `ai_generated`, and `engine`.
  Requirements:
  - Citation metadata survives across generation and export
  - DOCX export preserves citation verification metadata
  Validation: `pytest tests/test_document.py tests/test_cli_commands.py -q -k "stamp or verify"`
  Commit: `feat(document): record citation metadata fields`

- [ ] **T3.4** Add a repo-owned `gov-ai verify <docx>` path that checks exported
  citation metadata and source references against repo evidence.
  Requirements:
  - Verify flow compares exported docx state against knowledge-base evidence
  Validation: `pytest tests/test_cli_commands.py -q -k verify`
  Commit: `feat(cli): add exported docx citation verification`

- [ ] **T3.5** Requirement coverage: Citation output uses one canonical section
  marker is satisfied by `T3.0`, `T3.1`, and `T3.2`.
  Validation: `spectra analyze 03-citation-tw-format`

- [ ] **T3.6** Requirement coverage: Citation metadata survives across
  generation and export is satisfied by `T3.1`, `T3.2`, and `T3.3`.
  Validation: `spectra analyze 03-citation-tw-format`

- [ ] **T3.7** Requirement coverage: DOCX export preserves citation verification
  metadata is satisfied by `T3.2` and `T3.3`.
  Validation: `spectra analyze 03-citation-tw-format`

- [ ] **T3.8** Requirement coverage: Verify flow compares exported docx state
  against knowledge-base evidence is satisfied by `T3.3` and `T3.4`.
  Validation: `spectra analyze 03-citation-tw-format`

## Requirement Mapping

- Requirement: Citation output uses one canonical section marker
  Tasks: `T3.0`, `T3.1`, `T3.2`, `T3.5`

- Requirement: Citation metadata survives across generation and export
  Tasks: `T3.1`, `T3.2`, `T3.3`, `T3.6`

- Requirement: DOCX export preserves citation verification metadata
  Tasks: `T3.2`, `T3.3`, `T3.7`

- Requirement: Verify flow compares exported docx state against knowledge-base evidence
  Tasks: `T3.3`, `T3.4`, `T3.8`
