"""知識庫來源資料過期偵測模組。

提供 StalenessChecker 類別，追蹤各來源的最後更新時間（依檔案系統 mtime），
協助使用者識別哪些法規資料需要重新擷取，支援法規自動更新機制。

使用方式：
    checker = StalenessChecker()
    stale = checker.get_stale()          # 取得所有過期來源
    report = checker.check_all()         # 取得完整狀態報告
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# 各來源設定：目錄路徑、說明、建議更新頻率（天）、對應 CLI 指令、來源等級
SOURCE_CONFIG: dict[str, dict] = {
    "全國法規": {
        "dir": "kb_data/regulations/laws",
        "description": "公文程式條例、行政程序法等核心法規",
        "max_age_days": 30,
        "fetch_cmd": "fetch-laws",
        "level": "A",
    },
    "行政院公報": {
        "dir": "kb_data/examples/gazette",
        "description": "近期行政院公報（法規命令、行政規則）",
        "max_age_days": 7,
        "fetch_cmd": "fetch-gazette",
        "level": "A",
    },
    "司法院判決": {
        "dir": "kb_data/regulations/judicial",
        "description": "近期司法院裁判書",
        "max_age_days": 30,
        "fetch_cmd": "fetch-judicial",
        "level": "A",
    },
    "法務部函釋": {
        "dir": "kb_data/regulations/interpretations",
        "description": "行政函釋與解釋令",
        "max_age_days": 30,
        "fetch_cmd": "fetch-interpretations",
        "level": "A",
    },
    "地方法規": {
        "dir": "kb_data/regulations/local",
        "description": "直轄市與縣市地方自治法規",
        "max_age_days": 30,
        "fetch_cmd": "fetch-local",
        "level": "A",
    },
    "考試院法規": {
        "dir": "kb_data/regulations/exam_yuan",
        "description": "考試院相關法規",
        "max_age_days": 30,
        "fetch_cmd": "fetch-examyuan",
        "level": "A",
    },
    "行政院公報（全量）": {
        "dir": "kb_data/policies/gazette_bulk",
        "description": "行政院公報 bulk ZIP 全量下載",
        "max_age_days": 7,
        "fetch_cmd": "fetch-gazette --bulk",
        "level": "A",
    },
    "立法院": {
        "dir": "kb_data/policies/legislative",
        "description": "立法院法律草案與審議資料",
        "max_age_days": 7,
        "fetch_cmd": "fetch-legislative",
        "level": "B",
    },
    "立法院議事紀錄": {
        "dir": "kb_data/policies/legislative_debates",
        "description": "立法院委員會審議紀錄",
        "max_age_days": 7,
        "fetch_cmd": "fetch-debates",
        "level": "B",
    },
    "政府採購公告": {
        "dir": "kb_data/policies/procurement",
        "description": "招標公告、決標公告",
        "max_age_days": 7,
        "fetch_cmd": "fetch-procurement",
        "level": "B",
    },
    "政府開放資料": {
        "dir": "kb_data/policies/opendata",
        "description": "data.gov.tw 開放資料集",
        "max_age_days": 7,
        "fetch_cmd": "fetch-opendata",
        "level": "B",
    },
    "警政署資料": {
        "dir": "kb_data/policies/npa",
        "description": "警政署開放資料",
        "max_age_days": 14,
        "fetch_cmd": "fetch-npa",
        "level": "B",
    },
    "主計總處統計": {
        "dir": "kb_data/policies/statistics",
        "description": "主計總處統計資料",
        "max_age_days": 30,
        "fetch_cmd": "fetch-statistics",
        "level": "B",
    },
    "監察院": {
        "dir": "kb_data/policies/control_yuan",
        "description": "監察院糾正案、彈劾案等",
        "max_age_days": 30,
        "fetch_cmd": "fetch-controlyuan",
        "level": "B",
    },
}

# 只有這些 Level A 來源支援自動更新（其餘 Level B 需手動執行，因參數較多）
AUTO_UPDATABLE_SOURCES = frozenset({
    "全國法規",
    "行政院公報",
    "司法院判決",
    "法務部函釋",
    "地方法規",
    "考試院法規",
})

_DOC_EXTENSIONS = frozenset({".md", ".json", ".yaml", ".txt"})


@dataclass
class StalenessInfo:
    """單一來源的過期資訊。"""

    source_name: str
    directory: str
    description: str
    level: str          # "A" 或 "B"
    max_age_days: int
    fetch_cmd: str
    last_updated: datetime | None   # None = 從未擷取
    file_count: int

    @property
    def days_since_update(self) -> float:
        """距上次更新的天數。未曾更新回傳 float('inf')。"""
        if self.last_updated is None:
            return float("inf")
        now = datetime.now(timezone.utc)
        delta = now - self.last_updated.astimezone(timezone.utc)
        return delta.total_seconds() / 86400

    @property
    def is_stale(self) -> bool:
        """是否已超過建議更新頻率。"""
        return self.days_since_update > self.max_age_days

    @property
    def never_fetched(self) -> bool:
        """是否從未擷取過（目錄不存在或沒有任何文件）。"""
        return self.last_updated is None

    @property
    def is_auto_updatable(self) -> bool:
        """是否支援 auto-update 自動更新。"""
        return self.source_name in AUTO_UPDATABLE_SOURCES

    @property
    def status_icon(self) -> str:
        if self.never_fetched:
            return "⬜"   # 從未擷取
        if self.is_stale:
            return "❌"   # 過期
        return "✅"        # 正常


class StalenessChecker:
    """檢查知識庫各來源的資料新鮮度。

    以檔案系統 mtime 為判斷依據，無需額外追蹤基礎設施。
    每次呼叫 check_* 方法時即時讀取最新狀態。
    """

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or Path(".")

    def _get_latest_mtime(self, dir_path: Path) -> tuple[datetime | None, int]:
        """掃描目錄，回傳 (最新修改時間, 文件數量)。

        僅計算 .md / .json / .yaml / .txt 等知識庫文件。
        目錄不存在或無文件時回傳 (None, 0)。
        """
        if not dir_path.exists() or not dir_path.is_dir():
            return None, 0

        mtimes: list[float] = []
        try:
            for f in dir_path.rglob("*"):
                if f.is_file() and f.suffix.lower() in _DOC_EXTENSIONS:
                    mtimes.append(f.stat().st_mtime)
        except OSError as exc:
            logger.warning("無法讀取目錄 %s: %s", dir_path, exc)
            return None, 0

        if not mtimes:
            return None, 0

        latest = datetime.fromtimestamp(max(mtimes), tz=timezone.utc)
        return latest, len(mtimes)

    def check_source(self, source_name: str) -> StalenessInfo | None:
        """檢查單一來源的新鮮度。來源名稱不存在回傳 None。"""
        config = SOURCE_CONFIG.get(source_name)
        if config is None:
            return None

        dir_path = self.base_dir / config["dir"]
        last_updated, file_count = self._get_latest_mtime(dir_path)

        return StalenessInfo(
            source_name=source_name,
            directory=config["dir"],
            description=config["description"],
            level=config["level"],
            max_age_days=config["max_age_days"],
            fetch_cmd=config["fetch_cmd"],
            last_updated=last_updated,
            file_count=file_count,
        )

    def check_all(self) -> list[StalenessInfo]:
        """檢查所有來源，回傳按優先度排序的 StalenessInfo 清單。

        排序邏輯：從未更新 > 過期最嚴重 > 正常；Level A 優先於 Level B。
        """
        results: list[StalenessInfo] = []
        for source_name in SOURCE_CONFIG:
            info = self.check_source(source_name)
            if info is not None:
                results.append(info)

        results.sort(key=lambda x: (
            # Level A 優先（0），Level B 其次（1）
            0 if x.level == "A" else 1,
            # 從未更新最優先（0），過期次之（1），正常最後（2）
            0 if x.never_fetched else (1 if x.is_stale else 2),
            # 同等優先度內，過期越嚴重越前面（days 越大越前）
            -x.days_since_update if not x.never_fetched else 0,
        ))
        return results

    def get_stale(self, max_age_days: int | None = None) -> list[StalenessInfo]:
        """回傳所有過期（或從未更新）的來源。

        Args:
            max_age_days: 覆蓋各來源的 max_age_days 設定。
                          None 則使用各來源自己的設定。
        """
        all_sources = self.check_all()
        if max_age_days is None:
            return [s for s in all_sources if s.is_stale]
        return [s for s in all_sources if s.days_since_update > max_age_days]

    def get_critical_stale(self) -> list[StalenessInfo]:
        """回傳 Level A 權威來源中過期的項目（最高優先警告）。"""
        return [s for s in self.get_stale() if s.level == "A"]

    def summary(self) -> dict:
        """回傳摘要統計，供 CLI 快速顯示。"""
        all_sources = self.check_all()
        total = len(all_sources)
        never = sum(1 for s in all_sources if s.never_fetched)
        stale = sum(1 for s in all_sources if s.is_stale and not s.never_fetched)
        ok = total - never - stale
        critical = sum(1 for s in all_sources if s.is_stale and s.level == "A")
        return {
            "total": total,
            "never_fetched": never,
            "stale": stale,
            "ok": ok,
            "critical_stale": critical,
        }
