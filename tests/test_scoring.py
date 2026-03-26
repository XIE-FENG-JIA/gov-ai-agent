"""
core/scoring.py 單元測試 — 評分與風險判定的核心純函式。

測試範圍：
- get_agent_category: Agent 名稱 → 類別對應
- calculate_weighted_scores: 加權品質分數計算
- calculate_risk_scores: 加權風險分數計算
- assess_risk_level: 風險等級判定（從 constants 重新匯出）
"""

import pytest

from src.core.review_models import ReviewIssue, ReviewResult
from src.core.scoring import (
    get_agent_category,
    calculate_weighted_scores,
    calculate_risk_scores,
    CATEGORY_WEIGHTS,
    assess_risk_level,
)
from src.core.constants import WARNING_WEIGHT_FACTOR


# ============================================================
# 輔助工廠
# ============================================================

def _issue(category: str = "format", severity: str = "error") -> ReviewIssue:
    """建立測試用的 ReviewIssue。"""
    return ReviewIssue(
        category=category,
        severity=severity,
        risk_level="low",
        location="測試位置",
        description="測試描述",
    )


def _result(
    agent_name: str = "Format Auditor",
    score: float = 0.9,
    confidence: float = 1.0,
    issues: list[ReviewIssue] | None = None,
) -> ReviewResult:
    """建立測試用的 ReviewResult。"""
    return ReviewResult(
        agent_name=agent_name,
        score=score,
        confidence=confidence,
        issues=issues or [],
    )


# ============================================================
# get_agent_category
# ============================================================

class TestGetAgentCategory:
    """Agent 名稱 → 類別對應測試。"""

    @pytest.mark.parametrize(
        "name, expected",
        [
            ("Format Auditor", "format"),
            ("format_checker", "format"),
            ("Auditor Agent", "format"),
            ("Compliance Checker", "compliance"),
            ("Policy Verifier", "compliance"),
            ("Fact Checker", "fact"),
            ("fact_verifier", "fact"),
            ("Consistency Checker", "consistency"),
            ("Style Checker", "style"),
            ("Unknown Agent", "style"),  # 預設 fallback
            ("", "style"),  # 空字串 fallback
        ],
    )
    def test_category_mapping(self, name: str, expected: str):
        assert get_agent_category(name) == expected

    def test_case_insensitive(self):
        """名稱比對應忽略大小寫。"""
        assert get_agent_category("FORMAT AUDITOR") == "format"
        assert get_agent_category("COMPLIANCE checker") == "compliance"
        assert get_agent_category("FACT verifier") == "fact"


# ============================================================
# calculate_weighted_scores
# ============================================================

class TestCalculateWeightedScores:
    """加權品質分數計算測試。"""

    def test_empty_results(self):
        """空結果列表回傳 (0.0, 0.0)。"""
        ws, tw = calculate_weighted_scores([])
        assert ws == 0.0
        assert tw == 0.0

    def test_single_result_full_confidence(self):
        """單一結果、信心度 1.0 的加權計算。"""
        r = _result("Format Auditor", score=0.8, confidence=1.0)
        ws, tw = calculate_weighted_scores([r])
        expected_weight = CATEGORY_WEIGHTS["format"]  # 3.0
        assert ws == pytest.approx(0.8 * expected_weight * 1.0)
        assert tw == pytest.approx(expected_weight * 1.0)

    def test_single_result_partial_confidence(self):
        """信心度 < 1.0 時權重應按比例降低。"""
        r = _result("Fact Checker", score=0.7, confidence=0.5)
        ws, tw = calculate_weighted_scores([r])
        w = CATEGORY_WEIGHTS["fact"]  # 2.0
        assert ws == pytest.approx(0.7 * w * 0.5)
        assert tw == pytest.approx(w * 0.5)

    def test_multiple_results(self):
        """多個 Agent 結果的加權計算正確累加。"""
        results = [
            _result("Format Auditor", score=0.9, confidence=1.0),
            _result("Style Checker", score=0.8, confidence=0.8),
            _result("Fact Checker", score=0.7, confidence=1.0),
        ]
        ws, tw = calculate_weighted_scores(results)

        # 手動計算期望值
        expected_ws = (
            0.9 * CATEGORY_WEIGHTS["format"] * 1.0
            + 0.8 * CATEGORY_WEIGHTS["style"] * 0.8
            + 0.7 * CATEGORY_WEIGHTS["fact"] * 1.0
        )
        expected_tw = (
            CATEGORY_WEIGHTS["format"] * 1.0
            + CATEGORY_WEIGHTS["style"] * 0.8
            + CATEGORY_WEIGHTS["fact"] * 1.0
        )
        assert ws == pytest.approx(expected_ws)
        assert tw == pytest.approx(expected_tw)

    def test_zero_confidence_excluded(self):
        """信心度 0 的 Agent 不影響加權（權重貢獻為 0）。"""
        results = [
            _result("Format Auditor", score=0.9, confidence=1.0),
            _result("Style Checker", score=0.0, confidence=0.0),
        ]
        ws, tw = calculate_weighted_scores(results)
        # 只有 Format Auditor 有貢獻
        assert ws == pytest.approx(0.9 * CATEGORY_WEIGHTS["format"])
        assert tw == pytest.approx(CATEGORY_WEIGHTS["format"])

    def test_avg_score_derivation(self):
        """驗證 ws/tw 可正確算出平均分數（呼叫方的使用模式）。"""
        results = [
            _result("Format Auditor", score=1.0, confidence=1.0),
            _result("Compliance Checker", score=1.0, confidence=1.0),
        ]
        ws, tw = calculate_weighted_scores(results)
        avg = ws / tw if tw > 0 else 0.0
        assert avg == pytest.approx(1.0)


# ============================================================
# calculate_risk_scores
# ============================================================

class TestCalculateRiskScores:
    """加權風險分數計算測試。"""

    def test_empty_results(self):
        """空結果列表回傳 (0.0, 0.0)。"""
        es, ws = calculate_risk_scores([])
        assert es == 0.0
        assert ws == 0.0

    def test_no_issues(self):
        """結果中無 issues 時風險分數為零。"""
        r = _result("Format Auditor", issues=[])
        es, ws = calculate_risk_scores([r])
        assert es == 0.0
        assert ws == 0.0

    def test_error_issues_weighted(self):
        """error 嚴重度的 issue 按類別權重累加。"""
        r = _result(
            "Format Auditor",
            issues=[_issue("format", "error"), _issue("format", "error")],
        )
        es, ws = calculate_risk_scores([r])
        assert es == pytest.approx(CATEGORY_WEIGHTS["format"] * 2)
        assert ws == 0.0  # 無 warning

    def test_warning_issues_weighted_with_factor(self):
        """warning 嚴重度使用 WARNING_WEIGHT_FACTOR 打折。"""
        r = _result(
            "Compliance Checker",
            issues=[_issue("compliance", "warning")],
        )
        es, ws = calculate_risk_scores([r])
        assert es == 0.0  # 無 error
        assert ws == pytest.approx(
            CATEGORY_WEIGHTS["compliance"] * WARNING_WEIGHT_FACTOR
        )

    def test_info_issues_ignored(self):
        """info 嚴重度的 issue 不計入風險分數。"""
        r = _result(
            "Style Checker",
            issues=[_issue("style", "info")],
        )
        es, ws = calculate_risk_scores([r])
        assert es == 0.0
        assert ws == 0.0

    def test_mixed_issues(self):
        """混合 error + warning + info，各自正確累加。"""
        r = _result(
            "Fact Checker",
            issues=[
                _issue("fact", "error"),
                _issue("fact", "warning"),
                _issue("fact", "info"),
            ],
        )
        es, ws = calculate_risk_scores([r])
        w = CATEGORY_WEIGHTS["fact"]
        assert es == pytest.approx(w)  # 1 error
        assert ws == pytest.approx(w * WARNING_WEIGHT_FACTOR)  # 1 warning

    def test_multiple_agents_mixed(self):
        """跨 Agent 的風險分數正確累加。"""
        results = [
            _result("Format Auditor", issues=[_issue("format", "error")]),
            _result("Compliance Checker", issues=[_issue("compliance", "warning")]),
        ]
        es, ws = calculate_risk_scores(results)
        assert es == pytest.approx(CATEGORY_WEIGHTS["format"])
        assert ws == pytest.approx(
            CATEGORY_WEIGHTS["compliance"] * WARNING_WEIGHT_FACTOR
        )


# ============================================================
# assess_risk_level（從 scoring 重新匯出）
# ============================================================

class TestAssessRiskLevel:
    """風險等級判定測試。"""

    def test_critical_high_error_score(self):
        """加權錯誤分數 >= 3.0 → Critical。"""
        assert assess_risk_level(3.0, 0.0, 1.0) == "Critical"
        assert assess_risk_level(5.0, 0.0, 0.5) == "Critical"

    def test_high_any_error_or_high_warning(self):
        """有任何 error（< 3.0）或高 warning → High。"""
        assert assess_risk_level(0.1, 0.0, 1.0) == "High"
        assert assess_risk_level(0.0, 3.0, 1.0) == "High"
        assert assess_risk_level(0.0, 5.0, 1.0) == "High"

    def test_moderate_low_warning_or_low_score(self):
        """有 warning（< 3.0）或分數 < 0.9 → Moderate。"""
        assert assess_risk_level(0.0, 0.1, 1.0) == "Moderate"
        assert assess_risk_level(0.0, 0.0, 0.85) == "Moderate"

    def test_low_score_between_thresholds(self):
        """分數 0.9 ~ 0.95 → Low。"""
        assert assess_risk_level(0.0, 0.0, 0.92) == "Low"
        assert assess_risk_level(0.0, 0.0, 0.90) == "Low"

    def test_safe_high_score(self):
        """分數 >= 0.95 且無 error/warning → Safe。"""
        assert assess_risk_level(0.0, 0.0, 0.95) == "Safe"
        assert assess_risk_level(0.0, 0.0, 1.0) == "Safe"

    def test_critical_overrides_all(self):
        """Critical 等級優先於其他條件。"""
        # 即使分數很高，error 分數夠高仍為 Critical
        assert assess_risk_level(3.0, 5.0, 1.0) == "Critical"

    def test_boundary_values(self):
        """邊界值測試。"""
        # 剛好低於 Critical 閾值 → High（因為 error > 0）
        assert assess_risk_level(2.99, 0.0, 1.0) == "High"
        # 零 error、零 warning、分數剛好 0.95 → Safe
        assert assess_risk_level(0.0, 0.0, 0.95) == "Safe"
        # 零 error、零 warning、分數剛好 0.9 → Low
        assert assess_risk_level(0.0, 0.0, 0.9) == "Low"
        # 零 error、零 warning、分數 0.8999 → Moderate
        assert assess_risk_level(0.0, 0.0, 0.8999) == "Moderate"


# ============================================================
# 整合場景：calculate → assess 端到端
# ============================================================

class TestScoringEndToEnd:
    """模擬完整的計算流程：results → scores → risk level。"""

    def test_perfect_review(self):
        """全部滿分、無 issue → Safe。"""
        results = [
            _result("Format Auditor", score=1.0, confidence=1.0),
            _result("Compliance Checker", score=1.0, confidence=1.0),
            _result("Fact Checker", score=1.0, confidence=1.0),
        ]
        ws, tw = calculate_weighted_scores(results)
        avg = ws / tw
        es, ww = calculate_risk_scores(results)
        risk = assess_risk_level(es, ww, avg)
        assert avg == pytest.approx(1.0)
        assert risk == "Safe"

    def test_critical_format_errors(self):
        """格式 Agent 報告多個 error → Critical。"""
        results = [
            _result(
                "Format Auditor",
                score=0.3,
                confidence=1.0,
                issues=[_issue("format", "error")] * 2,  # 2 × 3.0 = 6.0
            ),
        ]
        es, ww = calculate_risk_scores(results)
        assert es == pytest.approx(6.0)
        risk = assess_risk_level(es, ww, 0.3)
        assert risk == "Critical"

    def test_moderate_with_warnings(self):
        """只有低權重 warning → Moderate。"""
        results = [
            _result(
                "Style Checker",
                score=0.95,
                confidence=1.0,
                issues=[_issue("style", "warning")],
            ),
        ]
        ws, tw = calculate_weighted_scores(results)
        avg = ws / tw
        es, ww = calculate_risk_scores(results)
        risk = assess_risk_level(es, ww, avg)
        assert avg == pytest.approx(0.95)
        assert risk == "Moderate"  # warning > 0 → Moderate
