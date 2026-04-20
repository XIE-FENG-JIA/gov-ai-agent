import re
from datetime import date, timedelta


class WriterCleanupMixin:
    @classmethod
    def _light_text_cleanup(cls, draft: str) -> str:
        replacements = {
            "請  查照": "請查照",
            "，及，": "，並",
            "爱核定": "已核定",
            "愛配合": "爰配合",
            "經濟部環境部": "環境部",
            "本部環境部": "環境部",
            "行政院環境部": "環境部",
            "各级": "各級",
            "本部指定資訊第三科": "本部綜合規劃科",
            "本部指定資訊": "本部綜合規劃科",
            "傳真：指定資訊": "傳真：(02)0000-0001",
            "部長　指定資訊": "部長　（簽署）",
            "經濟部工業局": "經濟部產業發展署",
            "(02)0000-0000": "(02)2391-0000",
            "承辦人員專員": "承辦專員",
            "依據相關法規及相關法規規定辦理": "依據相關法規規定辦理",
            "指定司（處）": "相關司（處）",
            "指定署": "相關署",
            "○○司（處）": "相關司（處）",
            "○○署": "相關署",
            "指定法": "相關法規",
            "撥冗": "",
            "踴躍與會": "準時出席",
            "！": "。",
        }
        for bad, good in replacements.items():
            draft = draft.replace(bad, good)
        for pattern in (
            r"(\d{2,3})年\s*OO月OO日",
            r"(\d{2,3})年\s*○○月○○日",
            r"(\d{2,3})年\s*O{2,}月O{2,}日",
        ):
            draft = re.sub(pattern, r"\1年12月31日", draft)
        draft = re.sub(r"(\d{2,3})年指定資訊日前", r"\1年12月31日前", draft)
        draft = re.sub(r"(\d{2,3})年指定資訊日", r"\1年12月31日", draft)
        draft = re.sub(r"(\d{2,3})年指定資訊月", r"\1年12月", draft)
        draft = re.sub(r"(\d{2,3})年指定資訊", r"\1年12月31日", draft)
        draft = draft.replace("○○會議室", "第一會議室").replace("○○○", "承辦人員")
        draft = draft.replace("請至本部綜合規劃科下載運用", "請至本部指定下載專區下載運用")
        draft = re.sub(r"副本：\s*指定資訊", "副本：本部相關單位", draft)
        draft = re.sub(r"副本：\s*相關資訊", "副本：本部相關單位", draft)
        draft = re.sub(r"[ \t]{2,}", " ", draft)

        deduped: list[str] = []
        for line in draft.splitlines():
            if deduped and line.strip() and line.strip() == deduped[-1].strip():
                continue
            deduped.append(line)
        draft = "\n".join(deduped)

        lines = draft.splitlines()
        for index, line in enumerate(lines):
            if line.startswith("**主旨**：") and line.count("請查照") > 1:
                lines[index] = line.split("請查照", 1)[0] + "請查照。"
                break
        draft = "\n".join(lines)
        draft = cls._normalize_issue_date_before_meeting(draft)
        draft = cls._stabilize_meeting_notice_fields(draft)
        draft = cls._stabilize_meeting_agenda(draft)
        return cls._normalize_explanation_numbering(draft)

    @staticmethod
    def _normalize_issue_date_before_meeting(draft: str) -> str:
        issue_match = re.search(
            r"(\*\*發文日期\*\*：\s*(?:中華民國)?)\s*(\d{2,3})年(\d{1,2})月(\d{1,2})日",
            draft,
        )
        if not issue_match:
            return draft
        try:
            issue_date = date(
                int(issue_match.group(2)) + 1911,
                int(issue_match.group(3)),
                int(issue_match.group(4)),
            )
        except ValueError:
            return draft

        meeting_dates: list[date] = []
        for pattern in (
            r"訂於\s*(\d{2,3})年(\d{1,2})月(\d{1,2})日",
            r"定於\s*(\d{2,3})年(\d{1,2})月(\d{1,2})日",
            r"開會時間[：:]\s*(\d{2,3})年(\d{1,2})月(\d{1,2})日",
        ):
            for match in re.finditer(pattern, draft):
                try:
                    meeting_dates.append(date(int(match.group(1)) + 1911, int(match.group(2)), int(match.group(3))))
                except ValueError:
                    continue
        if not meeting_dates:
            return draft

        nearest_meeting = min(meeting_dates)
        if nearest_meeting > issue_date:
            return draft

        adjusted_issue = nearest_meeting - timedelta(days=7)
        adjusted_text = (
            f"{issue_match.group(1)}"
            f"{adjusted_issue.year - 1911}年{adjusted_issue.month}月{adjusted_issue.day}日"
        )
        draft = re.sub(
            r"\*\*發文日期\*\*：\s*(?:中華民國)?\s*\d{2,3}年\d{1,2}月\d{1,2}日",
            adjusted_text,
            draft,
            count=1,
        )
        return re.sub(
            r"(\*\*發文字號\*\*：[^第\n]*第)\d{3}",
            lambda match: f"{match.group(1)}{adjusted_issue.year - 1911:03d}",
            draft,
            count=1,
        )

    @staticmethod
    def _stabilize_meeting_notice_fields(draft: str) -> str:
        if "會議" not in draft:
            return draft
        draft = draft.replace("請查照出席", "請查照並準時出席").replace("請查照並出席", "請查照並準時出席")
        if "開會地點" not in draft and "會議地點" not in draft and "地點：" not in draft:
            location_line = "會議地點：本部第一會議室。"
            if "**說明**：" in draft:
                draft = draft.replace("**說明**：", f"**說明**：\n{location_line}", 1)
            elif "**辦法**：" in draft:
                draft = draft.replace("**辦法**：", f"**辦法**：\n{location_line}", 1)
            elif location_line not in draft:
                draft += f"\n{location_line}"
        if "檢送" in draft and "附件：" not in draft:
            draft += "\n\n附件：會議通知及議程資料（隨函附送）"
        return draft

    @staticmethod
    def _stabilize_meeting_agenda(draft: str) -> str:
        if "會議" not in draft or "議程如下" not in draft:
            return draft
        if "（二）討論事項" in draft and "（三）臨時動議" in draft:
            return draft
        agenda_stub = (
            "議程如下：\n"
            "（一）報告事項：前次會議決議辦理情形。\n"
            "（二）討論事項：數位政府推動重點與跨機關協作事項。\n"
            "（三）臨時動議。"
        )
        return draft.replace("議程如下：", agenda_stub, 1)

    @staticmethod
    def _normalize_explanation_numbering(draft: str) -> str:
        if "**說明**：" not in draft:
            return draft
        numerals = "一二三四五六七八九十"
        lines = draft.splitlines()
        in_explanation = False
        counter = 0
        for index, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("**說明**："):
                in_explanation = True
                counter = 0
                continue
            if in_explanation and stripped.startswith("**") and not stripped.startswith("**說明**："):
                break
            if in_explanation and re.match(r"^[一二三四五六七八九十]+、", stripped):
                counter += 1
                numeral = numerals[counter - 1] if counter <= len(numerals) else str(counter)
                rest = re.sub(r"^[一二三四五六七八九十]+、\s*", "", stripped)
                indent = line[: len(line) - len(line.lstrip())]
                lines[index] = f"{indent}{numeral}、{rest}"
        return "\n".join(lines)
