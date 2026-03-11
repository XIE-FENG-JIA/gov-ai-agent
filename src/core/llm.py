import random
import logging
import threading
import litellm
from src.core.config import LLMProvider
from src.core.constants import LLM_GENERATION_TIMEOUT, LLM_CHECK_TIMEOUT

logger = logging.getLogger(__name__)


# ============================================================
# LLM 自訂例外類別
# ============================================================

class LLMError(Exception):
    """LLM 服務錯誤基礎類別。"""
    pass


class LLMConnectionError(LLMError):
    """無法連線到 LLM 服務。"""
    pass


class LLMAuthError(LLMError):
    """API Key 無效或認證失敗。"""
    pass

# 抑制 LiteLLM 的冗長錯誤訊息，只在真正需要除錯時開啟
litellm.suppress_debug_info = True
litellm.set_verbose = False
logging.getLogger("LiteLLM").setLevel(logging.ERROR)

class MockLLMProvider(LLMProvider):
    """模擬 LLM 提供者，用於不需要真實後端的測試。"""

    def __init__(self, provider_config: dict) -> None:
        self.model = provider_config.get("model", "mock-model")

    def generate(self, prompt: str, **kwargs) -> str:
        """產生模擬文字。"""
        # 防護空值輸入
        if not prompt or not prompt.strip():
            return ""
        return f"[MOCK] Generated response for: {prompt[:20]}..."

    def embed(self, text: str) -> list[float]:
        """產生固定的模擬嵌入向量（維度 384，執行緒安全）。"""
        # 防護空值輸入
        if not text or not text.strip():
            return []
        rng = random.Random(len(text))
        return [rng.random() for _ in range(384)]

class LiteLLMProvider(LLMProvider):
    """使用 LiteLLM 的 LLM 提供者實作。"""

    def check_connectivity(self, timeout: int = 5) -> tuple[bool, str]:
        """快速測試 LLM 連線是否正常。

        Args:
            timeout: 連線逾時秒數（預設 5 秒）

        Returns:
            (成功與否, 錯誤訊息或空字串)
        """
        try:
            litellm.completion(
                model=self.model_name,
                messages=[{"role": "user", "content": "Hi"}],
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=timeout,
                max_tokens=1,
            )
            return True, ""
        except Exception as e:
            error_msg = str(e)
            if "ConnectionError" in error_msg or "10061" in error_msg or "拒絕連線" in error_msg:
                if self.provider == "ollama":
                    return False, "無法連線到 Ollama 服務。請確認已啟動：ollama serve"
                return False, "無法連線到 LLM 服務，請確認網路連線。"
            if "AuthenticationError" in error_msg or "401" in error_msg or "Invalid API Key" in error_msg:
                return False, "API Key 無效或已過期。請確認已設定：export LLM_API_KEY=your-key"
            if "timeout" in error_msg.lower() or "Timeout" in error_msg:
                return False, f"LLM 連線逾時（{timeout} 秒）。請確認服務是否正常運作。"
            return False, f"LLM 連線失敗：{error_msg[:100]}"

    def __init__(self, provider_config: dict) -> None:
        self._embedding_error_shown: bool = False
        self._error_lock: threading.Lock = threading.Lock()
        self.provider = provider_config.get("provider", "ollama")
        self.model = provider_config.get("model", "mistral")
        self.api_key = provider_config.get("api_key")
        self.base_url = provider_config.get("base_url")

        # Embedding Config
        self.emb_provider = provider_config.get("embedding_provider", "ollama")
        self.emb_model = provider_config.get("embedding_model", "llama3.1:8b")
        self.emb_base_url = provider_config.get("embedding_base_url", "http://localhost:11434")

        # Validate API Key for cloud providers
        if self.provider in ["gemini", "openrouter"] and not self.api_key:
            logger.warning("找不到 %s 的 API Key，請求可能失敗", self.provider)

        # Construct the full model name for litellm generation
        if self.provider == "ollama":
            self.model_name = f"ollama/{self.model}"
        elif self.provider == "gemini":
            if not self.model.startswith("gemini/"):
                self.model_name = f"gemini/{self.model}"
            else:
                self.model_name = self.model
        elif self.provider == "openrouter":
            if not self.model.startswith("openrouter/"):
                self.model_name = f"openrouter/{self.model}"
            else:
                self.model_name = self.model
        else:
            self.model_name = self.model

    def generate(self, prompt: str, **kwargs) -> str:
        # 防護空值輸入
        if not prompt or not prompt.strip():
            logger.warning("LLM generate 收到空的 prompt，回傳空字串")
            return ""
        try:
            response = litellm.completion(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=LLM_GENERATION_TIMEOUT,
                **kwargs
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            error_msg = str(e)
            # 提供更清楚的錯誤訊息並拋出對應的自訂例外
            if "ConnectionError" in error_msg or "10061" in error_msg or "拒絕連線" in error_msg:
                logger.error(
                    "無法連線到 LLM 服務。若使用 Ollama，請確認已執行 'ollama serve'；"
                    "若使用雲端服務，請檢查網路連線。"
                )
                raise LLMConnectionError("無法連線到 LLM 服務，請確認服務已啟動。") from e
            if "AuthenticationError" in error_msg or "401" in error_msg or "Invalid API Key" in error_msg:
                logger.error("API Key 無效或已過期，請檢查設定檔中的 api_key。")
                raise LLMAuthError("API Key 無效，請檢查設定檔。") from e
            logger.error("LLM 生成失敗: %s", e)
            raise LLMError(f"LLM 生成失敗 — {error_msg}") from e

    def embed(self, text: str) -> list[float]:
        # 防護空值輸入
        if not text or not text.strip():
            logger.warning("LLM embed 收到空的文字，回傳空列表")
            return []
        try:
            # Construct embedding model name
            if self.emb_provider == "ollama":
                emb_model_name = f"ollama/{self.emb_model}"
            elif self.emb_provider == "gemini":
                emb_model_name = "gemini/text-embedding-004"
            elif self.emb_provider == "openrouter":
                emb_model_name = f"openrouter/{self.emb_model}"
            else:
                emb_model_name = self.emb_model

            # Use specific embedding credentials (usually same as main or none for ollama)
            # For simplicity, we assume Ollama needs no key, others use main key
            api_key = self.api_key if self.emb_provider != "ollama" else None
            base_url = self.emb_base_url if self.emb_provider == "ollama" else self.base_url

            response = litellm.embedding(
                model=emb_model_name,
                input=[text],
                api_key=api_key,
                base_url=base_url,
                timeout=LLM_CHECK_TIMEOUT,
            )
            if not response.data:
                logger.warning("Embedding 回應中無資料")
                return []
            return response.data[0]['embedding']
        except Exception as e:
            error_msg = str(e)
            if "ConnectionError" in error_msg or "拒絕連線" in error_msg or "10061" in error_msg:
                with self._error_lock:
                    if not self._embedding_error_shown:
                        logger.warning("Ollama 服務未啟動，請執行 'ollama serve' 或切換至雲端 embedding")
                        self._embedding_error_shown = True
            else:
                logger.warning("Embedding 錯誤: %s", error_msg[:80])
            return []

def get_llm_factory(config: dict, full_config: dict | None = None) -> LLMProvider:
    """
    取得 LLM 提供者實例的工廠函式。

    Args:
        config: LLM 區塊的設定字典（通常是 config['llm']）
        full_config: 完整的設定字典（可選）。若提供則從中讀取 provider
                     預設值；若未提供則不做 provider 合併，避免每次
                     都重新讀取設定檔。
    """
    active_provider = config.get("provider", "ollama")

    # 若有提供完整設定，合併 provider 預設值
    if full_config is not None:
        provider_defaults = full_config.get("providers", {}).get(active_provider, {})
    else:
        provider_defaults = {}

    final_config = provider_defaults.copy()
    final_config.update(config)

    # 若 config 中的 api_key 為空，嘗試使用 provider 預設值
    if not config.get("api_key") and provider_defaults.get("api_key"):
        final_config["api_key"] = provider_defaults["api_key"]
    if not config.get("model") or config.get("model") == "llama3.1:8b":
        if provider_defaults.get("model"):
            final_config["model"] = provider_defaults["model"]

    if active_provider == "mock":
        return MockLLMProvider(final_config)

    return LiteLLMProvider(final_config)
