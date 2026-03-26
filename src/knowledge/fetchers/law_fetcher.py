"""全國法規資料庫 Fetcher — 下載法規全文並產生 Markdown。"""
from __future__ import annotations

import io
import json
import logging
import re
import defusedxml.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

import requests

from src.knowledge.fetchers.base import BaseFetcher, FetchResult
from src.knowledge.fetchers.constants import (
    DEFAULT_LAW_PCODES,
    LAW_API_URL,
    LAW_BULK_XML_URL,
    LAW_DETAIL_URL,
    SOURCE_LEVEL_A,
)

logger = logging.getLogger(__name__)

# 超過此字數的法規，按每 CHUNK_ARTICLES 條分割
MAX_CHARS_PER_FILE = 10_000
CHUNK_ARTICLES = 20


class LawFetcher(BaseFetcher):
    """從全國法規資料庫下載指定法規的全文。"""

    def __init__(
        self,
        output_dir: Path | None = None,
        pcodes: dict[str, str] | None = None,
        rate_limit: float = 1.0,
    ) -> None:
        super().__init__(
            output_dir=output_dir or Path("kb_data/regulations/laws"),
            rate_limit=rate_limit,
        )
        self.pcodes = pcodes if pcodes is not None else DEFAULT_LAW_PCODES

    def name(self) -> str:
        return "全國法規資料庫"

    def fetch(self) -> list[FetchResult]:
        """下載 ZIP，解壓後篩選指定 PCode 並輸出 Markdown。"""
        try:
            resp = self._request_with_retry("get", LAW_API_URL, timeout=120)
        except requests.RequestException as exc:
            logger.error("下載法規資料失敗（已重試）：%s", exc)
            return []

        try:
            laws = self._extract_laws_from_response(resp.content)
        except Exception as exc:
            logger.error("解析法規資料失敗：%s", exc)
            return []

        results: list[FetchResult] = []
        for law in laws:
            pcode = law.get("PCode", "")
            if pcode not in self.pcodes:
                continue

            law_name = law.get("LawName", self.pcodes.get(pcode, "未知法規"))
            # 清理法規名稱中不合法的檔名字元
            safe_name = re.sub(r'[<>:"/\\|?*]', '_', law_name)
            articles = law.get("LawArticles", [])

            article_bodies = self._format_articles(articles)
            total_text = "\n\n".join(article_bodies)

            source_url = LAW_DETAIL_URL.format(pcode=pcode)

            if len(total_text) > MAX_CHARS_PER_FILE and len(article_bodies) > CHUNK_ARTICLES:
                results.extend(self._write_chunked(pcode, safe_name, law_name, articles, article_bodies, source_url))
            else:
                body = f"# {law_name}\n\n{total_text}"
                content_hash = self._compute_hash(body)
                metadata = {
                    "title": law_name,
                    "doc_type": "法規",
                    "source": "全國法規資料庫",
                    "pcode": pcode,
                    "article_count": len(articles),
                    "tags": ["法規", "全文"],
                    "source_level": SOURCE_LEVEL_A,
                    "source_url": source_url,
                    "content_hash": content_hash,
                }
                file_path = self.output_dir / f"{pcode}_{safe_name}.md"
                self._write_markdown(file_path, metadata, body)
                results.append(FetchResult(
                    file_path=file_path,
                    metadata=metadata,
                    collection="regulations",
                    source_level=SOURCE_LEVEL_A,
                    source_url=source_url,
                    content_hash=content_hash,
                ))

        logger.info("LawFetcher 擷取完成：%d 個檔案", len(results))
        return results

    # ------------------------------------------------------------------
    # 內部方法
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_laws_from_response(data: bytes) -> list[dict]:
        """嘗試以 ZIP 解壓，若失敗則直接當 JSON 解析。

        API 回傳格式可能是：
        - ZIP 內含 ChLaw.json → {"Laws": [...]} 或 [...]
        - 直接 JSON → {"Laws": [...]} 或 [...]
        每筆 law 的 PCode 可能在 LawURL 中而非獨立欄位。
        """
        raw_list: list[dict] = []

        def _unwrap_json(parsed: Any) -> list[dict]:
            """處理 {"Laws": [...]} 或直接 list 格式。"""
            if isinstance(parsed, dict):
                # API 新格式：{"UpdateDate": ..., "Laws": [...]}
                if "Laws" in parsed and isinstance(parsed["Laws"], list):
                    return parsed["Laws"]
                return [parsed]
            if isinstance(parsed, list):
                return parsed
            return []

        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                for name in zf.namelist():
                    if name.endswith(".json"):
                        raw = zf.read(name)
                        try:
                            parsed = json.loads(raw)
                        except (json.JSONDecodeError, ValueError):
                            logger.warning("ZIP 內 JSON 解析失敗：%s", name)
                            continue
                        raw_list.extend(_unwrap_json(parsed))
        except zipfile.BadZipFile:
            try:
                parsed = json.loads(data)
            except (json.JSONDecodeError, ValueError):
                logger.warning("法規 API 回傳資料非合法 ZIP 亦非合法 JSON（%d bytes）", len(data))
                return raw_list
            raw_list.extend(_unwrap_json(parsed))

        # 從 LawURL 提取 PCode（若缺少獨立 PCode 欄位）
        for law in raw_list:
            if "PCode" not in law:
                url = law.get("LawURL", "")
                m = re.search(r"pcode=([A-Z0-9]+)", url, re.IGNORECASE)
                if m:
                    law["PCode"] = m.group(1)

        return raw_list

    @staticmethod
    def _format_articles(articles: list[dict]) -> list[str]:
        """將條文清單格式化為 Markdown 段落。"""
        bodies: list[str] = []
        for art in articles:
            num = art.get("ArticleNo", art.get("Number", ""))
            content = art.get("ArticleContent", art.get("Content", ""))
            if num and content:
                bodies.append(f"### {num}\n{content}")
            elif content:
                bodies.append(content)
        return bodies

    def _write_chunked(
        self,
        pcode: str,
        safe_name: str,
        law_name: str,
        articles: list[dict],
        article_bodies: list[str],
        source_url: str = "",
    ) -> list[FetchResult]:
        """大型法規按每 CHUNK_ARTICLES 條分割為多檔。"""
        results: list[FetchResult] = []
        for idx in range(0, len(article_bodies), CHUNK_ARTICLES):
            chunk = article_bodies[idx:idx + CHUNK_ARTICLES]
            part_num = idx // CHUNK_ARTICLES + 1
            start = idx + 1
            end = min(idx + CHUNK_ARTICLES, len(article_bodies))

            body = f"# {law_name}（第 {start}-{end} 條）\n\n" + "\n\n".join(chunk)
            content_hash = self._compute_hash(body)
            metadata = {
                "title": f"{law_name}（第 {start}-{end} 條）",
                "doc_type": "法規",
                "source": "全國法規資料庫",
                "pcode": pcode,
                "article_count": len(chunk),
                "part": part_num,
                "tags": ["法規", "全文", "分段"],
                "source_level": SOURCE_LEVEL_A,
                "source_url": source_url,
                "content_hash": content_hash,
            }
            file_path = self.output_dir / f"{pcode}_{safe_name}_part{part_num}.md"
            self._write_markdown(file_path, metadata, body)
            results.append(FetchResult(
                file_path=file_path,
                metadata=metadata,
                collection="regulations",
                source_level=SOURCE_LEVEL_A,
                source_url=source_url,
                content_hash=content_hash,
            ))
        return results

    def fetch_bulk(self, *, au_data: str = "CFM") -> list[FetchResult]:
        """從全國法規資料庫下載 bulk XML 並產出 Markdown。"""
        url = f"{LAW_BULK_XML_URL}?DType=XML&AuData={au_data}"
        try:
            resp = self._request_with_retry("get", url, timeout=300)
        except requests.RequestException as exc:
            logger.error("下載法規 bulk XML 失敗（已重試）：%s", exc)
            return []

        # 嘗試 ZIP 解壓
        try:
            zf = zipfile.ZipFile(io.BytesIO(resp.content))
        except zipfile.BadZipFile:
            logger.error("法規 bulk ZIP 檔案損壞")
            return []

        all_laws: list[dict] = []
        with zf:
            for name in zf.namelist():
                if name.lower().endswith(".xml"):
                    try:
                        xml_data = zf.read(name)
                        all_laws.extend(self._parse_bulk_xml(xml_data))
                    except Exception as exc:
                        logger.warning("解析 ZIP 內 XML %s 失敗：%s", name, exc)

        results: list[FetchResult] = []
        for law in all_laws:
            pcode = law.get("PCode", "")
            # 若有指定 pcodes 則篩選
            if self.pcodes and pcode not in self.pcodes:
                continue

            law_name = law.get("LawName", self.pcodes.get(pcode, "未知法規") if self.pcodes else "未知法規")
            safe_name = re.sub(r'[<>:"/\\|?*]', '_', law_name)
            articles = law.get("LawArticles", [])

            article_bodies = self._format_articles(articles)
            total_text = "\n\n".join(article_bodies)

            source_url = LAW_DETAIL_URL.format(pcode=pcode)

            if len(total_text) > MAX_CHARS_PER_FILE and len(article_bodies) > CHUNK_ARTICLES:
                results.extend(self._write_chunked(
                    pcode, safe_name, law_name, articles, article_bodies, source_url,
                ))
            else:
                body = f"# {law_name}\n\n{total_text}"
                content_hash = self._compute_hash(body)
                metadata = {
                    "title": law_name,
                    "doc_type": "法規",
                    "source": "全國法規資料庫",
                    "pcode": pcode,
                    "article_count": len(articles),
                    "tags": ["法規", "全文"],
                    "source_level": SOURCE_LEVEL_A,
                    "source_url": source_url,
                    "fetch_mode": "bulk",
                    "content_hash": content_hash,
                }
                file_path = self.output_dir / f"{pcode}_{safe_name}.md"
                self._write_markdown(file_path, metadata, body)
                results.append(FetchResult(
                    file_path=file_path,
                    metadata=metadata,
                    collection="regulations",
                    source_level=SOURCE_LEVEL_A,
                    source_url=source_url,
                    content_hash=content_hash,
                ))

        logger.info("LawFetcher bulk 擷取完成：%d 個檔案", len(results))
        return results

    @staticmethod
    def _parse_bulk_xml(data: bytes) -> list[dict]:
        """解析全國法規資料庫 bulk XML，回傳與 JSON API 相同格式的 dict 清單。

        bulk XML 格式：根元素下有多個 <法規> 元素，每個含
        <法規性質>、<法規名稱>、<法規網址>、<法規類別>、<前言>、<條文> 子元素。
        條文含 <條號>、<條文內容> 子元素。
        """
        # 嘗試 UTF-8 和 Big5 編碼
        text = None
        for encoding in ("utf-8", "big5", "cp950"):
            try:
                text = data.decode(encoding)
                break
            except (UnicodeDecodeError, LookupError):
                continue
        if text is None:
            text = data.decode("utf-8", errors="replace")

        root = ET.fromstring(text)
        laws: list[dict] = []

        # 支援 <法規> 或 <Law> 標籤
        for law_elem in list(root.iter("法規")) + list(root.iter("Law")):
            law_dict: dict = {}

            # 提取法規基本資訊（使用 is not None 避免 Element 真值測試問題）
            name_el = law_elem.find("法規名稱")
            if name_el is None:
                name_el = law_elem.find("LawName")
            if name_el is not None and name_el.text:
                law_dict["LawName"] = name_el.text.strip()

            url_el = law_elem.find("法規網址")
            if url_el is None:
                url_el = law_elem.find("LawURL")
            if url_el is not None and url_el.text:
                # 從 URL 提取 PCode
                url_text = url_el.text.strip()
                pcode_match = re.search(r"pcode=([A-Z0-9]+)", url_text, re.IGNORECASE)
                if pcode_match:
                    law_dict["PCode"] = pcode_match.group(1)

            pcode_el = law_elem.find("PCode")
            if pcode_el is not None and pcode_el.text:
                law_dict["PCode"] = pcode_el.text.strip()

            # 跳過沒有 PCode 的法規
            if "PCode" not in law_dict:
                continue

            # 提取前言
            foreword_el = law_elem.find("前言")
            if foreword_el is None:
                foreword_el = law_elem.find("Foreword")
            foreword_text = ""
            if foreword_el is not None and foreword_el.text:
                foreword_text = foreword_el.text.strip()

            # 提取條文
            articles: list[dict] = []
            if foreword_text:
                articles.append({
                    "ArticleNo": "前言",
                    "ArticleContent": foreword_text,
                })
            for art_elem in list(law_elem.iter("條文")) + list(law_elem.iter("Article")):
                art_no_el = art_elem.find("條號")
                if art_no_el is None:
                    art_no_el = art_elem.find("ArticleNo")
                art_content_el = art_elem.find("條文內容")
                if art_content_el is None:
                    art_content_el = art_elem.find("ArticleContent")
                if art_no_el is not None and art_content_el is not None:
                    articles.append({
                        "ArticleNo": (art_no_el.text or "").strip(),
                        "ArticleContent": (art_content_el.text or "").strip(),
                    })

            law_dict["LawArticles"] = articles
            laws.append(law_dict)

        return laws
