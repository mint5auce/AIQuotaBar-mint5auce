"""Configuration constants and persistence."""

import glob
import json
import logging
import logging.handlers
import os

# ── logging ──────────────────────────────────────────────────────────────────

log = logging.getLogger("aiquotabar")
LOG_FILE = os.path.expanduser("~/.aiquotabar.log")
LOG_PURGE_MARKER = "log_cleanup_v1_done"


def _make_log_handler() -> logging.Handler:
    handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3,
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    )
    return handler


def _configure_logging():
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(_make_log_handler())
    root.setLevel(logging.DEBUG)


_configure_logging()

# ── paths & thresholds ───────────────────────────────────────────────────────

CONFIG_FILE = os.path.expanduser("~/.aiquotabar_config.json")

REFRESH_INTERVALS = {
    "1 min":  60,
    "5 min":  300,
    "15 min": 900,
}
DEFAULT_REFRESH = 300

WARN_THRESHOLD = 80   # notify when any limit crosses this %
CRIT_THRESHOLD = 95   # title turns red emoji above this %

# ── notification defaults ─────────────────────────────────────────────────────
# Keys stored in config under "notifications": { key: bool }
NOTIF_DEFAULTS = {
    "claude_reset":   True,   # notify when Claude session/weekly resets
    "chatgpt_reset":  True,   # notify when ChatGPT rate-limit resets
    "claude_warning": True,   # notify when Claude usage crosses WARN/CRIT
    "chatgpt_warning":True,   # notify when ChatGPT usage crosses WARN/CRIT
    "claude_pacing":  True,   # predictive alert when Claude ETA < 30 min
    "chatgpt_pacing": True,   # predictive alert when ChatGPT ETA < 30 min
    "copilot_pacing": True,   # predictive alert when Copilot ETA < 30 min
    "cursor_warning": True,   # notify when Cursor usage crosses WARN/CRIT
    "cursor_pacing":  True,   # predictive alert when Cursor ETA < 30 min
}

# ── usage history + burn rate ────────────────────────────────────────────────

HISTORY_FILE = os.path.expanduser("~/.aiquotabar_history.json")
HISTORY_MAX_AGE = 24 * 3600  # prune entries older than 24 h
PACING_ALERT_MINUTES = 30    # alert when ETA drops below this

# ── SQLite long-term history ─────────────────────────────────────────────────
HISTORY_DB = os.path.join(os.path.expanduser("~/Library/Application Support/aiquotabar"), "history.db")
SAMPLES_MAX_DAYS = 7
DAILY_MAX_DAYS = 90
LIMIT_HIT_PCT = 95
BURN_WINDOW = 30 * 60       # regression window: 30 minutes
MIN_SPAN_SECS = 5 * 60      # need >=5 min of data before showing ETA
RESET_DROP_PCT = 30          # pct drop that signals a reset
HISTORY_COLORS = {
    "claude": "#D97757", "chatgpt": "#74AA9C",
    "copilot": "#6E40C9", "cursor": "#00A0D1",
}


# ── config persistence ───────────────────────────────────────────────────────

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


def purge_compromised_logs_once(cfg: dict):
    """Delete old log files once, then recreate a fresh handler."""
    if cfg.get(LOG_PURGE_MARKER):
        return

    root = logging.getLogger()
    old_handlers = list(root.handlers)
    for handler in old_handlers:
        try:
            handler.flush()
            handler.close()
        except Exception:
            pass
        root.removeHandler(handler)

    for path in glob.glob(LOG_FILE + "*"):
        try:
            os.remove(path)
        except OSError:
            pass

    _configure_logging()
    cfg[LOG_PURGE_MARKER] = True
    save_config(cfg)


def notif_enabled(cfg: dict, key: str) -> bool:
    """Return True if the named notification is enabled (defaults to True)."""
    return cfg.get("notifications", {}).get(key, NOTIF_DEFAULTS.get(key, True))


def set_notif(cfg: dict, key: str, value: bool):
    """Persist a single notification toggle."""
    cfg.setdefault("notifications", {})[key] = value
    save_config(cfg)
