# Changelog

This changelog tracks notable user-facing changes to AI Quota Bar. It is curated manually rather than generated from raw commits.

For notable user-visible changes, update the `Unreleased` section in the same PR or commit. Purely internal refactors, tests, or docs-only cleanup can be skipped unless they change behavior users see.

Release dates below come from Git tag metadata when available.

## Unreleased

No unreleased changes yet.

## v1.7.0 - 2026-04-20

### Added

- Added a Git-derived build ID in the menu and floating panel footer so source runs and rebuilt app bundles show which build is running.
- Added a macOS app-bundle packaging flow via `py2app`, plus an installer flow that builds and installs `AIQuotaBar.app`.
- Added a browser cookies and permissions explainer, plus a "Learn More" setup path for cookie-related prompts.

### Changed

- Repositioned the fork as a local-first, multi-provider quota monitor instead of a Claude-only utility.
- Switched distribution to source builds and the bundled app installer rather than Homebrew or background self-update flows.
- Simplified sharing and settings actions by removing low-value menu items such as Share on X and the direct Claude settings link.
- Cut `v1.7.0` as a fully tested, working, release-ready baseline for this fork.

### Fixed

- Improved provider diagnostics and setup copy so refresh and auth failures tell users what action to take next.
- Tightened floating-panel and cookie-detection behavior for more reliable source runs and packaged app launches.

### Security

- Moved saved cookies and API keys into macOS Keychain instead of plaintext config.
- Reduced cookie capture to provider-specific allowlists and stopped logging cookies or session tokens.
- Removed silent self-update behavior and documented the fork's security-focused changes more clearly.

## v1.6.1 - 2026-03-01

### Fixed

- Improved usage estimation with reset detection, per-row ETA handling, and weighted regression for more reliable pacing output.

## v1.6.0 - 2026-03-01

### Added

- Added configurable widget and status bar provider selection so users can choose which AI providers are shown.

## v1.5.0 - 2026-03-01

### Added

- Added Cursor usage tracking with browser session auto-detection, warnings, and pacing alerts.
- Added GitHub Copilot usage monitoring alongside the existing provider set.
- Added burn-rate ETA and sparklines to make limit timing easier to understand.

### Changed

- Refreshed provider icons and tints for Cursor and Copilot in the UI and docs.

### Fixed

- Simplified menu presentation by removing the sparkline from the menu where it was hard to read.
- Changed ETA formatting to human-readable durations such as `2h 52 min`.

## v1.4.1 - 2026-02-27

### Added

- Added automatic installation support for the prebuilt desktop widget.

### Fixed

- Switched to a Safari TLS fingerprint to improve reliability against Cloudflare-protected requests.
- Improved welcome-screen GIF sizing, layout, and compression so onboarding visuals render more reliably.

## v1.4.0 - 2026-02-27

### Added

- Added a native macOS desktop widget built with WidgetKit.
- Added side-by-side demo GIF layouts in the README and welcome window.

### Fixed

- Preferred the freshest browser session when multiple supported browsers contained cookies.

## v1.3.0 - 2026-02-26

### Added

- Added reset notifications, Safari cookie detection, and smoother no-blink refresh behavior.

## v1.2.0 - 2026-02-26

### Added

- Added a GitHub Pages landing page and moved the demo GIF into the hero section for clearer product presentation.

### Changed

- Refined the landing page and app presentation to better match macOS HIG conventions.

### Fixed

- Improved Homebrew formula and launch-at-login defaults for a cleaner install experience.

## v1.1.0 - 2026-02-26

### Added

- Added a Homebrew tap installation path and a Share on X menu action.

### Changed

- Renamed the project to `AIQuotaBar` and updated the public positioning around Claude plus ChatGPT tracking.

## v1.0.0 - 2026-02-26

### Added

- Initial release of the macOS menu bar app for tracking Claude usage.
- Added browser cookie auto-detection, notifications, clipboard cookie paste, configurable refresh, and launch-at-login support.
- Added ChatGPT, Claude Code, and API-provider spend tracking for OpenAI, MiniMax, and GLM (Zhipu).
- Added menu bar branding improvements, native status indicators, demo media, and a one-line installer.

### Fixed

- Fixed early fetch, parsing, and session-reset issues that could incorrectly show 100% usage or crash on startup.
