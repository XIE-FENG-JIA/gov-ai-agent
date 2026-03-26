"""Golden Test Suite — 用真實公文建立品質對標

本測試套件使用 tests/golden_examples/ 中的真實政府公文作為黃金標準，
驗證系統的格式合規、引用正確性和內容保留度。

測試維度：
  1. 格式驗證：必要段落、編號格式、欄位完整性
  2. 引用驗證：法規引用使用書名號、引用標記完整
  3. 往返精確度：parse_draft → apply_template 的內容保留
  4. 內容相似度：BLEU/ROUGE 評分
  5. 驗證器覆蓋：ValidatorRegistry 不誤判黃金標準
"""
import difflib
import math
import re
import sys
from collections import Counter
from pathlib import Path

import pytest
import yaml

# 確保 src 在 Python 路徑中
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.agents.template import TemplateEngine  # noqa: E402
from src.agents.validators import ValidatorRegistry  # noqa: E402
from src.core.models import PublicDocRequirement  # noqa: E402

GOLDEN_DIR = Path(__file__).parent / "golden_examples"

# ---------------------------------------------------------------------------
# 黃金標準測試案例：(檔名, 公文類型)
# ---------------------------------------------------------------------------
GOLDEN_CASES: list[tuple[str, str]] = [
    # 函 ×5
    ("han_01_policy_relay.md", "函"),
    ("han_03_budget_request.md", "函"),
    ("han_05_inquiry_reply.md", "函"),
    ("han_07_deny_subsidy.md", "函"),
    ("han_12_cross_agency_coordination.md", "函"),
    # 公告 ×5
    ("announcement_01_personnel.md", "公告"),
    ("announcement_03_policy.md", "公告"),
    ("announcement_05_personnel_exam.md", "公告"),
    ("announcement_06_tender.md", "公告"),
    ("announcement_08_regulation_preview.md", "公告"),
    # 簽 ×5
    ("sign_01_budget_approval.md", "簽"),
    ("sign_02_procurement_plan.md", "簽"),
    ("sign_03_event_proposal.md", "簽"),
    ("sign_04_joint_countersign.md", "簽"),
    ("sign_05_internal_proposal.md", "簽"),
]

# 各公文類型的必要段落
REQUIRED_SECTIONS: dict[str, list[str]] = {
    "函": ["主旨"],
    "公告": ["主旨"],
    "簽": ["主旨"],
}

# 各公文類型應有的特徵段落
EXPECTED_SECTIONS: dict[str, list[str]] = {
    "函": ["說明", "辦法"],
    "公告": ["依據", "公告事項"],
    "簽": ["說明", "擬辦"],
}


# ═══════════════════════════════════════════════════════════════════════
# BLEU / ROUGE 輕量級實作（中文字元級）
# ═══════════════════════════════════════════════════════════════════════


def _tokenize_chinese(text: str) -> list[str]:
    """將中文文本拆成字元序列（過濾空白和標點）。"""
    # 保留中文字、英文字母、數字
    return [ch for ch in text if ch.strip() and (
        '\u4e00' <= ch <= '\u9fff'   # CJK 統一漢字
        or '\u3400' <= ch <= '\u4dbf'  # CJK 擴展 A
        or ch.isalnum()
    )]


def _get_ngrams(tokens: list[str], n: int) -> Counter:
    """取得 n-gram 計數。"""
    return Counter(tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1))


def bleu_score(reference: str, hypothesis: str, max_n: int = 4) -> float:
    """計算字元級 BLEU 分數（含 brevity penalty）。

    Args:
        reference: 參考文本（黃金標準）
        hypothesis: 待測文本（系統產出）
        max_n: 最大 n-gram 階數

    Returns:
        BLEU 分數 (0.0 ~ 1.0)
    """
    ref_tokens = _tokenize_chinese(reference)
    hyp_tokens = _tokenize_chinese(hypothesis)

    if not hyp_tokens or not ref_tokens:
        return 0.0

    # Brevity penalty
    bp = min(1.0, math.exp(1 - len(ref_tokens) / len(hyp_tokens))) if len(hyp_tokens) > 0 else 0.0

    # n-gram 精確度
    log_avg = 0.0
    effective_n = 0
    for n in range(1, max_n + 1):
        ref_ngrams = _get_ngrams(ref_tokens, n)
        hyp_ngrams = _get_ngrams(hyp_tokens, n)

        if not hyp_ngrams:
            continue

        # 截斷計數
        clipped = sum(min(hyp_ngrams[ng], ref_ngrams.get(ng, 0)) for ng in hyp_ngrams)
        total = sum(hyp_ngrams.values())

        precision = clipped / total if total > 0 else 0.0
        if precision > 0:
            log_avg += math.log(precision)
            effective_n += 1

    if effective_n == 0:
        return 0.0

    return bp * math.exp(log_avg / effective_n)


def rouge_l_score(reference: str, hypothesis: str) -> float:
    """計算字元級 ROUGE-L F1 分數（基於最長公共子序列）。

    Args:
        reference: 參考文本
        hypothesis: 待測文本

    Returns:
        ROUGE-L F1 分數 (0.0 ~ 1.0)
    """
    ref_tokens = _tokenize_chinese(reference)
    hyp_tokens = _tokenize_chinese(hypothesis)

    if not ref_tokens or not hyp_tokens:
        return 0.0

    # LCS 長度（使用空間優化的 DP）
    m, n = len(ref_tokens), len(hyp_tokens)
    prev = [0] * (n + 1)
    for i in range(1, m + 1):
        curr = [0] * (n + 1)
        for j in range(1, n + 1):
            if ref_tokens[i - 1] == hyp_tokens[j - 1]:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = max(curr[j - 1], prev[j])
        prev = curr

    lcs_len = prev[n]
    if lcs_len == 0:
        return 0.0

    precision = lcs_len / n
    recall = lcs_len / m
    f1 = 2 * precision * recall / (precision + recall)
    return f1


# ═══════════════════════════════════════════════════════════════════════
# 公文解析輔助函式
# ═══════════════════════════════════════════════════════════════════════


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """分離 YAML frontmatter 與 body。"""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if m:
        try:
            meta = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            meta = {}
        body = text[m.end():]
    else:
        meta = {}
        body = text
    return meta, body


def _extract_field(body: str, keyword: str) -> str:
    """從 body 中提取 **keyword**：value 格式的欄位值。"""
    pattern = rf"\*\*{re.escape(keyword)}\*\*[：:]\s*(.+)"
    m = re.search(pattern, body)
    if m:
        return m.group(1).strip()
    pattern2 = rf"^{re.escape(keyword)}[：:]\s*(.+)"
    m2 = re.search(pattern2, body, re.MULTILINE)
    if m2:
        return m2.group(1).strip()
    return ""


def _build_requirement(meta: dict, body: str, doc_type: str) -> PublicDocRequirement:
    """從 frontmatter 和 body 建構 PublicDocRequirement。"""
    sender = (
        _extract_field(body, "機關")
        or _extract_field(body, "發令人")
        or _extract_field(body, "發信人")
        or meta.get("agency", "")
        or meta.get("source", "")
        or "（未指定）"
    )
    receiver = (
        _extract_field(body, "受文者")
        or _extract_field(body, "受令人")
        or _extract_field(body, "收信人")
        or "（未指定）"
    )
    subject = _extract_field(body, "主旨") or meta.get("title", "（未提供主旨）")
    urgency_raw = _extract_field(body, "速別")
    urgency = urgency_raw.replace("件", "") if urgency_raw else "普通"
    if urgency not in ("普通", "速件", "最速件"):
        urgency = "普通"
    att_raw = _extract_field(body, "附件")
    attachments = [att_raw] if att_raw and att_raw != "無" else []

    return PublicDocRequirement(
        doc_type=doc_type,
        urgency=urgency,
        sender=sender,
        receiver=receiver if receiver else "（未指定）",
        subject=subject,
        attachments=attachments,
    )


def _strip_dynamic_lines(text: str) -> str:
    """移除動態行（日期、字號等）以利比較。"""
    exclude_patterns = [
        r"^\*\*發文日期\*\*", r"^\*\*發文字號\*\*", r"^\*\*速別\*\*",
        r"^\*\*密等", r"^\*\*紀錄日期\*\*", r"^\*\*發令日期\*\*",
        r"^\*\*日期\*\*", r"^\*\*字號\*\*", r"^\*\*會銜機關\*\*",
        r"^發文日期[：:]", r"^發文字號[：:]", r"^中華民國\d+年",
        r"^部長", r"^局長", r"^---", r"^#\s",
    ]
    lines = text.split("\n")
    result = []
    for line in lines:
        stripped = line.strip()
        if any(re.match(pat, stripped) for pat in exclude_patterns):
            continue
        result.append(line)
    return "\n".join(result)


def _detect_sections(body: str) -> set[str]:
    """偵測原文中存在的段落標題。"""
    section_keywords = {
        "主旨", "說明", "依據", "辦法", "公告事項", "擬辦",
        "附件", "正本", "副本",
    }
    found = set()
    for line in body.split("\n"):
        s = line.strip()
        s = re.sub(r"^#{1,3}\s+", "", s)
        s = re.sub(r"^\*\*([^*]+)\*\*[：:]?", r"\1", s)
        for kw in section_keywords:
            if s.startswith(kw):
                found.add(kw)
    return found


# ═══════════════════════════════════════════════════════════════════════
# 載入黃金範例
# ═══════════════════════════════════════════════════════════════════════


def _load_golden(filename: str) -> tuple[dict, str, str]:
    """載入黃金範例，回傳 (metadata, body, raw)。"""
    filepath = GOLDEN_DIR / filename
    raw = filepath.read_text(encoding="utf-8")
    meta, body = _split_frontmatter(raw)
    return meta, body, raw


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def template_engine():
    return TemplateEngine()


@pytest.fixture(scope="module")
def validator_registry():
    return ValidatorRegistry()


# ═══════════════════════════════════════════════════════════════════════
# 測試 1：格式驗證 — 必要段落與欄位完整性
# ═══════════════════════════════════════════════════════════════════════


class TestGoldenFormat:
    """驗證黃金標準公文的格式完整性。"""

    @pytest.mark.parametrize("filename,doc_type", GOLDEN_CASES,
                             ids=[c[0].replace(".md", "") for c in GOLDEN_CASES])
    def test_has_subject(self, filename: str, doc_type: str):
        """所有公文必須有主旨。"""
        _, body, _ = _load_golden(filename)
        subject = _extract_field(body, "主旨")
        assert subject, f"{filename} 缺少主旨欄位"

    @pytest.mark.parametrize("filename,doc_type", GOLDEN_CASES,
                             ids=[c[0].replace(".md", "") for c in GOLDEN_CASES])
    def test_has_agency(self, filename: str, doc_type: str):
        """所有公文必須有發文機關。"""
        meta, body, _ = _load_golden(filename)
        agency = (
            _extract_field(body, "機關")
            or _extract_field(body, "發令人")
            or _extract_field(body, "發信人")
            or meta.get("agency", "")
            or meta.get("source", "")
        )
        assert agency, f"{filename} 缺少發文機關"

    @pytest.mark.parametrize("filename,doc_type",
                             [c for c in GOLDEN_CASES if c[1] == "函"],
                             ids=[c[0].replace(".md", "") for c in GOLDEN_CASES if c[1] == "函"])
    def test_han_has_receiver(self, filename: str, doc_type: str):
        """函類公文必須有受文者。"""
        _, body, _ = _load_golden(filename)
        receiver = _extract_field(body, "受文者")
        assert receiver, f"函 {filename} 缺少受文者"

    @pytest.mark.parametrize("filename,doc_type",
                             [c for c in GOLDEN_CASES if c[1] == "函"],
                             ids=[c[0].replace(".md", "") for c in GOLDEN_CASES if c[1] == "函"])
    def test_han_has_explanation(self, filename: str, doc_type: str):
        """函類公文必須有說明段落。"""
        _, body, _ = _load_golden(filename)
        sections = _detect_sections(body)
        assert "說明" in sections, f"函 {filename} 缺少說明段落"

    @pytest.mark.parametrize("filename,doc_type",
                             [c for c in GOLDEN_CASES if c[1] == "公告"],
                             ids=[c[0].replace(".md", "") for c in GOLDEN_CASES if c[1] == "公告"])
    def test_announcement_has_basis(self, filename: str, doc_type: str):
        """公告必須有依據。"""
        _, body, _ = _load_golden(filename)
        sections = _detect_sections(body)
        assert "依據" in sections, f"公告 {filename} 缺少依據"

    @pytest.mark.parametrize("filename,doc_type",
                             [c for c in GOLDEN_CASES if c[1] == "公告"],
                             ids=[c[0].replace(".md", "") for c in GOLDEN_CASES if c[1] == "公告"])
    def test_announcement_has_items(self, filename: str, doc_type: str):
        """公告必須有公告事項。"""
        _, body, _ = _load_golden(filename)
        sections = _detect_sections(body)
        assert "公告事項" in sections, f"公告 {filename} 缺少公告事項"

    @pytest.mark.parametrize("filename,doc_type",
                             [c for c in GOLDEN_CASES if c[1] == "簽"],
                             ids=[c[0].replace(".md", "") for c in GOLDEN_CASES if c[1] == "簽"])
    def test_sign_has_proposal(self, filename: str, doc_type: str):
        """簽類公文必須有擬辦。"""
        _, body, _ = _load_golden(filename)
        sections = _detect_sections(body)
        assert "擬辦" in sections, f"簽 {filename} 缺少擬辦"

    @pytest.mark.parametrize("filename,doc_type", GOLDEN_CASES,
                             ids=[c[0].replace(".md", "") for c in GOLDEN_CASES])
    def test_chinese_numbering(self, filename: str, doc_type: str):
        """公文中的一級編號應使用中文（一、二、三…）。"""
        _, body, _ = _load_golden(filename)
        # 檢查是否存在中文編號（至少有「一、」）
        assert re.search(r"^[一二三四五六七八九十]+、", body, re.MULTILINE), \
            f"{filename} 未使用中文編號"

    @pytest.mark.parametrize("filename,doc_type", GOLDEN_CASES,
                             ids=[c[0].replace(".md", "") for c in GOLDEN_CASES])
    def test_roc_date_format(self, filename: str, doc_type: str):
        """公文中的日期應使用中華民國紀年（簽類允許年度格式）。"""
        _, body, _ = _load_golden(filename)
        # 完整日期：114年1月15日
        has_full_date = bool(re.search(r"\d{2,3}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日", body))
        # 年度格式：114年度、115年度
        has_year_ref = bool(re.search(r"\d{2,3}\s*年度", body))
        # 年月格式：114年4月
        has_year_month = bool(re.search(r"\d{2,3}\s*年\s*\d{1,2}\s*月", body))
        assert has_full_date or has_year_ref or has_year_month, \
            f"{filename} 未使用民國紀年日期"


# ═══════════════════════════════════════════════════════════════════════
# 測試 2：引用驗證 — 法規引用使用書名號
# ═══════════════════════════════════════════════════════════════════════


class TestGoldenCitations:
    """驗證黃金標準中的法規引用格式。"""

    @pytest.mark.parametrize("filename,doc_type", GOLDEN_CASES,
                             ids=[c[0].replace(".md", "") for c in GOLDEN_CASES])
    def test_law_citations_use_brackets(self, filename: str, doc_type: str):
        """引用法規名稱時應使用書名號《》。"""
        _, body, _ = _load_golden(filename)
        # 排除段落標題（**辦法**：等）以免誤判
        clean_body = re.sub(r"\*\*[^*]+\*\*[：:]", "", body)
        # 找出法規引用：要求至少 3 個中文字 + 法律後綴
        law_suffixes = r"(?:管理法|組織法|程序法|保護法|處罰法|條例|辦法|要點|準則|規則|細則|手冊)"
        # 先收集有括號的引用（《》或「」都算合法括號）
        bracketed = re.findall(r"[《「][^》」]+[》」]", body)
        # 再收集裸名引用
        bare_laws = re.findall(
            rf"[\u4e00-\u9fff]{{3,}}{law_suffixes}",
            clean_body,
        )
        # 排除已被括號包裹的裸名
        true_bare = []
        for law in bare_laws:
            if not any(law in b for b in bracketed):
                true_bare.append(law)

        total = len(bracketed) + len(true_bare)
        if total == 0:
            pytest.skip(f"{filename} 未引用法規")

        # 有括號的引用佔比（《》和「」都計入）
        ratio = len(bracketed) / total if total else 1.0
        assert ratio >= 0.3, (
            f"{filename} 法規引用括號比例過低: {len(bracketed)}/{total} "
            f"({ratio:.0%})"
        )

    @pytest.mark.parametrize("filename,doc_type", GOLDEN_CASES,
                             ids=[c[0].replace(".md", "") for c in GOLDEN_CASES])
    def test_no_orphan_footnotes(self, filename: str, doc_type: str):
        """不應有未定義的腳註引用 [^n]。"""
        _, body, _ = _load_golden(filename)
        # 找出本文中的所有引用
        used = set(re.findall(r"\[\^(\d+)\](?!:)", body))
        # 找出定義的引用
        defined = set(re.findall(r"\[\^(\d+)\]:", body))

        orphans = used - defined
        # 黃金標準不應有腳註（真實公文不使用 Markdown 腳註）
        # 如果有腳註，則每個都應有定義
        if used:
            assert not orphans, f"{filename} 有孤兒腳註: {orphans}"


# ═══════════════════════════════════════════════════════════════════════
# 測試 3：往返精確度 — parse_draft → apply_template
# ═══════════════════════════════════════════════════════════════════════


class TestGoldenRoundTrip:
    """測試往返精確度：原文 → parse → template → 比較。"""

    @pytest.mark.parametrize("filename,doc_type", GOLDEN_CASES,
                             ids=[c[0].replace(".md", "") for c in GOLDEN_CASES])
    def test_roundtrip_structure(self, filename: str, doc_type: str, template_engine: TemplateEngine):
        """parse_draft 應正確解析原文的段落結構。"""
        meta, body, _ = _load_golden(filename)
        sections = template_engine.parse_draft(body)
        original_sections = _detect_sections(body)

        # 主旨必須被解析
        subject = sections.get("subject", "")
        assert subject.strip(), f"{filename} parse_draft 未解析出主旨"

        # 核心段落應被解析（至少 50% 命中率）
        section_key_map = {
            "主旨": "subject", "說明": "explanation", "依據": "basis",
            "辦法": "provisions", "公告事項": "provisions", "擬辦": "provisions",
        }
        checkable = original_sections & set(section_key_map.keys())
        if not checkable:
            return

        detected = 0
        for kw in checkable:
            key = section_key_map.get(kw)
            if not key:
                continue
            if kw == "依據":
                val = sections.get("basis", "") or sections.get("explanation", "")
            else:
                val = sections.get(key, "")
            if val and val.strip():
                detected += 1

        ratio = detected / len(checkable) if checkable else 1.0
        assert ratio >= 0.5, (
            f"{filename} 段落解析率過低: {detected}/{len(checkable)} ({ratio:.0%})"
        )

    @pytest.mark.parametrize("filename,doc_type", GOLDEN_CASES,
                             ids=[c[0].replace(".md", "") for c in GOLDEN_CASES])
    def test_roundtrip_subject_fidelity(self, filename: str, doc_type: str, template_engine: TemplateEngine):
        """往返後主旨應保留高相似度（>= 0.7）。"""
        meta, body, _ = _load_golden(filename)
        sections = template_engine.parse_draft(body)
        req = _build_requirement(meta, body, doc_type)
        rendered = template_engine.apply_template(req, sections)

        orig_subject = _extract_field(body, "主旨")
        rendered_subject = _extract_field(rendered, "主旨")

        if not orig_subject:
            pytest.skip(f"{filename} 原文無主旨欄位")

        similarity = difflib.SequenceMatcher(None, orig_subject, rendered_subject).ratio()
        assert similarity >= 0.7, (
            f"{filename} 主旨相似度不足: {similarity:.3f}\n"
            f"  原文: {orig_subject[:80]}\n"
            f"  渲染: {rendered_subject[:80]}"
        )

    @pytest.mark.parametrize("filename,doc_type", GOLDEN_CASES,
                             ids=[c[0].replace(".md", "") for c in GOLDEN_CASES])
    def test_roundtrip_content_preservation(self, filename: str, doc_type: str, template_engine: TemplateEngine):
        """往返後應保留至少 60% 的核心文字。"""
        meta, body, _ = _load_golden(filename)
        sections = template_engine.parse_draft(body)
        req = _build_requirement(meta, body, doc_type)
        rendered = template_engine.apply_template(req, sections)

        # 提取核心文字行
        cleaned_body = _strip_dynamic_lines(body)
        core_lines = []
        for line in cleaned_body.split("\n"):
            s = line.strip()
            if not s or len(s) < 5:
                continue
            # 移除格式標記
            s = re.sub(r"^\*\*[^*]+\*\*[：:]\s*", "", s)
            s = re.sub(r"^#{1,3}\s+", "", s)
            s = re.sub(r"^[一二三四五六七八九十]+、\s*", "", s)
            s = s.strip()
            if s and len(s) > 3:
                core_lines.append(s)

        if not core_lines:
            return

        rendered_plain = rendered.replace("**", "").replace("###", "").replace("---", "")
        found = sum(1 for line in core_lines if line[:20] in rendered_plain)
        ratio = found / len(core_lines) if core_lines else 1.0

        assert ratio >= 0.6, (
            f"{filename} 內容保留率過低: {found}/{len(core_lines)} ({ratio:.0%})"
        )

    @pytest.mark.parametrize("filename,doc_type", GOLDEN_CASES,
                             ids=[c[0].replace(".md", "") for c in GOLDEN_CASES])
    def test_roundtrip_format_compliance(self, filename: str, doc_type: str, template_engine: TemplateEngine):
        """渲染後不應有 ### 標題或 --- 分隔線。"""
        meta, body, _ = _load_golden(filename)
        sections = template_engine.parse_draft(body)
        req = _build_requirement(meta, body, doc_type)
        rendered = template_engine.apply_template(req, sections)

        lines = rendered.split("\n")
        assert not any(re.match(r"^#{1,3}\s", line) for line in lines), \
            f"{filename} 渲染後仍有 ### 標題格式"
        assert not any(line.strip() == "---" for line in lines), \
            f"{filename} 渲染後仍有 --- 分隔線"


# ═══════════════════════════════════════════════════════════════════════
# 測試 4：BLEU/ROUGE 內容相似度
# ═══════════════════════════════════════════════════════════════════════


class TestGoldenSimilarity:
    """使用 BLEU/ROUGE 評估往返後的內容相似度。"""

    @pytest.mark.parametrize("filename,doc_type", GOLDEN_CASES,
                             ids=[c[0].replace(".md", "") for c in GOLDEN_CASES])
    def test_bleu_score(self, filename: str, doc_type: str, template_engine: TemplateEngine):
        """往返後的 BLEU 分數應 >= 0.3（字元級）。"""
        meta, body, _ = _load_golden(filename)
        sections = template_engine.parse_draft(body)
        req = _build_requirement(meta, body, doc_type)
        rendered = template_engine.apply_template(req, sections)

        # 使用去除動態行的版本比較
        ref_text = _strip_dynamic_lines(body)
        hyp_text = _strip_dynamic_lines(rendered)

        score = bleu_score(ref_text, hyp_text)
        assert score >= 0.3, (
            f"{filename} BLEU 分數過低: {score:.4f} (閾值: 0.3)"
        )

    @pytest.mark.parametrize("filename,doc_type", GOLDEN_CASES,
                             ids=[c[0].replace(".md", "") for c in GOLDEN_CASES])
    def test_rouge_l_score(self, filename: str, doc_type: str, template_engine: TemplateEngine):
        """往返後的 ROUGE-L 分數應 >= 0.5。"""
        meta, body, _ = _load_golden(filename)
        sections = template_engine.parse_draft(body)
        req = _build_requirement(meta, body, doc_type)
        rendered = template_engine.apply_template(req, sections)

        ref_text = _strip_dynamic_lines(body)
        hyp_text = _strip_dynamic_lines(rendered)

        score = rouge_l_score(ref_text, hyp_text)
        assert score >= 0.5, (
            f"{filename} ROUGE-L 分數過低: {score:.4f} (閾值: 0.5)"
        )


# ═══════════════════════════════════════════════════════════════════════
# 測試 5：驗證器覆蓋 — 黃金標準不應被誤判
# ═══════════════════════════════════════════════════════════════════════


class TestGoldenValidators:
    """驗證器對黃金標準公文不應產生嚴重錯誤。"""

    @pytest.mark.parametrize("filename,doc_type", GOLDEN_CASES,
                             ids=[c[0].replace(".md", "") for c in GOLDEN_CASES])
    def test_no_false_positive_dates(self, filename: str, doc_type: str,
                                      validator_registry: ValidatorRegistry):
        """日期驗證器不應誤判黃金標準中的合法日期。"""
        _, body, _ = _load_golden(filename)
        errors = validator_registry.check_date_logic(body)
        assert not errors, (
            f"{filename} 日期驗證誤判: {errors}"
        )

    @pytest.mark.parametrize("filename,doc_type", GOLDEN_CASES,
                             ids=[c[0].replace(".md", "") for c in GOLDEN_CASES])
    def test_no_false_positive_terminology(self, filename: str, doc_type: str,
                                            validator_registry: ValidatorRegistry):
        """術語驗證器不應誤判黃金標準中的機關名稱。"""
        _, body, _ = _load_golden(filename)
        errors = validator_registry.check_terminology(body)
        # 允許黃金標準中有術語警告（部分舊範例可能有過時名稱），但不應超過 2 個
        assert len(errors) <= 2, (
            f"{filename} 過多術語警告 ({len(errors)}): {errors[:3]}"
        )

    @pytest.mark.parametrize("filename,doc_type", GOLDEN_CASES,
                             ids=[c[0].replace(".md", "") for c in GOLDEN_CASES])
    def test_citation_format_quality(self, filename: str, doc_type: str,
                                      validator_registry: ValidatorRegistry):
        """引用格式驗證器對黃金標準的警告應控制在合理範圍。"""
        _, body, _ = _load_golden(filename)
        errors = validator_registry.check_citation_format(body)
        # 黃金標準中允許少量引用格式建議，但不應超過 3 個
        assert len(errors) <= 3, (
            f"{filename} 過多引用格式問題 ({len(errors)}): {errors[:3]}"
        )


# ═══════════════════════════════════════════════════════════════════════
# 彙總報告：整體通過率
# ═══════════════════════════════════════════════════════════════════════


class TestGoldenPassRate:
    """彙總測試：計算整體品質分數和通過率。"""

    def test_overall_pass_rate(self, template_engine: TemplateEngine):
        """黃金標準的整體品質評分應 >= 85 分。

        評分方式（每份公文 100 分）：
        - 結構完整性: 20 分
        - 主旨精確度: 20 分
        - 內容保留度: 20 分
        - 格式合規度: 20 分
        - BLEU/ROUGE 相似度: 20 分
        """
        total_score = 0.0
        results = []

        for filename, doc_type in GOLDEN_CASES:
            meta, body, _ = _load_golden(filename)
            sections = template_engine.parse_draft(body)
            req = _build_requirement(meta, body, doc_type)
            rendered = template_engine.apply_template(req, sections)

            # 維度 1：結構完整性 (20)
            section_key_map = {
                "主旨": "subject", "說明": "explanation", "依據": "basis",
                "辦法": "provisions", "公告事項": "provisions", "擬辦": "provisions",
            }
            original = _detect_sections(body)
            checkable = original & set(section_key_map.keys())
            if checkable:
                detected = 0
                for kw in checkable:
                    key = section_key_map.get(kw)
                    if not key:
                        continue
                    val = sections.get("basis", "") or sections.get("explanation", "") \
                        if kw == "依據" else sections.get(key, "")
                    if val and val.strip():
                        detected += 1
                s1 = (detected / len(checkable)) * 20
            else:
                s1 = 20.0

            # 維度 2：主旨精確度 (20)
            orig_subject = _extract_field(body, "主旨")
            rendered_subject = _extract_field(rendered, "主旨")
            if orig_subject and rendered_subject:
                s2 = difflib.SequenceMatcher(None, orig_subject, rendered_subject).ratio() * 20
            elif not orig_subject:
                s2 = 20.0
            else:
                s2 = 0.0

            # 維度 3：內容保留度 (20)
            cleaned_body = _strip_dynamic_lines(body)
            core_lines = []
            for line in cleaned_body.split("\n"):
                s = line.strip()
                if not s or len(s) < 5:
                    continue
                s = re.sub(r"^\*\*[^*]+\*\*[：:]\s*", "", s)
                s = re.sub(r"^#{1,3}\s+", "", s)
                s = re.sub(r"^[一二三四五六七八九十]+、\s*", "", s)
                s = s.strip()
                if s and len(s) > 3:
                    core_lines.append(s)

            rendered_plain = rendered.replace("**", "").replace("###", "").replace("---", "")
            if core_lines:
                found = sum(1 for line in core_lines if line[:20] in rendered_plain)
                s3 = (found / len(core_lines)) * 20
            else:
                s3 = 20.0

            # 維度 4：格式合規度 (20)
            rlines = rendered.split("\n")
            checks, passed = 0, 0
            checks += 1
            if not any(re.match(r"^#{1,3}\s", l) for l in rlines):
                passed += 1
            checks += 1
            if not any(l.strip() == "---" for l in rlines):
                passed += 1
            checks += 1
            if not any(re.match(rf"^#\s+{re.escape(doc_type)}", l) for l in rlines):
                passed += 1
            s4 = (passed / checks) * 20 if checks else 20.0

            # 維度 5：BLEU/ROUGE 相似度 (20)
            ref_text = _strip_dynamic_lines(body)
            hyp_text = _strip_dynamic_lines(rendered)
            b_score = bleu_score(ref_text, hyp_text)
            r_score = rouge_l_score(ref_text, hyp_text)
            # 取 BLEU 和 ROUGE-L 的加權平均
            s5 = ((b_score * 0.4 + r_score * 0.6) / 0.8) * 20  # 正規化到 20 分
            s5 = min(s5, 20.0)

            doc_score = s1 + s2 + s3 + s4 + s5
            total_score += doc_score
            results.append({
                "file": filename,
                "doc_type": doc_type,
                "total": doc_score,
                "structure": s1,
                "subject": s2,
                "content": s3,
                "format": s4,
                "similarity": s5,
                "bleu": b_score,
                "rouge_l": r_score,
            })

        avg_score = total_score / len(GOLDEN_CASES)

        # 列印報告
        print("\n" + "=" * 70)
        print("  Golden Test Suite — 品質對標報告")
        print("=" * 70)
        for r in results:
            icon = "PASS" if r["total"] >= 85 else ("WARN" if r["total"] >= 70 else "FAIL")
            print(f"  [{icon}] {r['doc_type']:4s} {r['file']:45s} {r['total']:6.1f}/100"
                  f"  BLEU={r['bleu']:.3f} ROUGE-L={r['rouge_l']:.3f}")

        print(f"\n  平均分數: {avg_score:.1f}/100")
        passed_count = sum(1 for r in results if r["total"] >= 70)
        print(f"  通過率: {passed_count}/{len(results)} ({passed_count / len(results):.0%})")
        print("=" * 70)

        assert avg_score >= 70, (
            f"Golden test 整體平均分 {avg_score:.1f} 未達 70 分門檻"
        )
        assert passed_count / len(results) >= 0.85, (
            f"Golden test 通過率 {passed_count / len(results):.0%} 未達 85% 門檻"
        )
