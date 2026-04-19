from __future__ import annotations

import runpy
import sys
import types


def test_app_launcher_dispatches_main(monkeypatch):
    called = {"main": False}

    fake_entrypoint = types.ModuleType("aiquotabar.__main__")
    fake_entrypoint.main = lambda: called.__setitem__("main", True)

    monkeypatch.setitem(sys.modules, "aiquotabar.__main__", fake_entrypoint)

    runpy.run_path("app.py", run_name="__main__")

    assert called["main"] is True
