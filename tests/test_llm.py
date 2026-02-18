"""
src/core/llm.py 的單元測試
測試 LLM 提供者的建構、模型名稱格式化和工廠函數
"""
from unittest.mock import MagicMock, patch
from src.core.llm import MockLLMProvider, LiteLLMProvider, get_llm_factory


# ==================== MockLLMProvider ====================

class TestMockLLMProvider:
    """MockLLMProvider 的測試"""

    def test_generate_returns_mock_text(self):
        """測試 generate 回傳包含提示語的假文字"""
        provider = MockLLMProvider({"model": "test-model"})
        result = provider.generate("寫一份公文")
        assert "[MOCK]" in result
        assert "寫一份公文" in result

    def test_generate_with_long_prompt(self):
        """測試長提示語被截斷顯示"""
        provider = MockLLMProvider({})
        long_prompt = "A" * 100
        result = provider.generate(long_prompt)
        assert "[MOCK]" in result
        assert "..." in result

    def test_embed_returns_384_dimensions(self):
        """測試 embed 回傳 384 維向量"""
        provider = MockLLMProvider({})
        embedding = provider.embed("測試文字")
        assert len(embedding) == 384
        assert all(isinstance(x, float) for x in embedding)

    def test_embed_consistent_for_same_length(self):
        """測試相同長度的文字回傳相同的 embedding（固定 seed）"""
        provider = MockLLMProvider({})
        emb1 = provider.embed("ABC")
        emb2 = provider.embed("XYZ")  # 相同長度
        assert emb1 == emb2

    def test_embed_different_for_different_length(self):
        """測試不同長度的文字回傳不同的 embedding"""
        provider = MockLLMProvider({})
        emb1 = provider.embed("AB")
        emb2 = provider.embed("ABCDE")
        assert emb1 != emb2

    def test_default_model_name(self):
        """測試預設模型名稱"""
        provider = MockLLMProvider({})
        assert provider.model == "mock-model"

    def test_custom_model_name(self):
        """測試自訂模型名稱"""
        provider = MockLLMProvider({"model": "my-custom-model"})
        assert provider.model == "my-custom-model"


# ==================== LiteLLMProvider 建構測試 ====================

class TestLiteLLMProviderInit:
    """LiteLLMProvider 建構子的測試"""

    def test_ollama_model_name(self):
        """測試 Ollama 提供者的模型名稱格式"""
        config = {"provider": "ollama", "model": "mistral"}
        provider = LiteLLMProvider(config)
        assert provider.model_name == "ollama/mistral"

    def test_gemini_model_name_without_prefix(self):
        """測試 Gemini 提供者自動加前綴"""
        config = {"provider": "gemini", "model": "gemini-1.5-flash", "api_key": "test-key"}
        provider = LiteLLMProvider(config)
        assert provider.model_name == "gemini/gemini-1.5-flash"

    def test_gemini_model_name_with_prefix(self):
        """測試 Gemini 提供者已有前綴不重複加"""
        config = {"provider": "gemini", "model": "gemini/gemini-1.5-pro", "api_key": "test-key"}
        provider = LiteLLMProvider(config)
        assert provider.model_name == "gemini/gemini-1.5-pro"

    def test_openrouter_model_name_without_prefix(self):
        """測試 OpenRouter 提供者自動加前綴"""
        config = {"provider": "openrouter", "model": "meta-llama/llama-3.1-8b-instruct:free", "api_key": "key"}
        provider = LiteLLMProvider(config)
        assert provider.model_name == "openrouter/meta-llama/llama-3.1-8b-instruct:free"

    def test_openrouter_model_name_with_prefix(self):
        """測試 OpenRouter 提供者已有前綴不重複加"""
        config = {"provider": "openrouter", "model": "openrouter/some-model", "api_key": "key"}
        provider = LiteLLMProvider(config)
        assert provider.model_name == "openrouter/some-model"

    def test_unknown_provider_passthrough(self):
        """測試未知提供者直接使用模型名稱"""
        config = {"provider": "custom", "model": "my-model"}
        provider = LiteLLMProvider(config)
        assert provider.model_name == "my-model"

    def test_default_values(self):
        """測試所有預設值"""
        provider = LiteLLMProvider({})
        assert provider.provider == "ollama"
        assert provider.model == "mistral"
        assert provider.api_key is None
        assert provider.base_url is None

    def test_embedding_config(self):
        """測試 embedding 相關配置"""
        config = {
            "embedding_provider": "gemini",
            "embedding_model": "text-embedding-004",
            "embedding_base_url": "https://custom.url"
        }
        provider = LiteLLMProvider(config)
        assert provider.emb_provider == "gemini"
        assert provider.emb_model == "text-embedding-004"
        assert provider.emb_base_url == "https://custom.url"


# ==================== LiteLLMProvider generate / embed ====================

class TestLiteLLMProviderMethods:
    """LiteLLMProvider 方法的測試（使用 mock）"""

    @patch("src.core.llm.litellm")
    def test_generate_success(self, mock_litellm):
        """測試 generate 成功時回傳正確內容"""
        # 設定 mock 回應
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "生成的公文內容"
        mock_litellm.completion.return_value = mock_response

        provider = LiteLLMProvider({"provider": "ollama", "model": "mistral"})
        result = provider.generate("寫一份公文")

        assert result == "生成的公文內容"
        mock_litellm.completion.assert_called_once()

    @patch("src.core.llm.litellm")
    def test_generate_failure_returns_error(self, mock_litellm):
        """測試 generate 失敗時回傳錯誤訊息"""
        mock_litellm.completion.side_effect = Exception("Connection refused")

        provider = LiteLLMProvider({"provider": "ollama", "model": "mistral"})
        result = provider.generate("寫一份公文")

        assert "Error" in result
        assert "Connection refused" in result

    @patch("src.core.llm.litellm")
    def test_generate_null_content(self, mock_litellm):
        """測試 generate 回傳 None 時回傳空字串"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None
        mock_litellm.completion.return_value = mock_response

        provider = LiteLLMProvider({"provider": "ollama", "model": "mistral"})
        result = provider.generate("測試")

        assert result == ""

    @patch("src.core.llm.litellm")
    def test_embed_success(self, mock_litellm):
        """測試 embed 成功時回傳正確向量"""
        mock_response = MagicMock()
        mock_response.data = [{"embedding": [0.1, 0.2, 0.3]}]
        mock_litellm.embedding.return_value = mock_response

        provider = LiteLLMProvider({"provider": "ollama", "model": "mistral"})
        result = provider.embed("測試文字")

        assert result == [0.1, 0.2, 0.3]

    @patch("src.core.llm.litellm")
    def test_embed_connection_error_returns_empty(self, mock_litellm):
        """測試 embed 連線失敗時回傳空列表"""
        mock_litellm.embedding.side_effect = Exception("ConnectionError: 10061")

        # 重設錯誤顯示旗標
        LiteLLMProvider._embedding_error_shown = False

        provider = LiteLLMProvider({"provider": "ollama", "model": "mistral"})
        result = provider.embed("測試")

        assert result == []

    @patch("src.core.llm.litellm")
    def test_embed_other_error_returns_empty(self, mock_litellm):
        """測試 embed 其他錯誤時回傳空列表"""
        mock_litellm.embedding.side_effect = Exception("Unknown error")

        provider = LiteLLMProvider({"provider": "ollama", "model": "mistral"})
        result = provider.embed("測試")

        assert result == []

    @patch("src.core.llm.litellm")
    def test_embed_ollama_model_name(self, mock_litellm):
        """測試 Ollama embedding 模型名稱格式"""
        mock_response = MagicMock()
        mock_response.data = [{"embedding": [0.1]}]
        mock_litellm.embedding.return_value = mock_response

        provider = LiteLLMProvider({
            "provider": "ollama",
            "embedding_provider": "ollama",
            "embedding_model": "llama3.1:8b"
        })
        provider.embed("test")

        call_kwargs = mock_litellm.embedding.call_args
        assert call_kwargs[1]["model"] == "ollama/llama3.1:8b"
        assert call_kwargs[1]["api_key"] is None  # Ollama 不需要 key

    @patch("src.core.llm.litellm")
    def test_embed_gemini_model_name(self, mock_litellm):
        """測試 Gemini embedding 模型名稱格式"""
        mock_response = MagicMock()
        mock_response.data = [{"embedding": [0.1]}]
        mock_litellm.embedding.return_value = mock_response

        provider = LiteLLMProvider({
            "provider": "gemini",
            "api_key": "test-key",
            "embedding_provider": "gemini"
        })
        provider.embed("test")

        call_kwargs = mock_litellm.embedding.call_args
        assert call_kwargs[1]["model"] == "gemini/text-embedding-004"


# ==================== get_llm_factory ====================

class TestGetLLMFactory:
    """get_llm_factory 工廠函數的測試（重構後使用 full_config 參數）"""

    def test_mock_provider(self):
        """測試建立 mock 提供者"""
        result = get_llm_factory({"provider": "mock"})
        assert isinstance(result, MockLLMProvider)

    def test_ollama_provider(self):
        """測試建立 Ollama 提供者"""
        result = get_llm_factory({"provider": "ollama", "model": "mistral"})
        assert isinstance(result, LiteLLMProvider)
        assert result.provider == "ollama"

    def test_gemini_provider(self):
        """測試建立 Gemini 提供者"""
        full_config = {
            "providers": {
                "gemini": {"model": "gemini-1.5-flash", "api_key": "test"}
            }
        }
        result = get_llm_factory({"provider": "gemini"}, full_config=full_config)
        assert isinstance(result, LiteLLMProvider)
        assert result.provider == "gemini"

    def test_provider_defaults_merge(self):
        """測試提供者預設值與傳入配置的合併"""
        full_config = {
            "providers": {
                "openrouter": {
                    "model": "default-model",
                    "api_key": "default-key",
                    "base_url": "https://openrouter.ai/api/v1"
                }
            }
        }
        result = get_llm_factory({"provider": "openrouter"}, full_config=full_config)
        assert isinstance(result, LiteLLMProvider)
        assert result.api_key == "default-key"

    def test_config_api_key_override(self):
        """測試傳入的 api_key 覆蓋預設值"""
        full_config = {
            "providers": {
                "openrouter": {
                    "model": "default-model",
                    "api_key": "default-key"
                }
            }
        }
        result = get_llm_factory(
            {"provider": "openrouter", "api_key": "custom-key"},
            full_config=full_config,
        )
        assert result.api_key == "custom-key"


# ==================== LiteLLMProvider embed 邊界測試 ====================

class TestLiteLLMEmbedEdgeCases:
    """LiteLLMProvider.embed 的邊界路徑測試"""

    @patch("src.core.llm.litellm")
    def test_embed_openrouter_model_name(self, mock_litellm):
        """測試 OpenRouter embedding 模型名稱格式"""
        mock_response = MagicMock()
        mock_response.data = [{"embedding": [0.5]}]
        mock_litellm.embedding.return_value = mock_response

        provider = LiteLLMProvider({
            "provider": "openrouter",
            "api_key": "test-key",
            "embedding_provider": "openrouter",
            "embedding_model": "text-embed-v1"
        })
        result = provider.embed("test")

        call_kwargs = mock_litellm.embedding.call_args
        assert call_kwargs[1]["model"] == "openrouter/text-embed-v1"
        assert call_kwargs[1]["api_key"] == "test-key"
        assert result == [0.5]

    @patch("src.core.llm.litellm")
    def test_embed_default_provider_model_name(self, mock_litellm):
        """測試預設（非 ollama/gemini/openrouter）embedding 提供者"""
        mock_response = MagicMock()
        mock_response.data = [{"embedding": [0.3]}]
        mock_litellm.embedding.return_value = mock_response

        provider = LiteLLMProvider({
            "provider": "anthropic",
            "api_key": "test-key",
            "embedding_provider": "anthropic",
            "embedding_model": "claude-embed-v1"
        })
        result = provider.embed("test")

        call_kwargs = mock_litellm.embedding.call_args
        # 非特殊提供者，直接使用原始模型名稱
        assert call_kwargs[1]["model"] == "claude-embed-v1"
        assert result == [0.3]

    @patch("src.core.llm.litellm")
    def test_embed_empty_response_data(self, mock_litellm):
        """測試 embedding 回應中 data 為空時回傳空列表"""
        mock_response = MagicMock()
        mock_response.data = []
        mock_litellm.embedding.return_value = mock_response

        provider = LiteLLMProvider({
            "provider": "ollama",
            "embedding_provider": "ollama",
            "embedding_model": "llama3"
        })
        result = provider.embed("test")
        assert result == []

    @patch("src.core.llm.litellm")
    def test_embed_none_response_data(self, mock_litellm):
        """測試 embedding 回應中 data 為 None 時回傳空列表"""
        mock_response = MagicMock()
        mock_response.data = None
        mock_litellm.embedding.return_value = mock_response

        provider = LiteLLMProvider({
            "provider": "ollama",
            "embedding_provider": "ollama",
            "embedding_model": "llama3"
        })
        result = provider.embed("test")
        assert result == []
