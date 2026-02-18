"""
validators.py 的單元測試
測試所有自訂驗證器函數的正確性和邊界情況
"""
import pytest
from src.agents.validators import ValidatorRegistry


@pytest.fixture
def registry():
    """回傳一個 ValidatorRegistry 實例。"""
    return ValidatorRegistry()


# ==================== check_date_logic ====================

class TestCheckDateLogic:
    """日期邏輯檢查器的測試"""

    def test_valid_roc_date(self, registry):
        """測試合法的民國日期不會產生錯誤"""
        draft = "本案訂於114年3月15日辦理。"
        errors = registry.check_date_logic(draft)
        assert len(errors) == 0

    def test_invalid_date_month_13(self, registry):
        """測試無效月份（13月）會產生錯誤"""
        draft = "本案訂於114年13月1日辦理。"
        errors = registry.check_date_logic(draft)
        assert len(errors) == 1
        assert "無效日期" in errors[0]

    def test_invalid_date_day_32(self, registry):
        """測試無效日期（32日）會產生錯誤"""
        draft = "本案訂於114年2月32日辦理。"
        errors = registry.check_date_logic(draft)
        assert len(errors) == 1
        assert "無效日期" in errors[0]

    def test_no_date_in_text(self, registry):
        """測試沒有日期的文字不產生錯誤"""
        draft = "本案請查照辦理。"
        errors = registry.check_date_logic(draft)
        assert len(errors) == 0

    def test_multiple_dates(self, registry):
        """測試多個日期同時存在的情況"""
        draft = "本案訂於114年3月15日至114年4月30日辦理。"
        errors = registry.check_date_logic(draft)
        assert len(errors) == 0

    def test_invalid_date_feb_30(self, registry):
        """測試2月30日（不存在的日期）會產生錯誤"""
        draft = "本案訂於114年2月30日辦理。"
        errors = registry.check_date_logic(draft)
        assert len(errors) == 1


# ==================== check_attachment_consistency ====================

class TestCheckAttachmentConsistency:
    """附件一致性檢查器的測試"""

    def test_mention_without_section(self, registry):
        """測試提及附件但缺少附件段落時產生錯誤"""
        draft = "請參閱檢附之資料辦理。\n### 主旨\n某主旨"
        errors = registry.check_attachment_consistency(draft)
        assert len(errors) == 1
        assert "附件" in errors[0]

    def test_mention_with_section_full_width(self, registry):
        """測試提及附件且有附件段落（全形冒號）時不產生錯誤"""
        draft = "請參閱檢附之資料。\n附件：回收指南"
        errors = registry.check_attachment_consistency(draft)
        assert len(errors) == 0

    def test_mention_with_section_half_width(self, registry):
        """測試提及附件且有附件段落（半形冒號）時不產生錯誤"""
        draft = "請參閱附件辦理。\n附件:回收指南"
        errors = registry.check_attachment_consistency(draft)
        assert len(errors) == 0

    def test_no_mention_no_section(self, registry):
        """測試沒有提及附件也沒有附件段落時不產生錯誤"""
        draft = "本案請查照辦理。"
        errors = registry.check_attachment_consistency(draft)
        assert len(errors) == 0

    def test_multiple_attachment_mentions(self, registry):
        """測試多次提及附件但無段落"""
        draft = "檢附報告一份，另有附表二份，請查照。"
        errors = registry.check_attachment_consistency(draft)
        assert len(errors) == 1


# ==================== check_citation_format ====================

class TestCheckCitationFormat:
    """法規引用格式檢查器的測試"""

    def test_missing_book_title_marks(self, registry):
        """測試缺少書名號的法規引用會產生建議"""
        draft = "依據勞動基準法辦理。"
        errors = registry.check_citation_format(draft)
        assert len(errors) == 1
        assert "書名號" in errors[0]
        assert "勞動基準法" in errors[0]

    def test_with_book_title_marks(self, registry):
        """測試有書名號的法規引用不產生建議"""
        draft = "依據《勞動基準法》辦理。"
        errors = registry.check_citation_format(draft)
        assert len(errors) == 0

    def test_regulation_with_article(self, registry):
        """測試法規加條文引用"""
        draft = "依據廢棄物清理法第三條辦理。"
        errors = registry.check_citation_format(draft)
        # 應建議使用書名號
        assert len(errors) >= 1

    def test_no_citation(self, registry):
        """測試沒有法規引用時不產生建議"""
        draft = "本案請查照辦理。"
        errors = registry.check_citation_format(draft)
        assert len(errors) == 0

    def test_ordinance_citation(self, registry):
        """測試條例引用格式"""
        draft = "依據地方制度法施行細則辦理。"
        errors = registry.check_citation_format(draft)
        assert len(errors) >= 1


# ==================== check_doc_integrity ====================

class TestCheckDocIntegrity:
    """文件完整性檢查器的測試"""

    def test_placeholder_detected(self, registry):
        """測試偵測到未填寫的發文字號 placeholder"""
        draft = "發文字號：第______號\n**機關**：測試\n**受文者**：對象\n**速別**：普通\n**發文日期**：今日"
        errors = registry.check_doc_integrity(draft)
        assert any("發文字號" in e for e in errors)

    def test_missing_standard_headers(self, registry):
        """測試缺少標準檔頭欄位"""
        draft = "### 主旨\n測試主旨\n### 說明\n測試說明"
        errors = registry.check_doc_integrity(draft)
        # 應缺少機關、受文者、速別、發文日期
        assert len(errors) >= 4

    def test_complete_headers(self, registry):
        """測試完整的檔頭欄位不產生錯誤"""
        draft = "**機關**：測試機關\n**受文者**：測試單位\n**速別**：普通\n**發文日期**：114年2月18日"
        errors = registry.check_doc_integrity(draft)
        # 不應有檔頭錯誤（但可能有 placeholder 錯誤）
        header_errors = [e for e in errors if "缺少標準檔頭欄位" in e]
        assert len(header_errors) == 0

    def test_partial_headers(self, registry):
        """測試部分檔頭欄位缺失"""
        draft = "**機關**：測試機關\n**受文者**：測試單位"
        errors = registry.check_doc_integrity(draft)
        missing = [e for e in errors if "缺少標準檔頭欄位" in e]
        assert len(missing) == 2  # 缺少速別和發文日期


# ==================== ValidatorRegistry 初始化 ====================

class TestValidatorRegistryInit:
    """ValidatorRegistry 初始化的測試"""

    def test_registry_loads_terms(self, registry):
        """測試註冊表能正常載入（或優雅降級）"""
        # terms 應為 dict（即使字典檔不存在也不會崩潰）
        assert isinstance(registry.terms, dict)

    def test_registry_missing_terms_file(self):
        """測試當術語字典不存在時優雅降級"""
        from unittest.mock import patch

        # Mock open to raise FileNotFoundError
        with patch("builtins.open", side_effect=FileNotFoundError("No such file")):
            reg = ValidatorRegistry()
            assert reg.terms == {}


# ==================== check_date_logic 邊界日期 ====================

class TestCheckDateLogicEdgeCases:
    """日期檢查器的邊界測試"""

    def test_old_date_warning(self, registry):
        """測試超過 2 年的日期產生過舊警告"""
        # 民國 110 年 = 2021 年，距今超過 2 年
        draft = "本案訂於110年1月1日辦理。"
        errors = registry.check_date_logic(draft)
        assert len(errors) == 1
        assert "過舊" in errors[0]

    def test_future_date_warning(self, registry):
        """測試超過未來 1 年的日期產生有誤警告"""
        # 民國 118 年 = 2029 年，超過未來 1 年
        draft = "本案訂於118年6月15日辦理。"
        errors = registry.check_date_logic(draft)
        assert len(errors) == 1
        assert "有誤" in errors[0]

    def test_near_future_date_ok(self, registry):
        """測試近未來的日期不產生警告"""
        # 民國 115 年 = 2026 年（今年或明年），應該不會觸發
        draft = "本案訂於115年6月15日辦理。"
        errors = registry.check_date_logic(draft)
        assert len(errors) == 0
