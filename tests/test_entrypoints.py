from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import aiquotabar.__main__ as entrypoint


def _load_script_module():
    path = Path(__file__).resolve().parents[1] / "aiquotabar.py"
    spec = importlib.util.spec_from_file_location("aiquotabar_script", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_main_dispatches_history(monkeypatch):
    called = {"history": False}
    fake_history = types.ModuleType("aiquotabar.history")
    fake_history.cli_history = lambda: called.__setitem__("history", True)

    monkeypatch.setattr(entrypoint.sys, "argv", ["aiquotabar", "--history"])
    monkeypatch.setitem(sys.modules, "aiquotabar.history", fake_history)

    entrypoint.main()

    assert called["history"] is True


def test_main_dispatches_ui_run(monkeypatch):
    called = {"run": False}

    class FakeAIQuotaBarApp:
        def run(self):
            called["run"] = True

    fake_ui = types.ModuleType("aiquotabar.ui")
    fake_ui.AIQuotaBarApp = FakeAIQuotaBarApp

    monkeypatch.setattr(entrypoint.sys, "argv", ["aiquotabar"])
    monkeypatch.setitem(sys.modules, "aiquotabar.ui", fake_ui)

    entrypoint.main()

    assert called["run"] is True


def test_aiquotabar_script_reexports_main():
    script_module = _load_script_module()
    assert script_module.main is entrypoint.main
