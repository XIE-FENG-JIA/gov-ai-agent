# Spec: Fat-File Rotation Iteration 3

## Summary

Third package-split iteration. Breaks three large Python modules into
packages while preserving `from <old.path> import <Name>` contracts. Restores
the repo-wide 400-line anchor by turning the largest historical blind spot
(`rebuild.py 572`) into a 4-module package discovered by the new sensor.

## ADDED Requirements

### Requirement: No module larger than 300 lines after rotation

After iteration 3 lands, every file produced by the three splits
(`src/cli/kb/rebuild/*.py`, `src/sources/datagovtw/*.py`,
`src/api/routes/agents/*.py`) MUST be ≤ 300 lines. The sensor's
`fat_files.red_over_400` count for these three modules MUST be 0, and none
of them appears in the `yellow_350_to_400` tier.

#### Scenario: sensor reports zero red-tier fat files for rotated modules

- **WHEN** `python scripts/sensor_refresh.py` runs after merge
- **THEN** `fat_files.red_over_400` is an empty list
- **AND** the three ex-fat module basenames do not appear in
  `fat_files.yellow_350_to_400`

### Requirement: Import contract preserved through `__init__.py` re-exports

Every existing `from src.cli.kb.rebuild import X` / `from src.sources.datagovtw
import X` / `from src.api.routes.agents import X` call site MUST continue
resolving without source-code edits elsewhere. The splits rely on
`__init__.py` re-export exactly as iterations 7–9 of `T-FAT-ROTATE-V2`
demonstrated (e.g., `src/agents/fact_checker/__init__.py`).

FastAPI router paths served by `src/api/routes/agents/__init__.py` MUST be
byte-identical to the pre-split paths.

#### Scenario: import paths keep resolving

- **GIVEN** a module uses `from src.sources.datagovtw import DataGovTwAdapter`
- **WHEN** the split reorganises the module into a package
- **THEN** that import still resolves to the same class
- **AND** `pytest tests/test_datagovtw_adapter.py -q` runs without changes

#### Scenario: FastAPI routes unchanged after agents split

- **GIVEN** the FastAPI test client hits `/api/v1/agents/...`
- **WHEN** the router is served from the new package
- **THEN** the route path, method, and response model stay identical
