import logging
import os
import re
import tempfile
from abc import ABC, abstractmethod
from typing import Any
import yaml
from pathlib import Path

logger = logging.getLogger(__name__)

_MISSING = object()  # sentinel：區分「值為 None」和「key 不存在」

# 載入 .env 檔案
def load_dotenv() -> None:
    """從專案目錄載入 .env 檔案（自製輕量解析器）。

    僅讀取專案根目錄的 .env，不讀取使用者 home 目錄（避免
    跨專案環境汙染與測試隔離問題）。已存在的環境變數不會被覆蓋。

    **支援格式限制**:
    - 每行一組 ``KEY=VALUE``，不支援 ``export`` 前綴
    - 值可用成對的單引號或雙引號包裹（``KEY="val"``、``KEY='val'``）
    - 未引號的值支援行尾 ``#`` 內聯註解
    - 不支援多行值、跳脫字元（``\\n``、``\\"`` 等不會被展開）
    - ``#`` 開頭的行視為註解
    """
    env_path = Path(__file__).parent.parent.parent / ".env"
    if not env_path.exists():
        return
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    # 移除引號（配對引號）或未引號值的內聯註解
                    if (value.startswith('"') and value.endswith('"')) or \
                       (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]
                    elif not (value.startswith('"') or value.startswith("'")):
                        value = value.split('#')[0].rstrip()
                    if key not in os.environ:  # 不覆蓋已存在的環境變數
                        os.environ[key] = value
    except OSError as exc:
        logger.warning("無法讀取 .env 檔案 %s: %s", env_path, exc)

# 啟動時自動載入
load_dotenv()

class LLMProvider(ABC):
    """LLM 提供者的抽象基底類別。"""

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """根據提示語產生文字。"""
        pass

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """產生文字的嵌入向量。"""
        pass

class ConfigManager:
    """管理設定檔的載入與儲存。"""

    def __init__(self, config_path: str = "config.yaml") -> None:
        self.config_path = Path(config_path)
        self.config = self._load_config()

    def _expand_env_vars(self, value: Any, _path: str = "") -> Any:
        """遞迴展開字串值中的環境變數。

        Args:
            value: 要展開的值
            _path: 內部追蹤用的設定路徑（如 "providers.gemini.api_key"），
                   用於判斷是否為非活躍 provider 的設定以降低警告噪音。

        Note:
            providers.* 路徑下的未設定環境變數使用 debug 層級記錄。
            這包含所有 providers 子路徑（含活躍的 provider），因此若活躍
            provider 的 key 也放在 providers.* 路徑下，缺失時不會發出 warning。
            CLI 使用者應透過 ``gov-ai config validate`` 檢查設定完整性。
        """
        if isinstance(value, str):
            # Match ${VAR_NAME}
            match = re.match(r"^\$\{(.+)\}$", value)
            if match:
                env_var = match.group(1)
                resolved = os.getenv(env_var)
                if resolved is None:
                    # 對非活躍 provider 的設定僅記錄 debug，避免警告噪音
                    if _path.startswith("providers."):
                        logger.debug(
                            "環境變數 %s 未設定（路徑: %s），解析為空字串。",
                            env_var, _path,
                        )
                    else:
                        logger.warning(
                            "環境變數 %s 未設定，config 中的 ${%s} 將解析為空字串。"
                            "請在 .env 檔案或環境變數中設定此值。",
                            env_var, env_var,
                        )
                    return ""
                return resolved
            return value
        elif isinstance(value, dict):
            return {
                k: self._expand_env_vars(v, f"{_path}.{k}" if _path else k)
                for k, v in value.items()
            }
        elif isinstance(value, list):
            return [self._expand_env_vars(v, _path) for v in value]
        return value

    def _load_config(self) -> dict[str, Any]:
        if not self.config_path.exists():
            return self._create_default_config()
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                raw_config = yaml.safe_load(f) or {}
                return self._expand_env_vars(raw_config)
        except Exception as e:
            logger.error("設定檔載入失敗: %s", e)
            return self._create_default_config()

    def _create_default_config(self) -> dict[str, Any]:
        default_config = {
            "llm": {
                "provider": "ollama",
                "model": "mistral",
                "api_key": "",
                "base_url": "http://127.0.0.1:11434"
            },
            "knowledge_base": {
                "path": "./kb_data",
                "contextual_retrieval": False,
            }
        }
        # Only save if it doesn't exist to avoid overwriting
        if not self.config_path.exists():
            try:
                self.config_path.parent.mkdir(parents=True, exist_ok=True)
                self.save_config(default_config)
            except OSError as e:
                logger.warning("無法建立預設設定檔: %s", e)
        return default_config

    def save_config(self, config: dict[str, Any]) -> None:
        """原子寫入設定檔（先寫暫存檔再 rename，防止中途崩潰損毀）。"""
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self.config_path.parent),
            suffix=".tmp",
            prefix=".config_",
        )
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
            os.replace(tmp_path, str(self.config_path))
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        self.config = config

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, _MISSING)
                if value is _MISSING:
                    return default
            else:
                return default
        return value
