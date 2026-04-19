from __future__ import annotations

import json
import sys
import types

import aiquotabar.__main__ as entrypoint


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


def test_main_dispatches_cookie_detection_cli(monkeypatch):
    called = {"provider_key": None}

    fake_providers = types.ModuleType("aiquotabar.providers")
    fake_providers.run_cookie_detection_cli = (
        lambda provider_key: called.__setitem__("provider_key", provider_key) or 7
    )

    monkeypatch.setattr(entrypoint.sys, "argv", ["aiquotabar", "--detect-cookies", "cookie_str"])
    monkeypatch.setitem(sys.modules, "aiquotabar.providers", fake_providers)

    try:
        entrypoint.main()
    except SystemExit as exc:
        assert exc.code == 7
    else:
        raise AssertionError("main() did not exit for --detect-cookies")

    assert called["provider_key"] == "cookie_str"


def test_main_detect_cookies_requires_provider_key(monkeypatch, capsys):
    monkeypatch.setattr(entrypoint.sys, "argv", ["aiquotabar", "--detect-cookies"])

    try:
        entrypoint.main()
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("main() did not exit for invalid --detect-cookies usage")

    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["status"] == "error"
    assert payload["error_type"] == "UsageError"
