import logging
import re
from typing import Dict, Optional

from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from src.agents.template import TemplateEngine, clean_markdown_artifacts
from src.core.constants import (
    FONT_SIZE_TITLE,
    FONT_SIZE_SECTION_LABEL,
    FONT_SIZE_BODY,
    FONT_SIZE_META,
    FONT_SIZE_LOG,
    PAGE_MARGIN_TOP,
    PAGE_MARGIN_BOTTOM,
    PAGE_MARGIN_LEFT,
    PAGE_MARGIN_RIGHT,
    FIRST_LINE_INDENT,
    FONT_TITLE,
    FONT_BODY,
    FONT_LOG,
)

logger = logging.getLogger(__name__)

# 所有已知的公文類型（用於識別標題行）
KNOWN_DOC_TYPES = frozenset(["函", "公告", "簽", "書函", "令", "開會通知單", "通知"])


class DocxExporter:
    """
    將 Markdown 草稿匯出為符合政府標準格式的 Microsoft Word 文件。
    """

    def __init__(self):
        self.template_engine = TemplateEngine()

    @staticmethod
    def _sanitize_text(text: str) -> str:
        """
        清理文字中可能導致 Word 文件損壞的特殊字元。

        移除 XML 不允許的控制字元（保留換行和 Tab），
        並替換可能導致問題的 Unicode 字元。
        """
        if not text:
            return ""
        # 移除 XML 1.0 不允許的控制字元（0x00-0x08, 0x0B-0x0C, 0x0E-0x1F）
        # 保留 0x09 (Tab), 0x0A (LF), 0x0D (CR)
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
        # 移除 Unicode 替代碼位（surrogate pairs，可能出現在錯誤的 LLM 輸出中）
        text = re.sub(r'[\ud800-\udfff]', '', text)
        # 移除零寬度字元
        text = text.replace('\ufeff', '').replace('\u200b', '')
        return text

    def _set_font(self, run, font_name: str = FONT_BODY, size: int = FONT_SIZE_META, bold: bool = False) -> None:
        """設定文字段落的字體、大小和粗體。"""
        run.font.name = font_name
        run.font.size = Pt(size)
        run.font.bold = bold
        # 確保 rPr 元素存在後再設定東亞字體
        rPr = run._element.get_or_add_rPr()
        rFonts = rPr.get_or_add_rFonts()
        rFonts.set(qn("w:eastAsia"), font_name)

    def _clean_line(self, line: str) -> str:
        """清理單行文字中的 Markdown 標記和特殊字元。"""
        line = self._sanitize_text(line)
        line = clean_markdown_artifacts(line)
        # 額外清理：移除行首的 Markdown 標記殘留
        line = re.sub(r"^[#\*\-]+\s*", "", line)
        return line.strip()

    def _extract_doc_type(self, draft_text: str) -> str:
        """從草稿前 5 行中提取公文類型。"""
        lines = draft_text.strip().split("\n")
        header_scan_lines = 5
        for line in lines[:header_scan_lines]:
            clean = self._clean_line(line)
            if clean in KNOWN_DOC_TYPES:
                return clean
        return "函"  # 預設公文類型

    def export(self, draft_text: str, output_path: str, qa_report: Optional[str] = None) -> str:
        """將 Markdown 草稿轉換為 docx 檔案。"""
        # 防護空值輸入
        if not draft_text or not draft_text.strip():
            logger.warning("匯出收到空的草稿，產生空白文件")
            draft_text = "（無內容）"

        # 先清理整體文字和特殊字元
        draft_text = self._sanitize_text(draft_text)
        draft_text = clean_markdown_artifacts(draft_text)

        doc = Document()
        self._setup_page(doc)

        # 解析內容結構
        sections = self.template_engine.parse_draft(draft_text)

        # 1. 公文類型標題
        self._write_title(doc, draft_text)

        # 2. 檔頭資訊（機關、受文者等）
        self._write_meta_info(doc, draft_text)

        # 3. 本文（主旨、說明、辦法）
        self._write_body(doc, sections)

        # 4. 附件與參考來源
        self._write_attachments(doc, sections)

        # 5. QA 報告（選用附件）
        if qa_report:
            self._write_qa_report(doc, qa_report)

        doc.save(output_path)
        return output_path

    def _setup_page(self, doc: Document) -> None:
        """設定 A4 頁面邊距。"""
        section = doc.sections[0]
        section.top_margin = Cm(PAGE_MARGIN_TOP)
        section.bottom_margin = Cm(PAGE_MARGIN_BOTTOM)
        section.left_margin = Cm(PAGE_MARGIN_LEFT)
        section.right_margin = Cm(PAGE_MARGIN_RIGHT)

    def _write_title(self, doc: Document, draft_text: str) -> None:
        """寫入公文類型標題。"""
        doc_type = self._extract_doc_type(draft_text)
        p_title = doc.add_paragraph()
        p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p_title.add_run(doc_type)
        self._set_font(run, FONT_TITLE, FONT_SIZE_TITLE, bold=True)

    def _write_meta_info(self, doc: Document, draft_text: str) -> None:
        """寫入檔頭資訊區塊。"""
        lines = draft_text.strip().split("\n")
        for line in lines[1:]:
            clean = self._clean_line(line)
            if not clean:
                continue
            # 遇到主旨段落則結束檔頭區塊
            if clean.startswith("---") or clean.startswith("###") or clean.startswith("主旨"):
                break
            # 跳過公文類型重複
            if clean in KNOWN_DOC_TYPES:
                continue
            if clean:
                p = doc.add_paragraph()
                run = p.add_run(clean)
                self._set_font(run, FONT_BODY, FONT_SIZE_META)

        doc.add_paragraph()  # 間距

    def _write_body(self, doc: Document, sections: Dict[str, str]) -> None:
        """寫入主旨、說明、辦法等本文段落。"""
        body_order = [("主旨", "subject"), ("說明", "explanation"), ("辦法", "provisions")]

        for label, key in body_order:
            content = sections.get(key)
            if not content:
                continue

            # 段落標籤
            p_label = doc.add_paragraph()
            run_label = p_label.add_run(f"{label}：")
            self._set_font(run_label, FONT_TITLE, FONT_SIZE_SECTION_LABEL, bold=True)

            # 段落內容
            for line in content.split("\n"):
                clean_content = self._clean_line(line)
                if clean_content:
                    p_content = doc.add_paragraph()
                    p_content.paragraph_format.first_line_indent = Pt(FIRST_LINE_INDENT)
                    run_content = p_content.add_run(clean_content)
                    self._set_font(run_content, FONT_BODY, FONT_SIZE_BODY)

    def _write_attachments(self, doc: Document, sections: Dict[str, str]) -> None:
        """寫入附件和參考來源。"""
        attachment_keys = [
            ("attachments", "附件："),
            ("references", "參考來源："),
        ]

        for key, label in attachment_keys:
            content = sections.get(key)
            if not content:
                continue

            doc.add_paragraph()
            p_att = doc.add_paragraph()
            run_att = p_att.add_run(label)
            self._set_font(run_att, FONT_TITLE, FONT_SIZE_BODY, bold=True)

            clean_content = self._clean_line(content)
            p_content = doc.add_paragraph(clean_content)
            for run in p_content.runs:
                self._set_font(run, FONT_BODY, FONT_SIZE_META)

    def _write_qa_report(self, doc: Document, qa_report: str) -> None:
        """寫入 QA 報告附件頁。"""
        doc.add_page_break()
        p_qa_title = doc.add_paragraph()
        run_qa = p_qa_title.add_run("附件：AI 品質保證報告 (QA Report)")
        self._set_font(run_qa, FONT_TITLE, FONT_SIZE_SECTION_LABEL, bold=True)

        # 清理特殊字元和 Markdown 標記
        clean_qa = self._sanitize_text(qa_report)
        clean_qa = clean_markdown_artifacts(clean_qa)
        p_log = doc.add_paragraph(clean_qa)
        for run in p_log.runs:
            run.font.name = FONT_LOG
            run.font.size = Pt(FONT_SIZE_LOG)
