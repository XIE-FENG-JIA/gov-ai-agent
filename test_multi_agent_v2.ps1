# 多 Agent 架構強化測試腳本
# 測試：法規合規 Agent + 加權評分系統 + 機構記憶

Write-Host "🚀 Multi-Agent Architecture Enhancement Test" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""

# 設定測試環境
$env:PYTHONPATH = "$PWD\src;$env:PYTHONPATH"

Write-Host "📋 Phase 1: 測試合規性檢查器 (Compliance Checker)" -ForegroundColor Yellow
Write-Host "------------------------------------------------" -ForegroundColor Yellow

# 建立測試公文（故意包含政策不一致的內容）
$testDraft = @"
# 函
**主旨**：為推動本市垃圾焚化政策，擬增設焚化爐乙座，請 貴局配合辦理。

**說明**：
一、依據環境保護法第10條及本府環境政策辦理。
二、為解決垃圾處理問題，擬於明年增設大型焚化爐。
三、本案已編列預算新臺幣5億元。

**辦法**：請於文到7日內回復意見。
"@

$testDraft | Out-File -FilePath "./test_compliance_draft.md" -Encoding UTF8

Write-Host "✓ 測試草稿已建立：test_compliance_draft.md" -ForegroundColor Green
Write-Host ""

Write-Host "📋 Phase 2: 測試機構記憶系統 (Organizational Memory)" -ForegroundColor Yellow
Write-Host "------------------------------------------------" -ForegroundColor Yellow

# 測試機構記憶 API
python -c @'
from src.agents.org_memory import OrganizationalMemory

# 初始化機構記憶
org_mem = OrganizationalMemory()

# 測試取得機關偏好
print('\n=== 測試1: 取得臺北市環保局偏好 ===')
profile = org_mem.get_agency_profile('臺北市政府環境保護局')
print(f'正式程度: {profile.get("formal_level")}')
print(f'偏好詞彙: {profile.get("preferred_terms")}')

# 測試更新偏好
print('\n=== 測試2: 更新機關偏好 ===')
org_mem.update_preference('臺北市環保局', 'formal_level', 'concise')
org_mem.update_preference('臺北市環保局', 'preferred_terms', {'函復': '復', '惠請': '請'})

# 測試取得寫作提示
print('\n=== 測試3: 取得寫作提示 ===')
hints = org_mem.get_writing_hints('臺北市政府環境保護局')
print(f'寫作提示:\n{hints}')

# 匯出統計報告
print('\n=== 測試4: 匯出統計報告 ===')
report = org_mem.export_report()
print(report)
'@

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ 機構記憶系統測試通過" -ForegroundColor Green
} else {
    Write-Host "✗ 機構記憶系統測試失敗" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "📋 Phase 3: 測試加權評分系統" -ForegroundColor Yellow
Write-Host "------------------------------------------------" -ForegroundColor Yellow

# 測試加權評分邏輯
python -c @'
from src.agents.editor import EditorInChief

# 顯示權重配置
print('\n=== 類別權重配置 ===')
for category, weight in sorted(EditorInChief.CATEGORY_WEIGHTS.items(), key=lambda x: -x[1]):
    print(f'{category:15s}: {weight:.1f}x')

print('\n說明：')
print('- format (格式) 錯誤影響最大，權重 3.0x')
print('- compliance (合規) 次之，權重 2.5x')
print('- fact (事實) 權重 2.0x')
print('- consistency (一致性) 權重 1.5x')
print('- style (文風) 權重 1.0x')
'@

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ 加權評分系統配置正確" -ForegroundColor Green
} else {
    Write-Host "✗ 加權評分系統測試失敗" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "📋 Phase 4: 整合測試（完整流程）" -ForegroundColor Yellow
Write-Host "------------------------------------------------" -ForegroundColor Yellow

Write-Host "正在執行完整的 Multi-Agent Review..." -ForegroundColor Cyan
python -c @'
import sys
sys.path.insert(0, './src')

from src.core.config import load_config
from src.core.llm import get_llm_provider
from src.knowledge.manager import KnowledgeBaseManager
from src.agents.editor import EditorInChief
from src.agents.org_memory import OrganizationalMemory

# 初始化（使用正確的方式）
config = load_config()
llm = get_llm_provider(config)
kb_manager = KnowledgeBaseManager()
editor = EditorInChief(llm, kb_manager)
org_mem = OrganizationalMemory()

# 讀取測試草稿
with open('./test_compliance_draft.md', 'r', encoding='utf-8') as f:
    draft = f.read()

print('\n=== 執行 Multi-Agent Review ===')
print(f'原始草稿長度: {len(draft)} 字元\n')

# 執行審查
try:
    refined_draft, qa_report = editor.review_and_refine(draft, 'letter')
    
    print('\n=== QA Report Summary ===')
    print(f'Overall Score: {qa_report.overall_score:.2f}')
    print(f'Risk Level: {qa_report.risk_summary}')
    print(f'Total Agents: {len(qa_report.agent_results)}')
    
    # 儲存報告
    with open('./test_qa_weighted_report.md', 'w', encoding='utf-8') as f:
        f.write(qa_report.audit_log)
    
    print('\n✓ QA Report 已儲存至: test_qa_weighted_report.md')
    
except Exception as e:
    print(f'\n✗ Error: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
'@

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✓ 整合測試成功完成！" -ForegroundColor Green
    Write-Host ""
    Write-Host "📊 生成的檔案：" -ForegroundColor Cyan
    Write-Host "  - test_compliance_draft.md (測試草稿)" -ForegroundColor White
    Write-Host "  - test_qa_weighted_report.md (加權評分報告)" -ForegroundColor White
    Write-Host "  - kb_data/agency_preferences.json (機構偏好)" -ForegroundColor White
} else {
    Write-Host ""
    Write-Host "✗ 整合測試失敗" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "🎉 所有測試完成！" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Cyan
