from __future__ import annotations

import re


REFERENCE_SECTION_HEADING = "### 參考來源 (AI 引用追蹤)"


class CitationFormatter:
    """Repo-owned seam for assembling canonical citation output."""

    @staticmethod
    def _normalize_title_for_context(draft: str, title: str) -> str:
        is_meeting_context = (
            ("會議" in draft or "開會" in draft)
            and any(keyword in draft for keyword in ("委員會", "會議通知", "開會", "出席"))
        )
        if is_meeting_context and not any(
            keyword in title for keyword in ("會議", "通知", "議程", "委員會")
        ):
            return "會議通知行政範本"
        return title

    @classmethod
    def build_reference_lines(
        cls,
        draft: str,
        sources_list: list[dict],
        *,
        preserve_all_sources: bool = False,
    ) -> list[str]:
        if not sources_list:
            return []

        used = {int(match) for match in re.findall(r"\[\^(\d+)\](?!:)", draft)}
        if preserve_all_sources or not used:
            used = {
                int(source["index"])
                for source in sources_list
                if isinstance(source.get("index"), int)
            }

        by_index = {
            int(source["index"]): source
            for source in sources_list
            if isinstance(source.get("index"), int)
        }

        lines: list[str] = []
        for idx in sorted(used):
            source = by_index.get(idx)
            if source is None:
                continue
            title = cls._normalize_title_for_context(draft, str(source.get("title", "")))
            lines.append(
                "[^{i}]: [Level {lvl}] {title}{url}{hash_value}".format(
                    i=source["index"],
                    lvl=source.get("source_level", "B"),
                    title=title,
                    url=f" | URL: {source['source_url']}" if source.get("source_url") else "",
                    hash_value=(
                        f" | Hash: {source['content_hash']}" if source.get("content_hash") else ""
                    ),
                )
            )
        return lines

    @classmethod
    def build_reference_block(
        cls,
        draft: str,
        sources_list: list[dict],
        *,
        preserve_all_sources: bool = False,
    ) -> str:
        lines = cls.build_reference_lines(
            draft,
            sources_list,
            preserve_all_sources=preserve_all_sources,
        )
        if not lines:
            return ""
        return REFERENCE_SECTION_HEADING + "\n" + "\n".join(lines)
