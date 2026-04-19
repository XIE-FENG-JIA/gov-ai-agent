# Coverage Baseline

Generated on `2026-04-20` from the current green test suite.

## Command

```powershell
pytest tests/
pytest --cov=src --cov-report=json:coverage.json --cov-report=term --cov-report=html:htmlcov
python -m coverage json -o coverage.json
python -m coverage html -d htmlcov
python -m coverage report
```

Note: on this Windows workspace, `pytest-cov` completed all `3544` tests but failed during `coverage combine` cleanup with `PermissionError` while deleting a temporary `.coverage.*` file. The persisted `.coverage` file was still valid, so JSON and HTML reports were generated directly from `coverage.py`.

## Total Coverage

- Total line coverage: `91%`
- Statements: `12,533`
- Missing lines: `1,100`
- Empty files skipped by coverage: `7`

## Module Coverage

| Module | Statements | Missing | Coverage |
| --- | ---: | ---: | ---: |
| `agents` | 1,962 | 95 | 95.16% |
| `api` | 1,125 | 86 | 92.36% |
| `cli` | 5,457 | 620 | 88.64% |
| `core` | 627 | 15 | 97.61% |
| `document` | 256 | 13 | 94.92% |
| `graph` | 452 | 108 | 76.11% |
| `knowledge` | 2,449 | 155 | 93.67% |
| `utils` | 24 | 1 | 95.83% |
| `web_preview` | 179 | 7 | 96.09% |
| `theme` | 1 | 0 | 100.00% |
| root `__init__` | 1 | 0 | 100.00% |

## Files Below 60%

| File | Statements | Missing | Coverage |
| --- | ---: | ---: | ---: |
| `src/graph/nodes/writer.py` | 20 | 16 | 20.00% |
| `src/graph/nodes/requirement.py` | 17 | 13 | 23.53% |
| `src/graph/nodes/exporter.py` | 25 | 18 | 28.00% |
| `src/graph/nodes/reviewers.py` | 70 | 38 | 45.71% |
| `src/graph/routing/conditions.py` | 46 | 20 | 56.52% |

## Highest Missing-Line Hotspots

| File | Missing | Coverage |
| --- | ---: | ---: |
| `src/cli/kb.py` | 232 | 70.37% |
| `src/cli/generate.py` | 92 | 86.71% |
| `src/api/routes/workflow.py` | 50 | 84.89% |
| `src/agents/writer.py` | 40 | 90.61% |
| `src/cli/history.py` | 38 | 91.12% |

## Recommended Test Priorities

1. `graph` flow first: cover `src/graph/nodes/{writer,requirement,exporter,reviewers}.py` and `src/graph/routing/conditions.py`. These are the only files below `60%`, so they are the clearest blind spot.
2. `src/cli/kb.py` next: biggest absolute gap (`232` missing lines) and already flagged in `program.md` as a future split candidate.
3. `src/cli/generate.py` plus `src/api/routes/workflow.py`: both sit on core user paths, and together leave `142` lines untested.
4. Rerun this baseline after any Epic 8 large-file split so before/after comparisons stay credible.
