"""批次處理純函式（無 typer/rich 依賴）。"""
import csv
import json
from pathlib import Path


class BatchLoadError(Exception):
    """批次檔案載入失敗。"""


_TEMPLATE_ITEMS = [
    {
        "input": "台北市政府環保局致各級學校，加強校園資源回收分類作業",
        "output": "batch_output_1.docx",
    },
    {
        "input": "衛生福利部函請各縣市衛生局，配合辦理流感疫苗接種事宜",
        "output": "batch_output_2.docx",
    },
    {
        "input": "教育部通知各大專校院，辦理校園安全防護演練",
        "output": "batch_output_3.docx",
    },
]

_BATCH_INFORMAL = {
    "所以": "爰此",
    "但是": "惟",
    "而且": "且",
    "因為": "因",
    "可是": "然",
    "還有": "另",
    "已經": "業已",
}

_BATCH_REQUIRED = ["主旨", "說明"]


def _load_items(file_path: Path) -> list[dict]:
    """根據副檔名載入 JSON 或 CSV 批次檔案。"""
    if file_path.suffix.lower() == ".csv":
        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None or "input" not in reader.fieldnames:
                raise BatchLoadError("CSV 必須包含 input 欄位")
            items = []
            for row in reader:
                if not row.get("input", "").strip():
                    continue
                items.append({
                    "input": row["input"],
                    "output": row.get("output", "").strip() or f"batch_output_{len(items)+1}.docx",
                })
            return items
    else:
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise BatchLoadError(f"JSON 格式錯誤：{e}")
        if not isinstance(data, list):
            raise BatchLoadError("JSON 必須是陣列")
        return data


def check_doc_content(text: str, strict: bool = False) -> tuple[str, str]:
    """驗證公文純文字是否符合基本格式，回傳 (status, detail)。"""
    issues = []
    missing = [s for s in _BATCH_REQUIRED if s not in text]
    if missing:
        issues.append(f"缺少：{'、'.join(missing)}")
    if strict:
        for informal in _BATCH_INFORMAL:
            if informal in text:
                issues.append(f"口語用詞「{informal}」")
    if issues:
        return "失敗", "；".join(issues)
    return "通過", "格式正確"


def lint_doc_content(text: str) -> tuple[int, str]:
    """批次 lint 單一公文純文字，回傳 (issue_count, detail_text)。"""
    issue_count = 0
    details = []
    for informal in _BATCH_INFORMAL:
        if informal in text:
            issue_count += 1
            details.append(f"口語：{informal}")
    for section in _BATCH_REQUIRED:
        if section not in text:
            issue_count += 1
            details.append(f"缺少：{section}")
    detail_text = "；".join(details) if details else "通過"
    return issue_count, detail_text
