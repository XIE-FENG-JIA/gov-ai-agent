"""公文用語品質檢查工具。"""

# 口語詞 → 公文用語對照表
INFORMAL_TERMS: dict[str, str] = {
    "然後": "繼而",
    "很多": "多數",
    "可是": "惟",
    "所以": "爰",
    "因為": "緣",
    "雖然": "雖",
    "但是": "惟",
    "而且": "且",
    "一些": "若干",
    "大概": "約略",
    "馬上": "即刻",
    "沒有": "未有",
    "已經": "業已",
    "還是": "仍",
    "如果": "倘",
    "希望": "冀",
    "告訴": "函知",
    "要求": "請",
    "處理": "辦理",
    "東西": "事物",
}

# 贅詞（可省略的冗餘用語）
REDUNDANT_PHRASES: dict[str, str] = {
    "進行研究": "研究",
    "進行調查": "調查",
    "進行檢查": "檢查",
    "做出決定": "決定",
    "加以處理": "處理",
    "予以核准": "核准",
    "有關於": "關於",
    "針對於": "針對",
}


def check_language(text: str) -> list[dict]:
    """
    檢查公文文字中的口語詞和贅詞。

    Returns:
        list of {"type": "informal"|"redundant", "found": str, "suggest": str, "count": int}
    """
    results = []
    for informal, formal in INFORMAL_TERMS.items():
        count = text.count(informal)
        if count > 0:
            results.append({
                "type": "informal",
                "found": informal,
                "suggest": formal,
                "count": count,
            })
    for redundant, concise in REDUNDANT_PHRASES.items():
        count = text.count(redundant)
        if count > 0:
            results.append({
                "type": "redundant",
                "found": redundant,
                "suggest": concise,
                "count": count,
            })
    return sorted(results, key=lambda x: -x["count"])
