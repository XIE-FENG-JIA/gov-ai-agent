"""Schema validation + roundtrip tests for kb_data/regulation_doc_type_mapping.yaml."""
import io
import re
from pathlib import Path

import pytest
import yaml

YAML_PATH = Path(__file__).resolve().parent.parent / "kb_data" / "regulation_doc_type_mapping.yaml"

VALID_DOC_TYPES = frozenset(
    ["函", "公告", "簽", "令", "書函", "開會通知單", "會議紀錄", "人事令", "環保公告", "採購公告", "訴願決定書"]
)

PCODE_RE = re.compile(r"^[A-Z][A-Z0-9]\d{5,7}$")


def _load_yaml():
    return yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))


class TestRegulationDocTypeMappingSchema:
    def test_yaml_file_exists(self):
        assert YAML_PATH.exists(), f"Missing {YAML_PATH}"

    def test_top_level_has_regulations_key(self):
        data = _load_yaml()
        assert "regulations" in data, "Top-level key 'regulations' missing"
        assert isinstance(data["regulations"], dict), "'regulations' must be a dict"

    def test_regulations_non_empty(self):
        data = _load_yaml()
        assert len(data["regulations"]) > 0, "regulations dict is empty"

    def test_schema_all_entries_valid(self):
        data = _load_yaml()
        errors = []
        for name, entry in data["regulations"].items():
            if not isinstance(entry, dict):
                errors.append(f"{name}: entry must be a dict, got {type(entry)}")
                continue

            # Required: pcode
            pcode = entry.get("pcode")
            if not pcode:
                errors.append(f"{name}: missing required field 'pcode'")
            elif not PCODE_RE.match(str(pcode)):
                errors.append(f"{name}: pcode '{pcode}' does not match expected pattern")

            # Required: applicable_doc_types
            adt = entry.get("applicable_doc_types")
            if not adt:
                errors.append(f"{name}: missing or empty 'applicable_doc_types'")
            elif not isinstance(adt, list):
                errors.append(f"{name}: 'applicable_doc_types' must be a list")
            else:
                invalid = [t for t in adt if t not in VALID_DOC_TYPES]
                if invalid:
                    errors.append(f"{name}: unknown doc_types in applicable_doc_types: {invalid}")

            # Optional: description
            desc = entry.get("description")
            if desc is not None and not isinstance(desc, str):
                errors.append(f"{name}: 'description' must be a string")

            # Optional: not_applicable
            na = entry.get("not_applicable")
            if na is not None:
                if not isinstance(na, list):
                    errors.append(f"{name}: 'not_applicable' must be a list")
                else:
                    invalid_na = [t for t in na if t not in VALID_DOC_TYPES]
                    if invalid_na:
                        errors.append(
                            f"{name}: unknown doc_types in not_applicable: {invalid_na}"
                        )
                    if isinstance(adt, list):
                        overlap = set(adt) & set(na)
                        if overlap:
                            errors.append(
                                f"{name}: doc_types appear in both applicable and not_applicable: {overlap}"
                            )

        assert not errors, "Schema violations:\n" + "\n".join(errors)

    def test_roundtrip_load_dump_reload(self):
        original = _load_yaml()
        buf = io.StringIO()
        yaml.dump(original, buf, allow_unicode=True, default_flow_style=False)
        buf.seek(0)
        reloaded = yaml.safe_load(buf)
        assert original == reloaded, "YAML roundtrip (load→dump→reload) changed the data"

    def test_known_regulations_present(self):
        """Spot-check that key baseline regulations are still in the file."""
        data = _load_yaml()
        regs = data["regulations"]
        expected = ["公文程式條例", "行政程序法", "政府採購法"]
        missing = [r for r in expected if r not in regs]
        assert not missing, f"Expected regulations missing: {missing}"

    def test_pcode_uniqueness(self):
        data = _load_yaml()
        pcodes = [str(entry.get("pcode", "")) for entry in data["regulations"].values()]
        seen = set()
        duplicates = [p for p in pcodes if p in seen or seen.add(p)]
        assert not duplicates, f"Duplicate pcodes found: {duplicates}"
