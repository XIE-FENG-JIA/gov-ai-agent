$env:OLLAMA_MODELS="D:\OllamaModels"
Set-Location "C:\Users\User\Desktop\公文ai agent"

$code = @"
from src.core.config import ConfigManager
from src.core.llm import get_llm_factory
from src.knowledge.manager import KnowledgeBaseManager
from src.agents.auditor import FormatAuditor

def test_custom_validator():
    config = ConfigManager().config
    llm = get_llm_factory(config['llm'])
    kb = KnowledgeBaseManager(config['knowledge_base']['path'], llm)
    auditor = FormatAuditor(llm, kb)
    
    bad_draft = """
### 主旨：請查照。
### 說明：
一、依據本局 100年1月1日 函辦理。
二、檢附會議記錄 1 份。
"""
    
    print("Testing Draft with Logic Errors...")
    result = auditor.audit(bad_draft, "函")
    
    print("\n[Audit Results]")
    print("Errors:", result['errors'])

if __name__ == '__main__':
    test_custom_validator()
"@

$code | Out-File -Encoding utf8 "test_phase4.py"

python test_phase4.py
Remove-Item "test_phase4.py"
