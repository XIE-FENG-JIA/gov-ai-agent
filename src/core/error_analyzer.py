"""智能錯誤診斷模組：分類例外並提供修復建議。"""

import json


class ErrorAnalyzer:
    """分析例外類型並回傳結構化診斷結果。"""

    @staticmethod
    def diagnose(exception: Exception) -> dict:
        """診斷例外並回傳 error_type、root_cause、suggestion、severity。"""
        exc_type = type(exception)
        msg = str(exception).lower()

        if exc_type in (ConnectionError, ConnectionRefusedError, ConnectionResetError):
            return {
                "error_type": "LLM_CONNECTION",
                "root_cause": "無法連線至 LLM 服務",
                "suggestion": "請確認 LLM 服務已啟動，並檢查網路連線與 API 設定",
                "severity": "high",
            }

        if exc_type is TimeoutError:
            return {
                "error_type": "LLM_CONNECTION",
                "root_cause": "LLM 服務回應逾時",
                "suggestion": "請確認 LLM 服務狀態，或嘗試增加逾時設定",
                "severity": "high",
            }

        if exc_type is json.JSONDecodeError:
            return {
                "error_type": "LLM_RESPONSE",
                "root_cause": "LLM 回傳的內容無法解析為 JSON",
                "suggestion": "請重試，若持續發生請檢查 LLM 模型設定",
                "severity": "medium",
            }

        if exc_type is FileNotFoundError:
            return {
                "error_type": "CONFIG_MISSING",
                "root_cause": "找不到必要的設定檔或資源檔案",
                "suggestion": "請執行 gov-ai config init 初始化設定",
                "severity": "high",
            }

        if exc_type is ValueError and "knowledge" in msg:
            return {
                "error_type": "KB_ERROR",
                "root_cause": "知識庫相關錯誤",
                "suggestion": "請執行 gov-ai kb ingest 匯入知識庫資料",
                "severity": "medium",
            }

        return {
            "error_type": "UNKNOWN",
            "root_cause": f"未預期的錯誤：{type(exception).__name__}",
            "suggestion": "請執行 gov-ai doctor 進行系統診斷",
            "severity": "low",
        }
