# ACL V3 RCA Handoff

Date: 2026-04-26 01:20 Asia/Taipei

## Summary

Git writes are blocked by a stale `.git/index.lock` that the sandbox user cannot delete. This prevents staging and commits, so verified work remains in the working tree and `T-WORKTREE-COMMIT-FLUSH` cannot proceed.

## Current Evidence

- `git commit -m "fix(commit-lint): reject copilot batch noise"` fails before staging/commit with `Unable to create '.git/index.lock': File exists`.
- `.git/index.lock` exists, is 0 bytes, and was last modified at `2026-04-26 00:50`.
- `del .git\index.lock` fails with `Access is denied` from the current sandbox user.
- No `openspec/changes` pending work exists outside `archive`.
- Full test suite still passes before the commit attempt: `python -m pytest -q` = `3952 passed, 34 skipped in 42.25s`.

## Tried From Repo Sandbox

1. `git add ... && git commit ...` — blocked by existing `.git/index.lock`.
2. `dir .git\index.lock` — confirms stale 0-byte lock.
3. `tasklist | findstr /I git` — no useful active git process evidence returned.
4. `del .git\index.lock` — denied by ACL.

Earlier recorded attempts in `program.md` also exhausted repo-local cleanup routes: `icacls`, Win32 DACL cleanup, and PowerShell cleanup were blocked by sandbox/ACL constraints.

## Stale Paths To Inspect

- `.git/index.lock`
- `.git/objects/d8/tmp_obj_*`
- Any `.git/objects/**/tmp_obj_*` files created near `2026-04-26 00:50`

## Host/Admin Recovery Order

Run these from an elevated host shell outside the Codex sandbox:

1. Stop any real Git clients/editors touching this repository.
2. Remove stale lock/temp files:
   - `Remove-Item -LiteralPath ".git\index.lock" -Force`
   - `Get-ChildItem -LiteralPath ".git\objects" -Recurse -Filter "tmp_obj_*" | Remove-Item -Force`
3. Reset orphan deny ACL entries on `.git` and children if deletion still fails:
   - `icacls .git /inheritance:e /T`
   - `icacls .git /remove:d *S-1-5-32-544 *S-1-5-18 *S-1-5-21-* /T` only if deny ACEs are confirmed stale/orphaned.
4. Re-run five empty commits to verify `.git` writes are stable:
   - `for ($i=1; $i -le 5; $i++) { git commit --allow-empty -m "test: ACL V3 verify $i"; Start-Sleep -Seconds 30 }`
5. Verify auto-rescue does not reappear:
   - `git log --grep="AUTO-RESCUE" --since="1 hour ago" --format="%h %s"`

## Success Criteria

- `.git/index.lock` no longer exists when no git process is running.
- Five empty commits complete without lock, unlink, or tmp object errors.
- `git log --grep="AUTO-RESCUE" --since="1 hour ago"` returns zero entries.
- `T-WORKTREE-COMMIT-FLUSH` can proceed with five semantic commits for the already-verified working tree changes.

