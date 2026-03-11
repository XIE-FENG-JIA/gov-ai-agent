"""
機構記憶 Agent - 學習並儲存機關的使用偏好
"""
import difflib
import json
import logging
import os
import re
import tempfile
import threading
from pathlib import Path
from typing import Any
from datetime import datetime
from rich.console import Console

logger = logging.getLogger(__name__)
console = Console()

class OrganizationalMemory:
    """
    儲存與讀取機關的使用偏好，包括：
    - 常用詞彙偏好（如：「惠請」vs「請」）
    - 署名格式偏好
    - 文風偏好（正式/簡潔）
    - 歷史修改模式
    """

    def __init__(self, storage_path: str = "./kb_data/agency_preferences.json") -> None:
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.preferences = self._load_preferences()

    def _load_preferences(self) -> dict[str, Any]:
        """載入已儲存的偏好設定"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                # 保留損毀備份，避免後續覆蓋導致永久資料遺失
                backup_path = self.storage_path.with_suffix(".json.bak")
                try:
                    import shutil
                    shutil.copy2(str(self.storage_path), str(backup_path))
                    logger.warning("偏好設定損毀，已備份至 %s", backup_path)
                except OSError:
                    pass
                console.print(f"[yellow]警告：無法載入偏好設定：{e}（已備份損毀檔案）[/yellow]")
                return {}
        return {}

    def _save_preferences(self) -> None:
        """原子寫入偏好設定到檔案（先寫暫存檔再 rename，防止中途崩潰損毀）。"""
        try:
            fd, tmp_path = tempfile.mkstemp(
                dir=str(self.storage_path.parent),
                suffix=".tmp",
                prefix=".prefs_",
            )
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    json.dump(self.preferences, f, ensure_ascii=False, indent=2)
                # 原子替換：Windows 上 os.replace 也是原子的
                os.replace(tmp_path, str(self.storage_path))
            except BaseException:
                # 清理暫存檔
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except Exception as e:
            logger.warning("儲存偏好設定失敗: %s", e)
            console.print(f"[red]儲存偏好設定失敗：{e}[/red]")

    def get_agency_profile(self, agency_name: str) -> dict[str, Any]:
        """取得特定機關的偏好設定"""
        return self.preferences.get(agency_name, {
            "formal_level": "standard",  # standard, formal, concise
            "preferred_terms": {},       # {"請": "惠請", ...}
            "signature_format": "default",
            "creation_date": datetime.now().isoformat(),
            "usage_count": 0
        })

    def update_preference(self, agency_name: str, key: str, value: Any) -> None:
        """更新特定偏好項目（執行緒安全）。"""
        with self._lock:
            if agency_name not in self.preferences:
                self.preferences[agency_name] = self.get_agency_profile(agency_name)

            self.preferences[agency_name][key] = value
            self.preferences[agency_name]["last_updated"] = datetime.now().isoformat()
            self._save_preferences()
        console.print(f"[green]已更新 {agency_name} 的偏好設定：{key} = {value}[/green]")

    def learn_from_edit(self, agency_name: str, original: str, edited: str) -> None:
        """
        從使用者的手動修改中學習偏好（執行緒安全）。

        使用 difflib 分析修改內容，提取常見的詞彙替換模式。
        """
        # 在鎖外計算 diff（純計算，無共享狀態）
        replacements = self._extract_replacements(original, edited)

        with self._lock:
            if agency_name not in self.preferences:
                self.preferences[agency_name] = self.get_agency_profile(agency_name)

            self.preferences[agency_name]["usage_count"] = self.preferences[agency_name].get("usage_count", 0) + 1
            self.preferences[agency_name]["last_edit"] = datetime.now().isoformat()

            if replacements:
                preferred = self.preferences[agency_name].get("preferred_terms", {})
                for old_term, new_term in replacements:
                    preferred[old_term] = new_term
                self.preferences[agency_name]["preferred_terms"] = preferred

            self._save_preferences()
        console.print(f"[cyan]正在從 {agency_name} 的修改中學習...[/cyan]")

    @staticmethod
    def _extract_replacements(original: str, edited: str) -> list[tuple[str, str]]:
        """從 diff 中提取短語級替換（同長度或相近長度的替換）。"""
        replacements: list[tuple[str, str]] = []
        matcher = difflib.SequenceMatcher(None, original, edited)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "replace":
                old_fragment = original[i1:i2].strip()
                new_fragment = edited[j1:j2].strip()
                # 僅學習短語級替換（2-20 字），避免噪音
                if (2 <= len(old_fragment) <= 20
                        and 2 <= len(new_fragment) <= 20
                        and not re.search(r"[.。\n]", old_fragment)):
                    replacements.append((old_fragment, new_fragment))
        return replacements

    def get_writing_hints(self, agency_name: str) -> str:
        """
        為 WriterAgent 生成提示語，讓它遵循該機關的偏好
        """
        profile = self.get_agency_profile(agency_name)

        hints = []

        if profile.get("formal_level") == "formal":
            hints.append("使用較為正式的用語（如：惠請、敬請）")
        elif profile.get("formal_level") == "concise":
            hints.append("使用簡潔明確的用語，避免冗詞贅字")

        if profile.get("preferred_terms"):
            # 限制數量並截斷長度，防止 stored prompt injection
            safe_terms = []
            for k, v in list(profile["preferred_terms"].items())[:20]:
                sk = str(k)[:30].replace("'", "").replace("\n", "")
                sv = str(v)[:30].replace("'", "").replace("\n", "")
                safe_terms.append(f"'{sk}' → '{sv}'")
            terms_str = ", ".join(safe_terms)
            hints.append(f"偏好詞彙：{terms_str}")

        if profile.get("signature_format") and profile["signature_format"] != "default":
            hints.append(f"署名格式：{profile['signature_format']}")

        if hints:
            return "\n".join([f"  - {h}" for h in hints])
        return ""

    def export_report(self) -> str:
        """匯出機構記憶統計報告"""
        parts = [
            "# 機構記憶統計\n",
            f"總計追蹤機關數：{len(self.preferences)}\n",
        ]

        for agency, profile in sorted(
            self.preferences.items(), key=lambda x: -x[1].get("usage_count", 0)
        ):
            parts.append(f"## {agency}")
            parts.append(f"- 使用次數：{profile.get('usage_count', 0)}")
            parts.append(f"- 正式程度：{profile.get('formal_level', 'standard')}")
            parts.append(f"- 偏好詞彙數：{len(profile.get('preferred_terms', {}))}")
            if profile.get("last_updated"):
                parts.append(f"- 最後更新：{profile['last_updated']}")
            parts.append("")

        return "\n".join(parts)
