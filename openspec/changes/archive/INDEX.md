# OpenSpec Changes Archive Index

This index records all completed and archived openspec change sets.

| ID | Archived Date | Summary | Tasks | Status |
|----|--------------|---------|-------|--------|
| 01-real-sources | 2026-04-25 | 真實公開公文來源整合契約（PublicGovDoc model / BaseSourceAdapter / 5 adapters / ingest pipeline / CLI） | T1.1–T1.15 | 100% (15/15) |
| 02-open-notebook-fork | 2026-04-25 | open-notebook fork 整合邊界定義（vendor import / ask-service adapter / fallback / freeze gate） | T2.0–T2.14 | 100% (15/15) |
| 03-citation-tw-format | 2026-04-25 | 台灣公文引用格式標準化（citation_formatter / DOCX export / metadata keys / verify CLI） | T3.0–T3.8 | 100% (9/9) |
| 04-audit-citation | 2026-04-25 | 引用稽核流程強化（citation_checker / fact_checker tighten / auditor aggregation / failure matrix） | T4.0–T4.7 | 100% (8/8) |
| 05-kb-governance | 2026-04-25 | 知識庫治理規則落地（corpus eligibility / live-ingest retirement / only-real rebuild / post-rebuild verify） | T5.0–T5.7 | 100% (8/8) |
| 06-live-ingest-quality-gate | 2026-04-25 | 即時擷取品質閘門（QualityGate.evaluate / 4 named failures / gate-check CLI / --quality-gate flag / failure matrix doc） | T-LIQG-0–T-LIQG-12 | 100% (13/13) |
| 07-auto-commit-semantic-enforce | 2026-04-25 | 自動提交語意驗證強化（validate_auto_commit_msg / 8 test cases / runtime-seat enforce / sensor soft gate 0.9） | T7.1–T7.5 | 100% (5/5) |
| 08-bare-except-audit-iter6 | 2026-04-25 | 裸 except 稽核第六刀（compliance_checker / editor / workflow endpoints / config_tools / reviewers / _manager_hybrid typed buckets） | T8.1–T8.7 | 100% (7/7) |
| 09-fat-rotate-iter3 | 2026-04-25 | 肥大模組旋轉第三輪（kb/rebuild 572→190 / datagovtw 410→split / routes/agents 397→split；全 ≤300 lines） | T9.1–T9.5 | 100% (5/5) |
| 10-test-local-binding-audit-systematic | 2026-04-25 | 測試 local binding 系統化稽核（audit_local_binding.py AST / rebind_local helper / CONTRIBUTING mock rules / taxonomy doc） | T10.1–T10.6 | 100% (6/6) |
| 11-bare-except-iter6-regression | 2026-04-25 | 裸 except iter6 回歸修復（writer/editor/fact_checker typed bucket 加 RuntimeError/ConnectionError；3949 passed） | T11.1–T11.5 | 100% (5/5) |
| 12-commit-msg-noise-floor | 2026-04-25 | 提交訊息噪音下限（commit_msg_lint reject pseudo-semantic / wrapper 升級 chore(auto-engineer): patch 格式 / 30-commit 驗證 0 violations） | T12.1–T12.5 | 100% (5/5) |
| 13-cli-fat-rotate-v3 | 2026-04-26 | CLI fat-rotate v3（utils god-object split / Track B shared services / micro-file mergers / full regression gate） | T13.1a–T13.7 | 100% (14/14) |
| 14-13-acceptance-audit | 2026-04-26 | Change 13 acceptance audit（gap evidence / remediation paths / red-line v8 wrapper structural payload） | T14.1–T14.5 | 100% (5/5) |
| 15-pytest-runtime-regression-iter7 | 2026-04-26 | pytest runtime regression iter7（LOOP5 drift 315s→median 189.81s；-n auto→-n 8；red-line v9 two-baseline median） | T15.1–T15.5 | 100% (5/5) |
| 16-regulation-doc-type-mapping | 2026-04-26 | 公文種類對應規範（kb_data/regulation_doc_type_mapping.yaml schema contract；7 schema+roundtrip tests） | T16.1–T16.3 | 100% (3/3) |
| 17-embedding-provider-rest-fallback | 2026-04-26 | Embedding provider REST fallback（OpenRouter REST shim / embedding_provider config / EmbeddingError typed / REST+litellm dual path） | T17.1–T17.3 | 100% (3/3) |
| 18-multi-llm-provider-abstraction | 2026-04-26 | 多 LLM provider 抽象（LLMProvider protocol / LiteLLM + OpenRouter providers / make_provider factory / core llm delegation / provider tests） | T18.1–T18.6 | 100% (6/6) |
| 19-kb-recall-validation-pipeline | 2026-04-27 | KB recall 驗證管線（eval set 35 筆 / eval_recall.py recall@1/3/5 / recall_baseline ratchet / sensor soft violation / unit tests 12 cases / CI integration） | T19.1–T19.6 | 100% (6/6) |
| 20-pytest-runtime-regression-guard | 2026-04-27 | pytest runtime 回歸守衛（measure_pytest_runtime.py / ceiling ratchet-down / sensor check_pytest_runtime / 8 unit tests / CONTRIBUTING docs） | T20.1–T20.5 | 100% (5/5) |
| 21-cold-runtime-root-cause-fix | 2026-04-27 | cold runtime 根因修復（real baseline measurement / --durations=10 profile / top-3 slow test fix / sensor ceiling activation） | T21.1–T21.5 | 100% (5/5) |

| 22-source-adapter-health-metrics | 2026-04-27 | Source adapter health metrics（adapter_health.py probe / dry-fetch limit=3 / sensor adapter_health field / soft violation on zero-count / 6 unit tests / CONTRIBUTING docs） | T22.1–T22.6 | 100% (6/6) |
| 23-realtime-law-disable-test-fix | 2026-04-27 | Realtime law disable test fix（`GOVAI_DISABLE_REALTIME_LAW` bypass 診斷 + `_clear_caches` monkeypatch 修復 / 48 passed） | T23.1–T23.4 | 100% (4/4) |
| 24-cli-output-json-mode | 2026-04-27 | CLI 統一 JSON 輸出模式（lint/cite/verify/kb-search 加 `--format json` / schema 驗證 tests / CONTRIBUTING 節） | T24.1–T24.5 | 100% (5/5) |

## Active Epics

| ID | Created | Summary | Tasks | Status |
|----|---------|---------|-------|--------|
| 25-cli-stats-status-json | 2026-04-27 | CLI stats/status JSON 輸出模式（stats/status 加 `--format json` / schema 驗證 tests / CONTRIBUTING 補節） | T25.1–T25.5 | active |

## Notes

- Promoted specs are in `openspec/specs/<capability>/spec.md`.
- Archive folder naming: `<YYYY-MM-DD>-<change-id>/`.
