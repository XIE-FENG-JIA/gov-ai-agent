"""
src/document/exporter.py 的延伸測試
補充匯出格式、邊界條件和特殊字元處理
"""
from docx import Document
from src.document.exporter import DocxExporter


# ==================== 文件類型偵測 ====================

class TestExtractDocType:
    """_extract_doc_type 方法的測試"""

    def test_detect_han(self):
        """測試偵測「函」類型"""
        exporter = DocxExporter()
        assert exporter._extract_doc_type("# 函\n內容") == "函"

    def test_detect_announcement(self):
        """測試偵測「公告」類型"""
        exporter = DocxExporter()
        assert exporter._extract_doc_type("# 公告\n內容") == "公告"

    def test_detect_sign(self):
        """測試偵測「簽」類型"""
        exporter = DocxExporter()
        assert exporter._extract_doc_type("# 簽\n內容") == "簽"

    def test_detect_order(self):
        """測試偵測「令」類型"""
        exporter = DocxExporter()
        assert exporter._extract_doc_type("# 令\n內容") == "令"

    def test_detect_meeting_notice(self):
        """測試偵測「開會通知單」類型"""
        exporter = DocxExporter()
        assert exporter._extract_doc_type("# 開會通知單\n內容") == "開會通知單"

    def test_default_type(self):
        """測試無法偵測時預設為「函」"""
        exporter = DocxExporter()
        assert exporter._extract_doc_type("隨便的文字\n沒有類型") == "函"

    def test_type_within_first_5_lines(self):
        """測試類型在前5行內被偵測"""
        exporter = DocxExporter()
        draft = "一些前綴\n\n\n公告\n內容"
        assert exporter._extract_doc_type(draft) == "公告"


# ==================== 清理行文字 ====================

class TestCleanLine:
    """_clean_line 方法的測試"""

    def test_remove_markdown_headers(self):
        """測試移除 markdown 標題符號"""
        exporter = DocxExporter()
        assert exporter._clean_line("### 主旨") == "主旨"

    def test_remove_bold_markers(self):
        """測試移除粗體標記"""
        exporter = DocxExporter()
        result = exporter._clean_line("**機關**：測試")
        assert "**" not in result
        assert "機關" in result

    def test_remove_list_markers(self):
        """測試移除列表標記"""
        exporter = DocxExporter()
        result = exporter._clean_line("- 項目一")
        assert result == "項目一"

    def test_empty_string(self):
        """測試空字串"""
        exporter = DocxExporter()
        assert exporter._clean_line("") == ""

    def test_preserve_chinese_content(self):
        """測試保留中文內容"""
        exporter = DocxExporter()
        assert "依據" in exporter._clean_line("依據某法規辦理")


# ==================== 簽類型匯出 ====================

class TestSignExport:
    """簽類型文件匯出的測試"""

    def test_sign_export(self, tmp_path):
        """測試簽類型的匯出"""
        exporter = DocxExporter()
        output_file = tmp_path / "test_sign.docx"

        draft = """# 簽

**機關**：市府

---

### 主旨
簽呈主旨

### 說明
簽呈說明

### 擬辦
建議方案
"""
        exporter.export(draft, str(output_file))
        assert output_file.exists()
        assert output_file.stat().st_size > 0

    def test_sign_with_reason(self, tmp_path):
        """測試簽類型包含依據"""
        exporter = DocxExporter()
        output_file = tmp_path / "test_sign_basis.docx"

        draft = """# 簽

### 主旨
簽呈測試

### 依據
某法規

### 說明
詳細說明
"""
        exporter.export(draft, str(output_file))
        assert output_file.exists()


# ==================== 特殊內容匯出 ====================

class TestSpecialContentExport:
    """特殊內容的匯出測試"""

    def test_export_with_citations(self, tmp_path):
        """測試含有引用標記的匯出"""
        exporter = DocxExporter()
        output_file = tmp_path / "test_citation.docx"

        draft = """# 函

### 主旨
引用測試

### 說明
依據某法辦理[^1]。

### 參考來源
[^1]: 某法規
"""
        exporter.export(draft, str(output_file))
        assert output_file.exists()

    def test_export_with_numbered_provisions(self, tmp_path):
        """測試含有編號辦法的匯出"""
        exporter = DocxExporter()
        output_file = tmp_path / "test_provisions.docx"

        draft = """# 函

### 主旨
辦法測試

### 辦法
一、第一項辦法
二、第二項辦法
（一）子項目
（二）另一子項目
"""
        exporter.export(draft, str(output_file))
        assert output_file.exists()

    def test_export_with_special_characters(self, tmp_path):
        """測試含有特殊字元的匯出"""
        exporter = DocxExporter()
        output_file = tmp_path / "test_special.docx"

        draft = """# 函

### 主旨
測試「全形引號」和《書名號》及（括號）

### 說明
金額：新臺幣1,000元整
百分比：50%
電話：(02)1234-5678
"""
        exporter.export(draft, str(output_file))
        assert output_file.exists()

    def test_export_with_long_content(self, tmp_path):
        """測試長內容的匯出"""
        exporter = DocxExporter()
        output_file = tmp_path / "test_long.docx"

        long_explanation = "\n".join([f"{i+1}、第{i+1}項說明內容，這是一段較長的文字。" for i in range(20)])
        draft = f"# 函\n\n### 主旨\n長內容測試\n\n### 說明\n{long_explanation}"
        exporter.export(draft, str(output_file))
        assert output_file.exists()
        assert output_file.stat().st_size > 1000  # 長內容應產生較大的檔案

    def test_export_only_subject(self, tmp_path):
        """測試只有主旨的最簡內容"""
        exporter = DocxExporter()
        output_file = tmp_path / "test_minimal.docx"

        draft = "# 函\n### 主旨\n最簡測試"
        exporter.export(draft, str(output_file))
        assert output_file.exists()

    def test_export_with_attachments(self, tmp_path):
        """測試包含附件段落的匯出"""
        exporter = DocxExporter()
        output_file = tmp_path / "test_attach.docx"

        draft = """# 函

### 主旨
附件測試

### 說明
請參閱附件。

### 附件
一、某報告一份
二、某表格一份
"""
        exporter.export(draft, str(output_file))
        assert output_file.exists()

    def test_export_returns_output_path(self, tmp_path):
        """測試 export 回傳輸出路徑"""
        exporter = DocxExporter()
        output_file = tmp_path / "test_return.docx"

        result = exporter.export("# 函\n### 主旨\n測試", str(output_file))
        assert result == str(output_file)


# ==================== DOCX 內容驗證 ====================

class TestDocxContentVerification:
    """驗證生成的 DOCX 文件內容"""

    def test_docx_has_title(self, tmp_path):
        """測試 DOCX 包含文件類型標題"""
        exporter = DocxExporter()
        output_file = tmp_path / "test_verify.docx"
        exporter.export("# 函\n### 主旨\n測試主旨", str(output_file))

        doc = Document(str(output_file))
        all_text = "\n".join([p.text for p in doc.paragraphs])
        assert "函" in all_text

    def test_docx_has_subject(self, tmp_path):
        """測試 DOCX 包含主旨內容"""
        exporter = DocxExporter()
        output_file = tmp_path / "test_subject.docx"
        exporter.export("# 函\n### 主旨\n驗證這個主旨", str(output_file))

        doc = Document(str(output_file))
        all_text = "\n".join([p.text for p in doc.paragraphs])
        assert "驗證這個主旨" in all_text

    def test_docx_qa_report_on_new_page(self, tmp_path):
        """測試 QA 報告在新頁面"""
        exporter = DocxExporter()
        output_file = tmp_path / "test_qa_page.docx"
        exporter.export(
            "# 函\n### 主旨\n測試",
            str(output_file),
            qa_report="# QA Report\nScore: 0.95"
        )

        doc = Document(str(output_file))
        all_text = "\n".join([p.text for p in doc.paragraphs])
        assert "品質保證報告" in all_text or "QA Report" in all_text
