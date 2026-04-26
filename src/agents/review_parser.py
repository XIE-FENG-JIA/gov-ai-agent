"""
審查結果 JSON 解析共用模組

統一處理各審查 Agent 從 LLM 回應中解析 JSON 的邏輯，
消除 StyleChecker、FactChecker、ConsistencyChecker 中的重複程式碼。
"""
import json
import logging
import math

from src.core.review_models import ReviewIssue, ReviewResult
from src.core.constants import DEFAULT_REVIEW_SCORE, is_llm_error_response
from src.agents._scoring import format_audit_to_review_result  # noqa: F401 — re-exported for callers

logger = logging.getLogger(__name__)


def _sanitize_json_string(text: str | None) -> str:
    """
    清理 LLM 回應中可能導致 JSON 解析失敗的不可見 Unicode 字元。

    這些字元若出現在 JSON 鍵名或值中，可能導致欄位名稱不匹配
    （例如 ``"doc\\u200c_type"`` 無法匹配 ``"doc_type"``）。
    """
    if not text:
        return ""
    for ch in [
        '\ufeff',   # BOM (Byte Order Mark)
        '\u200b',   # ZWSP (Zero Width Space)
        '\u200c',   # ZWNJ (Zero Width Non-Joiner)
        '\u200d',   # ZWJ (Zero Width Joiner)
        '\u200e',   # LRM (Left-to-Right Mark)
        '\u200f',   # RLM (Right-to-Left Mark)
        '\u00ad',   # Soft Hyphen
        '\u2060',   # Word Joiner
    ]:
        text = text.replace(ch, '')
    return text


def _extract_json_object(text: str) -> str | None:
    """
    從文字中提取第一個平衡的 JSON 物件。

    使用括號計數法（而非貪婪正則 `\\{.*\\}`），
    能更可靠地處理 LLM 回應中包含的引號、換行、Unicode 等特殊字元。

    Args:
        text: 原始文字

    Returns:
        提取到的 JSON 字串，若找不到則回傳 None
    """
    if not text:
        return None

    start_idx = text.find('{')
    if start_idx == -1:
        return None

    depth = 0
    in_string = False
    backslash_count = 0

    for i in range(start_idx, len(text)):
        char = text[i]

        if in_string:
            if char == '\\':
                backslash_count += 1
                continue
            elif char == '"':
                # 偶數個反斜線 → 引號未被轉義 → 字串結束
                if backslash_count % 2 == 0:
                    in_string = False
                backslash_count = 0
                continue
            else:
                backslash_count = 0
                continue

        # 非字串狀態
        if char == '"':
            in_string = True
            backslash_count = 0
        elif char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                return text[start_idx:i + 1]

    return None


def parse_review_response(
    response: str,
    agent_name: str,
    category: str,
    default_score: float = DEFAULT_REVIEW_SCORE,
    default_confidence: float = 1.0,
    derive_risk_from_severity: bool = False,
) -> ReviewResult:
    """
    從 LLM 回應中解析審查結果 JSON。

    統一處理所有審查 Agent 的 JSON 解析邏輯，包含：
    - 空回應處理
    - JSON 提取（正規表達式）
    - 錯誤容錯（回傳預設結果）

    Args:
        response: LLM 的原始回應文字
        agent_name: Agent 名稱（用於結果標識）
        category: 問題類別（如 "style", "fact", "consistency"）
        default_score: 解析失敗時的預設分數
        default_confidence: 解析失敗時的預設信心度
        derive_risk_from_severity: 若為 True，從 severity 推導 risk_level
            （error→high, warning→medium, info→low），而非使用 LLM 回傳的值

    Returns:
        ReviewResult 物件
    """
    if not response or not response.strip():
        return ReviewResult(
            agent_name=agent_name,
            issues=[],
            score=default_score,
            confidence=default_confidence,
        )

    # 過濾 LLM 回傳的錯誤訊息（如連線失敗），避免被當成審查通過
    if is_llm_error_response(response):
        logger.warning("%s: LLM 回傳錯誤訊息: %s", agent_name, response[:80])
        return ReviewResult(
            agent_name=agent_name,
            issues=[],
            score=0.0,
            confidence=0.0,
        )

    try:
        # 清理 BOM / 零寬字元，避免欄位名稱不匹配導致 issues 靜默遺失
        response = _sanitize_json_string(response)

        # 使用平衡括號匹配取代貪婪正則，更能處理包含引號和換行的回應
        json_str = _extract_json_object(response)
        if not json_str:
            return ReviewResult(
                agent_name=agent_name,
                issues=[],
                score=default_score,
                confidence=default_confidence,
            )

        data = json.loads(json_str)

        # 安全處理 issues 欄位：確保它是列表
        raw_issues = data.get("issues", [])
        if not isinstance(raw_issues, list):
            logger.debug("%s: issues 欄位不是列表，忽略", agent_name)
            raw_issues = []

        issues = []
        for item in raw_issues:
            if not isinstance(item, dict):
                continue
            try:
                # 確保必要欄位存在且有合理預設值
                sanitized_item = {
                    "severity": item.get("severity", "info"),
                    "location": item.get("location", "未知"),
                    "description": item.get("description", "（無描述）"),
                    "suggestion": item.get("suggestion"),
                }
                # 驗證 severity 值
                if sanitized_item["severity"] not in ("error", "warning", "info"):
                    sanitized_item["severity"] = "info"
                # 決定 risk_level：從 severity 推導或使用 LLM 回傳值
                if derive_risk_from_severity:
                    sev = sanitized_item["severity"]
                    raw_risk = (
                        "high" if sev == "error"
                        else "medium" if sev == "warning"
                        else "low"
                    )
                else:
                    raw_risk = item.get("risk_level", "low")
                    if raw_risk not in ("high", "medium", "low"):
                        raw_risk = "low"
                sanitized_item["risk_level"] = raw_risk
                issues.append(ReviewIssue(category=category, **sanitized_item))
            except (KeyError, TypeError, ValueError) as item_exc:
                logger.debug(
                    "%s: 解析單一 issue 失敗: %s", agent_name, item_exc
                )
                continue

        # 鉗位分數和信心度到 [0, 1] 範圍，避免 LLM 回傳超出範圍的值
        # 導致 Pydantic 驗證失敗而丟失整個審查結果
        raw_score = data.get("score", default_score)
        raw_confidence = data.get("confidence", default_confidence)
        try:
            clamped_score = float(raw_score)
            # NaN / Infinity 不是有效分數，回退為預設值
            if math.isnan(clamped_score) or math.isinf(clamped_score):
                logger.debug("%s: score 為 NaN 或 Infinity，使用預設值", agent_name)
                clamped_score = default_score
            else:
                clamped_score = max(0.0, min(1.0, clamped_score))
        except (ValueError, TypeError):
            logger.debug("%s: 無法將 score 轉為浮點數: %s", agent_name, raw_score)
            clamped_score = default_score
        try:
            clamped_confidence = float(raw_confidence)
            if math.isnan(clamped_confidence) or math.isinf(clamped_confidence):
                logger.debug("%s: confidence 為 NaN 或 Infinity，使用預設值", agent_name)
                clamped_confidence = default_confidence
            else:
                clamped_confidence = max(0.0, min(1.0, clamped_confidence))
        except (ValueError, TypeError):
            logger.debug("%s: 無法將 confidence 轉為浮點數: %s", agent_name, raw_confidence)
            clamped_confidence = default_confidence

        return ReviewResult(
            agent_name=agent_name,
            issues=issues,
            score=clamped_score,
            confidence=clamped_confidence,
        )
    except json.JSONDecodeError:
        logger.warning("%s: 無法解析 LLM 回應中的 JSON（回應格式可能退化）", agent_name)
        return ReviewResult(
            agent_name=agent_name,
            issues=[],
            score=default_score,
            confidence=default_confidence,
        )
    except (AttributeError, KeyError, TypeError, ValueError, RuntimeError, OverflowError, ArithmeticError) as exc:
        return ReviewResult(
            agent_name=agent_name,
            issues=[],
            score=default_score,
            confidence=default_confidence,
        )
