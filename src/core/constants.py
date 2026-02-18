"""
共用常數定義模組

集中管理專案中的所有魔法數字和共用常數，
避免散落在各模組中造成維護困難。
"""
from typing import Dict, Literal

# ============================================================
# LLM 呼叫相關常數
# ============================================================

# 各 Agent 的 LLM 溫度設定
LLM_TEMPERATURE_CREATIVE = 0.3      # 草稿撰寫（需要一定創意）
LLM_TEMPERATURE_PRECISE = 0.1       # 結構化分析（需要精確）
LLM_TEMPERATURE_BALANCED = 0.2      # 合規檢查（平衡精確與靈活）

# 知識庫查詢預設結果數
KB_DEFAULT_RESULTS = 3              # 預設查詢結果數
KB_WRITER_RESULTS = 2               # 撰寫 Agent 查詢範例數
KB_REGULATION_RESULTS = 1           # 法規查詢結果數
KB_POLICY_RESULTS = 3               # 政策查詢結果數

# ============================================================
# 審查系統常數
# ============================================================

# 各類別的加權係數：不同類別的問題嚴重性不同
CATEGORY_WEIGHTS: Dict[str, float] = {
    "format": 3.0,       # 格式錯誤影響最大（公文規範）
    "compliance": 2.5,   # 政策合規性次之（法規要求）
    "fact": 2.0,         # 事實正確性很重要（資訊準確）
    "consistency": 1.5,  # 一致性中等重要（邏輯連貫）
    "style": 1.0,        # 文風問題影響最小（可讀性）
}

# 風險等級判定閾值
RISK_CRITICAL_ERROR_THRESHOLD = 3.0   # 加權錯誤分數 >= 此值視為 Critical
RISK_HIGH_WARNING_THRESHOLD = 3.0     # 加權警告分數 >= 此值視為 High
RISK_MODERATE_SCORE_THRESHOLD = 0.9   # 平均分數 < 此值視為 Moderate
RISK_LOW_SCORE_THRESHOLD = 0.95       # 平均分數 < 此值視為 Low
WARNING_WEIGHT_FACTOR = 0.5           # 警告的權重因子（相對於錯誤）

# 審查 Agent 失敗時的預設分數
DEFAULT_REVIEW_SCORE = 0.8            # 無法解析結果時的預設分數
DEFAULT_COMPLIANCE_SCORE = 0.85       # 合規 Agent 的預設分數
DEFAULT_COMPLIANCE_CONFIDENCE = 0.5   # 合規 Agent 的預設信心度
DEFAULT_FAILED_SCORE = 0.8            # Agent 執行失敗時的預設分數
DEFAULT_FAILED_CONFIDENCE = 0.5       # Agent 執行失敗時的預設信心度

# 並行執行設定
EDITOR_MAX_WORKERS = 4                # EditorInChief 並行審查執行緒數
API_MAX_WORKERS = 5                   # API Server 並行執行緒數

# ============================================================
# 輸入限制常數（防止超出 LLM 上下文限制）
# ============================================================

# 草稿截斷上限（字元數），超過此長度的草稿將被截斷後再送入 LLM
MAX_DRAFT_LENGTH = 15000              # 約 7500 個中文字
# 使用者輸入截斷上限（字元數）
MAX_USER_INPUT_LENGTH = 5000          # 使用者需求描述上限
# 知識庫範例截斷上限（每筆範例）
MAX_EXAMPLE_LENGTH = 3000             # 每筆範例的最大字元數
# 回饋意見截斷上限
MAX_FEEDBACK_LENGTH = 5000            # 審查回饋彙整的最大字元數

# ============================================================
# 文件格式常數
# ============================================================

# 公文輸出字體大小（單位：pt）
# 注意：document_standards.json 設計規範定義為 16/14/12/10，
# 此處實際匯出值每級加大 4pt 以提升 DOCX 可讀性。
# 若需嚴格符合設計規範，請改為 16/14/12/10。
FONT_SIZE_TITLE = 20          # 公文類型標題（設計規範：16pt）
FONT_SIZE_SECTION_LABEL = 16  # 段落標籤（設計規範：14pt）
FONT_SIZE_BODY = 14           # 本文內容（設計規範：12pt）
FONT_SIZE_META = 12           # 檔頭資訊（設計規範：10pt）
FONT_SIZE_LOG = 10            # QA 報告

# 頁面邊距（單位：cm）
PAGE_MARGIN_TOP = 2.54
PAGE_MARGIN_BOTTOM = 2.54
PAGE_MARGIN_LEFT = 3.17       # 傳統裝訂側加寬
PAGE_MARGIN_RIGHT = 3.17

# 首行縮排（單位：pt）
FIRST_LINE_INDENT = 24

# 字體名稱
FONT_TITLE = "DFKai-SB"      # 標楷體（標題用）
FONT_BODY = "MingLiU"        # 細明體（內文用）
FONT_LOG = "Courier New"     # 等寬字體（日誌用）

# ============================================================
# 中文編號
# ============================================================

CHINESE_NUMBERS = [
    "一", "二", "三", "四", "五", "六", "七", "八", "九", "十",
    "十一", "十二", "十三", "十四", "十五", "十六", "十七", "十八", "十九", "二十",
]
MAX_CHINESE_NUMBER = len(CHINESE_NUMBERS)

# ============================================================
# API Server 常數
# ============================================================

SESSION_ID_LENGTH = 8                 # Session ID 截取長度
API_VERSION = "2.0.0"                 # API 版本號


def assess_risk_level(
    weighted_error_score: float,
    weighted_warning_score: float,
    avg_score: float,
) -> Literal["Critical", "High", "Moderate", "Low", "Safe"]:
    """
    根據加權錯誤/警告分數和平均分數判定風險等級。

    這是一個共用函式，供 EditorInChief 和 API Server 使用，
    確保風險判定邏輯的一致性。

    Args:
        weighted_error_score: 加權錯誤分數
        weighted_warning_score: 加權警告分數
        avg_score: 加權平均品質分數

    Returns:
        風險等級字串："Critical", "High", "Moderate", "Low", 或 "Safe"
    """
    if weighted_error_score >= RISK_CRITICAL_ERROR_THRESHOLD:
        return "Critical"
    elif weighted_error_score > 0 or weighted_warning_score >= RISK_HIGH_WARNING_THRESHOLD:
        return "High"
    elif weighted_warning_score > 0 or avg_score < RISK_MODERATE_SCORE_THRESHOLD:
        return "Moderate"
    elif avg_score < RISK_LOW_SCORE_THRESHOLD:
        return "Low"
    return "Safe"
