"""Tests for scripts/check_acl_state.py."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parent.parent / "scripts" / "check_acl_state.py"
_spec = importlib.util.spec_from_file_location("check_acl_state", _MODULE_PATH)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

parse_deny_aces = _mod.parse_deny_aces
is_foreign_sid = _mod.is_foreign_sid
check = _mod.check


_SAMPLE_DENIED_OUTPUT = """\
.git S-1-5-21-541253457-2268935619-321007557-692795393:(DENY)(W,D,Rc,DC)
     S-1-5-21-541253457-2268935619-321007557-692795393:(OI)(CI)(IO)(DENY)(W,D,Rc,GW,DC)
     S-1-5-21-2402424919-1912629089-3910208045-2312607390:(I)(OI)(CI)(RX,W)
     BUILTIN\\Administrators:(I)(F)
     NT AUTHORITY\\SYSTEM:(I)(F)
"""

_SAMPLE_CLEAN_OUTPUT = """\
.git BUILTIN\\Administrators:(I)(F)
     BUILTIN\\Administrators:(I)(OI)(CI)(IO)(F)
     NT AUTHORITY\\SYSTEM:(I)(F)
     NT AUTHORITY\\Authenticated Users:(I)(M)
"""


def test_parse_deny_aces_pulls_sid_and_perms() -> None:
    aces = parse_deny_aces(_SAMPLE_DENIED_OUTPUT)
    assert len(aces) == 2
    sid, perms = aces[0]
    assert sid.startswith("S-1-5-21-541253457")
    assert "DC" in perms


def test_parse_deny_aces_empty_when_clean() -> None:
    assert parse_deny_aces(_SAMPLE_CLEAN_OUTPUT) == []


def test_parse_deny_aces_handles_garbled_lines() -> None:
    out = "garbage line\n\n# comment\nS-malformed:(DENY)\n"
    assert parse_deny_aces(out) == []


def test_is_foreign_sid_recognises_local_machine_sid() -> None:
    # local machine SID prefix is in the trusted list
    assert not is_foreign_sid("S-1-5-21-2402424919-1912629089-3910208045-2312607390")


def test_is_foreign_sid_flags_unknown_domain_sid() -> None:
    assert is_foreign_sid("S-1-5-21-541253457-2268935619-321007557-692795393")


def test_check_returns_clean_for_missing_target(tmp_path) -> None:
    nonexistent = tmp_path / "no-such-dir"
    report = check(nonexistent)
    assert report["status"] == "clean"
    assert report["recommended_mode"] == "full"


def test_check_handles_real_dir(tmp_path, monkeypatch) -> None:
    """When icacls returns clean output, status should be 'clean'."""
    monkeypatch.setattr(_mod, "_run_icacls", lambda _: _SAMPLE_CLEAN_OUTPUT)
    report = check(tmp_path)
    assert report["status"] == "clean"
    assert report["foreign_sids"] == []
    assert report["recommended_mode"] == "full"


def test_check_handles_denied_dir(tmp_path, monkeypatch) -> None:
    """When icacls returns DENY ACEs from foreign SIDs, recommend read-only."""
    monkeypatch.setattr(_mod, "_run_icacls", lambda _: _SAMPLE_DENIED_OUTPUT)
    report = check(tmp_path)
    assert report["status"] == "denied"
    assert report["deny_count"] == 2
    assert any(sid.startswith("S-1-5-21-541253457") for sid in report["foreign_sids"])
    assert report["recommended_mode"] == "read-only"
