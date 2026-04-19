from __future__ import annotations

"""Runtime build/version helpers for AI Quota Bar."""

import os
import plistlib
import subprocess
import sys
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[1]
_PLIST_BUILD_KEY = "AIQuotaBarBuildVersion"


def _repo_root() -> Path:
    return _REPO_ROOT


def _git_describe(repo_root: Path | None = None) -> str | None:
    root = repo_root or _repo_root()
    if not (root / ".git").exists():
        return None

    try:
        result = subprocess.run(
            ["git", "describe", "--always", "--dirty", "--tags"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, OSError):
        return None

    version = result.stdout.strip()
    if not version:
        return None
    if version.endswith("-dirty") or not _git_worktree_dirty(root):
        return version
    return f"{version}-dirty"


def _git_worktree_dirty(repo_root: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=normal"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, OSError):
        return False

    return bool(result.stdout.strip())


def _bundle_info_plist_path() -> Path | None:
    resource_path = os.environ.get("RESOURCEPATH")
    if resource_path:
        plist_path = Path(resource_path).resolve().parent / "Info.plist"
        if plist_path.exists():
            return plist_path

    exe_path = Path(sys.executable).resolve()
    if exe_path.parent.name == "MacOS" and exe_path.parent.parent.name == "Contents":
        plist_path = exe_path.parent.parent / "Info.plist"
        if plist_path.exists():
            return plist_path

    return None


def _bundle_build_version(plist_path: Path | None = None) -> str | None:
    target = plist_path or _bundle_info_plist_path()
    if target is None:
        return None

    try:
        with target.open("rb") as handle:
            info = plistlib.load(handle)
    except (OSError, plistlib.InvalidFileException, ValueError):
        return None

    version = info.get(_PLIST_BUILD_KEY)
    if not isinstance(version, str):
        return None

    version = version.strip()
    return version or None


def get_display_version() -> str:
    return _git_describe() or _bundle_build_version() or "unknown"
