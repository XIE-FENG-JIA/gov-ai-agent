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


def _build_default_doc_number(sender: str, roc_year: int, month: int, day: int) -> str:
    """建立可用的預設發文字號，避免空白 placeholder。"""
    cleaned = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", sender or "")
    prefix = cleaned[:3] if cleaned else "公文"
    return f"{prefix}字第{roc_year:03d}{month:02d}{day:02d}001號"


# ---------------------------------------------------------------------------
# parse_draft 段落解析：資料定義與輔助函式
# ---------------------------------------------------------------------------

_SECTION_KEYS = (
    "subject", "explanation", "basis", "provisions", "attachments", "references",
    # 開會通知單
    "meeting_time", "meeting_location", "agenda",
    # 會勘通知單
    "inspection_time", "inspection_location", "inspection_items",
    "required_documents", "attendees",
    # 公務電話紀錄
    "call_time", "call_summary", "caller", "callee",
    "follow_up_items", "recorder", "reviewer",
    # 手令
    "directive_content", "deadline", "cc_list",
    # 開會紀錄
    "meeting_name", "chairperson", "observers", "absentees",
    "opening_remarks", "previous_minutes", "report_items",
    "discussion_items", "resolutions", "motions",
    "chairman_conclusion", "adjournment_time",
    # 通用
    "copies_to", "cc_copies",
)

# 關鍵字 → section key（按長度降序排列，避免短前綴先匹配）
_KEYWORD_TO_SECTION: dict[str, str] = {
    k: v for k, v in sorted([
        ("主旨", "subject"), ("說明", "explanation"), ("依據", "basis"),
        ("辦法", "provisions"), ("公告事項", "provisions"),
        ("辦法/公告事項", "provisions"), ("擬辦", "provisions"),
        ("附件", "attachments"), ("參考來源", "references"),
        ("開會時間", "meeting_time"), ("開會地點", "meeting_location"),
        ("議程", "agenda"),
        ("會勘時間", "inspection_time"), ("會勘地點", "inspection_location"),
        ("會勘事項", "inspection_items"), ("應攜文件", "required_documents"),
        ("應出席單位", "attendees"),
        ("通話時間", "call_time"), ("發話人", "caller"), ("受話人", "callee"),
        ("通話摘要", "call_summary"), ("追蹤事項", "follow_up_items"),
        ("紀錄人", "recorder"), ("核閱", "reviewer"),
        ("指示事項", "directive_content"), ("完成期限", "deadline"),
        ("副知", "cc_list"),
        # 開會紀錄
        ("會議名稱", "meeting_name"), ("主席", "chairperson"),
        ("主持人", "chairperson"), ("主席（主持人）", "chairperson"),
        ("出席人員", "attendees"), ("列席人員", "observers"),
        ("請假人員", "absentees"), ("紀錄人", "recorder"),
        ("主席致詞", "opening_remarks"),
        ("確認上次會議紀錄", "previous_minutes"),
        ("報告事項", "report_items"), ("討論事項", "discussion_items"),
        ("決議", "resolutions"), ("決定", "resolutions"),
        ("臨時動議", "motions"), ("主席結論", "chairman_conclusion"),
        ("散會時間", "adjournment_time"), ("散會", "adjournment_time"),
        ("正本", "copies_to"), ("副本", "cc_copies"),
    ], key=lambda pair: len(pair[0]), reverse=True)
}

# 檔頭欄位：僅作為段落邊界，不收集內容
_HEADER_FIELDS = (
    "密等及解密條件或保密期限", "密等",
    "機關", "受文者", "發文日期", "發文字號", "速別",
    "發令人", "受令人", "發令日期", "發令字號",
    "發信人", "收信人", "紀錄日期", "紀錄字號",
    "日期", "字號", "會銜機關",
    "時間", "地點",
)

# 用於行內內容擷取的關鍵字清單（長度降序）
_HEADER_KEYWORDS = sorted(_KEYWORD_TO_SECTION.keys(), key=len, reverse=True)


def _is_section_header(text: str, keyword: str) -> bool:
    """檢查 text 是否精確以 keyword 作為段落標題。

    標題詞後必須接冒號、空白或直接結尾，
    避免「說明書」「主旨演講」等非標題文字誤判。
    """
    if not text.startswith(keyword):
        return False
    if len(text) == len(keyword):
        return True
    return text[len(keyword)] in ("：", ":", " ", "\t", "\u3000")


def _detect_header(line: str) -> str | None:
    """偵測公文段落標題，回傳對應的 section key 或 '_skip'。"""
    clean = line.strip().replace('#', '').strip()
    for keyword, section in _KEYWORD_TO_SECTION.items():
        if _is_section_header(clean, keyword):
            return section
    for hf in _HEADER_FIELDS:
        if _is_section_header(clean, hf):
            return "_skip"
    return None


class TemplateEngine:
    """
    模板引擎：使用 Jinja2 模板結構化並標準化公文內容。
    """

    def __init__(self) -> None:
        template_dir = os.path.join(os.path.dirname(__file__), "..", "assets", "templates")
        # keep_trailing_newline=True 保留結尾換行
        # autoescape=False：此模板引擎僅用於公文 Markdown/純文字渲染，
        # 輸出不直接作為 HTML 回應。Web UI 使用獨立的 Jinja2 環境（autoescape=True）。
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            keep_trailing_newline=True,
            autoescape=False,
        )
        # 註冊自訂過濾器：將 loop.index 轉為中文數字
        self.env.filters["cn"] = _chinese_index

    def parse_draft(self, draft_text: str) -> dict[str, str]:
        """使用逐行狀態機將原始 Markdown 草稿解析為結構化段落。"""
        if not draft_text:
            return {k: "" for k in _SECTION_KEYS}

        draft_text = clean_markdown_artifacts(draft_text)
        lines = draft_text.replace('\r\n', '\n').split('\n')

        buffer: dict[str, list[str]] = {k: [] for k in _SECTION_KEYS}
        current_section: str | None = None

        for line in lines:
            new_section = _detect_header(line)
            if new_section:
                if new_section == "_skip":
                    current_section = None
                    continue
                current_section = new_section
                # 嘗試提取同行內容：先用冒號分割，再嘗試關鍵字長度截取
                parts = line.split('：', 1) if '：' in line else line.split(':', 1)
                if len(parts) > 1 and parts[1].strip():
                    buffer[current_section].append(parts[1].strip())
                else:
                    clean = line.strip().replace('#', '').strip()
                    for kw in _HEADER_KEYWORDS:
                        if clean.startswith(kw) and len(clean) > len(kw):
                            rest = clean[len(kw):].lstrip(" \t\u3000：:")
                            if rest:
                                buffer[current_section].append(rest)
                            break
                continue

            if current_section and line.strip():
                buffer[current_section].append(line.strip())

        # 後處理：統一 join 所有段落
        sections = {k: "\n".join(v).strip() for k, v in buffer.items()}

        # 特殊處理：依據合併至說明
        if sections["basis"]:
            if sections["explanation"]:
                sections["explanation"] = f"依據：{sections['basis']}\n{sections['explanation']}"
            else:
                sections["explanation"] = f"依據：{sections['basis']}"

        # 特殊處理：重新編排辦法段落編號
        sections["provisions"] = renumber_provisions(sections["provisions"])

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
            "開會紀錄": "meeting_minutes.j2",
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
            # 開會紀錄專用欄位
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
            # 通用：正本、副本
            "copies_to": sections.get("copies_to") or "",
            "cc_copies": sections.get("cc_copies") or "",
        }

        try:
            output = template.render(**context)
        except Exception as e:
            logger.warning("Jinja2 模板渲染失敗: %s，使用備用格式", e)
            return self._fallback_apply(requirement, sections)

        # 在輸出前加入公文類型標題行，供 DocxExporter 辨識與測試驗證
        doc_type_title = context["doc_type"]
        output = f"{doc_type_title}\n\n{output}"

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

        doc_type = requirement.doc_type or "函"
        template = f"""{doc_type}

**機關**：{requirement.sender}
**發文日期**：中華民國{_roc}年{_today.month}月{_today.day}日
**發文字號**：{_build_default_doc_number(requirement.sender, _roc, _today.month, _today.day)}
**速別**：{_normalize_urgency(requirement.urgency or "普通")}
**密等及解密條件或保密期限**：普通

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
