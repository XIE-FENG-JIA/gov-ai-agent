import logging
import os
import re

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: F401
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

from src.agents.template import TemplateEngine, clean_markdown_artifacts
from src.core.constants import (
    CHINESE_NUMBERS,
    FIRST_LINE_INDENT,  # noqa: F401
    FONT_LOG,  # noqa: F401
    FONT_SIZE_BODY,
    FONT_SIZE_LOG,  # noqa: F401
    FONT_SIZE_META,
    FONT_SIZE_SECTION_LABEL,
    FONT_SIZE_TITLE,
    PAGE_MARGIN_BOTTOM,
    PAGE_MARGIN_LEFT,
    PAGE_MARGIN_RIGHT,
    PAGE_MARGIN_TOP,
    STRICT_FONT_SIZE_BODY,
    STRICT_FONT_SIZE_META,
    STRICT_FONT_SIZE_SECTION_LABEL,
    STRICT_FONT_SIZE_TITLE,
    STRICT_LINE_SPACING,
    STRICT_PAGE_MARGIN,
    STRICT_SPACE_AFTER_LINES,
    STRICT_SPACE_BEFORE_LINES,
    get_platform_fonts,
)
from src.document.citation_metadata import build_citation_export_metadata
from src.document.exporter._text_utils import auto_number as _auto_number_fn
from src.document.exporter._text_utils import sanitize_text as _sanitize_text_fn
from src.document.exporter._custom_properties import (
    CONTENT_TYPES_NS,
    CONTENT_TYPES_XML_PATH,
    CUSTOM_PROPERTIES_NS,
    CUSTOM_PROPERTIES_XML_PATH,
    CUSTOM_PROPERTY_CONTENT_TYPE,
    CUSTOM_PROPERTY_FMTID,
    CUSTOM_PROPERTY_REL_TYPE,
    DOC_PROPS_VT_NS,
    PACKAGE_RELS_NS,
    PACKAGE_RELS_XML_PATH,
    write_custom_properties,
)
from src.document.exporter._sections import (
    write_attachments,
    write_body,
    write_meta_info,
    write_qa_report,
    write_title,
)

logger = logging.getLogger(__name__)

KNOWN_DOC_TYPES = frozenset(
    [
        "函",
        "公告",
        "簽",
        "書函",
        "令",
        "開會通知單",
        "開會紀錄",
        "呈",
        "咨",
        "會勘通知單",
        "公務電話紀錄",
        "手令",
        "箋函",
    ]
)


class DocxExporter:
    """
    將 Markdown 草稿匯出為符合政府標準格式的 Microsoft Word 文件。
    """

    KNOWN_DOC_TYPES = KNOWN_DOC_TYPES

    def __init__(self, strict_format: bool = True) -> None:
        self.template_engine = TemplateEngine()
        self.strict_format = strict_format
        title_font, body_font = get_platform_fonts()
        self._font_title: str | None = title_font
        self._font_body: str | None = body_font
        if strict_format:
            self._size_title = STRICT_FONT_SIZE_TITLE
            self._size_section = STRICT_FONT_SIZE_SECTION_LABEL
            self._size_body = STRICT_FONT_SIZE_BODY
            self._size_meta = STRICT_FONT_SIZE_META
        else:
            self._size_title = FONT_SIZE_TITLE
            self._size_section = FONT_SIZE_SECTION_LABEL
            self._size_body = FONT_SIZE_BODY
            self._size_meta = FONT_SIZE_META

    @staticmethod
    def _sanitize_text(text: str) -> str:
        """清理文字中可能導致 Word 文件損壞的特殊字元。"""
        return _sanitize_text_fn(text)

    def _set_paragraph_spacing(self, paragraph) -> None:
        """設定段落的行距與段前/段後間距（嚴格模式）。"""
        if not self.strict_format:
            return
        pf = paragraph.paragraph_format
        pf.line_spacing = STRICT_LINE_SPACING
        pf.space_before = Pt(self._size_body * STRICT_SPACE_BEFORE_LINES)
        pf.space_after = Pt(STRICT_SPACE_AFTER_LINES)

    def _set_font(self, run, font_name: str | None = None, size: int = FONT_SIZE_META, bold: bool = False) -> None:
        """設定文字段落的字體、大小和粗體。"""
        run.font.size = Pt(size)
        run.font.bold = bold
        if font_name is not None:
            run.font.name = font_name
            r_pr = run._element.get_or_add_rPr()
            r_fonts = r_pr.get_or_add_rFonts()
            r_fonts.set(qn("w:eastAsia"), font_name)

    def _clean_line(self, line: str) -> str:
        """清理單行文字中的 Markdown 標記和特殊字元。"""
        line = self._sanitize_text(line)
        line = clean_markdown_artifacts(line)
        line = re.sub(r"^[#\*\-]+\s*", "", line)
        return line.strip()

    def _extract_doc_type(self, draft_text: str) -> str:
        """從草稿前 10 行中提取公文類型。"""
        lines = draft_text.strip().split("\n")
        for line in lines[:10]:
            clean = self._clean_line(line)
            if clean in KNOWN_DOC_TYPES:
                return clean

        for line in lines[:10]:
            clean = self._clean_line(line)
            for doc_type in sorted(KNOWN_DOC_TYPES, key=len, reverse=True):
                if len(doc_type) == 1:
                    if clean.endswith(doc_type):
                        return doc_type
                    continue
                if doc_type in clean:
                    return doc_type

        return "函"

    @classmethod
    def _write_custom_properties(cls, output_path: str, properties: dict[str, object]) -> None:
        write_custom_properties(output_path, properties)

    def export(
        self,
        draft_text: str,
        output_path: str,
        qa_report: str | None = None,
        citation_metadata: dict | None = None,
    ) -> str:
        """將 Markdown 草稿轉換為 docx 檔案。"""
        if not draft_text or not draft_text.strip():
            logger.warning("匯出收到空的草稿，產生空白文件")
            draft_text = "（無內容）"

        draft_text = self._sanitize_text(draft_text)
        draft_text = clean_markdown_artifacts(draft_text)

        doc = Document()
        self._setup_page(doc)

        try:
            sections = self.template_engine.parse_draft(draft_text)
        except (ValueError, TypeError, AttributeError, KeyError) as exc:
            logger.warning("草稿解析失敗，產生最小有效文件: %s", exc)
            sections = {}

        doc_type = self._extract_doc_type(draft_text)
        write_title(self, doc, doc_type)
        write_meta_info(self, doc, draft_text)
        write_body(self, doc, sections, doc_type)
        write_attachments(self, doc, sections)

        if qa_report:
            write_qa_report(self, doc, qa_report)

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

        export_metadata = build_citation_export_metadata(draft_text, citation_metadata)
        if export_metadata:
            self._write_custom_properties(output_path, export_metadata)
        return output_path

    def _setup_page(self, doc: Document) -> None:
        """設定 A4 頁面邊距。"""
        section = doc.sections[0]
        if self.strict_format:
            section.top_margin = Cm(STRICT_PAGE_MARGIN)
            section.bottom_margin = Cm(STRICT_PAGE_MARGIN)
            section.left_margin = Cm(STRICT_PAGE_MARGIN)
            section.right_margin = Cm(STRICT_PAGE_MARGIN)
        else:
            section.top_margin = Cm(PAGE_MARGIN_TOP)
            section.bottom_margin = Cm(PAGE_MARGIN_BOTTOM)
            section.left_margin = Cm(PAGE_MARGIN_LEFT)
            section.right_margin = Cm(PAGE_MARGIN_RIGHT)

    def _auto_number(self, lines: list[str]) -> list[str]:
        """將多項說明轉換為多層級編號。"""
        return _auto_number_fn(lines, self._clean_line)


__all__ = [
    "CONTENT_TYPES_NS",
    "CONTENT_TYPES_XML_PATH",
    "CUSTOM_PROPERTIES_NS",
    "CUSTOM_PROPERTIES_XML_PATH",
    "CUSTOM_PROPERTY_CONTENT_TYPE",
    "CUSTOM_PROPERTY_FMTID",
    "CUSTOM_PROPERTY_REL_TYPE",
    "DOC_PROPS_VT_NS",
    "DocxExporter",
    "KNOWN_DOC_TYPES",
    "PACKAGE_RELS_NS",
    "PACKAGE_RELS_XML_PATH",
    "get_platform_fonts",
]
