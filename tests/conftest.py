from __future__ import annotations

import importlib
import os
import sys
import tempfile
from pathlib import Path

import pytest


_TEST_HOME = tempfile.mkdtemp(prefix="aiquotabar-pytest-home-")
os.environ["HOME"] = _TEST_HOME
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def reload_module():
    def _reload(module):
        return importlib.reload(module)

    return _reload


@pytest.fixture(autouse=True)
def isolate_app_state(tmp_path, monkeypatch):
    import aiquotabar.config as config
    import aiquotabar.history as history
    import aiquotabar.providers as providers
    import aiquotabar.secrets as secrets

    support_dir = tmp_path / "Library" / "Application Support" / "AIQuotaBar"
    support_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(config, "CONFIG_FILE", str(tmp_path / "config.json"))
    monkeypatch.setattr(config, "LOG_FILE", str(tmp_path / "claude_bar.log"))
    monkeypatch.setattr(history, "HISTORY_FILE", str(tmp_path / "history.json"))
    monkeypatch.setattr(history, "HISTORY_DB", str(support_dir / "history.db"))

    secrets._runtime_cache.clear()
    providers._keychain_warned = False

    yield {
        "config_file": config.CONFIG_FILE,
        "history_file": history.HISTORY_FILE,
        "history_db": history.HISTORY_DB,
        "log_file": config.LOG_FILE,
    }

    secrets._runtime_cache.clear()
