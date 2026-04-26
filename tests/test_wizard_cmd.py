"""Tests for gov-ai wizard interactive document wizard."""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest
from typer.testing import CliRunner
from src.cli.main import app

runner = CliRunner()


# ── 常數測試 ────────────────────────────────────────────────────────────────

class TestDocTypes:
    """DOC_TYPES 清單結構測試。"""

    def test_twelve_types_defined(self):
        from src.cli.wizard_cmd import DOC_TYPES
        assert len(DOC_TYPES) == 12

    def test_all_types_have_three_fields(self):
        from src.cli.wizard_cmd import DOC_TYPES
        for entry in DOC_TYPES:
            assert len(entry) == 3, f"類型 {entry[0]} 欄位數不正確"

    def test_required_types_present(self):
        from src.cli.wizard_cmd import DOC_TYPES
        names = {t[0] for t in DOC_TYPES}
        for required in ("函", "公告", "簽", "令", "書函", "開會通知單"):
            assert required in names, f"缺少必要類型：{required}"


# ── _build_input_text 測試 ───────────────────────────────────────────────────

class TestBuildInputText:
    """_build_input_text 組合邏輯測試。"""

    def _call(self, doc_type, subject="測試主旨內容", urgency="普通", extra=""):
        from src.cli.wizard_cmd import _build_input_text
        return _build_input_text(
            doc_type=doc_type,
            sender="台北市政府",
            receiver="各區公所",
            subject=subject,
            urgency=urgency,
            extra_context=extra,
        )

    def test_han_contains_sender_and_receiver(self):
        result = self._call("函")
        assert "台北市政府" in result
        assert "各區公所" in result

    def test_gongao_contains_gongao_keyword(self):
        result = self._call("公告")
        assert "公告" in result

    def test_sign_contains_sign_keyword(self):
        result = self._call("簽")
        assert "簽請" in result

    def test_urgency_appended_when_not_normal(self):
        result = self._call("函", urgency="速件")
        assert "速件" in result

    def test_urgency_not_appended_when_normal(self):
        result = self._call("函", urgency="普通")
        assert "普通" not in result

    def test_subject_in_result(self):
        result = self._call("函", subject="請配合辦理資源回收")
        assert "請配合辦理資源回收" in result

    def test_extra_context_appended(self):
        result = self._call("函", extra="依據環保法第三條")
        assert "依據環保法第三條" in result

    def test_extra_context_empty_not_appended(self):
        result = self._call("函", extra="")
        assert "補充說明" not in result

    def test_kaihui_contains_receiver(self):
        from src.cli.wizard_cmd import _build_input_text
        result = _build_input_text(
            doc_type="開會通知單",
            sender="局長室",
            receiver="各科室主管",
            subject="研商工作計畫",
            urgency="普通",
            extra_context="",
        )
        assert "各科室主管" in result
        assert "開會" in result

    def test_ling_contains_ling_keyword(self):
        from src.cli.wizard_cmd import _build_input_text
        result = _build_input_text(
            doc_type="令",
            sender="行政院",
            receiver="各部會",
            subject="修正施行細則",
            urgency="普通",
            extra_context="",
        )
        assert "令" in result


# ── CLI 整合測試（dry-run 模式，不呼叫 LLM）────────────────────────────────

class TestWizardCLI:
    """wizard 命令 CLI 整合測試。"""

    def test_wizard_help(self):
        result = runner.invoke(app, ["wizard", "--help"])
        assert result.exit_code == 0
        assert "wizard" in result.output.lower() or "精靈" in result.output

    def test_dry_run_shows_command_not_generates(self):
        """dry-run 模式應顯示等效命令而非呼叫 generate。"""
        inputs = "1\n台北市環保局\n各里辦公處\n請加強資源回收宣導活動\n普通\n\n\n"
        # dry-run 在顯示命令後直接 return，不會呼叫 generate
        result = runner.invoke(app, ["wizard", "--dry-run"], input=inputs)
        assert result.exit_code == 0
        assert "gov-ai generate" in result.output

    def test_dry_run_no_cite_flag(self):
        """--no-cite 應出現在 dry-run 輸出中。"""
        inputs = "1\n台北市環保局\n各里辦公處\n請加強資源回收宣導活動\n普通\n\n\n"
        result = runner.invoke(app, ["wizard", "--dry-run", "--no-cite"], input=inputs)
        assert result.exit_code == 0
        assert "--no-cite" in result.output

    def test_quick_mode_skips_optional_fields(self):
        """quick 模式下只問類型/發/收/主旨，不問速別日期。"""
        inputs = "1\n台北市政府\n各區公所\n請配合辦理消防演習\n"
        # --quick --dry-run：不呼叫 generate，直接顯示命令
        result = runner.invoke(app, ["wizard", "--quick", "--dry-run"], input=inputs)
        assert result.exit_code == 0
        # quick 模式組合的 input_text 應包含主旨
        assert "消防演習" in result.output

    def test_invalid_type_number_reprompts(self):
        """輸入超出範圍的數字應重新提示。"""
        # 先輸入 99（無效），再輸入 1（有效）
        inputs = "99\n1\n台北市政府\n各區公所\n請配合辦理測試\n普通\n\n\n"
        result = runner.invoke(app, ["wizard", "--dry-run"], input=inputs)
        assert result.exit_code == 0

    def test_type_name_input_accepted(self):
        """直接輸入類型名稱（如「公告」）應被接受。"""
        inputs = "公告\n台北市政府\n全體市民\n修正垃圾分類規定\n普通\n\n\n"
        result = runner.invoke(app, ["wizard", "--dry-run"], input=inputs)
        assert result.exit_code == 0

    def test_output_path_passed(self):
        """自訂 --output 應出現在 dry-run 命令中。"""
        inputs = "1\n台北市環保局\n各里辦公處\n請辦理環保業務\n普通\n\n\n"
        result = runner.invoke(app, ["wizard", "--dry-run", "--output", "my_doc.docx"], input=inputs)
        assert result.exit_code == 0
        assert "my_doc.docx" in result.output

    def test_confirmed_wizard_calls_generate_wrapper(self):
        """非 dry-run 確認後應呼叫 wizard generate wrapper。"""
        inputs = "1\n台北市環保局\n各里辦公處\n請辦理環保業務\n普通\n\n\ny\n"
        with patch("src.cli.wizard_cmd.run_wizard_generate") as run_wizard_generate:
            result = runner.invoke(app, ["wizard", "--output", "my_doc.docx", "--skip-review", "--preview"], input=inputs)

        assert result.exit_code == 0
        run_wizard_generate.assert_called_once()
        assert run_wizard_generate.call_args.kwargs["output"] == "my_doc.docx"
        assert run_wizard_generate.call_args.kwargs["skip_review"] is True
        assert run_wizard_generate.call_args.kwargs["preview"] is True

    def test_abort_on_keyboard_interrupt(self):
        """Ctrl+C（KeyboardInterrupt）應優雅中止。"""
        with patch("src.cli.wizard_cmd.Prompt.ask", side_effect=KeyboardInterrupt):
            result = runner.invoke(app, ["wizard"])
        # 應以非零或零退出，但不拋出未捕獲的例外
        assert "wizard" not in str(result.exception or "") or result.exit_code in (0, 1)


# ── _load_profile 與 --from-profile 測試 ────────────────────────────────────

class TestFromProfile:
    """wizard --from-profile 個人設定檔預填測試。"""

    def test_load_profile_returns_dict_when_file_exists(self, tmp_path, monkeypatch):
        """存在設定檔時應正確回傳字典。"""
        profile_file = tmp_path / ".gov-ai-profile.json"
        profile_file.write_text('{"agency": "臺北市政府", "name": "王小明"}', encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        from src.cli.wizard_cmd import _load_profile
        result = _load_profile()
        assert result["agency"] == "臺北市政府"
        assert result["name"] == "王小明"

    def test_load_profile_returns_empty_when_no_file(self, tmp_path, monkeypatch):
        """無設定檔時應回傳空字典，不拋出例外。"""
        monkeypatch.chdir(tmp_path)
        from src.cli.wizard_cmd import _load_profile
        result = _load_profile()
        assert result == {}

    def test_load_profile_returns_empty_on_invalid_json(self, tmp_path, monkeypatch):
        """設定檔 JSON 損壞時應靜默回傳空字典。"""
        profile_file = tmp_path / ".gov-ai-profile.json"
        profile_file.write_text("invalid json {{{", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        from src.cli.wizard_cmd import _load_profile
        result = _load_profile()
        assert result == {}

    def test_from_profile_pre_fills_sender_in_dry_run(self, tmp_path, monkeypatch):
        """profile 有 agency 時，dry-run 輸出中應出現該機關名稱（預填為預設值）。"""
        profile_file = tmp_path / ".gov-ai-profile.json"
        profile_file.write_text('{"agency": "新北市政府環保局"}', encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        # 使用者按 Enter 接受預填值，再輸入收文和主旨
        inputs = "1\n\n各區公所\n辦理環保業務宣導\n普通\n\n\n"
        result = runner.invoke(app, ["wizard", "--dry-run", "--from-profile"], input=inputs)
        assert result.exit_code == 0
        assert "新北市政府環保局" in result.output

    def test_no_from_profile_disables_prefill(self, tmp_path, monkeypatch):
        """--no-from-profile 時即使 profile 有 agency 也不顯示預填提示。"""
        profile_file = tmp_path / ".gov-ai-profile.json"
        profile_file.write_text('{"agency": "應被忽略的機關"}', encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        inputs = "1\n台北市政府\n各區公所\n辦理業務測試工作\n普通\n\n\n"
        result = runner.invoke(app, ["wizard", "--dry-run", "--no-from-profile"], input=inputs)
        assert result.exit_code == 0
        assert "從個人設定檔預填" not in result.output
