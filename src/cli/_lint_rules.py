"""公文 lint 規則常數與純函式（無 CLI 依賴）。"""
import re

_INFORMAL_TERMS = {
    "所以": "爰此",
    "但是": "惟",
    "而且": "且",
    "因為": "因",
    "可是": "然",
    "還有": "另",
    "已經": "業已",
    "馬上": "即刻",
    "大概": "約",
    "一定要": "應",
    "以後": "嗣後",
    "不過": "惟",
    "同時": "並",
    "為了": "為",
    "沒有": "無",
    "快點": "儘速",
    "先前": "前",
    "有些": "部分",
}

_REQUIRED_SECTIONS = ["主旨", "說明"]

_SUBJECT_CLOSINGS = [
    "查照", "照辦", "鑒核", "核示", "遵照辦理",
    "辦理見復", "備查", "鑒察", "核備",
]

_FORMAL_DOC_INDICATOR = "受文者"

_ATTACHMENT_KEYWORDS = ("附件", "附表", "附圖")

_OFFICIAL_TITLE_RE = re.compile(
    r"(院長|副院長|部長|副部長|局長|副局長|處長|副處長|廳長|副廳長|"
    r"署長|副署長|主任委員|副主任委員|委員長|副委員長|秘書長|副秘書長|"
    r"科長|副科長|課長|主席|市長|縣長|鄉長|鎮長|所長|副所長|校長|副校長|"
    r"首長)[　 ]*[\u4e00-\u9fff]{2,4}"
)

_ATTACHMENT_VALID_PATTERNS = [
    re.compile(r"附件[\d一二三四五六七八九十百]+"),
    re.compile(r"附件\s*共\s*\d+\s*件"),
    re.compile(r"共\s*\d+\s*件"),
    re.compile(r"附件清單"),
    re.compile(r"如附"),
    re.compile(r"附[表圖][\d一二三四五六七八九十]+"),
    re.compile(r"附件\d+份"),
    re.compile(r"附[件表圖]\s*\d+份"),
]


def _check_speed_level(text: str) -> list[dict]:
    """含「受文者」的外發函文若缺少「速別」標示則回報 issue。"""
    if _FORMAL_DOC_INDICATOR in text and "速別" not in text:
        return [{
            "line": 0,
            "category": "缺少速別",
            "detail": "函文含「受文者」但缺少「速別」標示（普通件／速件／最速件）",
        }]
    return []


def _check_subject_closing(text: str) -> list[dict]:
    """外發函文的「主旨」段落宜以正式結尾語收尾。"""
    if _FORMAL_DOC_INDICATOR not in text:
        return []

    lines = text.split("\n")
    subject_lines: list[str] = []
    in_subject = False
    _NEXT_SECTION_KEYWORDS = ("說明", "公告事項", "依據", "正本", "副本", "擬辦", "附件")

    for line in lines:
        stripped = line.strip()
        if "主旨" in stripped and ("：" in stripped or ":" in stripped):
            in_subject = True
            subject_lines.append(stripped)
            continue
        if in_subject:
            if stripped and any(
                kw in stripped and ("：" in stripped or ":" in stripped)
                for kw in _NEXT_SECTION_KEYWORDS
            ):
                break
            if stripped:
                subject_lines.append(stripped)

    if not subject_lines:
        return []

    subject_text = " ".join(subject_lines)
    if not any(closing in subject_text for closing in _SUBJECT_CLOSINGS):
        return [{
            "line": 0,
            "category": "主旨結尾",
            "detail": "函文主旨宜以「請　查照」「請　照辦」「請　鑒核」等結尾語收尾",
        }]
    return []


def _check_main_copy(text: str) -> list[dict]:
    """含「受文者」的外發函文應有「正本：」欄位。"""
    if _FORMAL_DOC_INDICATOR not in text:
        return []
    if "正本" not in text:
        return [{
            "line": 0,
            "category": "缺少正本欄",
            "detail": "正式外發函文應填列「正本：」欄位，逐一書明收受機關全銜",
        }]
    return []


def _check_attachment_numbering(text: str) -> list[dict]:
    """文中提及附件但未標明件數時回報 issue。"""
    has_attachment = any(kw in text for kw in _ATTACHMENT_KEYWORDS)
    if not has_attachment:
        return []
    for pattern in _ATTACHMENT_VALID_PATTERNS:
        if pattern.search(text):
            return []
    return [{
        "line": 0,
        "category": "附件件數",
        "detail": "文中提及附件，請標明件數（如「附件1份」「共2件」「如附件清單」）",
    }]


def _check_doc_number(text: str) -> list[dict]:
    """正式外發公文含「受文者」但缺少發文字號時回報 issue。"""
    if _FORMAL_DOC_INDICATOR in text and "字號" not in text and "字第" not in text:
        return [{
            "line": 0,
            "category": "缺少字號",
            "detail": "正式公文應標示發文字號（格式：XX字第XXXXXXXXXX號）",
        }]
    return []


def _check_seal_format(text: str) -> list[dict]:
    """正式外發函文應有機關首長職銜署名欄位。"""
    if _FORMAL_DOC_INDICATOR not in text:
        return []
    if _OFFICIAL_TITLE_RE.search(text):
        return []
    return [{
        "line": 0,
        "category": "用印格式",
        "detail": "正式外發函文應有機關首長職銜署名（如「局長　王小明」），請確認用印欄位是否完整",
    }]


def _run_lint(text: str) -> list[dict]:
    """對公文純文字內容執行 lint 檢查，回傳 issue 清單。

    每個 issue 為 dict，含 ``line``（行號，0 = 全文）、``category``、``detail``。
    此函式不依賴檔案 I/O，可直接被其他模組（如 generate）呼叫。
    """
    lines = text.split("\n")
    issues: list[dict] = []

    for i, line in enumerate(lines, 1):
        for informal, formal in _INFORMAL_TERMS.items():
            if informal in line:
                issues.append({
                    "line": i,
                    "category": "口語化用詞",
                    "detail": f"「{informal}」建議改為「{formal}」",
                })

    for section in _REQUIRED_SECTIONS:
        if section not in text:
            issues.append({
                "line": 0,
                "category": "缺少段落",
                "detail": f"缺少「{section}」段落",
            })

    punctuations_used = set()
    for line in lines:
        stripped = line.strip()
        if stripped and stripped[-1] in ("。", "；", ".", "："):
            punctuations_used.add(stripped[-1])
    if len(punctuations_used) > 1:
        issues.append({
            "line": 0,
            "category": "標點不一致",
            "detail": f"句末混用多種標點：{'、'.join(sorted(punctuations_used))}",
        })

    issues.extend(_check_speed_level(text))
    issues.extend(_check_subject_closing(text))
    issues.extend(_check_doc_number(text))
    issues.extend(_check_main_copy(text))
    issues.extend(_check_attachment_numbering(text))
    issues.extend(_check_seal_format(text))

    return issues
