_SECTION_KEYS = (
    "subject", "explanation", "basis", "provisions", "attachments", "references",
    "meeting_time", "meeting_location", "agenda",
    "inspection_time", "inspection_location", "inspection_items",
    "required_documents", "attendees",
    "call_time", "call_summary", "caller", "callee",
    "follow_up_items", "recorder", "reviewer",
    "directive_content", "deadline", "cc_list",
    "meeting_name", "chairperson", "observers", "absentees",
    "opening_remarks", "previous_minutes", "report_items",
    "discussion_items", "resolutions", "motions",
    "chairman_conclusion", "adjournment_time",
    "copies_to", "cc_copies",
)

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

_HEADER_FIELDS = (
    "密等及解密條件或保密期限", "密等",
    "機關", "受文者", "發文日期", "發文字號", "速別",
    "發令人", "受令人", "發令日期", "發令字號",
    "發信人", "收信人", "紀錄日期", "紀錄字號",
    "日期", "字號", "會銜機關",
    "時間", "地點",
)

_HEADER_KEYWORDS = sorted(_KEYWORD_TO_SECTION.keys(), key=len, reverse=True)


def _is_section_header(text: str, keyword: str) -> bool:
    if not text.startswith(keyword):
        return False
    if len(text) == len(keyword):
        return True
    return text[len(keyword)] in ("：", ":", " ", "\t", "\u3000")


def _detect_header(line: str) -> str | None:
    clean = line.strip().replace("#", "").strip()
    for keyword, section in _KEYWORD_TO_SECTION.items():
        if _is_section_header(clean, keyword):
            return section
    for header_field in _HEADER_FIELDS:
        if _is_section_header(clean, header_field):
            return "_skip"
    return None
