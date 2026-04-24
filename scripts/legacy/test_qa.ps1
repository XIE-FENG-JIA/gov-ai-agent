$env:OLLAMA_MODELS="D:\OllamaModels"
Set-Location "C:\Users\User\Desktop\公文ai agent"

# Force OpenRouter/Gemini for best results
python -m src.cli.main switch -p openrouter

# Generate a doc
$input = "發一份公告給各單位，本週五下午要進行大掃除。"
python -m src.cli.main generate --input $input --output "test_qa_report.docx"
