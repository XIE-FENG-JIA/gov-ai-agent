"""
validators.py 的單元測試
測試所有自訂驗證器函數的正確性和邊界情況
"""
import pytest
from src.agents.validators import ValidatorRegistry


def _d(issue: dict) -> str:
    """從結構化驗證問題字典中取出 description 欄位，方便斷言。"""
    return issue["description"]


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
        assert "無效日期" in _d(errors[0])

    def test_invalid_date_day_32(self, registry):
        """測試無效日期（32日）會產生錯誤"""
        draft = "本案訂於114年2月32日辦理。"
        errors = registry.check_date_logic(draft)
        assert len(errors) == 1
        assert "無效日期" in _d(errors[0])

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
        assert "附件" in _d(errors[0])

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
        assert "書名號" in _d(errors[0])
        assert "勞動基準法" in _d(errors[0])

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
        assert any("發文字號" in _d(e) for e in errors)

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
        header_errors = [e for e in errors if "缺少標準檔頭欄位" in _d(e)]
        assert len(header_errors) == 0

    def test_partial_headers(self, registry):
        """測試部分檔頭欄位缺失"""
        draft = "**機關**：測試機關\n**受文者**：測試單位"
        errors = registry.check_doc_integrity(draft)
        missing = [e for e in errors if "缺少標準檔頭欄位" in _d(e)]
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
        assert "過舊" in _d(errors[0])

    def test_future_date_warning(self, registry):
        """測試超過未來 1 年的日期產生有誤警告"""
        # 民國 118 年 = 2029 年，超過未來 1 年
        draft = "本案訂於118年6月15日辦理。"
        errors = registry.check_date_logic(draft)
        assert len(errors) == 1
        assert "有誤" in _d(errors[0])

    def test_near_future_date_ok(self, registry):
        """測試近未來的日期不產生警告"""
        # 民國 115 年 = 2026 年（今年或明年），應該不會觸發
        draft = "本案訂於115年6月15日辦理。"
        errors = registry.check_date_logic(draft)
        assert len(errors) == 0

    def test_roc_year_zero(self, registry):
        """測試民國 0 年（不存在的年份，轉換為西元 1911）會被標記過舊"""
        # 注意: regex 要求 2-3 位數字，所以 "0年" 不會被匹配到
        # 但 "00年" 會匹配 → AD 1911，距今超過 2 年
        draft = "本案訂於00年1月1日辦理。"
        errors = registry.check_date_logic(draft)
        if errors:
            assert any("過舊" in _d(e) for e in errors)

    def test_roc_year_one(self, registry):
        """測試民國 01 年（西元 1912 年）會被標記過舊"""
        draft = "本案訂於01年6月15日辦理。"
        errors = registry.check_date_logic(draft)
        assert len(errors) == 1
        assert "過舊" in _d(errors[0])

    def test_roc_year_999_far_future(self, registry):
        """測試民國 999 年（西元 2910 年）會被標記有誤"""
        draft = "本案訂於999年1月1日辦理。"
        errors = registry.check_date_logic(draft)
        assert len(errors) == 1
        assert "有誤" in _d(errors[0])

    def test_invalid_month_zero(self, registry):
        """測試月份為 0 產生無效日期錯誤"""
        draft = "本案訂於114年0月15日辦理。"
        errors = registry.check_date_logic(draft)
        assert len(errors) == 1
        assert "無效日期" in _d(errors[0])

    def test_invalid_day_zero(self, registry):
        """測試日期為 0 產生無效日期錯誤"""
        draft = "本案訂於114年3月0日辦理。"
        errors = registry.check_date_logic(draft)
        assert len(errors) == 1
        assert "無效日期" in _d(errors[0])

    def test_leap_year_feb_29_valid(self, registry):
        """測試閏年 2 月 29 日不產生錯誤（民國 113 年 = 2024 閏年）"""
        draft = "本案訂於113年2月29日辦理。"
        errors = registry.check_date_logic(draft)
        # 2024 年距今 2 年，可能觸發「過舊」但不應觸發「無效日期」
        invalid_errors = [e for e in errors if "無效日期" in _d(e)]
        assert len(invalid_errors) == 0

    def test_non_leap_year_feb_29_invalid(self, registry):
        """測試非閏年 2 月 29 日產生無效日期（民國 114 年 = 2025 非閏年）"""
        draft = "本案訂於114年2月29日辦理。"
        errors = registry.check_date_logic(draft)
        assert any("無效日期" in _d(e) for e in errors)

    def test_multiple_dates_mixed_validity(self, registry):
        """測試多個日期中有合法和不合法的混合"""
        draft = "本案訂於115年3月15日至115年13月1日辦理。"
        errors = registry.check_date_logic(draft)
        # 第二個日期月份 13 不合法
        assert any("無效日期" in _d(e) for e in errors)


# ==================== BUG-007: 西元年份不應被誤匹配為 ROC 年份 ====================

class TestCheckDateLogicADYearFilter:
    """確保 4 位數西元年份不被誤匹配為 ROC 年份"""

    def test_ad_year_not_matched(self, registry):
        """4 位數西元年份（如 2025年1月1日）不應被匹配為 ROC 年份"""
        draft = "西元2025年1月1日辦理。"
        errors = registry.check_date_logic(draft)
        # 2025 的最後 3 位 "025" 不應被匹配（前面有數字 2）
        assert len(errors) == 0

    def test_ad_year_full_context(self, registry):
        """混合包含西元年份和 ROC 年份時只匹配 ROC"""
        draft = "2024年已過去，本案訂於114年3月15日辦理。"
        errors = registry.check_date_logic(draft)
        # 只有 "114年3月15日" 是合法 ROC 日期，"2024年" 不應被匹配
        # 114年3月15日 = 2025年3月15日，近期日期不應有錯誤
        assert len(errors) == 0

    def test_roc_year_still_works(self, registry):
        """正常的 2-3 位 ROC 年份仍然被正確匹配"""
        draft = "本案訂於114年6月15日辦理。"
        errors = registry.check_date_logic(draft)
        assert len(errors) == 0

    def test_roc_year_at_line_start(self, registry):
        """行首的 ROC 年份仍然被匹配"""
        draft = "114年3月15日辦理。"
        errors = registry.check_date_logic(draft)
        assert len(errors) == 0


# ==================== check_citation_integrity ====================

class TestCheckCitationIntegrity:
    """引用完整性檢查器的測試"""

    def test_orphan_reference(self, registry):
        """測試孤兒引用：文中引用了 [^1] 但無定義"""
        draft = "依據相關法規辦理[^1]。\n### 參考來源\n（無定義）"
        errors = registry.check_citation_integrity(draft)
        assert any("孤兒引用" in _d(e) and "[^1]" in _d(e) for e in errors)

    def test_unused_definition(self, registry):
        """測試未使用定義：定義了 [^2] 但文中未引用"""
        draft = "依據相關法規辦理[^1]。\n### 參考來源\n[^1]: 來源一\n[^2]: 來源二"
        errors = registry.check_citation_integrity(draft)
        assert any("未使用定義" in _d(e) and "[^2]" in _d(e) for e in errors)

    def test_all_matched(self, registry):
        """測試所有引用都有對應定義，不產生錯誤"""
        draft = "依據法規[^1]及規定[^2]辦理。\n### 參考來源\n[^1]: 來源一\n[^2]: 來源二"
        errors = registry.check_citation_integrity(draft)
        assert len(errors) == 0

    def test_no_references(self, registry):
        """測試無任何引用標記時不產生錯誤"""
        draft = "本案請查照辦理。"
        errors = registry.check_citation_integrity(draft)
        assert len(errors) == 0

    def test_multiple_orphans_and_unused(self, registry):
        """測試同時有多個孤兒引用和未使用定義"""
        draft = "引用[^1]和[^3]。\n### 參考來源\n[^1]: 來源一\n[^2]: 來源二\n[^4]: 來源四"
        errors = registry.check_citation_integrity(draft)
        orphans = [e for e in errors if "孤兒引用" in _d(e)]
        unused = [e for e in errors if "未使用定義" in _d(e)]
        assert len(orphans) == 1  # [^3] 是孤兒
        assert len(unused) == 2  # [^2] 和 [^4] 未使用

    def test_definition_not_counted_as_inline(self, registry):
        """測試定義行的 [^n]: 不被計為行內引用"""
        draft = "### 參考來源\n[^1]: 某法規公報\n[^2]: 某行政命令"
        errors = registry.check_citation_integrity(draft)
        # 兩個定義都未在文中引用
        unused = [e for e in errors if "未使用定義" in _d(e)]
        assert len(unused) == 2


# ==================== check_terminology ====================

class TestCheckTerminology:
    """術語（機關名稱）檢查器的測試"""

    def test_outdated_epa(self, registry):
        """測試偵測過時的「環保署」"""
        draft = "依據環保署公告辦理。"
        errors = registry.check_terminology(draft)
        assert any("環保署" in _d(e) and "環境部" in _d(e) for e in errors)

    def test_outdated_council_of_agriculture(self, registry):
        """測試偵測過時的「農委會」"""
        draft = "農委會已於日前發布通知。"
        errors = registry.check_terminology(draft)
        assert any("農委會" in _d(e) and "農業部" in _d(e) for e in errors)

    def test_outdated_tourism_bureau(self, registry):
        """測試偵測過時的「觀光局」"""
        draft = "交通部觀光局辦理觀光推廣活動。"
        errors = registry.check_terminology(draft)
        assert any("觀光局" in _d(e) or "交通部觀光局" in _d(e) for e in errors)

    def test_no_outdated_terms(self, registry):
        """測試無過時名稱時不產生警告"""
        draft = "依據環境部公告辦理。"
        errors = registry.check_terminology(draft)
        assert len(errors) == 0

    def test_multiple_outdated_terms(self, registry):
        """測試同時出現多個過時名稱"""
        draft = "環保署與農委會聯合辦理。"
        errors = registry.check_terminology(draft)
        assert len(errors) >= 2

    def test_outdated_most(self, registry):
        """測試偵測過時的「科技部」"""
        draft = "科技部補助研究計畫。"
        errors = registry.check_terminology(draft)
        assert any("科技部" in _d(e) and "國家科學及技術委員會" in _d(e) for e in errors)

    def test_outdated_highway_bureau(self, registry):
        """測試偵測過時的「公路總局」"""
        draft = "交通部公路總局核發牌照。"
        errors = registry.check_terminology(draft)
        assert any("公路總局" in _d(e) or "交通部公路總局" in _d(e) for e in errors)


# ==================== check_attachment_consistency 增強測試 ====================

class TestCheckAttachmentConsistencyEnhanced:
    """附件一致性檢查器增強功能的測試"""

    def test_variant_ru_fu_jian(self, registry):
        """測試「如附件」變體被偵測"""
        draft = "相關資料如附件，請查照。"
        errors = registry.check_attachment_consistency(draft)
        assert any("附件" in _d(e) for e in errors)

    def test_variant_ru_fu_biao(self, registry):
        """測試「如附表」變體被偵測"""
        draft = "統計數據如附表所示。"
        errors = registry.check_attachment_consistency(draft)
        assert any("附件" in _d(e) or "附表" in _d(e) for e in errors)

    def test_attachment_numbering_skip(self, registry):
        """測試附件編號跳號偵測"""
        draft = "附件一、附件三\n附件：相關資料"
        errors = registry.check_attachment_consistency(draft)
        assert any("不連續" in _d(e) for e in errors)

    def test_attachment_numbering_continuous(self, registry):
        """測試附件編號連續不產生錯誤"""
        draft = "附件一、附件二、附件三\n附件：相關資料"
        errors = registry.check_attachment_consistency(draft)
        numbering_errors = [e for e in errors if "不連續" in _d(e)]
        assert len(numbering_errors) == 0

    def test_attachment_with_section_no_error(self, registry):
        """測試有附件段落且「檢附如附件」不產生缺段落錯誤"""
        draft = "檢附如附件，請查照。\n附件：會議紀錄"
        errors = registry.check_attachment_consistency(draft)
        section_errors = [e for e in errors if "缺少" in _d(e)]
        assert len(section_errors) == 0


# ==================== check_citation_format 增強測試 ====================

class TestCheckCitationFormatEnhanced:
    """法規引用格式檢查器增強功能的測試"""

    def test_rule_suffix_detected(self, registry):
        """測試「規則」後綴被偵測"""
        draft = "依據海關進口貨物查驗規則辦理。"
        errors = registry.check_citation_format(draft)
        assert any("書名號" in _d(e) for e in errors)

    def test_incomplete_book_title(self, registry):
        """測試書名號內容過短被警告"""
        draft = "依據《法》辦理。"
        errors = registry.check_citation_format(draft)
        # "法" 只有 1 個字且不以法規後綴結尾（太短），應提示
        assert any("可能不完整" in _d(e) for e in errors)

    def test_proper_book_title_no_warning(self, registry):
        """測試正確的書名號引用不產生警告"""
        draft = "依據《勞動基準法》辦理。"
        errors = registry.check_citation_format(draft)
        assert len(errors) == 0

    def test_guideline_suffix(self, registry):
        """測試「綱要」後綴被偵測"""
        draft = "依據國家發展綱要辦理。"
        errors = registry.check_citation_format(draft)
        assert any("書名號" in _d(e) for e in errors)

    def test_procedure_suffix(self, registry):
        """測試「規程」後綴被偵測"""
        draft = "依據船員服務規程辦理。"
        errors = registry.check_citation_format(draft)
        assert any("書名號" in _d(e) for e in errors)


# ==================== 結構化回傳格式驗證 ====================

class TestStructuredIssueFormat:
    """驗證所有驗證器回傳結構化字典格式，含 suggestion 欄位。"""

    def test_date_issue_has_suggestion(self, registry):
        """日期錯誤應包含具體修正建議"""
        errors = registry.check_date_logic("本案訂於114年13月1日辦理。")
        assert len(errors) == 1
        assert errors[0]["suggestion"] is not None
        assert "月份" in errors[0]["suggestion"]

    def test_attachment_issue_has_suggestion(self, registry):
        """附件缺失應建議新增附件段落"""
        errors = registry.check_attachment_consistency("請參閱附件辦理。")
        assert len(errors) == 1
        assert errors[0]["suggestion"] is not None
        assert "新增" in errors[0]["suggestion"]

    def test_citation_format_has_suggestion(self, registry):
        """法規引用格式應建議加書名號"""
        errors = registry.check_citation_format("依據勞動基準法辦理。")
        assert len(errors) == 1
        assert errors[0]["suggestion"] is not None
        assert "《勞動基準法》" in errors[0]["suggestion"]

    def test_doc_integrity_has_suggestion(self, registry):
        """缺失欄位應建議新增"""
        errors = registry.check_doc_integrity("### 主旨\n測試")
        assert len(errors) >= 1
        for e in errors:
            assert e["suggestion"] is not None

    def test_colloquial_has_suggestion(self, registry):
        """口語化用詞應建議具體替換"""
        errors = registry.check_colloquial_language("請幫我處理。")
        assert len(errors) >= 1
        assert errors[0]["suggestion"] is not None
        assert "將" in errors[0]["suggestion"]

    def test_terminology_has_suggestion(self, registry):
        """過時機關名稱應建議替換為新名"""
        errors = registry.check_terminology("依據環保署公告辦理。")
        assert len(errors) >= 1
        assert errors[0]["suggestion"] is not None
        assert "環境部" in errors[0]["suggestion"]

    def test_citation_integrity_orphan_has_suggestion(self, registry):
        """孤兒引用應建議新增定義"""
        errors = registry.check_citation_integrity("引用[^1]。\n### 參考來源\n無")
        orphans = [e for e in errors if "孤兒引用" in _d(e)]
        assert len(orphans) == 1
        assert orphans[0]["suggestion"] is not None
        assert "[^1]" in orphans[0]["suggestion"]

    def test_evidence_presence_has_suggestion(self, registry):
        """缺少參考來源應建議新增段落"""
        errors = registry.check_evidence_presence("本案請查照辦理。")
        assert len(errors) >= 1
        for e in errors:
            assert e["suggestion"] is not None

    def test_all_issues_have_required_keys(self, registry):
        """所有回傳的 issue 字典都應包含 description、location、suggestion 三個 key"""
        draft = "幫我依據勞動基準法辦理。環保署公告。附件如下。"
        all_errors = []
        all_errors.extend(registry.check_colloquial_language(draft))
        all_errors.extend(registry.check_citation_format(draft))
        all_errors.extend(registry.check_terminology(draft))
        all_errors.extend(registry.check_attachment_consistency(draft))
        assert len(all_errors) >= 3
        for e in all_errors:
            assert "description" in e, f"缺少 description: {e}"
            assert "location" in e, f"缺少 location: {e}"
            assert "suggestion" in e, f"缺少 suggestion: {e}"
