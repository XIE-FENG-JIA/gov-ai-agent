"""
12 種公文類型端對端品質檢查腳本

模擬真實草稿 → parse_draft → apply_template → DocxExporter.export
逐一檢查：欄位完整性、格式正確性、內容是否會被長官退件
"""
import os
import sys
import tempfile
import traceback
from dataclasses import dataclass, field

# 加入專案根目錄
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.template import TemplateEngine
from src.document.exporter import DocxExporter
from src.core.models import PublicDocRequirement
from docx import Document


# ── 12 種公文的擬真草稿 ──────────────────────────────────

MOCK_DRAFTS = {
    "函": """# 函

**機關**：臺北市政府環境保護局
**受文者**：臺北市各級學校
**速別**：普通
**發文日期**：中華民國 115 年 3 月 7 日
**發文字號**：北市環廢字第 11530012340 號

---

### 主旨
為加強本市各級學校資源回收分類工作，請配合辦理，請查照。

### 說明
一、依據行政院環境保護署 115 年 2 月 20 日環署廢字第 1150012345 號函辦理。
二、為落實本市垃圾減量及資源回收政策，各校應於 115 年 4 月 1 日前完成回收設施檢視及更新。
三、各校應指定專責人員負責資源回收分類督導工作，並於每月 5 日前填報回收成果。

### 辦法
一、請各校依「臺北市機關學校資源回收分類實施要點」辦理。
二、本局將於 115 年 5 月起進行實地訪查，未符合規定者將列入改善追蹤。
三、相關表單及填報系統操作說明，請至本局網站下載。

---
附件：臺北市機關學校資源回收分類實施要點 1 份
""",

    "公告": """# 公告

**機關**：內政部
**發文日期**：中華民國 115 年 3 月 1 日
**發文字號**：台內營字第 11508012340 號

---

### 主旨
修正「建築技術規則建築設計施工編」部分條文，自即日生效。

### 依據
建築法第九十七條。

### 公告事項
一、修正「建築技術規則建築設計施工編」第一百六十二條、第一百六十三條。
二、修正重點如下：
（一）增訂建築物無障礙設施設置基準。
（二）修正停車空間計算標準。
（三）調整綠建築設計規範相關條文。
三、本修正自發布日施行。

---
附件：修正條文對照表 1 份
""",

    "簽": """# 簽

**機關**：臺北市政府秘書處
**日期**：中華民國 115 年 3 月 5 日
**速別**：速件

---

### 主旨
擬請同意本處 115 年度第 2 季員工在職訓練計畫，陳請核示。

### 說明
一、本處為提升同仁公文寫作及數位應用能力，擬於 115 年 4 月至 6 月辦理在職訓練。
二、訓練課程規劃如下：
（一）公文寫作精進班：4 月 15 日、22 日，共 2 梯次。
（二）AI 數位工具應用班：5 月 10 日、17 日，共 2 梯次。
（三）法制作業研習班：6 月 12 日，共 1 梯次。
三、所需經費新臺幣 15 萬元整，由本處 115 年度教育訓練預算項下支應。

### 擬辦
一、擬請核准本處 115 年度第 2 季在職訓練計畫。
二、核准後由本處人事室統籌辦理報名及行政事宜。

---
附件：115 年度第 2 季在職訓練計畫書 1 份
""",

    "書函": """# 書函

**機關**：臺北市政府都市發展局
**受文者**：財團法人臺北市都市更新推動中心
**速別**：普通
**發文日期**：中華民國 115 年 3 月 6 日
**發文字號**：北市都更字第 11530098760 號

---

### 主旨
檢送本局 115 年度都市更新案件進度彙整表，請查照。

### 說明
一、依據本局 114 年 12 月 25 日第 4 季都市更新推動會議決議辦理。
二、截至 115 年 2 月底，本市都市更新案件共計 52 件進行中，其中 15 件已進入實施階段。
三、請貴中心協助追蹤各案進度，並於每月 10 日前回報異常案件。

---
附件：115 年度都市更新案件進度彙整表 1 份
""",

    "令": """# 令

**機關**：行政院
**發文日期**：中華民國 115 年 3 月 1 日
**發文字號**：院臺人字第 11500123450 號

---

### 主旨
茲修正「行政院及所屬各機關公務人員出國報告綜合處理要點」，自即日生效。

### 依據
公務人員訓練進修法第十七條。

### 辦法
一、第三點修正為：「各機關公務人員因公出國回國後，應於一個月內繳交出國報告。」
二、第五點修正為：「出國報告應包含任務執行情形、心得與建議事項。」
三、本令自發布日施行。

---
附件：修正對照表 1 份
""",

    "開會通知單": """# 開會通知單

**機關**：臺北市政府工務局
**受文者**：臺北市政府各局處
**發文日期**：中華民國 115 年 3 月 5 日
**發文字號**：北市工新字第 11530045670 號

---

### 主旨
召開「115 年度市區道路養護工程第 1 次協調會議」，請派員出席。

### 說明
一、為協調本年度市區道路養護工程施工期程，避免重複開挖，特召開本次會議。
二、請各局處就轄管管線工程需求提出年度施工計畫。

### 開會時間
中華民國 115 年 3 月 20 日（星期四）上午 10 時

### 開會地點
臺北市政府市政大樓 9 樓 901 會議室

### 議程
一、114 年度道路養護工程執行成果報告。
二、115 年度各局處管線工程需求彙整。
三、施工期程協調及路權管理事宜。
四、臨時動議。

---
附件：出席人員回條 1 份
""",

    "呈": """# 呈

**機關**：行政院
**受文者**：總統府
**速別**：速件
**發文日期**：中華民國 115 年 3 月 1 日
**發文字號**：院臺經字第 11500567890 號

---

### 主旨
檢呈「115 年度國家經濟發展策略報告」，敬請鑒核。

### 說明
一、依據總統府 114 年 12 月 20 日華總一義字第 11400123456 號函示辦理。
二、本報告彙整國內外經濟情勢分析、重點產業發展現況及未來政策規劃方向。
三、重點摘要如下：
（一）115 年經濟成長率預估為 3.2%。
（二）半導體及 AI 產業持續為成長主力。
（三）綠能轉型投資將達新臺幣 2,000 億元。
四、敬請鈞府鑒核後，俾據以推動相關施政。

---
附件：115 年度國家經濟發展策略報告全文 1 份
""",

    "咨": """# 咨

**機關**：總統府
**受文者**：立法院
**速別**：普通
**發文日期**：中華民國 115 年 2 月 28 日
**發文字號**：華總一義字第 11500234560 號

---

### 主旨
茲咨請貴院審議「國土計畫法修正草案」，請查照審議。

### 說明
一、為因應氣候變遷及國土永續發展需要，行政院擬具「國土計畫法修正草案」。
二、修正重點如下：
（一）強化海岸地區管理機制。
（二）增訂氣候變遷調適專章。
（三）修正國土保育地區使用管制規定。
三、檢附修正草案及總說明各 1 份，咨請貴院審議。

---
附件：
- 國土計畫法修正草案 1 份
- 修正草案總說明 1 份
""",

    "會勘通知單": """# 會勘通知單

**機關**：臺北市政府工務局新建工程處
**受文者**：相關單位
**速別**：速件
**發文日期**：中華民國 115 年 3 月 6 日
**發文字號**：北市工新字第 11530067890 號

---

### 主旨
辦理信義區松仁路 200 號前路面坍塌案現場會勘，請派員出席。

### 說明
一、本處接獲民眾陳情，信義區松仁路 200 號前路面出現坍塌現象。
二、為釐清坍塌原因及研擬修復方案，需請相關管線單位到場確認管線狀況。

### 會勘時間
中華民國 115 年 3 月 10 日（星期一）上午 9 時 30 分

### 會勘地點
臺北市信義區松仁路 200 號前

### 會勘事項
一、路面坍塌範圍及深度確認。
二、地下管線（自來水、瓦斯、電力、電信）現況檢視。
三、坍塌原因初步研判。
四、修復工法及期程研議。

### 應攜文件
各單位地下管線圖資、近期施工紀錄

### 應出席單位
臺北自來水事業處、大台北區瓦斯公司、台灣電力公司臺北市區營業處、中華電信臺北營運處

### 注意事項
一、請各單位派熟悉該區域管線之工程人員出席。
二、現場請著安全背心並攜帶安全帽。

---
附件：現場位置圖 1 份
""",

    "公務電話紀錄": """# 公務電話紀錄

**機關**：臺北市政府秘書處
**紀錄日期**：中華民國 115 年 3 月 5 日
**紀錄字號**：北市秘文字第 11530011220 號

---

### 通話時間
中華民國 115 年 3 月 5 日 上午 10 時 15 分至 10 時 30 分

### 發話人
行政院秘書處科長 張明德

### 受話人
臺北市政府秘書處科長 李淑芬

### 主旨
協調「115 年度全國行政效能提升方案」臺北市配合事項。

### 通話摘要
一、行政院預定 115 年 4 月推動全國行政效能提升方案。
二、請臺北市政府於 3 月 20 日前提報市府執行計畫。
三、行政院將於 3 月底召開全國視訊會議說明方案細節。

### 說明
一、本方案涉及各局處業務流程精簡及數位化推動。
二、已請各局處先行盤點可精簡之作業流程。

### 追蹤事項
一、3 月 15 日前彙整各局處回報內容。
二、3 月 20 日前提報市府執行計畫至行政院。
三、3 月底派員出席行政院全國視訊會議。

---

**紀錄人**：臺北市政府秘書處 科員 王小明
**核閱**：臺北市政府秘書處 科長 李淑芬
""",

    "手令": """# 手令

**發令人**：臺北市市長
**受令人**：都市發展局局長
**發令日期**：中華民國 115 年 3 月 1 日
**發令字號**：北市府令字第 11500034560 號

---

### 主旨
令都市發展局就本市社會住宅推動進度進行專案檢討，並提出改善方案。

### 指示事項
一、檢討本市社會住宅興建進度落後原因，提出具體改善對策。
二、盤點可加速推動之基地，研擬縮短工期方案。
三、評估引入民間投資興辦社會住宅之可行性。
四、提出 115 年度社會住宅推動修正計畫。

### 說明
一、本市社會住宅興建目標為 5 萬戶，截至 114 年底累計完工 1.8 萬戶，進度落後。
二、市議會已多次質詢要求加速推動。

### 完成期限
中華民國 115 年 3 月 31 日前

---

**副知**：臺北市政府秘書長、臺北市政府工務局局長
""",

    "箋函": """# 箋函

**發信人**：臺北市政府秘書處
**收信人**：臺北市政府人事處
**日期**：中華民國 115 年 3 月 6 日
**字號**：北市秘總字第 11530022330 號

---

### 主旨
有關本處會議室投影設備更新案，請貴處協助辦理財產報廢作業，請查照。

### 說明
一、本處 8 樓大會議室投影設備使用逾 8 年，已達財產使用年限且故障頻繁。
二、新設備已完成採購驗收，舊設備 2 台（財產編號：A-2017-001、A-2017-002）需辦理報廢。
三、請貴處依「臺北市政府財產管理作業要點」協助辦理報廢程序。

---

**正本**：臺北市政府人事處
**副本**：臺北市政府主計處
""",
}


MOCK_REQUIREMENTS = {
    "函": PublicDocRequirement(
        doc_type="函", sender="臺北市政府環境保護局", receiver="臺北市各級學校",
        subject="加強資源回收分類工作", urgency="普通", action_items=[], attachments=[]
    ),
    "公告": PublicDocRequirement(
        doc_type="公告", sender="內政部", receiver="（公告無特定受文者）",
        subject="修正建築技術規則", urgency="普通", action_items=[], attachments=[]
    ),
    "簽": PublicDocRequirement(
        doc_type="簽", sender="臺北市政府秘書處", receiver="（簽為內部文件）",
        subject="員工在職訓練計畫", urgency="速件", action_items=[], attachments=[]
    ),
    "書函": PublicDocRequirement(
        doc_type="書函", sender="臺北市政府都市發展局", receiver="財團法人臺北市都市更新推動中心",
        subject="都市更新案件進度彙整", urgency="普通", action_items=[], attachments=[]
    ),
    "令": PublicDocRequirement(
        doc_type="令", sender="行政院", receiver="（令無特定受文者）",
        subject="修正出國報告處理要點", urgency="普通", action_items=[], attachments=[]
    ),
    "開會通知單": PublicDocRequirement(
        doc_type="開會通知單", sender="臺北市政府工務局", receiver="臺北市政府各局處",
        subject="道路養護工程協調會議", urgency="普通", action_items=[], attachments=[]
    ),
    "呈": PublicDocRequirement(
        doc_type="呈", sender="行政院", receiver="總統府",
        subject="國家經濟發展策略報告", urgency="速件", action_items=[], attachments=[]
    ),
    "咨": PublicDocRequirement(
        doc_type="咨", sender="總統府", receiver="立法院",
        subject="國土計畫法修正草案", urgency="普通", action_items=[], attachments=[]
    ),
    "會勘通知單": PublicDocRequirement(
        doc_type="會勘通知單", sender="臺北市政府工務局新建工程處", receiver="相關單位",
        subject="路面坍塌會勘", urgency="速件", action_items=[], attachments=[]
    ),
    "公務電話紀錄": PublicDocRequirement(
        doc_type="公務電話紀錄", sender="臺北市政府秘書處", receiver="臺北市政府環境保護局",
        subject="全國行政效能提升方案", urgency="普通", action_items=[], attachments=[]
    ),
    "手令": PublicDocRequirement(
        doc_type="手令", sender="臺北市市長", receiver="都市發展局局長",
        subject="社會住宅推動檢討", urgency="普通", action_items=[], attachments=[]
    ),
    "箋函": PublicDocRequirement(
        doc_type="箋函", sender="臺北市政府秘書處", receiver="臺北市政府人事處",
        subject="投影設備報廢作業", urgency="普通", action_items=[], attachments=[]
    ),
}


# ── 品質檢查項目 ─────────────────────────────────────────

@dataclass
class CheckResult:
    passed: bool
    message: str
    severity: str = "error"  # error, warning, info


@dataclass
class DocTypeReport:
    doc_type: str
    checks: list[CheckResult] = field(default_factory=list)
    error_count: int = 0
    warning_count: int = 0
    fatal: str | None = None

    def add(self, check: CheckResult):
        self.checks.append(check)
        if not check.passed:
            if check.severity == "error":
                self.error_count += 1
            elif check.severity == "warning":
                self.warning_count += 1

    @property
    def grade(self) -> str:
        if self.fatal:
            return "F（完全失敗）"
        if self.error_count >= 3:
            return "D（會被退件）"
        if self.error_count >= 1:
            return "C（需要修改）"
        if self.warning_count >= 3:
            return "B-（勉強過關）"
        if self.warning_count >= 1:
            return "B+（小瑕疵）"
        return "A（可直接送出）"


# 各類型必備欄位
REQUIRED_FIELDS = {
    "函": {"主旨", "說明", "辦法"},
    "公告": {"主旨", "依據", "公告事項"},
    "簽": {"主旨", "說明", "擬辦"},
    "書函": {"主旨", "說明"},
    "令": {"主旨"},
    "開會通知單": {"主旨", "開會時間", "開會地點", "議程"},
    "呈": {"主旨", "說明"},
    "咨": {"主旨", "說明"},
    "會勘通知單": {"主旨", "會勘時間", "會勘地點", "會勘事項"},
    "公務電話紀錄": {"主旨", "通話時間", "發話人", "受話人", "通話摘要"},
    "手令": {"主旨", "指示事項"},
    "箋函": {"主旨", "說明"},
}

# 各類型不該出現的欄位（格式錯誤）
FORBIDDEN_FIELDS = {
    "公告": {"受文者", "速別"},
    "簽": {"受文者", "發文字號"},
    "令": {"受文者", "速別"},
}

# 各類型的 DOCX body_order label 對照
EXPECTED_BODY_LABELS = {
    "函": ["主旨：", "說明：", "辦法："],
    "公告": ["主旨：", "依據：", "公告事項："],
    "簽": ["主旨：", "說明：", "擬辦："],
    "書函": ["主旨：", "說明："],
    "令": ["主旨："],
    "開會通知單": ["主旨："],
    "呈": ["主旨：", "說明："],
    "咨": ["主旨：", "說明："],
    "會勘通知單": ["主旨：", "會勘時間：", "會勘地點：", "會勘事項："],
    "公務電話紀錄": ["通話時間：", "發話人：", "受話人：", "主旨：", "通話摘要："],
    "手令": ["主旨：", "指示事項："],
    "箋函": ["主旨：", "說明："],
}


def extract_docx_text(path: str) -> list[str]:
    """讀取 DOCX 全文（按段落）"""
    doc = Document(path)
    return [p.text.strip() for p in doc.paragraphs if p.text.strip()]


def check_one_type(doc_type: str, output_dir: str) -> DocTypeReport:
    report = DocTypeReport(doc_type=doc_type)
    draft = MOCK_DRAFTS[doc_type]
    req = MOCK_REQUIREMENTS[doc_type]

    # ── Step 1: parse_draft ──
    engine = TemplateEngine()
    try:
        sections = engine.parse_draft(draft)
    except Exception as e:
        report.fatal = f"parse_draft 失敗: {e}"
        return report

    # 檢查必備段落
    required = REQUIRED_FIELDS.get(doc_type, set())
    section_key_map = {
        "主旨": "subject", "說明": "explanation", "辦法": "provisions",
        "依據": "basis", "公告事項": "provisions", "擬辦": "provisions",
        "開會時間": "meeting_time", "開會地點": "meeting_location",
        "議程": "agenda",
        "會勘時間": "inspection_time", "會勘地點": "inspection_location",
        "會勘事項": "inspection_items",
        "通話時間": "call_time", "發話人": "caller", "受話人": "callee",
        "通話摘要": "call_summary",
        "指示事項": "directive_content",
    }

    for field_name in required:
        key = section_key_map.get(field_name, field_name)
        val = sections.get(key, "")
        if val and val.strip():
            report.add(CheckResult(True, f"✓ 段落「{field_name}」已正確解析"))
        else:
            report.add(CheckResult(False, f"✗ 缺少必備段落「{field_name}」（key={key}）", "error"))

    # ── Step 2: apply_template ──
    try:
        rendered = engine.apply_template(req, sections)
    except Exception as e:
        report.fatal = f"apply_template 失敗: {e}"
        return report

    # 檢查渲染結果不為空
    if not rendered or len(rendered.strip()) < 50:
        report.add(CheckResult(False, "✗ 模板渲染結果過短或為空", "error"))
    else:
        report.add(CheckResult(True, f"✓ 模板渲染成功（{len(rendered)} 字）"))

    # 檢查模板渲染是否遺留 Jinja2 變數
    if "{{" in rendered or "{%" in rendered:
        report.add(CheckResult(False, "✗ 渲染結果殘留未替換的 Jinja2 標籤", "error"))

    # 檢查不該出現的欄位
    forbidden = FORBIDDEN_FIELDS.get(doc_type, set())
    for f in forbidden:
        if f"**{f}**" in rendered or f"{f}：" in rendered:
            report.add(CheckResult(False, f"✗ 不應出現「{f}」（此類型無此欄位）", "warning"))

    # ── Step 3: DOCX export ──
    exporter = DocxExporter()
    out_path = os.path.join(output_dir, f"{doc_type}.docx")
    try:
        final_path = exporter.export(rendered, out_path)
    except Exception as e:
        report.fatal = f"DOCX 匯出失敗: {e}"
        return report

    if not os.path.exists(final_path):
        report.add(CheckResult(False, "✗ DOCX 檔案未產生", "error"))
        return report

    file_size = os.path.getsize(final_path)
    if file_size < 1000:
        report.add(CheckResult(False, f"✗ DOCX 檔案過小（{file_size} bytes），可能內容缺失", "warning"))
    else:
        report.add(CheckResult(True, f"✓ DOCX 匯出成功（{file_size:,} bytes）"))

    # ── Step 4: 讀取 DOCX 內容做深度檢查 ──
    try:
        paragraphs = extract_docx_text(final_path)
    except Exception as e:
        report.add(CheckResult(False, f"✗ DOCX 讀取失敗: {e}", "error"))
        return report

    full_text = "\n".join(paragraphs)

    # 4a. 標題檢查
    if paragraphs and paragraphs[0] == doc_type:
        report.add(CheckResult(True, f"✓ 文件標題正確：「{doc_type}」"))
    else:
        first = paragraphs[0] if paragraphs else "(空)"
        report.add(CheckResult(False, f"✗ 文件標題錯誤：期望「{doc_type}」，得到「{first}」", "error"))

    # 4b. 本文段落標籤檢查
    expected_labels = EXPECTED_BODY_LABELS.get(doc_type, [])
    for label in expected_labels:
        found = any(label in p for p in paragraphs)
        if found:
            report.add(CheckResult(True, f"✓ DOCX 含段落標籤「{label}」"))
        else:
            report.add(CheckResult(False, f"✗ DOCX 缺少段落標籤「{label}」", "error"))

    # 4c. 發文機關檢查
    sender = req.sender
    if sender in full_text:
        report.add(CheckResult(True, f"✓ DOCX 含發文機關「{sender}」"))
    else:
        report.add(CheckResult(False, f"✗ DOCX 未顯示發文機關「{sender}」", "warning"))

    # 4d. Markdown 殘留檢查
    md_markers = ["**", "###", "---", "```", "- ["]
    for marker in md_markers:
        if marker in full_text:
            report.add(CheckResult(False, f"✗ DOCX 殘留 Markdown 標記「{marker}」", "warning"))

    # 4e. 型別特有內容檢查
    if doc_type == "會勘通知單":
        for kw in ["會勘時間", "會勘地點", "會勘事項"]:
            if kw not in full_text:
                report.add(CheckResult(False, f"✗ 會勘通知單缺少「{kw}」內容", "error"))

    elif doc_type == "公務電話紀錄":
        for kw in ["通話時間", "發話人", "受話人", "通話摘要", "紀錄人", "核閱"]:
            if kw not in full_text:
                report.add(CheckResult(False, f"✗ 公務電話紀錄缺少「{kw}」", "error"))

    elif doc_type == "手令":
        for kw in ["指示事項", "完成期限", "副知"]:
            if kw not in full_text:
                report.add(CheckResult(False, f"✗ 手令缺少「{kw}」", "error"))

    elif doc_type == "箋函":
        for kw in ["正本", "副本"]:
            if kw not in full_text:
                report.add(CheckResult(False, f"✗ 箋函缺少「{kw}」", "warning"))

    elif doc_type == "呈":
        if "敬請鑒核" not in full_text and "鑒核" not in full_text and "鈞" not in full_text:
            report.add(CheckResult(False, "✗ 呈文語氣不夠恭敬（缺少敬詞）", "warning"))

    return report


def main():
    print("=" * 70)
    print("  12 種公文類型 端對端品質檢查")
    print("  模擬「長官審件」情境")
    print("=" * 70)

    with tempfile.TemporaryDirectory(prefix="qa_check_") as tmpdir:
        reports: list[DocTypeReport] = []

        for doc_type in MOCK_DRAFTS:
            print(f"\n{'─' * 50}")
            print(f"  檢查：{doc_type}")
            print(f"{'─' * 50}")

            try:
                report = check_one_type(doc_type, tmpdir)
            except Exception as e:
                report = DocTypeReport(doc_type=doc_type, fatal=f"未預期例外: {e}")
                traceback.print_exc()

            reports.append(report)

            if report.fatal:
                print(f"  !! 致命錯誤: {report.fatal}")
            else:
                for c in report.checks:
                    if not c.passed:
                        print(f"  {c.message}")

            print(f"  評等：{report.grade}")

        # ── 總結報告 ──
        print("\n" + "=" * 70)
        print("  總結報告")
        print("=" * 70)

        total_errors = 0
        total_warnings = 0
        total_fatal = 0

        for r in reports:
            icon = "💀" if r.fatal else ("❌" if r.error_count > 0 else ("⚠️" if r.warning_count > 0 else "✅"))
            status = f"E={r.error_count} W={r.warning_count}"
            if r.fatal:
                status = "FATAL"
                total_fatal += 1
            total_errors += r.error_count
            total_warnings += r.warning_count
            print(f"  {icon} {r.doc_type:10s}  {r.grade:20s}  ({status})")

        print(f"\n  致命: {total_fatal}  錯誤: {total_errors}  警告: {total_warnings}")

        if total_fatal > 0:
            print("\n  結論：有公文類型完全無法產出，長官一定會罵 😱")
        elif total_errors > 0:
            print("\n  結論：有些公文有格式缺漏，長官可能會退件要求修改 😰")
        elif total_warnings > 0:
            print("\n  結論：大致過關，有小瑕疵可改進 🤔")
        else:
            print("\n  結論：所有公文格式正確、內容完整，可以放心送出 ✅")

        # 列出所有產出的檔案
        print(f"\n  DOCX 產出目錄：{tmpdir}")
        for f in sorted(os.listdir(tmpdir)):
            fpath = os.path.join(tmpdir, f)
            print(f"    {f} ({os.path.getsize(fpath):,} bytes)")

        return total_fatal + total_errors


if __name__ == "__main__":
    exit_code = main()
    sys.exit(min(exit_code, 1))
