# Proposal — Epic 22: Source Adapter Health Metrics

## Problem

The five live source adapters (mojlaw, executive_yuan_rss, mohw, fda, datagovtw) are
invoked during `kb rebuild` and `kb gate-check` but there is no lightweight way to:

1. See the *last fetch latency* and *record count* per adapter without running a full rebuild.
2. Detect adapters that are consistently returning 0 records (silent stall).
3. Surface adapter health in the sensor without live network calls on every `sensor_refresh.py` run.

## Goal

Implement a `scripts/adapter_health.py` probe script that:
- Runs a quick *dry fetch* (limit=3) for each adapter.
- Records `{adapter, status, latency_ms, count, error}` to
  `scripts/adapter_health_report.json`.
- Exposes a `--human` summary (icon + adapter + latency + count).
- Integrates with `sensor_refresh.py` via `check_adapter_health()` yielding a
  soft violation when any adapter returns 0 records **or** raises an exception.

## Non-goals

- Full rebuild / quality-gate check (that is `gov-ai kb rebuild --quality-gate`).
- Changing adapter fetch internals.
- Requiring `GOV_AI_RUN_INTEGRATION=1` (unit tests mock adapters).

## Acceptance Criteria

| ID | Criterion |
|----|-----------|
| AC-1 | `python scripts/adapter_health.py --dry-run` exits 0, writes report |
| AC-2 | `python scripts/adapter_health.py --human` prints ≥1 adapter row |
| AC-3 | `sensor["adapter_health"]` field present with `ok`/`violation` status |
| AC-4 | `tests/test_adapter_health.py` ≥ 6 unit tests (mock adapters; no live calls) |
| AC-5 | `sensor_refresh.py` produces soft violation when any adapter count=0 |
| AC-6 | `CONTRIBUTING.md` updated with "Adapter Health" section |

## Tasks

See `tasks.md` for T22.1–T22.6.
