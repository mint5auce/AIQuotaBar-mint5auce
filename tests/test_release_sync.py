from __future__ import annotations

import re
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_release_version_in_setup_matches_top_changelog_release():
    changelog = _read("CHANGELOG.md")
    setup_py = _read("setup.py")

    changelog_match = re.search(r"^## (v\d+\.\d+\.\d+) - ", changelog, re.MULTILINE)
    assert changelog_match, "Expected a versioned release heading at the top of CHANGELOG.md"

    short_match = re.search(r'"CFBundleShortVersionString": "(\d+\.\d+\.\d+)"', setup_py)
    bundle_match = re.search(r'"CFBundleVersion": "(\d+\.\d+\.\d+)"', setup_py)
    assert short_match, "Expected CFBundleShortVersionString in setup.py"
    assert bundle_match, "Expected CFBundleVersion in setup.py"

    changelog_version = changelog_match.group(1).removeprefix("v")
    assert short_match.group(1) == changelog_version
    assert bundle_match.group(1) == changelog_version


def test_latest_git_release_tag_matches_top_changelog_release():
    changelog = _read("CHANGELOG.md")
    changelog_match = re.search(r"^## (v\d+\.\d+\.\d+) - ", changelog, re.MULTILINE)
    assert changelog_match, "Expected a versioned release heading at the top of CHANGELOG.md"

    latest_tag = subprocess.check_output(
        ["git", "tag", "--list", "v*", "--sort=-version:refname"],
        cwd=REPO_ROOT,
        text=True,
    ).splitlines()[0]

    assert latest_tag == changelog_match.group(1)
