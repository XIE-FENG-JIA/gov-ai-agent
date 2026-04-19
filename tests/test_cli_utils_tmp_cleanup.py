import os
import time

from src.cli.utils import atomic_text_write, cleanup_orphan_tmps


def test_atomic_write_cleans_only_stale_atomic_tmp_files(tmp_path):
    stale_json = tmp_path / ".json_stale.tmp"
    stale_txt = tmp_path / ".txt_stale.tmp"
    stale_yaml = tmp_path / ".yaml_stale.tmp"
    fresh_txt = tmp_path / ".txt_fresh.tmp"
    unrelated = tmp_path / "notes.tmp"

    for path in (stale_json, stale_txt, stale_yaml, fresh_txt, unrelated):
        path.write_text("tmp", encoding="utf-8")

    stale_time = time.time() - 7200
    fresh_time = time.time() - 300
    os.utime(stale_json, (stale_time, stale_time))
    os.utime(stale_txt, (stale_time, stale_time))
    os.utime(stale_yaml, (stale_time, stale_time))
    os.utime(fresh_txt, (fresh_time, fresh_time))
    os.utime(unrelated, (stale_time, stale_time))

    atomic_text_write(str(tmp_path / "output.txt"), "ok")

    assert not stale_json.exists()
    assert not stale_txt.exists()
    assert not stale_yaml.exists()
    assert fresh_txt.exists()
    assert unrelated.exists()


def test_atomic_write_still_creates_target_after_cleanup(tmp_path):
    stale_tmp = tmp_path / ".txt_orphan.tmp"
    stale_tmp.write_text("old", encoding="utf-8")
    stale_time = time.time() - 7200
    os.utime(stale_tmp, (stale_time, stale_time))

    target = tmp_path / "report.txt"
    atomic_text_write(str(target), "clean content")

    assert target.read_text(encoding="utf-8") == "clean content"
    assert not stale_tmp.exists()


def test_cleanup_orphan_tmps_can_remove_fresh_repo_root_orphans(tmp_path):
    fresh_json = tmp_path / ".json_fresh.tmp"
    fresh_txt = tmp_path / ".txt_fresh.tmp"
    keeper = tmp_path / "report.txt"

    fresh_json.write_text("{}", encoding="utf-8")
    fresh_txt.write_text("draft", encoding="utf-8")
    keeper.write_text("keep", encoding="utf-8")

    removed = cleanup_orphan_tmps(str(tmp_path), max_age_seconds=None)

    assert removed == 2
    assert not fresh_json.exists()
    assert not fresh_txt.exists()
    assert keeper.exists()
