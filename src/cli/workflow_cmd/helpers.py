"""workflow 指令共用 helper。"""

import json
from typing import Any


def load_workflow(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as file_obj:
        return json.load(file_obj)


def build_generate_command(
    *,
    input_text: str,
    output_path: str,
    skip_review: bool,
    max_rounds: int,
    convergence: bool,
    skip_info: bool,
    output_format: str,
) -> str:
    cmd_parts = ["gov-ai", "generate", "-i", f'"{input_text}"', "-o", output_path]
    if skip_review:
        cmd_parts.append("--skip-review")
    if convergence:
        cmd_parts.append("--convergence")
        if skip_info:
            cmd_parts.append("--skip-info")
    else:
        cmd_parts.extend(["--max-rounds", str(max_rounds)])
    if output_format == "markdown":
        cmd_parts.append("--markdown")
    return " ".join(cmd_parts)


def builtin_templates() -> dict[str, dict[str, Any]]:
    return {
        "standard": {
            "name": "標準公文流程",
            "description": "一般公文的完整生成流程",
            "steps": ["需求分析", "草稿撰寫", "格式套用", "品質審查", "匯出"],
            "created": "內建範本",
        },
        "quick": {
            "name": "快速公文流程",
            "description": "跳過審查的快速生成流程",
            "steps": ["需求分析", "草稿撰寫", "格式套用", "匯出"],
            "created": "內建範本",
        },
        "review-only": {
            "name": "純審查流程",
            "description": "僅對現有公文進行品質審查",
            "steps": ["載入公文", "品質審查", "產生報告"],
            "created": "內建範本",
        },
    }


def validate_workflow_yaml(data: Any) -> list[str]:
    problems: list[str] = []
    if not isinstance(data, dict):
        return ["檔案內容必須為 YAML 映射（字典）"]

    if "name" not in data:
        problems.append("缺少必要欄位：name")
    if "steps" not in data:
        problems.append("缺少必要欄位：steps")
    elif not isinstance(data["steps"], list):
        problems.append("steps 必須為列表")
    elif len(data["steps"]) == 0:
        problems.append("steps 列表不得為空")
    else:
        for index, step in enumerate(data["steps"], 1):
            if not isinstance(step, dict) or "name" not in step:
                problems.append(f"步驟 {index} 缺少 name 欄位")

    return problems
