"""
機構記憶 Agent - 學習並儲存機關的使用偏好
"""
import json
from pathlib import Path
from typing import Any, Dict
from datetime import datetime
from rich.console import Console

console = Console()

class OrganizationalMemory:
    """
    儲存與讀取機關的使用偏好，包括：
    - 常用詞彙偏好（如：「惠請」vs「請」）
    - 署名格式偏好
    - 文風偏好（正式/簡潔）
    - 歷史修改模式
    """
    
    def __init__(self, storage_path: str = "./kb_data/agency_preferences.json"):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.preferences = self._load_preferences()
    
    def _load_preferences(self) -> Dict[str, Any]:
        """載入已儲存的偏好設定"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                console.print(f"[yellow]警告：無法載入偏好設定：{e}[/yellow]")
                return {}
        return {}
    
    def _save_preferences(self) -> None:
        """儲存偏好設定到檔案"""
        try:
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(self.preferences, f, ensure_ascii=False, indent=2)
        except Exception as e:
            console.print(f"[red]儲存偏好設定失敗：{e}[/red]")
    
    def get_agency_profile(self, agency_name: str) -> Dict[str, Any]:
        """取得特定機關的偏好設定"""
        return self.preferences.get(agency_name, {
            "formal_level": "standard",  # standard, formal, concise
            "preferred_terms": {},       # {"請": "惠請", ...}
            "signature_format": "default",
            "creation_date": datetime.now().isoformat(),
            "usage_count": 0
        })
    
    def update_preference(self, agency_name: str, key: str, value: Any) -> None:
        """更新特定偏好項目"""
        if agency_name not in self.preferences:
            self.preferences[agency_name] = self.get_agency_profile(agency_name)
        
        self.preferences[agency_name][key] = value
        self.preferences[agency_name]["last_updated"] = datetime.now().isoformat()
        self._save_preferences()
        console.print(f"[green]已更新 {agency_name} 的偏好設定：{key} = {value}[/green]")
    
    def learn_from_edit(self, agency_name: str, original: str, edited: str) -> None:
        """
        從使用者的手動修改中學習偏好
        （未來可使用 diff 演算法分析常見修改模式）
        """
        if agency_name not in self.preferences:
            self.preferences[agency_name] = self.get_agency_profile(agency_name)
        
        # 簡單範例：記錄修改次數
        self.preferences[agency_name]["usage_count"] = self.preferences[agency_name].get("usage_count", 0) + 1
        self.preferences[agency_name]["last_edit"] = datetime.now().isoformat()
        
        # TODO: 實作進階學習邏輯（詞彙替換模式、格式偏好等）
        
        self._save_preferences()
        console.print(f"[cyan]正在從 {agency_name} 的修改中學習...[/cyan]")
    
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
            terms_str = ", ".join([f"'{k}' → '{v}'" for k, v in profile["preferred_terms"].items()])
            hints.append(f"偏好詞彙：{terms_str}")
        
        if profile.get("signature_format") and profile["signature_format"] != "default":
            hints.append(f"署名格式：{profile['signature_format']}")
        
        if hints:
            return "\n".join([f"  - {h}" for h in hints])
        return ""
    
    def export_report(self) -> str:
        """匯出機構記憶統計報告"""
        report = "# 機構記憶統計\n\n"
        report += f"總計追蹤機關數：{len(self.preferences)}\n\n"
        
        for agency, profile in sorted(self.preferences.items(), key=lambda x: -x[1].get("usage_count", 0)):
            report += f"## {agency}\n"
            report += f"- 使用次數：{profile.get('usage_count', 0)}\n"
            report += f"- 正式程度：{profile.get('formal_level', 'standard')}\n"
            report += f"- 偏好詞彙數：{len(profile.get('preferred_terms', {}))}\n"
            if profile.get("last_updated"):
                report += f"- 最後更新：{profile['last_updated']}\n"
            report += "\n"
        
        return report
