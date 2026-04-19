#!/bin/bash
# AI Quota Bar — one-line installer
# Usage: curl -fsSL https://raw.githubusercontent.com/mint5auce/AIQuotaBar-mint5auce/main/install.sh | bash
#
# Builds a real macOS .app bundle (via py2app) and installs it to /Applications,
# so the app appears as "AIQuotaBar" in the menu bar and System Settings —
# not as a generic "python3" background process.

set -e

REPO="https://github.com/mint5auce/AIQuotaBar-mint5auce"
SRC_DIR="$HOME/.ai-quota-bar"
VENV_DIR="$SRC_DIR/.venv"
APP_NAME="AIQuotaBar.app"
LEGACY_PLIST="$HOME/Library/LaunchAgents/com.aiquotabar.plist"

echo ""
echo "  AI Quota Bar — installer"
echo "  ──────────────────────"
echo ""

# ── 1. Python 3.10+ (build dep) ───────────────────────────────────────────────
BASE_PYTHON=""
for candidate in python3 python3.13 python3.12 python3.11 python3.10; do
  if command -v "$candidate" &>/dev/null; then
    VER=$("$candidate" -c 'import sys; print(sys.version_info >= (3,10))' 2>/dev/null)
    if [ "$VER" = "True" ]; then
      BASE_PYTHON="$candidate"
      break
    fi
  fi
done

if [ -z "$BASE_PYTHON" ]; then
  echo "  ✗  Python 3.10+ not found (required to build the app bundle)."
  echo "     Install it from https://www.python.org/downloads/ and re-run."
  exit 1
fi
echo "  ✓  Python: $($BASE_PYTHON --version)"

# ── 2. Git check ──────────────────────────────────────────────────────────────
if ! command -v git &>/dev/null; then
  echo "  ✗  Git not found. Install Xcode Command Line Tools first:"
  echo "     xcode-select --install"
  exit 1
fi

# ── 3. Clone / update source ──────────────────────────────────────────────────
if [ -d "$SRC_DIR/.git" ]; then
  echo "  ↻  Updating existing source…"
  git -C "$SRC_DIR" fetch --quiet origin
  git -C "$SRC_DIR" stash --quiet 2>/dev/null || true
  git -C "$SRC_DIR" checkout main --quiet 2>/dev/null || true
  git -C "$SRC_DIR" merge --ff-only origin/main --quiet
else
  echo "  ↓  Cloning repository…"
  git clone --quiet --depth 1 "$REPO" "$SRC_DIR"
fi

# ── 4. Build venv + install build deps ────────────────────────────────────────
echo "  ↓  Setting up build environment…"
if [ ! -d "$VENV_DIR" ]; then
  "$BASE_PYTHON" -m venv "$VENV_DIR"
fi
PYTHON="$VENV_DIR/bin/python3"
"$PYTHON" -m pip install --quiet --upgrade pip
echo "  ↓  Installing build dependencies (this takes a minute)…"
"$PYTHON" -m pip install --quiet --upgrade -r "$SRC_DIR/requirements.txt"

# ── 5. Build the .app bundle ──────────────────────────────────────────────────
echo "  ↓  Building $APP_NAME…"
rm -rf "$SRC_DIR/build" "$SRC_DIR/dist"
(cd "$SRC_DIR" && "$PYTHON" setup.py py2app --quiet 2>&1 | tail -5)
BUILT_APP="$SRC_DIR/dist/$APP_NAME"
if [ ! -d "$BUILT_APP" ]; then
  echo "  ✗  Build failed: $BUILT_APP not found"
  exit 1
fi
echo "  ✓  Built $APP_NAME"

# ── 6. Install to /Applications (or ~/Applications fallback) ──────────────────
TARGET_DIR="/Applications"
if ! [ -w "$TARGET_DIR" ]; then
  TARGET_DIR="$HOME/Applications"
  mkdir -p "$TARGET_DIR"
fi
TARGET_APP="$TARGET_DIR/$APP_NAME"

# Stop any running copy before overwriting
osascript -e 'tell application "AIQuotaBar" to quit' 2>/dev/null || true
sleep 1

rm -rf "$TARGET_APP"
cp -R "$BUILT_APP" "$TARGET_APP"

# Ad-hoc codesign — silences "unidentified developer" Gatekeeper prompt
# for the user who built the app on this machine. Does NOT make the bundle
# distributable to other machines (that needs a real Developer ID).
codesign --force --deep --sign - "$TARGET_APP" 2>/dev/null || true
echo "  ✓  Installed to $TARGET_APP"

# ── 7. Migrate from legacy LaunchAgent ────────────────────────────────────────
if [ -f "$LEGACY_PLIST" ]; then
  echo "  ↻  Removing legacy LaunchAgent (replaced by Login Items)…"
  launchctl bootout "gui/$(id -u)" "$LEGACY_PLIST" 2>/dev/null || true
  launchctl unload "$LEGACY_PLIST" 2>/dev/null || true
  rm -f "$LEGACY_PLIST"
fi

# ── 8. Launch ─────────────────────────────────────────────────────────────────
open "$TARGET_APP"
echo "  ✓  Launched!"
echo ""
echo "  Look for the ◆ icon in your menu bar."
echo "  It will auto-detect your Claude session from your browser."
echo ""
echo "  To run at login: open the menu and toggle \"Start at Login\"."
echo "  Manage in System Settings → General → Login Items."
echo ""
echo "  ─────────────────────────────────────────────────"
echo "  ⭐ If you find this useful, star the repo!"
echo "     https://github.com/mint5auce/AIQuotaBar-mint5auce"
echo "  ─────────────────────────────────────────────────"
echo ""
