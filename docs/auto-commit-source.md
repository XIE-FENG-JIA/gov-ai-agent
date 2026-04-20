# auto-commit source audit

## 1. 排查證據

- `rg -n "auto-commit:|checkpoint" .claude scripts .github docs src tests program.md`
  - repo 內沒有任何會產生 `auto-commit:` commit message 的腳本。
  - 唯一直接命中 `.claude/ralph-loop.local.md:14-16`，內容是「禁止 `auto-commit:` / `checkpoint` 類提交訊息」。
- `git log --oneline -10`
  - 最近 10 筆 commit 有 8 筆是 `auto-commit: auto-engineer checkpoint (...)`。
  - 這種前綴不符合 repo 規則，且 commit 作者行為和 repo 內規則相反。
- `.git` ACL 現況
  - `icacls .git` 仍顯示外來 SID `S-1-5-21-541253457-2268935619-321007557-692795393` 的 `DENY`。
  - auto-engineer 本身被 ACL 擋住，無法自行 `git add` / `git commit`。

## 2. 真實來源

`auto-commit:` 訊息來源不在 repo。來源是 Admin 側的 AUTO-RESCUE 流程。

證據在 `results.log`：

- `2026-04-20 05:59:41` `hash=1c47b76`
- `2026-04-20 06:29:43` `hash=e83411e`
- `2026-04-20 06:39:44` `hash=76171f3`
- `2026-04-20 07:19:47` `hash=edbab4c`
- `2026-04-20 07:29:51` `hash=0962fc6`
- `2026-04-20 07:39:52` `hash=19ebabb`
- `2026-04-20 07:49:53` `hash=df395bc`
- `2026-04-20 08:09:57` `hash=fe9ab20`
- `2026-04-20 08:29:59` `hash=5f08772`
- `2026-04-20 08:50:01` `hash=1d1457f`
- `2026-04-20 09:00:02` `hash=3dbf2dc`
- `2026-04-20 09:10:05` `hash=cc1cdf6`
- `2026-04-20 09:30:08` `hash=a7d4c9b`
- `2026-04-20 09:30:18` `hash=3a26e4b`
- `2026-04-20 09:40:40` `hash=b379823`
- `2026-04-20 12:48:19` `hash=7a10179`

這些條目都明寫「Admin session 代 auto-engineer commit」。所以問題不是 repo hook，不是 `.claude/` 指令，不是 `scripts/` 內部模板。

## 3. Admin 側修復 SOP

Admin rescue 腳本要改 message 模板。不要再產生 `auto-commit:` 或 `checkpoint`。

建議格式：

`chore(rescue): restore auto-engineer working tree (2026-04-20T12:48:19+08:00)`

SOP:

1. 保留 `results.log` 的 `AUTO-RESCUE` 條目，作為權限救援審計。
2. Admin session stage 需要落版的 working tree 變更。
3. commit message 一律改用 conventional commit。
4. message 要描述「救援了什麼」，不要用泛化 checkpoint 字眼。
5. 若同輪有多組不相干變更，拆 commit，不要一次混在一起。

## 4. 驗收

ACL 解後或下次 Admin rescue 後，驗這兩條：

1. `git log --oneline -5` 不再出現 `auto-commit:`
2. `git log --oneline -5` 不再出現 `checkpoint`

若仍出現，表示 Admin 側模板還沒換，repo 內改檔無法真正止血。
