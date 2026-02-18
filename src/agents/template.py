import logging
import re
import os
from datetime import date
from typing import Dict, List, Optional
from jinja2 import Environment, FileSystemLoader
from src.core.models import PublicDocRequirement
from src.core.constants import CHINESE_NUMBERS, MAX_CHINESE_NUMBER

logger = logging.getLogger(__name__)

def clean_markdown_artifacts(text: Optional[str]) -> str:
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
    
    # 移除 markdown 連結標記 [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    
    # 移除多餘的分隔線
    text = re.sub(r'^---+\s*$', '', text, flags=re.MULTILINE)
    
    # 移除「捺印處」等不應出現的文字
    text = re.sub(r'捺印處', '', text)
    
    # 清理多餘空行
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()

def renumber_provisions(text: Optional[str]) -> str:
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
        stripped_no_num = re.sub(r'^[\d一二三四五六七八九十]+[、.)\.]?\s*', '', stripped)
        should_skip = False
        for pattern in skip_patterns:
            if re.match(pattern, stripped_no_num):
                should_skip = True
                result.append(stripped_no_num)
                break

        if should_skip:
            continue
        
        # 檢測是否為主編號項目（數字、中文數字開頭）
        main_match = re.match(r'^[\d一二三四五六七八九十]+[、.)\.]?\s*(.+)', stripped)
        # 檢測是否為子編號項目（括號數字開頭）
        sub_match = re.match(r'^[\(（][\d一二三四五六七八九十]+[\)）][、.]?\s*(.+)', stripped)
        
        if sub_match:
            # 子項目
            sub_counter += 1
            content = sub_match.group(1)
            result.append(f"（{CHINESE_NUMBERS[sub_counter-1] if sub_counter <= MAX_CHINESE_NUMBER else sub_counter}）{content}")
        elif main_match:
            # 主項目
            main_counter += 1
            sub_counter = 0  # 重置子編號
            content = main_match.group(1)
            result.append(f"{CHINESE_NUMBERS[main_counter-1] if main_counter <= MAX_CHINESE_NUMBER else main_counter}、{content}")
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


class TemplateEngine:
    """
    模板引擎：使用 Jinja2 模板結構化並標準化公文內容。
    """

    def __init__(self):
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

    def parse_draft(self, draft_text: str) -> Dict[str, str]:
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
            "references": ""
        }
        
        # Internal state
        current_section = None
        buffer = {
            "subject": [],
            "explanation": [],
            "basis": [], # 依據
            "provisions": [],
            "attachments": [],
            "references": []
        }
        
        # Normalize
        lines = draft_text.replace('\r\n', '\n').split('\n')
        
        # 辨識段落標題的輔助函式
        def detect_header(line: str) -> Optional[str]:
            """偵測公文段落標題，回傳對應的 section 鍵值。"""
            clean = line.strip().replace('#', '').strip()
            if clean.startswith("主旨"):
                return "subject"
            if clean.startswith("說明"):
                return "explanation"
            if clean.startswith("依據"):
                return "basis"
            if (clean.startswith("辦法")
                    or clean.startswith("公告事項")
                    or "辦法/公告事項" in clean
                    or clean.startswith("擬辦")):
                return "provisions"
            if clean.startswith("附件"):
                return "attachments"
            if clean.startswith("參考來源"):
                return "references"
            return None

        for line in lines:
            new_section = detect_header(line)
            if new_section:
                current_section = new_section
                parts = line.split('：', 1) if '：' in line else line.split(':', 1)
                if len(parts) > 1 and parts[1].strip():
                     buffer[current_section].append(parts[1].strip())
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

        return sections

    def _parse_list_items(self, text: str) -> List[str]:
        """將文字區塊轉換為清單項目，並移除既有的編號。"""
        items = []
        if not text:
            return items
            
        for line in text.split('\n'):
            clean = line.strip()
            if not clean:
                continue
            clean = re.sub(r"^\s*(?:\(?[\d\u4e00-\u9fa5]+[.)、])\s*", "", clean)
            items.append(clean)
        return items

    def apply_template(self, requirement: PublicDocRequirement, sections: Dict[str, str]) -> str:
        """
        使用 Jinja2 將內容渲染為標準 Markdown 模板格式。
        """
        today = date.today()
        roc_year = today.year - 1911
        
        if requirement.doc_type == "公告":
            template_name = "announcement.j2"
        elif requirement.doc_type == "簽":
            template_name = "sign.j2"
        else:
            template_name = "han.j2" # Default
            
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
            "urgency": requirement.urgency or "普通",
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
            "attachments": requirement.attachments or [],
        }

        try:
            output = template.render(**context)
        except Exception as e:
            logger.warning("Jinja2 模板渲染失敗: %s，使用備用格式", e)
            return self._fallback_apply(requirement, sections)

        if sections.get("references"):
            output += "\n\n### 參考來源\n" + sections["references"]

        return output

    def _fallback_apply(self, requirement: PublicDocRequirement, sections: Dict[str, str]) -> str:
        """備用的簡易字串格式化方法。"""
        subject = sections.get("subject") or requirement.subject
        explanation = sections.get("explanation") or requirement.reason or ""
        provisions = sections.get("provisions") or ""
        
        if requirement.action_items and not explanation:
            explanation = "\n".join([f"{i+1}、{item}" for i, item in enumerate(requirement.action_items)])
        
        att_text = ""
        if requirement.attachments:
            att_text = "附件：\n" + "\n".join([f"- {item}" for item in requirement.attachments])

        template = f"""# {requirement.doc_type}

**機關**：{requirement.sender}
**受文者**：{requirement.receiver}
**速別**：{requirement.urgency}
**密等及解密條件或保密期限**：普通

---

### 主旨
{subject}

### 說明
{explanation}

### 辦法
{provisions}

---
{att_text}
"""
        return template.replace("### 辦法\n\n", "")