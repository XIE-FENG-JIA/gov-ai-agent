# ACL Recalibration — 2026-04-25

## Goal

Re-check whether `.git` foreign SID DENY is the real blocker for this session's `git commit` failures.

## Evidence

### 1. Current token SID

- Current user: `HPZBOOKG10-\Administrator`
- Current user SID: `S-1-5-21-1271297351-773185924-864452041-500`
- Probe method: PowerShell/.NET `WindowsIdentity`
- Reason: `whoami /user` is unreliable on this host under the Git/MSYS shell and crashes with `CreateFileMapping ... error 5`

### 2. `.git` ACL snapshot

- `icacls .git` shows foreign DENY SID:
  - `S-1-5-21-541253457-2268935619-321007557-692795393`
- `.git` owner is current `Administrator`
- `.git` still grants:
  - `BUILTIN\Administrators: FullControl`
  - `NT AUTHORITY\Authenticated Users: Modify`

### 3. Token match check

- Current token SIDs do **not** include the foreign DENY SID
- Direct probe result: `NO_MATCH`
- Conclusion: the foreign DENY ACE is present, but it is **not** proven to apply to the current token

### 4. Lock failure still reproduces

- `git status --short` succeeds
- `git commit --dry-run --allow-empty -m "chore: acl probe"` fails with:
  - `fatal: Unable to create '.git/index.lock': Permission denied`
- `.git/index.lock` does not already exist
- `.git/index` attributes are only `A` (`attrib .git\index`)

## Conclusion

Old claim was wrong:

- Wrong: "foreign SID DENY ACL directly blocks the current user"
- Correct: "foreign SID DENY exists, but it does not match the current token; current write failure is a separate `.git/index.lock` permission issue"

So:

- `P0.D` should not stay framed as the primary root cause
- Foreign DENY ACL moves to advisory / legacy tracking
- Active write-path problem becomes `.git/index.lock Permission denied`

## Working hypothesis

Most likely causes now:

1. Git/MSYS shell interaction on this host
2. Session-specific file lock / handle issue
3. Parallel auto-engineer or background process racing on `.git`
4. Host-local permission quirk not explained by the orphan SID alone

## Immediate policy change

- Do not treat foreign DENY ACE as sufficient proof of current-user ACL blockage
- Keep commit path cautious until a minimal repro isolates the real `index.lock` failure
- Use token-aware ACL reporting in `scripts/check_acl_state.py`

