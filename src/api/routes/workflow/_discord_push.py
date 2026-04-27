"""Discord push helper — meeting endpoint 完成後 fire-and-forget 推送 5 reviewer 報告

從 qa_report dict 直接組 embed（不解 docx），比 watcher daemon 可靠：
- agent_results 含真實分數（避開 docx export silent fail）
- 即時觸發（不用等 60s tick）
- 不需要 docx 內含 QA Report 段
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# 6 reviewer 順序（對齊 src.graph.routing.review_selector）
_REVIEWER_ORDER = [
    "Format Auditor",
    "Style Checker",
    "Fact Checker",
    "Consistency Checker",
    "Compliance Checker",
    "Citation Checker",
]


def _color_for(score: float | None, risk: str | None) -> int:
    if risk and any(k in str(risk) for k in ("Critical", "嚴重", "critical")):
        return 0xEF4444
    if risk and any(k in str(risk) for k in ("High", "高", "high")):
        return 0xF59E0B
    if score is not None and score >= 0.85:
        return 0x10B981
    if score is not None and score >= 0.65:
        return 0xF59E0B
    return 0xEF4444


def _build_embed(
    session_id: str,
    user_input: str,
    output_path: str | None,
    qa_report: dict[str, Any] | None,
) -> dict[str, Any]:
    qa = qa_report or {}
    overall = qa.get("overall_score")
    risk = qa.get("risk_summary") or "?"
    rounds = qa.get("rounds_used") or 1

    # agent_results 可能是 list 或 dict
    agents = qa.get("agent_results") or []
    score_lines: list[str] = []
    issue_lines: list[str] = []

    if isinstance(agents, list):
        # 第 1 pass：先全收 score（reviewer 全要顯示）
        for i, r in enumerate(agents):
            if not isinstance(r, dict):
                continue
            name = r.get("agent_name") or r.get("agent") or r.get("name")
            if not name and i < len(_REVIEWER_ORDER):
                name = _REVIEWER_ORDER[i]
            score = r.get("score")
            if score is None:
                continue
            emoji = "🟢" if score >= 0.85 else "🟡" if score >= 0.65 else "🔴"
            score_lines.append(f"{emoji} **{name or '(unknown)'}** `{score:.2f}`")

        # 第 2 pass：再抽 Top 3 high/medium issues（跨 reviewer，不限制單一 reviewer）
        candidate_issues: list[tuple[int, str]] = []  # (priority, formatted line)
        for i, r in enumerate(agents):
            if not isinstance(r, dict):
                continue
            name = r.get("agent_name") or r.get("agent") or (_REVIEWER_ORDER[i] if i < len(_REVIEWER_ORDER) else "?")
            for issue in (r.get("issues") or []):
                if not isinstance(issue, dict):
                    continue
                risk = (issue.get("risk_level") or issue.get("severity") or "").lower()
                if risk not in ("high", "medium"):
                    continue
                priority = 0 if risk == "high" else 1  # high 排前
                msg = (issue.get("description") or issue.get("message") or "")[:140]
                loc = (issue.get("location") or issue.get("section") or name)[:50]
                emoji = "🔴" if risk == "high" else "🟡"
                candidate_issues.append((priority, f"{emoji} **{name} · {loc}**\n{msg}"))

        # 排序 + 取 Top 3
        candidate_issues.sort(key=lambda x: x[0])
        issue_lines = [x[1] for x in candidate_issues[:3]]
    elif isinstance(agents, dict):
        for name, r in agents.items():
            if isinstance(r, dict) and r.get("score") is not None:
                s = r["score"]
                emoji = "🟢" if s >= 0.85 else "🟡" if s >= 0.65 else "🔴"
                score_lines.append(f"{emoji} **{name}** `{s:.2f}`")

    # subject 從 user_input 取前 80 字
    subject = (user_input or "(無 user_input)").strip().splitlines()[0][:120]

    return {
        "embeds": [{
            "title": f"📄 公文 QA 報告 · {session_id}",
            "description": subject,
            "color": _color_for(overall, risk),
            "fields": [
                {"name": "加權總分", "value": f"`{overall:.2f}` / 1.00" if overall is not None else "?", "inline": True},
                {"name": "風險等級", "value": f"**{risk}**", "inline": True},
                {"name": "輪數", "value": f"`{rounds}`", "inline": True},
                {"name": "DOCX", "value": f"`{output_path or '(無)'}`", "inline": False},
                {"name": f"Reviewer 分數（{len(score_lines)}）", "value": "\n".join(score_lines) or "(無 agent_results)", "inline": False},
                {"name": "Top Issues", "value": "\n\n".join(issue_lines) or "(無 HIGH/MEDIUM 議題或結構不識別)", "inline": False},
            ],
            "footer": {"text": "gov-ai · meeting endpoint 直推"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }]
    }


async def _post_discord(payload: dict[str, Any]) -> None:
    token = os.environ.get("DISCORD_BOT_TOKEN", "")
    channel = os.environ.get("DISCORD_ALERT_CHANNEL_ID", "")
    if not token or not channel:
        logger.info("DISCORD_BOT_TOKEN/CHANNEL_ID 未設，跳過 review push")
        return
    url = f"https://discord.com/api/v10/channels/{channel}/messages"
    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "gov-ai-meeting/1.0",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, headers=headers, content=json.dumps(payload, ensure_ascii=False).encode("utf-8"))
            if resp.status_code in (200, 201):
                logger.info("review pushed to Discord (%d)", resp.status_code)
            else:
                logger.warning("review push failed: %d %s", resp.status_code, resp.text[:200])
    except (httpx.HTTPError, httpx.TimeoutException, OSError) as e:
        logger.warning("review push error: %s", e)


def schedule_push(
    session_id: str,
    user_input: str,
    output_path: str | None,
    qa_report: dict[str, Any] | None,
) -> None:
    """Fire-and-forget 推送（不阻塞 meeting response 返回）。

    若不在 event loop 內（rare），靜默跳過。
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            payload = _build_embed(session_id, user_input, output_path, qa_report)
            loop.create_task(_post_discord(payload))
    except (RuntimeError, AttributeError) as e:
        logger.debug("schedule_push skipped: %s", e)
