"""
review_parser.py 單元測試

覆蓋 4 個公開函式：
- _sanitize_json_string
- _extract_json_object
- parse_review_response
- format_audit_to_review_result
"""
import json
import pytest

from src.agents.review_parser import (
    _sanitize_json_string,
    _extract_json_object,
    parse_review_response,
    format_audit_to_review_result,
)
from src.core.review_models import ReviewResult


# ============================================================
# _sanitize_json_string
# ============================================================

class TestSanitizeJsonString:
    """測試不可見 Unicode 字元清理。"""

    def test_none_returns_empty(self):
        assert _sanitize_json_string(None) == ""

    def test_empty_returns_empty(self):
        assert _sanitize_json_string("") == ""

    def test_normal_text_unchanged(self):
        assert _sanitize_json_string("hello world") == "hello world"

    def test_bom_removed(self):
        assert _sanitize_json_string('\ufeff{"key": "val"}') == '{"key": "val"}'

    def test_zwsp_removed(self):
        assert _sanitize_json_string('doc\u200b_type') == "doc_type"

    def test_zwnj_removed(self):
        assert _sanitize_json_string('doc\u200c_type') == "doc_type"

    def test_zwj_removed(self):
        assert _sanitize_json_string('doc\u200d_type') == "doc_type"

    def test_lrm_rlm_removed(self):
        assert _sanitize_json_string('\u200ehello\u200f') == "hello"

    def test_soft_hyphen_removed(self):
        assert _sanitize_json_string('soft\u00adhyphen') == "softhyphen"

    def test_word_joiner_removed(self):
        assert _sanitize_json_string('word\u2060joiner') == "wordjoiner"

    def test_multiple_invisible_chars(self):
        text = '\ufeff\u200b\u200c\u200d\u200e\u200f\u00ad\u2060clean'
        assert _sanitize_json_string(text) == "clean"

    def test_chinese_text_preserved(self):
        assert _sanitize_json_string("公文審查結果") == "公文審查結果"


# ============================================================
# _extract_json_object
# ============================================================

class TestExtractJsonObject:
    """測試 JSON 物件提取（平衡括號法）。"""

    def test_none_returns_none(self):
        assert _extract_json_object(None) is None

    def test_empty_returns_none(self):
        assert _extract_json_object("") is None

    def test_no_brace_returns_none(self):
        assert _extract_json_object("just text, no json") is None

    def test_simple_object(self):
        result = _extract_json_object('{"key": "value"}')
        assert result == '{"key": "value"}'
        assert json.loads(result) == {"key": "value"}

    def test_surrounded_by_text(self):
        text = 'Here is the result: {"score": 0.9} and some more text.'
        result = _extract_json_object(text)
        assert json.loads(result) == {"score": 0.9}

    def test_nested_objects(self):
        text = '{"outer": {"inner": 1}}'
        result = _extract_json_object(text)
        assert json.loads(result) == {"outer": {"inner": 1}}

    def test_string_with_braces(self):
        """JSON 值中包含大括號字元。"""
        text = '{"desc": "use {curly} braces"}'
        result = _extract_json_object(text)
        assert json.loads(result)["desc"] == "use {curly} braces"

    def test_escaped_quotes_in_string(self):
        """字串中包含轉義引號。"""
        text = r'{"desc": "he said \"hello\""}'
        result = _extract_json_object(text)
        assert result is not None
        parsed = json.loads(result)
        assert "hello" in parsed["desc"]

    def test_double_backslash_before_quote(self):
        r"""雙反斜線後接引號：\\" 表示反斜線結尾 + 字串終結。"""
        text = '{"path": "C:\\\\"}'
        result = _extract_json_object(text)
        assert result is not None

    def test_multiple_objects_returns_first(self):
        text = '{"a": 1} {"b": 2}'
        result = _extract_json_object(text)
        assert json.loads(result) == {"a": 1}

    def test_unbalanced_open_returns_none(self):
        """只有開括號沒有配對。"""
        assert _extract_json_object('{"key": "value"') is None

    def test_markdown_codeblock(self):
        """LLM 常用 markdown code block 包裹 JSON。"""
        text = '```json\n{"score": 0.85, "issues": []}\n```'
        result = _extract_json_object(text)
        assert json.loads(result) == {"score": 0.85, "issues": []}


# ============================================================
# parse_review_response
# ============================================================

class TestParseReviewResponse:
    """測試主解析函式。"""

    def _make_response(self, data: dict) -> str:
        return json.dumps(data, ensure_ascii=False)

    # --- 空值 / 錯誤回應 ---

    def test_none_response(self):
        result = parse_review_response(None, "TestAgent", "style")
        assert isinstance(result, ReviewResult)
        assert result.agent_name == "TestAgent"
        assert result.issues == []
        assert result.score == 0.8  # DEFAULT_REVIEW_SCORE

    def test_empty_string(self):
        result = parse_review_response("", "TestAgent", "style")
        assert result.issues == []
        assert result.score == 0.8

    def test_whitespace_only(self):
        result = parse_review_response("   \n  ", "TestAgent", "style")
        assert result.issues == []

    def test_error_prefix(self):
        """以 'Error' 開頭的回應視為 LLM 錯誤。"""
        result = parse_review_response("Error: connection refused", "TestAgent", "style")
        assert result.score == 0.0
        assert result.confidence == 0.0
        assert result.issues == []

    # --- 正常解析 ---

    def test_valid_response_no_issues(self):
        resp = self._make_response({"score": 0.95, "issues": [], "confidence": 0.9})
        result = parse_review_response(resp, "StyleChecker", "style")
        assert result.score == 0.95
        assert result.confidence == 0.9
        assert result.issues == []

    def test_valid_response_with_issues(self):
        resp = self._make_response({
            "score": 0.6,
            "confidence": 0.85,
            "issues": [
                {
                    "severity": "error",
                    "location": "第一段",
                    "description": "用詞不當",
                    "suggestion": "建議修改",
                    "risk_level": "high",
                }
            ],
        })
        result = parse_review_response(resp, "StyleChecker", "style")
        assert len(result.issues) == 1
        assert result.issues[0].severity == "error"
        assert result.issues[0].category == "style"
        assert result.issues[0].risk_level == "high"
        assert result.issues[0].suggestion == "建議修改"

    def test_multiple_issues(self):
        resp = self._make_response({
            "score": 0.5,
            "issues": [
                {"severity": "error", "location": "A", "description": "問題一"},
                {"severity": "warning", "location": "B", "description": "問題二"},
                {"severity": "info", "location": "C", "description": "問題三"},
            ],
        })
        result = parse_review_response(resp, "Agent", "fact")
        assert len(result.issues) == 3
        for issue in result.issues:
            assert issue.category == "fact"

    # --- severity 驗證 ---

    def test_invalid_severity_defaults_to_info(self):
        resp = self._make_response({
            "score": 0.7,
            "issues": [
                {"severity": "critical", "location": "X", "description": "嚴重問題"}
            ],
        })
        result = parse_review_response(resp, "Agent", "style")
        assert result.issues[0].severity == "info"

    def test_missing_severity_defaults_to_info(self):
        resp = self._make_response({
            "score": 0.7,
            "issues": [
                {"location": "X", "description": "缺少嚴重性"}
            ],
        })
        result = parse_review_response(resp, "Agent", "style")
        assert result.issues[0].severity == "info"

    # --- derive_risk_from_severity ---

    def test_derive_risk_from_severity_error(self):
        resp = self._make_response({
            "score": 0.5,
            "issues": [
                {"severity": "error", "location": "A", "description": "錯誤", "risk_level": "low"}
            ],
        })
        result = parse_review_response(resp, "Agent", "style", derive_risk_from_severity=True)
        assert result.issues[0].risk_level == "high"  # severity=error → high（忽略 LLM 的 low）

    def test_derive_risk_from_severity_warning(self):
        resp = self._make_response({
            "score": 0.5,
            "issues": [
                {"severity": "warning", "location": "A", "description": "警告"}
            ],
        })
        result = parse_review_response(resp, "Agent", "style", derive_risk_from_severity=True)
        assert result.issues[0].risk_level == "medium"

    def test_derive_risk_from_severity_info(self):
        resp = self._make_response({
            "score": 0.5,
            "issues": [
                {"severity": "info", "location": "A", "description": "資訊"}
            ],
        })
        result = parse_review_response(resp, "Agent", "style", derive_risk_from_severity=True)
        assert result.issues[0].risk_level == "low"

    def test_no_derive_uses_llm_risk(self):
        resp = self._make_response({
            "score": 0.5,
            "issues": [
                {"severity": "info", "location": "A", "description": "X", "risk_level": "high"}
            ],
        })
        result = parse_review_response(resp, "Agent", "style", derive_risk_from_severity=False)
        assert result.issues[0].risk_level == "high"

    def test_invalid_risk_level_defaults_to_low(self):
        resp = self._make_response({
            "score": 0.5,
            "issues": [
                {"severity": "info", "location": "A", "description": "X", "risk_level": "critical"}
            ],
        })
        result = parse_review_response(resp, "Agent", "style")
        assert result.issues[0].risk_level == "low"

    # --- 分數/信心度鉗位 ---

    def test_score_clamped_above_1(self):
        resp = self._make_response({"score": 1.5, "issues": []})
        result = parse_review_response(resp, "Agent", "style")
        assert result.score == 1.0

    def test_score_clamped_below_0(self):
        resp = self._make_response({"score": -0.5, "issues": []})
        result = parse_review_response(resp, "Agent", "style")
        assert result.score == 0.0

    def test_confidence_clamped(self):
        resp = self._make_response({"score": 0.8, "confidence": 2.0, "issues": []})
        result = parse_review_response(resp, "Agent", "style")
        assert result.confidence == 1.0

    def test_nan_score_uses_default(self):
        resp = self._make_response({"score": float("nan"), "issues": []})
        result = parse_review_response(resp, "Agent", "style")
        assert result.score == 0.8  # DEFAULT_REVIEW_SCORE

    def test_inf_score_uses_default(self):
        resp = self._make_response({"score": float("inf"), "issues": []})
        result = parse_review_response(resp, "Agent", "style")
        assert result.score == 0.8

    def test_non_numeric_score_uses_default(self):
        resp = '{"score": "excellent", "issues": []}'
        result = parse_review_response(resp, "Agent", "style")
        assert result.score == 0.8

    def test_nan_confidence_uses_default(self):
        resp = self._make_response({"score": 0.8, "confidence": float("nan"), "issues": []})
        result = parse_review_response(resp, "Agent", "style")
        assert result.confidence == 1.0  # default_confidence

    def test_non_numeric_confidence_uses_default(self):
        resp = '{"score": 0.8, "confidence": "high", "issues": []}'
        result = parse_review_response(resp, "Agent", "style")
        assert result.confidence == 1.0

    # --- 預設值 / 缺少欄位 ---

    def test_missing_score_uses_default(self):
        resp = '{"issues": []}'
        result = parse_review_response(resp, "Agent", "style")
        assert result.score == 0.8

    def test_custom_defaults(self):
        resp = '{"issues": []}'
        result = parse_review_response(resp, "Agent", "style", default_score=0.5, default_confidence=0.7)
        assert result.score == 0.5
        assert result.confidence == 0.7

    def test_missing_location_defaults(self):
        resp = self._make_response({
            "score": 0.7,
            "issues": [{"severity": "info", "description": "缺少位置"}],
        })
        result = parse_review_response(resp, "Agent", "style")
        assert result.issues[0].location == "未知"

    def test_missing_description_defaults(self):
        resp = self._make_response({
            "score": 0.7,
            "issues": [{"severity": "info", "location": "A"}],
        })
        result = parse_review_response(resp, "Agent", "style")
        assert result.issues[0].description == "（無描述）"

    # --- 容錯 ---

    def test_issues_not_list_ignored(self):
        resp = '{"score": 0.7, "issues": "some string"}'
        result = parse_review_response(resp, "Agent", "style")
        assert result.issues == []

    def test_issue_not_dict_skipped(self):
        resp = '{"score": 0.7, "issues": ["string item", 42]}'
        result = parse_review_response(resp, "Agent", "style")
        assert result.issues == []

    def test_no_json_in_response(self):
        result = parse_review_response("This response has no JSON at all.", "Agent", "style")
        assert result.issues == []
        assert result.score == 0.8

    def test_invalid_json_returns_default(self):
        result = parse_review_response("{broken json", "Agent", "style")
        assert result.issues == []
        assert result.score == 0.8

    def test_unicode_chars_cleaned_before_parse(self):
        """BOM + ZWSP 在 key 中應被清理後正常解析。"""
        resp = '\ufeff{"sc\u200bore": 0.7, "iss\u200cues": []}'
        result = parse_review_response(resp, "Agent", "style")
        assert result.score == 0.7
        assert result.issues == []

    def test_markdown_wrapped_json(self):
        resp = '審查結果如下：\n```json\n{"score": 0.9, "issues": []}\n```\n請參考。'
        result = parse_review_response(resp, "Agent", "style")
        assert result.score == 0.9


# ============================================================
# format_audit_to_review_result
# ============================================================

class TestFormatAuditToReviewResult:
    """測試 FormatAuditor 結果轉換。"""

    def test_empty_audit(self):
        result = format_audit_to_review_result({"errors": [], "warnings": []})
        assert result.agent_name == "Format Auditor"
        assert result.score == 1.0
        assert result.issues == []
        assert result.confidence == 1.0

    def test_no_errors_no_warnings_keys(self):
        result = format_audit_to_review_result({})
        assert result.score == 1.0
        assert result.issues == []

    def test_custom_agent_name(self):
        result = format_audit_to_review_result({}, agent_name="CustomAuditor")
        assert result.agent_name == "CustomAuditor"

    def test_errors_as_dicts(self):
        audit = {
            "errors": [
                {
                    "location": "標題",
                    "description": "缺少發文字號",
                    "suggestion": "請加上字號",
                }
            ],
            "warnings": [],
        }
        result = format_audit_to_review_result(audit)
        assert len(result.issues) == 1
        issue = result.issues[0]
        assert issue.category == "format"
        assert issue.severity == "error"
        assert issue.risk_level == "high"
        assert issue.location == "標題"
        assert issue.description == "缺少發文字號"
        assert issue.suggestion == "請加上字號"

    def test_errors_as_strings(self):
        audit = {"errors": ["缺少日期"], "warnings": []}
        result = format_audit_to_review_result(audit)
        assert len(result.issues) == 1
        assert result.issues[0].description == "缺少日期"
        assert result.issues[0].location == "文件結構"

    def test_warnings_as_dicts(self):
        audit = {
            "errors": [],
            "warnings": [
                {"location": "第二段", "description": "語句冗長"}
            ],
        }
        result = format_audit_to_review_result(audit)
        assert len(result.issues) == 1
        issue = result.issues[0]
        assert issue.severity == "warning"
        assert issue.risk_level == "medium"

    def test_warnings_as_strings(self):
        audit = {"errors": [], "warnings": ["格式建議"]}
        result = format_audit_to_review_result(audit)
        assert result.issues[0].severity == "warning"
        assert result.issues[0].description == "格式建議"

    def test_mixed_errors_and_warnings(self):
        audit = {
            "errors": [{"location": "A", "description": "錯誤"}],
            "warnings": [{"location": "B", "description": "警告"}],
        }
        result = format_audit_to_review_result(audit)
        assert len(result.issues) == 2
        errors = [i for i in result.issues if i.severity == "error"]
        warnings = [i for i in result.issues if i.severity == "warning"]
        assert len(errors) == 1
        assert len(warnings) == 1

    # --- 分數動態計算 ---

    def test_score_with_one_error(self):
        audit = {"errors": [{"location": "A", "description": "E"}], "warnings": []}
        result = format_audit_to_review_result(audit)
        assert result.score == pytest.approx(0.6)  # 0.7 - 1*0.1

    def test_score_with_multiple_errors(self):
        audit = {
            "errors": [
                {"location": "A", "description": "E1"},
                {"location": "B", "description": "E2"},
                {"location": "C", "description": "E3"},
            ],
            "warnings": [],
        }
        result = format_audit_to_review_result(audit)
        assert result.score == pytest.approx(0.4)  # 0.7 - 3*0.1

    def test_score_many_errors_clamped_to_zero(self):
        """超過 7 個 error 時分數不低於 0。"""
        audit = {
            "errors": [{"location": f"L{i}", "description": f"E{i}"} for i in range(10)],
            "warnings": [],
        }
        result = format_audit_to_review_result(audit)
        assert result.score == 0.0

    def test_score_warnings_only(self):
        audit = {
            "errors": [],
            "warnings": [
                {"location": "A", "description": "W1"},
                {"location": "B", "description": "W2"},
            ],
        }
        result = format_audit_to_review_result(audit)
        assert result.score == pytest.approx(0.9)  # 1.0 - 2*0.05

    def test_score_many_warnings_clamped_to_half(self):
        """超過 10 個 warning 時分數不低於 0.5。"""
        audit = {
            "errors": [],
            "warnings": [{"location": f"L{i}", "description": f"W{i}"} for i in range(20)],
        }
        result = format_audit_to_review_result(audit)
        assert result.score == 0.5

    def test_error_dict_missing_location(self):
        audit = {"errors": [{"description": "缺位置"}], "warnings": []}
        result = format_audit_to_review_result(audit)
        assert result.issues[0].location == "文件結構"

    def test_error_dict_missing_description(self):
        audit = {"errors": [{"location": "標題"}], "warnings": []}
        result = format_audit_to_review_result(audit)
        # description 來自 str(err)
        assert "標題" in result.issues[0].description
