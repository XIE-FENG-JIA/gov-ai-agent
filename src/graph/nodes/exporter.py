"""
export_docx node — 包裝 DocxExporter.export()
"""

import logging
import os
import tempfile

from src.core.constants import OUTPUT_DIR
from src.graph.state import GovDocState

logger = logging.getLogger(__name__)


def export_docx(state: GovDocState) -> dict:
    """將最終草稿匯出為 .docx 檔案。

    讀取: refined_draft/formatted_draft/draft, report, output_path (可選)
    寫入: output_path, phase
    """
    try:
        from src.document.exporter import DocxExporter

        # 取得最終草稿
        final_draft = (
            state.get("refined_draft")
            or state.get("formatted_draft")
            or state.get("draft", "")
        )

        if not final_draft or not final_draft.strip():
            return {"error": "無可匯出的草稿內容", "phase": "failed"}

        qa_report = state.get("report")

        # 輸出路徑：使用者指定或自動產生
        output_path = state.get("output_path", "")
        if not output_path:
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            fd, output_path = tempfile.mkstemp(
                suffix=".docx",
                prefix="gov_doc_",
                dir=str(OUTPUT_DIR),
            )
            os.close(fd)

        exporter = DocxExporter()
        saved_path = exporter.export(final_draft, output_path, qa_report=qa_report)

        logger.info("公文已匯出至: %s", saved_path)

        return {
            "output_path": saved_path,
            "phase": "exported",
        }

    except (OSError, ValueError, RuntimeError) as exc:
        logger.exception("export_docx 失敗: %s", exc)
        return {"error": f"DOCX 匯出失敗: {exc}", "phase": "failed"}
