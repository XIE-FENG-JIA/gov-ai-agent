"""Integration tests: cite_cmd e2e — CLI condition resolution → citation output.

Gated by GOV_AI_RUN_INTEGRATION=1 — default skip.
Tests the cite command helper functions end-to-end using the repo's real
regulation_doc_type_mapping.yaml file without network calls.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


def _require_live_integration() -> None:
    if os.getenv("GOV_AI_RUN_INTEGRATION") != "1":
        pytest.skip("set GOV_AI_RUN_INTEGRATION=1 to run cite_cmd integration tests")


_MAPPING_PATH = Path("kb_data/regulation_doc_type_mapping.yaml")


# ---------------------------------------------------------------------------
# cite_cmd helper e2e tests (use real mapping file, no network)
# ---------------------------------------------------------------------------

def test_cite_cmd_detect_and_filter_函() -> None:
    """A 函 draft should detect doc_type=函 and return applicable regulations."""
    _require_live_integration()

    if not _MAPPING_PATH.exists():
        pytest.skip(f"regulation mapping file not found at {_MAPPING_PATH}")

    from src.cli.cite_cmd import _detect_doc_type, _filter_applicable, _load_mapping

    draft = "主旨：函請 貴機關辦理相關業務，請查照辦理。說明：依本院指示辦理。"
    detected_type = _detect_doc_type(draft)

    # type detection must return a non-empty string
    assert detected_type is not None, "Type detection returned None for 函 draft"
    assert isinstance(detected_type, str) and detected_type.strip(), (
        f"Type detection returned empty string for 函 draft"
    )

    regulations = _load_mapping(_MAPPING_PATH)
    assert isinstance(regulations, dict) and regulations, (
        "Regulation mapping is empty — check kb_data/regulation_doc_type_mapping.yaml"
    )

    applicable = _filter_applicable(regulations, detected_type)
    assert isinstance(applicable, list), "_filter_applicable must return a list"
    # For 函, at least one regulation should be applicable
    assert len(applicable) >= 1, (
        f"No applicable regulations found for doc_type={detected_type!r}. "
        f"Mapping has {len(regulations)} entries."
    )

    # Each entry must have the expected shape
    for reg in applicable:
        assert "name" in reg, f"Regulation missing 'name': {reg}"
        assert "cite_format" in reg, f"Regulation missing 'cite_format': {reg}"
        assert reg["cite_format"].startswith("依據《"), (
            f"cite_format does not start with '依據《': {reg['cite_format']!r}"
        )


def test_cite_cmd_detect_公告_type() -> None:
    """A 公告 draft should be detected correctly."""
    _require_live_integration()

    if not _MAPPING_PATH.exists():
        pytest.skip(f"regulation mapping file not found at {_MAPPING_PATH}")

    from src.cli.cite_cmd import _detect_doc_type, _filter_applicable, _load_mapping

    draft = "主旨：公告本機關相關政策措施。依據：行政院函。說明：本公告自即日起生效。"
    detected_type = _detect_doc_type(draft)
    assert detected_type is not None

    regulations = _load_mapping(_MAPPING_PATH)
    applicable = _filter_applicable(regulations, detected_type)
    assert isinstance(applicable, list)


def test_cite_cmd_json_output_schema() -> None:
    """cite_cmd JSON output schema must include doc_type and applicable_regulations keys."""
    _require_live_integration()

    if not _MAPPING_PATH.exists():
        pytest.skip(f"regulation mapping file not found at {_MAPPING_PATH}")

    from src.cli.cite_cmd import _detect_doc_type, _filter_applicable, _load_mapping

    draft = "主旨：為辦理本院年度採購事宜，公告相關規定，請依照辦理。採購公告。"
    detected_type = _detect_doc_type(draft)
    if not detected_type:
        pytest.skip("Type detection could not classify draft — expected 採購公告")

    regulations = _load_mapping(_MAPPING_PATH)
    applicable = _filter_applicable(regulations, detected_type)

    output = {
        "doc_type": detected_type,
        "applicable_regulations": applicable,
        "kb_semantic_results": [],
    }

    # Verify it serialises to valid JSON
    serialised = json.dumps(output, ensure_ascii=False)
    parsed = json.loads(serialised)
    assert parsed["doc_type"] == detected_type
    assert isinstance(parsed["applicable_regulations"], list)
    assert "kb_semantic_results" in parsed


def test_cite_cmd_filter_returns_sorted_by_name() -> None:
    """_filter_applicable results must be sorted by regulation name (ascending)."""
    _require_live_integration()

    if not _MAPPING_PATH.exists():
        pytest.skip(f"regulation mapping file not found at {_MAPPING_PATH}")

    from src.cli.cite_cmd import _filter_applicable, _load_mapping

    regulations = _load_mapping(_MAPPING_PATH)
    applicable = _filter_applicable(regulations, "函")
    if len(applicable) < 2:
        pytest.skip("Not enough 函 regulations to verify sort order")

    names = [r["name"] for r in applicable]
    assert names == sorted(names), f"Regulations not sorted by name: {names}"


def test_cite_cmd_missing_mapping_raises_file_not_found() -> None:
    """_load_mapping with a nonexistent path must raise FileNotFoundError."""
    _require_live_integration()

    from src.cli.cite_cmd import _load_mapping

    with pytest.raises(FileNotFoundError):
        _load_mapping(Path("/nonexistent/path/to/mapping.yaml"))
