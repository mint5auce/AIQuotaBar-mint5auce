# AIQuotaBar Security Review

Reviewed on 2026-04-17.

## Executive Summary

I did not find evidence of hidden telemetry or arbitrary outbound exfiltration endpoints. The core app does read browser cookies locally and uses them to call the expected provider endpoints.

I did find several significant security issues around how those cookies and other secrets are handled after collection:

1. Auto-detected cookies are logged to disk.
2. Full browser session cookies and API keys are persisted in plaintext outside the browser keychain.
3. The app copies broader cookie sets than necessary, including entire domain cookie jars.
4. The default git-based install path enables silent remote code updates and dependency refreshes.
Together, these issues mean the app does more than "read cookies for usage checks": it also retains, logs, and auto-updates code using trust paths that are not hardened.

## Scope Reviewed

- Python app under `aiquotabar/`
- Entry point `claude_bar.py`
- Installers: `install.sh`, `setup.sh`, `Formula/aiquotabar.rb`
- Dependency manifest `requirements.txt`

## Critical Findings

### F-01: Auto-detected session cookies are written into the rotating log file

Impact: any local process or user with read access to `~/.claude_bar.log` can recover live session material and hijack Claude, ChatGPT, GitHub, or Cursor sessions.

Evidence:

- `aiquotabar/providers.py:567-574` runs the cookie-detection subprocess and logs `r.stdout[:200]`.
- `aiquotabar/providers.py:560` prints the detected cookie string as JSON to stdout.
- `aiquotabar/config.py:10-15` configures a rotating file logger at `~/.claude_bar.log`.
- `README.md:182-185` tells users to inspect that log file for troubleshooting.

Why this matters:

- The subprocess stdout is the cookie jar itself.
- Even truncating to 200 characters still leaks high-value session tokens.
- This directly contradicts the "local only" privacy posture because secrets are copied into an additional persistence channel not needed for functionality.

Recommendation:

- Remove cookie values from logs entirely.
- If detection must be logged, log only browser name and cookie names, never values.
- Treat existing logs as compromised and rotate/delete them on upgrade.

## High Findings

### F-02: Browser sessions and API keys are persisted in plaintext outside Keychain

Impact: the app turns browser-protected sessions into long-lived plaintext secrets under the user profile, expanding the blast radius of any local compromise.

Evidence:

- `aiquotabar/config.py:20` stores configuration in `~/.claude_bar_config.json`.
- `aiquotabar/config.py:91-95` writes JSON directly with no encryption and no explicit permission hardening.
- `aiquotabar/ui.py:2475-2481`, `2563-2567`, `2867-2877`, `3176-3210` persist auto-detected cookies.
- `aiquotabar/ui.py:2967-2971` persists API keys the same way.

Notes:

- In this review environment the shell `umask` is `022`, so newly created files default to `0644` unless the process tightens them.
- Even with stricter home-directory permissions, any process running as the same user can read these files.

Recommendation:

- Store secrets in macOS Keychain, not JSON.
- If a plaintext fallback is unavoidable, explicitly create files with `0600` and minimize retention.
- Provide a "do not persist cookies" mode and keep auto-detected cookies in memory only.

### F-03: Cookie collection is broader than necessary for the stated feature

Impact: the app does not copy only the minimum cookies needed for usage checks; it copies entire domain cookie jars and auto-collects multiple services in the background.

Evidence:

- `aiquotabar/providers.py:542-548` serializes every cookie returned for the matched domain into one string.
- `aiquotabar/providers.py:580-606` performs detection for `claude.ai`, `chatgpt.com`, `github.com`, and `cursor.com`.
- `aiquotabar/ui.py:2861-2877` auto-detects and stores ChatGPT, Copilot, and Cursor cookies whenever they are not already saved.

Why this matters:

- For GitHub in particular, this can capture a full `github.com` authenticated session, not just the minimum needed to read Copilot usage.
- This exceeds least privilege and makes F-01/F-02 materially worse.

Recommendation:

- Collect only the specific cookies required per provider.
- Avoid background auto-detection for providers the user has not explicitly enabled.
- Document exactly which cookie names are read and why.

### F-04: Git installs silently self-update code and dependencies from the network

Impact: the primary install path can execute newly fetched code and refreshed dependencies without a user action at runtime.

Evidence:

- `install.sh:44-63` clones the repository and installs dependencies into a venv.
- `aiquotabar/ui.py:2546-2553` checks for updates every four hours and restarts if one is applied.
- `aiquotabar/update.py:10-35` runs `git fetch`, fast-forward merges `origin/main`, runs `pip install -r requirements.txt`, then restarts the app.

Why this matters:

- This is effectively a silent remote code execution path gated only by trust in the repo origin and package index.
- There is no signature verification, release pinning, or explicit in-app consent.
- The updater also runs `git stash`, which mutates the local install state.

Recommendation:

- Remove silent self-update by default.
- If update support is kept, require explicit user confirmation and update only to signed/tagged releases.
- Pin and verify dependency artifacts instead of live `pip install -r requirements.txt` from the network.

## Medium Findings

### F-05: `curl_cffi` is currently on a version with a published high-severity advisory

Impact: the dependency has a current SSRF advisory; exploitability in this app is limited because the app uses hard-coded URLs, but the dependency should still be updated.

Evidence:

- `requirements.txt:2` allows `curl_cffi>=0.7.0,<1.0`; the installed review environment resolved `0.13.0`.
- `python3 -m pip_audit -r requirements.txt` on 2026-04-17 reported `GHSA-qw2m-4pqf-rmpp` / `CVE-2026-33752` with fix version `0.15.0`.
- GitHub Advisory Database: `https://github.com/advisories/GHSA-qw2m-4pqf-rmpp`

Assessment:

- I did not find a direct user-controlled URL path in this codebase, so this is not the most urgent issue here.
- It is still an avoidable dependency risk and should be upgraded.

Recommendation:

- Raise the minimum version to `0.15.0` or newer and retest provider fetch flows.

## What I Did Not Find

- No evidence of analytics, telemetry beacons, advertising SDKs, or arbitrary exfiltration endpoints in the app code.
- Runtime network destinations in the Python app are hard-coded provider endpoints plus GitHub/X for user actions and updates.

## Overall Assessment

The app is not behaving like a cookie stealer in the classic sense: I did not find code that ships cookies to unrelated servers or hidden collectors. However, it is not currently safe enough to claim it uses browser cookies only for the narrow stated need. The biggest problems are local secret handling and software supply-chain behavior after the cookies have been copied.

Before treating this app as safe for regular use, I would fix F-01 through F-04 first.
