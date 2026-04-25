import json
import logging
import os
import re
from datetime import date

from src.agents.validator_citations import (
    check_citation_integrity as _check_citation_integrity,
    check_citation_level as _check_citation_level,
    check_evidence_presence as _check_evidence_presence,
)
from src.agents.validator_terms import COLLOQUIAL_PATTERNS, OUTDATED_AGENCY_MAP

logger = logging.getLogger(__name__)


def _issue(
    description: str,
    location: str = "文件結構",
    suggestion: str | None = None,
) -> dict:
    """建立結構化驗證問題字典，供 auditor 與 ReviewIssue 使用。"""
    return {"description": description, "location": location, "suggestion": suggestion}


class ValidatorRegistry:
    """自訂驗證函式的註冊表。"""

    def __init__(self) -> None:
        # 載入術語字典
        term_path = os.path.join(os.path.dirname(__file__), "..", "..", "kb_data", "terminology", "dictionary.json")
        try:
            with open(term_path, 'r', encoding='utf-8') as f:
                self.terms = json.load(f)
        except (OSError, json.JSONDecodeError, ValueError) as e:
            self.terms = {}

    def check_date_logic(self, draft_text: str, **kwargs) -> list[dict]:
        """檢查文件中的日期是否合理（例如不在遠過去）。"""
        errors: list[dict] = []
        today = date.today()

        roc_matches = re.findall(r"(?<!\d)(\d{2,3})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", draft_text)
        for year, month, day in roc_matches:
            roc_year = int(year)
            m, d = int(month), int(day)
            date_str = f"{year}年{month}月{day}日"
            loc = f"日期「{date_str}」"

            # 民國年份基本範圍檢查（1-200，對應西元 1912-2111）
            if roc_year < 1:
                errors.append(_issue(
                    f"日期可能過舊: {date_str}（民國年份須 >= 1）",
                    loc, "請確認民國年份是否正確，民國年份應介於 1 至 200 之間",
                ))
                continue
            if roc_year > 200:
                errors.append(_issue(
                    f"日期可能有誤: {date_str}（民國年份超過 200）",
                    loc, "請確認民國年份是否正確，民國年份應介於 1 至 200 之間",
                ))
                continue

            # 月份、日期基本合法性
            if m < 1 or m > 12:
                errors.append(_issue(
                    f"發現無效日期格式: {date_str}",
                    loc, f"月份「{month}」不合法，請修正為 1 至 12 之間的數值",
                ))
                continue
            if d < 1 or d > 31:
                errors.append(_issue(
                    f"發現無效日期格式: {date_str}",
                    loc, f"日期「{day}」不合法，請修正為該月份的有效日期",
                ))
                continue

            try:
                ad_year = roc_year + 1911
                doc_date = date(ad_year, m, d)
                current_roc = today.year - 1911
                if (today.year - doc_date.year) > 2:
                    errors.append(_issue(
                        f"日期可能過舊: {date_str}（距今超過 2 年）",
                        loc, f"請確認日期是否應為民國 {current_roc} 年前後",
                    ))
                elif doc_date.year - today.year > 1:
                    errors.append(_issue(
                        f"日期可能有誤: {date_str}（超過未來 1 年）",
                        loc, f"請確認日期是否應為民國 {current_roc} 年前後",
                    ))
            except ValueError:
                errors.append(_issue(
                    f"發現無效日期格式: {date_str}",
                    loc, f"「{date_str}」不是有效的日曆日期，請修正日期數值",
                ))

        return errors

    def check_attachment_consistency(self, draft_text: str, **kwargs) -> list[dict]:
        """檢查附件提及與附件段落是否一致，含變體偵測與編號連續性。"""
        errors: list[dict] = []
        # 擴展正則匹配：加入「檢附如附件」「如附表」「如附件」等變體
        mentions = len(re.findall(r"檢附|附件|附表|如附件|如附表|檢附如附件", draft_text))
        has_attachment_section = "附件：" in draft_text or "附件:" in draft_text

        if mentions > 0 and not has_attachment_section:
            errors.append(_issue(
                "說明欄位提及了附件，但文末缺少「附件」段落。",
                "附件段落",
                "在文末新增「附件：」段落，列出所有附件名稱與份數",
            ))

        # 檢查附件編號連續性（附件一、附件二...不應跳號）
        cn_nums = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
                   "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
        att_cn = re.findall(r"附件([一二三四五六七八九十])", draft_text)
        if att_cn:
            found_nums = sorted(set(cn_nums[c] for c in att_cn if c in cn_nums))
            for i, num in enumerate(found_nums):
                expected = i + 1
                if num != expected:
                    missing_cn = "一二三四五六七八九十"[expected - 1]
                    errors.append(_issue(
                        f"附件編號不連續：缺少附件{missing_cn}（跳號）。",
                        "附件編號",
                        f"補充「附件{missing_cn}」或將後續附件編號依序前移",
                    ))
                    break

        return errors

    def check_citation_format(self, draft_text: str, **kwargs) -> list[dict]:
        """檢查法規引用是否使用正確的書名號格式，並區分法規類型。"""
        errors: list[dict] = []

        # 法規類型後綴與對應說明
        law_suffixes = ["法", "條例", "細則", "辦法", "準則", "規則", "規程", "綱要"]
        suffix_pattern = "|".join(law_suffixes)

        # 偵測缺少書名號的法規引用
        matches = re.finditer(
            rf"依據\s*([^《》\n,，。]+?(?:{suffix_pattern}))", draft_text
        )

        _MAX_CITATION_WARNINGS = 5
        for m in matches:
            citation = m.group(1).strip()
            if 1 < len(citation) < 30:
                errors.append(_issue(
                    f"法規引用格式建議：請使用書名號，例如《{citation}》。",
                    f"引用「{citation}」",
                    f"將「{citation}」改為「《{citation}》」",
                ))
            if len(errors) >= _MAX_CITATION_WARNINGS:
                errors.append(_issue("（其餘引用格式問題已省略）", "引用格式"))
                break

        # 檢查書名號內的法規名稱是否完整（至少包含法規類型後綴且名稱夠長）
        book_citations = re.findall(r"《([^》]+)》", draft_text)
        for citation in book_citations:
            # 書名號內文字過短（少於 3 字）可能不完整
            if len(citation) < 3:
                errors.append(_issue(
                    f"書名號內容「{citation}」可能不完整，請確認是否為正式法規全名。",
                    f"引用「《{citation}》」",
                    f"將「《{citation}》」補充為法規全名（如《{citation}○○法》）",
                ))

        return errors

    def check_doc_integrity(self, draft_text: str, **kwargs) -> list[dict]:
        """檢查是否缺少重要的佔位符號欄位。"""
        errors: list[dict] = []
        if "______號" in draft_text:
            errors.append(_issue(
                "發文字號尚未填寫 (仍為 placeholder)。",
                "發文字號",
                "將「______號」替換為正式發文字號（如「府環衛字第 1140001234 號」）",
            ))

        # Check standard headers existence
        headers = ["機關", "受文者", "速別", "發文日期"]
        header_examples = {
            "機關": "**機關**：○○市政府○○局",
            "受文者": "**受文者**：○○單位",
            "速別": "**速別**：普通件",
            "發文日期": "**發文日期**：中華民國○○○年○○月○○日",
        }
        for h in headers:
            if f"**{h}**" not in draft_text:
                errors.append(_issue(
                    f"缺少標準檔頭欄位：{h}",
                    "檔頭欄位",
                    f"在檔頭區域新增「{header_examples[h]}」",
                ))

        return errors

    def check_citation_level(self, draft_text: str, **kwargs) -> list[dict]:
        """檢查引用等級合規性：Level A 權威來源、待補依據標記。"""
        return _check_citation_level(draft_text, _issue)

    def check_evidence_presence(self, draft_text: str, **kwargs) -> list[dict]:
        """檢查草稿是否包含至少一個 evidence-backed 引用。"""
        return _check_evidence_presence(draft_text, _issue)

    def check_citation_integrity(self, draft_text: str, **kwargs) -> list[dict]:
        """檢查引用完整性：找出孤兒引用與未使用定義。"""
        return _check_citation_integrity(draft_text, _issue)

    _OUTDATED_AGENCY_MAP = OUTDATED_AGENCY_MAP
    _COLLOQUIAL_PATTERNS = COLLOQUIAL_PATTERNS

    # 單字語氣詞在句尾出現的上下文：後接中文標點、空白或文末
    _CLAUSE_END_RE = re.compile(r"(?=[，。、；：！？」）\s\n]|$)")

    def check_colloquial_language(self, draft_text: str, **kwargs) -> list[dict]:
        """檢查草稿中是否含有口語化用詞，公文應使用正式書面語。

        單字語氣詞（啦、喔、嗎、吧、耶、欸、哦）僅在後接標點或文末時
        才視為口語語氣詞，避免「吧台」「嗎啡」「啦啦隊」「耶穌」等誤判。
        """
        errors: list[dict] = []
        for pattern, replacement in self._COLLOQUIAL_PATTERNS:
            if len(pattern) == 1:
                # 單字語氣詞：僅匹配句尾位置（後接標點/空白/文末）
                if not re.search(re.escape(pattern) + self._CLAUSE_END_RE.pattern, draft_text):
                    continue
            else:
                if pattern not in draft_text:
                    continue
            if replacement:
                errors.append(_issue(
                    f"口語化用詞：「{pattern}」建議改為「{replacement}」。",
                    f"用詞「{pattern}」",
                    f"將「{pattern}」改為「{replacement}」",
                ))
            else:
                errors.append(_issue(
                    f"口語化語氣詞：「{pattern}」不應出現在正式公文中。",
                    f"語氣詞「{pattern}」",
                    f"刪除「{pattern}」",
                ))
        return errors

    def check_terminology(self, draft_text: str, **kwargs) -> list[dict]:
        """檢查草稿中是否使用了過時的機關名稱，提供更正建議。

        長名優先：「內政部營建署」已匹配時，不再重複報告「營建署」。
        """
        errors: list[dict] = []
        # 依名稱長度降序處理，確保長名優先匹配
        sorted_entries = sorted(
            self._OUTDATED_AGENCY_MAP.items(),
            key=lambda x: len(x[0]),
            reverse=True,
        )
        matched_names: list[str] = []
        for old_name, new_name in sorted_entries:
            if old_name not in draft_text:
                continue
            # 若此短名是某個已匹配長名的子字串，跳過以避免重複報告
            if any(old_name in longer for longer in matched_names):
                continue
            matched_names.append(old_name)
            errors.append(_issue(
                f"術語更新建議：「{old_name}」已更名為「{new_name}」，請更新用語。",
                f"機關名稱「{old_name}」",
                f"將「{old_name}」改為「{new_name}」",
            ))
        return errors


validator_registry = ValidatorRegistry()
