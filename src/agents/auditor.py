from typing import Dict, List, Optional
import json
import re
from rich.console import Console
from src.core.llm import LLMProvider
from src.core.constants import LLM_TEMPERATURE_PRECISE, KB_REGULATION_RESULTS, MAX_DRAFT_LENGTH
from src.agents.template import TemplateEngine
from src.knowledge.manager import KnowledgeBaseManager
from src.agents.validators import validator_registry

console = Console()

class FormatAuditor:
    """
    格式審查 Agent：負責檢查公文格式合規性（完整性、長度、結構）。
    """

    def __init__(self, llm_provider: LLMProvider, kb_manager: Optional[KnowledgeBaseManager] = None):
        self.llm = llm_provider
        self.kb = kb_manager
        self.template_engine = TemplateEngine()

    def audit(self, draft_text: str, doc_type: str) -> Dict[str, List[str]]:
        """
        使用規則引擎和自訂驗證器審查草稿的格式問題。
        """
        errors = []
        warnings = []

        # 防護空值輸入
        if not draft_text or not draft_text.strip():
            return {"errors": ["草稿內容為空"], "warnings": []}

        console.print("[cyan]正在審查格式（動態規則引擎 + 驗證器）...[/cyan]")

        # 1. 檢索規則
        rule_context = ""
        if self.kb:
            console.print(f"[cyan]正在擷取「{doc_type}」的動態規則...[/cyan]")
            try:
                regs = self.kb.search_regulations(f"{doc_type} 格式規則", doc_type=doc_type, n_results=KB_REGULATION_RESULTS)
                if regs:
                    rule_content = regs[0].get('content', '')
                    rule_context = f"### Active Regulation Set ({doc_type})\n{rule_content}"
                    rule_metadata = regs[0].get('metadata', {})
                    rule_title = rule_metadata.get('title', '未知') if isinstance(rule_metadata, dict) else '未知'
                    console.print(f"[green]已載入規則：{rule_title}[/green]")
            except Exception as e:
                console.print(f"[yellow]知識庫查詢失敗：{str(e)[:50]}，將使用通用規則。[/yellow]")
        
        # 2. Execute Custom Validators (Function Calls)
        # Scan rule_context for [Call: func_name]
        # 安全性：僅允許白名單內的驗證函數
        ALLOWED_VALIDATORS = {
            "check_date_logic",
            "check_attachment_consistency",
            "check_citation_format",
            "check_doc_integrity",
        }
        if rule_context:
            call_matches = re.findall(r"\[Call:\s*(\w+)\]", rule_context)
            for func_name in call_matches:
                if func_name not in ALLOWED_VALIDATORS:
                    console.print(f"[yellow]不允許的驗證器: {func_name}（已跳過）[/yellow]")
                    continue
                if hasattr(validator_registry, func_name):
                    console.print(f"[blue]執行驗證器: {func_name}[/blue]")
                    func = getattr(validator_registry, func_name)
                    try:
                        validation_errors = func(draft_text)
                        errors.extend(validation_errors)
                    except Exception as e:
                        console.print(f"[red]驗證器 {func_name} 失敗: {e}[/red]")
                else:
                    console.print(f"[yellow]未知的驗證器: {func_name}[/yellow]")

        # 3. 退回安全機制
        if not rule_context:
            console.print("[yellow]知識庫中找不到特定規則，使用通用安全規則。[/yellow]")
            rule_context = """### Generic Safety Rules
- [Error] Must have a 'Subject' (主旨) section.
- [Warning] Should have 'Explanation' (說明) or 'Provisions' (辦法) section.
- [Warning] Tone should be formal.
"""

        # 4. Construct Prompt Engine (LLM Audit)
        # 截斷過長的草稿
        truncated_draft = draft_text
        if len(draft_text) > MAX_DRAFT_LENGTH:
            truncated_draft = draft_text[:MAX_DRAFT_LENGTH] + "\n...(草稿已截斷)"

        audit_prompt = f"""You are a strict Government Document Compliance Engine.
Your goal is to validate the Draft against the provided Rule Set.

{rule_context}

# Draft to Validate
{truncated_draft}

# Execution Instructions
1. Read the "Active Regulation Set" carefully.
2. Check if the Draft violates ANY rule marked as [Error] or [Warning] or [Info].
3. IGNORE lines starting with [Call: ...], as they are handled programmatically.
4. Pay special attention to:
   - Missing sections (Structure)
   - Forbidden terms
   - Formatting constraints (e.g. word count, ending phrases)

# Output Format
Return purely a JSON object:
{{
    "errors": ["List of specific violations marked as [Error] in rules"],
    "warnings": ["List of suggestions or [Warning]/[Info] violations"]
}}
If perfect, return empty lists.
"""
        try:
            response = self.llm.generate(audit_prompt, temperature=LLM_TEMPERATURE_PRECISE)
            if not response or not response.strip():
                warnings.append("審查系統收到空白回應，請手動檢查。")
                return {"errors": errors, "warnings": warnings}

            match = re.search(r"(\{.*\})", response, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
                errors.extend(data.get("errors", []))
                warnings.extend(data.get("warnings", []))
            else:
                warnings.append("審查系統無法解析結果，請手動檢查。")

        except json.JSONDecodeError:
            warnings.append("審查系統無法解析 JSON，請手動檢查。")
        except Exception as e:
            warnings.append(f"審查錯誤：{str(e)[:50]}")

        return {
            "errors": errors,
            "warnings": warnings
        }