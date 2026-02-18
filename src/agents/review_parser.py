"""
審查結果 JSON 解析共用模組

統一處理各審查 Agent 從 LLM 回應中解析 JSON 的邏輯，
消除 StyleChecker、FactChecker、ConsistencyChecker 中的重複程式碼。
"""
import json
import logging
from typing import Optional

from src.core.review_models import ReviewIssue, ReviewResult
from src.core.constants import DEFAULT_REVIEW_SCORE

logger = logging.getLogger(__name__)


def _extract_json_object(text: str) -> Optional[str]:
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
    escape_next = False

    for i in range(start_idx, len(text)):
        char = text[i]

        if escape_next:
            escape_next = False
            continue

        if char == '\\' and in_string:
            escape_next = True
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == '{':
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

    Returns:
        ReviewResult 物件
    """
    if not response or not response.strip():
        return ReviewResult(
            agent_name=agent_name,
            issues=[],
            score=default_score,
        )

    try:
        # 使用平衡括號匹配取代貪婪正則，更能處理包含引號和換行的回應
        json_str = _extract_json_object(response)
        if not json_str:
            return ReviewResult(
                agent_name=agent_name,
                issues=[],
                score=default_score,
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
                issues.append(ReviewIssue(category=category, **sanitized_item))
            except Exception as item_exc:
                logger.debug(
                    "%s: 解析單一 issue 失敗: %s", agent_name, item_exc
                )
                continue

        return ReviewResult(
            agent_name=agent_name,
            issues=issues,
            score=data.get("score", default_score),
            confidence=data.get("confidence", 1.0),
        )
    except json.JSONDecodeError:
        logger.debug("%s: 無法解析 LLM 回應中的 JSON", agent_name)
        return ReviewResult(
            agent_name=agent_name,
            issues=[],
            score=default_score,
        )
    except Exception as exc:
        logger.debug("%s: 解析審查結果時發生例外: %s", agent_name, exc)
        return ReviewResult(
            agent_name=agent_name,
            issues=[],
            score=default_score,
        )


def format_audit_to_review_result(
    fmt_raw: dict,
    agent_name: str = "Format Auditor",
) -> ReviewResult:
    """
    將 FormatAuditor 的原始字典結果轉換為 ReviewResult。

    這段轉換邏輯原本在 editor.py 和 api_server.py 中各自重複實作，
    現統一由此函式處理。

    Args:
        fmt_raw: FormatAuditor.audit() 的回傳字典，包含 "errors" 和 "warnings"
        agent_name: Agent 名稱

    Returns:
        ReviewResult 物件
    """
    fmt_issues = []
    for err in fmt_raw.get("errors", []):
        fmt_issues.append(
            ReviewIssue(
                category="format",
                severity="error",
                risk_level="high",
                location="文件結構",
                description=err,
            )
        )
    for warn in fmt_raw.get("warnings", []):
        fmt_issues.append(
            ReviewIssue(
                category="format",
                severity="warning",
                risk_level="medium",
                location="文件結構",
                description=warn,
            )
        )

    return ReviewResult(
        agent_name=agent_name,
        issues=fmt_issues,
        score=1.0 if not fmt_issues else 0.5,
        confidence=1.0,
    )
