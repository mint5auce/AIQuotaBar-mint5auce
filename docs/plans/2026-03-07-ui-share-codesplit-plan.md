# Floating Panel + Share + Code Split — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the NSMenu dropdown with a premium floating panel, add share-to-clipboard and share-to-X, and split the 3545-line single file into clean modules.

**Architecture:** Code split first (foundation), then build the floating panel in the new `ui.py`, then add share. Each task produces a working app — no broken intermediate states.

**Tech Stack:** Python 3.10+, rumps, AppKit/PyObjC (NSPanel, NSVisualEffectView, NSBezierPath), curl_cffi, browser-cookie3. No new dependencies.

---

### Task 1: Create the package skeleton and `config.py`

**Files:**
- Create: `aiquotabar/__init__.py`
- Create: `aiquotabar/config.py`
- Modify: `aiquotabar.py` (will become shim at end, but keep working for now)

**Step 1: Create the package directory**

```bash
mkdir -p aiquotabar
```

**Step 2: Create `aiquotabar/__init__.py`**

Empty file:
```python
```

**Step 3: Create `aiquotabar/config.py`**

Extract from `aiquotabar.py` lines 40-96 (constants) and lines 500-532 (config functions):

```python
"""Configuration constants and persistence."""

import json
import os

CONFIG_FILE = os.path.expanduser("~/.aiquotabar_config.json")

REFRESH_INTERVALS = {
    "1 min":  60,
    "5 min":  300,
    "15 min": 900,
}
DEFAULT_REFRESH = 300

WARN_THRESHOLD = 80
CRIT_THRESHOLD = 95

# Notification defaults
NOTIF_DEFAULTS = {
    "claude_reset":   True,
    "chatgpt_reset":  True,
    "claude_warning": True,
    "chatgpt_warning":True,
    "claude_pacing":  True,
    "chatgpt_pacing": True,
    "copilot_pacing": True,
    "cursor_warning": True,
    "cursor_pacing":  True,
}

# Usage history
HISTORY_FILE = os.path.expanduser("~/.aiquotabar_history.json")
HISTORY_MAX_AGE = 24 * 3600
PACING_ALERT_MINUTES = 30

# SQLite history
HISTORY_DB = os.path.join(
    os.path.expanduser("~/Library/Application Support/aiquotabar"),
    "history.db",
)
SAMPLES_MAX_DAYS = 7
DAILY_MAX_DAYS = 90
LIMIT_HIT_PCT = 95
BURN_WINDOW = 30 * 60
MIN_SPAN_SECS = 5 * 60
RESET_DROP_PCT = 30
UPDATE_CHECK_INTERVAL = 4 * 3600

HISTORY_COLORS = {
    "claude": "#D97757", "chatgpt": "#74AA9C",
    "copilot": "#6E40C9", "cursor": "#00A0D1",
}

# Logging
import logging
import logging.handlers

LOG_FILE = os.path.expanduser("~/.aiquotabar.log")
_log_handler = logging.handlers.RotatingFileHandler(
    LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3,
)
_log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logging.basicConfig(handlers=[_log_handler], level=logging.DEBUG)
log = logging.getLogger("aiquotabar")


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            corrupt = CONFIG_FILE + ".bak"
            log.warning("Config file corrupt (%s), resetting. Backup at %s", e, corrupt)
            try:
                os.replace(CONFIG_FILE, corrupt)
            except OSError:
                pass
    return {}


def save_config(cfg: dict):
    tmp = CONFIG_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, CONFIG_FILE)


def notif_enabled(cfg: dict, key: str) -> bool:
    return cfg.get("notifications", {}).get(key, NOTIF_DEFAULTS.get(key, True))


def set_notif(cfg: dict, key: str, value: bool):
    cfg.setdefault("notifications", {})[key] = value
    save_config(cfg)
```

**Step 4: Verify it imports cleanly**

```bash
cd /Users/toprakyagcioglu/AIQuotaBar && python3 -c "from aiquotabar.config import load_config, save_config, log; print('OK')"
```
Expected: `OK`

**Step 5: Commit**

```bash
git add aiquotabar/__init__.py aiquotabar/config.py
git commit -m "refactor: extract config.py module from aiquotabar.py"
```

---

### Task 2: Extract `providers.py`

**Files:**
- Create: `aiquotabar/providers.py`

**Step 1: Create `aiquotabar/providers.py`**

Extract from `aiquotabar.py`:
- Lines 575-610: `LimitRow`, `UsageData`, `ProviderData` dataclasses
- Lines 612-935: All fetch functions, cookie detection, parsing
- Lines 940-972: `_fmt_reset` time helper
- Lines 976-1006: `_row`, `parse_usage`
- Lines 1113-1144: `fetch_claude_code_stats`
- Lines 2123-2214: Cookie detection (`_DETECT_SCRIPT`, `_run_cookie_detection`, `_auto_detect_*`)

Key imports to add at top:
```python
from aiquotabar.config import log, LIMIT_HIT_PCT
```

The module should export:
- `LimitRow`, `UsageData`, `ProviderData`
- `parse_cookie_string`, `fetch_raw`, `parse_usage`
- `fetch_chatgpt`, `fetch_openai`, `fetch_minimax`, `fetch_glm`, `fetch_copilot`, `fetch_cursor`
- `fetch_claude_code_stats`
- `PROVIDER_REGISTRY`, `COOKIE_PROVIDERS`
- `_auto_detect_cookies`, `_auto_detect_chatgpt_cookies`, `_auto_detect_copilot_cookies`, `_auto_detect_cursor_cookies`
- `_warn_keychain_once`
- `_fmt_reset` (needed by UI for display)

Rename private prefixes: `_CF_COOKIE_KEYS` -> `CF_COOKIE_KEYS`, `_COOKIE_PROVIDERS` -> `COOKIE_PROVIDERS` (module-level, no longer class-internal).

**Step 2: Verify imports**

```bash
python3 -c "from aiquotabar.providers import LimitRow, UsageData, ProviderData, PROVIDER_REGISTRY; print('OK')"
```
Expected: `OK`

**Step 3: Commit**

```bash
git add aiquotabar/providers.py
git commit -m "refactor: extract providers.py — all fetch functions and data models"
```

---

### Task 3: Extract `history.py`

**Files:**
- Create: `aiquotabar/history.py`

**Step 1: Create `aiquotabar/history.py`**

Extract from `aiquotabar.py`:
- Lines 104-109: `_nscolor` helper
- Lines 112-244: JSON history functions (`_load_history`, `_save_history`, `_append_history`, `_calc_burn_rate`, `_calc_eta_minutes`, `_fmt_eta`, `_sparkline`)
- Lines 247-497: SQLite history functions (`_init_history_db`, `_record_sample`, `_rollup_daily_stats`, `_get_weekly_stats`, `_get_week_limit_hits`, `_weekly_sparkline`, `_get_today_stats`, `_fetch_history_data`)
- Lines 3472-3537: `_cli_history` function

Key imports:
```python
from aiquotabar.config import (
    log, HISTORY_FILE, HISTORY_MAX_AGE, HISTORY_DB,
    SAMPLES_MAX_DAYS, DAILY_MAX_DAYS, LIMIT_HIT_PCT,
    BURN_WINDOW, MIN_SPAN_SECS, RESET_DROP_PCT, HISTORY_COLORS,
)
```

**Step 2: Verify imports**

```bash
python3 -c "from aiquotabar.history import _load_history, _calc_burn_rate, _init_history_db; print('OK')"
```
Expected: `OK`

**Step 3: Commit**

```bash
git add aiquotabar/history.py
git commit -m "refactor: extract history.py — burn rate, sparklines, SQLite tracking"
```

---

### Task 4: Extract `update.py`

**Files:**
- Create: `aiquotabar/update.py`

**Step 1: Create `aiquotabar/update.py`**

Extract from `aiquotabar.py`:
- Lines 535-572: `_check_and_apply_update`, `_restart_app`

Imports:
```python
from aiquotabar.config import log
```

**Step 2: Verify the import**

```bash
python3 -c "from aiquotabar.update import _check_and_apply_update; print('OK')"
```
Expected: `OK`

**Step 3: Commit**

```bash
git add aiquotabar/update.py
git commit -m "refactor: extract update.py"
```

---

### Task 5: Create `ui.py` — migrate existing AIQuotaBarApp class

**Files:**
- Create: `aiquotabar/ui.py`

**Step 1: Create `aiquotabar/ui.py`**

Move the remaining code from `aiquotabar.py`:
- Lines 1009-1110: Icon helpers, `_BarToggleView`
- Lines 1271-1464: Welcome window (`_show_welcome_window`)
- Lines 1467-1883: History window (`_show_history_window`)
- Lines 1886-2018: Display helpers (`_bar`, `_status_icon`, `_row_lines`, `_provider_lines`, `_mi`, `_colored_mi`, `_menu_icon`, `_section_header_mi`)
- Lines 2021-2088: Login item helpers, dialog helpers (`_ask_text`, `_clipboard_text`, `_warn_keychain_once`)
- Lines 2216-2244: `_notify`, `_show_text`
- Lines 2246-3470: `AIQuotaBarApp` class (entire)
- Lines 1886-1898: `_bar`, `_status_icon`, `_fmt_count`

Imports at top:
```python
from aiquotabar.config import (
    log, load_config, save_config, notif_enabled, set_notif,
    CONFIG_FILE, REFRESH_INTERVALS, DEFAULT_REFRESH,
    WARN_THRESHOLD, CRIT_THRESHOLD, PACING_ALERT_MINUTES,
    UPDATE_CHECK_INTERVAL, HISTORY_COLORS,
)
from aiquotabar.providers import (
    LimitRow, UsageData, ProviderData, parse_usage, fetch_raw,
    fetch_claude_code_stats, PROVIDER_REGISTRY, COOKIE_PROVIDERS,
    _auto_detect_cookies, _auto_detect_chatgpt_cookies,
    _auto_detect_copilot_cookies, _auto_detect_cursor_cookies,
)
from aiquotabar.history import (
    _load_history, _save_history, _append_history,
    _calc_burn_rate, _calc_eta_minutes, _fmt_eta, _sparkline,
    _init_history_db, _record_sample, _rollup_daily_stats,
    _get_week_limit_hits, _get_today_stats,
    _show_history_window,
)
from aiquotabar.update import _check_and_apply_update, _restart_app
```

At this point `ui.py` should contain the AIQuotaBarApp class and all UI helpers. The app should work identically to before.

**Step 2: Verify the app launches**

```bash
python3 -c "from aiquotabar.ui import AIQuotaBarApp; print('OK')"
```
Expected: `OK`

**Step 3: Commit**

```bash
git add aiquotabar/ui.py
git commit -m "refactor: extract ui.py — AIQuotaBarApp class and all UI components"
```

---

### Task 6: Wire up `__main__.py` and convert `aiquotabar.py` to shim

**Files:**
- Create: `aiquotabar/__main__.py`
- Modify: `aiquotabar.py` (replace 3545 lines with 8-line shim)

**Step 1: Create `aiquotabar/__main__.py`**

```python
"""AI Quota Bar entry point."""

import sys
from aiquotabar.history import cli_history
from aiquotabar.ui import AIQuotaBarApp


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("--history", "-H"):
        cli_history()
    else:
        AIQuotaBarApp().run()


if __name__ == "__main__":
    main()
```

**Step 2: Replace `aiquotabar.py` with a shim**

```python
#!/usr/bin/env python3
"""AI Quota Bar entry point.

The real code lives in the aiquotabar/ package.

"""
from aiquotabar.__main__ import main

if __name__ == "__main__":
    main()
```

**Step 3: Verify the app launches both ways**

```bash
python3 aiquotabar.py --history 2>/dev/null; echo "shim OK"
python3 -m aiquotabar --history 2>/dev/null; echo "package OK"
```

**Step 4: Verify install.sh still references `aiquotabar.py` correctly**

The plist in `install.sh` line 78 points to `$INSTALL_DIR/aiquotabar.py` — this still works because the shim imports from the package. No changes needed.

**Step 5: Commit**

```bash
git add aiquotabar/__main__.py aiquotabar.py
git commit -m "refactor: complete code split — aiquotabar.py is now a shim

The 3545-line single file is split into 6 modules:
  config.py, providers.py, history.py, update.py, ui.py
aiquotabar.py remains as a thin shim for backwards compatibility."
```

---

### Task 7: Build the floating panel — `_UsagePanel` class

**Files:**
- Modify: `aiquotabar/ui.py`

This is the core new feature. Replace the NSMenu with a custom NSPanel.

**Step 1: Add the `_UsagePanel` class**

Add to `ui.py` a new class that creates a borderless floating panel:

```python
from AppKit import (
    NSPanel, NSView, NSTextField, NSFont, NSColor, NSButton,
    NSVisualEffectView, NSBezierPath, NSImage, NSImageView,
    NSMakeRect, NSBackingStoreBuffered, NSTextAlignmentLeft,
    NSTextAlignmentRight, NSTextAlignmentCenter,
    NSApplication, NSScreen, NSTrackingArea,
    NSWindowStyleMaskBorderless, NSWindowStyleMaskNonactivatingPanel,
    NSFloatingWindowLevel,
)
from Foundation import NSMutableAttributedString, NSAttributedString
import Quartz
import objc


PANEL_W = 340
PAD = 16
ROW_H = 20
BAR_H = 6
SECTION_GAP = 12
HEADER_H = 40
FOOTER_H = 44


class _UsagePanel:
    """Custom floating panel that replaces the NSMenu dropdown."""

    def __init__(self, app):
        self.app = app          # reference to AIQuotaBarApp
        self._panel = None
        self._content = None    # the scrollable content view
        self._visible = False

    def toggle(self, status_item_button):
        """Show or hide the panel, anchored below the status item."""
        if self._visible:
            self.dismiss()
        else:
            self._show(status_item_button)

    def dismiss(self):
        if self._panel:
            self._panel.orderOut_(None)
        self._visible = False

    def _show(self, button):
        """Build and show the panel below the menu bar icon."""
        # Get button position in screen coordinates
        btn_frame = button.window().frame()
        x = btn_frame.origin.x
        y = btn_frame.origin.y  # bottom of menu bar

        # Build content to measure height
        content_views, total_h = self._build_content()
        panel_h = min(total_h + HEADER_H + FOOTER_H, 600)

        if self._panel:
            self._panel.orderOut_(None)

        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(x, y - panel_h, PANEL_W, panel_h),
            NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel,
            NSBackingStoreBuffered,
            False,
        )
        panel.setLevel_(NSFloatingWindowLevel)
        panel.setHasShadow_(True)
        panel.setOpaque_(False)
        panel.setBackgroundColor_(NSColor.clearColor())

        # Vibrancy background
        cv = panel.contentView()
        cv.setWantsLayer_(True)
        cv.layer().setCornerRadius_(12)
        cv.layer().setMasksToBounds_(True)

        blur = NSVisualEffectView.alloc().initWithFrame_(cv.bounds())
        blur.setAutoresizingMask_(18)  # flexible width + height
        blur.setBlendingMode_(0)  # behindWindow
        blur.setMaterial_(3)  # dark
        blur.setState_(1)  # active
        cv.addSubview_(blur)

        # Add header, content views, footer to blur
        self._add_header(blur, PANEL_W, panel_h)
        # ... add provider sections ...
        self._add_footer(blur, PANEL_W, panel_h)

        for view, vy in content_views:
            view.setFrameOrigin_((PAD, panel_h - HEADER_H - vy - view.frame().size.height))
            blur.addSubview_(view)

        panel.makeKeyAndOrderFront_(None)
        self._panel = panel
        self._visible = True

    def _build_content(self):
        """Build all provider section views. Returns (views_with_y, total_height)."""
        views = []
        y = 0
        app = self.app
        data = app._last_data

        # Claude section
        if data and any([data.session, data.weekly_all, data.weekly_sonnet]):
            section, sh = self._provider_section(
                "Claude", "#D97757",
                rows=[r for r in [data.session, data.weekly_all, data.weekly_sonnet] if r],
                history=app._history, history_db=app._history_db,
            )
            views.append((section, y))
            y += sh + SECTION_GAP

        # ChatGPT, Copilot, Cursor from provider_data
        for pd in app._provider_data:
            if pd.name in ("ChatGPT", "Copilot", "Cursor"):
                color = HISTORY_COLORS.get(pd.name.lower(), "#AAAAAA")
                limit_rows = getattr(pd, "_rows", None) or []
                section, sh = self._provider_section(
                    pd.name, color,
                    rows=limit_rows,
                    provider_data=pd,
                    history=app._history, history_db=app._history_db,
                )
                views.append((section, y))
                y += sh + SECTION_GAP

        return views, y

    def _provider_section(self, name, color_hex, rows=None, provider_data=None,
                          history=None, history_db=None):
        """Build an NSView for one provider section. Returns (view, height)."""
        # Implementation: colored dot + name label + progress bar rows
        # Each row: label, rounded-rect progress bar (track + fill), pct label, reset time
        # Below rows: ETA line + sparkline if available
        ...  # detailed implementation in the actual task

    def _progress_bar(self, parent, x, y, w, pct, color_hex):
        """Draw a real rounded-rect progress bar using NSView layers."""
        track = NSView.alloc().initWithFrame_(NSMakeRect(x, y, w, BAR_H))
        track.setWantsLayer_(True)
        track.layer().setCornerRadius_(BAR_H / 2)
        track.layer().setBackgroundColor_(
            Quartz.CGColorCreateGenericRGB(0.15, 0.15, 0.2, 1.0)
        )
        parent.addSubview_(track)

        if pct > 0:
            fill_w = max(BAR_H, w * pct / 100)  # min width = corner radius
            fill = NSView.alloc().initWithFrame_(NSMakeRect(x, y, fill_w, BAR_H))
            fill.setWantsLayer_(True)
            fill.layer().setCornerRadius_(BAR_H / 2)
            h = color_hex.lstrip("#")
            r, g, b = int(h[0:2], 16)/255, int(h[2:4], 16)/255, int(h[4:6], 16)/255
            fill.layer().setBackgroundColor_(
                Quartz.CGColorCreateGenericRGB(r, g, b, 1.0)
            )
            parent.addSubview_(fill)

    def _add_header(self, parent, w, panel_h):
        """Title bar with 'AI Quota Bar' + share + gear buttons."""
        ...

    def _add_footer(self, parent, w, panel_h):
        """'Updated HH:MM' + Refresh button."""
        ...
```

**Step 2: Wire the panel into AIQuotaBarApp**

In `AIQuotaBarApp.__init__`, create the panel:
```python
self._panel = _UsagePanel(self)
```

Override the status item click to toggle the panel instead of showing the menu. The key technique: set `rumps.App.menu` to an empty menu and intercept the NSStatusItem button click:

```python
# In __init__, after super().__init__:
self._nsapp = None  # will be set when run loop starts

# After the app starts, hook into the NSStatusItem button:
def _deferred_hook(self, _timer):
    _timer.stop()
    try:
        btn = self._nsapp.nsstatusitem.button()
        btn.setAction_(b"statusItemClicked:")
        btn.setTarget_(self._click_handler)
    except Exception:
        log.debug("Failed to hook status item button", exc_info=True)
```

Create an ObjC class to handle the click:
```python
from AppKit import NSObject
import objc

class _ClickHandler(NSObject):
    def initWithApp_(self, app):
        self = objc.super(_ClickHandler, self).init()
        self._app = app
        return self

    def statusItemClicked_(self, sender):
        self._app._panel.toggle(sender)
```

**Step 3: Remove the old `_rebuild_menu` method**

The old menu-building code (`_rebuild_menu`) is no longer needed. Replace it with a stub that sets an empty menu (rumps requires one):
```python
def _rebuild_menu(self, data):
    self.menu.clear()
    self.menu = [rumps.MenuItem("Quit", callback=rumps.quit_application)]
```

The full content display now happens in `_UsagePanel._build_content()`.

**Step 4: Update `_apply` to refresh the panel**

```python
def _apply(self, data):
    # ... existing title logic stays ...
    if self._panel._visible:
        self._panel.refresh()  # rebuild content in-place
```

**Step 5: Test manually**

```bash
pkill -f aiquotabar.py; sleep 1; python3 aiquotabar.py &
```

Click the menu bar icon. The floating panel should appear with vibrancy blur, real progress bars, and brand colors. Click outside to dismiss.

**Step 6: Commit**

```bash
git add aiquotabar/ui.py
git commit -m "feat: floating panel UI — replaces NSMenu with premium NSPanel

Custom borderless panel with vibrancy blur, real rounded-rect progress
bars, brand-colored provider sections, and auto-sizing layout."
```

---

### Task 8: Implement the settings popover (gear icon)

**Files:**
- Modify: `aiquotabar/ui.py`

**Step 1: Add settings popover**

The gear icon in the panel header opens a popover (or secondary panel) containing:
- Refresh interval (1/5/15 min radio buttons)
- Notification toggles
- Status bar provider toggles
- API provider management
- Auto-detect from Browser
- Set Session Cookie...
- Launch at Login toggle
- Show Raw API Data
- Quit

Implement as a second `NSPanel` that appears next to the main panel, or as an `NSPopover` attached to the gear button.

```python
class _SettingsPopover:
    def __init__(self, app):
        self.app = app
        self._popover = None

    def show(self, relative_to_view):
        """Build and show settings popover."""
        # Build NSPopover with content view containing all settings
        ...

    def _build_content(self):
        """Vertical stack of settings groups."""
        # Refresh interval group
        # Notification toggles group
        # Status bar providers group
        # API providers group
        # Actions group (auto-detect, set cookie, raw data)
        # Footer (launch at login, quit)
        ...
```

**Step 2: Wire gear button in panel header to settings popover**

In `_UsagePanel._add_header`, the gear button's action calls `self.app._settings.show(button)`.

**Step 3: Test manually**

Click gear icon. Settings popover appears. Toggle a notification. Change refresh interval. All should persist to config.

**Step 4: Commit**

```bash
git add aiquotabar/ui.py
git commit -m "feat: settings popover — all settings accessible from gear icon"
```

---

### Task 9: Implement share feature

**Files:**
- Modify: `aiquotabar/ui.py`

**Step 1: Add share popover with two actions**

The `[share]` button in the panel header shows a small popover with two rows:
- "Copy Image" — renders panel to PNG, copies to clipboard
- "Share on X" — opens pre-filled tweet URL

```python
class _SharePopover:
    def __init__(self, app):
        self.app = app

    def show(self, relative_to_view):
        """Show 2-item share menu."""
        ...

    def copy_image(self):
        """Render the panel content as PNG and copy to clipboard."""
        from AppKit import NSBitmapImageRep, NSPasteboard, NSPNGFileType
        panel = self.app._panel._panel
        if not panel:
            return

        view = panel.contentView()
        # Capture the view as a bitmap
        view.lockFocus()
        rep = NSBitmapImageRep.alloc().initWithFocusedViewRect_(view.bounds())
        view.unlockFocus()

        # Add watermark text at bottom
        # ... draw "AI Quota Bar - github.com/yagcioglutoprak/AIQuotaBar" ...

        png_data = rep.representationUsingType_properties_(NSPNGFileType, {})
        pb = NSPasteboard.generalPasteboard()
        pb.clearContents()
        pb.setData_forType_(png_data, "public.png")

        # Flash "Copied" confirmation on the share button
        ...

    def share_on_x(self):
        """Open X/Twitter with pre-filled usage stats."""
        import subprocess
        import urllib.parse

        parts = []
        data = self.app._last_data
        if data and data.session:
            parts.append(f"Claude {data.session.pct}%")
        for pd in self.app._provider_data:
            if pd.name == "ChatGPT" and not pd.error:
                rows = getattr(pd, "_rows", None) or []
                if rows:
                    worst = max(r.pct for r in rows)
                    parts.append(f"ChatGPT {worst}%")
            elif pd.name == "Copilot" and not pd.error and pd.pct is not None:
                parts.append(f"Copilot {pd.pct}%")
            elif pd.name == "Cursor" and not pd.error:
                rows = getattr(pd, "_rows", None) or []
                if rows:
                    worst = max(r.pct for r in rows)
                    parts.append(f"Cursor {worst}%")

        stats = " / ".join(parts) if parts else "my AI usage"
        text = f"{stats} -- tracking with AI Quota Bar"
        url = (
            "https://x.com/intent/post?text="
            + urllib.parse.quote(text)
            + "&url="
            + urllib.parse.quote("https://github.com/yagcioglutoprak/AIQuotaBar")
        )
        subprocess.Popen(["open", url])
```

**Step 2: Wire share button in panel header**

In `_UsagePanel._add_header`, the share button's action calls `self.app._share.show(button)`.

**Step 3: Test both share actions manually**

- Click share -> Copy Image -> open Preview -> Cmd+N (new from clipboard). Should see the panel as a PNG with watermark.
- Click share -> Share on X -> browser opens with pre-filled tweet.

**Step 4: Commit**

```bash
git add aiquotabar/ui.py
git commit -m "feat: share — copy panel as image or post to X with usage stats"
```

---

### Task 10: Polish and cleanup

**Files:**
- Modify: `aiquotabar/ui.py`
- Modify: `aiquotabar.py` (ensure shim is minimal)

**Step 1: Panel dismiss on click-outside and Esc**

```python
# In _UsagePanel, make the panel resign key on outside click:
panel.setBecomesKeyOnlyIfNeeded_(True)

# Override cancelOperation: on the panel to dismiss on Esc
class _DismissPanel(NSPanel):
    def cancelOperation_(self, sender):
        self.orderOut_(None)
        # notify _UsagePanel to set _visible = False

    def resignKeyWindow(self):
        objc.super(_DismissPanel, self).resignKeyWindow()
        self.orderOut_(None)
```

**Step 2: Panel animation**

Add a subtle fade-in when the panel appears:
```python
panel.setAlphaValue_(0)
panel.makeKeyAndOrderFront_(None)
# Animate alpha to 1.0 over 0.15s
NSAnimationContext.runAnimationGroup_(
    lambda ctx: (ctx.setDuration_(0.15), panel.animator().setAlphaValue_(1.0)),
    completionHandler_=None,
)
```

**Step 3: Verify all features work end-to-end**

```bash
pkill -f aiquotabar.py; sleep 1; python3 aiquotabar.py &
```

Test checklist:
- [ ] Click icon -> panel appears with blur background
- [ ] Provider sections show real progress bars
- [ ] ETA and sparklines show for active providers
- [ ] Click outside -> panel dismisses
- [ ] Esc -> panel dismisses
- [ ] Gear icon -> settings popover with all options
- [ ] Share -> Copy Image works
- [ ] Share -> Post to X opens browser
- [ ] `python3 aiquotabar.py` works (shim)
- [ ] `python3 -m aiquotabar` works (package)
- [ ] `python3 aiquotabar.py --history` works (CLI)
- [ ] Notifications still fire at 80%/95%
- [ ] Auto-update still works
- [ ] Widget cache still writes

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: polish floating panel — dismiss, animation, cleanup

Completes the UI overhaul: floating panel replaces NSMenu,
share (copy image + X), and code split into 6 modules."
```

---

### Summary

| Task | What | Estimated size |
|------|------|----------------|
| 1 | config.py | ~100 lines |
| 2 | providers.py | ~700 lines |
| 3 | history.py | ~450 lines |
| 4 | update.py | ~35 lines |
| 5 | ui.py (migrate existing) | ~1500 lines |
| 6 | Shim + __main__.py | ~20 lines |
| 7 | Floating panel (_UsagePanel) | ~300 lines new |
| 8 | Settings popover | ~200 lines new |
| 9 | Share feature | ~100 lines new |
| 10 | Polish + cleanup | ~50 lines |

Total: same line count, spread across 7 files, with ~650 lines of new UI code.
