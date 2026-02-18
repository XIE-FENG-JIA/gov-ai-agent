import json
import logging
import os
import re
from datetime import date
from typing import List

logger = logging.getLogger(__name__)

class ValidatorRegistry:
    """自訂驗證函式的註冊表。"""

    def __init__(self):
        # 載入術語字典
        term_path = os.path.join(os.path.dirname(__file__), "..", "..", "kb_data", "terminology", "dictionary.json")
        try:
            with open(term_path, 'r', encoding='utf-8') as f:
                self.terms = json.load(f)
        except Exception as e:
            logger.debug("Terminology dict not found (optional): %s", e)
            self.terms = {}

    def check_date_logic(self, draft_text: str, **kwargs) -> List[str]:
        """檢查文件中的日期是否合理（例如不在遠過去）。"""
        errors = []
        today = date.today()

        roc_matches = re.findall(r"(\d{2,3})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", draft_text)
        for year, month, day in roc_matches:
            try:
                ad_year = int(year) + 1911
                doc_date = date(ad_year, int(month), int(day))
                if (today.year - doc_date.year) > 2:
                    errors.append(f"日期可能過舊: {year}年{month}月{day}日（距今超過 2 年）")
                elif doc_date.year - today.year > 1:
                    errors.append(f"日期可能有誤: {year}年{month}月{day}日（超過未來 1 年）")
            except ValueError:
                errors.append(f"發現無效日期格式: {year}年{month}月{day}日")

        return errors

    def check_attachment_consistency(self, draft_text: str, **kwargs) -> List[str]:
        """檢查附件提及與附件段落是否一致。"""
        errors = []
        mentions = len(re.findall(r"檢附|附件|附表", draft_text))
        has_attachment_section = "附件：" in draft_text or "附件:" in draft_text
        
        if mentions > 0 and not has_attachment_section:
            errors.append("說明欄位提及了附件，但文末缺少「附件」段落。")
            
        return errors

    def check_citation_format(self, draft_text: str, **kwargs) -> List[str]:
        """檢查法規引用是否使用正確的書名號格式（例如《勞動基準法》）。"""
        errors = []
        # Find "依據..." pattern
        # Look for patterns that look like law citations but miss book title marks
        # e.g. "依據勞動基準法" (Bad) vs "依據《勞動基準法》" (Good)
        
        # Heuristic: "依據" followed by Chinese characters ending in "法" or "條例" without 《》
        # This regex is tricky, let's try to find "依據" and see if followed by non-symbol chars ending in 法/條例
        matches = re.finditer(r"依據\s*([^《》\n,。]+?(?:法|條例|細則|辦法|準則))", draft_text)
        
        for m in matches:
            citation = m.group(1).strip()
            # If it's a very short generic word like "法", skip
            if len(citation) > 1:
                errors.append(f"法規引用格式建議：請使用書名號，例如《{citation}》。")
        
        return errors

    def check_doc_integrity(self, draft_text: str, **kwargs) -> List[str]:
        """檢查是否缺少重要的佔位符號欄位。"""
        errors = []
        if "______號" in draft_text:
            errors.append("發文字號尚未填寫 (仍為 placeholder)。")
        
        # Check standard headers existence
        headers = ["機關", "受文者", "速別", "發文日期"]
        for h in headers:
            if f"**{h}**" not in draft_text:
                errors.append(f"缺少標準檔頭欄位：{h}")
                
        return errors

validator_registry = ValidatorRegistry()
