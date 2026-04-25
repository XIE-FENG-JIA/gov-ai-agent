## Problem

`kb_data/regulation_doc_type_mapping.yaml` (144 lines, 20 regulations) maps
regulation names to allowed government-document types (公文類型) for
cross-referencing in `FactChecker`. It was added without a spec, without a
dedicated reader module, and without any test coverage.

Risks:
1. **Schema drift** — new contributors can add entries in arbitrary shapes
   (wrong field names, wrong pcode format, unknown doc types) with no
   rejection mechanism.
2. **Silent regression** — if the yaml becomes malformed it fails only at
   runtime inside FactChecker; there is no automated gate.
3. **No documented contract** — the four-field schema (`pcode`,
   `applicable_doc_types`, `description?`, `not_applicable?`) and valid
   doc-type universe are implied by comments only.

## Solution

Add a spec, schema contract, and a roundtrip test:

1. **Spec file** (`openspec/specs/regulation-doc-type-mapping/spec.md`) —
   document the allowed doc_types universe, required vs optional fields, pcode
   format, and cross-validation rules.
2. **Roundtrip test** (`tests/test_regulation_doc_type_mapping.py`) — load the
   yaml, validate every entry against the schema, dump to a temp buffer, reload,
   and assert structural equality. Runs in the standard `pytest` suite without
   mocks or network access.

## Non-Goals

- No reader module refactor in this change.
- No changes to FactChecker logic or any src/ files.
- No additional entries added to the yaml.

## Acceptance Criteria

1. `openspec/specs/regulation-doc-type-mapping/spec.md` exists with:
   - Valid doc_types universe listed
   - Required vs optional fields documented
   - Pcode format specified (`[A-Z][A-Z0-9]\d{6,7}` allowed)
2. `tests/test_regulation_doc_type_mapping.py` exists and passes:
   - `test_schema_all_entries_valid` — every regulation entry matches schema
   - `test_roundtrip_load_dump_reload` — yaml roundtrip preserves structure
3. `python -m pytest tests/test_regulation_doc_type_mapping.py -q` = all green
