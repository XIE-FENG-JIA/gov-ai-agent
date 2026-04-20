import json
from pathlib import Path

from src.cli import profile_cmd, wizard_cmd, workflow_cmd
from src.cli.utils import JSONStore, configure_state_dir, resolve_state_read_path, set_state_dir


def test_json_store_uses_user_state_dir_in_repo_root(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    (repo_root / "program.md").write_text("# test\n", encoding="utf-8")

    home_dir = tmp_path / "home"
    home_dir.mkdir()

    monkeypatch.setenv("USERPROFILE", str(home_dir))
    monkeypatch.delenv("GOV_AI_STATE_DIR", raising=False)
    monkeypatch.chdir(repo_root)

    set_state_dir(None)
    try:
        state_dir = configure_state_dir()
        store = JSONStore(".gov-ai-history.json", default=[])
        store.save([{"id": 1}])
    finally:
        set_state_dir(None)

    assert Path(state_dir) == home_dir / ".gov-ai" / "state"
    assert (home_dir / ".gov-ai" / "state" / ".gov-ai-history.json").exists()
    assert not (repo_root / ".gov-ai-history.json").exists()


def test_json_store_reads_legacy_root_file_before_state_migration(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    (repo_root / "program.md").write_text("# test\n", encoding="utf-8")
    legacy_history = repo_root / ".gov-ai-history.json"
    legacy_history.write_text(json.dumps([{"id": 1}]), encoding="utf-8")

    home_dir = tmp_path / "home"
    home_dir.mkdir()

    monkeypatch.setenv("USERPROFILE", str(home_dir))
    monkeypatch.delenv("GOV_AI_STATE_DIR", raising=False)
    monkeypatch.chdir(repo_root)

    set_state_dir(None)
    try:
        configure_state_dir()
        store = JSONStore(".gov-ai-history.json", default=[])
        assert store.load() == [{"id": 1}]

        store.save([{"id": 1}, {"id": 2}])
    finally:
        set_state_dir(None)

    state_history = home_dir / ".gov-ai" / "state" / ".gov-ai-history.json"
    assert json.loads(state_history.read_text(encoding="utf-8")) == [{"id": 1}, {"id": 2}]
    assert json.loads(legacy_history.read_text(encoding="utf-8")) == [{"id": 1}]


def test_resolve_state_read_path_falls_back_to_legacy_cwd_file(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    legacy_path = repo_root / ".gov-ai-feedback.json"
    legacy_path.write_text("[]", encoding="utf-8")

    state_dir = tmp_path / "state"
    monkeypatch.chdir(repo_root)

    resolved = resolve_state_read_path(".gov-ai-feedback.json", state_dir=str(state_dir))

    assert Path(resolved) == legacy_path


def test_workflow_dir_uses_user_state_dir_in_repo_root(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    (repo_root / "program.md").write_text("# test\n", encoding="utf-8")

    home_dir = tmp_path / "home"
    home_dir.mkdir()

    monkeypatch.setenv("USERPROFILE", str(home_dir))
    monkeypatch.delenv("GOV_AI_STATE_DIR", raising=False)
    monkeypatch.chdir(repo_root)

    set_state_dir(None)
    try:
        configure_state_dir()
        workflow_dir = Path(workflow_cmd._ensure_dir())
        workflow_path = Path(workflow_cmd._workflow_path("demo", for_write=True))
    finally:
        set_state_dir(None)

    expected_dir = home_dir / ".gov-ai" / "state" / ".gov-ai-workflows"
    assert workflow_dir == expected_dir
    assert workflow_path == expected_dir / "demo.json"
    assert not (repo_root / ".gov-ai-workflows").exists()


def test_profile_set_default_dir_uses_user_state_dir_in_repo_root(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    (repo_root / "program.md").write_text("# test\n", encoding="utf-8")

    home_dir = tmp_path / "home"
    home_dir.mkdir()

    monkeypatch.setenv("USERPROFILE", str(home_dir))
    monkeypatch.delenv("GOV_AI_STATE_DIR", raising=False)
    monkeypatch.chdir(repo_root)

    set_state_dir(None)
    try:
        configure_state_dir()
        profile_cmd.profile_set("agency", "新北市政府", ".profile")
    finally:
        set_state_dir(None)

    expected = home_dir / ".gov-ai" / "state" / ".profile" / "settings.json"
    assert json.loads(expected.read_text(encoding="utf-8")) == {"agency": "新北市政府"}
    assert not (repo_root / ".profile").exists()


def test_wizard_load_profile_reads_state_dir_in_repo_root(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    (repo_root / "program.md").write_text("# test\n", encoding="utf-8")

    home_dir = tmp_path / "home"
    state_dir = home_dir / ".gov-ai" / "state"
    state_dir.mkdir(parents=True)
    (state_dir / ".gov-ai-profile.json").write_text(
        json.dumps({"agency": "臺北市政府環保局"}, ensure_ascii=False),
        encoding="utf-8",
    )

    monkeypatch.setenv("USERPROFILE", str(home_dir))
    monkeypatch.delenv("GOV_AI_STATE_DIR", raising=False)
    monkeypatch.chdir(repo_root)

    set_state_dir(None)
    try:
        configure_state_dir()
        profile = wizard_cmd._load_profile()
    finally:
        set_state_dir(None)

    assert profile == {"agency": "臺北市政府環保局"}
