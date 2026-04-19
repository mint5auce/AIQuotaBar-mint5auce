# AI Quota Bar

**Stop getting rate-limited by surprise.** See your Claude, ChatGPT, Cursor, and Copilot usage live in the macOS menu bar.

No Electron. No browser extension. One command to install.

## About this fork

This fork keeps the original AI Quota Bar concept by Toprak Yagcioglu, with these differences from upstream:

- Ships as a real `AIQuotaBar.app` bundle (built with py2app) and uses the macOS Login Items API, instead of running a raw `python3` LaunchAgent.
- Stores provider secrets in the macOS Keychain instead of plaintext config.
- Restricts browser cookie collection to a per-provider allowlist of the cookies actually needed.
- Does not log detected cookies or session tokens.
- No background self-update; updates happen when you rerun the installer or rebuild from source.
- Distribution is via `install.sh` and source build only (no Homebrew tap).


---

## Install

**One-line:**
```bash
curl -fsSL https://raw.githubusercontent.com/yagcioglutoprak/AIQuotaBar/main/install.sh | bash
```

The installer builds a real `AIQuotaBar.app` bundle (via py2app), copies it to `/Applications`, ad-hoc codesigns it, and launches it. The app auto-detects your Claude, ChatGPT, Cursor, and Copilot sessions from Chrome, Arc, Brave, Edge, Firefox, or Safari — no copy-pasting cookies.

Updates are manual: rerun the installer or pull the repo and rebuild yourself. The app does not self-update in the background.

---

### Why I built this

I kept getting cut off mid-session on Claude Pro with zero warning. Claude.ai doesn't show your usage until you hit the wall. Same with ChatGPT, Cursor, and Copilot. So I built a tiny menu bar app that shows them all.

---

## What it shows

| Menu bar | Meaning |
|---|---|
| 🟢 12% | Session usage is low — you're good |
| 🟡 83% | Approaching the 5-hour limit |
| 🔴 100% | Rate-limited — shows time until reset |
| 🔴 100% · | Session is fine but weekly limit is maxed |

Open the menu for full detail:

```
CLAUDE

  🟢 Current Session
  ██░░░░░░░░░░░░  12%
  resets in 3h 41m

  🟡 All Models
  ████████████░░  83%
  resets Wed 23:00

  🟢 Sonnet Only
  ███░░░░░░░░░░░  22%
  resets Wed 23:00

CHATGPT

  🟢 Codex Tasks
  █░░░░░░░░░░░░░  0%
  resets Thu 05:38

GITHUB COPILOT

  0 / 300 this month
  █░░░░░░░░░░░░░  0%

CURSOR

  🟢 Auto
  █░░░░░░░░░░░░░  0%
  resets in 27d

  🟢 API
  █░░░░░░░░░░░░░  0%
  resets in 27d
```

---

## Features

- **Zero-setup auth for Claude** — reads the minimum Claude cookies it needs from your browser (Chrome, Arc, Brave, Edge, Firefox, Safari)
- **Claude + ChatGPT + Cursor + Copilot** — tracks Claude.ai session/weekly limits, ChatGPT rate limits, Cursor Auto/API usage, and GitHub Copilot premium requests — all in one place
- **Multi-provider** — add OpenAI, MiniMax, GLM (Zhipu) API keys to see spending alongside usage
- **Burn rate + ETA** — predicts when you'll hit each limit based on your current pace
- **Pacing alerts** — notifies you when you're on track to hit a limit within 30 minutes
- **Auto-refresh on session expiry** — silently grabs fresh cookies when your session expires
- **macOS notifications** — alerts at 80% and 95% usage for Claude, ChatGPT, and Cursor
- **Configurable refresh** — 1 / 5 / 15 min
- **Runs at login** — via LaunchAgent, toggle from the menu
- **Tiny footprint** — single-file Python app, no Electron, no background services beyond the app itself

---

## Why not just check the settings page?

| | AI Quota Bar | Open settings page | Browser extension |
|---|---|---|---|
| Always visible | ✅ Menu bar | ❌ Manual tab switch | ⚠️ Badge only |
| Notifications | ✅ 80% + 95% + pacing alerts | ❌ None | ⚠️ Varies |
| Claude + ChatGPT + Cursor + Copilot | ✅ All in one place | ❌ One at a time | ❌ |
| Privacy | ✅ Local only | ✅ | ⚠️ Depends on extension |
| Install | ✅ One command | ✅ Nothing | ❌ Store + permissions |
| No Electron | ✅ Single-file Python | ✅ | ❌ Often Electron |

---

## Requirements

- macOS 13+ (uses the modern Login Items API)
- Python 3.10+ (build-time only — the installer ships a self-contained `AIQuotaBar.app`)
- A paid account for any supported service (Claude, ChatGPT, Cursor, or Copilot)
- Chrome, Arc, Brave, Edge, Firefox, or Safari with an active session

---

## Manual install / build from source

Set up a venv with the build + runtime dependencies:
```bash
git clone https://github.com/yagcioglutoprak/AIQuotaBar.git
cd AIQuotaBar
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools
.venv/bin/python -m pip install -r requirements.txt
```

`requirements.txt` includes the PyObjC macOS framework bindings the native UI depends on (Quartz, ServiceManagement) and `py2app` for the bundle build.

### Build the `.app` bundle

**Dev iteration (alias mode — instant rebuild, edits live):**
```bash
.venv/bin/python setup.py py2app -A
open dist/AIQuotaBar.app
```
Alias bundles symlink back to your source tree. Edit `aiquotabar/*.py`, quit the app, `open` it again — no rebuild needed.

**Full standalone build (frozen, distributable):**
```bash
rm -rf build dist
.venv/bin/python setup.py py2app
open dist/AIQuotaBar.app
```

### Install to `/Applications`

```bash
osascript -e 'tell application "AIQuotaBar" to quit' 2>/dev/null
rm -rf /Applications/AIQuotaBar.app
cp -R dist/AIQuotaBar.app /Applications/
codesign --force --deep --sign - /Applications/AIQuotaBar.app
open /Applications/AIQuotaBar.app
```

(Ad-hoc `codesign` silences the unidentified-developer Gatekeeper prompt for the machine you built on.)

### Run from source without bundling

```bash
.venv/bin/python -m aiquotabar
```
Works fine for development, but macOS will label it as a generic `python3` process — no proper app name in the menu bar or Login Items.

### Tests

```bash
.venv/bin/python -m pytest -q
```

### Caveats

- **macOS 13+ required** for the modern Login Items API (`SMAppService`).
- **Alias-mode + Login Items**: if you toggle "Start at Login" while running an alias-mode build, the registration points at `dist/AIQuotaBar.app` in your source tree. Toggle it back off (or remove it from System Settings → General → Login Items) before swapping to a real install in `/Applications`.

To upgrade later, rerun the install command or pull the repo manually and rebuild.

---

## How it works

The app calls the same private usage API that `claude.ai/settings/usage` uses. It authenticates using your browser's existing session cookies (read locally — never transmitted anywhere except to `claude.ai`).

Cookie collection is minimized per provider:

- Claude: `sessionKey`, `lastActiveOrg`, `routingHint`, and Cloudflare cookies if present
- ChatGPT: `__Secure-next-auth.session-token`
- Copilot: `user_session`, `logged_in`, `dotcom_user`
- Cursor: `WorkosCursorSessionToken`

Claude cookies auto-detect on startup. ChatGPT, Copilot, and Cursor cookies are only detected when you explicitly enable those providers from the menu.

[`curl_cffi`](https://github.com/yifeikong/curl_cffi) is used to mimic a Chrome TLS fingerprint, which is required to pass Cloudflare's bot protection.

| API field | Displayed as |
|---|---|
| `five_hour` | Current Session |
| `seven_day` | All Models (weekly) |
| `seven_day_sonnet` | Sonnet Only (weekly) |
| `extra_usage` | Extra Usage toggle |

---

## Troubleshooting

**App doesn't appear in menu bar**
```bash
tail -50 ~/.aiquotabar.log
```

**Cookies not detected**
Make sure you're logged into [claude.ai](https://claude.ai) in your browser, then click **Auto-detect from Browser** in the menu.

**Session expired / showing ◆ !**
The app will try to auto-detect fresh cookies from your browser. If that fails, click **Set Session Cookie…**.

---

## Roadmap

- [x] Cursor IDE usage tracking (Auto + API)
- [x] GitHub Copilot premium request tracking
- [x] Burn rate ETA + pacing alerts
- [ ] Linux system tray support
- [ ] Windows tray app
- [ ] Customizable notification thresholds
- [ ] Usage history graph
- [ ] Multiple Claude account support

---

## Contributing

PRs welcome. Open an issue first for large changes. See [Manual install](#manual-install) for dev setup. Logs: `~/.aiquotabar.log`.

---

## License

MIT — see [LICENSE](LICENSE).

## Disclaimer

Not affiliated with or endorsed by Anthropic. Uses undocumented internal APIs that may change without notice.
