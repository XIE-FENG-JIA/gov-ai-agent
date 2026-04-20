import json
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch
from xml.etree import ElementTree as ET

from typer.testing import CliRunner

from src.document.exporter import (
    CUSTOM_PROPERTIES_NS,
    DOC_PROPS_VT_NS,
    DocxExporter,
)


runner = CliRunner()


def _read_custom_properties(path: Path) -> dict[str, str]:
    with zipfile.ZipFile(path, "r") as archive:
        custom_xml = archive.read("docProps/custom.xml")
    root = ET.fromstring(custom_xml)
    values: dict[str, str] = {}
    for prop in root.findall(f"{{{CUSTOM_PROPERTIES_NS}}}property"):
        name = prop.get("name", "")
        for child in list(prop):
            if child.tag in {
                f"{{{DOC_PROPS_VT_NS}}}lpwstr",
                f"{{{DOC_PROPS_VT_NS}}}i4",
                f"{{{DOC_PROPS_VT_NS}}}bool",
            }:
                values[name] = child.text or ""
                break
    return values


def test_docx_export_writes_citation_custom_properties(tmp_path):
    exporter = DocxExporter()
    output_file = tmp_path / "citation.docx"
    draft = """# 函

### 主旨
引用測試

### 說明
依據《公文程式條例》辦理[^1]。

### 參考來源 (AI 引用追蹤)
[^1]: [Level A] 公文程式條例 | URL: https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=A0030055 | Hash: a1b2c3d4e5f67890
"""

    exporter.export(
        draft,
        str(output_file),
        citation_metadata={
            "reviewed_sources": [
                {
                    "index": 1,
                    "title": "公文程式條例",
                    "source_level": "A",
                    "source_url": "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=A0030055",
                    "record_id": "A0030055",
                    "content_hash": "a1b2c3d4e5f67890",
                }
            ],
            "engine": "openrouter/elephant-alpha",
            "ai_generated": True,
        },
    )

    props = _read_custom_properties(output_file)
    assert json.loads(props["source_doc_ids"]) == ["A0030055"]
    assert props["citation_count"] == "1"
    assert props["ai_generated"] == "true"
    assert props["engine"] == "openrouter/elephant-alpha"
    sources = json.loads(props["citation_sources_json"])
    assert sources == [
        {
            "index": 1,
            "title": "公文程式條例",
            "source_level": "A",
            "source_url": "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=A0030055",
            "content_hash": "a1b2c3d4e5f67890",
            "source_doc_id": "A0030055",
        }
    ]


@patch("src.cli.generate.append_record")
@patch("src.cli.generate.detect_simplified", return_value=[])
@patch("src.cli.generate.DocxExporter")
@patch("src.cli.generate.TemplateEngine")
@patch("src.cli.generate.WriterAgent")
@patch("src.cli.generate.RequirementAgent")
@patch("src.cli.generate.KnowledgeBaseManager")
@patch("src.cli.generate.get_llm_factory")
@patch("src.cli.generate.ConfigManager")
def test_generate_passes_reviewed_citation_metadata_to_exporter(
    mock_cm,
    mock_factory,
    mock_kb,
    mock_req,
    mock_writer,
    mock_template,
    mock_exporter,
    _mock_simplified,
    _mock_history,
):
    from src.cli.main import app

    mock_cm.return_value.config = {
        "llm": {"provider": "mock"},
        "knowledge_base": {"path": "./test_kb"},
    }
    mock_req.return_value.analyze.return_value = MagicMock(
        doc_type="函",
        subject="測試主旨",
        sender="測試機關",
        receiver="測試單位",
        urgency="普通",
    )
    writer_instance = mock_writer.return_value
    writer_instance.write_draft.return_value = (
        "### 主旨\n測試\n\n### 說明\n依據測試辦理[^1]。\n\n"
        "### 參考來源 (AI 引用追蹤)\n"
        "[^1]: [Level A] 測試法規 | URL: https://example.test/law | Hash: abcdef1234567890"
    )
    writer_instance._last_sources_list = [
        {
            "index": 1,
            "title": "測試法規",
            "source_level": "A",
            "source_url": "https://example.test/law",
            "record_id": "law-1",
            "content_hash": "abcdef1234567890",
        }
    ]
    mock_template.return_value.parse_draft.return_value = {
        "subject": "測試",
        "explanation": "依據測試辦理[^1]。",
        "references": "[^1]: [Level A] 測試法規 | URL: https://example.test/law | Hash: abcdef1234567890",
    }
    mock_template.return_value.apply_template.return_value = writer_instance.write_draft.return_value
    llm_instance = MagicMock()
    llm_instance.provider = "openrouter"
    llm_instance.model_name = "openrouter/elephant-alpha"
    mock_factory.return_value = llm_instance
    mock_exporter.return_value.export.return_value = "output.docx"

    result = runner.invoke(app, ["generate", "--input", "寫一份正式公函", "--output", "test.docx", "--skip-review"])

    assert result.exit_code == 0
    _, kwargs = mock_exporter.return_value.export.call_args
    assert kwargs["citation_metadata"] == {
        "reviewed_sources": writer_instance._last_sources_list,
        "engine": "openrouter/elephant-alpha",
        "ai_generated": True,
    }
