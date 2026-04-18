from __future__ import annotations

import sys
import types

import aiquotabar.__main__ as entrypoint
import claude_bar


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

    class FakeClaudeBar:
        def run(self):
            called["run"] = True

    fake_ui = types.ModuleType("aiquotabar.ui")
    fake_ui.ClaudeBar = FakeClaudeBar

    monkeypatch.setattr(entrypoint.sys, "argv", ["aiquotabar"])
    monkeypatch.setitem(sys.modules, "aiquotabar.ui", fake_ui)

    entrypoint.main()

    assert called["run"] is True


def test_claude_bar_shim_reexports_main():
    assert claude_bar.main is entrypoint.main
