# Windows Gotchas — 公文 AI Agent

> 本專案在 Windows 11 + MSYS2 bash + Python 3.11 環境踩過的坑。
> 目的：新接手 session 啟動前 3 分鐘看完，避免重踩。
> 每條附 **症狀 / 根因 / 修法 / 事故 commit**（能追到就追）。

---

## 1. MSYS2 bash 在中文路徑下 glob 失真

**症狀**：`cd "D:/路徑/公文ai agent" && ls *.ps1 *.docx` 輸出 6 個檔名，
但實際檔案早已搬走。工作樹狀態幻覺。

**根因**：MSYS2 bash 處理中文 cwd + glob 有不一致實作；某些 glob 會 fallback
到 `$HOME` 或錯誤的 prev-cwd 展開，不報錯。

**修法**：檔案列舉一律走 **PowerShell `Get-ChildItem`** 或 **Claude Glob tool**
當單一事實源。bash glob 的輸出視為提示，不當判斷依據。

**事故**：LOOP2 第 2 輪（2026-04-24）誤以為 root 還有 6 支 .ps1/.docx 要歸位，
實際早由 commit `a838fd3` 清空。

---

## 2. Bash tool cwd 每次 reset

**症狀**：`cd "D:/Users/.../公文ai agent" && ls` 第一次 OK，下一次 bash call
`ls` 直接在 `C:/Users/Administrator` 跑，找不到檔。

**根因**：Claude Code Bash tool 每次 invocation 是新 bash 進程，shell state
不跨 call 保留。狀態列「cwd reset to C:\Users\Administrator」是明示。

**修法**：
- 用 **絕對路徑**（`ls "D:/.../檔名"`）
- 或把 `cd && ...` 串在**同一個 command** 裡（不跨 call）
- Edit / Read / Glob / Grep 工具可以直接用絕對路徑，不受影響

---

## 3. Python 預設編碼 cp950 / CRLF 問題

**症狀**：
- `python ... > file.txt` 寫入中文 → 讀回 cp950 亂碼
- `subprocess.run(curl)` 中文 JSON response 變問號
- pytest stdout 中文 traceback UnicodeEncodeError

**根因**：Windows Python 3.11 stdout.encoding 預設 `cp950`（繁中系統 locale），
不是 utf-8。

**修法**：
```python
# 程式內
sys.stdout.reconfigure(encoding="utf-8")
# 或檔案讀寫時明寫
open(path, "r", encoding="utf-8")
# 執行時
$env:PYTHONIOENCODING = "utf-8"
python script.py
```

**本專案**：`src/cli/utils.py` atomic_text/json/yaml_write 三件都強制
`encoding="utf-8"`，別動。

---

## 4. CRLF vs LF — Claude Edit 把 .bat 變 LF

**症狀**：Edit 一個 `.bat` 檔後，Windows `cmd /c script.bat` 執行異常 /
echo 輸出錯亂。

**根因**：Claude Code Edit tool 把行尾統一為 LF，但 Windows cmd 直譯 `.bat`
需要 CRLF。

**修法**：
- `.bat` 檔避免用 Edit，用 **Python 強制 CRLF 寫**：
  ```python
  Path(bat).write_text(content, encoding="utf-8", newline="\r\n")
  ```
- `.gitattributes` 已對 `*.bat *.cmd *.ps1` 加 `eol=crlf`（如沒有，補）

---

## 5. schtasks Access Denied — 改走 Startup folder

**症狀**：
```
PowerShell> Register-ScheduledTask ...
ERROR: HRESULT 0x80070005 (Access Denied)
```
即使以 Administrator 身份跑。

**根因**：Task Scheduler 部分操作需要 **elevated** 而不只是 Administrator
group 成員。UAC auto-elevation 在非 interactive 下不觸發。

**修法**：改用 **Startup folder** .bat / .vbs：
```
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\
```
- 登入觸發 = `LogonTrigger` 等效
- 不需 elevated 權限
- 搭配 Windows 自動登入（若開）= 開機自啟

**本專案相關**：
- `Happy-Daemon.vbs`（iPhone 遙控）
- `auto-engineer-keeper.vbs`（本 agent keeper）
- 但 auto-engineer 仍可能 orphan（見 T10.2）

---

## 6. Node 20+ spawn `.cmd`/`.bat` 直接 EINVAL

**症狀**：
```js
const { spawn } = require('child_process');
spawn('npm', ['install']);  // → Error: EINVAL
```

**根因**：CVE-2024-27980 防護，Node 20.12+ / 22+ / 25+ 禁止直接 spawn
`.cmd` / `.bat` without shell wrapping，防 argument injection。

**修法**：
```js
spawn('npm', ['install'], { shell: true });
// 或
spawn('cmd.exe', ['/c', 'npm', 'install']);
```

---

## 7. Tauri/Rust `Command::new` 缺 `CREATE_NO_WINDOW` → conhost 跳窗

**症狀**：Tauri app 呼叫 node/python/curl，每次跑都跳一個 conhost 黑窗。

**根因**：Windows `CreateProcess` 預設 `dwCreationFlags = 0`，子進程繼承
console。

**修法**：
```rust
use std::os::windows::process::CommandExt;
Command::new("python")
    .args(&["script.py"])
    .creation_flags(0x08000000)  // CREATE_NO_WINDOW
    .spawn()?;
```

---

## 8. `cmd /c "9>file (timeout)"` 孤兒 FD 持鎖

**症狀**：watchdog kill 了 cmd.exe 後，某個檔案仍被鎖住，無法刪除。

**根因**：Windows `cmd /c` + fd 重導 (`9>file`) + child 進程（如 `timeout.exe`）
繼承 fd。kill cmd.exe 後，grandchild 仍持 fd。

**修法**：
```powershell
taskkill /PID <cmd_pid> /T /F   # /T = 遞迴殺 child tree
```
**不要**用 `Stop-Process -Id <cmd_pid>`，它不級聯。

**本專案相關**：TaskStop tool 已內建 `/T /F`，Claude Code 用它 kill 背景 bash
是 safe 的。

---

## 9. dataclass + importlib 動態載入 `AttributeError: NoneType __dict__`

**症狀**：
```python
spec = importlib.util.spec_from_file_location("my_mod", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)   # ← 若 my_mod 裡有 @dataclass，炸
```
錯誤：`AttributeError: 'NoneType' object has no attribute '__dict__'`

**根因**：`@dataclass` 裝飾時用 `sys.modules.get(cls.__module__).__dict__`，
若模組未 register 就拿不到。

**修法**：`exec_module` **前**先 register：
```python
mod = importlib.util.module_from_spec(spec)
sys.modules["my_mod"] = mod            # ← 先 register
spec.loader.exec_module(mod)
```

**本專案**：`tests/test_check_autoengineer_stall.py`（已刪除）踩過一次；
T10.2 開發過程紀錄。

---

## 10. 中文路徑下 `pytest rootdir` 顯示亂碼（不影響執行）

**症狀**：
```
rootdir: D:\Users\Administrator\Desktop\����ai agent
```
亂碼「公文」二字。

**根因**：PowerShell 7 stdout encoding 和 pytest 印 rootdir 的 Windows console
code page 不同步。顯示壞，內部路徑正常。

**修法**：**忽略**。pytest 實際跑的路徑是正確 UTF-8，只是印出時被 console
解碼錯。若真要修：
```powershell
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```

---

## 11. `.git` ACL 外來 SID DENY

**症狀**：
```
fatal: Unable to create '.git/index.lock': Permission denied
```
Admin 身份仍失敗。

**根因**：某次操作（可能 codex subprocess IL 降級、WSL mount、或別的工具）
在 `.git` 上留了 explicit **Deny Write/Delete** ACE，繫結到**外來 SID**
（非本機帳號）。

**修法**（本專案 P0.D 仍 blocker，以下非一鍵方案）：
```powershell
takeown /F .git /R
icacls .git /reset /T
icacls .git /remove:d <外來SID>   # 需要列出現存 SID
```
本專案同時跑 auto-commit 10-min loop + ACL watcher 30s + 三 loop Startup .vbs
作治標。T10.4 `scripts/check_acl_state.py` 可做啟動 gate。

---

## 12. MSYS2 fork 效能差 — hot loop 禁 sed/grep

**症狀**：shell script 裡 `for f in *.txt; do sed ... | grep ... done` 在 Windows
跑一次要幾分鐘，Linux 跑同樣東西秒殺。

**根因**：MSYS2 fork() 在 Windows 沒有 native，用 ptrace + DLL 模擬，慢 10-100x。

**修法**：
- Python one-shot 處理取代 shell pipeline
- 或 PowerShell（`Get-ChildItem | ForEach-Object`）
- 本專案 `scripts/*.py` 都走 Python，避免 shell hot loop

---

## 13. taskkill 全殺 cmd.exe 連帶殺 Happy daemon

**症狀**：`taskkill /F /IM cmd.exe` 後 Happy CLI daemon 也死了，App 斷線。

**根因**：Happy daemon 用 cmd.exe 包 node。`/IM cmd.exe` 不分青紅皂白全殺。

**修法**：
- 精確 kill by PID，不用 `/IM`
- 或 kill by 整條 command line（PowerShell + WMI filter）：
  ```powershell
  Get-CimInstance Win32_Process -Filter "CommandLine LIKE '%目標%'" |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
  ```

---

## 14. wscript detached 啟 bat → 偽 orphan

**症狀**：Bot watchdog 看到「parent 死了但 child 還跑」，判定 orphan 清掃，
誤殺正常服務。

**根因**：wscript `.vbs` 用 `Run ... , vbHide, True` 啟動 bat 後**立刻返回**，
造成 bat 的 parent PID 指向已死 wscript。但 bat 本身是故意 detached，不是 orphan。

**修法**：orphan 清掃 whitelist 必含 CommandLine 檢查：
```powershell
if ($proc.CommandLine -match 'openab|lobsterpulse|happy') {
    Write-Output "whitelisted, skip"
    continue
}
```

---

## 15. pytest runtime baseline 會被 Windows Defender 拖慢

**症狀**：同一組 pytest suite，Windows 跑 550s，WSL 跑 200s。

**根因**：Windows Defender real-time protection 掃每個 `.pyc` write、每次
`import`、每個 `tempfile`。MSYS2 fork 成本 + Defender 掃描 = 雙殺。

**修法**：
- `tests/` 和 `__pycache__` 加到 Defender 例外
  ```powershell
  Add-MpPreference -ExclusionPath "D:\Users\...\公文ai agent\tests"
  Add-MpPreference -ExclusionPath "D:\Users\...\公文ai agent\__pycache__"
  ```
- 或改在 WSL 跑 pytest（專案 src 共用，但 CI 也要同環境驗）

---

## 16. LOOP starter checklist（新 session 第一動作）

```powershell
# 1. ACL 血債
python scripts/check_acl_state.py --human
# exit 1 = read-only 模式

# 2. auto-engineer 是否 orphan / race 會發生
python scripts/check_auto_engineer_state.py
# status=orphan/stale → 可安全 commit；status=running → 挑 auto-engineer 熱區外 task

# 3. git status
git status -s
# 非空 = 前輪半成品，先收尾再接新 task

# 4. pytest baseline（可選，大任務才跑）
python -m pytest -q --ignore=tests/integration --durations=30
# target ≤ 700s
```

---

## 備註

- 本檔**只記專案踩過 + 重現過**的坑。通用 Windows 知識請看 [Microsoft Docs](https://learn.microsoft.com/).
- 新事故 → 先 append 到本檔（不要散在 engineer-log），保持單一 knowledge base。
- 校準紀錄：檔案建立於 2026-04-24 LOOP2 第 4 輪（task i P0.GG）；上一次 survey 合併
  自 `.claude/CLAUDE.md` + MemPalace 記憶 + engineer-log.md 封存批次。
