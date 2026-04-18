from __future__ import annotations

import json
import logging
from pathlib import Path

import aiquotabar.config as config


def test_load_config_returns_empty_when_missing():
    assert config.load_config() == {}


def test_save_config_and_load_round_trip(isolate_app_state):
    cfg = {"refresh": 300, "notifications": {"chatgpt_warning": False}}

    config.save_config(cfg)

    assert Path(isolate_app_state["config_file"]).exists()
    assert config.load_config() == cfg


def test_load_config_moves_corrupt_file_to_backup(isolate_app_state):
    cfg_path = Path(isolate_app_state["config_file"])
    cfg_path.write_text("{not valid json", encoding="utf-8")

    assert config.load_config() == {}
    assert not cfg_path.exists()
    assert cfg_path.with_suffix(cfg_path.suffix + ".bak").exists()


def test_notif_enabled_uses_defaults_and_overrides():
    assert config.notif_enabled({}, "claude_warning") is True
    assert config.notif_enabled(
        {"notifications": {"claude_warning": False}},
        "claude_warning",
    ) is False


def test_set_notif_updates_config_and_persists(isolate_app_state):
    cfg = {}

    config.set_notif(cfg, "cursor_warning", False)

    assert cfg["notifications"]["cursor_warning"] is False
    saved = json.loads(
        Path(isolate_app_state["config_file"]).read_text(encoding="utf-8")
    )
    assert saved["notifications"]["cursor_warning"] is False


def test_purge_compromised_logs_once_deletes_old_logs_and_marks_config(
    isolate_app_state, monkeypatch
):
    root = logging.getLogger()
    first = logging.StreamHandler()
    second = logging.StreamHandler()
    root.handlers[:] = [first, second]

    log_file = Path(isolate_app_state["log_file"])
    rotated_file = Path(f"{isolate_app_state['log_file']}.1")
    log_file.write_text("sensitive", encoding="utf-8")
    rotated_file.write_text("older sensitive", encoding="utf-8")

    configure_calls = []
    save_calls = []

    def fake_configure():
        configure_calls.append(True)

    def fake_save(cfg):
        save_calls.append(dict(cfg))

    monkeypatch.setattr(config, "_configure_logging", fake_configure)
    monkeypatch.setattr(config, "save_config", fake_save)

    cfg = {}
    config.purge_compromised_logs_once(cfg)

    assert not log_file.exists()
    assert not rotated_file.exists()
    assert config.LOG_PURGE_MARKER in cfg
    assert len(configure_calls) == 1
    assert save_calls and save_calls[-1][config.LOG_PURGE_MARKER] is True
    assert first not in root.handlers
    assert second not in root.handlers

    log_file.write_text("fresh", encoding="utf-8")
    config.purge_compromised_logs_once(cfg)

    assert log_file.exists()
    assert len(configure_calls) == 1
