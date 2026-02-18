"""
src/cli/ 的命令行介面測試
使用 typer.testing.CliRunner 來測試 CLI 命令
"""
import json
import yaml
import requests
from unittest.mock import MagicMock, patch
from typer.testing import CliRunner



runner = CliRunner()


# ==================== Main CLI ====================

class TestMainCLI:
    """主 CLI 入口的測試"""

    def test_version_flag(self):
        """測試 --version 旗標"""
        from src.cli.main import app
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "版本" in result.stdout

    def test_no_args_shows_help(self):
        """測試無參數時顯示說明（no_args_is_help=True 導致 exit_code=2 但仍輸出幫助文字）"""
        from src.cli.main import app
        result = runner.invoke(app, [])
        # typer 的 no_args_is_help=True 會以 exit_code=2 退出
        assert result.exit_code in (0, 2)
        assert "Usage" in result.stdout or "help" in result.stdout.lower() or "generate" in result.stdout

    def test_help_flag(self):
        """測試 --help 旗標"""
        from src.cli.main import app
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "generate" in result.stdout
        assert "kb" in result.stdout


# ==================== Generate Command ====================

class TestGenerateCommand:
    """generate 命令的測試"""

    @patch("src.cli.generate.DocxExporter")
    @patch("src.cli.generate.TemplateEngine")
    @patch("src.cli.generate.WriterAgent")
    @patch("src.cli.generate.RequirementAgent")
    @patch("src.cli.generate.KnowledgeBaseManager")
    @patch("src.cli.generate.get_llm_factory")
    @patch("src.cli.generate.ConfigManager")
    def test_generate_skip_review(
        self, mock_cm, mock_factory, mock_kb, mock_req, mock_writer,
        mock_template, mock_exporter
    ):
        """測試跳過審查的文件產生"""
        from src.cli.main import app

        # 設定 mock
        mock_cm.return_value.config = {
            "llm": {"provider": "mock"},
            "knowledge_base": {"path": "./test_kb"}
        }

        mock_req_instance = mock_req.return_value
        mock_req_instance.analyze.return_value = MagicMock(
            doc_type="函", subject="測試"
        )

        mock_writer_instance = mock_writer.return_value
        mock_writer_instance.write_draft.return_value = "### 主旨\n測試"

        mock_template_instance = mock_template.return_value
        mock_template_instance.parse_draft.return_value = {"subject": "測試"}
        mock_template_instance.apply_template.return_value = "格式化後的草稿"

        mock_exporter_instance = mock_exporter.return_value
        mock_exporter_instance.export.return_value = "output.docx"

        result = runner.invoke(app, [
            "generate", "--input", "寫一份函", "--output", "test.docx", "--skip-review"
        ])
        assert result.exit_code == 0
        assert "完成" in result.stdout

    @patch("src.cli.generate.RequirementAgent")
    @patch("src.cli.generate.KnowledgeBaseManager")
    @patch("src.cli.generate.get_llm_factory")
    @patch("src.cli.generate.ConfigManager")
    def test_generate_analysis_failure(
        self, mock_cm, mock_factory, mock_kb, mock_req
    ):
        """測試需求分析失敗時的處理"""
        from src.cli.main import app

        mock_cm.return_value.config = {
            "llm": {"provider": "mock"},
            "knowledge_base": {"path": "./test_kb"}
        }

        mock_req_instance = mock_req.return_value
        mock_req_instance.analyze.side_effect = ValueError("Parse error")

        result = runner.invoke(app, [
            "generate", "--input", "invalid"
        ])
        assert result.exit_code == 1

    @patch("src.cli.generate.DocxExporter")
    @patch("src.cli.generate.EditorInChief")
    @patch("src.cli.generate.TemplateEngine")
    @patch("src.cli.generate.WriterAgent")
    @patch("src.cli.generate.RequirementAgent")
    @patch("src.cli.generate.KnowledgeBaseManager")
    @patch("src.cli.generate.get_llm_factory")
    @patch("src.cli.generate.ConfigManager")
    def test_generate_with_review(
        self, mock_cm, mock_factory, mock_kb, mock_req, mock_writer,
        mock_template, mock_editor, mock_exporter
    ):
        """測試含審查的完整生成流程"""
        from src.cli.main import app

        mock_cm.return_value.config = {
            "llm": {"provider": "mock"},
            "knowledge_base": {"path": "./test_kb"}
        }

        mock_req_instance = mock_req.return_value
        mock_req_instance.analyze.return_value = MagicMock(
            doc_type="函", subject="測試"
        )

        mock_writer_instance = mock_writer.return_value
        mock_writer_instance.write_draft.return_value = "### 主旨\n測試"

        mock_template_instance = mock_template.return_value
        mock_template_instance.parse_draft.return_value = {"subject": "測試"}
        mock_template_instance.apply_template.return_value = "格式化後的草稿"

        mock_qa_report = MagicMock()
        mock_qa_report.audit_log = "審查報告內容"
        mock_editor_instance = mock_editor.return_value
        mock_editor_instance.review_and_refine.return_value = ("修改後草稿", mock_qa_report)

        mock_exporter_instance = mock_exporter.return_value
        mock_exporter_instance.export.return_value = "output.docx"

        result = runner.invoke(app, [
            "generate", "--input", "寫一份函", "--output", "test.docx"
        ])
        assert result.exit_code == 0
        assert "完成" in result.stdout
        mock_editor_instance.review_and_refine.assert_called_once()

    @patch("src.cli.generate.DocxExporter")
    @patch("src.cli.generate.TemplateEngine")
    @patch("src.cli.generate.WriterAgent")
    @patch("src.cli.generate.RequirementAgent")
    @patch("src.cli.generate.KnowledgeBaseManager")
    @patch("src.cli.generate.get_llm_factory")
    @patch("src.cli.generate.ConfigManager")
    def test_generate_export_failure(
        self, mock_cm, mock_factory, mock_kb, mock_req, mock_writer,
        mock_template, mock_exporter
    ):
        """測試匯出失敗時的處理"""
        from src.cli.main import app

        mock_cm.return_value.config = {
            "llm": {"provider": "mock"},
            "knowledge_base": {"path": "./test_kb"}
        }

        mock_req_instance = mock_req.return_value
        mock_req_instance.analyze.return_value = MagicMock(
            doc_type="函", subject="測試"
        )

        mock_writer_instance = mock_writer.return_value
        mock_writer_instance.write_draft.return_value = "### 主旨\n測試"

        mock_template_instance = mock_template.return_value
        mock_template_instance.parse_draft.return_value = {"subject": "測試"}
        mock_template_instance.apply_template.return_value = "格式化後的草稿"

        mock_exporter_instance = mock_exporter.return_value
        mock_exporter_instance.export.side_effect = OSError("磁碟已滿")

        result = runner.invoke(app, [
            "generate", "--input", "寫一份函", "--output", "test.docx", "--skip-review"
        ])
        assert result.exit_code == 1
        assert "匯出失敗" in result.stdout


# ==================== Switch Command ====================

class TestSwitchCommand:
    """switch 命令的測試"""

    def test_switch_direct_provider(self, tmp_path):
        """測試直接指定提供者切換"""
        from src.cli.main import app

        # 建立測試配置檔案
        config_file = tmp_path / "config.yaml"
        config = {
            "llm": {"provider": "ollama", "model": "mistral", "api_key": "", "base_url": ""},
            "providers": {
                "ollama": {"model": "mistral"},
                "gemini": {"model": "gemini-1.5-flash"}
            }
        }
        config_file.write_text(yaml.dump(config), encoding="utf-8")

        with patch("src.cli.switcher.ConfigManager") as mock_cm:
            mock_cm.return_value.config_path = config_file
            mock_cm.return_value.config = config

            result = runner.invoke(app, ["switch", "--provider", "gemini"])
            assert result.exit_code == 0
            assert "gemini" in result.stdout

    def test_switch_invalid_provider(self, tmp_path):
        """測試切換到無效提供者"""
        from src.cli.main import app

        config_file = tmp_path / "config.yaml"
        config = {
            "llm": {"provider": "ollama"},
            "providers": {"ollama": {}, "gemini": {}}
        }
        config_file.write_text(yaml.dump(config), encoding="utf-8")

        with patch("src.cli.switcher.ConfigManager") as mock_cm:
            mock_cm.return_value.config_path = config_file
            mock_cm.return_value.config = config

            result = runner.invoke(app, ["switch", "--provider", "nonexistent"])
            assert result.exit_code == 1

    def test_switch_config_load_error(self, tmp_path):
        """測試設定檔載入失敗"""
        from src.cli.main import app

        with patch("src.cli.switcher.ConfigManager") as mock_cm:
            mock_cm.return_value.config_path = tmp_path / "nonexistent.yaml"

            result = runner.invoke(app, ["switch", "--provider", "gemini"])
            assert result.exit_code == 1
            assert "錯誤" in result.stdout

    def test_switch_adds_ollama_if_missing(self, tmp_path):
        """測試 providers 列表中沒有 ollama 時自動加入"""
        from src.cli.main import app

        config_file = tmp_path / "config.yaml"
        config = {
            "llm": {"provider": "gemini"},
            "providers": {"gemini": {"model": "gemini-flash"}}
        }
        config_file.write_text(yaml.dump(config), encoding="utf-8")

        with patch("src.cli.switcher.ConfigManager") as mock_cm:
            mock_cm.return_value.config_path = config_file
            mock_cm.return_value.config = config

            result = runner.invoke(app, ["switch", "--provider", "ollama"])
            assert result.exit_code == 0
            assert "ollama" in result.stdout

    def test_switch_with_base_url(self, tmp_path):
        """測試切換至有 base_url 的提供者"""
        from src.cli.main import app

        config_file = tmp_path / "config.yaml"
        config = {
            "llm": {"provider": "ollama", "model": "mistral", "api_key": "key123", "base_url": "http://old"},
            "providers": {
                "ollama": {"model": "mistral"},
                "openrouter": {"model": "gpt-3.5", "base_url": "https://openrouter.ai/api/v1"}
            }
        }
        config_file.write_text(yaml.dump(config), encoding="utf-8")

        with patch("src.cli.switcher.ConfigManager") as mock_cm:
            mock_cm.return_value.config_path = config_file
            mock_cm.return_value.config = config

            result = runner.invoke(app, ["switch", "--provider", "openrouter"])
            assert result.exit_code == 0
            assert "openrouter" in result.stdout

            # 驗證 base_url 已更新
            updated = yaml.safe_load(config_file.read_text(encoding="utf-8"))
            assert updated["llm"]["base_url"] == "https://openrouter.ai/api/v1"
            assert updated["llm"]["api_key"] == ""  # api_key 應被重設

    def test_switch_no_llm_section(self, tmp_path):
        """測試設定檔中沒有 llm 區塊時自動建立"""
        from src.cli.main import app

        config_file = tmp_path / "config.yaml"
        config = {
            "providers": {"gemini": {"model": "gemini-flash"}}
        }
        config_file.write_text(yaml.dump(config), encoding="utf-8")

        with patch("src.cli.switcher.ConfigManager") as mock_cm:
            mock_cm.return_value.config_path = config_file
            mock_cm.return_value.config = config

            result = runner.invoke(app, ["switch", "--provider", "gemini"])
            assert result.exit_code == 0
            assert "gemini" in result.stdout

    def test_switch_clears_base_url_if_no_default(self, tmp_path):
        """測試切換至無 base_url 的提供者時清除 base_url"""
        from src.cli.main import app

        config_file = tmp_path / "config.yaml"
        config = {
            "llm": {"provider": "openrouter", "model": "gpt-3.5", "base_url": "https://openrouter.ai/api/v1"},
            "providers": {
                "openrouter": {"model": "gpt-3.5", "base_url": "https://openrouter.ai/api/v1"},
                "gemini": {"model": "gemini-flash"}  # 沒有 base_url
            }
        }
        config_file.write_text(yaml.dump(config), encoding="utf-8")

        with patch("src.cli.switcher.ConfigManager") as mock_cm:
            mock_cm.return_value.config_path = config_file
            mock_cm.return_value.config = config

            result = runner.invoke(app, ["switch", "--provider", "gemini"])
            assert result.exit_code == 0

            updated = yaml.safe_load(config_file.read_text(encoding="utf-8"))
            assert updated["llm"]["base_url"] == ""

    def test_switch_interactive_mode(self, tmp_path):
        """測試互動式選擇提供者"""
        from src.cli.main import app

        config_file = tmp_path / "config.yaml"
        config = {
            "llm": {"provider": "ollama"},
            "providers": {"ollama": {}, "gemini": {"model": "gemini-flash"}}
        }
        config_file.write_text(yaml.dump(config), encoding="utf-8")

        with patch("src.cli.switcher.ConfigManager") as mock_cm:
            mock_cm.return_value.config_path = config_file
            mock_cm.return_value.config = config

            # 模擬使用者選擇第 2 個提供者（gemini）
            result = runner.invoke(app, ["switch"], input="2\n")
            assert result.exit_code == 0
            assert "gemini" in result.stdout

    def test_switch_same_provider(self, tmp_path):
        """測試切換到相同提供者時不變更"""
        from src.cli.main import app

        config_file = tmp_path / "config.yaml"
        config = {
            "llm": {"provider": "ollama"},
            "providers": {"ollama": {}}
        }
        config_file.write_text(yaml.dump(config), encoding="utf-8")

        with patch("src.cli.switcher.ConfigManager") as mock_cm:
            mock_cm.return_value.config_path = config_file
            mock_cm.return_value.config = config

            result = runner.invoke(app, ["switch", "--provider", "ollama"])
            assert result.exit_code == 0
            assert "未變更" in result.stdout


# ==================== KB Commands ====================

class TestKBCommands:
    """知識庫命令的測試"""

    @patch("src.cli.kb.KnowledgeBaseManager")
    @patch("src.cli.kb.get_llm_factory")
    @patch("src.cli.kb.ConfigManager")
    def test_kb_search(self, mock_cm, mock_factory, mock_kb_class):
        """測試知識庫搜尋命令"""
        from src.cli.main import app

        mock_cm.return_value.config = {
            "llm": {"provider": "mock"},
            "knowledge_base": {"path": "./test_kb"}
        }

        mock_kb_instance = mock_kb_class.return_value
        mock_kb_instance.search_examples.return_value = [
            {
                "content": "範例公文",
                "metadata": {"title": "測試函", "doc_type": "函"},
                "distance": 0.1
            }
        ]

        result = runner.invoke(app, ["kb", "search", "回收公告"])
        assert result.exit_code == 0
        assert "測試函" in result.stdout

    @patch("src.cli.kb.KnowledgeBaseManager")
    @patch("src.cli.kb.get_llm_factory")
    @patch("src.cli.kb.ConfigManager")
    def test_kb_search_no_results(self, mock_cm, mock_factory, mock_kb_class):
        """測試知識庫搜尋無結果"""
        from src.cli.main import app

        mock_cm.return_value.config = {
            "llm": {"provider": "mock"},
            "knowledge_base": {"path": "./test_kb"}
        }

        mock_kb_instance = mock_kb_class.return_value
        mock_kb_instance.search_examples.return_value = []

        result = runner.invoke(app, ["kb", "search", "不存在的東西"])
        assert result.exit_code == 0
        assert "找不到" in result.stdout

    def test_kb_ingest_nonexistent_dir(self):
        """測試 ingest 不存在的目錄"""
        from src.cli.main import app

        with patch("src.cli.kb.ConfigManager") as mock_cm:
            mock_cm.return_value.config = {
                "llm": {"provider": "mock"},
                "knowledge_base": {"path": "./test_kb"}
            }
            with patch("src.cli.kb.get_llm_factory"):
                with patch("src.cli.kb.KnowledgeBaseManager"):
                    result = runner.invoke(app, [
                        "kb", "ingest", "--source-dir", "/nonexistent/path"
                    ])
                    assert result.exit_code == 1

    @patch("src.cli.kb.KnowledgeBaseManager")
    @patch("src.cli.kb.get_llm_factory")
    @patch("src.cli.kb.ConfigManager")
    def test_kb_ingest_normal_flow(self, mock_cm, mock_factory, mock_kb_class, tmp_path):
        """測試正常匯入多個 Markdown 檔案的流程"""
        from src.cli.main import app

        mock_cm.return_value.config = {
            "llm": {"provider": "mock"},
            "knowledge_base": {"path": "./test_kb"}
        }
        mock_kb_instance = mock_kb_class.return_value
        mock_kb_instance.get_stats.return_value = {"examples_count": 2}

        # 建立測試用 Markdown 檔案（無 frontmatter）
        (tmp_path / "doc1.md").write_text("# 文件一\n內容一", encoding="utf-8")
        (tmp_path / "doc2.md").write_text("# 文件二\n內容二", encoding="utf-8")

        result = runner.invoke(app, [
            "kb", "ingest", "--source-dir", str(tmp_path), "--collection", "test_col"
        ])

        assert result.exit_code == 0
        assert "成功匯入 2 筆" in result.stdout
        assert "test_col" in result.stdout
        assert mock_kb_instance.add_document.call_count == 2

    @patch("src.cli.kb.KnowledgeBaseManager")
    @patch("src.cli.kb.get_llm_factory")
    @patch("src.cli.kb.ConfigManager")
    def test_kb_ingest_with_yaml_frontmatter(self, mock_cm, mock_factory, mock_kb_class, tmp_path):
        """測試匯入含有 YAML frontmatter 的 Markdown 並正確傳遞 metadata"""
        from src.cli.main import app

        mock_cm.return_value.config = {
            "llm": {"provider": "mock"},
            "knowledge_base": {"path": "./test_kb"}
        }
        mock_kb_instance = mock_kb_class.return_value
        mock_kb_instance.get_stats.return_value = {"examples_count": 1}

        # 建立含 YAML frontmatter 的 Markdown
        md_content = "---\ntitle: 測試函文\ndoc_type: 函\ntags:\n  - 測試\n  - 範例\n---\n公文主體內容"
        (tmp_path / "with_meta.md").write_text(md_content, encoding="utf-8")

        result = runner.invoke(app, [
            "kb", "ingest", "--source-dir", str(tmp_path)
        ])

        assert result.exit_code == 0
        assert "成功匯入 1 筆" in result.stdout

        # 驗證 add_document 傳入的 metadata 正確
        call_args = mock_kb_instance.add_document.call_args
        content_arg = call_args[0][0]
        metadata_arg = call_args[0][1]
        assert content_arg == "公文主體內容"
        assert metadata_arg["title"] == "測試函文"
        assert metadata_arg["doc_type"] == "函"
        # tags 是 list，應被 JSON 序列化
        assert json.loads(metadata_arg["tags"]) == ["測試", "範例"]

    @patch("src.cli.kb.KnowledgeBaseManager")
    @patch("src.cli.kb.get_llm_factory")
    @patch("src.cli.kb.ConfigManager")
    def test_kb_ingest_skips_deprecated_files(self, mock_cm, mock_factory, mock_kb_class, tmp_path):
        """測試跳過已棄用（deprecated: true）的文件"""
        from src.cli.main import app

        mock_cm.return_value.config = {
            "llm": {"provider": "mock"},
            "knowledge_base": {"path": "./test_kb"}
        }
        mock_kb_instance = mock_kb_class.return_value
        mock_kb_instance.get_stats.return_value = {"examples_count": 1}

        # 建立一個已棄用和一個正常的檔案
        deprecated_md = "---\ntitle: 舊文件\ndeprecated: true\n---\n已過期的內容"
        normal_md = "---\ntitle: 新文件\n---\n正常的內容"
        (tmp_path / "old.md").write_text(deprecated_md, encoding="utf-8")
        (tmp_path / "new.md").write_text(normal_md, encoding="utf-8")

        result = runner.invoke(app, [
            "kb", "ingest", "--source-dir", str(tmp_path)
        ])

        assert result.exit_code == 0
        assert "跳過已棄用" in result.stdout
        assert "已跳過 1 筆" in result.stdout
        assert "成功匯入 1 筆" in result.stdout
        # 只有一個檔案應被匯入
        assert mock_kb_instance.add_document.call_count == 1

    @patch("src.cli.kb.KnowledgeBaseManager")
    @patch("src.cli.kb.get_llm_factory")
    @patch("src.cli.kb.ConfigManager")
    def test_kb_ingest_with_reset_flag(self, mock_cm, mock_factory, mock_kb_class, tmp_path):
        """測試 --reset 旗標會呼叫 reset_db()"""
        from src.cli.main import app

        mock_cm.return_value.config = {
            "llm": {"provider": "mock"},
            "knowledge_base": {"path": "./test_kb"}
        }
        mock_kb_instance = mock_kb_class.return_value
        mock_kb_instance.get_stats.return_value = {"examples_count": 1}

        (tmp_path / "doc.md").write_text("# 測試\n內容", encoding="utf-8")

        result = runner.invoke(app, [
            "kb", "ingest", "--source-dir", str(tmp_path), "--reset"
        ])

        assert result.exit_code == 0
        assert "重設" in result.stdout
        mock_kb_instance.reset_db.assert_called_once()

    @patch("src.cli.kb.KnowledgeBaseManager")
    @patch("src.cli.kb.get_llm_factory")
    @patch("src.cli.kb.ConfigManager")
    def test_kb_ingest_metadata_sanitization(self, mock_cm, mock_factory, mock_kb_class, tmp_path):
        """測試 metadata 中各種資料型態的清理（datetime, list, 其他）"""
        from src.cli.main import app

        mock_cm.return_value.config = {
            "llm": {"provider": "mock"},
            "knowledge_base": {"path": "./test_kb"}
        }
        mock_kb_instance = mock_kb_class.return_value
        mock_kb_instance.get_stats.return_value = {"examples_count": 1}

        # 建立含有 date 欄位的 YAML frontmatter
        md_content = "---\ntitle: 日期測試\ndate: 2025-06-15\ncount: 42\nactive: true\n---\n內容"
        (tmp_path / "dated.md").write_text(md_content, encoding="utf-8")

        result = runner.invoke(app, [
            "kb", "ingest", "--source-dir", str(tmp_path)
        ])

        assert result.exit_code == 0
        call_args = mock_kb_instance.add_document.call_args
        metadata_arg = call_args[0][1]
        # YAML 解析的 date 會變成 datetime.date，應被轉為 ISO 字串
        assert metadata_arg["date"] == "2025-06-15"
        assert metadata_arg["count"] == 42
        assert metadata_arg["active"] is True

    @patch("src.cli.kb.KnowledgeBaseManager")
    @patch("src.cli.kb.get_llm_factory")
    @patch("src.cli.kb.ConfigManager")
    def test_kb_ingest_auto_fills_missing_metadata(self, mock_cm, mock_factory, mock_kb_class, tmp_path):
        """測試無 frontmatter 時自動填入 title 和 doc_type"""
        from src.cli.main import app

        mock_cm.return_value.config = {
            "llm": {"provider": "mock"},
            "knowledge_base": {"path": "./test_kb"}
        }
        mock_kb_instance = mock_kb_class.return_value
        mock_kb_instance.get_stats.return_value = {"examples_count": 1}

        (tmp_path / "no_meta.md").write_text("純文字公文內容", encoding="utf-8")

        result = runner.invoke(app, [
            "kb", "ingest", "--source-dir", str(tmp_path)
        ])

        assert result.exit_code == 0
        call_args = mock_kb_instance.add_document.call_args
        metadata_arg = call_args[0][1]
        # 自動填入 title 為檔名 stem、doc_type 為 unknown
        assert metadata_arg["title"] == "no_meta"
        assert metadata_arg["doc_type"] == "unknown"

    @patch("src.cli.kb.KnowledgeBaseManager")
    @patch("src.cli.kb.get_llm_factory")
    @patch("src.cli.kb.ConfigManager")
    def test_kb_search_multiple_results_table(self, mock_cm, mock_factory, mock_kb_class):
        """測試搜尋多個結果時正確顯示表格"""
        from src.cli.main import app

        mock_cm.return_value.config = {
            "llm": {"provider": "mock"},
            "knowledge_base": {"path": "./test_kb"}
        }

        mock_kb_instance = mock_kb_class.return_value
        mock_kb_instance.search_examples.return_value = [
            {
                "content": "第一份公文的內容",
                "metadata": {"title": "公告一", "doc_type": "公告"},
                "distance": 0.1
            },
            {
                "content": "第二份公文的內容",
                "metadata": {"title": "函二", "doc_type": "函"},
                "distance": 0.3
            },
            {
                "content": "第三份公文的內容，這是一份比較長的公文內容",
                "metadata": {"title": "簽三", "doc_type": "簽"},
                "distance": 0.5
            },
        ]

        result = runner.invoke(app, ["kb", "search", "公文", "--limit", "3"])
        assert result.exit_code == 0
        assert "公告一" in result.stdout
        assert "函二" in result.stdout
        assert "簽三" in result.stdout
        assert "搜尋結果" in result.stdout

    @patch("src.cli.kb.KnowledgeBaseManager")
    @patch("src.cli.kb.get_llm_factory")
    @patch("src.cli.kb.ConfigManager")
    def test_kb_search_with_none_metadata(self, mock_cm, mock_factory, mock_kb_class):
        """測試搜尋結果的 metadata 不是 dict 時的安全處理"""
        from src.cli.main import app

        mock_cm.return_value.config = {
            "llm": {"provider": "mock"},
            "knowledge_base": {"path": "./test_kb"}
        }

        mock_kb_instance = mock_kb_class.return_value
        mock_kb_instance.search_examples.return_value = [
            {
                "content": "某些內容",
                "metadata": None,
                "distance": 0.2
            },
            {
                "content": "其他內容",
                "metadata": "not_a_dict",
                "distance": 0.4
            },
        ]

        result = runner.invoke(app, ["kb", "search", "測試"])
        assert result.exit_code == 0
        # 當 metadata 不是 dict 時，應顯示 "未知" 和 "無標題"
        assert "未知" in result.stdout
        assert "無標題" in result.stdout

    @patch("src.cli.kb.KnowledgeBaseManager")
    @patch("src.cli.kb.get_llm_factory")
    @patch("src.cli.kb.ConfigManager")
    def test_kb_search_with_none_distance(self, mock_cm, mock_factory, mock_kb_class):
        """測試搜尋結果的 distance 為 None 時顯示 N/A"""
        from src.cli.main import app

        mock_cm.return_value.config = {
            "llm": {"provider": "mock"},
            "knowledge_base": {"path": "./test_kb"}
        }

        mock_kb_instance = mock_kb_class.return_value
        mock_kb_instance.search_examples.return_value = [
            {
                "content": "某內容",
                "metadata": {"title": "測試文件", "doc_type": "函"},
                "distance": None
            },
        ]

        result = runner.invoke(app, ["kb", "search", "測試"])
        assert result.exit_code == 0
        assert "N/A" in result.stdout

    @patch("src.cli.kb.KnowledgeBaseManager")
    @patch("src.cli.kb.get_llm_factory")
    @patch("src.cli.kb.ConfigManager")
    def test_kb_search_with_empty_content(self, mock_cm, mock_factory, mock_kb_class):
        """測試搜尋結果的 content 為空時顯示（無內容）"""
        from src.cli.main import app

        mock_cm.return_value.config = {
            "llm": {"provider": "mock"},
            "knowledge_base": {"path": "./test_kb"}
        }

        mock_kb_instance = mock_kb_class.return_value
        mock_kb_instance.search_examples.return_value = [
            {
                "content": "",
                "metadata": {"title": "空文件", "doc_type": "函"},
                "distance": 0.1
            },
        ]

        result = runner.invoke(app, ["kb", "search", "空"])
        assert result.exit_code == 0
        assert "無內容" in result.stdout


# ==================== KB parse_markdown_with_metadata ====================

class TestParseMarkdownWithMetadata:
    """解析帶 metadata 的 markdown 的測試"""

    def test_with_frontmatter(self, tmp_path):
        """測試有 YAML frontmatter 的 markdown"""
        from src.cli.kb import parse_markdown_with_metadata

        md_file = tmp_path / "test.md"
        md_file.write_text("---\ntitle: 測試\ndoc_type: 函\n---\n公文內容", encoding="utf-8")

        metadata, body = parse_markdown_with_metadata(md_file)
        assert metadata["title"] == "測試"
        assert metadata["doc_type"] == "函"
        assert body == "公文內容"

    def test_without_frontmatter(self, tmp_path):
        """測試沒有 frontmatter 的 markdown"""
        from src.cli.kb import parse_markdown_with_metadata

        md_file = tmp_path / "test.md"
        md_file.write_text("純文字內容\n第二行", encoding="utf-8")

        metadata, body = parse_markdown_with_metadata(md_file)
        assert metadata == {}
        assert "純文字內容" in body

    def test_with_invalid_yaml(self, tmp_path):
        """測試無效 YAML frontmatter"""
        from src.cli.kb import parse_markdown_with_metadata

        md_file = tmp_path / "test.md"
        md_file.write_text("---\ninvalid: [yaml: broken\n---\n內容", encoding="utf-8")

        metadata, body = parse_markdown_with_metadata(md_file)
        # 應回退到全文作為內容
        assert isinstance(metadata, dict)


# ==================== Config Tools Commands ====================

class TestConfigToolsCommand:
    """config_tools 模組的測試（test_connectivity 函數 + fetch_models CLI 命令）"""

    # ---------- test_connectivity 測試 ----------

    @patch("src.cli.config_tools.LiteLLMProvider")
    def test_connectivity_success(self, mock_llm_cls):
        """測試連線成功時回傳 True"""
        from src.cli.config_tools import test_connectivity

        mock_instance = MagicMock()
        mock_llm_cls.return_value = mock_instance

        result = test_connectivity("openrouter/test-model", "sk-test-key")

        assert result is True
        mock_llm_cls.assert_called_once_with({
            "provider": "openrouter",
            "model": "openrouter/test-model",
            "api_key": "sk-test-key",
            "base_url": "https://openrouter.ai/api/v1"
        })
        mock_instance.generate.assert_called_once_with("Hi", max_tokens=1)

    @patch("src.cli.config_tools.LiteLLMProvider")
    def test_connectivity_failure(self, mock_llm_cls):
        """測試連線失敗（generate 拋出例外）時回傳 False"""
        from src.cli.config_tools import test_connectivity

        mock_instance = MagicMock()
        mock_instance.generate.side_effect = Exception("Connection refused")
        mock_llm_cls.return_value = mock_instance

        result = test_connectivity("openrouter/bad-model", "sk-test-key")

        assert result is False

    def test_connectivity_empty_api_key(self):
        """測試空 API key 時直接回傳 False，不呼叫 LLM"""
        from src.cli.config_tools import test_connectivity

        assert test_connectivity("openrouter/model", "") is False
        assert test_connectivity("openrouter/model", None) is False

    @patch("src.cli.config_tools.LiteLLMProvider")
    def test_connectivity_constructor_raises(self, mock_llm_cls):
        """測試 LiteLLMProvider 建構時拋出例外也回傳 False"""
        from src.cli.config_tools import test_connectivity

        mock_llm_cls.side_effect = Exception("Invalid config")

        result = test_connectivity("openrouter/model", "sk-key")

        assert result is False

    # ---------- fetch_models CLI 命令測試 ----------

    @patch("src.cli.config_tools.test_connectivity")
    @patch("src.cli.config_tools.requests.get")
    @patch("src.cli.config_tools.ConfigManager")
    def test_fetch_models_normal(self, mock_cm, mock_get, mock_test_conn):
        """測試正常擷取免費模型清單並測試連線"""
        from src.cli.config_tools import app as config_app

        # 設定 ConfigManager mock
        mock_cm.return_value.config = {
            "providers": {"openrouter": {"api_key": "sk-test"}}
        }

        # 設定 API 回應：2 個免費模型 + 1 個付費模型
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "free/model-a",
                    "name": "Free Model A",
                    "context_length": 128000,
                    "pricing": {"prompt": "0", "completion": "0"}
                },
                {
                    "id": "free/model-b",
                    "name": "Free Model B",
                    "context_length": 64000,
                    "pricing": {"prompt": "0", "completion": "0"}
                },
                {
                    "id": "paid/model-c",
                    "name": "Paid Model C",
                    "context_length": 32000,
                    "pricing": {"prompt": "0.001", "completion": "0.002"}
                },
            ]
        }
        mock_get.return_value = mock_response

        # 第一個模型連線成功，第二個失敗
        mock_test_conn.side_effect = [True, False]

        result = runner.invoke(config_app, ["--limit", "2"])

        assert result.exit_code == 0
        assert "free/model-a" in result.stdout
        assert "free/model-b" in result.stdout
        # 付費模型不應出現
        assert "paid/model-c" not in result.stdout

    @patch("src.cli.config_tools.requests.get")
    @patch("src.cli.config_tools.ConfigManager")
    def test_fetch_models_api_error(self, mock_cm, mock_get):
        """測試 API 請求失敗時的錯誤處理"""
        from src.cli.config_tools import app as config_app

        mock_cm.return_value.config = {
            "providers": {"openrouter": {"api_key": "sk-test"}}
        }

        mock_get.side_effect = requests.exceptions.ConnectionError("Network unreachable")

        result = runner.invoke(config_app, [])

        assert result.exit_code == 1
        assert "失敗" in result.stdout

    @patch("src.cli.config_tools.requests.get")
    @patch("src.cli.config_tools.ConfigManager")
    def test_fetch_models_no_free_models(self, mock_cm, mock_get):
        """測試 API 回應中沒有免費模型時的處理"""
        from src.cli.config_tools import app as config_app

        mock_cm.return_value.config = {
            "providers": {"openrouter": {"api_key": "sk-test"}}
        }

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "paid/only",
                    "name": "Paid Only",
                    "context_length": 8000,
                    "pricing": {"prompt": "0.01", "completion": "0.02"}
                }
            ]
        }
        mock_get.return_value = mock_response

        result = runner.invoke(config_app, [])

        assert result.exit_code == 0
        # 表格應該不含任何模型列
        assert "paid/only" not in result.stdout

    @patch("src.cli.config_tools.test_connectivity")
    @patch("src.cli.config_tools.requests.get")
    @patch("src.cli.config_tools.ConfigManager")
    def test_fetch_models_no_test_flag(self, mock_cm, mock_get, mock_test_conn):
        """測試 --no-test 旗標跳過連線測試"""
        from src.cli.config_tools import app as config_app

        mock_cm.return_value.config = {
            "providers": {"openrouter": {"api_key": "sk-test"}}
        }

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "free/model-x",
                    "name": "Free Model X",
                    "context_length": 32000,
                    "pricing": {"prompt": "0", "completion": "0"}
                }
            ]
        }
        mock_get.return_value = mock_response

        result = runner.invoke(config_app, ["--no-test"])

        assert result.exit_code == 0
        assert "free/model-x" in result.stdout
        # 未呼叫 test_connectivity
        mock_test_conn.assert_not_called()

    @patch("src.cli.config_tools.test_connectivity")
    @patch("src.cli.config_tools.requests.get")
    @patch("src.cli.config_tools.os.getenv", return_value=None)
    @patch("src.cli.config_tools.ConfigManager")
    def test_fetch_models_no_api_key(self, mock_cm, mock_getenv, mock_get, mock_test_conn):
        """測試沒有 API key 時跳過連線測試並顯示警告"""
        from src.cli.config_tools import app as config_app

        mock_cm.return_value.config = {
            "providers": {"openrouter": {"api_key": ""}}
        }

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "free/model-z",
                    "name": "Free Model Z",
                    "context_length": 16000,
                    "pricing": {"prompt": "0", "completion": "0"}
                }
            ]
        }
        mock_get.return_value = mock_response

        result = runner.invoke(config_app, [])

        assert result.exit_code == 0
        assert "警告" in result.stdout or "API Key" in result.stdout
        # 沒有 API key 時不應呼叫連線測試
        mock_test_conn.assert_not_called()

    @patch("src.cli.config_tools.Confirm")
    @patch("src.cli.config_tools.yaml")
    @patch("src.cli.config_tools.test_connectivity")
    @patch("src.cli.config_tools.requests.get")
    @patch("src.cli.config_tools.ConfigManager")
    def test_fetch_models_update_flag_confirm(
        self, mock_cm, mock_get, mock_test_conn, mock_yaml, mock_confirm
    ):
        """測試 --update 旗標且使用者確認時更新設定檔"""
        from src.cli.config_tools import app as config_app

        mock_cm_instance = mock_cm.return_value
        mock_cm_instance.config = {
            "providers": {"openrouter": {"api_key": "sk-test"}}
        }
        mock_cm_instance.config_path = "config.yaml"

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "free/best-model",
                    "name": "Best Free Model",
                    "context_length": 200000,
                    "pricing": {"prompt": "0", "completion": "0"}
                }
            ]
        }
        mock_get.return_value = mock_response

        # 連線測試成功
        mock_test_conn.return_value = True

        # 使用者確認更新
        mock_confirm.ask.return_value = True

        # Mock open 和 yaml 操作
        mock_yaml.safe_load.return_value = {
            "providers": {"openrouter": {"model": "old-model"}}
        }

        mock_open = MagicMock()
        with patch("builtins.open", mock_open):
            result = runner.invoke(config_app, ["--update"])

        assert result.exit_code == 0
        assert "更新成功" in result.stdout
        mock_confirm.ask.assert_called_once()

    @patch("src.cli.config_tools.Confirm")
    @patch("src.cli.config_tools.test_connectivity")
    @patch("src.cli.config_tools.requests.get")
    @patch("src.cli.config_tools.ConfigManager")
    def test_fetch_models_update_flag_decline(
        self, mock_cm, mock_get, mock_test_conn, mock_confirm
    ):
        """測試 --update 旗標但使用者拒絕時不更新"""
        from src.cli.config_tools import app as config_app

        mock_cm_instance = mock_cm.return_value
        mock_cm_instance.config = {
            "providers": {"openrouter": {"api_key": "sk-test"}}
        }
        mock_cm_instance.config_path = "config.yaml"

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "free/some-model",
                    "name": "Some Model",
                    "context_length": 100000,
                    "pricing": {"prompt": "0", "completion": "0"}
                }
            ]
        }
        mock_get.return_value = mock_response

        mock_test_conn.return_value = True
        mock_confirm.ask.return_value = False

        result = runner.invoke(config_app, ["--update"])

        assert result.exit_code == 0
        # 使用者拒絕，不應顯示更新成功
        assert "更新成功" not in result.stdout

    @patch("src.cli.config_tools.requests.get")
    @patch("src.cli.config_tools.ConfigManager")
    def test_fetch_models_http_status_error(self, mock_cm, mock_get):
        """測試 HTTP 狀態碼錯誤（如 500）的處理"""
        from src.cli.config_tools import app as config_app

        mock_cm.return_value.config = {
            "providers": {"openrouter": {"api_key": "sk-test"}}
        }

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
        mock_get.return_value = mock_response

        result = runner.invoke(config_app, [])

        assert result.exit_code == 1
        assert "失敗" in result.stdout

    @patch("src.cli.config_tools.requests.get")
    @patch("src.cli.config_tools.ConfigManager")
    def test_fetch_models_invalid_pricing(self, mock_cm, mock_get):
        """測試定價欄位為無效值時，該模型被跳過"""
        from src.cli.config_tools import app as config_app

        mock_cm.return_value.config = {
            "providers": {"openrouter": {"api_key": "sk-test"}}
        }

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "model/bad-price",
                    "name": "Bad Price Model",
                    "context_length": 8000,
                    "pricing": {"prompt": "not-a-number", "completion": "0"}
                },
                {
                    "id": "free/good-model",
                    "name": "Good Free Model",
                    "context_length": 32000,
                    "pricing": {"prompt": "0", "completion": "0"}
                }
            ]
        }
        mock_get.return_value = mock_response

        result = runner.invoke(config_app, ["--no-test"])

        assert result.exit_code == 0
        # 無效定價的模型被跳過
        assert "model/bad-price" not in result.stdout
        # 有效免費模型仍顯示
        assert "free/good-model" in result.stdout

    @patch("src.cli.config_tools.test_connectivity")
    @patch("src.cli.config_tools.requests.get")
    @patch("src.cli.config_tools.ConfigManager")
    def test_fetch_models_all_fail_connectivity(self, mock_cm, mock_get, mock_test_conn):
        """測試所有模型連線測試都失敗時退回使用第一個模型"""
        from src.cli.config_tools import app as config_app

        mock_cm.return_value.config = {
            "providers": {"openrouter": {"api_key": "sk-test"}}
        }

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "free/fail-1",
                    "name": "Fail 1",
                    "context_length": 50000,
                    "pricing": {"prompt": "0", "completion": "0"}
                },
                {
                    "id": "free/fail-2",
                    "name": "Fail 2",
                    "context_length": 30000,
                    "pricing": {"prompt": "0", "completion": "0"}
                }
            ]
        }
        mock_get.return_value = mock_response

        # 所有連線測試都失敗
        mock_test_conn.return_value = False

        result = runner.invoke(config_app, [])

        assert result.exit_code == 0
        # 應顯示退回訊息
        assert "退回" in result.stdout or "沒有模型通過" in result.stdout

    @patch("src.cli.config_tools.test_connectivity")
    @patch("src.cli.config_tools.requests.get")
    @patch("src.cli.config_tools.ConfigManager")
    def test_fetch_models_sorted_by_context_length(self, mock_cm, mock_get, mock_test_conn):
        """測試模型按上下文長度降序排列"""
        from src.cli.config_tools import app as config_app

        mock_cm.return_value.config = {
            "providers": {"openrouter": {"api_key": "sk-test"}}
        }

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "free/small",
                    "name": "Small Context",
                    "context_length": 4000,
                    "pricing": {"prompt": "0", "completion": "0"}
                },
                {
                    "id": "free/large",
                    "name": "Large Context",
                    "context_length": 200000,
                    "pricing": {"prompt": "0", "completion": "0"}
                }
            ]
        }
        mock_get.return_value = mock_response

        mock_test_conn.return_value = True

        result = runner.invoke(config_app, ["--limit", "5"])

        assert result.exit_code == 0
        # 確認兩個模型都出現
        assert "free/large" in result.stdout
        assert "free/small" in result.stdout
        # large 應排在 small 前面（在輸出中先出現）
        large_pos = result.stdout.index("free/large")
        small_pos = result.stdout.index("free/small")
        assert large_pos < small_pos

    @patch("src.cli.config_tools.requests.get")
    @patch("src.cli.config_tools.os.getenv")
    @patch("src.cli.config_tools.ConfigManager")
    def test_fetch_models_api_key_from_env(self, mock_cm, mock_getenv, mock_get):
        """測試從環境變數取得 API key"""
        from src.cli.config_tools import app as config_app

        # ConfigManager 沒有 API key
        mock_cm.return_value.config = {
            "providers": {"openrouter": {"api_key": ""}}
        }

        # 環境變數有 API key
        def getenv_side_effect(key, *args):
            if key == "LLM_API_KEY":
                return "sk-from-env"
            return None
        mock_getenv.side_effect = getenv_side_effect

        mock_response = MagicMock()
        mock_response.json.return_value = {"data": []}
        mock_get.return_value = mock_response

        result = runner.invoke(config_app, ["--no-test"])

        assert result.exit_code == 0

    @patch("src.cli.config_tools.requests.get")
    @patch("src.cli.config_tools.ConfigManager")
    def test_fetch_models_empty_data_response(self, mock_cm, mock_get):
        """測試 API 回傳空 data 陣列"""
        from src.cli.config_tools import app as config_app

        mock_cm.return_value.config = {
            "providers": {"openrouter": {"api_key": "sk-test"}}
        }

        mock_response = MagicMock()
        mock_response.json.return_value = {"data": []}
        mock_get.return_value = mock_response

        result = runner.invoke(config_app, [])

        assert result.exit_code == 0

    @patch("src.cli.config_tools.Confirm")
    @patch("src.cli.config_tools.yaml")
    @patch("src.cli.config_tools.test_connectivity")
    @patch("src.cli.config_tools.requests.get")
    @patch("src.cli.config_tools.ConfigManager")
    def test_fetch_models_update_config_missing_providers_key(
        self, mock_cm, mock_get, mock_test_conn, mock_yaml, mock_confirm
    ):
        """測試 --update 時 config 檔案中缺少 providers 鍵的防禦性處理"""
        from src.cli.config_tools import app as config_app

        mock_cm_instance = mock_cm.return_value
        mock_cm_instance.config = {
            "providers": {"openrouter": {"api_key": "sk-test"}}
        }
        mock_cm_instance.config_path = "config.yaml"

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "free/model-update",
                    "name": "Update Model",
                    "context_length": 50000,
                    "pricing": {"prompt": "0", "completion": "0"}
                }
            ]
        }
        mock_get.return_value = mock_response

        mock_test_conn.return_value = True
        mock_confirm.ask.return_value = True

        # yaml.safe_load 回傳完全沒有 providers 鍵的結構
        mock_yaml.safe_load.return_value = {}

        mock_open = MagicMock()
        with patch("builtins.open", mock_open):
            result = runner.invoke(config_app, ["--update"])

        assert result.exit_code == 0
        assert "更新成功" in result.stdout

    @patch("src.cli.config_tools.Confirm")
    @patch("src.cli.config_tools.yaml")
    @patch("src.cli.config_tools.test_connectivity")
    @patch("src.cli.config_tools.requests.get")
    @patch("src.cli.config_tools.ConfigManager")
    def test_fetch_models_update_config_missing_openrouter_key(
        self, mock_cm, mock_get, mock_test_conn, mock_yaml, mock_confirm
    ):
        """測試 --update 時 config 有 providers 但缺少 openrouter 子鍵"""
        from src.cli.config_tools import app as config_app

        mock_cm_instance = mock_cm.return_value
        mock_cm_instance.config = {
            "providers": {"openrouter": {"api_key": "sk-test"}}
        }
        mock_cm_instance.config_path = "config.yaml"

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "free/model-update2",
                    "name": "Update Model 2",
                    "context_length": 40000,
                    "pricing": {"prompt": "0", "completion": "0"}
                }
            ]
        }
        mock_get.return_value = mock_response

        mock_test_conn.return_value = True
        mock_confirm.ask.return_value = True

        # yaml.safe_load 回傳有 providers 但沒有 openrouter 的結構
        mock_yaml.safe_load.return_value = {"providers": {"ollama": {}}}

        mock_open = MagicMock()
        with patch("builtins.open", mock_open):
            result = runner.invoke(config_app, ["--update"])

        assert result.exit_code == 0
        assert "更新成功" in result.stdout
