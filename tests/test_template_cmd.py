"""template_cmd 測試 — 範本清單、公類範本、--list 功能、--generate pipeline。"""
import pytest
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock

from src.cli.template_cmd import template, _TEMPLATES, _TEMPLATE_CATEGORIES, _show_template_list, _launch_generate
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

    def test_template_hints_generate_flag(self):
        """正常顯示範本時應提示 --generate 快速入口。"""
        result = runner.invoke(app, ["template", "函"])
        assert result.exit_code == 0
        assert "--generate" in result.output


# ============================================================
# --generate pipeline 旗標
# ============================================================

class TestTemplateGenerateFlag:
    """驗證 --generate 旗標觸發 template → generate → lint pipeline。"""

    def _mock_run_ok(self):
        m = MagicMock()
        m.returncode = 0
        return m

    def test_generate_flag_invokes_subprocess(self):
        """--generate 應呼叫 subprocess.run。"""
        with patch("src.cli.template_cmd.subprocess.run", return_value=self._mock_run_ok()) as mock_run:
            result = runner.invoke(app, ["template", "函", "--generate"])
        assert result.exit_code == 0
        mock_run.assert_called_once()

    def test_generate_flag_passes_from_file(self):
        """subprocess 命令中應包含 --from-file。"""
        with patch("src.cli.template_cmd.subprocess.run", return_value=self._mock_run_ok()) as mock_run:
            runner.invoke(app, ["template", "函", "--generate"])
        cmd = mock_run.call_args[0][0]
        assert "--from-file" in cmd

    def test_generate_flag_passes_default_output(self):
        """未指定 --gen-output 時應傳 output.docx。"""
        with patch("src.cli.template_cmd.subprocess.run", return_value=self._mock_run_ok()) as mock_run:
            runner.invoke(app, ["template", "函", "--generate"])
        cmd = mock_run.call_args[0][0]
        assert "--output" in cmd
        output_idx = cmd.index("--output")
        assert cmd[output_idx + 1] == "output.docx"

    def test_generate_flag_respects_gen_output(self):
        """--gen-output 應轉發至 subprocess --output。"""
        with patch("src.cli.template_cmd.subprocess.run", return_value=self._mock_run_ok()) as mock_run:
            runner.invoke(app, ["template", "函", "--generate", "--gen-output", "函文.docx"])
        cmd = mock_run.call_args[0][0]
        output_idx = cmd.index("--output")
        assert cmd[output_idx + 1] == "函文.docx"

    def test_generate_flag_respects_gen_preview(self):
        """--gen-preview 應在 subprocess cmd 中帶 --preview。"""
        with patch("src.cli.template_cmd.subprocess.run", return_value=self._mock_run_ok()) as mock_run:
            runner.invoke(app, ["template", "函", "--generate", "--gen-preview"])
        cmd = mock_run.call_args[0][0]
        assert "--preview" in cmd

    def test_generate_flag_respects_gen_skip_review(self):
        """--gen-skip-review 應在 subprocess cmd 中帶 --skip-review。"""
        with patch("src.cli.template_cmd.subprocess.run", return_value=self._mock_run_ok()) as mock_run:
            runner.invoke(app, ["template", "函", "--generate", "--gen-skip-review"])
        cmd = mock_run.call_args[0][0]
        assert "--skip-review" in cmd

    def test_generate_flag_respects_gen_no_lint(self):
        """--gen-no-lint 應在 subprocess cmd 中帶 --no-lint。"""
        with patch("src.cli.template_cmd.subprocess.run", return_value=self._mock_run_ok()) as mock_run:
            runner.invoke(app, ["template", "函", "--generate", "--gen-no-lint"])
        cmd = mock_run.call_args[0][0]
        assert "--no-lint" in cmd

    def test_generate_flag_without_flags_no_optional_args(self):
        """未指定 preview/skip-review/no-lint 時 subprocess cmd 不含這些旗標。"""
        with patch("src.cli.template_cmd.subprocess.run", return_value=self._mock_run_ok()) as mock_run:
            runner.invoke(app, ["template", "函", "--generate"])
        cmd = mock_run.call_args[0][0]
        assert "--preview" not in cmd
        assert "--skip-review" not in cmd
        assert "--no-lint" not in cmd

    def test_generate_flag_cleans_up_temp_file(self):
        """subprocess 執行後暫存檔應被刪除。"""
        captured_paths = []

        def fake_run(cmd, **kwargs):
            # 擷取 --from-file 後的路徑
            idx = cmd.index("--from-file")
            captured_paths.append(cmd[idx + 1])
            m = MagicMock()
            m.returncode = 0
            return m

        with patch("src.cli.template_cmd.subprocess.run", side_effect=fake_run):
            runner.invoke(app, ["template", "函", "--generate"])

        assert len(captured_paths) == 1
        import os
        assert not os.path.exists(captured_paths[0]), "暫存檔未被清除"

    def test_generate_flag_not_set_no_subprocess(self):
        """不帶 --generate 時不應呼叫 subprocess.run。"""
        with patch("src.cli.template_cmd.subprocess.run") as mock_run:
            result = runner.invoke(app, ["template", "函"])
        assert result.exit_code == 0
        mock_run.assert_not_called()

    def test_generate_flag_nonzero_returncode_exits(self):
        """subprocess returncode != 0 時 CLI 應以相同 code 退出。"""
        m = MagicMock()
        m.returncode = 2
        with patch("src.cli.template_cmd.subprocess.run", return_value=m):
            result = runner.invoke(app, ["template", "函", "--generate"])
        assert result.exit_code == 2

    def test_launch_generate_writes_template_content(self):
        """_launch_generate 應將 template_content 寫入暫存檔供 generate 讀取。"""
        written_contents = []

        def fake_run(cmd, **kwargs):
            idx = cmd.index("--from-file")
            path = cmd[idx + 1]
            with open(path, encoding="utf-8") as f:
                written_contents.append(f.read())
            m = MagicMock()
            m.returncode = 0
            return m

        with patch("src.cli.template_cmd.subprocess.run", side_effect=fake_run):
            _launch_generate("測試範本內容", "out.docx")

        assert len(written_contents) == 1
        assert "測試範本內容" in written_contents[0]
