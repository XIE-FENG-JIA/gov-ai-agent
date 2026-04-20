from __future__ import annotations

from contextlib import contextmanager
import warnings

try:
    from pydantic.warnings import PydanticDeprecatedSince211
except Exception:  # pragma: no cover - compatibility with older pydantic
    PydanticDeprecatedSince211 = DeprecationWarning


def _apply_known_third_party_warning_filters() -> None:
    """Install narrow filters for noisy third-party deprecations.

    Keep filters narrow so project-local deprecations still fail under
    ``-W error::DeprecationWarning``.
    """
    chromadb_model_fields_message = r"Accessing the 'model_fields' attribute on the instance is deprecated\."
    warnings.filterwarnings(
        "ignore",
        message=r"open_text is deprecated\. Use files\(\) instead\.",
        category=DeprecationWarning,
        module=r"litellm\.litellm_core_utils\.get_model_cost_map",
    )
    warnings.filterwarnings(
        "ignore",
        message=chromadb_model_fields_message,
        category=PydanticDeprecatedSince211,
    )
    warnings.filterwarnings(
        "ignore",
        message=chromadb_model_fields_message,
        category=DeprecationWarning,
    )


def suppress_known_third_party_deprecations() -> None:
    """Install process-wide filters for known third-party deprecations."""
    _apply_known_third_party_warning_filters()


@contextmanager
def suppress_known_third_party_deprecations_temporarily():
    """Re-apply known warning filters inside a local warnings context.

    Some callers run under ``warnings.simplefilter("error", DeprecationWarning)``.
    ChromaDB currently emits a burst of ``PydanticDeprecatedSince211`` warnings
    during routine collection operations, so we suppress that category inside the
    scoped context and keep the process-wide filter narrow.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", PydanticDeprecatedSince211)
        _apply_known_third_party_warning_filters()
        yield
