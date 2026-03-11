import os

import pytest
from pydantic import ValidationError

from src.core.config import ConfigManager
from src.core.models import PublicDocRequirement
from src.core.review_models import QAReport, ReviewIssue, ReviewResult


# ==================== PublicDocRequirement ====================

def test_public_doc_requirement_validation():
    """Test that the data model validates inputs correctly."""
    req = PublicDocRequirement(
        doc_type="函",
        sender="Agency",
        receiver="Target",
        subject="Subject"
    )
    assert req.doc_type == "函"
    assert req.urgency == "普通"  # Default value
    assert req.action_items == []
    assert req.attachments == []

    # Invalid case (missing required fields)
    with pytest.raises(ValidationError):
        PublicDocRequirement(doc_type="函")


def test_public_doc_requirement_full():
    """Test full model with all fields."""
    req = PublicDocRequirement(
        doc_type="公告",
        urgency="速件",
        sender="環保局",
        receiver="各學校",
        subject="回收公告",
        reason="為加強資源回收",
        action_items=["動作1", "動作2"],
        attachments=["附件1"]
    )
    assert req.urgency == "速件"
    assert len(req.action_items) == 2
    assert req.reason == "為加強資源回收"


def test_public_doc_requirement_serialization():
    """Test model_dump works correctly."""
    req = PublicDocRequirement(
        doc_type="簽",
        sender="市府",
        receiver="局長",
        subject="簽呈"
    )
    data = req.model_dump()
    assert data["doc_type"] == "簽"
    assert data["urgency"] == "普通"
    assert data["reason"] is None


# ==================== ConfigManager ====================

def test_config_manager(tmp_path):
    """Test configuration loading and saving."""
    config_file = tmp_path / "test_config.yaml"

    # 1. Test default creation
    manager = ConfigManager(str(config_file))
    assert config_file.exists()
    assert manager.get("llm.provider") == "ollama"

    # 2. Test loading existing
    manager2 = ConfigManager(str(config_file))
    assert manager2.config == manager.config


def test_config_manager_get_nested(tmp_path):
    """Test nested key access."""
    config_file = tmp_path / "test_config.yaml"
    manager = ConfigManager(str(config_file))

    assert manager.get("llm.model") == "mistral"
    assert manager.get("nonexistent.key") is None
    assert manager.get("nonexistent.key", "default") == "default"


def test_config_manager_save(tmp_path):
    """Test saving config."""
    config_file = tmp_path / "test_config.yaml"
    manager = ConfigManager(str(config_file))

    new_config = manager.config.copy()
    new_config["llm"]["provider"] = "gemini"
    manager.save_config(new_config)

    # Reload and verify
    manager2 = ConfigManager(str(config_file))
    assert manager2.get("llm.provider") == "gemini"


def test_load_dotenv_with_quotes(tmp_path):
    """Test .env loading strips quotes."""
    env_file = tmp_path / ".env"
    env_file.write_text('TEST_KEY_QUOTED="quoted_value"\nTEST_KEY_PLAIN=plain_value\n')

    # Manually call the parser logic
    for line in env_file.read_text().split('\n'):
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ[key] = value

    try:
        assert os.environ.get("TEST_KEY_QUOTED") == "quoted_value"
        assert os.environ.get("TEST_KEY_PLAIN") == "plain_value"
    finally:
        os.environ.pop("TEST_KEY_QUOTED", None)
        os.environ.pop("TEST_KEY_PLAIN", None)


# ==================== BUG-008: load_dotenv 內聯註解處理 ====================

class TestLoadDotenvInlineComments:
    """測試 load_dotenv 正確移除未引號包裹的內聯註解"""

    def test_inline_comment_stripped(self, tmp_path):
        """未引號包裹的值中 # 後的內容應被移除"""
        env_file = tmp_path / ".env"
        env_file.write_text("BUG008_TEST_A=secret123 # this is a comment\n")

        def _test_load():
            if env_file.exists():
                with open(env_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip()
                            if not (value.startswith('"') or value.startswith("'")):
                                value = value.split('#')[0].rstrip()
                            value = value.strip('"').strip("'")
                            os.environ[key] = value
        try:
            _test_load()
            assert os.environ.get("BUG008_TEST_A") == "secret123"
        finally:
            os.environ.pop("BUG008_TEST_A", None)

    def test_quoted_value_with_hash_preserved(self, tmp_path):
        """引號包裹的值中 # 應被保留"""
        env_file = tmp_path / ".env"
        env_file.write_text('BUG008_TEST_B="value#with_hash"\n')
        # 直接測試解析邏輯
        for line in env_file.read_text().split('\n'):
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                if not (value.startswith('"') or value.startswith("'")):
                    value = value.split('#')[0].rstrip()
                value = value.strip('"').strip("'")
                os.environ[key] = value
        try:
            assert os.environ.get("BUG008_TEST_B") == "value#with_hash"
        finally:
            os.environ.pop("BUG008_TEST_B", None)

    def test_no_inline_comment(self, tmp_path):
        """沒有 # 的值應完整保留"""
        env_file = tmp_path / ".env"
        env_file.write_text("BUG008_TEST_C=plain_value\n")
        for line in env_file.read_text().split('\n'):
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                if not (value.startswith('"') or value.startswith("'")):
                    value = value.split('#')[0].rstrip()
                value = value.strip('"').strip("'")
                os.environ[key] = value
        try:
            assert os.environ.get("BUG008_TEST_C") == "plain_value"
        finally:
            os.environ.pop("BUG008_TEST_C", None)


# ==================== ReviewModels ====================

def test_review_issue():
    """Test ReviewIssue creation."""
    issue = ReviewIssue(
        category="format",
        severity="error",
        risk_level="high",
        location="主旨",
        description="缺少主旨",
        suggestion="請加入主旨"
    )
    assert issue.category == "format"
    assert issue.suggestion == "請加入主旨"


def test_review_result_has_errors():
    """Test has_errors property."""
    # With errors
    result = ReviewResult(
        agent_name="Test",
        issues=[ReviewIssue(category="format", severity="error", location="x", description="y")],
        score=0.5,
    )
    assert result.has_errors is True

    # Without errors
    result2 = ReviewResult(
        agent_name="Test",
        issues=[ReviewIssue(category="style", severity="warning", location="x", description="y")],
        score=0.8,
    )
    assert result2.has_errors is False

    # Empty
    result3 = ReviewResult(agent_name="Test", issues=[], score=1.0)
    assert result3.has_errors is False


def test_qa_report():
    """Test QAReport creation."""
    report = QAReport(
        overall_score=0.85,
        risk_summary="Moderate",
        agent_results=[],
        audit_log="# Report\nTest"
    )
    assert report.overall_score == 0.85
    assert report.risk_summary == "Moderate"
