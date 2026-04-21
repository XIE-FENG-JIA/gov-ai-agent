# Tasks: 05-kb-governance

- [x] **T5.0** Finalize the knowledge-base governance change package with
  proposal, tasks, and spec coverage for Epic 5.
  Requirements:
  - Active retrieval excludes synthetic or fixture-backed corpus entries
  - Live ingest and retirement rules fail loudly and leave audit evidence
  - Only-real rebuilds require explicit post-rebuild verification
  Validation: `spectra analyze 05-kb-governance`
  Commit: `docs(spec): bootstrap kb governance change`

- [x] **T5.1** Consolidate corpus-eligibility helpers so rebuild, rewrite, and
  verify share one repo-owned rule for excluding `synthetic` and
  `fixture_fallback` corpus entries.
  Requirements:
  - Active retrieval excludes synthetic or fixture-backed corpus entries
  Validation: `python -m pytest tests/test_corpus_provenance_guard.py tests/test_cli_commands.py -q -k "verify or kb_rebuild"`
  Commit: `refactor(kb): centralize active corpus eligibility rules`

- [x] **T5.2** Harden live-ingest governance so `--require-live` failures leave
  clear retirement/archive evidence whenever a source falls back to fixtures.
  Requirements:
  - Live ingest and retirement rules fail loudly and leave audit evidence
  Validation: `python -m pytest tests/test_live_ingest_script.py tests/test_sources_ingest.py -q`
  Commit: `feat(kb): record loud fixture-fallback retirement outcomes`

- [ ] **T5.3** Enforce `gov-ai kb rebuild --only-real` as the operational path
  for real-source index rebuilds and report imported vs skipped provenance
  counts.
  Requirements:
  - Active retrieval excludes synthetic or fixture-backed corpus entries
  - Only-real rebuilds require explicit post-rebuild verification
  Validation: `python -m pytest tests/test_cli_commands.py tests/test_knowledge.py -q -k "kb_rebuild or stats"`
  Commit: `feat(kb): harden only-real rebuild reporting`

- [ ] **T5.4** Add a post-rebuild verification step that proves exported
  citation metadata still resolves only to active repo evidence after an
  `--only-real` rebuild.
  Requirements:
  - Only-real rebuilds require explicit post-rebuild verification
  Validation: `python -m pytest tests/test_cli_commands.py tests/test_e2e_rewrite.py tests/test_corpus_provenance_guard.py -q -k "verify or rebuild or provenance"`
  Commit: `test(kb): verify only-real rebuild evidence integrity`

- [ ] **T5.5** Requirement coverage: Active retrieval excludes synthetic or fixture-backed corpus entries is satisfied by `T5.0`, `T5.1`, and `T5.3`.
  Requirements:
  - Active retrieval excludes synthetic or fixture-backed corpus entries
  Validation: `spectra analyze 05-kb-governance`

- [ ] **T5.6** Requirement coverage: Live ingest and retirement rules fail loudly and leave audit evidence is satisfied by `T5.0` and `T5.2`.
  Requirements:
  - Live ingest and retirement rules fail loudly and leave audit evidence
  Validation: `spectra analyze 05-kb-governance`

- [ ] **T5.7** Requirement coverage: Only-real rebuilds require explicit post-rebuild verification is satisfied by `T5.0`, `T5.3`, and `T5.4`.
  Requirements:
  - Only-real rebuilds require explicit post-rebuild verification
  Validation: `spectra analyze 05-kb-governance`

## Requirement Mapping

- Requirement: Active retrieval excludes synthetic or fixture-backed corpus entries
  Tasks: `T5.0`, `T5.1`, `T5.3`, `T5.5`

- Requirement: Live ingest and retirement rules fail loudly and leave audit evidence
  Tasks: `T5.0`, `T5.2`, `T5.6`

- Requirement: Only-real rebuilds require explicit post-rebuild verification
  Tasks: `T5.0`, `T5.3`, `T5.4`, `T5.7`
