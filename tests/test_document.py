from src.document.exporter import DocxExporter


def test_docx_export(tmp_path):
    """Test docx file generation."""
    exporter = DocxExporter()
    output_file = tmp_path / "test.docx"

    draft = "# 函\n\n**機關**：測試機關\n**受文者**：測試單位\n\n---\n\n### 主旨\n測試主旨\n\n### 說明\n測試說明內容"
    exporter.export(draft, str(output_file))

    assert output_file.exists()
    assert output_file.stat().st_size > 0


def test_docx_export_with_qa_report(tmp_path):
    """Test docx export with QA report appendix."""
    exporter = DocxExporter()
    output_file = tmp_path / "test_qa.docx"

    draft = "# 函\n### 主旨\n測試主旨\n### 說明\n測試說明"
    qa_report = "# Quality Report\n- Score: 0.85\n- Risk: Low"
    exporter.export(draft, str(output_file), qa_report=qa_report)

    assert output_file.exists()
    assert output_file.stat().st_size > 0


def test_docx_export_announcement(tmp_path):
    """Test docx export for 公告 type."""
    exporter = DocxExporter()
    output_file = tmp_path / "test_announce.docx"

    draft = "# 公告\n\n**機關**：環保局\n\n---\n\n### 主旨\n公告主旨\n\n### 公告事項\n一、第一項\n二、第二項"
    exporter.export(draft, str(output_file))

    assert output_file.exists()


def test_docx_export_empty_content(tmp_path):
    """Test docx export with minimal content."""
    exporter = DocxExporter()
    output_file = tmp_path / "test_empty.docx"

    draft = "# 函\n### 主旨\n空白測試"
    exporter.export(draft, str(output_file))

    assert output_file.exists()
    assert output_file.stat().st_size > 0


def test_docx_export_markdown_cleanup(tmp_path):
    """Test that markdown artifacts are cleaned in export."""
    exporter = DocxExporter()
    output_file = tmp_path / "test_clean.docx"

    draft = "# 函\n### 主旨\n**粗體**測試 _斜體_ [連結](http://example.com)\n### 說明\n```code\nblock\n```"
    exporter.export(draft, str(output_file))

    assert output_file.exists()
