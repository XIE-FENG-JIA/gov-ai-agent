$env:OLLAMA_MODELS="D:\OllamaModels"
Set-Location "C:\Users\User\Desktop\公文ai agent"

# Force OpenRouter for smart citation
python -m src.cli.main switch -p openrouter

# Generate a document that definitely needs reference
$input = "發一份函給各區公所，轉知行政院關於加強資安防護的規定。"
python -m src.cli.main generate --input $input --output "test_citation.docx"
