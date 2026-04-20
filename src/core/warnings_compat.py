from __future__ import annotations

import warnings


def suppress_known_third_party_deprecations() -> None:
    """Suppress known upstream deprecations that block strict warning gates.

    Keep filters narrow so project-local deprecations still fail under
    ``-W error::DeprecationWarning``.
    """
    warnings.filterwarnings(
        "ignore",
        message=r"open_text is deprecated\. Use files\(\) instead\.",
        category=DeprecationWarning,
        module=r"litellm\.litellm_core_utils\.get_model_cost_map",
    )
    warnings.filterwarnings(
        "ignore",
        message=r"Accessing the 'model_fields' attribute on the instance is deprecated\.",
        category=DeprecationWarning,
        module=r"chromadb\.types",
    )
