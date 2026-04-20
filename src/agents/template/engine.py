import logging
import os
import re
from datetime import date

from jinja2 import Environment, FileSystemLoader

from src.agents.template.helpers import (
    _build_attachment_ref,
    _build_default_doc_number,
    _chinese_index,
    _normalize_reference_section,
    _normalize_urgency,
    clean_markdown_artifacts,
    renumber_provisions,
)
from src.agents.template.parser import _HEADER_KEYWORDS, _SECTION_KEYS, _detect_header
from src.core.models import PublicDocRequirement

logger = logging.getLogger(__name__)


class TemplateEngine:
    """模板引擎：使用 Jinja2 模板結構化並標準化公文內容。"""

    def __init__(self) -> None:
        template_dir = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "assets", "templates")
        )
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            keep_trailing_newline=True,
            autoescape=False,
        )
        self.env.filters["cn"] = _chinese_index

    def parse_draft(self, draft_text: str) -> dict[str, str]:
        if not draft_text:
            return {key: "" for key in _SECTION_KEYS}

        draft_text = clean_markdown_artifacts(draft_text)
        lines = draft_text.replace("\r\n", "\n").split("\n")
        buffer: dict[str, list[str]] = {key: [] for key in _SECTION_KEYS}
        current_section: str | None = None

        for line in lines:
            new_section = _detect_header(line)
            if new_section:
                if new_section == "_skip":
                    current_section = None
                    continue
                current_section = new_section
                parts = line.split("：", 1) if "：" in line else line.split(":", 1)
                if len(parts) > 1 and parts[1].strip():
                    buffer[current_section].append(parts[1].strip())
                else:
                    clean = line.strip().replace("#", "").strip()
                    for keyword in _HEADER_KEYWORDS:
                        if clean.startswith(keyword) and len(clean) > len(keyword):
                            rest = clean[len(keyword):].lstrip(" \t\u3000：:")
                            if rest:
                                buffer[current_section].append(rest)
                            break
                continue

            if current_section and line.strip():
                buffer[current_section].append(line.strip())

        sections = {key: "\n".join(values).strip() for key, values in buffer.items()}
        if sections["basis"]:
            if sections["explanation"]:
                sections["explanation"] = f"依據：{sections['basis']}\n{sections['explanation']}"
            else:
                sections["explanation"] = f"依據：{sections['basis']}"

        sections["provisions"] = renumber_provisions(sections["provisions"])
        return sections

    @staticmethod
    def _resolve_attachments(sections: dict[str, str], requirement: PublicDocRequirement) -> list[str]:
        section_attachments = sections.get("attachments", "").strip()
        if section_attachments:
            return [attachment.strip() for attachment in section_attachments.split("\n") if attachment.strip()]
        return requirement.attachments or []

    def _parse_list_items(self, text: str) -> list[str]:
        items: list[str] = []
        if not text:
            return items

        sub_item_re = re.compile(r"^[（\(][\d一二三四五六七八九十]+[）\)][、.]?\s*")
        main_item_re = re.compile(r"^[\d一二三四五六七八九十]+[、.)]\s*(.+)")

        for line in text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            if sub_item_re.match(stripped):
                if items:
                    items[-1] += "\n" + stripped
                else:
                    items.append(stripped)
                continue
            main_match = main_item_re.match(stripped)
            if main_match:
                items.append(main_match.group(1))
            else:
                items.append(stripped)

        return items

    def apply_template(self, requirement: PublicDocRequirement, sections: dict[str, str]) -> str:
        today = date.today()
        roc_year = today.year - 1911
        doc_type_template_map = {
            "函": "han.j2",
            "書函": "han.j2",
            "呈": "han.j2",
            "咨": "han.j2",
            "公告": "announcement.j2",
            "簽": "sign.j2",
            "令": "decree.j2",
            "開會通知單": "meeting_notice.j2",
            "會勘通知單": "site_inspection.j2",
            "公務電話紀錄": "phone_record.j2",
            "手令": "directive.j2",
            "箋函": "memo.j2",
            "開會紀錄": "meeting_minutes.j2",
        }
        template_name = doc_type_template_map.get(requirement.doc_type)
        if template_name is None:
            logger.warning("未知公文類型 '%s'，使用預設函模板", requirement.doc_type)
            template_name = "han.j2"

        try:
            template = self.env.get_template(template_name)
        except Exception as exc:
            logger.warning("模板載入失敗: %s，使用備用格式", exc)
            return self._fallback_apply(requirement, sections)

        context = {
            "doc_type": requirement.doc_type or "函",
            "sender": requirement.sender or "（未指定）",
            "receiver": requirement.receiver or "（未指定）",
            "urgency": _normalize_urgency(requirement.urgency or "普通"),
            "security_level": "普通",
            "year": roc_year,
            "month": today.month,
            "day": today.day,
            "doc_number": _build_default_doc_number(requirement.sender, roc_year, today.month, today.day),
            "subject": sections.get("subject") or requirement.subject or "（未提供主旨）",
            "explanation_text": sections.get("explanation") or requirement.reason or "",
            "explanation_points": self._parse_list_items(sections.get("explanation") or ""),
            "provision_text": sections.get("provisions") or "",
            "provision_points": self._parse_list_items(sections.get("provisions") or ""),
            "action_text": sections.get("provisions") or "",
            "action_points": self._parse_list_items(sections.get("provisions") or ""),
            "basis": sections.get("basis") or "",
            "attachments": self._resolve_attachments(sections, requirement),
            "attachment_ref": _build_attachment_ref(requirement.attachments),
            "meeting_time": sections.get("meeting_time") or "",
            "meeting_location": sections.get("meeting_location") or "",
            "agenda_text": sections.get("agenda") or "",
            "agenda_points": self._parse_list_items(sections.get("agenda") or ""),
            "inspection_time": sections.get("inspection_time") or "",
            "inspection_location": sections.get("inspection_location") or "",
            "inspection_items": sections.get("inspection_items") or "",
            "required_documents": sections.get("required_documents") or "",
            "call_time": sections.get("call_time") or "",
            "caller": sections.get("caller") or "",
            "callee": sections.get("callee") or "",
            "call_summary": sections.get("call_summary") or "",
            "follow_up_items": sections.get("follow_up_items") or "",
            "directive_content": sections.get("directive_content") or "",
            "deadline": sections.get("deadline") or "",
            "attendees": sections.get("attendees") or "",
            "recorder": sections.get("recorder") or "",
            "reviewer": sections.get("reviewer") or "",
            "cc_list": sections.get("cc_list") or "",
            "meeting_name": sections.get("meeting_name") or sections.get("subject") or "",
            "chairperson": sections.get("chairperson") or "",
            "observers": sections.get("observers") or "",
            "absentees": sections.get("absentees") or "",
            "opening_remarks": sections.get("opening_remarks") or "",
            "previous_minutes": sections.get("previous_minutes") or "",
            "report_items_text": sections.get("report_items") or "",
            "report_items_points": self._parse_list_items(sections.get("report_items") or ""),
            "discussion_items_text": sections.get("discussion_items") or "",
            "discussion_items_points": self._parse_list_items(sections.get("discussion_items") or ""),
            "resolutions_text": sections.get("resolutions") or "",
            "resolutions_points": self._parse_list_items(sections.get("resolutions") or ""),
            "motions_text": sections.get("motions") or "",
            "chairman_conclusion": sections.get("chairman_conclusion") or "",
            "adjournment_time": sections.get("adjournment_time") or "",
            "copies_to": sections.get("copies_to") or "",
            "cc_copies": sections.get("cc_copies") or "",
        }

        try:
            output = template.render(**context)
        except Exception as exc:
            logger.warning("Jinja2 模板渲染失敗: %s，使用備用格式", exc)
            return self._fallback_apply(requirement, sections)

        output = f"{context['doc_type']}\n\n{output}"
        reference_block = _normalize_reference_section(sections.get("references") or "")
        if reference_block:
            output += "\n\n" + reference_block
        return output

    def _fallback_apply(self, requirement: PublicDocRequirement, sections: dict[str, str]) -> str:
        subject = sections.get("subject") or requirement.subject
        explanation = sections.get("explanation") or requirement.reason or ""
        provisions = sections.get("provisions") or ""

        if requirement.action_items and not explanation:
            explanation = "\n".join([f"{index + 1}、{item}" for index, item in enumerate(requirement.action_items)])

        attachment_text = ""
        if requirement.attachments:
            attachment_text = "附件：\n" + "\n".join([f"- {item}" for item in requirement.attachments])

        today = date.today()
        roc_year = today.year - 1911
        doc_type = requirement.doc_type or "函"
        template = f"""{doc_type}

**機關**：{requirement.sender}
**發文日期**：中華民國{roc_year}年{today.month}月{today.day}日
**發文字號**：{_build_default_doc_number(requirement.sender, roc_year, today.month, today.day)}
**速別**：{_normalize_urgency(requirement.urgency or "普通")}
**密等及解密條件或保密期限**：普通

**受文者**：{requirement.receiver}

**主旨**：{subject}

**說明**：
{explanation}

**辦法**：
{provisions}
{attachment_text}
"""
        result = template.replace("**辦法**：\n\n", "")
        result = result.replace("**說明**：\n\n", "")
        return result
