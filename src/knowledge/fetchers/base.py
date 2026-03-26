"""BaseFetcher 抽象基底類別與共用工具。"""
from __future__ import annotations

import re
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import requests
import yaml

logger = logging.getLogger(__name__)

# 共用 HTTP retry 設定
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_BACKOFF_BASE = 2  # 指數退避基數（秒）
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


@dataclass
class FetchResult:
    """單一擷取結果。"""
    file_path: Path
    metadata: dict
    collection: str
    source_level: str = "B"
    source_url: str | None = None
    content_hash: str = ""


class BaseFetcher(ABC):
    """所有政府 API fetcher 的抽象基底類別。"""

    def __init__(
        self,
        output_dir: Path,
        rate_limit: float = 1.0,
        allow_ssl_fallback: bool = False,
    ) -> None:
        self.output_dir = output_dir
        self.rate_limit = rate_limit
        self.allow_ssl_fallback = allow_ssl_fallback
        self._last_request_time: float = 0.0

    def _throttle(self) -> None:
        """速率限制：確保兩次請求之間至少間隔 rate_limit 秒。"""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self._last_request_time = time.time()

    def _request_with_retry(
        self,
        method: str,
        url: str,
        *,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        **kwargs,
    ) -> requests.Response:
        """帶指數退避重試的 HTTP 請求。

        Args:
            method: HTTP 方法（"get" 或 "post"）
            url: 請求 URL
            max_retries: 最大重試次數
            **kwargs: 傳遞給 requests.request() 的額外參數

        Returns:
            requests.Response

        Raises:
            requests.RequestException: 所有重試皆失敗後拋出
        """
        last_exc: Exception | None = None
        ssl_fallback = False  # SSL 憑證驗證降級旗標
        for attempt in range(max_retries + 1):
            self._throttle()
            try:
                http_func = getattr(requests, method)
                if ssl_fallback:
                    kwargs.setdefault("verify", False)
                resp = http_func(url, **kwargs)
                if resp.status_code not in _RETRYABLE_STATUS_CODES:
                    resp.raise_for_status()
                    return resp
                # 可重試的狀態碼
                logger.warning(
                    "%s 回傳 %d，第 %d/%d 次重試",
                    url, resp.status_code, attempt + 1, max_retries,
                )
                last_exc = requests.HTTPError(
                    f"HTTP {resp.status_code}", response=resp,
                )
            except requests.ConnectionError as e:
                if "SSL" in str(e) or "CERTIFICATE" in str(e):
                    if not ssl_fallback:
                        if self.allow_ssl_fallback:
                            ssl_fallback = True
                            last_exc = e
                            logger.error(
                                "SSL 憑證驗證失敗 %s，已啟用 allow_ssl_fallback，降級為不驗證模式重試。"
                                "注意：這會停用 MITM 防護。", url,
                            )
                            continue  # 立即重試，不消耗重試次數
                        else:
                            logger.error(
                                "SSL 憑證驗證失敗 %s。如需連線此端點，"
                                "請設定 allow_ssl_fallback=True 或修正憑證。", url,
                            )
                            raise
                logger.warning("連線失敗 %s（第 %d/%d 次）: %s", url, attempt + 1, max_retries, e)
                last_exc = e
            except requests.Timeout as e:
                logger.warning("請求逾時 %s（第 %d/%d 次）: %s", url, attempt + 1, max_retries, e)
                last_exc = e
            except requests.HTTPError:
                raise  # 非可重試的 HTTP 錯誤直接拋出

            if attempt < max_retries:
                wait = _DEFAULT_BACKOFF_BASE ** attempt
                logger.info("等待 %d 秒後重試...", wait)
                time.sleep(wait)

        raise last_exc  # type: ignore[misc]

    def _fetch_json(
        self,
        method: str,
        url: str,
        *,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        **kwargs,
    ) -> dict | list | None:
        """HTTP 請求 + JSON 解析的快捷方法。

        結合 _request_with_retry 與 resp.json()，失敗時回傳 None 並記錄錯誤。
        適用於大多數回傳 JSON 的政府 API 端點。
        """
        try:
            resp = self._request_with_retry(method, url, max_retries=max_retries, **kwargs)
        except requests.RequestException as exc:
            logger.error("HTTP 請求失敗 %s：%s", url, exc)
            return None
        try:
            return resp.json()
        except Exception as exc:
            logger.error("JSON 解析失敗 %s：%s", url, exc)
            return None

    def _write_markdown(self, file_path: Path, metadata: dict, body: str) -> Path | None:
        """輸出含 YAML frontmatter 的 Markdown 檔案。

        格式與 parse_markdown_with_metadata 完全相容。
        寫入失敗時記錄警告並回傳 None（不再回傳不存在的路徑）。
        """
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)

            frontmatter = yaml.dump(
                metadata, allow_unicode=True, default_flow_style=False
            ).strip()

            content = f"---\n{frontmatter}\n---\n{body}"
            file_path.write_text(content, encoding="utf-8")
        except OSError as exc:
            logger.warning("寫入檔案失敗 '%s': %s", file_path, exc)
            return None
        return file_path

    @staticmethod
    def _compute_hash(text: str) -> str:
        """計算文本的 SHA-256 hash（前 16 字元）。"""
        import hashlib
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    @abstractmethod
    def fetch(self) -> list[FetchResult]:
        """執行擷取，回傳所有產生的結果。"""
        ...

    @abstractmethod
    def name(self) -> str:
        """回傳 fetcher 名稱（用於日誌和 CLI 顯示）。"""
        ...


def html_to_markdown(html: str) -> str:
    """將簡單 HTML 轉換為 Markdown（regex 實作，零外部依賴）。"""
    if not html:
        return ""

    text = html

    # 移除 CDATA 包裝
    text = re.sub(r'<!\[CDATA\[', '', text)
    text = re.sub(r'\]\]>', '', text)

    # 標題轉換
    for i in range(1, 7):
        text = re.sub(rf'<h{i}[^>]*>(.*?)</h{i}>', rf'{"#" * i} \1', text, flags=re.DOTALL | re.IGNORECASE)

    # 段落和換行
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', text, flags=re.DOTALL | re.IGNORECASE)

    # 粗體和斜體
    text = re.sub(r'<(?:b|strong)[^>]*>(.*?)</(?:b|strong)>', r'**\1**', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<(?:i|em)[^>]*>(.*?)</(?:i|em)>', r'*\1*', text, flags=re.DOTALL | re.IGNORECASE)

    # 清單
    text = re.sub(r'<li[^>]*>(.*?)</li>', r'- \1\n', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'</?(?:ul|ol)[^>]*>', '', text, flags=re.IGNORECASE)

    # 表格簡化：移除標籤但保留文字
    text = re.sub(r'</?(?:table|thead|tbody|tr|th|td)[^>]*>', ' ', text, flags=re.IGNORECASE)

    # 移除所有其餘 HTML 標籤
    text = re.sub(r'<[^>]+>', '', text)

    # HTML 實體
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&quot;', '"')

    # 清理多餘空白行
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()
