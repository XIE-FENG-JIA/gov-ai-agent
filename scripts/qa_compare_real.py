"""
真實文本對照檢查：生成 DOCX → 提取文字 → 對照 kb_data 範例
"""
import os, sys, glob

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.template import TemplateEngine
from src.document.exporter import DocxExporter
from src.core.models import PublicDocRequirement
from docx import Document

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "qa_output")
KB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "kb_data", "examples")

# ── 使用 kb_data 範例作為草稿 ──
# 每種類型取第一個範例檔
TYPE_EXAMPLE_MAP = {
    "函": "han_01_*.md",
    "公告": "announcement_01_*.md",
    "簽": "sign_01_*.md",
    "書函": "letter_01_*.md",
    "令": "decree_01_*.md",
    "開會通知單": "meeting_01_*.md",
    "呈": "chen_01_*.md",
    "咨": "zi_01_*.md",
    "會勘通知單": "inspection_01_*.md",
    "公務電話紀錄": "phone_01_*.md",
    "手令": "directive_01_*.md",
    "箋函": "memo_01_*.md",
}

MOCK_REQUIREMENTS = {
    "函": PublicDocRequirement(doc_type="函", sender="臺北市政府環境保護局", receiver="臺北市各級學校", subject="加強資源回收", urgency="普通", action_items=[], attachments=[]),
    "公告": PublicDocRequirement(doc_type="公告", sender="內政部", receiver="（公告）", subject="修正建築法", urgency="普通", action_items=[], attachments=[]),
    "簽": PublicDocRequirement(doc_type="簽", sender="臺北市政府秘書處", receiver="（內部）", subject="在職訓練", urgency="速件", action_items=[], attachments=[]),
    "書函": PublicDocRequirement(doc_type="書函", sender="臺北市政府", receiver="某基金會", subject="資料函送", urgency="普通", action_items=[], attachments=[]),
    "令": PublicDocRequirement(doc_type="令", sender="行政院", receiver="（令）", subject="修正要點", urgency="普通", action_items=[], attachments=[]),
    "開會通知單": PublicDocRequirement(doc_type="開會通知單", sender="臺北市政府工務局", receiver="各局處", subject="協調會議", urgency="普通", action_items=[], attachments=[]),
    "呈": PublicDocRequirement(doc_type="呈", sender="行政院", receiver="總統府", subject="施政報告", urgency="速件", action_items=[], attachments=[]),
    "咨": PublicDocRequirement(doc_type="咨", sender="總統府", receiver="立法院", subject="法律案", urgency="普通", action_items=[], attachments=[]),
    "會勘通知單": PublicDocRequirement(doc_type="會勘通知單", sender="臺北市政府工務局", receiver="相關單位", subject="路面會勘", urgency="速件", action_items=[], attachments=[]),
    "公務電話紀錄": PublicDocRequirement(doc_type="公務電話紀錄", sender="臺北市政府秘書處", receiver="環保局", subject="協調事項", urgency="普通", action_items=[], attachments=[]),
    "手令": PublicDocRequirement(doc_type="手令", sender="臺北市市長", receiver="都發局局長", subject="社宅檢討", urgency="普通", action_items=[], attachments=[]),
    "箋函": PublicDocRequirement(doc_type="箋函", sender="臺北市政府秘書處", receiver="人事處", subject="設備報廢", urgency="普通", action_items=[], attachments=[]),
}


def find_example(pattern: str) -> str | None:
    matches = glob.glob(os.path.join(KB_DIR, pattern))
    if not matches:
        # 嘗試子目錄
        matches = glob.glob(os.path.join(KB_DIR, "**", pattern), recursive=True)
    return matches[0] if matches else None


def extract_docx_paragraphs(path: str) -> list[str]:
    doc = Document(path)
    return [p.text for p in doc.paragraphs]


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    engine = TemplateEngine()
    exporter = DocxExporter()

    all_issues = []

    for doc_type, pattern in TYPE_EXAMPLE_MAP.items():
        print(f"\n{'═' * 70}")
        print(f"  【{doc_type}】")
        print(f"{'═' * 70}")

        # 1. 讀取範例
        example_path = find_example(pattern)
        if not example_path:
            print(f"  ⚠ 找不到範例：{pattern}")
            continue

        with open(example_path, "r", encoding="utf-8") as f:
            example_text = f.read()

        print(f"  範例檔案：{os.path.basename(example_path)}")

        # 2. 顯示原始範例（前 30 行）
        example_lines = example_text.strip().split("\n")
        print(f"\n  ── 原始範例（{len(example_lines)} 行）──")
        for i, line in enumerate(example_lines[:35]):
            print(f"  原| {line}")
        if len(example_lines) > 35:
            print(f"  原| ... (共 {len(example_lines)} 行)")

        # 3. 走管線：parse → apply_template → export
        req = MOCK_REQUIREMENTS[doc_type]
        try:
            sections = engine.parse_draft(example_text)
            rendered = engine.apply_template(req, sections)
            out_path = os.path.join(OUTPUT_DIR, f"{doc_type}.docx")
            exporter.export(rendered, out_path)
        except Exception as e:
            print(f"  ✗ 管線失敗：{e}")
            all_issues.append((doc_type, f"管線失敗: {e}"))
            continue

        # 4. 提取 DOCX 文字
        paras = extract_docx_paragraphs(out_path)
        print(f"\n  ── DOCX 輸出（{len(paras)} 段）──")
        for i, p in enumerate(paras):
            if p.strip():
                print(f"  出| {p}")

        # 5. 對照檢查
        print(f"\n  ── 格式對照檢查 ──")
        issues = []

        # 5a. 標題是否正確
        non_empty = [p for p in paras if p.strip()]
        if non_empty and non_empty[0].strip() == doc_type:
            print(f"  ✓ 標題正確：「{doc_type}」")
        else:
            msg = f"標題錯誤：期望「{doc_type}」，得到「{non_empty[0] if non_empty else '空'}」"
            print(f"  ✗ {msg}")
            issues.append(msg)

        full_text = "\n".join(paras)

        # 5b. 檢查關鍵段落在原始範例中出現但 DOCX 缺失的
        SECTION_KEYWORDS = {
            "函": ["主旨", "說明", "辦法"],
            "公告": ["主旨", "依據", "公告事項"],
            "簽": ["主旨", "說明", "擬辦"],
            "書函": ["主旨", "說明"],
            "令": ["主旨"],
            "開會通知單": ["主旨", "開會時間", "開會地點", "議程"],
            "呈": ["主旨", "說明"],
            "咨": ["主旨", "說明"],
            "會勘通知單": ["主旨", "會勘時間", "會勘地點", "會勘事項"],
            "公務電話紀錄": ["通話時間", "發話人", "受話人", "主旨", "通話摘要"],
            "手令": ["主旨", "指示事項"],
            "箋函": ["主旨", "說明"],
        }

        for kw in SECTION_KEYWORDS.get(doc_type, []):
            in_example = kw in example_text
            in_docx = kw in full_text
            if in_example and in_docx:
                print(f"  ✓ 「{kw}」：範例有 → DOCX 有")
            elif in_example and not in_docx:
                msg = f"「{kw}」：範例有 → DOCX 缺失！"
                print(f"  ✗ {msg}")
                issues.append(msg)
            elif not in_example and in_docx:
                print(f"  ~ 「{kw}」：範例無 → DOCX 有（可能自動補充）")

        # 5c. 特殊欄位對照
        EXTRA_CHECKS = {
            "公告": {"不應有": ["受文者"]},
            "簽": {"不應有": ["受文者", "發文字號"]},
            "令": {"不應有": ["受文者"]},
            "公務電話紀錄": {"應有": ["紀錄人", "核閱"]},
            "手令": {"應有": ["完成期限", "副知"]},
            "箋函": {"應有": ["正本", "副本"]},
            "會勘通知單": {"應有": ["應攜文件", "應出席單位"]},
            "呈": {"應有敬詞": ["鑒核", "鈞", "敬請"]},
        }

        checks = EXTRA_CHECKS.get(doc_type, {})
        for kw in checks.get("不應有", []):
            # 檢查是否在 body 區域（不包括標題前2段）
            body_text = "\n".join(paras[2:])
            if kw in body_text:
                msg = f"不應出現「{kw}」但 DOCX 中有"
                print(f"  ⚠ {msg}")
                issues.append(msg)
            else:
                print(f"  ✓ 正確不含「{kw}」")

        for kw in checks.get("應有", []):
            if kw in full_text:
                print(f"  ✓ 含「{kw}」")
            else:
                in_ex = kw in example_text
                if in_ex:
                    msg = f"範例有「{kw}」但 DOCX 缺失"
                    print(f"  ✗ {msg}")
                    issues.append(msg)
                else:
                    print(f"  ~ 範例和 DOCX 都無「{kw}」（可能此範例不含）")

        for kw in checks.get("應有敬詞", []):
            if kw in full_text:
                print(f"  ✓ 含敬詞「{kw}」")
                break
        else:
            if checks.get("應有敬詞"):
                msg = "呈文缺少敬詞（鑒核/鈞/敬請）"
                print(f"  ⚠ {msg}")
                issues.append(msg)

        # 5d. Markdown 殘留
        for marker in ["**", "###", "---", "```"]:
            if marker in full_text:
                msg = f"DOCX 殘留 Markdown「{marker}」"
                print(f"  ✗ {msg}")
                issues.append(msg)

        # 5e. 主旨內容是否保留（核心內容不能丟失）
        # 從範例中提取主旨的第一句
        for line in example_lines:
            stripped = line.strip().replace("#", "").strip()
            if stripped.startswith("主旨") and ("：" in stripped or ":" in stripped):
                subject_content = stripped.split("：", 1)[-1].split(":", 1)[-1].strip()[:20]
                if subject_content and subject_content in full_text:
                    print(f"  ✓ 主旨內容保留：「{subject_content}...」")
                elif subject_content:
                    msg = f"主旨內容可能遺失：「{subject_content}...」"
                    print(f"  ⚠ {msg}")
                    issues.append(msg)
                break

        if issues:
            all_issues.append((doc_type, issues))
            print(f"\n  評等：{'C（需修改）' if len(issues) > 2 else 'B（小瑕疵）'}")
        else:
            print(f"\n  評等：A（與範例格式一致）")

    # ── 總結 ──
    print(f"\n{'═' * 70}")
    print(f"  總結")
    print(f"{'═' * 70}")

    if not all_issues:
        print("  12 種公文全部與範例格式一致，可以交給長官 ✅")
    else:
        print(f"  有 {len(all_issues)} 種公文存在差異：")
        for doc_type, issues in all_issues:
            if isinstance(issues, str):
                print(f"    {doc_type}: {issues}")
            else:
                for iss in issues:
                    print(f"    {doc_type}: {iss}")

    print(f"\n  DOCX 已存放在：{OUTPUT_DIR}")


if __name__ == "__main__":
    main()
