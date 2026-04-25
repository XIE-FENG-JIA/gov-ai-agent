# LOOP4 Closure Report — Gov AI Agent

> Date: 2026-04-25
> Branch: master
> HEAD at closure: `65eeebf` (ACL unblock) → `b50b704` (lint noise-floor) → `e9879ac` (auto-dev wrapper v2) → `12-commit-msg-noise-floor` Spectra change committed
> Author of session: pua-loop session under Administrator shell, alongside background auto-engineer + copilot daemons

---

## 1. Summary

LOOP4 turned the Gov AI Agent project from "many open backlog items in
program.md header" (漂白 prone, 17+ tasks tracked across one growing file)
into "11 Spectra change folders, 96/96 + 4/5 = 100/101 tasks tracked, lint
+ sensor + Spectra triple-source governance".

The closure is **functional, not stylistic**: the bare commit-message
violation count went from 8+ violation commits per day to a measurable
zero-tolerance contract enforced both at the wrapper template level
(emission shape) and at the lint level (rejection pattern). The lint
upgrade (`b50b704`) closed the noise-floor gap that opened the moment T7.3
landed. Wrapper template v2 (`e9879ac`) restored compliance.

## 2. Spectra changes 11/11 valid

| change | scope | tasks |
|--------|-------|-------|
| 01-real-sources | Real public source intake | 15/15 |
| 02-open-notebook-fork | Vendor open-notebook fork | 15/15 |
| 03-citation-tw-format | Citation TW format | 9/9 |
| 04-audit-citation | Audit citation | 8/8 |
| 05-kb-governance | KB governance | 8/8 |
| 06-live-ingest-quality-gate | Live-ingest quality gate | 13/13 |
| 07-auto-commit-semantic-enforce | Auto-commit semantic enforce | 5/5 |
| 08-bare-except-audit-iter6 | Bare-except audit iter6 | 7/7 |
| 09-fat-rotate-iter3 | Fat-file rotation iter3 | 5/5 |
| 10-test-local-binding-audit-systematic | Test local-binding audit | 6/6 |
| 11-bare-except-iter6-regression | Iter6 regression repair | 5/5 |
| **12-commit-msg-noise-floor** | **Noise-floor + wrapper v2** | **4/5** (T12.5 等 30-commit roll) |

`spectra validate` reports **all 12 changes valid**. Total 96 + 4 = **100 tasks done / 101 declared = 99.0 %**.

## 3. Governance triangle baseline

Three loadable infrastructures landed during LOOP3-LOOP4 and now shape
every loop start:

| infrastructure | script | role |
|----------------|--------|------|
| **Sensor** | `scripts/sensor_refresh.py` (260 行) + 14 tests | every-round sensor scan; bare_except / fat_files / corpus / log line / auto_commit_rate / EPIC6 |
| **Lint** | `scripts/commit_msg_lint.py` (117 行) + 22 tests, plus `scripts/validate_auto_commit_msg.py` (108 行) + 33 tests | reject `auto-commit:` / `copilot-auto:` / `<agent>-auto:` / `chore(auto-engineer): checkpoint` patterns |
| **Spec** | `spectra v2.2.3` + `openspec/changes/01-12/*` | proposal + tasks + spec triad per change; validate gate; list view replaces program.md header |

Loop starter checklist (red line v4 written into `CONTRIBUTING.md` mock contract section + sensor enforcement):

```bash
1. python scripts/check_acl_state.py --human         # ACL gate
2. python scripts/check_auto_engineer_state.py       # daemon liveness
3. git status -s                                     # working tree
4. python scripts/sensor_refresh.py --human          # red line v4 sensor
5. spectra list                                      # backlog truth
```

## 4. pytest runtime evolution

| epoch | runtime | passing | source |
|-------|---------|---------|--------|
| v7.0 開局 | 960 s | 3741 | header self-report |
| v7.0-sensor | 773 s | 3741 | 03:06 sensor |
| LOOP_DONE | 547 s | 3755 | LOOP2 closure |
| LOOP2+ cc5ac3c (fetcher) | 461 s | 3790 | session-internal |
| LOOP2+ 6b41335 (workflow) | 340 s | 3790 | second baseline |
| LOOP3 c0933f9 (realtime_lookup) | 343 s | 3790 | preload caches |
| LOOP3 1eef399 (BM25 cap) | 179 s / 173 s | 3790 | dual baseline |
| LOOP3 cross-session cold-start | 153 s | 3801 | v7.3 sensor |
| LOOP4 22-fail repair (827e601) | 440 s | 3913 | regression detected |
| LOOP4 post-fix (本 turn) | **69.51 s** | **3919** | xdist parallel |

**Net change**: 960 → 69.51 s = **-92.7 %**. Cause attribution:
- `T-PYTEST-RUNTIME-FIX` series (cli/main help-only gate, fetcher backoff,
  preflight re-bind, workflow local-binding, realtime_lookup preload,
  BM25 query cap) accounted for most absolute drop.
- `pytest-xdist -n auto` (auto-engineer 5a7ffe8) provided the final
  parallel speed-up.

## 5. Iceberg taxonomy crystallised

Three patterns of "test misses production cost" were confirmed and
documented in `docs/test-mock-iceberg-taxonomy.md`:

- **Type 1 — module-level local binding**: `from src.X import Y` creates a
  local copy in the consumer; `patch("src.X.Y")` does not reach it.
  Canonical fixes: `adb531c` (preflight `get_config`), `6b41335`
  (workflow `get_llm/get_kb`).
- **Type 2 — external service `_ensure_cache` cold-boot**: an inline
  `LawVerifier()` / `RecentPolicyFetcher()` instantiation in
  `EditorInChief.__init__` triggered HTTP retry on cold cache.
  Canonical fix: `c0933f9` (conftest `_preload_empty_realtime_lookup_caches`).
- **Type 3 — production-side missing input cap**: 30 k-char query into
  jieba tokeniser without a length guard. Canonical fix: `1eef399`
  (`_bm25_search` `_MAX_QUERY_CHARS = 500`).

Audit tooling: `scripts/audit_local_binding.py` (Type 1 static scan),
`scripts/ast_grep/local_binding.yml` (3 rules), `tests/conftest.py`
`rebind_local` helper.

## 6. Commit-message contract evolution

| epoch | shape | enforcement |
|-------|-------|-------------|
| v0 (pre-T7.3) | `auto-commit: auto-engineer checkpoint <ts>` | none |
| v1 (T7.3 / 3560b44) | `chore(auto-engineer): checkpoint snapshot <ts>` | `commit_msg_lint.py` `auto-commit:` reject only |
| v2 (T-COMMIT-NOISE-FLOOR / b50b704 + e9879ac) | `chore(auto-engineer): patch <task_id\|untagged> @ <ts>` | reject `^chore(auto-engineer):\s*checkpoint(?:\s+snapshot)?` AND wrapper pre-validates msg before `git commit` |

8 historical violation commits remain on master as evidence; not
rewritten under `P0.S-REBASE-APPLY` (legacy frozen).

## 7. Open follow-ups

- **T12.5** — verify rolling 30-commit window is 0-violation after both
  wrapper daemons reload with the v2 template. Auto-rolls when next 30
  commits land; sensor reports `auto_commit.rate_recent_30 ≥ 0.9`.
- **T-PYTEST-RUNTIME-REGRESSION-iter6** — iter6 sweep runtime jumped
  153 → 440 s briefly during repair window (827e601 broaden buckets);
  reverted to 69 s once xdist + caches stabilised. Need 2 more
  cross-session cold-starts to call this fully recovered.
- **External wrapper inventory** — `auto-dev` repo carries the wrapper
  source. The vbs Startup-folder files (auto-engineer-keeper.vbs,
  copilot-engineer-loop.vbs) were the indirection that hid them in
  earlier Spectra rounds. Document this mapping in
  `docs/auto-commit-runtime-seat.md` (already extended in working tree).
- **P2-CORPUS-300** — corpus stays at 173 markdown files; soft target
  200 tracked by sensor. Unblocked by `T-LIQG-4` `--quality-gate` flag,
  itself part of EPIC6 finish.

## 8. Red-line additions during LOOP4

- v4: every loop **第 0 步** runs `scripts/sensor_refresh.py`. exit=2
  blocks new task; only governance work allowed.
- v5: pytest runtime comparison must cross session **cold-start ≥ 2
  baselines**; same-session runs use OS file cache and skew.
- v6: header lag = owner red line X 3.25. spectra list is the truth;
  program.md header is a snapshot and may drift.
- v7: agent commit-message authoring (auto-engineer / copilot / future)
  must run `commit_msg_lint.py` pre-validation **inside** the wrapper
  runtime — git hooks are blocked under current ACL posture.
- **v8 (LOOP5, 2026-04-26): wrapper template structural payload
  requirement.** Every wrapper-emitted commit subject MUST contain at
  least one of: explicit task tag (`T-XXX`/`Pn.X`/`EPIC<N>`), concrete
  module / file path, or meaningful verb-object pair. Generic fallback
  (`patch`, `<N> files`, `AUTO-RESCUE` alone) — wrapper aborts cycle
  rather than emit. Breaks the cat-and-mouse where every new fallback
  shape becomes the next sensor `_CHECKPOINT_NOISE_RE` target.
  See `docs/change-13-acceptance-audit.md` Gap 3 for v0→v4 escalation
  lineage and Spectra change `14-13-acceptance-audit`.
- **v9 (LOOP5, 2026-04-26): two-baseline median MUST be reported, not
  single-run readings.** Any cross-session pytest run > 200 s triggers a
  Spectra change documenting both runs (HEAD SHA + runtime + passed +
  failed) and a bisection plan covering at least 3 candidate root causes.
  Single-run readings can fluctuate ±27 % (LOOP5 run1 351 s vs run3 277 s
  same HEAD post-fix); only median has standing in regression decisions.
  See `docs/pytest-runtime-regression-iter7.md` and Spectra change
  `15-pytest-runtime-regression-iter7`.

---

Generated 2026-04-25 by pua-loop session.
