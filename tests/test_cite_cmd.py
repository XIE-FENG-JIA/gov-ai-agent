"""cite_cmd 單元測試——法規引用建議功能。"""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from src.cli.cite_cmd import (
    _detect_doc_type,
    _filter_applicable,
    _load_mapping,
    _MAPPING_PATH,
    _TYPE_LABELS,
)


# ──────────────────────────────────────────────────────────────
# 測試用假映射表（不依賴真實 kb_data 目錄）
# ──────────────────────────────────────────────────────────────

FAKE_MAPPING = {
    "regulations": {
        "公文程式條例": {
            "pcode": "A0030018",
            "applicable_doc_types": ["函", "公告", "簽", "令", "書函", "開會通知單"],
            "description": "公文格式基本規範",
        },
        "行政程序法": {
            "pcode": "A0030055",
            "applicable_doc_types": ["函", "公告", "簽", "令"],
            "description": "行政處分程序規範",
        },
        "政府採購法": {
            "pcode": "A1030010",
            "applicable_doc_types": ["採購公告"],
            "description": "政府採購程序規範",
        },
    }
}


@pytest.fixture()
def mapping_yaml_file(tmp_path: Path) -> Path:
    """建立暫存映射 YAML 檔案。"""
    mapping_file = tmp_path / "regulation_doc_type_mapping.yaml"
    mapping_file.write_text(
        yaml.dump(FAKE_MAPPING, allow_unicode=True), encoding="utf-8"
    )
    return mapping_file


# ──────────────────────────────────────────────────────────────
# _detect_doc_type 測試
# ──────────────────────────────────────────────────────────────


class TestDetectDocType:
    def test_detects_han_from_keywords(self):
        # 函的兜底規則：正本+副本是函的專屬特徵
        text = "主旨：請查照。\n說明：依規定辦理。\n正本：內政部\n副本：行政院"
        assert _detect_doc_type(text) == "函"

    def test_detects_gonggao_from_keywords(self):
        # 公告用「茲公告」觸發，不依賴「主旨：」（函也有主旨）
        text = "茲公告本府修正建築法施行細則，並自即日起生效。"
        assert _detect_doc_type(text) == "公告"

    def test_detects_meeting_notice(self):
        text = "開會通知單\n敬邀出席本次協調會議。\n列席：各機關代表"
        assert _detect_doc_type(text) == "開會通知單"

    def test_detects_meeting_minutes(self):
        # 會議紀錄規則比開會通知單優先，且「主持人」+「出席人員」是特徵
        text = "會議紀錄\n主持人：XXX 局長\n出席人員：各部代表\n決議事項：通過。"
        assert _detect_doc_type(text) == "會議紀錄"

    def test_detects_procurement(self):
        text = "採購公告\n廠商投標須知\n開標日期：...\n底價：..."
        assert _detect_doc_type(text) == "採購公告"

    def test_detects_personnel_order(self):
        text = "茲任命王小明為本部司長，生效日期如下。\n任命令"
        assert _detect_doc_type(text) == "人事令"

    def test_fallback_to_han_for_unrecognized(self):
        """無法辨識的內容 fallback 到「函」（最常見公文類型）。"""
        text = "這是完全無法識別的文字內容，沒有任何公文關鍵字。"
        result = _detect_doc_type(text)
        assert result == "函"

    def test_returns_none_for_empty(self):
        """空內容回傳 None。"""
        assert _detect_doc_type("") is None
        assert _detect_doc_type("   ") is None

    def test_priority_meeting_notice_over_han(self):
        # 同時含「開會通知」與「主旨」，應優先偵測為開會通知單
        text = "開會通知單\n主旨：敬邀出席。\n說明：..."
        assert _detect_doc_type(text) == "開會通知單"


# ──────────────────────────────────────────────────────────────
# _load_mapping 測試
# ──────────────────────────────────────────────────────────────


class TestLoadMapping:
    def test_loads_yaml_successfully(self, mapping_yaml_file: Path):
        result = _load_mapping(mapping_yaml_file)
        assert "公文程式條例" in result
        assert result["公文程式條例"]["pcode"] == "A0030018"

    def test_raises_on_missing_file(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError, match="找不到法規映射表"):
            _load_mapping(tmp_path / "nonexistent.yaml")

    def test_returns_empty_dict_for_missing_regulations_key(self, tmp_path: Path):
        empty_yaml = tmp_path / "empty.yaml"
        empty_yaml.write_text("other_key: value\n", encoding="utf-8")
        result = _load_mapping(empty_yaml)
        assert result == {}


# ──────────────────────────────────────────────────────────────
# _filter_applicable 測試
# ──────────────────────────────────────────────────────────────


class TestFilterApplicable:
    def setup_method(self):
        self.regs = FAKE_MAPPING["regulations"]

    def test_filters_for_han(self):
        result = _filter_applicable(self.regs, "函")
        names = [r["name"] for r in result]
        assert "公文程式條例" in names
        assert "行政程序法" in names
        assert "政府採購法" not in names  # 採購法不適用於函

    def test_filters_for_procurement(self):
        result = _filter_applicable(self.regs, "採購公告")
        names = [r["name"] for r in result]
        assert "政府採購法" in names
        assert "公文程式條例" not in names

    def test_returns_empty_for_unknown_type(self):
        result = _filter_applicable(self.regs, "未知類型")
        assert result == []

    def test_includes_cite_format(self):
        result = _filter_applicable(self.regs, "函")
        for reg in result:
            assert "cite_format" in reg
            assert reg["name"] in reg["cite_format"]

    def test_result_is_sorted_by_name(self):
        result = _filter_applicable(self.regs, "函")
        names = [r["name"] for r in result]
        assert names == sorted(names)

    def test_result_contains_pcode(self):
        result = _filter_applicable(self.regs, "公告")
        for reg in result:
            assert reg["pcode"]  # 不能是空字串


# ──────────────────────────────────────────────────────────────
# cite CLI 整合測試（透過 typer CliRunner）
# ──────────────────────────────────────────────────────────────


class TestCiteCLI:
    """測試 CLI 入口點行為（不呼叫真實 KB/LLM）。"""

    def _run_cite(self, args: list[str], draft_content: str | None = None, tmp_path: Path | None = None):
        from typer.testing import CliRunner
        from src.cli.main import app

        runner = CliRunner()
        if draft_content is not None and tmp_path is not None:
            draft_file = tmp_path / "draft.md"
            draft_file.write_text(draft_content, encoding="utf-8")
            args = [str(draft_file)] + args
        return runner.invoke(app, ["cite"] + args)

    def test_cli_detects_type_and_shows_results(self, tmp_path, mapping_yaml_file):
        draft = "主旨：請查照。\n說明：依規定辦理。\n正本：行政院\n副本：內政部"
        result = self._run_cite(
            ["--mapping", str(mapping_yaml_file)],
            draft_content=draft,
            tmp_path=tmp_path,
        )
        assert result.exit_code == 0, result.output
        assert "公文程式條例" in result.output

    def test_cli_explicit_type_overrides_detection(self, tmp_path, mapping_yaml_file):
        draft = "主旨：請查照。\n說明：依規定辦理。"
        result = self._run_cite(
            ["--type", "採購公告", "--mapping", str(mapping_yaml_file)],
            draft_content=draft,
            tmp_path=tmp_path,
        )
        assert result.exit_code == 0
        assert "政府採購法" in result.output

    def test_cli_json_format(self, tmp_path, mapping_yaml_file):
        import json

        draft = "主旨：請查照。\n說明：依規定辦理。\n正本：行政院"
        result = self._run_cite(
            ["--format", "json", "--mapping", str(mapping_yaml_file)],
            draft_content=draft,
            tmp_path=tmp_path,
        )
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "doc_type" in parsed
        assert "applicable_regulations" in parsed

    def test_cli_fails_on_missing_file(self, tmp_path, mapping_yaml_file):
        result = self._run_cite(
            [str(tmp_path / "nonexistent.md"), "--mapping", str(mapping_yaml_file)]
        )
        assert result.exit_code != 0

    def test_cli_unrecognized_falls_back_to_han(self, tmp_path, mapping_yaml_file):
        """無法辨識的內容 fallback 到「函」，正常執行不會 exit 非 0。"""
        draft = "這是完全無法識別的文字內容。"
        result = self._run_cite(
            ["--mapping", str(mapping_yaml_file)],
            draft_content=draft,
            tmp_path=tmp_path,
        )
        # fallback 到「函」，正常執行
        assert result.exit_code == 0
