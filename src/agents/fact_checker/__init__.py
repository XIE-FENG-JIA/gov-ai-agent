from __future__ import annotations

import logging
import pathlib
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_MAPPING_PATH = pathlib.Path(__file__).resolve().parents[3] / "kb_data" / "regulation_doc_type_mapping.yaml"


def _load_regulation_doc_type_mapping() -> dict[str, dict[str, Any]]:
    """載入法規-文件類型映射表，找不到檔案時回傳空字典。"""
    if not _MAPPING_PATH.exists():
        logger.debug("法規-文件類型映射表不存在：%s", _MAPPING_PATH)
        return {}
    try:
        with open(_MAPPING_PATH, encoding="utf-8") as file:
            data = yaml.safe_load(file)
        return data.get("regulations", {}) if isinstance(data, dict) else {}
    except Exception as exc:
        logger.warning("載入法規-文件類型映射表失敗：%s", exc)
        return {}


from src.agents.fact_checker.pipeline import FactChecker

__all__ = ["FactChecker", "_MAPPING_PATH", "_load_regulation_doc_type_mapping"]
