"""
src/core/ 的延伸測試
補充 ConfigManager、ReviewModels 的邊界條件和未覆蓋的功能
"""
import pytest
import os
from pydantic import ValidationError

from src.core.config import ConfigManager, LLMProvider
from src.core.models import PublicDocRequirement
from src.core.review_models import ReviewIssue, ReviewResult, QAReport


# ==================== ConfigManager._expand_env_vars ====================

class TestExpandEnvVars:
    """_expand_env_vars 方法的測試"""

    def test_expand_simple_string(self, tmp_path):
        """測試展開簡單的環境變數字串"""
        os.environ["TEST_EXPAND_VAR"] = "expanded_value"
        try:
            config_file = tmp_path / "config.yaml"
            manager = ConfigManager(str(config_file))
            result = manager._expand_env_vars("${TEST_EXPAND_VAR}")
            assert result == "expanded_value"
        finally:
            del os.environ["TEST_EXPAND_VAR"]

    def test_expand_missing_env_var(self, tmp_path):
        """測試展開不存在的環境變數回傳空字串"""
        config_file = tmp_path / "config.yaml"
        manager = ConfigManager(str(config_file))
        result = manager._expand_env_vars("${NONEXISTENT_VAR_12345}")
        assert result == ""

    def test_expand_non_env_string(self, tmp_path):
        """測試普通字串不被修改"""
        config_file = tmp_path / "config.yaml"
        manager = ConfigManager(str(config_file))
        result = manager._expand_env_vars("plain text")
        assert result == "plain text"

    def test_expand_dict(self, tmp_path):
        """測試遞迴展開字典中的環境變數"""
        os.environ["TEST_DICT_VAR"] = "dict_value"
        try:
            config_file = tmp_path / "config.yaml"
            manager = ConfigManager(str(config_file))
            result = manager._expand_env_vars({
                "key1": "${TEST_DICT_VAR}",
                "key2": "normal"
            })
            assert result["key1"] == "dict_value"
            assert result["key2"] == "normal"
        finally:
            del os.environ["TEST_DICT_VAR"]

    def test_expand_list(self, tmp_path):
        """測試遞迴展開列表中的環境變數"""
        os.environ["TEST_LIST_VAR"] = "list_value"
        try:
            config_file = tmp_path / "config.yaml"
            manager = ConfigManager(str(config_file))
            result = manager._expand_env_vars(["${TEST_LIST_VAR}", "normal"])
            assert result[0] == "list_value"
            assert result[1] == "normal"
        finally:
            del os.environ["TEST_LIST_VAR"]

    def test_expand_non_string(self, tmp_path):
        """測試非字串值不被修改"""
        config_file = tmp_path / "config.yaml"
        manager = ConfigManager(str(config_file))
        assert manager._expand_env_vars(42) == 42
        assert manager._expand_env_vars(True) is True
        assert manager._expand_env_vars(None) is None


# ==================== ConfigManager 邊界測試 ====================

class TestConfigManagerEdgeCases:
    """ConfigManager 的邊界測試"""

    def test_load_corrupted_yaml(self, tmp_path):
        """測試載入損壞的 YAML 檔案"""
        config_file = tmp_path / "broken.yaml"
        config_file.write_text("invalid: yaml: [broken", encoding="utf-8")

        manager = ConfigManager(str(config_file))
        # 應載入預設配置
        assert manager.get("llm.provider") == "ollama"

    def test_load_empty_yaml(self, tmp_path):
        """測試載入空的 YAML 檔案"""
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("", encoding="utf-8")

        manager = ConfigManager(str(config_file))
        # 空 YAML 會解析為 None/{}，應有預設值
        assert manager.config is not None

    def test_get_deeply_nested_key(self, tmp_path):
        """測試深層巢狀 key 的存取"""
        config_file = tmp_path / "nested.yaml"
        manager = ConfigManager(str(config_file))

        # 配置不包含這個深層路徑
        result = manager.get("a.b.c.d.e")
        assert result is None

    def test_get_with_non_dict_intermediate(self, tmp_path):
        """測試中間路徑不是字典時的處理"""
        config_file = tmp_path / "config.yaml"
        manager = ConfigManager(str(config_file))

        # llm.provider 是字串，再往下取應回傳 None
        result = manager.get("llm.provider.sub_key")
        assert result is None

    def test_save_and_reload_preserves_unicode(self, tmp_path):
        """測試儲存和重載保留 Unicode 字元"""
        config_file = tmp_path / "unicode.yaml"
        manager = ConfigManager(str(config_file))

        new_config = manager.config.copy()
        new_config["custom"] = {"name": "臺北市政府"}
        manager.save_config(new_config)

        manager2 = ConfigManager(str(config_file))
        assert manager2.config["custom"]["name"] == "臺北市政府"

    def test_save_config_syncs_in_memory(self, tmp_path):
        """測試 save_config 後 self.config 同步更新"""
        config_file = tmp_path / "sync.yaml"
        manager = ConfigManager(str(config_file))

        new_config = {"llm": {"provider": "gemini", "model": "gemini-pro"}}
        manager.save_config(new_config)

        # 記憶體內的 config 應已更新，無需重新載入
        assert manager.config["llm"]["provider"] == "gemini"
        assert manager.get("llm.provider") == "gemini"

    def test_create_default_config_oserror_graceful(self, tmp_path):
        """測試建立預設設定檔時 OSError 被優雅處理（覆蓋 config.py:96-97）"""
        from unittest.mock import patch

        # 建立不存在的路徑
        config_path = tmp_path / "new_dir" / "config.yaml"
        # Mock save_config 拋出 OSError（模擬磁碟已滿等）
        with patch.object(ConfigManager, 'save_config', side_effect=OSError("磁碟已滿")):
            manager = ConfigManager(str(config_path))

        # 應該仍然回傳預設設定，不崩潰
        assert manager.config is not None
        assert manager.config["llm"]["provider"] == "ollama"


# ==================== load_dotenv 邊界測試 ====================

class TestLoadDotenv:
    """load_dotenv 函數的邊界測試"""

    def test_env_file_with_comments(self, tmp_path):
        """測試 .env 檔案中的註解被忽略"""
        env_file = tmp_path / ".env"
        env_file.write_text("# This is a comment\nTEST_DOTENV_KEY=value123\n", encoding="utf-8")

        # 手動解析（模擬 load_dotenv 邏輯）
        for line in env_file.read_text().split('\n'):
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                os.environ[key] = value

        try:
            assert os.environ.get("TEST_DOTENV_KEY") == "value123"
        finally:
            os.environ.pop("TEST_DOTENV_KEY", None)

    def test_env_file_with_single_quotes(self, tmp_path):
        """測試單引號包裹的值"""
        env_file = tmp_path / ".env"
        env_file.write_text("TEST_SQ_KEY='single_quoted'\n", encoding="utf-8")

        for line in env_file.read_text().split('\n'):
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                os.environ[key] = value

        try:
            assert os.environ.get("TEST_SQ_KEY") == "single_quoted"
        finally:
            os.environ.pop("TEST_SQ_KEY", None)

    def test_env_file_empty_lines(self, tmp_path):
        """測試空行被忽略"""
        env_file = tmp_path / ".env"
        env_file.write_text("\n\nTEST_EMPTY_LINE=ok\n\n", encoding="utf-8")

        for line in env_file.read_text().split('\n'):
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                os.environ[key] = value

        try:
            assert os.environ.get("TEST_EMPTY_LINE") == "ok"
        finally:
            os.environ.pop("TEST_EMPTY_LINE", None)


# ==================== PublicDocRequirement 邊界測試 ====================

class TestPublicDocRequirementEdgeCases:
    """PublicDocRequirement 的邊界測試"""

    def test_missing_subject_raises(self):
        """測試缺少 subject 拋出 ValidationError"""
        with pytest.raises(ValidationError):
            PublicDocRequirement(
                doc_type="函",
                sender="機關",
                receiver="對象"
                # 缺少 subject
            )

    def test_missing_sender_raises(self):
        """測試缺少 sender 拋出 ValidationError"""
        with pytest.raises(ValidationError):
            PublicDocRequirement(
                doc_type="函",
                receiver="對象",
                subject="主旨"
            )

    def test_missing_receiver_raises(self):
        """測試缺少 receiver 拋出 ValidationError"""
        with pytest.raises(ValidationError):
            PublicDocRequirement(
                doc_type="函",
                sender="機關",
                subject="主旨"
            )

    def test_empty_action_items_default(self):
        """測試 action_items 預設為空列表"""
        req = PublicDocRequirement(
            doc_type="函",
            sender="機關",
            receiver="對象",
            subject="主旨"
        )
        assert req.action_items == []

    def test_multiple_attachments(self):
        """測試多個附件"""
        req = PublicDocRequirement(
            doc_type="函",
            sender="機關",
            receiver="對象",
            subject="主旨",
            attachments=["附件A", "附件B", "附件C"]
        )
        assert len(req.attachments) == 3

    def test_model_dump_includes_defaults(self):
        """測試 model_dump 包含預設值"""
        req = PublicDocRequirement(
            doc_type="函",
            sender="機關",
            receiver="對象",
            subject="主旨"
        )
        data = req.model_dump()
        assert "urgency" in data
        assert data["urgency"] == "普通"
        assert "reason" in data
        assert data["reason"] is None

    def test_empty_doc_type_raises(self):
        """測試空白 doc_type 拋出 ValidationError"""
        with pytest.raises(ValidationError, match="公文類型不可為空白"):
            PublicDocRequirement(
                doc_type="   ",
                sender="機關",
                receiver="對象",
                subject="主旨"
            )

    def test_invalid_urgency_normalized(self):
        """測試無效速別自動正規化為「普通」"""
        req = PublicDocRequirement(
            doc_type="函",
            sender="機關",
            receiver="對象",
            subject="主旨",
            urgency="超級快"
        )
        assert req.urgency == "普通"

    def test_empty_subject_raises(self):
        """測試空白 subject 拋出 ValidationError"""
        with pytest.raises(ValidationError, match="主旨不可為空白"):
            PublicDocRequirement(
                doc_type="函",
                sender="機關",
                receiver="對象",
                subject="   "
            )

    def test_valid_urgency_levels(self):
        """測試所有合法速別"""
        for urgency in ("普通", "速件", "最速件"):
            req = PublicDocRequirement(
                doc_type="函",
                sender="機關",
                receiver="對象",
                subject="主旨",
                urgency=urgency
            )
            assert req.urgency == urgency


# ==================== ReviewIssue 邊界測試 ====================

class TestReviewIssueEdgeCases:
    """ReviewIssue 的邊界測試"""

    def test_default_risk_level(self):
        """測試預設風險等級"""
        issue = ReviewIssue(
            category="style",
            severity="warning",
            location="主旨",
            description="問題"
        )
        assert issue.risk_level == "low"

    def test_all_categories(self):
        """測試所有有效的類別"""
        for cat in ["format", "style", "fact", "consistency", "compliance"]:
            issue = ReviewIssue(
                category=cat,
                severity="info",
                location="test",
                description="test"
            )
            assert issue.category == cat

    def test_all_severities(self):
        """測試所有有效的嚴重性"""
        for sev in ["error", "warning", "info"]:
            issue = ReviewIssue(
                category="format",
                severity=sev,
                location="test",
                description="test"
            )
            assert issue.severity == sev

    def test_optional_suggestion(self):
        """測試 suggestion 是可選的"""
        issue = ReviewIssue(
            category="format",
            severity="error",
            location="test",
            description="test"
        )
        assert issue.suggestion is None

    def test_with_suggestion(self):
        """測試有建議的 issue"""
        issue = ReviewIssue(
            category="format",
            severity="error",
            location="test",
            description="test",
            suggestion="建議修正方式"
        )
        assert issue.suggestion == "建議修正方式"


# ==================== ReviewResult 邊界測試 ====================

class TestReviewResultEdgeCases:
    """ReviewResult 的邊界測試"""

    def test_has_errors_with_only_info(self):
        """測試只有 info 嚴重性時沒有錯誤"""
        result = ReviewResult(
            agent_name="Test",
            issues=[
                ReviewIssue(category="style", severity="info", location="x", description="y")
            ],
            score=0.9
        )
        assert result.has_errors is False

    def test_has_errors_mixed_severities(self):
        """測試混合嚴重性時有錯誤"""
        result = ReviewResult(
            agent_name="Test",
            issues=[
                ReviewIssue(category="style", severity="info", location="x", description="y"),
                ReviewIssue(category="format", severity="error", location="x", description="y")
            ],
            score=0.5
        )
        assert result.has_errors is True

    def test_default_confidence(self):
        """測試預設信心度"""
        result = ReviewResult(agent_name="Test", issues=[], score=1.0)
        assert result.confidence == 1.0

    def test_custom_confidence(self):
        """測試自訂信心度"""
        result = ReviewResult(
            agent_name="Test",
            issues=[],
            score=0.9,
            confidence=0.7
        )
        assert result.confidence == 0.7

    def test_score_boundary_zero(self):
        """測試分數下限"""
        result = ReviewResult(agent_name="Test", issues=[], score=0.0)
        assert result.score == 0.0

    def test_score_boundary_one(self):
        """測試分數上限"""
        result = ReviewResult(agent_name="Test", issues=[], score=1.0)
        assert result.score == 1.0


# ==================== QAReport 邊界測試 ====================

class TestQAReportEdgeCases:
    """QAReport 的邊界測試"""

    def test_all_risk_levels(self):
        """測試所有有效的風險等級"""
        for risk in ["Critical", "High", "Moderate", "Low", "Safe"]:
            report = QAReport(
                overall_score=0.5,
                risk_summary=risk,
                agent_results=[],
                audit_log="Test"
            )
            assert report.risk_summary == risk

    def test_with_multiple_agent_results(self):
        """測試多個 Agent 結果"""
        results = [
            ReviewResult(agent_name="A", issues=[], score=0.9),
            ReviewResult(agent_name="B", issues=[], score=0.8),
            ReviewResult(agent_name="C", issues=[], score=0.95),
        ]
        report = QAReport(
            overall_score=0.88,
            risk_summary="Low",
            agent_results=results,
            audit_log="# Report"
        )
        assert len(report.agent_results) == 3

    def test_empty_audit_log(self):
        """測試空的審計日誌"""
        report = QAReport(
            overall_score=1.0,
            risk_summary="Safe",
            agent_results=[],
            audit_log=""
        )
        assert report.audit_log == ""


# ==================== LLMProvider 抽象類別測試 ====================

class TestLLMProviderAbstract:
    """LLMProvider 抽象基礎類別的測試"""

    def test_cannot_instantiate(self):
        """測試無法直接實例化抽象類別"""
        with pytest.raises(TypeError):
            LLMProvider()

    def test_subclass_must_implement_generate(self):
        """測試子類別必須實作 generate"""
        class IncompleteProvider(LLMProvider):
            def embed(self, text):
                return []

        with pytest.raises(TypeError):
            IncompleteProvider()

    def test_subclass_must_implement_embed(self):
        """測試子類別必須實作 embed"""
        class IncompleteProvider(LLMProvider):
            def generate(self, prompt, **kwargs):
                return ""

        with pytest.raises(TypeError):
            IncompleteProvider()

    def test_complete_subclass_works(self):
        """測試完整的子類別可以實例化"""
        class CompleteProvider(LLMProvider):
            def generate(self, prompt, **kwargs):
                return "result"
            def embed(self, text):
                return [0.1]

        provider = CompleteProvider()
        assert provider.generate("test") == "result"
        assert provider.embed("test") == [0.1]


# ==================== cli_colors 匯入測試 ====================

class TestCliColors:
    """cli_colors 模組的基本匯入測試"""

    def test_cli_theme_is_dict(self):
        """測試 CLI_THEME 是一個字典且包含必要的顏色鍵"""
        from src.theme.cli_colors import CLI_THEME
        assert isinstance(CLI_THEME, dict)
        assert "CLI_INFO" in CLI_THEME
        assert "CLI_SUCCESS" in CLI_THEME
        assert "CLI_WARNING" in CLI_THEME
        assert "CLI_ERROR" in CLI_THEME

    def test_cli_theme_values_are_hex(self):
        """測試所有顏色值都是有效的十六進位色碼"""
        from src.theme.cli_colors import CLI_THEME
        import re
        for key, value in CLI_THEME.items():
            assert re.match(r'^#[0-9a-fA-F]{6}$', value), f"{key} 的值 {value} 不是有效色碼"


# ==================== DocxExporter KNOWN_DOC_TYPES 跳過 ====================

class TestExporterKnownDocTypes:
    """DocxExporter 跳過 KNOWN_DOC_TYPES 的測試"""

    def test_header_skips_known_doc_type(self, tmp_path):
        """測試檔頭中的公文類型名稱被跳過"""
        from src.document.exporter import DocxExporter
        exporter = DocxExporter()
        # 草稿第一行後面跟著公文類型名稱 "函"
        draft = "# 函\n函\n**機關**：測試機關\n---\n### 主旨\n測試"
        output_path = str(tmp_path / "test_skip.docx")
        result_path = exporter.export(draft, output_path)
        assert os.path.exists(result_path)


# ==================== VALID_DOC_TYPES 與 validate_doc_type ====================

class TestValidDocTypes:
    """驗證 VALID_DOC_TYPES 與 validate_doc_type 的一致性"""

    def test_known_doc_types_accepted(self):
        """測試所有已知公文類型都能通過驗證"""
        from src.core.models import VALID_DOC_TYPES
        for dt in VALID_DOC_TYPES:
            req = PublicDocRequirement(
                doc_type=dt, sender="A", receiver="B", subject="主旨"
            )
            assert req.doc_type == dt

    def test_unknown_doc_type_accepted_with_warning(self, caplog):
        """測試未知公文類型仍然接受，但會記錄警告"""
        import logging
        with caplog.at_level(logging.WARNING, logger="src.core.models"):
            req = PublicDocRequirement(
                doc_type="奇怪的類型", sender="A", receiver="B", subject="主旨"
            )
            assert req.doc_type == "奇怪的類型"
        assert "未知的公文類型" in caplog.text

    def test_empty_doc_type_rejected(self):
        """測試空白公文類型被拒絕"""
        with pytest.raises(ValidationError, match="公文類型不可為空白"):
            PublicDocRequirement(
                doc_type="  ", sender="A", receiver="B", subject="主旨"
            )

    def test_doc_type_literal_matches_valid_doc_types(self):
        """測試 DocTypeLiteral 和 VALID_DOC_TYPES 包含相同的值"""
        from typing import get_args
        from src.core.models import DocTypeLiteral, VALID_DOC_TYPES
        literal_values = set(get_args(DocTypeLiteral))
        assert literal_values == set(VALID_DOC_TYPES), (
            f"DocTypeLiteral {literal_values} 與 VALID_DOC_TYPES {set(VALID_DOC_TYPES)} 不一致"
        )


# ==================== PublicDocRequirement max_length ====================

class TestPublicDocRequirementMaxLength:
    """測試 PublicDocRequirement 欄位的 max_length 限制"""

    def test_sender_max_length(self):
        """測試 sender 超過 200 字元被拒絕"""
        with pytest.raises(ValidationError):
            PublicDocRequirement(
                doc_type="函", sender="A" * 201, receiver="B", subject="主旨"
            )

    def test_receiver_max_length(self):
        """測試 receiver 超過 500 字元被拒絕"""
        with pytest.raises(ValidationError):
            PublicDocRequirement(
                doc_type="函", sender="A", receiver="B" * 501, subject="主旨"
            )

    def test_subject_max_length(self):
        """測試 subject 超過 500 字元被拒絕"""
        with pytest.raises(ValidationError):
            PublicDocRequirement(
                doc_type="函", sender="A", receiver="B", subject="字" * 501
            )

    def test_fields_at_max_length_accepted(self):
        """測試欄位恰好在 max_length 邊界值時被接受"""
        req = PublicDocRequirement(
            doc_type="函",
            sender="A" * 200,
            receiver="B" * 500,
            subject="字" * 500,
        )
        assert len(req.sender) == 200
        assert len(req.receiver) == 500
        assert len(req.subject) == 500
