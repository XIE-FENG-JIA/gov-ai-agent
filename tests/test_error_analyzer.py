"""
core/error_analyzer.py 單元測試 — 智能錯誤診斷模組。

測試範圍：
- ErrorAnalyzer.diagnose() 全部 6 種例外分支
- 回傳結構驗證（error_type, root_cause, suggestion, severity）
- 子類別繼承行為（確認用 `is` 而非 isinstance）
"""

import json
import pytest

from src.core.error_analyzer import ErrorAnalyzer


class TestDiagnoseConnectionErrors:
    """LLM 連線相關例外。"""

    @pytest.mark.parametrize(
        "exc_class",
        [ConnectionError, ConnectionRefusedError, ConnectionResetError],
    )
    def test_connection_errors(self, exc_class):
        result = ErrorAnalyzer.diagnose(exc_class("connection failed"))
        assert result["error_type"] == "LLM_CONNECTION"
        assert result["severity"] == "high"
        assert "LLM" in result["root_cause"]

    def test_timeout_error(self):
        result = ErrorAnalyzer.diagnose(TimeoutError("request timed out"))
        assert result["error_type"] == "LLM_CONNECTION"
        assert result["severity"] == "high"
        assert "逾時" in result["root_cause"]


class TestDiagnoseResponseErrors:
    """LLM 回應解析錯誤。"""

    def test_json_decode_error(self):
        exc = json.JSONDecodeError("Expecting value", "doc", 0)
        result = ErrorAnalyzer.diagnose(exc)
        assert result["error_type"] == "LLM_RESPONSE"
        assert result["severity"] == "medium"
        assert "JSON" in result["root_cause"]


class TestDiagnoseConfigErrors:
    """設定檔缺失。"""

    def test_file_not_found(self):
        result = ErrorAnalyzer.diagnose(FileNotFoundError("config.yaml"))
        assert result["error_type"] == "CONFIG_MISSING"
        assert result["severity"] == "high"
        assert "設定檔" in result["root_cause"]


class TestDiagnoseKBErrors:
    """知識庫相關 ValueError。"""

    def test_knowledge_value_error(self):
        result = ErrorAnalyzer.diagnose(ValueError("knowledge base not found"))
        assert result["error_type"] == "KB_ERROR"
        assert result["severity"] == "medium"
        assert "知識庫" in result["root_cause"]

    def test_non_knowledge_value_error_falls_through(self):
        """不含 'knowledge' 的 ValueError 應走 UNKNOWN 路徑。"""
        result = ErrorAnalyzer.diagnose(ValueError("invalid input"))
        assert result["error_type"] == "UNKNOWN"


class TestDiagnoseUnknown:
    """未匹配的例外走 UNKNOWN 路徑。"""

    def test_runtime_error(self):
        result = ErrorAnalyzer.diagnose(RuntimeError("something went wrong"))
        assert result["error_type"] == "UNKNOWN"
        assert result["severity"] == "low"
        assert "RuntimeError" in result["root_cause"]

    def test_key_error(self):
        result = ErrorAnalyzer.diagnose(KeyError("missing_key"))
        assert result["error_type"] == "UNKNOWN"
        assert "KeyError" in result["root_cause"]

    def test_type_error(self):
        result = ErrorAnalyzer.diagnose(TypeError("bad type"))
        assert result["error_type"] == "UNKNOWN"


class TestDiagnoseReturnStructure:
    """所有回傳都有完整的 4 個 key。"""

    REQUIRED_KEYS = {"error_type", "root_cause", "suggestion", "severity"}

    @pytest.mark.parametrize(
        "exc",
        [
            ConnectionError("x"),
            TimeoutError("x"),
            json.JSONDecodeError("x", "d", 0),
            FileNotFoundError("x"),
            ValueError("knowledge issue"),
            RuntimeError("x"),
        ],
    )
    def test_all_keys_present(self, exc):
        result = ErrorAnalyzer.diagnose(exc)
        assert set(result.keys()) == self.REQUIRED_KEYS

    @pytest.mark.parametrize(
        "exc",
        [
            ConnectionError("x"),
            TimeoutError("x"),
            json.JSONDecodeError("x", "d", 0),
            FileNotFoundError("x"),
            ValueError("knowledge issue"),
            RuntimeError("x"),
        ],
    )
    def test_severity_valid_values(self, exc):
        result = ErrorAnalyzer.diagnose(exc)
        assert result["severity"] in ("high", "medium", "low")


class TestDiagnoseEdgeCases:
    """邊界情況。"""

    def test_empty_message(self):
        """空訊息的例外不應 crash。"""
        result = ErrorAnalyzer.diagnose(ConnectionError(""))
        assert result["error_type"] == "LLM_CONNECTION"

    def test_none_str_message(self):
        """str(exception) 可能產生 None-like 字串。"""
        result = ErrorAnalyzer.diagnose(ValueError("None"))
        assert result["error_type"] == "UNKNOWN"

    def test_knowledge_case_insensitive(self):
        """'knowledge' 比對使用 .lower()，大寫也應匹配。"""
        result = ErrorAnalyzer.diagnose(ValueError("Knowledge Base Error"))
        assert result["error_type"] == "KB_ERROR"

    def test_connection_subclass_not_matched(self):
        """diagnose 使用 `is` 精確比對，自訂子類別不會匹配 ConnectionError。"""

        class CustomConnectionError(ConnectionError):
            pass

        result = ErrorAnalyzer.diagnose(CustomConnectionError("custom"))
        # `type(exc) in (ConnectionError, ...)` 用 `in` 不用 isinstance
        # 所以自訂子類別不匹配 → 走 UNKNOWN
        assert result["error_type"] == "UNKNOWN"
