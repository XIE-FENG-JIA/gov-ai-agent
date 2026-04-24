# 公文 AI Agent + n8n 啟動腳本
# 同時啟動 API Server 和 n8n

Write-Host "🚀 公文 AI Agent + n8n 開會系統啟動中..." -ForegroundColor Cyan

# 設定工作目錄
$projectPath = "C:\Users\User\Desktop\公文ai agent"
Set-Location $projectPath

# 啟動 API Server (背景執行)
Write-Host "`n📡 啟動 API Server (port 8000)..." -ForegroundColor Green
$apiJob = Start-Job -ScriptBlock {
    Set-Location "C:\Users\User\Desktop\公文ai agent"
    python api_server.py
}
Write-Host "   API Server PID: $($apiJob.Id)" -ForegroundColor Gray

# 等待 API Server 啟動
Write-Host "   等待 API Server 初始化..." -ForegroundColor Gray
Start-Sleep -Seconds 5

# 檢查 API Server 是否成功啟動
try {
    $response = Invoke-RestMethod -Uri "http://localhost:8000/health" -Method Get -TimeoutSec 5
    Write-Host "   ✅ API Server 啟動成功!" -ForegroundColor Green
} catch {
    Write-Host "   ⚠️ API Server 可能尚未完全啟動，請稍候..." -ForegroundColor Yellow
}

# 啟動 n8n (背景執行)
Write-Host "`n🔗 啟動 n8n (port 5678)..." -ForegroundColor Green
$n8nJob = Start-Job -ScriptBlock {
    n8n start
}
Write-Host "   n8n PID: $($n8nJob.Id)" -ForegroundColor Gray

# 等待 n8n 啟動
Write-Host "   等待 n8n 初始化..." -ForegroundColor Gray
Start-Sleep -Seconds 8

# 開啟瀏覽器
Write-Host "`n🌐 開啟 n8n 介面..." -ForegroundColor Cyan
Start-Process "http://localhost:5678"

# 顯示資訊
Write-Host "`n" + "="*60 -ForegroundColor DarkGray
Write-Host "  🎉 系統已啟動！" -ForegroundColor Cyan
Write-Host "="*60 -ForegroundColor DarkGray
Write-Host ""
Write-Host "  📡 API Server:  http://localhost:8000" -ForegroundColor White
Write-Host "  📖 API 文件:    http://localhost:8000/docs" -ForegroundColor White
Write-Host "  🔗 n8n 介面:    http://localhost:5678" -ForegroundColor White
Write-Host ""
Write-Host "  📥 匯入 Workflow:" -ForegroundColor Yellow
Write-Host "     1. 在 n8n 中點擊右上角 '...' → 'Import from File'" -ForegroundColor Gray
Write-Host "     2. 選擇: n8n_workflow.json" -ForegroundColor Gray
Write-Host ""
Write-Host "  🧪 測試 API (PowerShell):" -ForegroundColor Yellow
Write-Host '     Invoke-RestMethod -Uri "http://localhost:8000/health"' -ForegroundColor Gray
Write-Host ""
Write-Host "  🛑 停止服務:" -ForegroundColor Yellow
Write-Host "     按 Ctrl+C 或執行: Stop-Job *; Remove-Job *" -ForegroundColor Gray
Write-Host ""
Write-Host "="*60 -ForegroundColor DarkGray

# 保持腳本運行，顯示即時日誌
Write-Host "`n📋 即時日誌 (按 Ctrl+C 停止):" -ForegroundColor Cyan
while ($true) {
    # 顯示 API Server 日誌
    $apiOutput = Receive-Job -Job $apiJob -Keep -ErrorAction SilentlyContinue
    if ($apiOutput) {
        Write-Host "[API] $apiOutput" -ForegroundColor Green
    }
    
    # 顯示 n8n 日誌
    $n8nOutput = Receive-Job -Job $n8nJob -Keep -ErrorAction SilentlyContinue
    if ($n8nOutput) {
        Write-Host "[n8n] $n8nOutput" -ForegroundColor Blue
    }
    
    Start-Sleep -Seconds 2
}
