# Atomic Tmp Audit (T9.2)

> 2026-04-24 — pua-loop session 排查

## Sources（誰會生成 `*.json_*.tmp` / `*.txt_*.tmp` / `*.yaml_*.tmp`）

`src/cli/utils.py` 的 `atomic_text_write` / `atomic_json_write` / `atomic_yaml_write`：

| API | 落點 | 清理方式 |
|---|---|---|
| `atomic_text_write(path, ...)` | `<path>_<random>.tmp` | 寫入後 `os.replace` 覆蓋目標 |
| `atomic_json_write(path, ...)` | `<path>_<random>.tmp` | 同上 |
| `atomic_yaml_write(path, ...)` | `<path>_<random>.tmp` | 同上 |

`src/cli/utils.py:128 _cleanup_stale_atomic_tmps(parent)` 在每次 atomic write
前主動清掃同目錄下的孤兒 tmp（被 `atomic_text_write` / json / yaml 在 line
140 / 161 / 182 各呼叫一次）。

## Lock（防止 commit 進 git）

`.gitignore` 已封 root 級 pattern：

```
.json_*.tmp
.txt_*.tmp
.yaml_*.tmp
```

額外 `*.docx` 也鎖（避免 test output / 範例公文外洩）。

## Cleanup（測試環境）

`tests/conftest.py` 的 session-scope autouse fixture：

```python
@pytest.fixture(scope="session", autouse=True)
def cleanup_repo_root_atomic_tmps():
    cleanup_orphan_tmps(str(repo_root), max_age_seconds=None)
    yield
    cleanup_orphan_tmps(str(repo_root), max_age_seconds=None)
```

每次 pytest session 前後各掃一次；`max_age_seconds=None` 表示無年齡門檻
（測試環境永遠清乾淨）。

## 驗證

```bash
pytest tests/test_cli_utils_tmp_cleanup.py -q
# 3 passed in 0.31s
```

## 為什麼 T9.2 拖了

機制其實 2026-04-19 左右就上了；漏的是把實作和 contract 寫成 audit doc。
本 commit 補完 — T9.2 標 ✅。
