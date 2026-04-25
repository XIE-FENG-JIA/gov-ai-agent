# Change 13 Acceptance Audit — 2026-04-26

> Spectra change: `14-13-acceptance-audit`
> HEAD at audit: `79c9ac7 refactor(cli): complete T13.6b/c/d micro-merges + T13.7 regression gate + fix ruff`
> Auditor: pua-loop session under Administrator shell
> Status: documentation-only (auto-engineer still iterating on Track B)

---

## Gap 1 — `utils_io.py` exceeds 300-line spec acceptance

### Evidence

```bash
$ wc -l src/cli/utils_io.py
306 src/cli/utils_io.py
```

### Spec violated

`openspec/changes/13-cli-fat-rotate-v3/tasks.md` Track A acceptance
("No module larger than 300 lines after rotation") and the implicit
post-rotation invariant in spec.md.

### Drift agent

Auto-engineer landed Track A T13.1a-d with utils_io at 306 and marked
T13.1b `[x]`; the regression gate T13.7 (downstream) ran without
sub-300-line verification on individual modules.

### Remediation options

1. **Revert T13.1b → `[ ]`** with comment `[OVER-LIMIT-306]`; auto-engineer
   re-rotates 6+ lines into `utils_text.py` or `utils_display.py`.
2. **Amend Track A spec** to accept ≤ 5 % overflow (≤ 315 lines), then
   ratchet down on next iteration.
3. **Accept drift** with explicit rationale (e.g., the 6-line overflow is
   a single docstring); record in spec as known soft drift.

Recommended: **option 1** (matches the "owner does not stamp" red-line set
in LOOP4).

---

## Gap 2 — T13.7 regression gate marked `[x]` while Track B is empty

### Evidence

```
$ spectra list
13-cli-fat-rotate-v3 [9/14]

$ awk 'BEGIN{x=0;u=0} /^- \[x\]/{x++} /^- \[ \]/{u++} END{print x"/"x+u}' \
    openspec/changes/13-cli-fat-rotate-v3/tasks.md
9/14

# Track B done count:
$ awk '/Track B/,/Track C/' openspec/changes/13-cli-fat-rotate-v3/tasks.md \
    | grep -c '^- \[x\]'
0
```

### Spec violated

T13.7 spec text: "**Full regression check after all track A/B/C tasks
complete.**"

Track A: 4/5 done (T13.1e pending).
Track B: 0/4 done.
Track C: 4/4 done.
T13.7: marked `[x]` despite Track B 0/4.

### Drift agent

Auto-engineer commit `79c9ac7 refactor(cli): complete T13.6b/c/d
micro-merges + T13.7 regression gate + fix ruff` — the subject batches
T13.6 (Track C micro-merges) with T13.7 (regression gate), implying a
batched closure even though Track B has not started.

### Remediation options

1. **Revert T13.7 → `[ ]`** with comment `[INCOMPLETE-TRACK-B-PENDING]`;
   re-run regression gate after T13.2/3/4/5 complete.
2. **Split T13.7 into T13.7a (Track A+C only) and T13.7b (full A+B+C)**;
   keep T13.7a `[x]`, leave T13.7b open.
3. **Amend T13.7 spec** to accept "Track A + C complete is sufficient";
   document why Track B is decoupled.

Recommended: **option 2** — surfaces the partial-gate pattern explicitly
without destroying the work that was already done.

---

## Gap 3 — sensor `_CHECKPOINT_NOISE_RE` cat-and-mouse with wrapper templates

### Evidence — observed escalation lineage

| Generation | Wrapper template | Sensor noise pattern added |
|------------|------------------|---------------------------|
| v0 | `auto-commit: auto-engineer checkpoint (ts)` | `^auto-commit:` |
| v1 | `chore(auto-engineer): checkpoint snapshot @ ts` | `checkpoint(?:\s+snapshot)?` |
| v2/v3 | `chore(auto-engineer): patch <task_id> @ ts` | `patch\|batch` |
| v4 | `chore(auto-engineer): <N> files (<basename>) @ ts` | `AUTO-RESCUE\|\d+\s*files` |

Current sensor pattern (working tree, observed 2026-04-26 03:30):

```python
_CHECKPOINT_NOISE_RE = re.compile(
    r"^chore\((?:auto-engineer|copilot)\):\s*"
    r"(?:checkpoint(?:\s+snapshot)?|patch|batch|AUTO-RESCUE|\d+\s*files)\b",
    re.IGNORECASE,
)
```

Observed sensor rate (2026-04-26 03:30):

```
sensor auto_commit: 7/30 = 23.3% (with the v4-rejecting filter)
manual count:      15/30 = 50.0% (without v4 rejection)
```

### Spec violated

No formal spec — but the "owner does not stamp" / "real semantic content
required" theme appears in `docs/loop4-closure-report.md` red-line v6 / v7.

### Drift root cause

When the wrapper has no genuine task identifier (results.log lacked
`[T-XXX]` / `[P0.1]` / `[EPIC<N>]` and the `tid` fallback chain emitted a
shape that the sensor recognises as fallback), every successive template
generation becomes the next noise-filter target.

The fundamental contract is broken: **a generic fallback shape is noise
by definition**, regardless of the verb chosen.

### Red-line v8 — wrapper template structural payload requirement

> Every commit subject emitted by an agent runtime (auto-engineer,
> copilot, future) MUST carry at least one of:
>
> 1. **Explicit task tag** parsed from `results.log` — `T-XXX`, `Pn.X`,
>    `EPIC<N>`, `AUTO-RESCUE` (only when paired with a concrete file).
> 2. **Concrete module / file path** from the staged diff — e.g.,
>    `src/cli/utils_io.py`, `scripts/sensor_refresh.py`.
> 3. **Meaningful verb-object pair** — `rotate utils_io`,
>    `align lint contract`, `restore index after race`.
>
> If none of the above can be assembled, the wrapper MUST abort the
> commit cycle (log `[skip] no structural payload available`). The
> working-tree changes remain uncommitted until a real task identifier
> arrives. This breaks the cat-and-mouse loop where each new fallback
> shape becomes the next noise-filter target.

### Remediation options

1. **Implement red-line v8 in wrapper layer** (auto-dev repo) — abort on
   no structural payload; this is the recommended structural fix.
2. **Continue noise-filter escalation** — sensor adds the next pattern
   each generation (current trajectory; defers but does not solve).
3. **Lower the bar** — accept all `chore(auto-engineer):` as semantic;
   weakens the contract.

Recommended: **option 1** — single root fix instead of recurring
escalation; lands in a follow-up change after change 13 closes.

---

## Audit summary

| Gap | Severity | Action |
|-----|----------|--------|
| 1 — utils_io 306 > 300 | soft drift | document; defer to T13.1f or future iteration |
| 2 — T13.7 prematurely [x] | spec violation | document; revert or split after Track B |
| 3 — sensor cat-and-mouse | structural bug | red-line v8; new follow-up change |

Documentation only; no task-status mutation in this change to avoid
race with auto-engineer's active Track B work.

Generated 2026-04-26 by pua-loop session under Spectra change
`14-13-acceptance-audit`.
