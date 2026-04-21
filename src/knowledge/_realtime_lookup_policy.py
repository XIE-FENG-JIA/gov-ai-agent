from __future__ import annotations


def parse_gazette_xml(root) -> list[dict]:
    """解析公報 XML，回傳 Record 字典清單。"""
    records: list[dict] = []
    for record_elem in root.iter("Record"):
        rec: dict[str, str] = {}
        for child in record_elem:
            rec[child.tag] = child.text or ""
        records.append(rec)
    return records


def filter_relevant_records(records: list[dict], query: str, keywords: list[str]) -> list[dict]:
    """按關鍵字過濾公報記錄。"""
    if not query or not keywords:
        return records[:10]

    scored: list[tuple[int, dict]] = []
    for rec in records:
        title = rec.get("Title", "")
        category = rec.get("Category", "")
        text = f"{title} {category}"
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scored.append((score, rec))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [rec for _, rec in scored]
