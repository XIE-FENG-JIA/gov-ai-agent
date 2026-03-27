"""template_cmd 測試 — 範本清單、公類範本、--list 功能。"""
import pytest
from typer.testing import CliRunner
from unittest.mock import patch

from src.cli.template_cmd import template, _TEMPLATES, _TEMPLATE_CATEGORIES, _show_template_list
from src.cli.main import app

runner = CliRunner()


# ============================================================
# 基本範本存取
# ============================================================

class TestExistingTemplates:
    """確認原有 12 種範本不受影響。"""

    @pytest.mark.parametrize("doc_type", [
        "函", "公告", "簽", "書函", "令",
        "開會通知單", "會勘通知單", "公務電話紀錄",
        "手令", "箋函", "呈", "咨",
    ])
    def test_original_templates_still_present(self, doc_type):
        assert doc_type in _TEMPLATES

    def test_total_template_count(self):
        # 原 12 + 新增 4 = 16
        assert len(_TEMPLATES) == 16

    def test_han_template_has_subject(self):
        assert "### 主旨" in _TEMPLATES["函"]

    def test_gonggao_template_has_yi_ju(self):
        assert "### 依據" in _TEMPLATES["公告"]


# ============================================================
# 新增「公」類範本內容驗證
# ============================================================

class TestGongTypeTemplates:
    """驗證 4 個新增的公類範本格式正確。"""

    def test_gong_shi_present(self):
        assert "公示" in _TEMPLATES

    def test_gong_shi_songda_present(self):
        assert "公示送達" in _TEMPLATES

    def test_gov_info_disclosure_present(self):
        assert "政府資訊公開" in _TEMPLATES

    def test_jianbian_present(self):
        assert "簡便行文表" in _TEMPLATES

    def test_gong_shi_has_yi_jian_qi_jian(self):
        content = _TEMPLATES["公示"]
        assert "公示期間" in content
        assert "意見" in content

    def test_gong_shi_has_lian_luo_chuang_kou(self):
        assert "聯絡窗口" in _TEMPLATES["公示"]

    def test_gong_shi_songda_cites_xing_zheng_cheng_xu_fa(self):
        assert "行政程序法第78條" in _TEMPLATES["公示送達"]

    def test_gong_shi_songda_has_20_days(self):
        # 行政程序法規定公示送達 20 日發生效力
        assert "20日" in _TEMPLATES["公示送達"]

    def test_gov_info_disclosure_cites_law(self):
        assert "政府資訊公開法" in _TEMPLATES["政府資訊公開"]

    def test_gov_info_disclosure_has_su_yuan_route(self):
        # 應告知救濟途徑
        assert "訴願" in _TEMPLATES["政府資訊公開"]

    def test_jianbian_has_disclaimer(self):
        # 簡便行文表應有使用限制說明
        assert "正式公文行為" in _TEMPLATES["簡便行文表"]

    def test_jianbian_has_shi_you(self):
        assert "### 事由" in _TEMPLATES["簡便行文表"]


# ============================================================
# 分類對應表
# ============================================================

class TestTemplateCategories:
    """驗證分類對應表正確。"""

    def test_public_category_exists(self):
        assert "公示與資訊公開" in _TEMPLATE_CATEGORIES

    def test_public_category_has_four_types(self):
        assert len(_TEMPLATE_CATEGORIES["公示與資訊公開"]) == 4

    def test_all_categorized_types_in_templates(self):
        for types in _TEMPLATE_CATEGORIES.values():
            for t in types:
                assert t in _TEMPLATES, f"分類中的 {t!r} 未在 _TEMPLATES 中"

    def test_all_templates_in_categories(self):
        categorized = {t for types in _TEMPLATE_CATEGORIES.values() for t in types}
        for key in _TEMPLATES:
            assert key in categorized, f"{key!r} 未被分類"


# ============================================================
# CLI —— template 顯示
# ============================================================

class TestTemplateCLI:
    """CLI 整合測試。"""

    def test_show_gong_shi_template(self):
        result = runner.invoke(app, ["template", "公示"])
        assert result.exit_code == 0
        assert "公示" in result.output

    def test_show_gong_shi_songda_template(self):
        result = runner.invoke(app, ["template", "公示送達"])
        assert result.exit_code == 0
        assert "公示送達" in result.output

    def test_show_gov_info_template(self):
        result = runner.invoke(app, ["template", "政府資訊公開"])
        assert result.exit_code == 0
        assert "政府資訊公開" in result.output

    def test_show_jianbian_template(self):
        result = runner.invoke(app, ["template", "簡便行文表"])
        assert result.exit_code == 0
        assert "簡便行文表" in result.output

    def test_unknown_type_exits_1(self):
        result = runner.invoke(app, ["template", "不存在類型"])
        assert result.exit_code == 1
        assert "錯誤" in result.output

    def test_unknown_type_suggests_list(self):
        result = runner.invoke(app, ["template", "不存在類型"])
        assert "--list" in result.output

    def test_list_flag_shows_all_categories(self):
        result = runner.invoke(app, ["template", "--list"])
        assert result.exit_code == 0
        assert "公示與資訊公開" in result.output
        assert "正式公文" in result.output

    def test_list_flag_shows_total_count(self):
        result = runner.invoke(app, ["template", "--list"])
        assert "16" in result.output  # 共 16 種範本

    def test_list_flag_shows_command_hint(self):
        result = runner.invoke(app, ["template", "--list"])
        assert "gov-ai template" in result.output

    def test_output_flag_writes_file(self, tmp_path):
        outfile = tmp_path / "公示.md"
        result = runner.invoke(app, ["template", "公示", "-o", str(outfile)])
        assert result.exit_code == 0
        assert outfile.exists()
        content = outfile.read_text(encoding="utf-8")
        assert "公示" in content
