"""tests/test_lint_cmd.py — lint_cmd 新規則專屬測試

涵蓋：
- 擴充口語化用詞（Round 15 新增 8 個）
- 速別缺失規則（_check_speed_level）
- 主旨結尾用語規則（_check_subject_closing）
- 缺少發文字號規則（_check_doc_number）
- 缺少正本欄規則（_check_main_copy）—— Round 16
- 附件件數未標明規則（_check_attachment_numbering）—— Round 16
- _run_lint 整合行為
"""
import pytest
from src.cli.lint_cmd import (
    _run_lint,
    _check_speed_level,
    _check_subject_closing,
    _check_doc_number,
    _check_main_copy,
    _check_attachment_numbering,
    _INFORMAL_TERMS,
    _SUBJECT_CLOSINGS,
)


# ─────────────────────────────────────────────
# 1. 擴充口語化用詞表
# ─────────────────────────────────────────────

class TestExpandedInformalTerms:
    """Round 15 擴充的 8 個口語化用詞應被偵測到。"""

    @pytest.mark.parametrize("term", [
        "以後", "不過", "同時", "為了", "沒有", "快點", "先前", "有些",
    ])
    def test_new_informal_term_detected(self, term):
        text = f"主旨：{term}請各單位配合辦理。\n說明：依規定。\n"
        issues = _run_lint(text)
        categories = [i["category"] for i in issues]
        assert "口語化用詞" in categories

    @pytest.mark.parametrize("term", [
        "以後", "不過", "同時", "為了", "沒有", "快點", "先前", "有些",
    ])
    def test_new_informal_term_in_dict(self, term):
        assert term in _INFORMAL_TERMS

    def test_total_informal_terms_count(self):
        """口語化用詞表應達 18 個（原 10 + 新增 8）。"""
        assert len(_INFORMAL_TERMS) >= 18

    def test_original_terms_still_present(self):
        """原有 10 個用詞應仍存在（不得被刪除）。"""
        originals = ["所以", "但是", "而且", "因為", "可是", "還有", "已經", "馬上", "大概", "一定要"]
        for term in originals:
            assert term in _INFORMAL_TERMS, f"原有用詞「{term}」不應被移除"


# ─────────────────────────────────────────────
# 2. _check_speed_level — 速別缺失規則
# ─────────────────────────────────────────────

class TestCheckSpeedLevel:

    def test_missing_speed_level_with_receiver(self):
        """含受文者但無速別 → 回報 issue。"""
        text = "受文者：各局處\n主旨：請配合辦理。\n說明：依規定。\n"
        issues = _check_speed_level(text)
        assert len(issues) == 1
        assert issues[0]["category"] == "缺少速別"
        assert "速別" in issues[0]["detail"]

    def test_speed_level_present_no_issue(self):
        """含受文者且有速別 → 無 issue。"""
        text = "受文者：各局處\n速別：普通件\n主旨：請配合。\n說明：依規定。\n"
        assert _check_speed_level(text) == []

    def test_no_receiver_no_speed_required(self):
        """無受文者（如簽呈）→ 不要求速別。"""
        text = "主旨：簽請核示。\n說明：依規定。\n"
        assert _check_speed_level(text) == []

    def test_speed_level_variants(self):
        """最速件、速件各自均可通過檢查。"""
        for speed in ("最速件", "速件", "普通件"):
            text = f"受文者：A機關\n速別：{speed}\n主旨：查照。\n說明：依規定。\n"
            assert _check_speed_level(text) == [], f"速別「{speed}」應通過"


# ─────────────────────────────────────────────
# 3. _check_subject_closing — 主旨結尾用語規則
# ─────────────────────────────────────────────

class TestCheckSubjectClosing:

    def test_missing_closing_phrase(self):
        """主旨無結尾語 → 回報 issue。"""
        text = "受文者：A機關\n主旨：請各單位配合本計畫推動工作。\n說明：依規定。\n"
        issues = _check_subject_closing(text)
        assert len(issues) == 1
        assert issues[0]["category"] == "主旨結尾"

    @pytest.mark.parametrize("closing", ["查照", "照辦", "鑒核", "核示", "備查"])
    def test_valid_closing_phrases(self, closing):
        """含合法結尾語 → 無 issue。"""
        text = f"受文者：A機關\n主旨：請各單位配合，請　{closing}。\n說明：依規定。\n"
        assert _check_subject_closing(text) == []

    def test_no_receiver_skips_check(self):
        """無受文者（簽/令等）→ 不執行主旨結尾檢查。"""
        text = "主旨：簽請核示相關事宜。\n說明：依規定。\n"
        assert _check_subject_closing(text) == []

    def test_no_subject_section_no_crash(self):
        """完全無主旨段落 → 不 crash，回傳空。"""
        text = "受文者：A機關\n說明：依規定。\n"
        result = _check_subject_closing(text)
        assert isinstance(result, list)

    def test_subject_closings_list_complete(self):
        """結尾語清單應涵蓋常見語（至少 5 個）。"""
        assert len(_SUBJECT_CLOSINGS) >= 5


# ─────────────────────────────────────────────
# 4. _check_doc_number — 缺少發文字號規則
# ─────────────────────────────────────────────

class TestCheckDocNumber:

    def test_missing_doc_number(self):
        """含受文者但無字號 → 回報 issue。"""
        text = "受文者：A機關\n主旨：請查照。\n說明：依規定。\n"
        issues = _check_doc_number(text)
        assert len(issues) == 1
        assert issues[0]["category"] == "缺少字號"

    def test_doc_number_via_zihao(self):
        """含「字號」欄位 → 無 issue。"""
        text = "受文者：A機關\n發文字號：北環資字第1140000001號\n主旨：請查照。\n說明：依規定。\n"
        assert _check_doc_number(text) == []

    def test_doc_number_via_zidi(self):
        """含「字第」（嵌入字號）→ 無 issue。"""
        text = "受文者：A機關\n字號：北環資字第1140000001號\n主旨：請查照。\n說明：依規定。\n"
        assert _check_doc_number(text) == []

    def test_no_receiver_no_check(self):
        """無受文者（如簽呈）→ 不要求字號。"""
        text = "主旨：簽請核示。\n說明：依規定。\n"
        assert _check_doc_number(text) == []


# ─────────────────────────────────────────────
# 5. _run_lint 整合測試（確認新規則被呼叫）
# ─────────────────────────────────────────────

class TestRunLintIntegration:

    def test_formal_doc_missing_all_new_fields(self):
        """含受文者但缺速別/字號且主旨無結尾語 → 應有 3 條新規則 issue。"""
        text = "受文者：A機關\n主旨：請各單位配合辦理本計畫。\n說明：依規定。\n"
        issues = _run_lint(text)
        categories = {i["category"] for i in issues}
        assert "缺少速別" in categories
        assert "主旨結尾" in categories
        assert "缺少字號" in categories

    def test_complete_formal_doc_no_new_issues(self):
        """完整正式函文應通過所有新規則檢查（無新規則 issue）。"""
        text = (
            "受文者：各局處\n"
            "速別：普通件\n"
            "發文字號：北環資字第1140000001號\n"
            "主旨：為加強校園資源回收工作，請各校配合辦理，請　查照。\n"
            "說明：依本局114年度計畫辦理。\n"
        )
        issues = _run_lint(text)
        new_categories = {"缺少速別", "主旨結尾", "缺少字號"}
        found_new = {i["category"] for i in issues} & new_categories
        assert found_new == set(), f"完整函文不應觸發新規則，但發現：{found_new}"

    def test_internal_doc_sign_no_new_issues(self):
        """內部簽呈（無受文者）不應觸發速別/字號/主旨結尾規則。"""
        text = "主旨：簽請核示差旅案。\n說明：依規定辦理。\n擬辦：請核示。\n"
        issues = _run_lint(text)
        new_categories = {"缺少速別", "主旨結尾", "缺少字號"}
        found_new = {i["category"] for i in issues} & new_categories
        assert found_new == set()

    def test_new_informal_terms_trigger_in_run_lint(self):
        """_run_lint 應偵測到新增的口語化用詞。"""
        text = "主旨：以後請各單位配合。\n說明：沒有例外。\n"
        issues = _run_lint(text)
        details = " ".join(i["detail"] for i in issues if i["category"] == "口語化用詞")
        assert "以後" in details
        assert "沒有" in details


# ─────────────────────────────────────────────
# 6. _check_main_copy — 缺少正本欄規則
# ─────────────────────────────────────────────

class TestCheckMainCopy:
    """Round 16：外發函文應有「正本：」欄位。"""

    def test_missing_main_copy_with_receiver(self):
        """含受文者但無正本欄 → 回報 issue。"""
        text = "受文者：A機關\n主旨：請查照。\n說明：依規定。\n"
        issues = _check_main_copy(text)
        assert len(issues) == 1
        assert issues[0]["category"] == "缺少正本欄"
        assert "正本" in issues[0]["detail"]

    def test_main_copy_present_no_issue(self):
        """含受文者且有正本欄 → 無 issue。"""
        text = "受文者：A機關\n正本：A機關\n主旨：請查照。\n說明：依規定。\n"
        assert _check_main_copy(text) == []

    def test_no_receiver_no_check(self):
        """無受文者（如簽呈）→ 不要求正本欄。"""
        text = "主旨：簽請核示。\n說明：依規定。\n"
        assert _check_main_copy(text) == []

    def test_main_copy_with_multiple_recipients(self):
        """正本欄含多機關時仍應通過。"""
        text = "受文者：各局處\n正本：A機關、B機關\n主旨：請查照。\n說明：依規定。\n"
        assert _check_main_copy(text) == []


# ─────────────────────────────────────────────
# 7. _check_attachment_numbering — 附件件數規則
# ─────────────────────────────────────────────

class TestCheckAttachmentNumbering:
    """Round 16：提及附件但未標明件數 → 提示。"""

    def test_attachment_mentioned_without_count(self):
        """提及附件但無件數標示 → 回報 issue。"""
        text = "主旨：請查照。\n說明：依規定。\n附件：計畫書。\n"
        issues = _check_attachment_numbering(text)
        assert len(issues) == 1
        assert issues[0]["category"] == "附件件數"

    def test_attachment_with_numeric_count(self):
        """「附件1份」→ 無 issue。"""
        text = "主旨：請查照。\n說明：依規定。\n附件1份：計畫書。\n"
        assert _check_attachment_numbering(text) == []

    def test_attachment_with_total_count(self):
        """「共2件」→ 無 issue。"""
        text = "主旨：請查照。\n說明：依規定。\n附件：共2件。\n"
        assert _check_attachment_numbering(text) == []

    def test_attachment_with_list_reference(self):
        """「如附件清單」→ 無 issue。"""
        text = "主旨：請查照。\n說明：依規定。\n如附件清單所示。\n"
        assert _check_attachment_numbering(text) == []

    def test_attachment_with_ruju_format(self):
        """「如附」→ 無 issue。"""
        text = "主旨：請查照。\n說明：如附。\n"
        assert _check_attachment_numbering(text) == []

    def test_no_attachment_no_issue(self):
        """無附件相關詞 → 無 issue。"""
        text = "主旨：請查照。\n說明：依規定辦理。\n"
        assert _check_attachment_numbering(text) == []

    def test_attachment_table_with_number(self):
        """「附表1」→ 無 issue。"""
        text = "主旨：請查照。\n說明：見附表1。\n"
        assert _check_attachment_numbering(text) == []

    def test_run_lint_includes_main_copy_and_attachment(self):
        """_run_lint 應整合呼叫新兩條規則。"""
        # 缺正本欄 + 附件無件數
        text = "受文者：A機關\n主旨：請查照。\n說明：依規定。\n附件：計畫書。\n"
        issues = _run_lint(text)
        categories = {i["category"] for i in issues}
        assert "缺少正本欄" in categories
        assert "附件件數" in categories

    def test_complete_doc_passes_new_rules(self):
        """含正本欄且附件有件數標示 → 新規則無 issue。"""
        text = (
            "受文者：各局處\n"
            "速別：普通件\n"
            "發文字號：北環資字第1140000001號\n"
            "正本：A機關\n"
            "主旨：為加強校園資源回收工作，請各校配合辦理，請　查照。\n"
            "說明：依本局114年度計畫辦理。\n"
            "附件1份：計畫書。\n"
        )
        issues = _run_lint(text)
        new_categories = {"缺少正本欄", "附件件數"}
        found = {i["category"] for i in issues} & new_categories
        assert found == set(), f"完整函文不應觸發新規則，但發現：{found}"

    def test_unrelated_份_does_not_suppress_issue(self):
        """「3份報告」等無關文字不應讓附件件數檢查誤判通過。"""
        text = "主旨：請查照。\n說明：依3份報告辦理。\n附件：計畫書。\n"
        issues = _check_attachment_numbering(text)
        assert len(issues) == 1
        assert issues[0]["category"] == "附件件數"
