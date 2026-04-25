"""Public interface for running lint checks shared between
``lint_cmd`` and ``generate/export``.

Extracted to break the iceberg coupling described in T13.3 of
``openspec/changes/13-cli-fat-rotate-v3/tasks.md``.
"""


def run_lint(text: str) -> list[dict]:
    """Run all gov-doc lint checks on *text* and return an issue list.

    Each issue is a dict with ``line`` (0 = whole doc), ``category``,
    and ``detail`` keys.  This is a thin public shim over
    ``lint_cmd._run_lint`` so that callers outside the ``lint_cmd``
    group do not import private symbols directly.
    """
    from src.cli.lint_cmd import _run_lint  # lazy to avoid circular import

    return _run_lint(text)
