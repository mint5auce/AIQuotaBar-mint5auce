# AGENTS.md

## Project Overview

AI Quota Bar is a macOS menu bar app that shows live usage and rate-limit status for Claude, ChatGPT, Cursor, and GitHub Copilot. It also supports optional API spend tracking for OpenAI, MiniMax, and GLM.

This fork keeps the app local-first and removes risky upstream behavior. Do not reintroduce background self-update, broad cookie harvesting, plaintext secret storage, or cookie logging.
The product is provider-agnostic. Brand the app as a multi-provider quota monitor, not as a Claude-specific utility, unless you are describing a provider-specific integration.

## Current Architecture

The app is package-based. `aiquotabar.py` is the top-level entry point.

```text
aiquotabar.py            Top-level entry point
aiquotabar/__main__.py   Main entry point and `--history` CLI switch
aiquotabar/ui.py         Menu bar app, floating panel UI, notifications, menu actions
aiquotabar/providers.py  Provider fetchers, Claude parsing, cookie detection/minimization
aiquotabar/history.py    Burn rate, history storage, sparklines, CLI history output
aiquotabar/config.py     Logging, config persistence, thresholds, filesystem paths
aiquotabar/secrets.py    macOS Keychain-backed secret storage and migration
```

Important runtime assets live under `assets/`. User-facing docs are in `README.md`. Technical implementation plans may exist under `docs/plans/`; they are not canonical repo instructions.

## Invariants To Preserve

- Store secrets in macOS Keychain via `aiquotabar/secrets.py`, not in tracked files or plaintext config.
- Minimize cookie capture to the provider-specific allowlists in `aiquotabar/providers.py`.
- Do not log raw cookies, session tokens, or API keys.
- Treat provider/API behavior as unstable: preserve defensive parsing and clear error handling.
- Keep the app local-first. Authentication data should only be used to talk to the relevant provider APIs.
- Keep naming and UX provider-agnostic at the product level. Provider-specific labels should only appear where they describe provider-specific behavior, metrics, or setup.

## Local Workflow

Run locally:

```bash
python3 aiquotabar.py
```

History CLI:

```bash
python3 -m aiquotabar --history
```

Basic validation:

```bash
python3 -m py_compile aiquotabar.py aiquotabar/*.py
```

Pytest:

```bash
pytest -q
```

Post-change validation policy:

- After every code change, run the relevant automated checks before finishing work.
- For changes under `aiquotabar/*.py` or `aiquotabar.py`, always run `python3 -m py_compile aiquotabar.py aiquotabar/*.py`.
- If the change touches existing tested behavior or any file under `tests/`, run `pytest -q` at minimum.
- Prefer the smallest relevant pytest target while iterating, but before handing off a code change, run the full `pytest -q` suite.
- If a change cannot be validated locally, say so explicitly and explain why.

Logs:

```bash
tail -f ~/.aiquotabar.log
```

Config and history are stored under the user home directory. The SQLite history database lives in `~/Library/Application Support/aiquotabar/history.db`.

## Editing Guidance

- Prefer changes that preserve the current package split rather than moving logic back into a monolith.
- When adding a provider, keep fetch/parsing logic in `aiquotabar/providers.py` and UI-only rendering in `aiquotabar/ui.py`.
- If you change config schema or secret handling, maintain migration behavior for existing local installs.
- If you touch notifications or refresh behavior, keep failure handling non-fatal so the menu bar app remains usable.
- Use `AI Quota Bar` in human-facing copy and `aiquotabar` in machine-facing identifiers.
- Update `README.md` only for real user-facing behavior changes.
