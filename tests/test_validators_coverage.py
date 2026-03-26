"""ValidatorRegistry 全面覆蓋測試 — 涵蓋日期、附件、引用、完整性、口語化、術語等驗證。"""

from datetime import date
from unittest.mock import patch

import pytest

from src.agents.validators import ValidatorRegistry


@pytest.fixture
def vr():
    """回傳 ValidatorRegistry 實例（容許 dictionary.json 不存在）。"""
    return ValidatorRegistry()


# ==================== check_date_logic ====================


class TestCheckDateLogic:
    def test_valid_roc_date(self, vr):
        today = date.today()
        roc_year = today.year - 1911
        text = f"{roc_year}年{today.month}月{today.day}日"
        errors = vr.check_date_logic(text)
        assert errors == []

    def test_roc_year_zero(self, vr):
        # regex 要求 2-3 位數字，所以用 "00年"
        errors = vr.check_date_logic("00年1月1日")
        assert any("民國年份須 >= 1" in e for e in errors)

    def test_roc_year_too_large(self, vr):
        errors = vr.check_date_logic("201年1月1日")
        assert any("民國年份超過 200" in e for e in errors)

    def test_invalid_month(self, vr):
        errors = vr.check_date_logic("114年13月1日")
        assert any("無效日期格式" in e for e in errors)

    def test_invalid_day(self, vr):
        errors = vr.check_date_logic("114年1月32日")
        assert any("無效日期格式" in e for e in errors)

    def test_date_too_old(self, vr):
        errors = vr.check_date_logic("100年1月1日")
        assert any("過舊" in e for e in errors)

    def test_date_too_far_future(self, vr):
        today = date.today()
        future_roc = today.year - 1911 + 2
        text = f"{future_roc}年1月1日"
        errors = vr.check_date_logic(text)
        assert any("有誤" in e for e in errors)

    def test_invalid_date_value_error(self, vr):
        # 2月30日 — valid month/day range check passes but date() raises ValueError
        errors = vr.check_date_logic("114年2月30日")
        assert any("無效日期格式" in e for e in errors)

    def test_no_date_no_errors(self, vr):
        errors = vr.check_date_logic("沒有任何日期的文字")
        assert errors == []

    def test_month_zero(self, vr):
        errors = vr.check_date_logic("114年0月1日")
        assert any("無效日期格式" in e for e in errors)

    def test_day_zero(self, vr):
        errors = vr.check_date_logic("114年1月0日")
        assert any("無效日期格式" in e for e in errors)


# ==================== check_attachment_consistency ====================


class TestCheckAttachmentConsistency:
    def test_mention_without_section(self, vr):
        text = "請參閱附件說明。"
        errors = vr.check_attachment_consistency(text)
        assert any("缺少「附件」段落" in e for e in errors)

    def test_mention_with_section(self, vr):
        text = "請參閱附件說明。\n附件：\n一、測試附件"
        errors = vr.check_attachment_consistency(text)
        assert not any("缺少「附件」段落" in e for e in errors)

    def test_no_mention_no_error(self, vr):
        text = "這是一段正常公文內容，不涉及額外資料。"
        errors = vr.check_attachment_consistency(text)
        assert errors == []

    def test_sequential_attachment_numbers(self, vr):
        text = "附件一、附件二、附件三\n附件："
        errors = vr.check_attachment_consistency(text)
        assert not any("不連續" in e for e in errors)

    def test_skipped_attachment_number(self, vr):
        text = "附件一、附件三\n附件："
        errors = vr.check_attachment_consistency(text)
        assert any("不連續" in e for e in errors)

    def test_attachment_colon_variant(self, vr):
        text = "檢附如附件相關資料。\n附件:\n一、報告書"
        errors = vr.check_attachment_consistency(text)
        assert not any("缺少「附件」段落" in e for e in errors)

    def test_as_attachment_variant(self, vr):
        text = "如附表所示。"
        errors = vr.check_attachment_consistency(text)
        assert any("缺少「附件」段落" in e for e in errors)


# ==================== check_citation_format ====================


class TestCheckCitationFormat:
    def test_citation_without_bookmarks(self, vr):
        text = "依據行政程序法第27條辦理"
        errors = vr.check_citation_format(text)
        assert any("書名號" in e for e in errors)

    def test_citation_with_bookmarks(self, vr):
        text = "依據《行政程序法》第27條辦理"
        errors = vr.check_citation_format(text)
        assert not any("書名號" in e and "行政程序法" in e for e in errors)

    def test_short_bookmark_content(self, vr):
        text = "依據《法》辦理"
        errors = vr.check_citation_format(text)
        assert any("可能不完整" in e for e in errors)

    def test_no_citation_no_error(self, vr):
        text = "普通文字，沒有法規引用。"
        errors = vr.check_citation_format(text)
        assert errors == []

    def test_many_citations_capped(self, vr):
        lines = []
        for i in range(10):
            lines.append(f"依據第{i}號辦法辦理")
        text = "\n".join(lines)
        errors = vr.check_citation_format(text)
        # 應有最多 5+1 個錯誤（_MAX_CITATION_WARNINGS + 省略訊息）
        assert len(errors) <= 6

    def test_proper_bookmark_no_error(self, vr):
        text = "依據《行政程序法施行細則》辦理"
        errors = vr.check_citation_format(text)
        assert not any("書名號" in e for e in errors)


# ==================== check_doc_integrity ====================


class TestCheckDocIntegrity:
    def test_placeholder_detected(self, vr):
        text = "發文字號：府環______號"
        errors = vr.check_doc_integrity(text)
        assert any("發文字號尚未填寫" in e for e in errors)

    def test_missing_headers(self, vr):
        text = "# 函\n**機關**：測試\n### 主旨\n測試"
        errors = vr.check_doc_integrity(text)
        assert any("受文者" in e for e in errors)
        assert any("速別" in e for e in errors)
        assert any("發文日期" in e for e in errors)

    def test_all_headers_present(self, vr):
        text = "**機關**：A\n**受文者**：B\n**速別**：普通\n**發文日期**：114年1月1日"
        errors = vr.check_doc_integrity(text)
        assert not any("缺少標準檔頭欄位" in e for e in errors)

    def test_no_placeholder_no_error(self, vr):
        text = "**機關**：A\n**受文者**：B\n**速別**：普通\n**發文日期**：114年1月1日"
        errors = vr.check_doc_integrity(text)
        assert not any("發文字號尚未填寫" in e for e in errors)


# ==================== check_citation_level ====================


class TestCheckCitationLevel:
    def test_pending_citation_marker(self, vr):
        text = "依據某法辦理。【待補依據】"
        errors = vr.check_citation_level(text)
        assert any("待補依據" in e for e in errors)

    def test_no_level_a_in_refs(self, vr):
        text = "### 參考來源\n[^1]: [Level B] 某報導"
        errors = vr.check_citation_level(text)
        assert any("Level A" in e for e in errors)

    def test_has_level_a_in_refs(self, vr):
        text = "### 參考來源\n[^1]: [Level A] 行政院公報"
        errors = vr.check_citation_level(text)
        assert not any("缺少 Level A" in e for e in errors)

    def test_yiju_without_citation_tag(self, vr):
        text = "依據行政程序法第27條辦理，不附引用。"
        errors = vr.check_citation_level(text)
        assert any("缺少引用標記" in e for e in errors)

    def test_yiju_with_citation_tag(self, vr):
        text = "依據行政程序法第27條辦理[^1]。"
        errors = vr.check_citation_level(text)
        assert not any("缺少引用標記" in e for e in errors)

    def test_no_refs_section_no_level_a_error(self, vr):
        text = "普通文字。"
        errors = vr.check_citation_level(text)
        assert not any("Level A" in e for e in errors)


# ==================== check_evidence_presence ====================


class TestCheckEvidencePresence:
    def test_no_ref_section(self, vr):
        text = "文字，無參考來源段落。"
        errors = vr.check_evidence_presence(text)
        assert any("缺少「參考來源」段落" in e for e in errors)

    def test_no_footnote(self, vr):
        text = "### 參考來源\n沒有標記。"
        errors = vr.check_evidence_presence(text)
        assert any("無任何引用標記" in e for e in errors)

    def test_has_ref_and_footnote(self, vr):
        text = "依據某法[^1]。\n### 參考來源\n[^1]: 來源"
        errors = vr.check_evidence_presence(text)
        assert errors == []


# ==================== check_citation_integrity ====================


class TestCheckCitationIntegrity:
    def test_orphan_reference(self, vr):
        text = "依據某法[^1]。依據某規[^2]。\n### 參考來源\n[^1]: 行政院公報"
        errors = vr.check_citation_integrity(text)
        assert any("孤兒引用" in e and "[^2]" in e for e in errors)

    def test_unused_definition(self, vr):
        text = "正文。\n### 參考來源\n[^1]: 來源一\n[^2]: 來源二"
        errors = vr.check_citation_integrity(text)
        assert any("未使用定義" in e for e in errors)

    def test_matched_refs(self, vr):
        text = "引用[^1]。\n### 參考來源\n[^1]: 來源"
        errors = vr.check_citation_integrity(text)
        assert errors == []

    def test_no_refs_no_error(self, vr):
        text = "普通文字。"
        errors = vr.check_citation_integrity(text)
        assert errors == []


# ==================== check_colloquial_language ====================


class TestCheckColloquialLanguage:
    def test_detect_colloquial_with_suggestion(self, vr):
        text = "請幫我處理。"
        errors = vr.check_colloquial_language(text)
        assert any("幫我" in e and "請協助" in e for e in errors)

    def test_detect_colloquial_particle(self, vr):
        text = "知道了啦。"
        errors = vr.check_colloquial_language(text)
        assert any("啦" in e and "不應出現" in e for e in errors)

    def test_formal_text_no_error(self, vr):
        text = "謹依規定辦理。"
        errors = vr.check_colloquial_language(text)
        assert errors == []

    def test_ok_detected(self, vr):
        text = "這樣OK嗎"
        errors = vr.check_colloquial_language(text)
        assert any("OK" in e for e in errors)


# ==================== check_terminology ====================


class TestCheckTerminology:
    def test_outdated_agency_detected(self, vr):
        text = "行政院環境保護署公告"
        errors = vr.check_terminology(text)
        assert any("環境部" in e for e in errors)

    def test_multiple_outdated(self, vr):
        text = "環保署與農委會聯合公告"
        errors = vr.check_terminology(text)
        assert any("環境部" in e for e in errors)
        assert any("農業部" in e for e in errors)

    def test_current_agency_no_error(self, vr):
        text = "環境部公告"
        errors = vr.check_terminology(text)
        assert errors == []

    def test_no_duplicates(self, vr):
        text = "環保署和環保署辦理"
        errors = vr.check_terminology(text)
        # 相同舊名只報一次
        count = sum(1 for e in errors if "環保署" in e)
        assert count == 1


# ==================== ValidatorRegistry 初始化 ====================


class TestValidatorRegistryInit:
    def test_init_without_dictionary(self):
        """術語字典不存在時 terms 為空字典"""
        vr = ValidatorRegistry()
        assert isinstance(vr.terms, dict)

    @patch("builtins.open", side_effect=OSError("read error"))
    def test_init_with_read_error(self, mock_open):
        """讀取失敗時 terms 回退為空字典"""
        vr = ValidatorRegistry()
        assert vr.terms == {}
