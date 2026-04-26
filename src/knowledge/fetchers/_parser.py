"""公報 Fetcher 解析工具 — XML 解析、PDF 擷取、類別分類、Markdown 組裝。"""
from __future__ import annotations

import io
import logging
import zipfile

import defusedxml.ElementTree as ET

logger = logging.getLogger(__name__)

# ── 例外桶 ────────────────────────────────────────────

_GAZETTE_PARSE_EXCEPTIONS = (
    ET.ParseError,
    TypeError,
    ValueError,
    Exception,
)
_GAZETTE_ZIP_MEMBER_EXCEPTIONS = (
    OSError,
    ValueError,
    zipfile.BadZipFile,
    Exception,
)
_GAZETTE_PDF_EXCEPTIONS = (
    OSError,
    RuntimeError,
    ValueError,
    Exception,
)


def _category_to_collection(category: str) -> str:
    """依據公報 Category 分配目標集合。"""
    if not category:
        return "examples"
    if "行政規則" in category or "法規命令" in category:
        return "regulations"
    if "施政計畫" in category:
        return "policies"
    return "examples"


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """從 PDF bytes 提取全文。需安裝 pdfplumber。"""
    try:
        import pdfplumber
    except ImportError:
        logger.warning("pdfplumber 未安裝，跳過 PDF 全文提取。安裝：pip install pdfplumber")
        return ""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            return "\n\n".join(
                page.extract_text() or "" for page in pdf.pages
            ).strip()
    except _GAZETTE_PDF_EXCEPTIONS as exc:
        logger.warning("PDF 全文提取失敗：%s", exc)
        return ""


def _parse_xml(data: bytes) -> list[dict]:
    """解析公報 XML，回傳 Record 字典清單。"""
    root = ET.fromstring(data)
    records: list[dict] = []
    for record_elem in root.iter("Record"):
        rec: dict[str, str] = {}
        for child in record_elem:
            rec[child.tag] = child.text or ""
        records.append(rec)
    return records


def _build_gazette_body(
    title: str,
    pub_gov: str,
    date_str: str,
    category: str,
    body_text: str,
    *,
    pdf_text: str = "",
) -> str:
    """組合公報 Markdown 主體。"""
    body = f"# {title}\n\n"
    if pub_gov:
        body += f"**發布機關**：{pub_gov}\n\n"
    if date_str:
        body += f"**發布日期**：{date_str}\n\n"
    if category:
        body += f"**類別**：{category}\n\n"
    if body_text:
        body += f"## 內容\n\n{body_text}"
    if pdf_text:
        body += f"\n\n## PDF 全文\n\n{pdf_text}"
    return body
