"""Parallel review helpers for agent routes."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from src.api.helpers import ENDPOINT_TIMEOUT, review_result_to_dict
from src.api.models import ParallelReviewRequest, ParallelReviewResponse, SingleAgentReviewResponse
from src.core.constants import DEFAULT_FAILED_CONFIDENCE, DEFAULT_FAILED_SCORE, assess_risk_level
from src.core.review_models import ReviewResult
from src.core.scoring import calculate_risk_scores, calculate_weighted_scores

logger = logging.getLogger(__name__)


def run_format_audit(
    draft: str,
    doc_type: str,
    llm: Any,
    kb: Any,
    format_auditor_cls: type,
    formatter: Any,
) -> ReviewResult:
    """Run the format auditor and normalize the result."""
    auditor = format_auditor_cls(llm, kb)
    return formatter(auditor.audit(draft, doc_type))


async def run_parallel_review(
    request: ParallelReviewRequest,
    *,
    llm: Any,
    kb: Any,
    executor: Any,
    format_auditor_cls: type,
    style_checker_cls: type,
    fact_checker_cls: type,
    consistency_checker_cls: type,
    compliance_checker_cls: type,
    formatter: Any,
) -> ParallelReviewResponse:
    """Execute all requested review agents and aggregate the outcome."""
    results: dict[str, SingleAgentReviewResponse] = {}
    agent_map = {
        "format": lambda: run_format_audit(
            request.draft,
            request.doc_type,
            llm,
            kb,
            format_auditor_cls,
            formatter,
        ),
        "style": lambda: style_checker_cls(llm).check(request.draft),
        "fact": lambda: fact_checker_cls(llm).check(request.draft, doc_type=request.doc_type),
        "consistency": lambda: consistency_checker_cls(llm).check(request.draft),
        "compliance": lambda: compliance_checker_cls(llm, kb).check(request.draft),
    }
    agent_display_names: dict[str, str] = {
        "format": "Format Auditor",
        "style": "Style Checker",
        "fact": "Fact Checker",
        "consistency": "Consistency Checker",
        "compliance": "Compliance Checker",
    }

    loop = asyncio.get_running_loop()
    tasks: list[asyncio.Future] = []
    agent_names: list[str] = []
    for agent_name in request.agents:
        if agent_name in agent_map:
            agent_names.append(agent_name)
            tasks.append(loop.run_in_executor(executor, agent_map[agent_name]))

    review_results = await asyncio.wait_for(
        asyncio.gather(*tasks, return_exceptions=True),
        timeout=ENDPOINT_TIMEOUT,
    )

    successful_results: list[ReviewResult] = []
    any_agent_failed = False
    for i, result in enumerate(review_results):
        agent_name = agent_names[i]
        if isinstance(result, Exception):
            any_agent_failed = True
            logger.warning("Agent %s 執行失敗: %s", agent_name, result)
            display_name = agent_display_names.get(agent_name, agent_name)
            results[agent_name] = SingleAgentReviewResponse(
                agent_name=display_name,
                score=DEFAULT_FAILED_SCORE,
                confidence=DEFAULT_FAILED_CONFIDENCE,
                issues=[
                    {
                        "category": agent_name,
                        "severity": "error",
                        "risk_level": "high",
                        "location": "Agent 執行",
                        "description": f"{display_name} 執行失敗，請稍後再試。",
                        "suggestion": None,
                    }
                ],
                has_errors=True,
            )
            continue

        results[agent_name] = review_result_to_dict(result)
        successful_results.append(result)

    weighted_score, total_weight = calculate_weighted_scores(successful_results)
    weighted_error_score, weighted_warning_score = calculate_risk_scores(successful_results)
    avg_score = weighted_score / total_weight if total_weight > 0 else 0.0
    if total_weight == 0.0:
        risk = "Critical"
    else:
        risk = assess_risk_level(weighted_error_score, weighted_warning_score, avg_score)
        if any_agent_failed and risk in ("Safe", "Low", "Moderate"):
            risk = "High"

    return ParallelReviewResponse(
        success=True,
        results=results,
        aggregated_score=round(avg_score, 3),
        risk_summary=risk,
    )
