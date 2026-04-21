# Tasks: 04-audit-citation

- [x] **T4.0** Finalize the citation-audit change package with proposal, tasks,
  and spec coverage for the Epic 4 review boundary.
  Requirements:
  - Citation audit stays repo-owned and source-grounded
  - Citation audit failures fail loudly before export handoff
  Validation: `spectra analyze 04-audit-citation`
  Commit: `docs(spec): bootstrap citation audit change`

- [x] **T4.1** Add a repo-owned `src/agents/citation_checker.py` seam for
  citation traceability review.
  Requirements:
  - Citation audit stays repo-owned and source-grounded
  Validation: `pytest tests/test_citation_level.py tests/test_validators.py -q`
  Commit: `feat(agents): add citation checker seam`
  - **完成（2026-04-21 11:27）**：新增 `src/agents/citation_checker.py`，以 repo-owned 規則檢查 citation level / evidence presence / citation integrity，並補 traceability guard：參考來源定義無法解析或缺少 `URL/Hash` 時直接報錯；同步匯出 `CitationChecker` 並補 `tests/test_citation_level.py` seam 測試。驗證 `python -m pytest tests/test_citation_level.py tests/test_validators.py -q` = 111 passed

- [x] **T4.2** Strengthen `src/agents/fact_checker.py` so legal-claim review
  consumes repo evidence and `realtime_lookup` results without silently
  downgrading citation failures.
  Requirements:
  - Citation audit uses repo evidence and verification state
  Validation: `pytest tests/test_fact_checker_coverage.py tests/test_fact_checker_enhanced.py tests/test_realtime_lookup.py -q`
  Commit: `feat(agents): tighten fact checker citation verification`
  - **完成（2026-04-21 12:16）**：`FactChecker` 現改為先產生 repo-owned citation finding，再讓 LLM 補日期/數字類問題；當 `realtime_lookup` 掛掉或 law cache 為空時，會留下單一 loud-failure error，不再靜默降級；只有具體法規引用才會升格成「法規不存在 / 條號不存在 / 缺少 repo evidence」finding，generic placeholder（如「相關法規」）不再誤判。新增回歸測試覆蓋 verifier failure、repo-owned nonexistent-law error、missing repo evidence warning、reference match、generic placeholder guard。驗證 `python -m pytest tests/test_fact_checker_coverage.py tests/test_fact_checker_enhanced.py tests/test_realtime_lookup.py -q` = 91 passed

- [ ] **T4.3** Integrate citation-checker findings into
  `src/agents/auditor.py` and downstream audit aggregation.
  Requirements:
  - Citation audit failures fail loudly before export handoff
  Validation: `pytest tests/test_editor.py tests/test_editor_coverage.py tests/test_review_parser.py -q`
  Commit: `feat(auditor): aggregate citation audit results`

- [ ] **T4.4** Add a citation-audit failure matrix covering orphan footnotes,
  missing evidence, unverifiable legal claims, and degraded verification
  upstreams.
  Requirements:
  - Citation audit failures fail loudly before export handoff
  Validation: `pytest tests/test_validators.py tests/test_fact_checker_enhanced.py tests/test_writer_agent_failure.py -q`
  Commit: `test(audit): cover citation audit failure matrix`

- [ ] **T4.5** Requirement coverage: repo-owned citation audit is satisfied by
  `T4.0`, `T4.1`, and `T4.3`.
  Validation: `spectra analyze 04-audit-citation`

- [ ] **T4.6** Requirement coverage: citation audit uses repo evidence and
  verification state is satisfied by `T4.1`, `T4.2`, and `T4.4`.
  Validation: `spectra analyze 04-audit-citation`

- [ ] **T4.7** Requirement coverage: citation audit failures fail loudly before
  export handoff is satisfied by `T4.2`, `T4.3`, and `T4.4`.
  Validation: `spectra analyze 04-audit-citation`

## Requirement Mapping

- Requirement: Citation audit stays repo-owned and source-grounded
  Tasks: `T4.0`, `T4.1`, `T4.3`, `T4.5`

- Requirement: Citation audit uses repo evidence and verification state
  Tasks: `T4.1`, `T4.2`, `T4.4`, `T4.6`

- Requirement: Citation audit failures fail loudly before export handoff
  Tasks: `T4.0`, `T4.2`, `T4.3`, `T4.4`, `T4.7`
