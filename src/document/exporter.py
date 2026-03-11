import logging
import os
import re

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
    FONT_LOG,
    get_platform_fonts,
)

logger = logging.getLogger(__name__)

# 所有已知的公文類型（用於識別標題行）
KNOWN_DOC_TYPES = frozenset([
    "函", "公告", "簽", "書函", "令", "開會通知單",
    "呈", "咨", "會勘通知單", "公務電話紀錄", "手令", "箋函",
])


class DocxExporter:
    """
    將 Markdown 草稿匯出為符合政府標準格式的 Microsoft Word 文件。
    """

    def __init__(self) -> None:
        self.template_engine = TemplateEngine()
        # 跨平台字體：依據作業系統選擇適當的中文字體
        title_font, body_font = get_platform_fonts()
        self._font_title: str | None = title_font
        self._font_body: str | None = body_font

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
        # 替換 Unicode 特殊空格為普通空格
        for ch in [
            '\u00a0',   # NBSP (No-Break Space)
            '\u2000',   # EN Quad
            '\u2001',   # EM Quad
            '\u2002',   # EN Space
            '\u2003',   # EM Space
            '\u2004',   # Three-Per-Em Space
            '\u2005',   # Four-Per-Em Space
            '\u2006',   # Six-Per-Em Space
            '\u2007',   # Figure Space
            '\u2008',   # Punctuation Space
            '\u2009',   # Thin Space
            '\u200a',   # Hair Space
            '\u202f',   # Narrow No-Break Space
            '\u205f',   # Medium Mathematical Space
            '\u3000',   # Ideographic Space（全形空格）
        ]:
            text = text.replace(ch, ' ')
        # 移除零寬度字元和其他不可見 Unicode 字元
        for ch in [
            '\ufeff',   # BOM (Byte Order Mark)
            '\u200b',   # ZWSP (Zero Width Space)
            '\u200c',   # ZWNJ (Zero Width Non-Joiner)
            '\u200d',   # ZWJ (Zero Width Joiner)
            '\u200e',   # LRM (Left-to-Right Mark)
            '\u200f',   # RLM (Right-to-Left Mark)
            '\u00ad',   # Soft Hyphen
            '\u2060',   # Word Joiner
        ]:
            text = text.replace(ch, '')
        return text

    def _set_font(self, run, font_name: str | None = None, size: int = FONT_SIZE_META, bold: bool = False) -> None:
        """設定文字段落的字體、大小和粗體。

        若 font_name 為 None，則不設定字體名稱，交由 Word 使用預設字體。
        """
        run.font.size = Pt(size)
        run.font.bold = bold
        if font_name is not None:
            run.font.name = font_name
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
        """從草稿前 10 行中提取公文類型。

        先精確匹配整行，再嘗試在行中搜尋已知類型關鍵字，
        以處理「# 臺北市政府公告」等格式。
        """
        lines = draft_text.strip().split("\n")
        header_scan_lines = 10

        # 第一遍：精確匹配（清理後整行等於類型名稱）
        for line in lines[:header_scan_lines]:
            clean = self._clean_line(line)
            if clean in KNOWN_DOC_TYPES:
                return clean

        # 第二遍：模糊匹配（行中包含類型關鍵字，優先長名稱）
        # 單字類型（令、呈、咨、函、簽）須出現在行尾才匹配，
        # 避免「茲令各局處」「呈報」等一般文句造成誤判，
        # 但允許「市府內部簽」「行政院令」等標題行正確匹配
        for line in lines[:header_scan_lines]:
            clean = self._clean_line(line)
            for doc_type in sorted(KNOWN_DOC_TYPES, key=len, reverse=True):
                if len(doc_type) == 1:
                    if clean.endswith(doc_type):
                        return doc_type
                    continue
                if doc_type in clean:
                    return doc_type

        return "函"  # 預設公文類型

    def export(self, draft_text: str, output_path: str, qa_report: str | None = None) -> str:
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

        # 解析內容結構（失敗時回退為空結構，產生最小有效 DOCX）
        try:
            sections = self.template_engine.parse_draft(draft_text)
        except Exception as exc:
            logger.warning("草稿解析失敗，產生最小有效文件: %s", exc)
            sections = {}

        # 偵測公文類型（供本文段落標籤使用）
        doc_type = self._extract_doc_type(draft_text)

        # 1. 公文類型標題
        self._write_title(doc, doc_type)

        # 2. 檔頭資訊（機關、受文者等）
        self._write_meta_info(doc, draft_text)

        # 3. 本文（主旨、說明、辦法 — 依文件類型調整標籤）
        self._write_body(doc, sections, doc_type)

        # 4. 附件與參考來源
        self._write_attachments(doc, sections)

        # 5. QA 報告（選用附件）
        if qa_report:
            self._write_qa_report(doc, qa_report)

        # 確保輸出目錄存在
        output_dir = os.path.dirname(output_path)
        if output_dir:
            try:
                os.makedirs(output_dir, exist_ok=True)
            except OSError as exc:
                logger.error("建立輸出目錄失敗（%s）: %s", output_dir, exc)
                raise

        try:
            doc.save(output_path)
        except OSError as exc:
            logger.error("DOCX 儲存失敗（%s）: %s", output_path, exc)
            raise
        return output_path

    def _setup_page(self, doc: Document) -> None:
        """設定 A4 頁面邊距。"""
        section = doc.sections[0]
        section.top_margin = Cm(PAGE_MARGIN_TOP)
        section.bottom_margin = Cm(PAGE_MARGIN_BOTTOM)
        section.left_margin = Cm(PAGE_MARGIN_LEFT)
        section.right_margin = Cm(PAGE_MARGIN_RIGHT)

    def _write_title(self, doc: Document, doc_type: str) -> None:
        """寫入公文類型標題。"""
        p_title = doc.add_paragraph()
        p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p_title.add_run(doc_type)
        self._set_font(run, self._font_title, FONT_SIZE_TITLE, bold=True)

    def _write_meta_info(self, doc: Document, draft_text: str) -> None:
        """寫入檔頭資訊區塊。"""
        lines = draft_text.strip().split("\n")
        for line in lines[1:]:
            clean = self._clean_line(line)
            if not clean:
                continue
            # 遇到本文段落標籤則結束檔頭區塊
            _BODY_START_KEYWORDS = ("主旨", "通話時間", "發話人", "指示事項")
            if clean.startswith("---") or clean.startswith("###"):
                break
            if any(clean.startswith(kw) for kw in _BODY_START_KEYWORDS):
                break
            # 跳過公文類型重複
            if clean in KNOWN_DOC_TYPES:
                continue
            if clean:
                p = doc.add_paragraph()
                run = p.add_run(clean)
                self._set_font(run, self._font_body, FONT_SIZE_META)

        doc.add_paragraph()  # 間距

    def _write_body(self, doc: Document, sections: dict[str, str], doc_type: str = "函") -> None:
        """寫入主旨、說明、辦法等本文段落（依文件類型調整標籤）。"""
        if doc_type == "公告":
            # 公告使用「依據」和「公告事項」，不使用「說明」和「辦法」
            body_order = [("主旨", "subject"), ("依據", "basis"), ("公告事項", "provisions")]
        elif doc_type == "簽":
            # 簽使用「擬辦」而非「辦法」
            body_order = [("主旨", "subject"), ("說明", "explanation"), ("擬辦", "provisions")]
        elif doc_type == "開會通知單":
            body_order = [
                ("主旨", "subject"),
                ("說明", "explanation"),
                ("開會時間", "meeting_time"),
                ("開會地點", "meeting_location"),
                ("議程", "agenda"),
                ("注意事項", "provisions"),
            ]
        elif doc_type == "會勘通知單":
            body_order = [
                ("主旨", "subject"),
                ("說明", "explanation"),
                ("會勘時間", "inspection_time"),
                ("會勘地點", "inspection_location"),
                ("會勘事項", "inspection_items"),
                ("應攜文件", "required_documents"),
                ("應出席單位", "attendees"),
                ("注意事項", "provisions"),
            ]
        elif doc_type == "公務電話紀錄":
            body_order = [
                ("通話時間", "call_time"),
                ("發話人", "caller"),
                ("受話人", "callee"),
                ("主旨", "subject"),
                ("通話摘要", "call_summary"),
                ("說明", "explanation"),
                ("追蹤事項", "follow_up_items"),
                ("紀錄人", "recorder"),
                ("核閱", "reviewer"),
            ]
        elif doc_type == "手令":
            body_order = [
                ("主旨", "subject"),
                ("指示事項", "directive_content"),
                ("說明", "explanation"),
                ("完成期限", "deadline"),
                ("副知", "cc_list"),
            ]
        elif doc_type == "箋函":
            body_order = [
                ("主旨", "subject"),
                ("說明", "explanation"),
                ("正本", "copies_to"),
                ("副本", "cc_copies"),
            ]
        else:
            body_order = [("主旨", "subject"), ("說明", "explanation"), ("辦法", "provisions")]

        for label, key in body_order:
            content = sections.get(key)
            if not content:
                continue

            # 段落標籤
            p_label = doc.add_paragraph()
            run_label = p_label.add_run(f"{label}：")
            self._set_font(run_label, self._font_title, FONT_SIZE_SECTION_LABEL, bold=True)

            # 段落內容
            for line in content.split("\n"):
                clean_content = self._clean_line(line)
                if clean_content:
                    p_content = doc.add_paragraph()
                    p_content.paragraph_format.first_line_indent = Pt(FIRST_LINE_INDENT)
                    run_content = p_content.add_run(clean_content)
                    self._set_font(run_content, self._font_body, FONT_SIZE_BODY)

    def _write_attachments(self, doc: Document, sections: dict[str, str]) -> None:
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
            self._set_font(run_att, self._font_title, FONT_SIZE_BODY, bold=True)

            # 逐行處理，與 _write_body 一致，避免多行內容中
            # 後續行的 markdown 標記（如 "- "）無法被清除
            for line in content.split("\n"):
                clean_content = self._clean_line(line)
                if clean_content:
                    p_content = doc.add_paragraph(clean_content)
                    for run in p_content.runs:
                        self._set_font(run, self._font_body, FONT_SIZE_META)

    def _write_qa_report(self, doc: Document, qa_report: str) -> None:
        """寫入 QA 報告附件頁。"""
        doc.add_page_break()
        p_qa_title = doc.add_paragraph()
        run_qa = p_qa_title.add_run("附件：AI 品質保證報告 (QA Report)")
        self._set_font(run_qa, self._font_title, FONT_SIZE_SECTION_LABEL, bold=True)

        # 清理特殊字元和 Markdown 標記
        clean_qa = self._sanitize_text(qa_report)
        clean_qa = clean_markdown_artifacts(clean_qa)
        p_log = doc.add_paragraph(clean_qa)
        for run in p_log.runs:
            run.font.name = FONT_LOG
            run.font.size = Pt(FONT_SIZE_LOG)
