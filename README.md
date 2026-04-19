# AI Quota Bar

**Stop getting rate-limited by surprise.** See your Claude, ChatGPT, Cursor, and Copilot usage live in the macOS menu bar.

No Electron. No browser extension. One command to install.

See [CHANGELOG.md](CHANGELOG.md) for curated release history.

## About this fork

This fork keeps the original AI Quota Bar concept by [Toprak Yagcioglu](https://github.com/yagcioglutoprak), with these key simplifications and differences from upstream:

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
curl -fsSL https://raw.githubusercontent.com/mint5auce/AIQuotaBar-mint5auce/main/install.sh | bash
```

The installer builds a real `AIQuotaBar.app` bundle (via py2app), copies it to `/Applications`, ad-hoc codesigns it, and launches it. The app auto-detects your Claude, ChatGPT, Cursor, and Copilot sessions from Chrome, Arc, Brave, Edge, Firefox, or Safari — no copy-pasting cookies.

Updates are manual: rerun the installer or pull the repo and rebuild yourself. The app does not self-update in the background.
The menu and floating panel show a Git-derived build ID in the footer; installed app bundles update that build ID when you rebuild or rerun the installer.

---

## Features

- **Zero-setup auth for Claude** — reads the minimum Claude cookies it needs from your browser (Chrome, Arc, Brave, Edge, Firefox, Safari)
- **Claude + ChatGPT + Cursor + Copilot** — tracks Claude.ai session/weekly limits, ChatGPT rate limits, Cursor Auto/API usage, and GitHub Copilot premium requests — all in one place
- **Multi-provider** — add OpenAI, MiniMax, GLM (Zhipu) API keys to see spending alongside usage
- **Burn rate + ETA** — predicts when you'll hit each limit based on your current pace
- **Pacing alerts** — notifies you when you're on track to hit a limit within 30 minutes
- **Auto-refresh on session expiry** — silently grabs fresh cookies when your session expires
- **Explicit setup diagnostics** — the floating panel shows which provider is missing setup or failing refresh, plus the next action to take
- **macOS notifications** — alerts at 80% and 95% usage for Claude, ChatGPT, and Cursor
- **Configurable refresh** — 1 / 5 / 15 min
- **Runs at login** — via LaunchAgent, toggle from the menu
- **Tiny footprint** — single-file Python app, no Electron, no background services beyond the app itself

## Requirements

- macOS 13+ (uses the modern Login Items API)
- Python 3.10+ (build-time only — the installer ships a self-contained `AIQuotaBar.app`)
- A paid account for any supported service (Claude, ChatGPT, Cursor, or Copilot)
- Chrome, Arc, Brave, Edge, Firefox, or Safari with an active session

---

## Manual install / build from source

Set up a venv with the build + runtime dependencies:
```bash
git clone https://github.com/mint5auce/AIQuotaBar-mint5auce.git
cd AIQuotaBar-mint5auce
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

Claude cookies auto-detect on startup through a separate helper launch so refresh works reliably in source runs, alias builds, and bundled app launches. ChatGPT, Copilot, and Cursor cookies are only detected when you explicitly enable those providers from the menu.

If Claude setup is broken, the app still refreshes any other configured providers and shows provider-specific diagnostics in the panel instead of a blank waiting state.

For the exact cookie list and a plain-English explanation of the macOS permission prompt, see [Browser cookies and permissions](docs/cookies-and-permissions.md).

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

If the panel shows a provider diagnostic, follow the action text there first. The app now distinguishes between missing setup, expired auth, and fetch failures per provider.

**Session expired / showing ◆ !**
The app will try to auto-detect fresh cookies from your browser. If that fails, click **Set Session Cookie…**.

---

## License

MIT — see [LICENSE](LICENSE).

## Disclaimer

Not affiliated with or endorsed by Anthropic. Uses undocumented internal APIs that may change without notice.
