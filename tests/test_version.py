from __future__ import annotations

import plistlib
import subprocess

import aiquotabar.version as version


def test_get_display_version_prefers_git_describe(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(version, "_repo_root", lambda: tmp_path)

    def fake_run(cmd, cwd, capture_output, text, check):
        assert cwd == tmp_path
        assert capture_output is True
        assert text is True
        assert check is True
        if cmd == ["git", "describe", "--always", "--dirty", "--tags"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="v1.7.0-2-gbb15f3e\n")
        if cmd == ["git", "status", "--porcelain", "--untracked-files=normal"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="")
        raise AssertionError(cmd)

    monkeypatch.setattr(version.subprocess, "run", fake_run)
    monkeypatch.setattr(version, "_bundle_build_version", lambda plist_path=None: "bundle-version")

    assert version.get_display_version() == "v1.7.0-2-gbb15f3e"


def test_get_display_version_marks_dirty_when_git_status_has_changes(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(version, "_repo_root", lambda: tmp_path)

    def fake_run(cmd, cwd, capture_output, text, check):
        assert cwd == tmp_path
        assert capture_output is True
        assert text is True
        assert check is True
        if cmd == ["git", "describe", "--always", "--dirty", "--tags"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="v1.7.0-2-gbb15f3e\n")
        if cmd == ["git", "status", "--porcelain", "--untracked-files=normal"]:
            return subprocess.CompletedProcess(cmd, 0, stdout=" M aiquotabar/ui.py\n")
        raise AssertionError(cmd)

    monkeypatch.setattr(version.subprocess, "run", fake_run)

    assert version.get_display_version() == "v1.7.0-2-gbb15f3e-dirty"


def test_get_display_version_accepts_exact_release_tag_without_suffix(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(version, "_repo_root", lambda: tmp_path)

    def fake_run(cmd, cwd, capture_output, text, check):
        assert cwd == tmp_path
        assert capture_output is True
        assert text is True
        assert check is True
        if cmd == ["git", "describe", "--always", "--dirty", "--tags"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="v1.7.0\n")
        if cmd == ["git", "status", "--porcelain", "--untracked-files=normal"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="")
        raise AssertionError(cmd)

    monkeypatch.setattr(version.subprocess, "run", fake_run)

    assert version.get_display_version() == "v1.7.0"


def test_get_display_version_falls_back_to_bundle_plist(tmp_path, monkeypatch):
    plist_path = tmp_path / "Info.plist"
    plist_path.write_bytes(plistlib.dumps({"AIQuotaBarBuildVersion": "bundle-snapshot"}))

    monkeypatch.setattr(version, "_repo_root", lambda: tmp_path)
    monkeypatch.setattr(version, "_bundle_info_plist_path", lambda: plist_path)

    assert version.get_display_version() == "bundle-snapshot"


def test_get_display_version_returns_unknown_without_git_or_bundle(tmp_path, monkeypatch):
    monkeypatch.setattr(version, "_repo_root", lambda: tmp_path)
    monkeypatch.setattr(version, "_bundle_info_plist_path", lambda: None)

    assert version.get_display_version() == "unknown"
