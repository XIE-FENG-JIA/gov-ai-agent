import logging
import os
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List
import yaml
from pathlib import Path

logger = logging.getLogger(__name__)

# 載入 .env 檔案
def load_dotenv() -> None:
    """從專案目錄和使用者目錄載入 .env 檔案"""
    env_paths = [
        Path(__file__).parent.parent.parent / ".env",  # 專案根目錄
        Path.home() / ".env",  # 使用者目錄
    ]
    for env_path in env_paths:
        if env_path.exists():
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key not in os.environ:  # 不覆蓋已存在的環境變數
                            os.environ[key] = value

# 啟動時自動載入
load_dotenv()

class LLMProvider(ABC):
    """LLM 提供者的抽象基底類別。"""

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """根據提示語產生文字。"""
        pass

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """產生文字的嵌入向量。"""
        pass

class ConfigManager:
    """管理設定檔的載入與儲存。"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self.config = self._load_config()

    def _expand_env_vars(self, value: Any) -> Any:
        """遞迴展開字串值中的環境變數。"""
        if isinstance(value, str):
            # Match ${VAR_NAME}
            match = re.match(r"^\$\{(.+)\}$", value)
            if match:
                env_var = match.group(1)
                return os.getenv(env_var, "") # Return empty string if not found
            return value
        elif isinstance(value, dict):
            return {k: self._expand_env_vars(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._expand_env_vars(v) for v in value]
        return value

    def _load_config(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            return self._create_default_config()
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                raw_config = yaml.safe_load(f) or {}
                return self._expand_env_vars(raw_config)
        except Exception as e:
            logger.error("設定檔載入失敗: %s", e)
            return self._create_default_config()

    def _create_default_config(self) -> Dict[str, Any]:
        default_config = {
            "llm": {
                "provider": "ollama",
                "model": "mistral",
                "api_key": "",
                "base_url": "http://localhost:11434"
            },
            "knowledge_base": {
                "path": "./kb_data"
            }
        }
        # Only save if it doesn't exist to avoid overwriting
        if not self.config_path.exists():
            self.save_config(default_config)
        return default_config

    def save_config(self, config: Dict[str, Any]) -> None:
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
            
    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default
