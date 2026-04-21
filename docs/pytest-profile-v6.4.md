# Pytest Profile v6.4

Generated on 2026-04-22 from:

```bash
python -m pytest tests/ --ignore=tests/integration --durations=30
```

Result:

- 3741 passed
- Total runtime: 841.51s wall time (`0:14:01`)
- Recent `-x` baseline on the same day: 870.87s (`0:14:30`)

## Slowest 30 tests

1. `tests/test_cite_cmd.py::TestCiteCLI::test_main_help_survives_cp950_console` — 28.84s
2. `tests/test_edge_cases.py::TestKBEdgeCases::test_search_very_long_string` — 22.50s
3. `tests/test_agents_extended.py::TestMeetingExportFailure::test_meeting_exporter_failure_returns_error` — 18.00s
4. `tests/test_fetchers.py::TestJudicialFetcher::test_fetch_basic` — 14.03s
5. `tests/test_e2e.py::TestScenario8_ParallelReviewTimeout::test_parallel_review_with_agent_exception` — 9.61s
6. `tests/test_agents_extended.py::TestEditorParallelEdgeCases::test_all_agents_fail` — 9.60s
7. `tests/test_agents_extended.py::TestEditorSafeLowNoRefine::test_safe_score_no_auto_refine` — 9.43s
8. `tests/test_robustness.py::TestDefaultFailedScoreExclusion::test_failed_agent_excluded_from_weighted_average` — 9.27s
9. `tests/test_fetchers.py::TestOpenDataFetcher::test_network_error` — 7.03s
10. `tests/test_fetchers.py::TestGazetteFetcherBulk::test_fetch_bulk_network_error` — 7.01s
11. `tests/test_fetchers.py::TestGazetteFetcher::test_network_error` — 7.01s
12. `tests/test_fetchers.py::TestLawFetcher::test_fetch_network_error` — 7.01s
13. `tests/test_cli_commands.py::TestWebUI::test_web_ui_kb` — 6.89s
14. `tests/test_api_server.py::TestWebUIGenerate::test_generate_post_returns_result` — 6.85s
15. `tests/test_cli_commands.py::TestWebUI::test_web_ui_config` — 6.43s
16. `tests/test_fetchers.py::TestNewFetcherCLI::test_fetch_procurement_cli` — 6.17s
17. `tests/test_mark_synthetic.py::test_repo_examples_corpus_count_and_flags_are_stable` — 6.05s
18. `tests/test_fetchers.py::TestProcurementFetcher::test_fetch_empty` — 6.02s
19. `tests/test_fetchers.py::TestExamYuanFetcher::test_fetch_from_category_fallback` — 6.02s
20. `tests/test_api_server.py::TestWebUIGenerate::test_generate_post_with_doc_type` — 6.00s
21. `tests/test_edge_cases.py::TestKBEdgeCases::test_search_empty_string` — 5.25s
22. `tests/test_e2e.py::TestUserSimulation::test_scenario_batch_mixed_types` — 5.22s
23. `tests/test_cli_commands.py::TestSwitchCommand::test_switch_direct_provider` — 4.55s
24. `tests/test_cli_commands.py::TestSwitchCommand::test_switch_adds_ollama_if_missing` — 4.41s
25. `tests/test_fetchers.py::TestInterpretationFetcher::test_fetch_basic` — 4.06s
26. `tests/test_e2e.py::TestIntegration::test_multiple_doc_types_in_sequence` — 4.05s
27. `tests/test_e2e.py::TestFullIntegrationFlow::test_multi_doc_type_full_flow` — 3.94s
28. `tests/test_e2e.py::TestScenario4_KnowledgeBase::test_kb_reset` — 2.66s
29. `tests/test_agents_extended.py::TestWriteMetaInfoStopConditions::test_both_attachment_keys_in_exporter` — 2.64s
30. `tests/test_e2e.py::TestScenario1_GenerateHan::test_full_han_pipeline` — 2.62s

## Hotspot clusters

- Console/encoding path: `test_main_help_survives_cp950_console` alone costs 28.84s.
- KB search path: `test_search_very_long_string` and `test_search_empty_string` cost 27.75s combined.
- Failure/timeout paths in agents and E2E cost about 55s across the top 8 entries.
- Fetcher network-error tests appear repeatedly at ~7s each, which suggests retry or timeout defaults are too large for mocked failure paths.
- Web UI end-to-end tests add ~26s across five entries.

## Next cuts

1. Reduce default timeout/retry values in mocked network-failure tests, especially fetchers near 7s each.
2. Inspect `tests/test_cite_cmd.py::TestCiteCLI::test_main_help_survives_cp950_console` for avoidable process startup or console wait cost.
3. Profile KB search guards for empty/very-long input before expensive retrieval work begins.
4. Split a fast smoke lane from timeout-heavy E2E/agent failure cases so default local CI does not always pay the slowest path.
