$env:OLLAMA_MODELS="D:\OllamaModels"
Set-Location "C:\Users\User\Desktop\公文ai agent"

# Force switch to Gemini (or OpenRouter) for smart auditing
# We need a smart model to understand the generic prompt instructions
python -m src.cli.main switch -p openrouter

$code = @"
from src.core.config import ConfigManager
from src.core.llm import get_llm_factory
from src.knowledge.manager import KnowledgeBaseManager
from src.agents.auditor import FormatAuditor

def test_dynamic_audit():
    config = ConfigManager().config
    llm = get_llm_factory(config['llm'])
    kb = KnowledgeBaseManager(config['knowledge_base']['path'], llm)
    auditor = FormatAuditor(llm, kb)
    
    # Test Case: A draft that violates the "Subject Expectation" rule
    # Rule says: Subject MUST end with "請 查照"
    bad_draft = """
### 主旨
關於舉辦資安講習的通知

### 說明
一、時間地點如附件。
"""
    
    print("Testing Draft (Missing '請 查照')...")
    result = auditor.audit(bad_draft, "函")
    
    print("\n[Audit Results]")
    print("Errors:", result['errors'])
    print("Warnings:", result['warnings'])

if __name__ == '__main__':
    test_dynamic_audit()
"@

$code | Out-File -Encoding utf8 "test_phase3.py"

python test_phase3.py
Remove-Item "test_phase3.py"
