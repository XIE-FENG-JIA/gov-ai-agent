# Commit Plan v3 — Semantic Commit Contract

> 版本：v3（2026-04-24，pua-loop session-driven 接管 codex daemon 後）
> 前一版：[2026-04-20-v2.2-split.md](archive/commit-plans/2026-04-20-v2.2-split.md)

## Why

Auto-commit 語意率長期 ≤ 7%（30 commits 中只有 1-2 條會說明 why）。
裸 `auto-commit: checkpoint (timestamp)` 形式在 git log 完全失去可讀性，
git blame / `git log --grep` 都打不到關鍵 commit。

v3 把語意 commit 從「人工自律」升級為 **lint-enforced contract**。

## Format Contract

```
<type>(<scope>): <subject>

<body — optional, why + what changed in 1-3 paragraphs>

<footer — optional, breaking changes / refs>
```

### Allowed `type`

| type | 用途 | 範例 |
|---|---|---|
| `feat` | 新功能 | `feat(api): add /v2/refine endpoint` |
| `fix` | bug 修復 | `fix(cli): handle missing config gracefully when LLM_API_KEY absent` |
| `refactor` | 不改外部行為的重構 | `refactor(monolith→package): split fact_checker` |
| `docs` | 文檔變更 | `docs(spec): 01-real-sources tasks.md` |
| `chore` | 雜務（工具設定、依賴升級、cleanup） | `chore(cleanup): T9.5 root .ps1 歸位` |
| `test` | 測試補完或修復 | `test(adapter): cover MohwRssAdapter timeout path` |
| `perf` | 效能優化 | `perf(kb): index search hot path` |
| `style` | 不影響語意的 formatting | `style(cli): black + isort` |
| `build` | 建置系統 | `build(deps): bump litellm 1.49 → 1.52` |
| `ci` | CI 設定 | `ci(github): add commit-msg lint job` |
| `revert` | 回退 | `revert(api): drop /v2/refine endpoint` |

### Subject 規則

- 至少 **10 個字符**（拒絕 `fix`, `update`, `WIP`）
- 描述 **what + why**，不只是 what — `commit_msg_lint.py` 的 minimum length 是
  最低安全網，真正可讀的 subject 通常 > 30 字符
- 末尾 **不加句號**
- 用祈使句現在式（「add」不是「added」「adds」）

### Scope（可選）

模塊或功能名稱 — `api`, `cli`, `agents`, `kb`, `sources`, `integration`, ...

### Body（建議，重要 commit 必填）

- **why** 比 **what** 更重要 — 程式碼自己會說 what
- 解釋背景、約束、踩過的雷
- 列驗證證據（pytest 結果、metrics 變化、benchmark 數字）

### Footer

- `BREAKING CHANGE: ...`
- `Refs: T-XXX, #issue`
- `Co-Authored-By: ...`

## Rejected Patterns

`scripts/commit_msg_lint.py` 主動拒絕：

```
auto-commit: checkpoint (...)   # 永遠拒絕
auto-commit:                    # 裸 prefix
WIP                             # placeholder
fix / update / change / tmp / temp / misc / checkpoint   # 單字
<no Conventional prefix>        # 缺 type
<type>: <subject < 10 chars>    # subject 太短
```

## Enforcement

### 本地

```bash
# 手動 lint 一條訊息
echo "feat(api): add /v2/refine endpoint" | python scripts/commit_msg_lint.py -

# Lint commit-msg 檔（pre-commit-msg hook 用）
python scripts/commit_msg_lint.py .git/COMMIT_EDITMSG
```

### Hook（ACL 解開後啟用）

```bash
# .git/hooks/commit-msg
#!/bin/bash
exec python "$(git rev-parse --show-toplevel)/scripts/commit_msg_lint.py" "$1"
```

> ACL 血債（P0.D）解除前 `.git/hooks/` 不能寫；先靠 pua-loop session
> 自律 + CI gate 兜底。

### CI

CI workflow 在 PR 上跑：

```yaml
- name: Lint commit messages
  run: |
    git log --format=%B origin/main..HEAD | \
      while read -r msg; do
        echo "$msg" | python scripts/commit_msg_lint.py -
      done
```

## 驗證

```bash
pytest tests/test_commit_msg_lint.py -q
# 19 passed in 0.32s
```

## Migration Note

歷史 `auto-commit: checkpoint` commits 不回頭改寫（rebase 會破壞已 push 歷史
+ ACL 還沒解）。v3 只規範 **新 commit**。

`scripts/rewrite_auto_commit_msgs.py` 留作 ACL 解後的可選工具（P0.S-REBASE-APPLY）。
