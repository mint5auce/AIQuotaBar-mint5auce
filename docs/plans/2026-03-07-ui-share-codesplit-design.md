# Design: Floating Panel UI + Share + Code Split

**Date:** 2026-03-07
**Status:** Approved

## Overview

Three changes to AI Quota Bar:
1. Replace the NSMenu dropdown with a custom floating panel (NSPanel)
2. Add share functionality (copy image + post to X)
3. Split the 2900-line single file into 5 modules

## 1. Floating Panel UI

### What changes

Replace the `rumps` NSMenu with a borderless `NSPanel` anchored below the menu bar icon. The panel uses `NSVisualEffectView` for vibrancy blur background, matching macOS system style.

### Layout

```
+--------------------------------------+
|  AI Quota Bar               [share][gear]  |
+--------------------------------------+
|                                      |
|  * Claude              resets 3h 41m |
|  Session     [======----]  42%       |
|  All Models  [==========]  83%       |
|  Sonnet      [===-------]  22%       |
|  timer Limit in ~47 min  sparkline   |
|                                      |
|  * ChatGPT             resets Thu    |
|  Codex Tasks [=---------]   0%       |
|                                      |
|  * Copilot           0 / 300         |
|  [==----------------]  0%            |
|                                      |
|  * Cursor              resets 27d    |
|  Auto        [=---------]   0%       |
|  API         [=---------]   0%       |
|                                      |
+--------------------------------------+
|  Claude Code  12 msgs / 3 sessions   |
|  Updated 14:32  /  Refresh btn       |
+--------------------------------------+
```

### Behavior

- Click menu bar icon -> panel appears anchored below icon. Click outside or Esc -> dismisses.
- `NSVisualEffectView` background (vibrancy blur).
- Progress bars are real `NSView` subviews: rounded corners, brand-colored fill, dark track.
- Each provider is a card-like group with brand color dot, name, sub-rows.
- Panel auto-sizes based on active providers.
- Settings (refresh interval, notifications, login item, providers) move to gear icon popover.
- Menu bar title still shows emoji + percentage text via `rumps.App`.
- All fetch logic, history, notifications, timers stay the same.

### Key implementation details

- Override `rumps.App` click behavior to show panel instead of menu.
- `NSPanel` with `NSWindowStyleMaskNonactivatingPanel` so it doesn't steal focus.
- Panel positions itself using `NSStatusItem` button frame.
- Dismiss on `resignKey` or Esc key.
- Provider sections only rendered for configured/active providers.

## 2. Share Feature

### Copy Image

- Render panel content area as PNG via `NSBitmapImageRep` from the panel's backing layer.
- Add subtle footer watermark: "AI Quota Bar - github.com/yagcioglutoprak/AIQuotaBar"
- Copy to clipboard via `NSPasteboard`.
- Share button shows brief "Copied" confirmation (1.5s).

### Post to X

- Open default browser with pre-filled tweet URL:
  `https://twitter.com/intent/tweet?text=...&url=https://github.com/yagcioglutoprak/AIQuotaBar`
- Text generated dynamically from current usage stats.
- Format: "Claude 42% / ChatGPT 0% / Copilot 0/300 -- tracking my AI usage with AI Quota Bar"

### UX

- `[share]` button in panel header shows 2-item popover: "Copy Image" and "Share on X".
- No extra windows or dialogs.

## 3. Code Split

### Structure

```
aiquotabar.py              # Shim: from aiquotabar.__main__ import main; main()
aiquotabar/
  __main__.py              # Entry point (~10 lines)
  config.py                # Constants, load/save config, notification prefs
  providers.py             # Data models, all fetch functions, cookie detection, parsing
  history.py               # Usage history, burn rate, SQLite, sparklines
  ui.py                    # AIQuotaBarApp(rumps.App), floating panel, share, settings, windows
  update.py                # Auto-update logic
```

### Dependency graph (no cycles)

```
config  <-  providers  <-  history  <-  ui  <-  __main__
                                        ^
                                   update
```

### Migration

- `aiquotabar.py` remains the entry point for local runs and packaging.
- install.sh and the LaunchAgent plist use the renamed `aiquotabar` entrypoint and identifiers.
- No new dependencies.
- Assets stay in `assets/` at repo root (referenced by `ui.py` via path relative to package).
