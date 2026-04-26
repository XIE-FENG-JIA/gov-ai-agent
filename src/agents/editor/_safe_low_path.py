"""Safe low-path helpers for EditorFlowMixin — targeted review execution.

Extracted from src/agents/editor/flow.py (T-FAT-WATCH-CUT-V6).
"""
from __future__ import annotations

from typing import Any

from src.core.constants import DEFAULT_FAILED_CONFIDENCE, DEFAULT_FAILED_SCORE
from src.core.review_models import ReviewResult


def execute_targeted_review(
    executor: Any,
    agent_factories: dict[str, Any],
    prev_results: list[ReviewResult],
    phase: str,
) -> tuple[list[ReviewResult], list[str]]:
    """Only re-run agents that had issues in *phase*; reuse other results.

    Parameters
    ----------
    executor:
        A ``concurrent.futures.Executor`` (or compatible) used to submit tasks.
    agent_factories:
        Mapping of agent name → zero-arg callable that returns a ``ReviewResult``.
        Only keys matching affected agents will be called.
    prev_results:
        Results from the previous review round.
    phase:
        Severity string (e.g. ``"error"``, ``"warning"``, ``"info"``).

    Returns
    -------
    tuple[list[ReviewResult], list[str]]
        ``(results, timed_out)`` — same contract as ``_execute_review``.
    """
    affected_agents = {
        result.agent_name
        for result in prev_results
        if any(issue.severity == phase for issue in result.issues)
    }
    if not affected_agents:
        return prev_results, []

    rerun_agents = {name: agent_factories[name] for name in affected_agents if name in agent_factories}
    preserved = [result for result in prev_results if result.agent_name not in rerun_agents]
    if not rerun_agents:
        return prev_results, []

    results: list[ReviewResult] = []
    future_to_agent = {executor.submit(task): name for name, task in rerun_agents.items()}
    for future, agent_name in future_to_agent.items():
        try:
            results.append(future.result())
        except (RuntimeError, OSError, ValueError):
            results.append(
                ReviewResult(
                    agent_name=agent_name,
                    issues=[],
                    score=DEFAULT_FAILED_SCORE,
                    confidence=DEFAULT_FAILED_CONFIDENCE,
                )
            )
    results.extend(preserved)
    return results, []
