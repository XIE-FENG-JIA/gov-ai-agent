#!/usr/bin/env python3
"""
公文品質評估腳本 — 用於 AutoResearch 迭代

Score: 0~100
五大維度（各 20 分）：
  1. 提示詞品質 (Prompt Quality)
  2. 產出格式品質 (Output Format Quality)
  3. 驗證器覆蓋 (Validator Coverage)
  4. 語言與模板品質 (Language & Template Quality)
  5. 進階品質防護 (Advanced Quality Guards)
"""
import inspect
import os
import re
import sys

# 確保專案根目錄在 sys.path 中
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from unittest.mock import MagicMock  # noqa: E402

from src.agents.writer import WriterAgent  # noqa: E402
from src.agents.validators import ValidatorRegistry  # noqa: E402
from src.agents.template import (  # noqa: E402
    TemplateEngine,
    clean_markdown_artifacts,
    renumber_provisions,
)
from src.core.models import PublicDocRequirement  # noqa: E402


# ─────────────────── 輔助工具 ───────────────────


def _pts(passed: bool, weight: float = 4.0) -> float:
    return weight if passed else 0.0


def _pts_ratio(passed: int, total: int, weight: float = 4.0) -> float:
    return weight * (passed / total) if total > 0 else 0.0


# ─────────────────── Mock 工廠 ───────────────────


def _make_mock_llm(response: str) -> MagicMock:
    llm = MagicMock()
    llm.generate.return_value = response
    llm.embed.return_value = [0.1] * 384
    return llm


def _make_mock_kb(results: list[dict] | None = None) -> MagicMock:
    kb = MagicMock()
    kb.is_available = True
    if results is None:
        results = []
    kb.search_hybrid.return_value = results
    return kb


GOOD_EVIDENCE = [
    {
        "id": "doc-1",
        "content": "公文程式條例第一條：本條例依中央法規標準法制定之。",
        "metadata": {
            "title": "公文程式條例",
            "source_level": "A",
            "source_url": "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=A0030055",
            "source": "全國法規資料庫",
            "content_hash": "a1b2c3d4e5f67890",
        },
        "distance": 0.1,
    },
    {
        "id": "doc-2",
        "content": "行政程序法相關規定。",
        "metadata": {
            "title": "行政程序法",
            "source_level": "A",
            "source_url": "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=A0030033",
            "source": "全國法規資料庫",
            "content_hash": "f0e1d2c3b4a59876",
        },
        "distance": 0.2,
    },
]

STANDARD_REQ = PublicDocRequirement(
    doc_type="函",
    urgency="普通",
    sender="臺北市政府環境保護局",
    receiver="臺北市各級學校",
    subject="關於加強資源回收分類一案",
    reason="為落實廢棄物清理法之規定",
    action_items=["加強分類", "定期宣導"],
    attachments=[],
)

GOOD_LLM_RESPONSE = (
    "### 主旨\n"
    "關於加強資源回收分類一案，請查照。\n\n"
    "### 說明\n"
    "一、依據《公文程式條例》辦理[^1]。\n"
    "二、為落實資源回收分類，提升環境品質，特函知。\n\n"
    "### 辦法\n"
    "一、請各校於校園內設置資源回收專區[^1][^2]。\n"
    "二、每月辦理宣導活動，加強師生環保意識。\n"
)


# ═══════════════ 維度 1：提示詞品質 (20 分) ═══════════════


def eval_prompt_quality() -> tuple[float, list[str]]:
    """檢查 WriterAgent 的 system prompt 是否包含必要指令。"""
    score = 0.0
    details: list[str] = []
    src = inspect.getsource(WriterAgent.write_draft)

    # 1. 格式規則覆蓋（8 種核心公文類型）
    core_types = ["函", "公告", "簽", "令", "開會通知單", "書函", "呈", "咨"]
    found = sum(1 for t in core_types if t in src)
    pts = _pts_ratio(found, len(core_types))
    score += pts
    details.append(f"格式規則覆蓋: {found}/{len(core_types)} 種核心公文 ({pts:.1f}/4)")

    # 2. 反虛構規則
    anti_halluc = ["fabricat", "hallucination", "待補依據"]
    found = sum(1 for m in anti_halluc if m.lower() in src.lower())
    pts = _pts_ratio(found, len(anti_halluc))
    score += pts
    details.append(f"反虛構規則: {found}/{len(anti_halluc)} ({pts:.1f}/4)")

    # 3. Level A/B 來源區分
    pts = _pts("Level A" in src and "Level B" in src)
    score += pts
    details.append(f"Level A/B 區分: {'有' if pts > 0 else '缺'} ({pts:.1f}/4)")

    # 4. 主旨長度或結構指引（prompt 是否指示主旨應簡潔）
    has_subject_guidance = any(k in src.lower() for k in [
        "concise", "簡潔", "brief", "short", "一句話", "50",
    ])
    pts = _pts(has_subject_guidance)
    score += pts
    details.append(f"主旨簡潔指引: {'有' if pts > 0 else '缺'} ({pts:.1f}/4)")

    # 5. 公文收尾語指引（查照/鑒核/轉陳 等結語）
    closing_phrases = ["查照", "鑒核", "轉陳", "核示", "照辦"]
    found = sum(1 for p in closing_phrases if p in src)
    pts = _pts(found >= 1)
    score += pts
    details.append(f"收尾語指引: {found}/{len(closing_phrases)} ({pts:.1f}/4)")

    return score, details


# ═══════════════ 維度 2：產出格式品質 (20 分) ═══════════════


def eval_output_quality() -> tuple[float, list[str]]:
    """用 mock LLM + KB 產生草稿，檢查輸出格式品質。"""
    score = 0.0
    details: list[str] = []

    # ── 場景 A：有 evidence ──
    mock_llm = _make_mock_llm(GOOD_LLM_RESPONSE)
    mock_kb = _make_mock_kb(GOOD_EVIDENCE)
    writer = WriterAgent(mock_llm, mock_kb)
    draft_a = writer.write_draft(STANDARD_REQ)

    # A1. 必要段落
    has_all = "主旨" in draft_a and "說明" in draft_a and "辦法" in draft_a
    pts = _pts(has_all)
    score += pts
    details.append(f"必要段落 (有 evidence): {'全有' if pts > 0 else '缺'} ({pts:.1f}/4)")

    # A2. 參考來源格式
    has_ref = "### 參考來源" in draft_a
    ref_ok = False
    if has_ref:
        ref_part = draft_a.split("### 參考來源")[1]
        ref_ok = bool(re.search(r"\[\^\d+\]:\s*\[Level [AB]\]", ref_part))
    pts = _pts(has_ref and ref_ok)
    score += pts
    details.append(f"參考來源格式: {'正確' if pts > 0 else '錯誤'} ({pts:.1f}/4)")

    # A3. Content hash
    has_hash = bool(re.search(r"Hash:\s*[a-f0-9]{8,}", draft_a))
    pts = _pts(has_hash)
    score += pts
    details.append(f"Content hash: {'有' if pts > 0 else '缺'} ({pts:.1f}/4)")

    # ── 場景 B：無 evidence ──
    mock_llm_b = _make_mock_llm(GOOD_LLM_RESPONSE)
    mock_kb_b = _make_mock_kb([])
    writer_b = WriterAgent(mock_llm_b, mock_kb_b)
    draft_b = writer_b.write_draft(STANDARD_REQ)

    # B1. 骨架模式警告
    pts = _pts("骨架模式" in draft_b)
    score += pts
    details.append(f"骨架模式警告: {'有' if pts > 0 else '缺'} ({pts:.1f}/4)")

    # B2. 無虛構引用
    body_b = draft_b.split("### 參考來源")[0] if "### 參考來源" in draft_b else draft_b
    no_fab = len(re.findall(r"\[\^\d+\]", body_b)) == 0 or "待補依據" in draft_b
    pts = _pts(no_fab)
    score += pts
    details.append(f"無虛構引用: {'通過' if pts > 0 else '失敗'} ({pts:.1f}/4)")

    return score, details


# ═══════════════ 維度 3：驗證器覆蓋 (20 分) ═══════════════


def eval_validator_coverage() -> tuple[float, list[str]]:
    """測試驗證器能否偵測各種品質問題。"""
    score = 0.0
    details: list[str] = []
    reg = ValidatorRegistry()

    # 1. 缺少參考來源
    errs = reg.check_evidence_presence("### 主旨\n測試。")
    pts = _pts(any("參考來源" in e for e in errs))
    score += pts
    details.append(f"偵測缺少參考來源: {'通過' if pts > 0 else '失敗'} ({pts:.1f}/4)")

    # 2. 孤兒引用
    errs = reg.check_citation_integrity(
        "辦理[^1][^3]。\n\n### 參考來源\n[^1]: [Level A] X\n"
    )
    pts = _pts(any("孤兒" in e for e in errs))
    score += pts
    details.append(f"偵測孤兒引用: {'通過' if pts > 0 else '失敗'} ({pts:.1f}/4)")

    # 3. 過時機關名稱
    pts = _pts(any("環境部" in e for e in reg.check_terminology("請環保署辦理。")))
    score += pts
    details.append(f"偵測過時機關名: {'通過' if pts > 0 else '失敗'} ({pts:.1f}/4)")

    # 4. 缺少書名號
    pts = _pts(any("書名號" in e for e in reg.check_citation_format("依據公文程式條例辦理。")))
    score += pts
    details.append(f"偵測缺少書名號: {'通過' if pts > 0 else '失敗'} ({pts:.1f}/4)")

    # 5. 口語化用詞偵測（check for colloquial language validator）
    colloquial_test = "幫我處理一下，這個超讚的，沒問題啦。"
    has_colloquial_validator = hasattr(reg, "check_colloquial_language")
    if has_colloquial_validator:
        errs = reg.check_colloquial_language(colloquial_test)
        pts = _pts(len(errs) > 0)
    else:
        pts = 0.0
    score += pts
    details.append(f"口語化偵測: {'通過' if pts > 0 else '缺少驗證器'} ({pts:.1f}/4)")

    return score, details


# ═══════════════ 維度 4：語言與模板品質 (20 分) ═══════════════


def eval_language_template_quality() -> tuple[float, list[str]]:
    """檢查模板覆蓋與語言品質邏輯。"""
    score = 0.0
    details: list[str] = []

    # 1. 模板覆蓋（12 種公文類型）
    engine = TemplateEngine()
    all_types = [
        "函", "書函", "呈", "咨", "公告", "簽", "令",
        "開會通知單", "會勘通知單", "公務電話紀錄", "手令", "箋函",
    ]
    mapped = 0
    sections = {"subject": "測試主旨", "explanation": "一、測試。", "provisions": "一、辦理。"}
    for dt in all_types:
        req = PublicDocRequirement(doc_type=dt, sender="X", receiver="Y", subject="Z")
        try:
            engine.apply_template(req, sections)
            mapped += 1
        except Exception:  # 預期：不支援的公文類型不計入覆蓋率
            pass
    pts = _pts_ratio(mapped, len(all_types))
    score += pts
    details.append(f"模板覆蓋: {mapped}/{len(all_types)} 種公文 ({pts:.1f}/4)")

    # 2. Markdown 清理
    dirty = "### **主旨**\n> `測試`\n---\n~~刪除~~"
    cleaned = clean_markdown_artifacts(dirty)
    pts = _pts("#" not in cleaned and "**" not in cleaned and "~~" not in cleaned)
    score += pts
    details.append(f"Markdown 清理: {'通過' if pts > 0 else '失敗'} ({pts:.1f}/4)")

    # 3. 中文編號排列
    messy = "1. 第一項\n2. 第二項\n3. 第三項"
    renumbered = renumber_provisions(messy)
    pts = _pts("一、" in renumbered and "二、" in renumbered)
    score += pts
    details.append(f"中文編號排列: {'通過' if pts > 0 else '失敗'} ({pts:.1f}/4)")

    # 4. 正式語氣引導
    src = inspect.getsource(WriterAgent.write_draft)
    formal = ["formal", "authoritative"]
    found = sum(1 for m in formal if m.lower() in src.lower())
    pts = _pts(found >= 2)
    score += pts
    details.append(f"正式語氣引導: {found}/{len(formal)} ({pts:.1f}/4)")

    # 5. 過時機關字典覆蓋度
    reg = ValidatorRegistry()
    count = len(reg._OUTDATED_AGENCY_MAP)
    pts = _pts(count >= 10)
    score += pts
    details.append(f"過時機關字典: {count} 筆 ({pts:.1f}/4)")

    return score, details


# ═══════════════ 維度 5：進階品質防護 (20 分) ═══════════════


def eval_advanced_guards() -> tuple[float, list[str]]:
    """檢查進階品質防護機制是否存在。"""
    score = 0.0
    details: list[str] = []
    src = inspect.getsource(WriterAgent.write_draft)
    reg = ValidatorRegistry()

    # 1. 敬語規範指引（prompt 提到敬語/台端/貴等用詞）
    honorific_markers = ["敬語", "台端", "貴機關", "honorific", "respectful"]
    found = sum(1 for m in honorific_markers if m in src)
    pts = _pts(found >= 1)
    score += pts
    details.append(f"敬語規範指引: {found}/{len(honorific_markers)} ({pts:.1f}/4)")

    # 2. 正本/副本結構指引
    cc_markers = ["正本", "副本", "cc", "copies"]
    found = sum(1 for m in cc_markers if m.lower() in src.lower())
    pts = _pts(found >= 1)
    score += pts
    details.append(f"正本副本指引: {found}/{len(cc_markers)} ({pts:.1f}/4)")

    # 3. 數字規範指引（公文數字用法：中文數字 vs 阿拉伯數字）
    number_markers = ["數字", "阿拉伯", "中文數字", "number format", "digit"]
    found = sum(1 for m in number_markers if m.lower() in src.lower())
    pts = _pts(found >= 1)
    score += pts
    details.append(f"數字規範指引: {found}/{len(number_markers)} ({pts:.1f}/4)")

    # 4. 句型長度限制或建議（prompt 提到句子長度或段落長度）
    length_markers = ["length", "長度", "字數", "character", "word count", "簡短"]
    found = sum(1 for m in length_markers if m.lower() in src.lower())
    pts = _pts(found >= 1)
    score += pts
    details.append(f"長度規範指引: {found}/{len(length_markers)} ({pts:.1f}/4)")

    # 5. 日期格式驗證器能偵測異常日期
    errs = reg.check_date_logic("民國 300 年 13 月 32 日辦理。")
    pts = _pts(len(errs) > 0)
    score += pts
    details.append(f"異常日期偵測: {'通過' if pts > 0 else '失敗'} ({pts:.1f}/4)")

    return score, details


# ═══════════════ 主程式 ═══════════════


def main() -> int:
    print("=" * 60)
    print("公文品質評估報告")
    print("=" * 60)

    total = 0.0
    all_details: list[tuple[str, float, list[str]]] = []

    evaluators = [
        ("提示詞品質", eval_prompt_quality),
        ("產出格式品質", eval_output_quality),
        ("驗證器覆蓋", eval_validator_coverage),
        ("語言與模板品質", eval_language_template_quality),
        ("進階品質防護", eval_advanced_guards),
    ]

    for name, func in evaluators:
        dim_score, dim_details = func()
        total += dim_score
        all_details.append((name, dim_score, dim_details))

    for name, dim_score, dim_details in all_details:
        print(f"\n── {name} ({dim_score:.1f}/20) ──")
        for d in dim_details:
            print(f"  {d}")

    print("\n" + "=" * 60)
    print(f"Score: {total:.1f}")
    print("=" * 60)

    return 0 if total >= 80 else 1


if __name__ == "__main__":
    sys.exit(main())
