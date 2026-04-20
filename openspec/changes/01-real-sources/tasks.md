# Tasks: 01-real-sources

- [x] **T1.1** Finalize source-onboarding spec and task map for the first three public sources.  
  Requirements:
  - The first approved source set is intentionally narrow
  Validation: `spectra status --change 01-real-sources` shows `✓ specs` and `✓ tasks`  
  Commit: `docs(spec): 01-real-sources add specs/sources + tasks.md`

- [x] **T1.2** Implement `PublicGovDoc` as the normalized real-source document model in `src/core/models.py`.  
  Requirements:
  - Normalized real-source documents preserve provenance
  Validation: `pytest tests/test_core.py -q`  
  Commit: `feat(core): add PublicGovDoc model for real public sources`

- [x] **T1.3** Implement `BaseSourceAdapter` as the shared source contract in `src/sources/base.py`.  
  Requirements:
  - Source adapters use one shared contract
  Validation: `pytest tests/test_sources_base.py -q`  
  Commit: `feat(sources): add base adapter contract for public sources`

- [x] **T1.4** Implement `MojLawAdapter` list/fetch/normalize with recorded fixtures.  
  Requirements:
  - The first approved source set is intentionally narrow
  - Source adapters use one shared contract
  - Normalized real-source documents preserve provenance
  Validation: `pytest tests/test_mojlaw_adapter.py -q`  
  Commit: `feat(sources): implement MojLawAdapter with real fixtures`

- [x] **T1.5** Implement `DataGovTwAdapter` list/fetch/normalize with recorded fixtures.  
  Requirements:
  - The first approved source set is intentionally narrow
  - Source adapters use one shared contract
  - Normalized real-source documents preserve provenance
  Validation: `pytest tests/test_datagovtw_adapter.py -q`  
  Commit: `feat(sources): implement DataGovTwAdapter with real fixtures`

- [x] **T1.6** Implement `ExecutiveYuanRssAdapter` for public Executive Yuan announcements.  
  Requirements:
  - The first approved source set is intentionally narrow
  - Source adapters use one shared contract
  - Normalized real-source documents preserve provenance
  Validation: `pytest tests/test_executive_yuan_rss_adapter.py -q`  
  Commit: `feat(sources): implement ExecutiveYuanRssAdapter`

- [x] **T1.7** Implement `MohwRssAdapter` for Ministry of Health and Welfare public notices.  
  Requirements:
  - Source adapters use one shared contract
  - Normalized real-source documents preserve provenance
  Validation: `pytest tests/test_mohw_rss_adapter.py -q`  
  Commit: `feat(sources): implement MohwRssAdapter`

- [x] **T1.8** Implement `FdaApiAdapter` for Food and Drug Administration public notices.  
  Requirements:
  - Source adapters use one shared contract
  - Normalized real-source documents preserve provenance
  Validation: `pytest tests/test_fda_api_adapter.py -q`  
  Commit: `feat(sources): implement FdaApiAdapter`

- [x] **T1.9** Build `src/sources/ingest.py` to persist raw snapshots and normalized markdown corpus entries.  
  Requirements:
  - Normalized real-source documents preserve provenance
  - Real-source ingestion follows public-data compliance rules
  - Synthetic content stays outside real-source retrieval
  Validation: `pytest tests/test_sources_ingest.py -q`  
  Commit: `feat(sources): add minimal ingest pipeline for public sources`

- [x] **T1.10** Wire CLI ingest entrypoints for one-source and all-source incremental runs.  
  Requirements:
  - Real-source ingestion follows public-data compliance rules
  - Synthetic content stays outside real-source retrieval
  Validation: `pytest tests/test_sources_cli.py -q`  
  Commit: `feat(cli): wire public source ingest commands`

## Requirement Mapping

- Requirement: Source adapters use one shared contract
  Tasks: `T1.3`

- Requirement: Normalized real-source documents preserve provenance
  Tasks: `T1.2`, `T1.9`

- Requirement: Real-source ingestion follows public-data compliance rules
  Tasks: `T1.1`, `T1.9`, `T1.10`

- Requirement: Synthetic content stays outside real-source retrieval
  Tasks: `T1.9`, `T1.10`

- Requirement: The first approved source set is intentionally narrow
  Tasks: `T1.1`, `T1.4`, `T1.5`, `T1.6`
