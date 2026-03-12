import logging
import re
import os
from datetime import date
from jinja2 import Environment, FileSystemLoader
from src.core.models import PublicDocRequirement
from src.core.constants import CHINESE_NUMBERS, MAX_CHINESE_NUMBER

logger = logging.getLogger(__name__)

def clean_markdown_artifacts(text: str | None) -> str:
    """清除 markdown 格式標記和其他不應出現在公文中的符號"""
    if not text:
        return ""

    # 移除 markdown 程式碼區塊標記
    text = re.sub(r'```\w*\n?', '', text)
    text = re.sub(r'```', '', text)

    # 移除 markdown 標題標記 (# ## ###)
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)

    # 移除 markdown 粗體/斜體標記
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)
    text = re.sub(r'_([^_]+)_', r'\1', text)

    # 移除 markdown 行內程式碼標記 `code` -> code
    text = re.sub(r'`([^`]+)`', r'\1', text)

    # 移除 markdown 刪除線 ~~text~~ -> text
    text = re.sub(r'~~([^~]+)~~', r'\1', text)

    # 移除 markdown 連結標記 [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)

    # 移除 markdown blockquote 標記 (> text -> text)
    text = re.sub(r'^>\s?', '', text, flags=re.MULTILINE)

    # 移除多餘的分隔線
    text = re.sub(r'^---+\s*$', '', text, flags=re.MULTILINE)

    # 移除「捺印處」等不應出現的文字
    text = re.sub(r'捺印處', '', text)

    # 清理多餘空行
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()

def renumber_provisions(text: str | None) -> str:
    """重新編排辦法段落的編號，使用標準中文編號格式"""
    if not text:
        return ""

    lines = text.split('\n')
    result = []
    main_counter = 0
    sub_counter = 0

    # 定義不應被編號的項目（簽署區相關）
    skip_patterns = [
        r'^正本[：:]',
        r'^副本[：:]',
        r'^承辦',
        r'^局長',
        r'^處長',
        r'^科長',
        r'^主任',
        r'^秘書',
        r'^中華民國',
        r'蓋章',
        r'（蓋章）',
    ]

    for line in lines:
        stripped = line.strip()
        if not stripped:
            result.append('')
            continue

        # 先移除原有編號，再檢查是否為不應被重新編號的項目（簽署區相關）
        # 要求分隔符號為必填（[、.).]），避免將「三民主義」等以中文數字開頭的普通文字誤判為編號
        stripped_no_num = re.sub(r'^[\d一二三四五六七八九十]+[、.)]\s*', '', stripped)
        should_skip = False
        for pattern in skip_patterns:
            if re.match(pattern, stripped_no_num):
                should_skip = True
                result.append(stripped_no_num)
                break

        if should_skip:
            continue

        # 檢測是否為主編號項目（數字或中文數字 + 必填分隔符號）
        main_match = re.match(r'^[\d一二三四五六七八九十]+[、.)]\s*(.+)', stripped)
        # 檢測是否為子編號項目（括號數字開頭）
        sub_match = re.match(r'^[\(（][\d一二三四五六七八九十]+[\)）][、.]?\s*(.+)', stripped)

        if sub_match:
            # 子項目
            sub_counter += 1
            content = sub_match.group(1)
            cn = CHINESE_NUMBERS[sub_counter - 1] if sub_counter <= MAX_CHINESE_NUMBER else sub_counter
            result.append(f"（{cn}）{content}")
        elif main_match:
            # 主項目
            main_counter += 1
            sub_counter = 0  # 重置子編號
            content = main_match.group(1)
            cn = CHINESE_NUMBERS[main_counter - 1] if main_counter <= MAX_CHINESE_NUMBER else main_counter
            result.append(f"{cn}、{content}")
        else:
            # 普通文字，保持原樣
            result.append(stripped)

    return '\n'.join(result)

def _chinese_index(value: int) -> str:
    """Jinja2 自訂過濾器：將阿拉伯數字轉換為中文數字（供公文條列編號使用）。"""
    idx = value - 1  # loop.index 從 1 開始，CHINESE_NUMBERS 從 0 開始
    if 0 <= idx < MAX_CHINESE_NUMBER:
        return CHINESE_NUMBERS[idx]
    return str(value)


def _build_attachment_ref(attachments: list[str] | None) -> str:
    """根據附件清單生成檔頭附件引用文字。

    單一附件直接使用附件名，多附件使用「如說明」引用。
    """
    if not attachments:
        return ""
    if len(attachments) == 1:
        return attachments[0]
    return "如說明"


def _normalize_urgency(urgency: str) -> str:
    """將速別標準化為含「件」後綴的正式格式。

    例如：「普通」→「普通件」，「最速件」維持不變。
    """
    if not urgency:
        return "普通件"
    if urgency.endswith("件"):
        return urgency
    return urgency + "件"


class TemplateEngine:
    """
    模板引擎：使用 Jinja2 模板結構化並標準化公文內容。
    """

    def __init__(self) -> None:
        template_dir = os.path.join(os.path.dirname(__file__), "..", "assets", "templates")
        # keep_trailing_newline=True 保留結尾換行
        # autoescape=False 公文不需要 HTML 轉義，避免特殊字元被意外轉義
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            keep_trailing_newline=True,
            autoescape=False,
        )
        # 註冊自訂過濾器：將 loop.index 轉為中文數字
        self.env.filters["cn"] = _chinese_index

    def parse_draft(self, draft_text: str) -> dict[str, str]:
        """
        使用逐行狀態機將原始 Markdown 草稿解析為結構化段落。
        會自動清理 Markdown 標記並重新編排編號。
        """
        # 防護空值輸入
        if not draft_text:
            return {
                "subject": "",
                "explanation": "",
                "basis": "",
                "provisions": "",
                "attachments": "",
                "references": "",
            }

        # 首先清理 markdown 標記
        draft_text = clean_markdown_artifacts(draft_text)

        sections = {
            "subject": "",
            "explanation": "",
            "basis": "",
            "provisions": "",
            "attachments": "",
            "references": "",
            # 開會通知單專用
            "meeting_time": "",
            "meeting_location": "",
            "agenda": "",
            # 會勘通知單專用
            "inspection_time": "",
            "inspection_location": "",
            "inspection_items": "",
            "required_documents": "",
            "attendees": "",
            # 公務電話紀錄專用
            "call_time": "",
            "call_summary": "",
            "caller": "",
            "callee": "",
            "follow_up_items": "",
            "recorder": "",
            "reviewer": "",
            # 手令專用
            "directive_content": "",
            "deadline": "",
            "cc_list": "",
            # 通用
            "copies_to": "",
            "cc_copies": "",
        }

        # Internal state
        current_section = None
        buffer = {
            "subject": [],
            "explanation": [],
            "basis": [], # 依據
            "provisions": [],
            "attachments": [],
            "references": [],
            # 開會通知單專用
            "meeting_time": [],
            "meeting_location": [],
            "agenda": [],
            # 會勘通知單專用
            "inspection_time": [],
            "inspection_location": [],
            "inspection_items": [],
            "required_documents": [],
            "attendees": [],
            # 公務電話紀錄專用
            "call_time": [],
            "caller": [],
            "callee": [],
            "call_summary": [],
            "follow_up_items": [],
            "recorder": [],
            "reviewer": [],
            # 手令專用
            "directive_content": [],
            "deadline": [],
            "cc_list": [],
            # 通用
            "copies_to": [],
            "cc_copies": [],
        }

        # Normalize
        lines = draft_text.replace('\r\n', '\n').split('\n')

        # 檔頭欄位：不會收集內容，僅作為段落邊界
        _HEADER_FIELDS = [
            "密等及解密條件或保密期限", "密等",
            "機關", "受文者", "發文日期", "發文字號", "速別",
            "發令人", "受令人", "發令日期", "發令字號",
            "發信人", "收信人",
            "紀錄日期", "紀錄字號",
            "日期", "字號",
            "會銜機關",
        ]

        # 辨識段落標題的輔助函式
        def _is_section_header(text: str, keyword: str) -> bool:
            """檢查 text 是否精確以 keyword 作為段落標題。

            標題詞後必須接冒號、空白或直接結尾，
            避免「說明書」「主旨演講」等非標題文字誤判。
            """
            if not text.startswith(keyword):
                return False
            if len(text) == len(keyword):
                return True
            next_char = text[len(keyword)]
            return next_char in ("：", ":", " ", "\t", "\u3000")

        def detect_header(line: str) -> str | None:
            """偵測公文段落標題，回傳對應的 section 鍵值。"""
            clean = line.strip().replace('#', '').strip()
            if _is_section_header(clean, "主旨"):
                return "subject"
            if _is_section_header(clean, "說明"):
                return "explanation"
            if _is_section_header(clean, "依據"):
                return "basis"
            if (_is_section_header(clean, "辦法")
                    or _is_section_header(clean, "公告事項")
                    or _is_section_header(clean, "辦法/公告事項")
                    or _is_section_header(clean, "擬辦")):
                return "provisions"
            if _is_section_header(clean, "附件"):
                return "attachments"
            if _is_section_header(clean, "參考來源"):
                return "references"
            # 開會通知單
            if _is_section_header(clean, "開會時間"):
                return "meeting_time"
            if _is_section_header(clean, "開會地點"):
                return "meeting_location"
            if _is_section_header(clean, "議程"):
                return "agenda"
            # 會勘通知單
            if _is_section_header(clean, "會勘時間"):
                return "inspection_time"
            if _is_section_header(clean, "會勘地點"):
                return "inspection_location"
            if _is_section_header(clean, "會勘事項"):
                return "inspection_items"
            if _is_section_header(clean, "應攜文件"):
                return "required_documents"
            if _is_section_header(clean, "應出席單位"):
                return "attendees"
            # 公務電話紀錄
            if _is_section_header(clean, "通話時間"):
                return "call_time"
            if _is_section_header(clean, "發話人"):
                return "caller"
            if _is_section_header(clean, "受話人"):
                return "callee"
            if _is_section_header(clean, "通話摘要"):
                return "call_summary"
            if _is_section_header(clean, "追蹤事項"):
                return "follow_up_items"
            if _is_section_header(clean, "紀錄人"):
                return "recorder"
            if _is_section_header(clean, "核閱"):
                return "reviewer"
            # 手令
            if _is_section_header(clean, "指示事項"):
                return "directive_content"
            if _is_section_header(clean, "完成期限"):
                return "deadline"
            # 通用
            if _is_section_header(clean, "副知"):
                return "cc_list"
            if _is_section_header(clean, "正本"):
                return "copies_to"
            if _is_section_header(clean, "副本"):
                return "cc_copies"
            # 檔頭欄位：視為段落邊界但不收集內容（避免誤歸前段）
            for hf in _HEADER_FIELDS:
                if _is_section_header(clean, hf):
                    return "_skip"
            return None

        # 所有段落標題關鍵字（按長度降序，避免短字串優先匹配）
        _HEADER_KEYWORDS = [
            "辦法/公告事項", "應出席單位", "參考來源", "公告事項",
            "開會時間", "開會地點",
            "會勘時間", "會勘地點", "會勘事項", "應攜文件",
            "通話時間", "通話摘要", "追蹤事項", "指示事項", "完成期限",
            "發話人", "受話人", "紀錄人",
            "主旨", "說明", "依據", "辦法", "擬辦", "附件", "議程", "核閱",
            "副知", "正本", "副本",
        ]

        for line in lines:
            new_section = detect_header(line)
            if new_section:
                if new_section == "_skip":
                    # 檔頭欄位：中斷當前段落收集但不開啟新段落
                    current_section = None
                    continue
                current_section = new_section
                # 嘗試提取同行內容：先用冒號分割，再嘗試空格分割
                parts = line.split('：', 1) if '：' in line else line.split(':', 1)
                if len(parts) > 1 and parts[1].strip():
                    buffer[current_section].append(parts[1].strip())
                else:
                    # 冒號分割無效時，根據關鍵字長度截取剩餘內容
                    clean = line.strip().replace('#', '').strip()
                    for kw in _HEADER_KEYWORDS:
                        if clean.startswith(kw) and len(clean) > len(kw):
                            rest = clean[len(kw):].lstrip(" \t\u3000：:")
                            if rest:
                                buffer[current_section].append(rest)
                            break
                continue

            if current_section:
                if line.strip():
                    buffer[current_section].append(line.strip())

        # Post-process
        sections["subject"] = "\n".join(buffer["subject"]).strip()

        basis_text = "\n".join(buffer["basis"]).strip()
        explanation_text = "\n".join(buffer["explanation"]).strip()

        # 保留獨立的 basis 欄位（供公告模板使用）
        sections["basis"] = basis_text

        if basis_text:
            if explanation_text:
                sections["explanation"] = f"依據：{basis_text}\n{explanation_text}"
            else:
                sections["explanation"] = f"依據：{basis_text}"
        else:
            sections["explanation"] = explanation_text

        # 重新編排辦法段落編號
        raw_provisions = "\n".join(buffer["provisions"]).strip()
        sections["provisions"] = renumber_provisions(raw_provisions)

        sections["attachments"] = "\n".join(buffer["attachments"]).strip()
        sections["references"] = "\n".join(buffer["references"]).strip()
        # 開會通知單
        sections["meeting_time"] = "\n".join(buffer["meeting_time"]).strip()
        sections["meeting_location"] = "\n".join(buffer["meeting_location"]).strip()
        sections["agenda"] = "\n".join(buffer["agenda"]).strip()
        # 會勘通知單
        sections["inspection_time"] = "\n".join(buffer["inspection_time"]).strip()
        sections["inspection_location"] = "\n".join(buffer["inspection_location"]).strip()
        sections["inspection_items"] = "\n".join(buffer["inspection_items"]).strip()
        sections["required_documents"] = "\n".join(buffer["required_documents"]).strip()
        sections["attendees"] = "\n".join(buffer["attendees"]).strip()
        # 公務電話紀錄
        sections["call_time"] = "\n".join(buffer["call_time"]).strip()
        sections["caller"] = "\n".join(buffer["caller"]).strip()
        sections["callee"] = "\n".join(buffer["callee"]).strip()
        sections["call_summary"] = "\n".join(buffer["call_summary"]).strip()
        sections["follow_up_items"] = "\n".join(buffer["follow_up_items"]).strip()
        sections["recorder"] = "\n".join(buffer["recorder"]).strip()
        sections["reviewer"] = "\n".join(buffer["reviewer"]).strip()
        # 手令
        sections["directive_content"] = "\n".join(buffer["directive_content"]).strip()
        sections["deadline"] = "\n".join(buffer["deadline"]).strip()
        sections["cc_list"] = "\n".join(buffer["cc_list"]).strip()
        # 通用
        sections["copies_to"] = "\n".join(buffer["copies_to"]).strip()
        sections["cc_copies"] = "\n".join(buffer["cc_copies"]).strip()

        return sections

    @staticmethod
    def _resolve_attachments(
        sections: dict[str, str],
        requirement: PublicDocRequirement,
    ) -> list[str]:
        """優先使用 sections 解析到的附件文字（更詳細），否則回退到 requirement。"""
        section_att = sections.get("attachments", "").strip()
        if section_att:
            return [a.strip() for a in section_att.split("\n") if a.strip()]
        return requirement.attachments or []

    def _parse_list_items(self, text: str) -> list[str]:
        """將文字區塊轉換為清單項目，並移除主編號但保留子編號。

        主項（一、二、三、）的編號會被移除（模板會重新編號），
        子項（（一）（二）等括號編號項目）保留原始格式並附加到父項中。
        """
        items: list[str] = []
        if not text:
            return items

        # 子項模式：以 （一） 或 (1) 開頭（括號包裹的編號）
        sub_item_re = re.compile(
            r"^[（\(][\d一二三四五六七八九十]+[）\)][、.]?\s*"
        )
        # 主項模式：行首中文/阿拉伯數字 + 必填分隔符號（一、二. 3）等）
        main_item_re = re.compile(r"^[\d一二三四五六七八九十]+[、.)]\s*(.+)")

        for line in text.split('\n'):
            stripped = line.strip()
            if not stripped:
                continue

            # 子項：保留原始格式，附加到最後一個主項
            if sub_item_re.match(stripped):
                if items:
                    items[-1] += "\n" + stripped
                else:
                    items.append(stripped)
                continue

            # 主項：移除編號
            main_match = main_item_re.match(stripped)
            if main_match:
                items.append(main_match.group(1))
            else:
                items.append(stripped)

        return items

    def apply_template(self, requirement: PublicDocRequirement, sections: dict[str, str]) -> str:
        """
        使用 Jinja2 將內容渲染為標準 Markdown 模板格式。
        """
        today = date.today()
        roc_year = today.year - 1911

        _DOC_TYPE_TEMPLATE_MAP = {
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
        }
        template_name = _DOC_TYPE_TEMPLATE_MAP.get(requirement.doc_type)
        if template_name is None:
            logger.warning("未知公文類型 '%s'，使用預設函模板", requirement.doc_type)
            template_name = "han.j2"

        try:
            template = self.env.get_template(template_name)
        except Exception as e:
            logger.warning("模板載入失敗: %s，使用備用格式", e)
            return self._fallback_apply(requirement, sections)

        # 安全處理所有可能為 None 的欄位
        context = {
            "doc_type": requirement.doc_type or "函",
            "sender": requirement.sender or "（未指定）",
            "receiver": requirement.receiver or "（未指定）",
            "urgency": _normalize_urgency(requirement.urgency or "普通"),
            "year": roc_year,
            "month": today.month,
            "day": today.day,
            "doc_number": "______號",
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
            # 開會通知單專用欄位
            "meeting_time": sections.get("meeting_time") or "",
            "meeting_location": sections.get("meeting_location") or "",
            "agenda_text": sections.get("agenda") or "",
            "agenda_points": self._parse_list_items(sections.get("agenda") or ""),
            # 會勘通知單專用欄位
            "inspection_time": sections.get("inspection_time") or "",
            "inspection_location": sections.get("inspection_location") or "",
            "inspection_items": sections.get("inspection_items") or "",
            "required_documents": sections.get("required_documents") or "",
            # 公務電話紀錄專用欄位
            "call_time": sections.get("call_time") or "",
            "caller": sections.get("caller") or "",
            "callee": sections.get("callee") or "",
            "call_summary": sections.get("call_summary") or "",
            "follow_up_items": sections.get("follow_up_items") or "",
            # 手令專用欄位
            "directive_content": sections.get("directive_content") or "",
            "deadline": sections.get("deadline") or "",
            # 會勘通知單：應出席單位
            "attendees": sections.get("attendees") or "",
            # 公務電話紀錄：紀錄人、核閱
            "recorder": sections.get("recorder") or "",
            "reviewer": sections.get("reviewer") or "",
            # 手令：副知
            "cc_list": sections.get("cc_list") or "",
            # 通用：正本、副本
            "copies_to": sections.get("copies_to") or "",
            "cc_copies": sections.get("cc_copies") or "",
        }

        try:
            output = template.render(**context)
        except Exception as e:
            logger.warning("Jinja2 模板渲染失敗: %s，使用備用格式", e)
            return self._fallback_apply(requirement, sections)

        if sections.get("references"):
            output += "\n\n**參考來源**：\n" + sections["references"]

        return output

    def _fallback_apply(self, requirement: PublicDocRequirement, sections: dict[str, str]) -> str:
        """備用的簡易字串格式化方法。"""
        subject = sections.get("subject") or requirement.subject
        explanation = sections.get("explanation") or requirement.reason or ""
        provisions = sections.get("provisions") or ""

        if requirement.action_items and not explanation:
            explanation = "\n".join([f"{i+1}、{item}" for i, item in enumerate(requirement.action_items)])

        att_text = ""
        if requirement.attachments:
            att_text = "附件：\n" + "\n".join([f"- {item}" for item in requirement.attachments])

        from datetime import date as _date
        _today = _date.today()
        _roc = _today.year - 1911

        template = f"""**機關**：{requirement.sender}
**發文日期**：中華民國{_roc}年{_today.month}月{_today.day}日
**發文字號**：______號
**速別**：{_normalize_urgency(requirement.urgency or "普通")}
**密等及解密條件或保密期限**：

**受文者**：{requirement.receiver}

**主旨**：{subject}

**說明**：
{explanation}

**辦法**：
{provisions}
{att_text}
"""
        # 移除空白段落（說明或辦法為空時不應渲染空標題）
        result = template.replace("**辦法**：\n\n", "")
        result = result.replace("**說明**：\n\n", "")
        return result
