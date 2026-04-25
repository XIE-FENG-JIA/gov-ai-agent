# Integration Test Skip Audit — 2026-04-25

> 任務：T-INT-TESTS-SKIP-AUDIT（P1；v7.8 開）
> 目的：分類 `tests/integration/` 下所有 skip，確認根因、標 reason category，消除 3 輪未深挖技術債。

---

## 方法

```bash
python -m pytest tests/ -q --ignore=tests/integration --tb=no   # → 3926 passed, 0 skipped
python -m pytest tests/integration/ -v --tb=no                   # → 10 skipped + 1 collected
```

主套件（`--ignore=tests/integration`）無 skip；所有 10 個 skip 集中在 `tests/integration/test_sources_smoke.py`。

---

## Skip 清單（共 10 個）

| # | 測試函式 | 來源 adapter | reason category | skip 條件 | 根因 |
|---|---------|-------------|-----------------|-----------|------|
| 1 | `test_live_source_smoke_normalizes_one_public_doc[mojlaw]` | MojLawAdapter | **live-API gating** | `GOV_AI_RUN_INTEGRATION != "1"` | 需真實 HTTP，CI/offline 不宜跑 |
| 2 | `test_live_source_smoke_normalizes_one_public_doc[datagovtw]` | DataGovTwAdapter | **live-API gating** | 同上 | 同上；robots.txt 另禁 API endpoint |
| 3 | `test_live_source_smoke_normalizes_one_public_doc[executiveyuanrss]` | ExecutiveYuanRssAdapter | **live-API gating** | 同上 | 同上 |
| 4 | `test_live_source_smoke_normalizes_one_public_doc[mohw]` | MohwRssAdapter | **live-API gating** | 同上 | 同上 |
| 5 | `test_live_source_smoke_normalizes_one_public_doc[fda]` | FdaApiAdapter | **live-API gating** | 同上 | 同上 |
| 6 | `test_live_source_loader_respects_default_rate_limit[mojlaw]` | MojLawAdapter | **live-API gating** | 同上 | 需真實 request timing（≥2s）|
| 7 | `test_live_source_loader_respects_default_rate_limit[datagovtw]` | DataGovTwAdapter | **live-API gating** | 同上 | 同上 |
| 8 | `test_live_source_loader_respects_default_rate_limit[executiveyuanrss]` | ExecutiveYuanRssAdapter | **live-API gating** | 同上 | 同上 |
| 9 | `test_live_source_loader_respects_default_rate_limit[mohw]` | MohwRssAdapter | **live-API gating** | 同上 | 同上 |
| 10 | `test_live_source_loader_respects_default_rate_limit[fda]` | FdaApiAdapter | **live-API gating** | 同上 | 同上 |

---

## Reason Category 定義

| Category | 說明 | 本次數量 |
|----------|------|---------|
| **live-API gating** | 需真實 HTTP / rate-limit timing；離線/CI 不允許發真實請求 | 10 |
| **環境缺失** | 套件未安裝（chromadb / multipart）或 env var 缺 | 0（主套件內 chromadb/multipart 均已裝，條件均為 False，測試正常 PASS） |
| **故意 skip** | 業務邏輯的條件 skip（如「該檔案無法規引用」）；inline `pytest.skip()` | 0（`test_golden_suite.py` 內的 inline skip 是動態業務判斷，非 class-level skip，不算 skip 計數） |

---

## 主套件（`--ignore=tests/integration`）skip 分析

```
3926 passed, 0 skipped, 2 warnings
```

- `@pytest.mark.skipif(not _has_chromadb, ...)` — chromadb 已安裝，條件為 False → **不 skip**
- `@pytest.mark.skipif(not _has_multipart, ...)` — multipart 已安裝，條件為 False → **不 skip**
- `@pytest.mark.skipif(sys.platform != "win32", ...)` — 本機 Windows，條件為 False → **不 skip**
- `pytest.skip(...)` in `test_golden_suite.py` — 動態 skip（每份文件判斷是否有法規/主旨），這類 skip 在 pytest 計數內但已被涵蓋於 3926 passed 中（golden_suite 測試用 `if not refs: pytest.skip(...)` 邏輯，正常計入 pass/skip 統計；不在本輪關注範圍）

---

## 結論

- **全部 10 skip 屬 live-API gating**，設計正確：offline/CI 不發真實 HTTP 是合規要求（robots.txt / rate limit）
- **無環境缺失 skip**（本機依賴完整）
- **無故意 skip 技術債**
- 後續行動：若要啟用 integration smoke，設 `GOV_AI_RUN_INTEGRATION=1` 並在有網路環境跑 `python -m pytest tests/integration/ -v`

---

## 驗證指令

```bash
# 確認主套件 0 skip
python -m pytest tests/ -q --ignore=tests/integration --tb=no | tail -1
# 確認 integration 10 skip
python -m pytest tests/integration/ -v --tb=no | grep -c "SKIPPED"
```
