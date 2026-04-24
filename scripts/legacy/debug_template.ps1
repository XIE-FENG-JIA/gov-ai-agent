$env:OLLAMA_MODELS="D:\OllamaModels"
Set-Location "C:\Users\User\Desktop\公文ai agent"

$code = @"
from src.core.models import PublicDocRequirement
from src.agents.template import TemplateEngine

def test_jinja_engine():
    engine = TemplateEngine()
    
    raw_draft = """
### 主旨
測試進階範本系統。

### 說明
一、第一點說明。
2. 第二點說明。
(3) 第三點說明。
"""
    
    sections = engine.parse_draft(raw_draft)
    print(f"Parsed Explanation: {sections.get('explanation')!r}")
    
    points = engine._parse_list_items(sections.get('explanation'))
    print(f"Parsed Points: {points}")
    
    final = engine.apply_template(PublicDocRequirement(doc_type="函", sender="A", receiver="B", subject="S"), sections)
    print("\n--- Final ---")
    print(final)

if __name__ == '__main__':
    test_jinja_engine()
"@

$code | Out-File -Encoding utf8 "debug_jinja.py"

python debug_jinja.py
Remove-Item "debug_jinja.py"
