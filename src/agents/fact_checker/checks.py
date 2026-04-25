from __future__ import annotations

import json
import logging
import math
from typing import Any

from src.agents.review_parser import parse_review_response
from src.core.llm import LLMError
from src.core.review_models import ReviewResult
from src.document.citation_metadata import extract_reference_entries

logger = logging.getLogger(__name__)


def build_repo_owned_issues(
    *,
    draft: str,
    citation_checks: list[Any],
    verification_degraded: bool,
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    reference_entries = extract_reference_entries(draft)
    referenced_titles = [str(entry.get("title", "")) for entry in reference_entries]
    actionable_checks = [
        chk
        for chk in citation_checks
        if is_actionable_citation(
            getattr(chk.citation, "law_name", ""),
            getattr(chk.citation, "article_no", None),
        )
    ]

    if verification_degraded and (actionable_checks or (not citation_checks and draft_has_legal_claims(draft))):
        issues.append(
            {
                "severity": "error",
                "location": "即時法規驗證",
                "description": "即時法規驗證服務失敗，當前無法確認法規引用真實性，不能視為 citation-clean。",
                "suggestion": "修復 realtime_lookup 或稍後重跑審查；在驗證恢復前，勿將此草稿視為已完成法規查核。",
            }
        )
        return issues

    for chk in actionable_checks:
        citation_text = getattr(chk.citation, "original_text", "") or getattr(chk.citation, "law_name", "法規引用")
        law_name = getattr(chk.citation, "law_name", "")
        article_no = getattr(chk.citation, "article_no", None)
        article_exists = getattr(chk, "article_exists", None)
        if not is_actionable_citation(law_name, article_no):
            continue

        if not chk.law_exists:
            issues.append(
                {
                    "severity": "error",
                    "location": getattr(chk.citation, "location", "法規引用"),
                    "description": f"法規引用不可驗證：{citation_text} 不存在於全國法規資料庫。",
                    "suggestion": f"刪除或改正「{citation_text}」；改用實際存在的法規名稱與條號。",
                }
            )
            continue

        if article_no and article_exists is False:
            issues.append(
                {
                    "severity": "error",
                    "location": getattr(chk.citation, "location", "法規引用"),
                    "description": f"法規引用不可驗證：{law_name} 第 {article_no} 條不存在或查無條文內容。",
                    "suggestion": f"將「{citation_text}」改為正確條號，或移除此無法驗證的條文引用。",
                }
            )
            continue

        if law_name and not has_repo_evidence(law_name, referenced_titles):
            issues.append(
                {
                    "severity": "warning",
                    "location": getattr(chk.citation, "location", "法規引用"),
                    "description": f"未驗證引用：{law_name} 未在參考來源段落找到對應 repo 證據。",
                    "suggestion": f"為「{law_name}」補上 [^i] 來源定義，並在參考來源段落加入 URL 或 Hash。",
                }
            )

    return issues


def draft_has_legal_claims(draft: str) -> bool:
    return "第" in draft and any(
        suffix in draft for suffix in ("法", "條例", "辦法", "規則", "細則", "規程", "標準", "準則", "綱要", "通則")
    )


def has_repo_evidence(law_name: str, referenced_titles: list[str]) -> bool:
    normalized_law = law_name.replace(" ", "")
    for title in referenced_titles:
        normalized_title = title.replace(" ", "")
        if not normalized_title:
            continue
        if normalized_law in normalized_title or normalized_title in normalized_law:
            return True
    return False


def is_verification_degraded(law_verifier: Any, citation_checks: list[Any]) -> bool:
    if not law_verifier or not citation_checks:
        return False
    cache = getattr(law_verifier.__class__, "_cache", None)
    if cache is None:
        cache = getattr(law_verifier, "_cache", None)
    cache_data = getattr(cache, "data", None)
    return isinstance(cache_data, dict) and not cache_data


def is_actionable_citation(law_name: str, article_no: str | None) -> bool:
    normalized = law_name.replace(" ", "")
    generic_names = {
        "相關法",
        "相關法規",
        "相關規定",
        "相關辦法",
        "相關條例",
        "相關規則",
    }
    if normalized in generic_names:
        return False
    if normalized.startswith("相關") and article_no is None:
        return False
    return bool(normalized)


def merge_repo_issues(
    *,
    llm_result: ReviewResult,
    repo_issues: list[dict[str, str]],
    agent_name: str,
    category: str,
) -> ReviewResult:
    merged = [
        *[
            {
                "severity": issue.severity,
                "location": issue.location,
                "description": issue.description,
                "suggestion": issue.suggestion,
            }
            for issue in llm_result.issues
        ],
        *repo_issues,
    ]
    seen = set()
    deduped = []
    for item in merged:
        key = (item["severity"], item["location"], item["description"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    issue_penalty = 0.0
    for item in deduped:
        issue_penalty += 0.2 if item["severity"] == "error" else 0.05 if item["severity"] == "warning" else 0.0

    merged_result = parse_review_response(
        response=json.dumps(
            {
                "issues": deduped,
                "score": min(llm_result.score, max(0.0, 1.0 - issue_penalty)),
                "confidence": llm_result.confidence,
            },
            ensure_ascii=False,
        ),
        agent_name=agent_name,
        category=category,
    )
    return ReviewResult(
        agent_name=merged_result.agent_name,
        issues=merged_result.issues,
        score=merged_result.score,
        confidence=llm_result.confidence,
    )


def semantic_similarity_check(
    *,
    llm: Any,
    checks: list[Any],
    draft: str,
) -> list[str]:
    """計算引用法規內容與公文語境的語義相似度。"""
    lines: list[str] = []
    for chk in checks:
        if not chk.law_exists or not chk.actual_content or not chk.citation.article_no:
            continue

        citation_text = chk.citation.original_text
        idx = draft.find(citation_text)
        if idx < 0:
            continue
        ctx_start = max(0, idx - 50)
        ctx_end = min(len(draft), idx + len(citation_text) + 50)
        draft_context = draft[ctx_start:ctx_end]

        try:
            emb_draft = llm.embed(draft_context)
            emb_law = llm.embed(chk.actual_content[:500])
            if not emb_draft or not emb_law:
                continue
            similarity = cosine_similarity(emb_draft, emb_law)
        except (LLMError, ValueError, RuntimeError, OSError) as exc:
            logger.warning("語義相似度計算失敗，跳過此引用：%s", exc)
            continue

        law_name = chk.citation.law_name
        art_no = chk.citation.article_no
        if similarity < 0.3:
            lines.append(
                f"❌ {law_name} 第 {art_no} 條 — 語義相似度極低（{similarity:.2f}），引用可能與公文內容無關"
            )
        elif similarity < 0.5:
            lines.append(
                f"⚠️ {law_name} 第 {art_no} 條 — 語義相似度偏低（{similarity:.2f}），請確認引用是否恰當"
            )
    return lines


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """計算兩個向量的餘弦相似度。"""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def cross_reference_doc_type(
    *,
    checks: list[Any],
    doc_type: str,
    reg_doc_mapping: dict[str, dict[str, Any]],
) -> list[str]:
    """交叉比對引用的法規是否適用於此公文類型。"""
    lines: list[str] = []
    for chk in checks:
        if not chk.law_exists:
            continue
        law_name = chk.citation.law_name
        mapping = reg_doc_mapping.get(law_name)
        if mapping is None:
            continue
        applicable = mapping.get("applicable_doc_types", [])
        not_applicable = mapping.get("not_applicable", [])
        if doc_type in not_applicable:
            lines.append(f"❌ {law_name} — 不適用於「{doc_type}」類型公文（明確排除）")
        elif applicable and doc_type not in applicable:
            lines.append(f"⚠️ {law_name} — 通常不用於「{doc_type}」類型公文，請確認引用是否恰當")
    return lines
