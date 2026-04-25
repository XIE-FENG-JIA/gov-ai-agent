# Checkpoint Squash Plan

- scanned_commits: 30
- checkpoint_commits: 27
- squashable_groups: 11
- commits_reducible: 13
- window_secs: 300

## Proposed Squash Groups

### Group 1 — 2 commits → 1
- window_start: 2026-04-25T08:13:42+00:00
- window_end: 2026-04-25T08:16:21+00:00
- proposed_msg: `chore(repo): squash 2 checkpoint snapshots covering results.log, scripts/live_ingest.py`
- commits:
  - `e1645a6c23ce` `auto-commit: auto-engineer checkpoint (2026-04-25 16:06:21) @ 2026-04-25 16:13`
  - `fbf8a438d3d9` `auto-commit: auto-engineer checkpoint (2026-04-25 16:13:43 +08:00) @ 2026-04-25 16:16`
- rebase_cmd: `git rebase -i e1645a6c23ce5565b390c9ad1482373e4a8bf426^` (squash all, set message to proposed_msg)

### Group 2 — 2 commits → 1
- window_start: 2026-04-25T08:24:06+00:00
- window_end: 2026-04-25T08:26:45+00:00
- proposed_msg: `chore(repo): squash 2 checkpoint snapshots covering docs/corpus-200-push-2026-04-25.md, docs/live-ingest-report.md`
- commits:
  - `a3ec0f88d432` `auto-commit: auto-engineer checkpoint (2026-04-25 16:16:21) @ 2026-04-25 16:24`
  - `c35e3e92f598` `auto-commit: auto-engineer checkpoint (2026-04-25 16:24:07) @ 2026-04-25 16:26`
- rebase_cmd: `git rebase -i a3ec0f88d43267e1ed1d8649f44b97944739cd9e^` (squash all, set message to proposed_msg)

### Group 3 — 2 commits → 1
- window_start: 2026-04-25T08:31:46+00:00
- window_end: 2026-04-25T08:34:29+00:00
- proposed_msg: `chore(repo): squash 2 checkpoint snapshots covering docs/live-ingest-report.md, .copilot-loop.state.json`
- commits:
  - `cad497297f0a` `copilot-auto: batch round 7 (2026-04-25 16:30:47) @ 16:31`
  - `d11822c81d71` `auto-commit: auto-engineer checkpoint (2026-04-25 16:30:47) @ 2026-04-25 16:34`
- rebase_cmd: `git rebase -i cad497297f0a39a3a4cf2896649fcc19f24b459b^` (squash all, set message to proposed_msg)

### Group 4 — 2 commits → 1
- window_start: 2026-04-25T08:44:54+00:00
- window_end: 2026-04-25T08:47:30+00:00
- proposed_msg: `chore(docs): squash 2 checkpoint snapshots covering results.log`
- commits:
  - `3df794ad5bba` `auto-commit: auto-engineer checkpoint (2026-04-25 16:37:08) @ 2026-04-25 16:44`
  - `a245977ef3a6` `auto-commit: auto-engineer checkpoint (2026-04-25 16:44:54) @ 2026-04-25 16:47`
- rebase_cmd: `git rebase -i 3df794ad5bba1942c6f22e0c9562471c38daab12^` (squash all, set message to proposed_msg)

### Group 5 — 2 commits → 1
- window_start: 2026-04-25T08:54:54+00:00
- window_end: 2026-04-25T08:57:32+00:00
- proposed_msg: `chore(docs): squash 2 checkpoint snapshots covering results.log`
- commits:
  - `79709dac63dd` `auto-commit: auto-engineer checkpoint (2026-04-25 16:47:30) @ 2026-04-25 16:54`
  - `0a77ae874b39` `auto-commit: auto-engineer checkpoint (2026-04-25 16:54:55) @ 2026-04-25 16:57`
- rebase_cmd: `git rebase -i 79709dac63dd5f109aa997eedaaab82a914970df^` (squash all, set message to proposed_msg)

### Group 6 — 2 commits → 1
- window_start: 2026-04-25T09:05:23+00:00
- window_end: 2026-04-25T09:07:31+00:00
- proposed_msg: `chore(docs): squash 2 checkpoint snapshots covering results.log`
- commits:
  - `7eef9088d3fe` `auto-commit: auto-engineer checkpoint (2026-04-25 16:57:32) @ 2026-04-25 17:05`
  - `6140e26c78c6` `auto-commit: auto-engineer checkpoint (2026-04-25 17:05:24) @ 2026-04-25 17:07`
- rebase_cmd: `git rebase -i 7eef9088d3fec5f7482dbecd9058bb441cc8fad9^` (squash all, set message to proposed_msg)

### Group 7 — 3 commits → 1
- window_start: 2026-04-25T09:15:19+00:00
- window_end: 2026-04-25T09:17:58+00:00
- proposed_msg: `chore(repo): squash 3 checkpoint snapshots covering engineer-log.md, program.md`
- commits:
  - `77cb76d3a77d` `auto-commit: auto-engineer checkpoint (2026-04-25 17:08:00) @ 2026-04-25 17:15`
  - `45f79e881df6` `copilot-auto: batch round 8 (2026-04-25 17:16:20) @ 17:16`
  - `5fc70bacb8e0` `auto-commit: auto-engineer checkpoint (週六 2026/04/25 17:17:15.27) @ 2026-04-25 17:17`
- rebase_cmd: `git rebase -i 77cb76d3a77dbbaf39eb322c80c8dde43e69e830^` (squash all, set message to proposed_msg)

### Group 8 — 2 commits → 1
- window_start: 2026-04-25T09:35:36+00:00
- window_end: 2026-04-25T09:38:33+00:00
- proposed_msg: `chore(repo): squash 2 checkpoint snapshots covering docs/auto-commit-runtime-seat.md, program.md`
- commits:
  - `8bcab8623c43` `auto-commit: auto-engineer checkpoint (2026-04-25 17:17:58) @ 2026-04-25 17:35`
  - `3d17d08fcb8d` `auto-commit: auto-engineer checkpoint (2026-04-25 17:36:07+0800) @ 2026-04-25 17:38`
- rebase_cmd: `git rebase -i 8bcab8623c430f604a9e83e6176717513ca987b1^` (squash all, set message to proposed_msg)

### Group 9 — 2 commits → 1
- window_start: 2026-04-25T09:46:02+00:00
- window_end: 2026-04-25T09:48:38+00:00
- proposed_msg: `chore(repo): squash 2 checkpoint snapshots covering docs/auto-commit-runtime-seat.md, results.log`
- commits:
  - `20afcbbb8088` `auto-commit: auto-engineer checkpoint (2026-04-25 17:44:26+0800) @ 2026-04-25 17:46`
  - `0e55c53fb4fd` `auto-commit: auto-engineer checkpoint (2026-04-25 17:46:02) @ 2026-04-25 17:48`
- rebase_cmd: `git rebase -i 20afcbbb8088b0ba8f54836c6addc52d921a4d9a^` (squash all, set message to proposed_msg)

### Group 10 — 2 commits → 1
- window_start: 2026-04-25T09:56:06+00:00
- window_end: 2026-04-25T09:59:07+00:00
- proposed_msg: `chore(repo): squash 2 checkpoint snapshots covering results.log, scripts/check_fat_files.py`
- commits:
  - `34a3e15a781d` `chore(auto-engineer): checkpoint snapshot (2026-04-25 17:48:39) @ 2026-04-25 17:56`
  - `47ce0873358f` `chore(auto-engineer): checkpoint snapshot (2026-04-25 17:56:07) @ 2026-04-25 17:59`
- rebase_cmd: `git rebase -i 34a3e15a781d89ce7a0e72ce32a92cfbe160b138^` (squash all, set message to proposed_msg)

### Group 11 — 3 commits → 1
- window_start: 2026-04-25T10:04:35+00:00
- window_end: 2026-04-25T10:09:28+00:00
- proposed_msg: `chore(repo): squash 3 checkpoint snapshots covering .github/workflows/ci.yml, program.md`
- commits:
  - `dcb52c454a2e` `copilot-auto: batch round 9 (2026-04-25 18:02:00+0800) @ 18:04`
  - `d2db28825834` `chore(auto-engineer): checkpoint snapshot (2026-04-25 18:02:00+0800) @ 2026-04-25 18:06`
  - `1cf654ee8cfd` `chore(auto-engineer): checkpoint snapshot (2026-04-25 18:07:12+0800) @ 2026-04-25 18:09`
- rebase_cmd: `git rebase -i dcb52c454a2ee7db2a2655cc8d36ac13398ee9c6^` (squash all, set message to proposed_msg)

---
Generated by `scripts/squash_checkpoint_window.py`. No git history was modified.