# 公文 AI Agent - 測試執行器
# 執行所有 pytest 測試套件並顯示結果

# 確保在專案目錄
Set-Location "C:\Users\User\Desktop\公文ai agent"

Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "   公文 AI Agent - 完整測試套件         " -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan

# 1. 安裝/檢查依賴
Write-Host "[1/2] 正在檢查測試依賴..." -ForegroundColor Yellow
pip install pytest pytest-cov httpx -q
if ($LASTEXITCODE -ne 0) {
    Write-Error "安裝依賴失敗。"
    exit 1
}

# 2. 執行 Pytest（含覆蓋率報告）
Write-Host "[2/2] 正在執行測試..." -ForegroundColor Yellow
$env:PYTHONPATH = $PWD
pytest tests/ -v --cov=src --cov=api_server --cov-report=term-missing

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n[成功] 所有測試通過！" -ForegroundColor Green
} else {
    Write-Host "`n[失敗] 部分測試未通過，請檢查日誌。" -ForegroundColor Red
    exit 1
}
