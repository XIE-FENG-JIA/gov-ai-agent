"""
共用常數定義模組

集中管理專案中的所有魔法數字和共用常數，
避免散落在各模組中造成維護困難。
"""
import logging
import os
import platform
import re
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

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
CATEGORY_WEIGHTS: dict[str, float] = {
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
DEFAULT_FAILED_SCORE = 0.0            # Agent 執行失敗時的預設分數（排除計算）
DEFAULT_FAILED_CONFIDENCE = 0.0       # Agent 執行失敗時的預設信心度（排除計算）

# 並行執行設定
EDITOR_MAX_WORKERS = 4                # EditorInChief 並行審查執行緒數
API_MAX_WORKERS = 5                   # API Server 並行執行緒數

# 超時設定（秒）
PARALLEL_REVIEW_TIMEOUT = 150         # 並行審查 as_completed 逾時
LLM_GENERATION_TIMEOUT = 300          # LLM 生成呼叫逾時（CPU 推理需要較長時間）
LLM_CHECK_TIMEOUT = 60               # LLM 審查/檢查呼叫逾時
CONNECTIVITY_CHECK_TIMEOUT = 10       # 連線測試逾時
HTTP_DEFAULT_TIMEOUT = 60             # 一般 HTTP 請求預設逾時

# 迭代審查
DEFAULT_MAX_REVIEW_ROUNDS = 3         # EditorInChief 預設最大審查輪數（舊模式）
MAX_REVIEW_ROUNDS_LIMIT = 5          # 舊模式允許的最大審查輪數上限

# 分層收斂迭代常數
CONVERGENCE_SAFETY_LIMIT = 15         # 分層收斂模式的安全總輪數上限
CONVERGENCE_STALE_ROUNDS = 2          # 連續幾輪無改善就強制進入下一 Phase
CONVERGENCE_MAX_FIX_ATTEMPTS = 3      # 同一 issue 最大修正嘗試次數
CONVERGENCE_PHASES = ("error", "warning", "info")  # 分層修正順序

# ============================================================
# HTTP 請求體大小限制（DoS 防護）
# ============================================================

# 最大請求體大小（bytes）：Pydantic 驗證在 JSON 解析後才生效，
# 必須在中介層攔截超大 payload 以防記憶體耗盡型 DoS。
# 2 MB 足夠覆蓋 max_length=50000 的 draft（UTF-8 最多 ~200KB）加上合理 overhead。
MAX_REQUEST_BODY_SIZE = int(os.environ.get("MAX_REQUEST_BODY_SIZE", str(2 * 1024 * 1024)))

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

# 公文輸出字體大小（單位：pt）— 寬鬆模式（向後相容）
# 每級比《文書處理手冊》規範加大 4pt，提升螢幕可讀性。
FONT_SIZE_TITLE = 20          # 公文類型標題
FONT_SIZE_SECTION_LABEL = 16  # 段落標籤
FONT_SIZE_BODY = 14           # 本文內容
FONT_SIZE_META = 12           # 檔頭資訊
FONT_SIZE_LOG = 10            # QA 報告

# 公文輸出字體大小（單位：pt）— 嚴格模式（《文書處理手冊》規範）
STRICT_FONT_SIZE_TITLE = 16          # 公文類型標題
STRICT_FONT_SIZE_SECTION_LABEL = 14  # 段落標籤
STRICT_FONT_SIZE_BODY = 12           # 本文內容
STRICT_FONT_SIZE_META = 10           # 檔頭資訊

# 頁面邊距（單位：cm）— A4 標準
STRICT_PAGE_MARGIN = 2.54            # 上下左右均 2.54cm

# 頁面邊距（單位：cm）— 寬鬆模式
PAGE_MARGIN_TOP = 2.54
PAGE_MARGIN_BOTTOM = 2.54
PAGE_MARGIN_LEFT = 3.17       # 傳統裝訂側加寬
PAGE_MARGIN_RIGHT = 3.17

# 行距與段距（嚴格模式）
STRICT_LINE_SPACING = 1.5            # 1.5 倍行距
STRICT_SPACE_BEFORE_LINES = 0.5      # 段前 0.5 行
STRICT_SPACE_AFTER_LINES = 0         # 段後 0 行

# 首行縮排（單位：pt）
FIRST_LINE_INDENT = 24

# 字體名稱（Windows 預設，用於向後相容）
FONT_TITLE = "DFKai-SB"      # 標楷體（標題用）
FONT_BODY = "MingLiU"        # 細明體（內文用）
FONT_LOG = "Courier New"     # 等寬字體（日誌用）

# 跨平台字體 fallback 鏈
# 每個平台依序嘗試，第一個找到的字體即被採用；
# 若全部不可用則回退為 None（使用 Word 預設字體）。
_FONT_FALLBACK: dict[str, dict[str, list[str]]] = {
    "Windows": {
        "title": ["DFKai-SB", "MingLiU", "標楷體"],
        "body": ["MingLiU", "DFKai-SB", "新細明體"],
    },
    "Darwin": {  # macOS
        "title": ["PingFang TC", "Heiti TC", "STSong"],
        "body": ["PingFang TC", "Heiti TC", "STSong"],
    },
    "Linux": {
        "title": ["Noto Sans CJK TC", "WenQuanYi Micro Hei"],
        "body": ["Noto Sans CJK TC", "WenQuanYi Micro Hei"],
    },
}


def _find_available_font(candidates: list[str]) -> str | None:
    """從候選字體清單中回傳第一個存在於系統的字體名稱。

    僅檢查常見的系統字體目錄，若完全找不到則回傳第一個候選並記錄警告。
    """
    if not candidates:
        return None

    os_name = platform.system()
    font_dirs: list[Path] = []
    if os_name == "Windows":
        windir = os.environ.get("WINDIR", r"C:\Windows")
        font_dirs.append(Path(windir) / "Fonts")
    elif os_name == "Darwin":
        font_dirs.extend([
            Path("/Library/Fonts"),
            Path.home() / "Library" / "Fonts",
            Path("/System/Library/Fonts"),
        ])
    elif os_name == "Linux":
        font_dirs.extend([
            Path("/usr/share/fonts"),
            Path("/usr/local/share/fonts"),
            Path.home() / ".local" / "share" / "fonts",
        ])

    # 字體名稱 → 可能的檔名對應（不含副檔名）
    _NAME_TO_FILE: dict[str, list[str]] = {
        "DFKai-SB": ["kaiu"],
        "MingLiU": ["mingliu"],
        "標楷體": ["kaiu"],
        "新細明體": ["mingliu"],
        "PingFang TC": ["PingFang"],
        "Heiti TC": ["STHeiti Medium"],
        "STSong": ["STSong"],
        "Noto Sans CJK TC": ["NotoSansCJK-Regular", "NotoSansCJKtc-Regular"],
        "WenQuanYi Micro Hei": ["wqy-microhei"],
    }

    # 預先快取每個字體目錄的一層子目錄（避免 N×M 重複 iterdir）
    _subdir_cache: dict[Path, list[Path]] = {}

    for candidate in candidates:
        file_stems = _NAME_TO_FILE.get(candidate, [candidate])
        for font_dir in font_dirs:
            if not font_dir.is_dir():
                continue
            # 快取子目錄列表：每個 font_dir 只遍歷一次
            if font_dir not in _subdir_cache:
                try:
                    _subdir_cache[font_dir] = [
                        d for d in font_dir.iterdir() if d.is_dir()
                    ]
                except OSError:
                    _subdir_cache[font_dir] = []
            for stem in file_stems:
                for ext in (".ttf", ".ttc", ".otf"):
                    if (font_dir / f"{stem}{ext}").exists():
                        return candidate
                    # 也搜尋子目錄一層（Linux 常見結構）
                    for sub in _subdir_cache[font_dir]:
                        if (sub / f"{stem}{ext}").exists():
                            return candidate

    # 找不到任何字體檔案，回傳第一個候選並警告
    logger.warning(
        "字體 fallback: 候選 %s 均未在系統字體目錄中找到，"
        "使用第一個候選 '%s'。如公文輸出字體異常，請安裝中文字體。",
        candidates, candidates[0],
    )
    return candidates[0]


def get_platform_fonts() -> tuple[str | None, str | None]:
    """依據作業系統回傳 (標題字體, 內文字體)。

    依序嘗試 fallback 鏈中的字體名稱，驗證字體檔案是否存在，
    若當前平台無對應設定則回傳 (None, None)，
    交由 Word 使用預設字體。
    """
    os_name = platform.system()
    chain = _FONT_FALLBACK.get(os_name)
    if not chain:
        return (None, None)
    title_font = _find_available_font(chain["title"])
    body_font = _find_available_font(chain["body"])
    return (title_font, body_font)

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

# 專案根目錄與輸出目錄（基於 __file__ 解析，不依賴 CWD）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"


# ---------------------------------------------------------------------------
# LLM 錯誤回應偵測
# ---------------------------------------------------------------------------

# 編譯一次，多處複用
_LLM_ERROR_PATTERN = re.compile(
    r"^("
    r"[Ee]rror\s*:"                    # English: "Error: ..."
    r"|錯誤\s*[：:]"                   # 繁中: "錯誤：..."
    r"|错误\s*[：:]"                   # 簡中: "错误：..."
    r"|I'?m sorry"                     # English refusal
    r"|I apologize"                    # English refusal
    r"|很抱歉"                         # 中文拒絕
    r"|抱歉[，,]?\s*我"                # "抱歉，我無法..."
    r"|對不起"                         # 繁中拒絕
    r"|对不起"                         # 簡中拒絕
    r"|無法[生完]成"                   # "無法生成" / "無法完成"
    r"|无法[生完]成"                   # 簡中版
    r"|我無法"                         # "我無法處理..."
    r"|我无法"                         # 簡中版
    r")",
    re.IGNORECASE,
)


def is_llm_error_response(text: str | None) -> bool:
    """判斷 LLM 回應是否為錯誤訊息或拒絕回覆，而非有效內容。

    涵蓋英文 ``Error:`` 前綴、中文錯誤/拒絕回覆常見模式。
    用於替換散落在各 agent 的 ``startswith("Error")`` 檢查，
    統一偵測邏輯並支援中文 LLM。

    Args:
        text: LLM 回傳的文字（可為 None 或空字串）

    Returns:
        True 表示偵測到錯誤/拒絕模式，應使用 fallback。
    """
    if not text or not text.strip():
        return True
    return bool(_LLM_ERROR_PATTERN.search(text.strip()))


def escape_prompt_tag(content: str, tag_name: str) -> str:
    """
    中和內容中的 XML 開頭與結束標籤，防止 prompt injection 突破標籤邊界。

    當使用者輸入或外部資料嵌入 ``<tag_name>...</tag_name>`` 格式的 prompt 區段時，
    若內容包含 ``</tag_name>`` 或 ``<tag_name>``，可能導致 LLM 誤判標籤結構。
    此函式將兩者替換為安全的方括號形式。

    Args:
        content: 要嵌入 prompt 的內容
        tag_name: 包圍該內容的 XML 標籤名稱

    Returns:
        已中和標籤的安全內容
    """
    if not content:
        return ""
    # 使用正則替換：處理大小寫不敏感及帶屬性的標籤形式，
    # 防止 </tag>、</TAG>、<tag attr="val"> 等變體繞過
    result = re.sub(
        rf"</{re.escape(tag_name)}\s*>",
        f"[/{tag_name}]",
        content,
        flags=re.IGNORECASE,
    )
    result = re.sub(
        rf"<{re.escape(tag_name)}(\s[^>]*)?>",
        f"[{tag_name}]",
        result,
        flags=re.IGNORECASE,
    )
    return result


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
