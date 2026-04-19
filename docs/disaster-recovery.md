# Disaster Recovery: `.git` ACL DENY 事故處置手冊

本文件記錄 2026-04-20 這次 `.git` ACL DENY 事故，目標不是追究，而是讓下一位 on-call engineer 能在 5 分鐘內判斷：現在是 `read-only` 模式、需要人工 Admin、還是可以安全回到正常提交流程。

## 1. 事故摘要

- 事故期間：從 v2.4 的權限異常一路延伸到 v2.7 根因回歸。
- 直接症狀：`git add`、`git commit`、`git stash` 反覆卡在 `.git/index.lock: Permission denied`。
- 真正根因：`.git` 目錄帶有外來 SID `S-1-5-21-541253457-2268935619-321007557-692795393` 的顯式 `DENY` ACL。
- 已知 DENY 權限：`(DENY)(W,D,Rc,DC)` 與 `(OI)(CI)(IO)(DENY)(W,D,Rc,GW,DC)`。
- 影響範圍：所有會寫入 `.git` metadata 的操作都不可信，包含 `git add`、`git commit`、`git stash`、`index.lock` 建立、以及手動寫入 `.git\codex_probe.tmp`。
- 關鍵證據：`results.log` 第 2、8、11、17 筆都指向同一條線，表示這不是單次 lock file 故障，而是系統層權限阻斷。

## 2. 快速判斷流程

### Step A: 檢查 ACL

```powershell
icacls .git
```

若輸出含 `DENY`，尤其是上述 SID，立刻進入 `read-only` 模式。此時不要嘗試 `git add`、`git commit`、`git stash`。v2.7 已把這條寫成硬規則，因為重複試只會新增無意義 FAIL log。

### Step B: 檢查工作樹

```powershell
git status --short
```

如果 ACL 仍是 deny，工作樹髒不代表可以硬提。當前正確做法是只做文件、調研、盤點類工作，並把 commit 留到 Admin 解鎖後。

### Step C: 跑整體測試確認功能面

```powershell
pytest tests -q
```

2026-04-20 現場結果是 `3544 passed, 1364 warnings`。這代表應用程式本體並沒有全面壞掉，阻斷點集中在 repo metadata 寫入，不在 Python runtime。

## 3. 事故時間線

### v2.4

- 開始出現 `.git/index.lock` 相關阻塞。
- 當時表象像 lock file 或暫存檔沒清乾淨，但後續證據證明只是表層症狀。

### v2.5

- 嘗試清 root tmp orphan、補 benchmark 文件、整理 `.gitignore`。
- 雖然測試能綠，但 commit 仍不穩。
- `.git_acl_backup.txt` 被外移成 `.git_acl_backup.txt.quarantine-050909`，顯示當時已經有人懷疑 ACL 與備援 git metadata 有關。

### v2.6

- 問題被誤判成「補交漏版控檔案」與「auto-commit 治理」優先。
- 三個硬指標最終 0/3，全 fail。
- 這輪最大的教訓：如果根因是系統權限，流程面補救會一直產生假進展。

### v2.7

- `results.log` 第 17 筆把根因鎖到外來 SID deny ACL。
- `AUTO-RESCUE` 歷史顯示 Admin session 可以繞過 auto-engineer 被擋的權限，進一步證明不是內容錯，而是 ACL 邊界不同。
- 專案因此新增 `ACL-gated` 規則與 `read-only` 任務池。

## 4. Admin 解鎖 SOP

只有 Admin session 可以做下面這段。普通 agent 已經驗證過 `Set-Acl` 會回 `Attempted to perform an unauthorized operation`。

```powershell
takeown /f .git /r /d y
icacls .git /reset /T /C
icacls .git /remove:d "*S-1-5-21-541253457-2268935619-321007557-692795393" /T /C
```

完成後立刻驗證：

```powershell
icacls .git
```

驗收標準：

- 不再出現 `DENY`
- `git add` 可以建立 `index.lock`
- `git status` 與 `git commit` 回到正常行為

如果 `takeown` 或 `icacls /reset` 仍失敗，不要在原 repo 內持續嘗試，先保留現場，改由人工 Admin 介入。

## 5. 備援目錄去留決策

事故期間曾出現六個備援目錄或探測產物。現場盤點如下：

- `meta_git/`：2786 items，約 12.26 MB，完整 git metadata 結構，含 `index.lock`。定位：失敗的備援 `.git` 複本。
- `meta_git_live/`：2789 items，約 12.24 MB，結構與 `meta_git/` 類似。定位：另一份 live 實驗複本。
- `repo_meta/`：2788 items，約 12.22 MB，同樣是完整 metadata 鏡像。定位：第三份備援 git dir。
- `recovered_repo/`：20 items，約 26 KB，內含 `.git/config.lock` 與基本骨架。定位：半成品恢復 repo。
- `git_safe/`：19 items，約 26 KB，只剩 `config.lock` 與基本目錄。定位：失敗的安全初始化嘗試。
- `meta_test/`：1 item，7 bytes，只有 `probe.tmp`。定位：單次探測殘留。

### 保留條件

只有在以下情況才保留：

- 需要法證或根因比對。
- 需要對照不同失敗階段的 `.git` metadata。
- 尚未完成人工 ACL 修復，怕唯一證據被誤刪。

### 刪除條件

滿足以下三點即可刪：

- `.git` ACL deny 已解除。
- 目前主 repo 可以正常 `git add` / `git commit`。
- `docs/disaster-recovery.md` 已記錄本次事故與備援目錄角色。

### 建議處置順序

1. 先保留 `meta_git/`、`meta_git_live/`、`repo_meta/` 到 ACL 解鎖後一輪。
2. `recovered_repo/` 與 `git_safe/` 因內容不完整，可在解鎖驗證通過後優先清掉。
3. `meta_test/` 僅 probe，價值最低，最後確認無追查需求即可刪。

## 6. `.git_acl_backup.txt.quarantine-*` 處置

`.git_acl_backup.txt` 已被外移為 `.git_acl_backup.txt.quarantine-050909`。這類檔案的處理原則：

- 不要重新命名回 `.git_acl_backup.txt` 放在 repo 根。
- 視為敏感但低風險的 Windows ACL 歷史紀錄，避免進版控。
- 若需要留證，放在 quarantine 名稱下即可。
- 若後續確認沒有法證價值，可在 ACL 修復穩定後刪除。
- 若專案要長期保留，應移到 repo 外的 incident evidence 位置，而不是跟產品程式碼同層。

## 7. 未來遇到 ACL DENY 的 read-only fallback

當 on-call agent 再次遇到 `.git` deny，請直接照這個 fallback，不要重演 v2.5 到 v2.6 的無效 commit 嘗試。

1. 跑 `icacls .git`。看到 deny 就標記 `ACL-gated`。
2. 跑 `git status --short`，記錄工作樹現況，但不做 commit。
3. 跑 `pytest tests -q`，確認功能層是否健康。
4. 只挑 `program.md` 標成 `✅ read-only` 的任務，例如文件、來源調研、盤點。
5. `results.log` 若任務本身因 ACL 無法收尾，用 `BLOCKED-ACL`；若 read-only 任務已完成並有 `ls` / `pytest` / 計數證據，可記 `PASS`。
6. 在 `program.md` 明確寫出下一個需要 Admin 的點，不要把系統權限問題偽裝成功能問題。

## 8. 這次事故的教訓

- 根因優先。看起來像 `index.lock`，實際上是 ACL deny。
- 測試綠不等於 repo 健康。Python code 可以過，git metadata 仍然可能死。
- 備援目錄不是解法，只是現場痕跡。沒有文件化就會變成長期垃圾。
- `AUTO-RESCUE` 能救一時，但如果不把 ACL 根因寫清楚，只會讓團隊誤以為問題已經自然消失。
- read-only 任務池是必要的。它讓 on-call 在無法 commit 的時候，仍能交付對後續排障有價值的產物。

## 9. 本文件完成後的下一步

- 下一個 read-only 任務是 `P0.3`：`docs/sources-research.md`。
- 等 Admin 解掉 ACL，再回補本文件對應 commit：`docs(ops): add disaster recovery playbook for .git ACL deny + backup dirs`。
- ACL 解鎖後第一輪要做的不是大量重構，而是先驗證 `.git` 可正常寫入，再清掉事故期間留下的備援目錄與 quarantine 檔策略。
