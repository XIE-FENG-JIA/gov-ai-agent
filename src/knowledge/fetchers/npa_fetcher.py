"""警政署 OPEN DATA Fetcher — 從 NPA 開放資料平臺擷取警政資料集。"""
from __future__ import annotations

import logging
import re
import defusedxml.ElementTree as ET
from pathlib import Path

import requests

from src.knowledge.fetchers.base import BaseFetcher, FetchResult
from src.knowledge.fetchers.constants import (
    NPA_API_BASE,
    NPA_DETAIL_URL,
    NPA_MODULES,
    SOURCE_LEVEL_B,
)

logger = logging.getLogger(__name__)


class NpaFetcher(BaseFetcher):
    """從警政署 OPEN DATA 擷取警政資料集並儲存為 Markdown。"""

    def __init__(
        self,
        output_dir: Path | None = None,
        rate_limit: float = 1.0,
        modules: list[str] | None = None,
    ) -> None:
        super().__init__(
            output_dir=output_dir or Path("kb_data/policies/npa"),
            rate_limit=rate_limit,
        )
        self.modules = modules if modules is not None else NPA_MODULES

    def name(self) -> str:
        return "警政署 OPEN DATA"

    def fetch(self) -> list[FetchResult]:
        """從 NPA API 取得多個模組資料（XML 優先，失敗時回退 JSON）。"""
        all_items: list[dict] = []
        seen_subjects: set[str] = set()

        for module in self.modules:
            items = self._fetch_module(module)
            if items is None:
                continue

            # 去重（跨模組可能有重複標題）
            for item in items:
                subj = item.get("subject", "")
                if subj and subj not in seen_subjects:
                    seen_subjects.add(subj)
                    item["_module"] = module
                    all_items.append(item)

            logger.info("NPA 模組 %s：%d 項（去重後累計 %d）",
                        module, len(items), len(all_items))

        results: list[FetchResult] = []
        for item in all_items:
            subject = item.get("subject", "無標題")
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', subject)[:50]
            pub_unit = item.get("pubUnitName", "")
            poster_date = item.get("posterDate", "")
            update_date = item.get("updateDate", "")
            relate_url = item.get("relateURL", "")

            # 從 relateURL 提取 data.gov.tw dataset ID
            dataset_id = self._extract_dataset_id(relate_url)
            source_url = NPA_DETAIL_URL.format(dataset_id=dataset_id) if dataset_id else relate_url

            detail_content = item.get("detailContent", "")

            body = f"# {subject}\n\n"
            if pub_unit:
                body += f"**發布單位**：{pub_unit}\n\n"
            if poster_date:
                body += f"**發布日期**：{poster_date}\n\n"
            if update_date:
                body += f"**更新日期**：{update_date}\n\n"
            if detail_content:
                from src.knowledge.fetchers.base import html_to_markdown
                md_content = html_to_markdown(detail_content)
                if md_content:
                    body += f"## 內容\n\n{md_content}\n\n"
            if relate_url:
                body += f"**相關連結**：{relate_url}\n"

            content_hash = self._compute_hash(body)
            metadata = {
                "title": subject,
                "doc_type": "警政資料",
                "source": "警政署 OPEN DATA",
                "agency": "內政部警政署",
                "pub_unit": pub_unit,
                "poster_date": poster_date,
                "tags": ["警政資料", "開放資料"],
                "source_level": SOURCE_LEVEL_B,
                "source_url": source_url,
                "content_hash": content_hash,
            }

            file_path = self.output_dir / f"npa_{safe_title}.md"
            if self._write_markdown(file_path, metadata, body) is not None:
                results.append(FetchResult(
                    file_path=file_path,
                    metadata=metadata,
                    collection="policies",
                    source_level=SOURCE_LEVEL_B,
                    source_url=source_url,
                    content_hash=content_hash,
                ))

        logger.info("NpaFetcher 擷取完成：%d 個檔案", len(results))
        return results

    # ------------------------------------------------------------------
    # 內部方法
    # ------------------------------------------------------------------

    def _fetch_module(self, module: str) -> list[dict] | None:
        """嘗試取得單一模組資料，XML 優先、失敗自動回退 JSON。"""
        for fmt in ("xml", "json"):
            url = f"{NPA_API_BASE}?module={module}&mserno=0&type={fmt}"
            try:
                # 單次嘗試，不重試（502 時快速切換格式比重試更有效）
                resp = self._request_with_retry("get", url, timeout=60, max_retries=0)
            except requests.RequestException:
                logger.debug("警政署模組 %s (%s) 請求失敗，嘗試另一格式", module, fmt)
                continue

            try:
                if fmt == "xml":
                    return self._parse_npa_xml(resp.content)
                else:
                    return self._parse_npa_json(resp.content)
            except (ValueError, ET.ParseError):
                logger.debug("解析警政署模組 %s (%s) 失敗，嘗試另一格式", module, fmt)
                continue

        logger.warning("下載警政署模組 %s 失敗（XML 及 JSON 皆不可用）", module)
        return None

    @staticmethod
    def _parse_npa_json(data: bytes) -> list[dict]:
        """從 NPA JSON 回應提取資料項目。"""
        import json
        records = json.loads(data)
        if not isinstance(records, list):
            return []
        items: list[dict] = []
        for rec in records:
            item: dict[str, str] = {}
            item["subject"] = rec.get("subject", "")
            item["pubUnitName"] = rec.get("pubUnitName", "")
            item["posterDate"] = rec.get("posterDate", "")
            item["updateDate"] = rec.get("updateDate", "")
            item["detailContent"] = rec.get("detailContent", "")
            # 從 resources 提取 relateURL
            resources = rec.get("resources", [])
            if isinstance(resources, list) and resources:
                first = resources[0]
                if isinstance(first, dict):
                    item["relateURL"] = first.get("relateURL", "")
            items.append(item)
        return items

    @staticmethod
    def _parse_npa_xml(data: bytes) -> list[dict]:
        """從 NPA XML 提取資料項目。

        預期結構：<List><item>...</item></List>
        或 <resources><resources><relateURL> 結構。
        """
        root = ET.fromstring(data)
        items: list[dict] = []

        for item_elem in root.iter("item"):
            rec: dict[str, str] = {}
            for child in item_elem:
                if child.tag == "resources":
                    # 處理巢狀 resources 結構
                    for res_child in child:
                        if res_child.tag == "resources":
                            for inner in res_child:
                                rec[inner.tag] = inner.text or ""
                        else:
                            rec[child.tag + "_" + res_child.tag] = res_child.text or ""
                else:
                    rec[child.tag] = child.text or ""
            items.append(rec)

        return items

    @staticmethod
    def _extract_dataset_id(url: str) -> str:
        """從 data.gov.tw URL 提取 dataset ID。"""
        if not url:
            return ""
        match = re.search(r"data\.gov\.tw/dataset/(\d+)", url)
        return match.group(1) if match else ""
