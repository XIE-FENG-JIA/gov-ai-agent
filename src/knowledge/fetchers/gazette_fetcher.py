"""行政院公報 Fetcher — 下載公報 XML 並產生 Markdown。"""
from __future__ import annotations

import io
import logging
import re
import defusedxml.ElementTree as ET
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

import requests

from src.knowledge.fetchers.base import BaseFetcher, FetchResult, html_to_markdown
from src.knowledge.fetchers.constants import (
    DEFAULT_GAZETTE_DAYS,
    GAZETTE_API_URL,
    GAZETTE_BULK_ZIP_URL,
    GAZETTE_DETAIL_URL,
    SOURCE_LEVEL_A,
)

logger = logging.getLogger(__name__)


def _category_to_collection(category: str) -> str:
    """依據公報 Category 分配目標集合。"""
    if not category:
        return "examples"
    if "行政規則" in category or "法規命令" in category:
        return "regulations"
    if "施政計畫" in category:
        return "policies"
    return "examples"


class GazetteFetcher(BaseFetcher):
    """從行政院公報下載近期公報並轉為 Markdown。"""

    def __init__(
        self,
        output_dir: Path | None = None,
        days: int = DEFAULT_GAZETTE_DAYS,
        category_filter: str | None = None,
        rate_limit: float = 1.0,
    ) -> None:
        super().__init__(
            output_dir=output_dir or Path("kb_data/examples/gazette"),
            rate_limit=rate_limit,
        )
        self.days = days
        self.category_filter = category_filter

    def name(self) -> str:
        return "行政院公報"

    def fetch(self) -> list[FetchResult]:
        """下載 XML 並按日期篩選後輸出 Markdown。"""
        try:
            resp = self._request_with_retry("get", GAZETTE_API_URL, timeout=60)
        except requests.RequestException as exc:
            logger.error("下載公報資料失敗（已重試）：%s", exc)
            return []

        try:
            records = self._parse_xml(resp.content)
        except Exception as exc:
            logger.error("解析公報 XML 失敗：%s", exc)
            return []

        cutoff = datetime.now() - timedelta(days=self.days)
        results: list[FetchResult] = []

        for rec in records:
            # 日期篩選
            date_str = rec.get("Date_Published", "")
            if date_str:
                try:
                    pub_date = datetime.strptime(date_str, "%Y-%m-%d")
                    if pub_date < cutoff:
                        continue
                except ValueError:
                    logger.warning(
                        "公報記錄日期格式無效（MetaId=%s, Date=%s），跳過日期篩選",
                        rec.get("MetaId", "?"), date_str,
                    )

            # Category 篩選
            category = rec.get("Category", "")
            if self.category_filter and self.category_filter not in category:
                continue

            collection = _category_to_collection(category)
            meta_id = rec.get("MetaId", "unknown")
            title = rec.get("Title", "無標題")
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)[:50]
            pub_gov = rec.get("PubGov", "")
            html_content = rec.get("HTMLContent", "")
            body_text = html_to_markdown(html_content) if html_content else ""

            source_url = GAZETTE_DETAIL_URL.format(meta_id=meta_id)
            metadata = {
                "title": title,
                "doc_type": "公報",
                "source": "行政院公報",
                "meta_id": meta_id,
                "category": category,
                "pub_gov": pub_gov,
                "date_published": date_str,
                "tags": ["公報", category] if category else ["公報"],
                "source_level": SOURCE_LEVEL_A,
                "source_url": source_url,
            }

            body = f"# {title}\n\n"
            if pub_gov:
                body += f"**發布機關**：{pub_gov}\n\n"
            if date_str:
                body += f"**發布日期**：{date_str}\n\n"
            if category:
                body += f"**類別**：{category}\n\n"
            if body_text:
                body += f"## 內容\n\n{body_text}"

            # 依 collection 決定輸出子目錄
            if collection == "regulations":
                out_dir = self.output_dir.parent.parent / "regulations" / "gazette"
            elif collection == "policies":
                out_dir = self.output_dir.parent.parent / "policies" / "gazette"
            else:
                out_dir = self.output_dir

            content_hash = self._compute_hash(body)
            metadata["content_hash"] = content_hash

            file_path = out_dir / f"gazette_{meta_id}_{safe_title}.md"
            self._write_markdown(file_path, metadata, body)
            results.append(FetchResult(
                file_path=file_path,
                metadata=metadata,
                collection=collection,
                source_level=SOURCE_LEVEL_A,
                source_url=source_url,
                content_hash=content_hash,
            ))

        logger.info("GazetteFetcher 擷取完成：%d 個檔案", len(results))
        return results

    # ------------------------------------------------------------------
    # 內部方法
    # ------------------------------------------------------------------

    def fetch_bulk(self, *, extract_pdf: bool = True) -> list[FetchResult]:
        """下載 bulk ZIP（含 XML + PDF），解壓後產出 Markdown。"""
        try:
            resp = self._request_with_retry("get", GAZETTE_BULK_ZIP_URL, timeout=180)
        except requests.RequestException as exc:
            logger.error("下載公報 bulk ZIP 失敗（已重試）：%s", exc)
            return []

        try:
            zf = zipfile.ZipFile(io.BytesIO(resp.content))
        except zipfile.BadZipFile:
            logger.error("公報 bulk ZIP 檔案損壞")
            return []

        # 先解析所有 XML，建立 MetaId → record 對照
        xml_records: dict[str, dict] = {}
        for name in zf.namelist():
            if name.lower().endswith(".xml"):
                try:
                    xml_data = zf.read(name)
                    for rec in self._parse_xml(xml_data):
                        meta_id = rec.get("MetaId", "")
                        if meta_id:
                            xml_records[meta_id] = rec
                except Exception as exc:
                    logger.warning("解析 ZIP 內 XML %s 失敗：%s", name, exc)

        # 收集 PDF bytes，以檔名（不含副檔名）為 key
        pdf_texts: dict[str, str] = {}
        if extract_pdf:
            for name in zf.namelist():
                if name.lower().endswith(".pdf"):
                    try:
                        pdf_bytes = zf.read(name)
                        text = self._extract_pdf_text(pdf_bytes)
                        # 以檔名 stem 作為 key（嘗試用 MetaId 匹配）
                        stem = Path(name).stem
                        pdf_texts[stem] = text
                    except Exception as exc:
                        logger.warning("讀取 ZIP 內 PDF %s 失敗：%s", name, exc)

        zf.close()

        cutoff = datetime.now() - timedelta(days=self.days)
        results: list[FetchResult] = []

        for meta_id, rec in xml_records.items():
            # 日期篩選
            date_str = rec.get("Date_Published", "")
            if date_str:
                try:
                    pub_date = datetime.strptime(date_str, "%Y-%m-%d")
                    if pub_date < cutoff:
                        continue
                except ValueError:
                    pass

            # Category 篩選
            category = rec.get("Category", "")
            if self.category_filter and self.category_filter not in category:
                continue

            collection = _category_to_collection(category)
            title = rec.get("Title", "無標題")
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)[:50]
            pub_gov = rec.get("PubGov", "")
            html_content = rec.get("HTMLContent", "")
            body_text = html_to_markdown(html_content) if html_content else ""

            source_url = GAZETTE_DETAIL_URL.format(meta_id=meta_id)

            body = f"# {title}\n\n"
            if pub_gov:
                body += f"**發布機關**：{pub_gov}\n\n"
            if date_str:
                body += f"**發布日期**：{date_str}\n\n"
            if category:
                body += f"**類別**：{category}\n\n"
            if body_text:
                body += f"## 內容\n\n{body_text}"

            # 嘗試匹配 PDF 全文
            pdf_text = pdf_texts.get(meta_id, "")
            has_pdf_text = bool(pdf_text)
            if pdf_text:
                body += f"\n\n## PDF 全文\n\n{pdf_text}"

            # 依 collection 決定輸出子目錄
            if collection == "regulations":
                out_dir = self.output_dir.parent.parent / "regulations" / "gazette"
            elif collection == "policies":
                out_dir = self.output_dir.parent.parent / "policies" / "gazette"
            else:
                out_dir = self.output_dir

            content_hash = self._compute_hash(body)
            metadata = {
                "title": title,
                "doc_type": "公報",
                "source": "行政院公報",
                "meta_id": meta_id,
                "category": category,
                "pub_gov": pub_gov,
                "date_published": date_str,
                "tags": ["公報", category] if category else ["公報"],
                "source_level": SOURCE_LEVEL_A,
                "source_url": source_url,
                "fetch_mode": "bulk",
                "has_pdf_text": has_pdf_text,
                "content_hash": content_hash,
            }

            file_path = out_dir / f"gazette_{meta_id}_{safe_title}.md"
            self._write_markdown(file_path, metadata, body)
            results.append(FetchResult(
                file_path=file_path,
                metadata=metadata,
                collection=collection,
                source_level=SOURCE_LEVEL_A,
                source_url=source_url,
                content_hash=content_hash,
            ))

        logger.info("GazetteFetcher bulk 擷取完成：%d 個檔案", len(results))
        return results

    # ------------------------------------------------------------------
    # 內部方法
    # ------------------------------------------------------------------

    @staticmethod
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
        except Exception as exc:
            logger.warning("PDF 全文提取失敗：%s", exc)
            return ""

    @staticmethod
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
