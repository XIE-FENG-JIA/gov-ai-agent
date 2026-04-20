#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import os
import sys
import types

import src.api.dependencies as _deps
import src.api.middleware as _mw
from src.api.app import (
    _ALLOWED_HEADERS, _ALLOWED_ORIGINS, _cleanup_old_outputs, _ensure_api_key,
    _expand_loopback_origins, _preflight_check, _setup_logging, _warmup_law_cache,
    create_app, lifespan, resolve_bind_host,
)
from src.api.dependencies import executor, get_config, get_kb, get_llm
from src.api.helpers import (  # noqa: F401
    ENDPOINT_TIMEOUT as _ENDPOINT_TIMEOUT, MEETING_TIMEOUT as _MEETING_TIMEOUT, _TRUST_PROXY, _get_client_ip,
    _get_error_code, _sanitize_error, _sanitize_output_filename, review_result_to_dict,
    run_in_executor as _run_in_executor,
)
from src.api.middleware import RequestBodyLimitMiddleware, _MetricsCollector, _RATE_LIMIT_RPM, _RateLimiter, security_middleware  # noqa: F401
from src.api.models import *  # noqa: F401,F403
from src.api.routes.agents import *  # noqa: F401,F403
from src.api.routes.health import *  # noqa: F401,F403
from src.api.routes.knowledge import *  # noqa: F401,F403
from src.api.routes.workflow import *  # noqa: F401,F403
from src.core.config import ConfigManager  # noqa: F401
from src.core.llm import get_llm_factory  # noqa: F401
from src.knowledge.manager import KnowledgeBaseManager  # noqa: F401
from src.agents.auditor import FormatAuditor  # noqa: F401
from src.agents.compliance_checker import ComplianceChecker  # noqa: F401
from src.agents.consistency_checker import ConsistencyChecker  # noqa: F401
from src.agents.fact_checker import FactChecker  # noqa: F401
from src.agents.requirement import RequirementAgent  # noqa: F401
from src.agents.review_parser import format_audit_to_review_result  # noqa: F401
from src.agents.style_checker import StyleChecker  # noqa: F401
from src.agents.template import TemplateEngine  # noqa: F401
from src.agents.writer import WriterAgent  # noqa: F401
from src.document.exporter import DocxExporter  # noqa: F401
from fastapi.responses import FileResponse  # noqa: F401

logger = logging.getLogger(__name__)
app = create_app()
class _BackwardCompatModule(types.ModuleType):
    _DEPS_ATTRS = frozenset({"_config", "_llm", "_kb", "_org_memory", "_init_lock"})
    _DEPS_ALIAS_MAP = {"_executor": "executor"}
    _MW_ATTR_MAP = {"_rate_limiter": "rate_limiter", "_metrics": "metrics"}

    def __init__(self, orig_module: types.ModuleType):
        super().__init__(orig_module.__name__)
        self.__dict__.update(orig_module.__dict__)
        self._orig_module = orig_module

    def __getattr__(self, name: str):
        if name in self._DEPS_ATTRS:
            return getattr(_deps, name)
        if name in self._DEPS_ALIAS_MAP:
            return getattr(_deps, self._DEPS_ALIAS_MAP[name])
        if name in self._MW_ATTR_MAP:
            return getattr(_mw, self._MW_ATTR_MAP[name])
        raise AttributeError(f"module 'api_server' has no attribute {name!r}")

    def __setattr__(self, name: str, value):
        if name in {"_orig_module"} or name.startswith("__"):
            super().__setattr__(name, value)
        elif name in self._DEPS_ATTRS:
            setattr(_deps, name, value)
        elif name in self._DEPS_ALIAS_MAP:
            setattr(_deps, self._DEPS_ALIAS_MAP[name], value)
        elif name in self._MW_ATTR_MAP:
            setattr(_mw, self._MW_ATTR_MAP[name], value)
        else:
            super().__setattr__(name, value)
sys.modules[__name__] = _BackwardCompatModule(sys.modules[__name__])
if __name__ == "__main__":
    import uvicorn

    startup_config = get_config()
    startup_api = startup_config.get("api", {})
    host = resolve_bind_host(
        os.environ.get("API_HOST", "0.0.0.0"),
        auth_enabled=startup_api.get("auth_enabled", True),
        api_keys=startup_api.get("api_keys", []),
        allow_insecure_bind=os.environ.get("ALLOW_INSECURE_BIND", "").lower() == "true",
    )
    uvicorn.run(
        "api_server:app",
        host=host,
        port=int(os.environ.get("API_PORT", "8000")),
        workers=int(os.environ.get("API_WORKERS", "1")),
        log_level=os.environ.get("LOG_LEVEL", "info").lower(),
    )
