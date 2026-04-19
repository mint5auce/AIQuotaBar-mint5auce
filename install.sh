#!/bin/bash
# AI Quota Bar — one-line installer
# Usage: curl -fsSL https://raw.githubusercontent.com/yagcioglutoprak/AIQuotaBar/main/install.sh | bash

set -e

REPO="https://github.com/yagcioglutoprak/AIQuotaBar"
INSTALL_DIR="$HOME/.ai-quota-bar"
VENV_DIR="$INSTALL_DIR/.venv"
PLIST="$HOME/Library/LaunchAgents/com.aiquotabar.plist"

echo ""
echo "  AI Quota Bar — installer"
echo "  ──────────────────────"
echo ""

# ── 1. Python 3.10+ ───────────────────────────────────────────────────────────
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
  echo "  ✗  Python 3.10+ not found."
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

# ── 3. Clone / update ─────────────────────────────────────────────────────────
if [ -d "$INSTALL_DIR/.git" ]; then
  echo "  ↻  Updating existing install…"
  git -C "$INSTALL_DIR" fetch --quiet origin
  git -C "$INSTALL_DIR" stash --quiet 2>/dev/null || true
  git -C "$INSTALL_DIR" checkout main --quiet 2>/dev/null || true
  git -C "$INSTALL_DIR" merge --ff-only origin/main --quiet
else
  echo "  ↓  Cloning repository…"
  git clone --quiet --depth 1 "$REPO" "$INSTALL_DIR"
fi

# ── 4. Virtual environment + dependencies ─────────────────────────────────────
echo "  ↓  Setting up virtual environment…"
if [ ! -d "$VENV_DIR" ]; then
  "$BASE_PYTHON" -m venv "$VENV_DIR"
fi
PYTHON="$VENV_DIR/bin/python3"
echo "  ↓  Installing Python dependencies…"
"$PYTHON" -m pip install --quiet --upgrade pip
"$PYTHON" -m pip install --quiet --upgrade -r "$INSTALL_DIR/requirements.txt"
echo "  ✓  Dependencies installed"

# ── 5. LaunchAgent (run at login) ─────────────────────────────────────────────
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.aiquotabar</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$INSTALL_DIR/aiquotabar.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>$HOME/.aiquotabar.log</string>
    <key>StandardErrorPath</key>
    <string>$HOME/.aiquotabar.log</string>
</dict>
</plist>
PLIST_EOF

launchctl bootout gui/$(id -u) "$PLIST" 2>/dev/null || true
sleep 1
launchctl bootstrap gui/$(id -u) "$PLIST"
echo "  ✓  Added to Login Items (runs at every login)"

# ── 6. Launch now ─────────────────────────────────────────────────────────────
pkill -f "$INSTALL_DIR/aiquotabar.py" 2>/dev/null || true
sleep 1
"$PYTHON" "$INSTALL_DIR/aiquotabar.py" &>/dev/null &
echo "  ✓  Launched!"
echo ""
echo "  Look for the ◆ icon in your menu bar."
echo "  It will auto-detect your Claude session from your browser."
echo ""
echo "  ─────────────────────────────────────────────────"
echo "  ⭐ If you find this useful, star the repo!"
echo "     https://github.com/yagcioglutoprak/AIQuotaBar"
echo "  ─────────────────────────────────────────────────"
echo ""
