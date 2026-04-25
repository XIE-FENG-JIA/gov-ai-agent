# Purpose

Define the schema contract for `kb_data/regulation_doc_type_mapping.yaml` so
that FactChecker's cross-validation logic has a documented, testable source
of truth for which regulations apply to which government document types (公文類型).

## Schema Contract

### Top-Level Structure

```yaml
regulations:
  <regulation_name>:   # string key, Chinese regulation name
    pcode: <str>
    applicable_doc_types: [<doc_type>, ...]
    description: <str>          # optional
    not_applicable: [<doc_type>, ...]  # optional
```

### Required Fields

| Field                  | Type            | Constraint                          |
|------------------------|-----------------|-------------------------------------|
| `pcode`                | `str`           | Alphanumeric, e.g. `A0030018`       |
| `applicable_doc_types` | `list[str]`     | Non-empty; each item in valid_types |

### Optional Fields

| Field            | Type        | Constraint                                  |
|------------------|-------------|---------------------------------------------|
| `description`    | `str`       | Non-empty human-readable description        |
| `not_applicable` | `list[str]` | Subset of valid_types; no overlap with applicable_doc_types |

### Valid Doc-Type Universe

```
函  公告  簽  令  書函  開會通知單  會議紀錄  人事令  環保公告  採購公告  訴願決定書
```

Any string outside this set in `applicable_doc_types` or `not_applicable` is
a schema violation.

### Cross-Validation Rules

1. `applicable_doc_types` must be non-empty.
2. `not_applicable` (if present) must not overlap with `applicable_doc_types`.
3. Each doc type in both lists must belong to the valid universe above.
4. `pcode` must be a non-empty string matching `^[A-Z][A-Z0-9]\d{5,7}$`.

## Runtime Semantics

- If a cited regulation is **in** the mapping and the document type is
  **in** `applicable_doc_types` → no flag.
- If a cited regulation is in the mapping and the document type is
  **in** `not_applicable` → flag as `error`.
- If a cited regulation is in the mapping and the document type is
  **not in** `applicable_doc_types` and **not in** `not_applicable` → flag as
  `warning`.
- If a cited regulation is **not in** the mapping → no cross-check (unknown
  regulation, pass through).

## Maintenance Rules

- Any new entry must include `pcode` and at least one `applicable_doc_types`.
- New doc type values must be added to the valid universe in this spec AND in
  the yaml comment header before use.
- The roundtrip test (`tests/test_regulation_doc_type_mapping.py`) must pass
  after every edit to the yaml.
