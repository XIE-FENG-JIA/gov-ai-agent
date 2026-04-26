# Pytest Runtime Profile — v8.16

> Generated: 2026-04-27 (Epic 21 T21.2)

## Summary

- **Runtime**: 50.70s (4039 passed, 8 workers, `pytest-xdist -n auto`)
- **Baseline**: ceiling_s=76.05, last_s=50.70, tolerance=0.20
- **Sensor status**: `ok` (last_s 50.70 ≤ ceiling 76.05)

## Top-10 Slowest Tests

| Rank | Duration | Test |
|------|----------|------|
| 1 | 8.91s | `tests/test_cli_commands.py::TestSwitchCommand::test_switch_adds_ollama_if_missing` |
| 2 | 6.86s | `tests/test_cli_commands.py::TestDoctorCommand::test_doctor_runs` |
| 3 | 5.54s | `tests/test_sensor_refresh.py::test_auto_commit_rate_semantic_vs_checkpoint` |
| 4 | 5.08s | `tests/test_quickstart.py::TestDoctor::test_doctor_all_ok` |
| 5 | 3.73s | `tests/test_sensor_refresh.py::test_marked_done_uncommitted_slug_in_commits` |
| 6 | 2.12s | `tests/test_sensor_refresh.py::test_main_exit_code_clean` |
| 7 | 1.72s | `tests/test_agents_extended.py::TestExporterAutoCreateDir::test_existing_directory_no_error` |
| 8 | 1.72s | `tests/test_cli_commands.py::TestHistoryCommand::test_history_list_empty` |
| 9 | 1.72s | `tests/test_cli_commands.py::TestKBCommands::test_kb_rebuild_reindexes_standard_collections` |
| 10 | 1.72s | `tests/test_check_acl_state.py::test_get_current_token_sids_includes_user` |

## Root-Cause Classification

| Test | Duration | Root Cause |
|------|----------|-----------|
| `test_switch_adds_ollama_if_missing` | 8.91s | CLI command with real subprocess/config write; fixture overhead |
| `test_doctor_runs` | 6.86s | Doctor CLI runs multiple health checks serially |
| `test_auto_commit_rate_semantic_vs_checkpoint` | 5.54s | Git subprocess calls in sensor refresh test |
| `test_doctor_all_ok` | 5.08s | Quickstart doctor — similar to above |
| `test_marked_done_uncommitted_slug_in_commits` | 3.73s | Git log subprocess in sensor test |
| `test_main_exit_code_clean` | 2.12s | Full sensor refresh with git subprocess |
| Multiple 1.72s entries | 1.72s | Jieba model load on first fixture setup (shared across workers) |

## Findings

1. **Top slow tests are CLI/git subprocess calls** — not chromadb cold-cache
2. **Jieba model load (~1.7s)** appears multiple times as `setup` cost
   - This is a shared-worker artifact: first test in each xdist worker loads jieba
   - With 8 workers, jieba is loaded up to 8 times in parallel (no shared cache)
3. **Sensor tests with git subprocess** account for 3 of top 6 slow tests

## Bugs Fixed (T21.3)

During profiling, 9 pre-existing test failures were discovered and fixed:

### Bug 1: `src/cli/utils_io.py` — missing `import yaml`
- **Impact**: 8 tests failing (`TestSafeConfigWrite` × 5, `TestConfigSet` × 3)
- **Fix**: Added `import yaml` to imports
- **Root cause**: `safe_config_write()` uses `yaml.safe_load()` and `yaml.YAMLError`
  but the module was never importing `yaml` directly

### Bug 2: `src/agents/editor/flow.py` — `_executor` accessed before early-exit check
- **Impact**: 1 test failing (`TestEditorTargetedReview::test_no_rerun_when_no_issues`)
- **Fix**: Added pre-check for `affected_agents` before building `agent_factories`
  and accessing `self._executor`
- **Root cause**: When no agents have issues in the specified phase, the function
  should return early without needing the executor

## Next Steps (T21.4+)

- Sensor `pytest_runtime.status` is now `"ok"` (ceiling activated)
- Future optimisation: Jieba lazy-load or pre-warm fixture could recover ~1.7s × workers
- CLI subprocess tests are intentional (testing real CLI flow); not candidates for mocking
