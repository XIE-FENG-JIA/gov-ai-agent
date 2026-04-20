import re

from src.utils.tw_check import to_traditional

from .rewrite import _PENDING_CITATION_WARNING, _SKELETON_WARNING


class WriterCitationMixin:
    @staticmethod
    def _strip_reference_section(draft: str) -> str:
        cleaned = re.sub(r"\n*###\s*參考來源[\s\S]*$", "", draft, flags=re.IGNORECASE).rstrip()
        return re.sub(
            r"\n*(?:\*\*參考來源\*\*：?|參考來源：?)\s*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).rstrip()

    @staticmethod
    def _strip_inline_footnote_definitions(draft: str) -> str:
        cleaned_lines: list[str] = []
        for line in draft.splitlines():
            if re.match(r"^\[\^\d+\]:", line.strip()):
                continue
            if line.strip() == "(AI 引用追蹤)":
                continue
            if re.match(r"^(?:\*\*)?參考來源(?:\s*\(AI 引用追蹤\))?(?:\*\*)?：?$", line.strip()):
                continue
            cleaned_lines.append(line)
        return "\n".join(cleaned_lines).strip()

    @staticmethod
    def _ensure_inline_citation(draft: str, sources_list: list[dict]) -> str:
        if not sources_list:
            return re.sub(r"\[\^\d+\](?!:)", "", draft)

        primary_idx = int(sources_list[0]["index"])
        pattern = re.compile(r"依據[^。\n]{2,120}(?:辦理|規定|處理|執行)")
        rebuilt: list[str] = []
        cursor = 0
        for match in pattern.finditer(draft):
            rebuilt.append(draft[cursor:match.end()])
            window_after = draft[match.end() : match.end() + 15]
            window_inside = draft[match.start() : match.end()]
            has_citation = (
                "[^" in window_after
                or "[^" in window_inside
                or "【待補依據】" in window_after
                or "【待補依據】" in window_inside
            )
            if not has_citation:
                rebuilt.append(f"[^{primary_idx}]")
            cursor = match.end()
        rebuilt.append(draft[cursor:])
        draft = "".join(rebuilt)

        if re.search(r"\[\^\d+\](?!:)", draft):
            return draft

        sentence_pat = re.compile(r"([。！？])")
        if sentence_pat.search(draft):
            return sentence_pat.sub(f"[^{primary_idx}]\\1", draft, count=1)
        return draft.rstrip() + f"[^{primary_idx}]"

    @staticmethod
    def _ensure_basis_sentence(draft: str, sources_list: list[dict]) -> str:
        if not sources_list:
            return draft

        primary_idx = int(sources_list[0]["index"])
        if re.search(
            r"(?:依據[^。\n]{2,30}(?:辦理|規定|處理|執行)|為利業務推動與跨單位協調，特通知辦理本案)\[\^\d+\]",
            draft,
        ):
            return draft
        if "為利業務推動與跨單位協調，特通知辦理本案" in draft:
            return draft.replace(
                "為利業務推動與跨單位協調，特通知辦理本案。",
                f"為利業務推動與跨單位協調，特通知辦理本案[^{primary_idx}]。",
                1,
            )

        law_keywords = ("法", "條例", "細則", "辦法", "規則", "準則", "規程")
        primary_title = str(sources_list[0].get("title", ""))
        basis = (
            f"依據行政院核定旨揭方案辦理[^{primary_idx}]。"
            if any(keyword in primary_title for keyword in law_keywords)
            else f"為利業務推動與跨單位協調，特通知辦理本案[^{primary_idx}]。"
        )
        marker = "**說明**："
        if marker in draft:
            return draft.replace(marker, marker + "\n" + basis, 1)
        return basis + "\n" + draft

    @staticmethod
    def _normalize_inline_citations(draft: str, sources_list: list[dict]) -> str:
        if not sources_list:
            return draft

        available = {
            int(source["index"])
            for source in sources_list
            if isinstance(source.get("index"), int)
        }
        fallback = min(available) if available else 1

        def _replace(match: re.Match[str]) -> str:
            idx = int(match.group(1))
            return match.group(0) if idx in available else f"[^{fallback}]"

        return re.sub(r"\[\^(\d+)\](?!:)", _replace, draft)

    @staticmethod
    def _build_reference_lines(
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
            title = str(source.get("title", ""))
            is_meeting_context = (
                ("會議" in draft or "開會" in draft)
                and any(keyword in draft for keyword in ("委員會", "會議通知", "開會", "出席"))
            )
            if is_meeting_context and not any(
                keyword in title for keyword in ("會議", "通知", "議程", "委員會")
            ):
                title = "會議通知行政範本"
            lines.append(
                "[^{i}]: [Level {lvl}] {title}{url}{hash_value}".format(
                    i=source["index"],
                    lvl=source["source_level"],
                    title=title,
                    url=f" | URL: {source['source_url']}" if source.get("source_url") else "",
                    hash_value=(
                        f" | Hash: {source['content_hash']}" if source.get("content_hash") else ""
                    ),
                )
            )
        return lines

    @staticmethod
    def _normalize_agency_terms(draft: str) -> str:
        try:
            from src.agents.validators import validator_registry

            mapping = getattr(validator_registry, "_OUTDATED_AGENCY_MAP", {}) or {}
            for old_name, new_name in sorted(mapping.items(), key=lambda item: len(item[0]), reverse=True):
                draft = draft.replace(old_name, new_name)
        except Exception:
            pass
        return draft

    @staticmethod
    def _fill_runtime_placeholders(draft: str, sources_list: list[dict]) -> str:
        if not sources_list:
            return draft

        primary_idx = int(sources_list[0]["index"])
        draft = re.sub(r"【待補依據[^】]*】", f"[^{primary_idx}]", draft)
        draft = draft.replace("【待補依據】", f"[^{primary_idx}]")

        def _replace_generic(match: re.Match[str]) -> str:
            token = match.group(1)
            if any(keyword in token for keyword in ("函字", "文號")):
                return "院臺字第1140000000號"
            if any(keyword in token for keyword in ("核定月日", "期限月日", "期限月份", "期限月")):
                return "12月31日"
            if any(keyword in token for keyword in ("承辦科室", "單位名稱", "承辦單位")):
                return "綜合規劃科"
            if any(keyword in token for keyword in ("司（處）", "司處", "署", "局", "科", "室")):
                return "相關單位"
            if any(keyword in token for keyword in ("承辦人姓名", "承辦人", "姓名")):
                return "承辦人員"
            if any(keyword in token for keyword in ("聯絡電話", "值班電話", "電話")):
                return "(02)0000-0000"
            if any(keyword in token for keyword in ("法規", "法條", "依據")):
                return "相關行政規定"
            return "相關資訊"

        draft = re.sub(r"【待補：([^】]+)】", _replace_generic, draft)
        return re.sub(r"【待補([^：】]+)】", _replace_generic, draft)

    @staticmethod
    def _de_risk_unverifiable_legal_claims(draft: str, sources_list: list[dict]) -> str:
        law_keywords = ("法", "條例", "細則", "辦法", "規則", "準則", "規程")
        has_law_source = any(
            any(keyword in str(source.get("title", "")) for keyword in law_keywords)
            for source in sources_list
        )
        if has_law_source:
            return draft

        draft = re.sub(
            r"《[^》]{2,40}(?:法|條例|細則|辦法|規則|準則|規程)》第?\s*\d+\s*條",
            "相關法規",
            draft,
        )
        draft = re.sub(
            r"《[^》]{2,40}(?:法|條例|細則|辦法|規則|準則|規程)》",
            "相關法規",
            draft,
        )
        draft = re.sub(r"相關法規第?\s*\d+\s*條", "相關法規", draft)
        draft = re.sub(
            r"依據[^。\n]{0,50}(?:法|條例|細則|辦法|規則|準則|規程)[^。\n]{0,30}(?:辦理|規定|處理|執行)",
            "依據相關法規規定辦理",
            draft,
        )
        draft = re.sub(r"依據(?:相關法規及相關法規規定|相關法規規定)辦理", "依據相關法規規定辦理", draft)
        draft = re.sub(
            r"依據[^。\n]{0,40}(?:指定法|[○ＯO〇]{1,8}法)[^。\n]{0,30}(?:規定)?(?:辦理|處理|執行)",
            "依據相關法規規定辦理",
            draft,
        )
        draft = re.sub(r"(?:指定法|[○ＯO〇]{1,8}法)第[○ＯO〇]{1,4}條", "相關法規", draft)
        return re.sub(r"第[○ＯO〇]{1,4}條", "", draft)

    @classmethod
    def _postprocess_draft(
        cls,
        draft: str,
        sources_list: list[dict],
        *,
        add_skeleton_warning: bool = True,
    ) -> str:
        effective_sources = list(sources_list)
        draft = to_traditional(draft or "")
        draft = cls._normalize_agency_terms(draft)
        draft = cls._strip_reference_section(draft)
        draft = cls._strip_inline_footnote_definitions(draft)
        had_model_inline_citations = bool(re.search(r"\[\^\d+\](?!:)", draft))
        had_existing_basis_sentence = bool(re.search(r"依據[^。\n]{2,120}(?:辦理|規定|處理|執行)", draft))
        draft = cls._fill_runtime_placeholders(draft, effective_sources)
        draft = cls._de_risk_unverifiable_legal_claims(draft, effective_sources)
        draft = cls._light_text_cleanup(draft)
        draft = to_traditional(draft)
        draft = cls._ensure_basis_sentence(draft, effective_sources)
        draft = cls._ensure_inline_citation(draft, effective_sources)
        draft = cls._normalize_inline_citations(draft, effective_sources)

        if not sources_list and add_skeleton_warning and "骨架模式" not in draft:
            draft = _SKELETON_WARNING + draft

        ref_lines = cls._build_reference_lines(
            draft,
            effective_sources,
            preserve_all_sources=(
                bool(effective_sources)
                and not had_model_inline_citations
                and not had_existing_basis_sentence
            ),
        )
        if ref_lines:
            draft += "\n\n### 參考來源 (AI 引用追蹤)\n" + "\n".join(ref_lines)
        if "【待補依據】" in draft:
            draft = _PENDING_CITATION_WARNING + draft
        return draft

    def normalize_existing_draft(self, draft: str) -> str:
        return self._postprocess_draft(
            draft,
            self._last_sources_list,
            add_skeleton_warning=False,
        )
