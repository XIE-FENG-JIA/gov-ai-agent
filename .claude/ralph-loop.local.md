---
active: true
iteration: 11
max_iterations: 15
completion_promise: null
started_at: "2026-03-09T02:06:14Z"
---

使用Agent Team模擬使用者使用公文AI Agent專案的功能，持續改進便利性以及增加實用功能。

硬性執行規則：
1. 每輪先執行 `icacls .git`。若存在 `DENY` ACL，進入 read-only 模式：允許寫 working tree 與文件，禁止任何 `git add`、`git commit`、`git stash`。
2. 每輪先看 `git status --short`。若工作樹不乾淨，先處理既有變更與紀錄，不得開新任務。
3. 禁止產生 `auto-commit:` 或 `checkpoint` 類提交訊息。只允許 conventional commits。
4. 若需要 checkpoint，只能把變更保留在 working tree，並把狀態寫入 `results.log`，不能用假 commit 掩蓋髒樹。
5. 若 `.git` ACL 解除，提交訊息必須使用 conventional commit，例如 `docs(loop): enforce acl-aware checkpoint policy`。
