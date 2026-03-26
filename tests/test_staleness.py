"""tests/test_staleness.py — StalenessChecker 單元測試。"""
from __future__ import annotations

import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from src.knowledge.staleness import (
    StalenessChecker,
    StalenessInfo,
    SOURCE_CONFIG,
    AUTO_UPDATABLE_SOURCES,
)


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _make_source_dir(tmp_path: Path, subdir: str, n_files: int = 1, age_days: float = 0) -> Path:
    """在 tmp_path 下建立測試目錄，並寫入 n_files 個 .md 檔案。
    age_days > 0 表示把檔案 mtime 向前調（模擬舊檔案）。
    """
    d = tmp_path / subdir
    d.mkdir(parents=True, exist_ok=True)
    for i in range(n_files):
        f = d / f"doc_{i}.md"
        f.write_text(f"# 文件 {i}\n內容", encoding="utf-8")
        if age_days > 0:
            old_time = time.time() - age_days * 86400
            import os
            os.utime(f, (old_time, old_time))
    return d


# ─────────────────────────────────────────────────────────────
# StalenessInfo 屬性測試
# ─────────────────────────────────────────────────────────────

class TestStalenessInfoProperties:

    def test_never_fetched_when_no_last_updated(self):
        info = StalenessInfo(
            source_name="測試",
            directory="kb_data/test",
            description="",
            level="A",
            max_age_days=7,
            fetch_cmd="fetch-test",
            last_updated=None,
            file_count=0,
        )
        assert info.never_fetched is True
        assert info.days_since_update == float("inf")
        assert info.is_stale is True
        assert info.status_icon == "⬜"

    def test_fresh_source_not_stale(self):
        recent = datetime.now(timezone.utc) - timedelta(days=3)
        info = StalenessInfo(
            source_name="測試",
            directory="kb_data/test",
            description="",
            level="A",
            max_age_days=7,
            fetch_cmd="fetch-test",
            last_updated=recent,
            file_count=5,
        )
        assert info.never_fetched is False
        assert info.is_stale is False
        assert info.status_icon == "✅"
        assert 2.9 < info.days_since_update < 3.1

    def test_stale_source(self):
        old = datetime.now(timezone.utc) - timedelta(days=15)
        info = StalenessInfo(
            source_name="測試",
            directory="kb_data/test",
            description="",
            level="A",
            max_age_days=7,
            fetch_cmd="fetch-test",
            last_updated=old,
            file_count=2,
        )
        assert info.is_stale is True
        assert info.status_icon == "❌"

    def test_exactly_at_max_age_not_stale(self):
        """等於 max_age_days 的當天不視為過期（嚴格 >）。"""
        edge = datetime.now(timezone.utc) - timedelta(days=7)
        info = StalenessInfo(
            source_name="測試",
            directory="kb_data/test",
            description="",
            level="A",
            max_age_days=7,
            fetch_cmd="fetch-test",
            last_updated=edge,
            file_count=1,
        )
        assert info.is_stale is False


# ─────────────────────────────────────────────────────────────
# StalenessChecker._get_latest_mtime
# ─────────────────────────────────────────────────────────────

class TestGetLatestMtime:

    def test_nonexistent_dir_returns_none(self, tmp_path):
        checker = StalenessChecker(base_dir=tmp_path)
        mtime, count = checker._get_latest_mtime(tmp_path / "does_not_exist")
        assert mtime is None
        assert count == 0

    def test_empty_dir_returns_none(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        checker = StalenessChecker(base_dir=tmp_path)
        mtime, count = checker._get_latest_mtime(empty)
        assert mtime is None
        assert count == 0

    def test_single_md_file(self, tmp_path):
        d = tmp_path / "laws"
        d.mkdir()
        (d / "law.md").write_text("# test", encoding="utf-8")
        checker = StalenessChecker(base_dir=tmp_path)
        mtime, count = checker._get_latest_mtime(d)
        assert mtime is not None
        assert isinstance(mtime, datetime)
        assert mtime.tzinfo is not None  # timezone-aware
        assert count == 1

    def test_multiple_files_returns_latest(self, tmp_path):
        d = tmp_path / "docs"
        d.mkdir()
        # 建立舊檔案
        old_file = d / "old.md"
        old_file.write_text("舊", encoding="utf-8")
        import os
        old_time = time.time() - 100
        os.utime(old_file, (old_time, old_time))
        # 建立新檔案
        new_file = d / "new.md"
        new_file.write_text("新", encoding="utf-8")
        # new_file 的 mtime 為現在

        checker = StalenessChecker(base_dir=tmp_path)
        mtime, count = checker._get_latest_mtime(d)
        assert count == 2
        # 回傳的 mtime 應接近現在（new_file），不是 old_file
        delta = datetime.now(timezone.utc) - mtime.astimezone(timezone.utc)
        assert delta.total_seconds() < 10

    def test_ignores_non_doc_extensions(self, tmp_path):
        d = tmp_path / "mixed"
        d.mkdir()
        (d / "data.md").write_text("文件", encoding="utf-8")
        (d / "script.py").write_text("# python", encoding="utf-8")
        (d / "image.png").write_bytes(b"\x89PNG")
        checker = StalenessChecker(base_dir=tmp_path)
        _, count = checker._get_latest_mtime(d)
        assert count == 1  # 只計 .md

    def test_json_and_yaml_counted(self, tmp_path):
        d = tmp_path / "meta"
        d.mkdir()
        (d / "a.md").write_text("md", encoding="utf-8")
        (d / "b.json").write_text("{}", encoding="utf-8")
        (d / "c.yaml").write_text("key: val", encoding="utf-8")
        checker = StalenessChecker(base_dir=tmp_path)
        _, count = checker._get_latest_mtime(d)
        assert count == 3


# ─────────────────────────────────────────────────────────────
# StalenessChecker.check_source
# ─────────────────────────────────────────────────────────────

class TestCheckSource:

    def test_unknown_source_returns_none(self, tmp_path):
        checker = StalenessChecker(base_dir=tmp_path)
        assert checker.check_source("不存在的來源") is None

    def test_known_source_no_dir(self, tmp_path):
        """目錄不存在 → never_fetched。"""
        checker = StalenessChecker(base_dir=tmp_path)
        info = checker.check_source("全國法規")
        assert info is not None
        assert info.source_name == "全國法規"
        assert info.never_fetched is True
        assert info.file_count == 0
        assert info.level == "A"

    def test_known_source_with_fresh_files(self, tmp_path):
        """目錄存在且有新鮮文件 → 不過期。"""
        _make_source_dir(tmp_path, "kb_data/regulations/laws", n_files=3, age_days=0)
        checker = StalenessChecker(base_dir=tmp_path)
        info = checker.check_source("全國法規")
        assert info is not None
        assert info.never_fetched is False
        assert info.file_count == 3
        assert info.is_stale is False

    def test_known_source_with_old_files(self, tmp_path):
        """目錄有超過 max_age_days 的舊檔案 → 過期。"""
        cfg = SOURCE_CONFIG["全國法規"]
        _make_source_dir(
            tmp_path,
            "kb_data/regulations/laws",
            n_files=2,
            age_days=cfg["max_age_days"] + 5,
        )
        checker = StalenessChecker(base_dir=tmp_path)
        info = checker.check_source("全國法規")
        assert info is not None
        assert info.is_stale is True


# ─────────────────────────────────────────────────────────────
# StalenessChecker.check_all
# ─────────────────────────────────────────────────────────────

class TestCheckAll:

    def test_returns_all_sources(self, tmp_path):
        checker = StalenessChecker(base_dir=tmp_path)
        results = checker.check_all()
        assert len(results) == len(SOURCE_CONFIG)

    def test_never_fetched_sources_appear_first(self, tmp_path):
        """當全部來源都未擷取時，Level A 應排在 Level B 前面。"""
        checker = StalenessChecker(base_dir=tmp_path)
        results = checker.check_all()
        level_a_indices = [i for i, r in enumerate(results) if r.level == "A"]
        level_b_indices = [i for i, r in enumerate(results) if r.level == "B"]
        if level_a_indices and level_b_indices:
            assert max(level_a_indices) < max(level_b_indices) or min(level_a_indices) < min(level_b_indices)

    def test_all_sources_have_required_fields(self, tmp_path):
        checker = StalenessChecker(base_dir=tmp_path)
        for info in checker.check_all():
            assert info.source_name
            assert info.fetch_cmd
            assert info.level in ("A", "B")
            assert info.max_age_days > 0


# ─────────────────────────────────────────────────────────────
# StalenessChecker.get_stale
# ─────────────────────────────────────────────────────────────

class TestGetStale:

    def test_all_never_fetched_are_stale(self, tmp_path):
        checker = StalenessChecker(base_dir=tmp_path)
        stale = checker.get_stale()
        assert len(stale) == len(SOURCE_CONFIG)  # 全部未擷取，全部過期

    def test_fresh_source_not_in_stale(self, tmp_path):
        _make_source_dir(tmp_path, "kb_data/regulations/laws", n_files=2, age_days=0)
        checker = StalenessChecker(base_dir=tmp_path)
        stale = checker.get_stale()
        stale_names = [s.source_name for s in stale]
        assert "全國法規" not in stale_names

    def test_max_age_days_override(self, tmp_path):
        """max_age_days=999 → 所有 <999 天的來源都不算過期。"""
        _make_source_dir(tmp_path, "kb_data/regulations/laws", n_files=1, age_days=10)
        checker = StalenessChecker(base_dir=tmp_path)
        stale = checker.get_stale(max_age_days=999)
        stale_names = [s.source_name for s in stale]
        assert "全國法規" not in stale_names

    def test_max_age_days_override_strict(self, tmp_path):
        """max_age_days=1 → 10 天前的檔案視為過期。"""
        _make_source_dir(tmp_path, "kb_data/regulations/laws", n_files=1, age_days=10)
        checker = StalenessChecker(base_dir=tmp_path)
        stale = checker.get_stale(max_age_days=1)
        stale_names = [s.source_name for s in stale]
        assert "全國法規" in stale_names


# ─────────────────────────────────────────────────────────────
# StalenessChecker.get_critical_stale
# ─────────────────────────────────────────────────────────────

class TestGetCriticalStale:

    def test_only_level_a_in_critical(self, tmp_path):
        checker = StalenessChecker(base_dir=tmp_path)
        critical = checker.get_critical_stale()
        for info in critical:
            assert info.level == "A"

    def test_level_b_not_in_critical(self, tmp_path):
        checker = StalenessChecker(base_dir=tmp_path)
        critical = checker.get_critical_stale()
        critical_names = {s.source_name for s in critical}
        for name, cfg in SOURCE_CONFIG.items():
            if cfg["level"] == "B":
                assert name not in critical_names


# ─────────────────────────────────────────────────────────────
# StalenessChecker.summary
# ─────────────────────────────────────────────────────────────

class TestSummary:

    def test_summary_keys(self, tmp_path):
        checker = StalenessChecker(base_dir=tmp_path)
        s = checker.summary()
        assert set(s.keys()) == {"total", "never_fetched", "stale", "ok", "critical_stale"}

    def test_summary_totals_add_up(self, tmp_path):
        checker = StalenessChecker(base_dir=tmp_path)
        s = checker.summary()
        assert s["never_fetched"] + s["stale"] + s["ok"] == s["total"]

    def test_summary_all_never_fetched(self, tmp_path):
        """無任何目錄時，全部應標記為 never_fetched。"""
        checker = StalenessChecker(base_dir=tmp_path)
        s = checker.summary()
        assert s["never_fetched"] == s["total"]
        assert s["stale"] == 0
        assert s["ok"] == 0


# ─────────────────────────────────────────────────────────────
# SOURCE_CONFIG 完整性檢查
# ─────────────────────────────────────────────────────────────

class TestSourceConfigIntegrity:

    def test_all_sources_have_required_keys(self):
        required = {"dir", "description", "max_age_days", "fetch_cmd", "level"}
        for name, cfg in SOURCE_CONFIG.items():
            missing = required - set(cfg.keys())
            assert not missing, f"{name} 缺少 key: {missing}"

    def test_all_levels_are_valid(self):
        for name, cfg in SOURCE_CONFIG.items():
            assert cfg["level"] in ("A", "B"), f"{name} level 無效：{cfg['level']}"

    def test_max_age_days_positive(self):
        for name, cfg in SOURCE_CONFIG.items():
            assert cfg["max_age_days"] > 0, f"{name} max_age_days 必須 > 0"

    def test_auto_updatable_sources_are_level_a(self):
        for name in AUTO_UPDATABLE_SOURCES:
            assert name in SOURCE_CONFIG, f"{name} 不在 SOURCE_CONFIG"
            assert SOURCE_CONFIG[name]["level"] == "A", f"{name} 應為 Level A"
