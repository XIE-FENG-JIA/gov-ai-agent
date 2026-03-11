$env:OLLAMA_MODELS="D:\OllamaModels"
Set-Location "C:\Users\User\Desktop\公文ai agent"

$code = @"
from src.core.models import PublicDocRequirement
from src.agents.template import TemplateEngine

def test_jinja_engine():
    engine = TemplateEngine()
    
    # Draft with messy numbering
    raw_draft = """
### 主旨
測試進階範本系統。

### 說明
一、第一點說明。
2. 第二點說明 (編號格式混亂)。
(3) 第三點說明。

### 辦法
請配合辦理。
"""
    
    req = PublicDocRequirement(
        doc_type="函",
        sender="測試局",
        receiver="測試處",
        subject="測試",
        urgency="速件",
        attachments=["附件A"]
    )
    
    # 1. Parse
    sections = engine.parse_draft(raw_draft)
    
    # 2. Apply Template (Should re-number nicely)
    final = engine.apply_template(req, sections)
    
    print(final)

if __name__ == '__main__':
    test_jinja_engine()
"@

$code | Out-File -Encoding utf8 "test_jinja.py"

python test_jinja.py
Remove-Item "test_jinja.py"
