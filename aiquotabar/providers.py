from __future__ import annotations

"""Data models and API fetch functions for all providers."""

import json
import math
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

from curl_cffi import requests
from curl_cffi.requests.exceptions import HTTPError as CurlHTTPError

try:
    import browser_cookie3
    _BROWSER_COOKIE3_OK = True
except ImportError:
    _BROWSER_COOKIE3_OK = False

from aiquotabar.config import log


# ── data models ───────────────────────────────────────────────────────────────

@dataclass
class LimitRow:
    label: str
    pct: int          # 0–100
    reset_str: str    # e.g. "resets in 1h 23m" or "resets Thu 00:00"


@dataclass
class UsageData:
    session: LimitRow | None = None
    weekly_all: LimitRow | None = None
    weekly_sonnet: LimitRow | None = None
    overages_enabled: bool | None = None
    raw: dict = field(default_factory=dict)


@dataclass
class ProviderData:
    """Usage/billing data for a third-party API provider."""
    name: str
    spent: float | None = None    # current period spend
    limit: float | None = None    # hard/soft limit
    balance: float | None = None  # prepaid balance (for credit-based providers)
    currency: str = "USD"
    period: str = "this month"
    error: str | None = None
    _rows: list = field(default_factory=list, repr=False)

    @property
    def pct(self) -> int | None:
        if self.spent is not None and self.limit and self.limit > 0:
            return min(100, round(self.spent / self.limit * 100))
        return None


@dataclass
class CookieDetectResult:
    provider_key: str
    status: str
    cookie_str: str | None = None
    error_type: str | None = None
    detail: str | None = None
    returncode: int | None = None


# ── claude.ai API ─────────────────────────────────────────────────────────────

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://claude.ai/settings/usage",
    "Origin": "https://claude.ai",
}
# Cloudflare fingerprint-checks Chrome aggressively; Safari passes cleanly.
_IMPERSONATE = "safari184"
# Cloudflare-bound cookies are tied to the real browser fingerprint —
# sending them from a different TLS stack causes a mismatch → 403.
CF_COOKIE_KEYS = frozenset({"cf_clearance", "__cf_bm", "_cfuvid"})
COOKIE_KEY_ALLOWLISTS: dict[str, tuple[str, ...]] = {
    "cookie_str": (
        "sessionKey",
        "lastActiveOrg",
        "routingHint",
        "cf_clearance",
        "__cf_bm",
        "_cfuvid",
    ),
    "chatgpt_cookies": (
        "__Secure-next-auth.session-token",
    ),
    "copilot_cookies": (
        "user_session",
        "logged_in",
        "dotcom_user",
    ),
    "cursor_cookies": (
        "WorkosCursorSessionToken",
    ),
}

COOKIE_DETECTION_TARGETS: dict[str, tuple[str, str, str]] = {
    "cookie_str": ("claude.ai", "sessionKey", "Claude"),
    "chatgpt_cookies": (
        "chatgpt.com", "__Secure-next-auth.session-token", "ChatGPT",
    ),
    "copilot_cookies": ("github.com", "user_session", "Copilot"),
    "cursor_cookies": ("cursor.com", "WorkosCursorSessionToken", "Cursor"),
}

COOKIE_PERMISSION_DOC_URL = (
    "https://github.com/mint5auce/AIQuotaBar-mint5auce/blob/main/"
    "docs/cookies-and-permissions.md"
)


def parse_cookie_string(raw: str) -> dict:
    """Parse 'key=val; key2=val2' or just a bare sessionKey value."""
    raw = raw.strip()
    if "=" not in raw:
        return {"sessionKey": raw}
    cookies = {}
    for part in raw.split(";"):
        part = part.strip()
        if "=" in part:
            k, _, v = part.partition("=")
            cookies[k.strip()] = v.strip()
    return cookies


def minimize_cookie_map(provider_key: str, cookies: dict) -> dict:
    """Return only the allowlisted cookies for the given provider key."""
    allowed = COOKIE_KEY_ALLOWLISTS.get(provider_key)
    if not allowed:
        return dict(cookies)
    return {k: v for k, v in cookies.items() if k in allowed}


def minimize_cookie_string(provider_key: str, raw: str) -> str:
    """Normalize a cookie string down to the provider allowlist."""
    cookies = minimize_cookie_map(provider_key, parse_cookie_string(raw))
    return "; ".join(f"{k}={v}" for k, v in cookies.items())


def _strip_cf_cookies(cookies: dict) -> dict:
    return {k: v for k, v in cookies.items() if k not in CF_COOKIE_KEYS}


def _get(url: str, cookies: dict) -> dict | list:
    r = requests.get(
        url, cookies=_strip_cf_cookies(cookies), headers=HEADERS, timeout=15,
        impersonate=_IMPERSONATE,
    )
    log.debug("GET %s status=%s", url, r.status_code)
    r.raise_for_status()
    return r.json()


def _org_id_from_cookies(cookies: dict) -> str | None:
    return cookies.get("lastActiveOrg") or cookies.get("routingHint")


def _org_id_from_api(cookies: dict) -> str | None:
    for path in (
        "/api/organizations",
        "/api/bootstrap",
        "/api/auth/current_account",
        "/api/account",
    ):
        try:
            data = _get(f"https://claude.ai{path}", cookies)
            if isinstance(data, list) and data:
                return data[0].get("id") or data[0].get("uuid")
            if isinstance(data, dict):
                for candidate in (
                    data.get("organization_id"),
                    data.get("org_id"),
                    (data.get("organizations") or [{}])[0].get("id"),
                    (data.get("account", {}).get("memberships") or [{}])[0]
                        .get("organization", {}).get("id"),
                ):
                    if candidate:
                        return candidate
        except Exception as e:
            log.debug("endpoint %s failed: %s", path, e)
    return None



def fetch_raw(cookie_str: str) -> dict:
    cookies = parse_cookie_string(cookie_str)
    log.debug("using cookies keys: %s", list(cookies.keys()))

    org_id = _org_id_from_cookies(cookies)
    log.debug("org_id from cookie: %s", org_id)

    if not org_id:
        org_id = _org_id_from_api(cookies)
        log.debug("org_id from api: %s", org_id)

    if not org_id:
        raise ValueError(
            "Could not find organization id.\n"
            "Make sure you copied ALL cookies (including lastActiveOrg)."
        )

    usage = _get(
        f"https://claude.ai/api/organizations/{org_id}/usage", cookies
    )
    log.debug("claude usage fetched for org=%s keys=%s", org_id, list(usage.keys()))
    return {"usage": usage, "org_id": org_id}


# ── time helpers ──────────────────────────────────────────────────────────────

_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _fmt_reset(val) -> str:
    if val is None:
        return ""
    try:
        if isinstance(val, (int, float)):
            dt = datetime.fromtimestamp(val, tz=timezone.utc)
        else:
            s = str(val).rstrip("Z")
            if "+" not in s[10:] and s[-6] != "+":
                s += "+00:00"
            dt = datetime.fromisoformat(s)
        now = datetime.now(timezone.utc)
        delta = dt - now
        secs = delta.total_seconds()
        if secs <= 0:
            return "resets soon"
        if secs < 3600 * 20:
            h, rem = divmod(int(secs), 3600)
            m = rem // 60
            if h > 0:
                return f"resets in {h}h {m}m"
            return f"resets in {m}m"
        day = _DAYS[dt.weekday()]
        return f"resets {day} {dt.strftime('%H:%M')}"
    except Exception:
        log.debug("_fmt_reset failed for %r", val, exc_info=True)
        return str(val)[:20]


# ── parser ────────────────────────────────────────────────────────────────────

def _row(data: dict, key: str, label: str) -> LimitRow | None:
    bucket = data.get(key)
    if not bucket or not isinstance(bucket, dict):
        return None
    raw = float(bucket.get("utilization", 0))
    # API returns 0-100 percentage for all fields (five_hour, seven_day, etc.)
    pct = min(100, round(raw))
    reset = _fmt_reset(bucket.get("resets_at"))
    return LimitRow(label, pct, reset)


def parse_usage(raw: dict) -> UsageData:
    """
    API response shape (confirmed):
      five_hour        -> Plan usage limits / Current session
      seven_day        -> Weekly limits / All models
      seven_day_sonnet -> Weekly limits / Sonnet only
      extra_usage      -> Extra usage toggle (null = off)
    """
    u = raw.get("usage", {})
    extra = u.get("extra_usage")
    overages = bool(extra) if extra is not None else None

    return UsageData(
        session=_row(u, "five_hour", "Current Session"),
        weekly_all=_row(u, "seven_day", "All Models"),
        weekly_sonnet=_row(u, "seven_day_sonnet", "Sonnet Only"),
        overages_enabled=overages,
        raw=raw,
    )


# ── third-party provider APIs ────────────────────────────────────────────────

def _api_get(url: str, headers: dict, cookies: dict | None = None) -> dict:
    clean = _strip_cf_cookies(cookies) if cookies else None
    r = requests.get(url, headers=headers, cookies=clean, timeout=10, impersonate=_IMPERSONATE)
    r.raise_for_status()
    return r.json()


_CHATGPT_HEADERS = {
    "Accept": "application/json",
    "Referer": "https://chatgpt.com/codex/settings/usage",
}


def _chatgpt_access_token(cookies: dict) -> str | None:
    """Exchange session cookie for a short-lived Bearer token."""
    data = _api_get("https://chatgpt.com/api/auth/session", _CHATGPT_HEADERS, cookies)
    return data.get("accessToken")


def _parse_wham_window(window: dict, label: str) -> LimitRow | None:
    """Parse a single rate-limit window dict into a LimitRow."""
    if not window or not isinstance(window, dict):
        return None
    pw = window.get("primary_window") or {}
    pct = min(100, int(pw.get("used_percent", 0)))
    reset_str = _fmt_reset(pw.get("reset_at")) if pw.get("reset_at") else ""
    return LimitRow(label, pct, reset_str)


def _parse_wham_usage(data: dict) -> ProviderData:
    """Parse /backend-api/wham/usage response.

    Confirmed shape (2026-02):
      rate_limit.primary_window.used_percent  (0-100)
      rate_limit.primary_window.reset_at      (Unix timestamp)
      code_review_rate_limit  -- same structure
    """
    log.debug("chatgpt usage fetched keys=%s", list(data.keys()))

    rows: list[LimitRow] = []

    label_map = {
        "rate_limit":            "Codex Tasks",
        "code_review_rate_limit": "Code Review",
    }
    for key, label in label_map.items():
        row = _parse_wham_window(data.get(key), label)
        if row is not None:
            rows.append(row)

    # additional_rate_limits may be a list of extra buckets
    for extra in (data.get("additional_rate_limits") or []):
        if isinstance(extra, dict):
            name = extra.get("name") or extra.get("type") or "Extra"
            row = _parse_wham_window(extra, name.replace("_", " ").title())
            if row:
                rows.append(row)

    if not rows:
        return ProviderData("ChatGPT", error="No rate limit data in response")

    worst = max(rows, key=lambda r: r.pct)
    pd = ProviderData("ChatGPT", spent=float(worst.pct), limit=100.0, currency="")
    pd._rows = rows
    return pd


def _chatgpt_http_error(step: str, exc: CurlHTTPError) -> str:
    """Build a structured error string and log diagnostics for a failed step.

    Returns strings like ``"session: 401"`` / ``"wham: 403"`` so the UI can
    distinguish *which* step rejected us and react accordingly. The full
    response body is emitted via ``log.warning`` for offline diagnosis.
    """
    resp = getattr(exc, "response", None)
    status = getattr(resp, "status_code", None)
    body = (getattr(resp, "text", "") or "")[:500].replace("\n", " ")
    log.warning("fetch_chatgpt %s step HTTP %s: %s", step, status, body)
    if status:
        return f"{step}: {status}"
    return f"{step}: {str(exc)[:60]}"


def fetch_chatgpt(cookie_str: str) -> ProviderData:
    """Fetch ChatGPT / Codex usage via /backend-api/wham/usage."""
    cookies = parse_cookie_string(cookie_str)

    try:
        token = _chatgpt_access_token(cookies)
    except CurlHTTPError as e:
        return ProviderData("ChatGPT", error=_chatgpt_http_error("session", e))
    except Exception as e:
        log.debug("fetch_chatgpt session step failed: %s", e)
        return ProviderData("ChatGPT", error=f"session: {str(e)[:60]}")

    if not token:
        return ProviderData("ChatGPT", error="session: no accessToken")

    h = {**_CHATGPT_HEADERS, "Authorization": f"Bearer {token}"}
    try:
        data = _api_get("https://chatgpt.com/backend-api/wham/usage", h, cookies)
    except CurlHTTPError as e:
        return ProviderData("ChatGPT", error=_chatgpt_http_error("wham", e))
    except Exception as e:
        log.debug("fetch_chatgpt wham step failed: %s", e)
        return ProviderData("ChatGPT", error=f"wham: {str(e)[:60]}")

    return _parse_wham_usage(data)


def fetch_openai(api_key: str) -> ProviderData:
    h = {"Authorization": f"Bearer {api_key}"}
    try:
        sub = _api_get(
            "https://api.openai.com/v1/dashboard/billing/subscription", h
        )
        hard_limit = float(
            sub.get("hard_limit_usd") or sub.get("system_hard_limit_usd") or 0
        )
        now = datetime.now()
        start = now.replace(day=1).strftime("%Y-%m-%d")
        end = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        usage = _api_get(
            f"https://api.openai.com/v1/dashboard/billing/usage"
            f"?start_date={start}&end_date={end}", h
        )
        spent = float(usage.get("total_usage", 0)) / 100  # cents -> dollars
        return ProviderData(
            "OpenAI", spent=spent,
            limit=hard_limit or None, currency="USD", period="this month",
        )
    except Exception as e:
        log.debug("fetch_openai failed: %s", e)
        return ProviderData("OpenAI", error=str(e)[:80])


def fetch_minimax(api_key: str) -> ProviderData:
    h = {"Authorization": f"Bearer {api_key}"}
    try:
        data = _api_get("https://api.minimax.chat/v1/account_information", h)
        balance = float(
            data.get("available_balance") or data.get("balance") or 0
        )
        return ProviderData("MiniMax", balance=balance, currency="CNY")
    except Exception as e:
        log.debug("fetch_minimax failed: %s", e)
        return ProviderData("MiniMax", error=str(e)[:80])


def fetch_glm(api_key: str) -> ProviderData:
    h = {"Authorization": f"Bearer {api_key}"}
    try:
        data = _api_get(
            "https://open.bigmodel.cn/api/paas/v4/account/balance", h
        )
        balance = float(
            data.get("total_balance") or data.get("balance") or 0
        )
        return ProviderData("GLM (Zhipu)", balance=balance, currency="CNY")
    except Exception as e:
        log.debug("fetch_glm failed: %s", e)
        return ProviderData("GLM (Zhipu)", error=str(e)[:80])


def fetch_copilot(cookie_str: str) -> ProviderData:
    """Fetch GitHub Copilot premium request usage via browser cookies."""
    cookies = parse_cookie_string(cookie_str)
    try:
        r = requests.get(
            "https://github.com/settings/billing/copilot_usage_card",
            cookies=_strip_cf_cookies(cookies),
            headers={
                "Accept": "application/json",
                "Referer": "https://github.com/settings/billing/premium_requests_usage",
            },
            timeout=10,
            impersonate=_IMPERSONATE,
        )
        r.raise_for_status()
        data = r.json()
        log.debug("copilot usage fetched keys=%s", list(data.keys()))
        used = float(data.get("discountQuantity", 0))
        limit = float(data.get("userPremiumRequestEntitlement", 0))
        return ProviderData(
            "Copilot", spent=used, limit=limit or None,
            currency="", period="this month",
        )
    except Exception as e:
        log.debug("fetch_copilot failed: %s", e)
        return ProviderData("Copilot", error=str(e)[:80])


def fetch_cursor(cookie_str: str) -> ProviderData:
    """Fetch Cursor IDE usage via browser cookies (WorkOS session)."""
    cookies = parse_cookie_string(cookie_str)
    try:
        r = requests.get(
            "https://cursor.com/api/usage-summary",
            cookies=_strip_cf_cookies(cookies),
            headers={
                "Accept": "application/json",
                "Referer": "https://cursor.com/dashboard?tab=usage",
            },
            timeout=10,
            impersonate=_IMPERSONATE,
        )
        r.raise_for_status()
        data = r.json()
        log.debug("cursor usage fetched keys=%s", list(data.keys()))
        plan = (data.get("individualUsage") or {}).get("plan") or {}
        auto_pct = int(round(float(plan.get("autoPercentUsed", 0))))
        api_pct = int(round(float(plan.get("apiPercentUsed", 0))))
        total_pct = int(round(float(plan.get("totalPercentUsed", 0))))
        # Build reset string from billingCycleEnd
        reset_str = ""
        cycle_end = data.get("billingCycleEnd")
        if cycle_end:
            try:
                end_dt = datetime.fromisoformat(cycle_end.replace("Z", "+00:00"))
                delta = end_dt - datetime.now(timezone.utc)
                if delta.total_seconds() > 0:
                    days = delta.days
                    hours = delta.seconds // 3600
                    if days > 0:
                        reset_str = f"resets in {days}d {hours}h"
                    else:
                        reset_str = f"resets in {hours}h"
            except (ValueError, TypeError):
                pass
        rows = [
            LimitRow(label="Auto", pct=auto_pct, reset_str=reset_str),
            LimitRow(label="API", pct=api_pct, reset_str=reset_str),
        ]
        pd = ProviderData("Cursor", spent=float(total_pct), limit=100.0, currency="")
        pd._rows = rows
        return pd
    except Exception as e:
        log.debug("fetch_cursor failed: %s", e)
        return ProviderData("Cursor", error=str(e)[:80])


# Registry: config_key -> (display_name, fetch_fn)
# chatgpt_cookies / copilot_cookies / cursor_cookies are cookie-based;
# others are API key-based.
PROVIDER_REGISTRY: dict[str, tuple[str, callable]] = {
    "chatgpt_cookies": ("ChatGPT",     fetch_chatgpt),
    "copilot_cookies": ("Copilot",     fetch_copilot),
    "cursor_cookies":  ("Cursor",      fetch_cursor),
    "openai_key":      ("OpenAI",      fetch_openai),
    "minimax_key":     ("MiniMax",     fetch_minimax),
    "glm_key":         ("GLM (Zhipu)", fetch_glm),
}

# Cookie-based optional providers (detected only when explicitly enabled)
COOKIE_PROVIDERS = {"chatgpt_cookies", "copilot_cookies", "cursor_cookies"}
COOKIE_DETECTORS: dict[str, tuple[callable, str]] = {}


# ── Claude Code local stats ───────────────────────────────────────────────────

CC_STATS_FILE = os.path.expanduser("~/.claude/stats-cache.json")


def fetch_claude_code_stats() -> dict | None:
    """Read Claude Code usage from ~/.claude/stats-cache.json (no network needed).

    Returns dict with today_messages, today_sessions, week_messages,
    week_sessions, week_tool_calls -- or None if the file doesn't exist.
    """
    if not os.path.exists(CC_STATS_FILE):
        return None
    try:
        with open(CC_STATS_FILE) as f:
            data = json.load(f)
        today = datetime.now().strftime("%Y-%m-%d")
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        entries = data.get("dailyActivity", [])
        today_e = next((e for e in entries if e["date"] == today), None)
        week_e  = [e for e in entries if e["date"] >= week_ago]
        return {
            "today_messages":   today_e["messageCount"]  if today_e else 0,
            "today_sessions":   today_e["sessionCount"]  if today_e else 0,
            "week_messages":    sum(e["messageCount"]  for e in week_e),
            "week_sessions":    sum(e["sessionCount"]  for e in week_e),
            "week_tool_calls":  sum(e["toolCallCount"] for e in week_e),
            "last_date": max((e["date"] for e in entries), default=None),
        }
    except Exception as e:
        log.debug("fetch_claude_code_stats failed: %s", e)
        return None


# ── Cookie detection ──────────────────────────────────────────────────────────

_keychain_warned = False  # show the dialog at most once per session


def _warn_keychain_once():
    """Show a one-time dialog before the macOS Keychain prompt appears."""
    global _keychain_warned
    if _keychain_warned:
        return
    _keychain_warned = True
    script_lines = [
        f'set infoUrl to "{COOKIE_PERMISSION_DOC_URL}"',
        'set dialogText to "AI Quota Bar needs one-time access to the '
        'browser session cookies it uses to read usage from supported AI '
        'providers." & return & return & '
        '"macOS may then show a security prompt. Click \\"Always Allow\\" '
        'so background refreshes can keep checking usage without asking '
        'every time." & return & return & '
        '"If you want the exact cookie list and permission details first, '
        'click Learn More."',
        'repeat',
        'set chosenButton to button returned of (display dialog dialogText '
        'with title "AI Quota Bar — One-time Setup" '
        'buttons {"Learn More", "Continue"} default button "Continue" '
        'with icon note)',
        'if chosenButton is "Learn More" then',
        'open location infoUrl',
        'else',
        'exit repeat',
        'end if',
        'end repeat',
    ]
    args = ["osascript"]
    for line in script_lines:
        args.extend(["-e", line])
    subprocess.run(args, capture_output=True, timeout=60)


_BROWSERS = (
    "firefox", "librewolf", "chrome", "arc", "brave",
    "edge", "chromium", "opera", "vivaldi", "safari",
)


def _detect_cookies_worker(domain: str, target: str, allowed: list[str], queue) -> None:
    """Run in a spawned child process. Isolates browser_cookie3 C-library
    crashes (libcrypto / sqlite segfaults on Chromium decryption) from the
    menu bar app. Posts the best cookie string (or None) onto `queue`.

    Picks the candidate with the latest `target` cookie expiry, tie-broken
    by longest cookie string (richest jar) so we use the freshest session
    when the user is logged into multiple browsers.
    """
    allowed_set = set(allowed)
    candidates: list[tuple[int, str]] = []
    try:
        import browser_cookie3  # type: ignore
        for name in _BROWSERS:
            fn = getattr(browser_cookie3, name, None)
            if fn is None:
                continue
            try:
                jar = fn(domain_name=domain)
                cookies = {x.name: x for x in jar}
                if target not in cookies:
                    continue
                expires = cookies[target].expires or 0
                selected = {k: c.value for k, c in cookies.items() if k in allowed_set}
                cookie_str = "; ".join(f"{k}={v}" for k, v in selected.items())
                candidates.append((expires, cookie_str))
            except Exception:
                pass
    except Exception:
        pass

    result = None
    if candidates:
        candidates.sort(key=lambda x: (x[0], len(x[1])), reverse=True)
        result = candidates[0][1]
    try:
        queue.put(result)
    except Exception:
        pass


def _detect_cookies_once(domain: str, target_cookie: str, provider_key: str) -> str | None:
    """Read browser cookies for one provider inside the current process."""
    allowlist = sorted(set(COOKIE_KEY_ALLOWLISTS.get(provider_key, ())) | {target_cookie})
    allowed_set = set(allowlist)
    candidates: list[tuple[int, str]] = []
    for name in _BROWSERS:
        fn = getattr(browser_cookie3, name, None)
        if fn is None:
            continue
        try:
            jar = fn(domain_name=domain)
            cookies = {x.name: x for x in jar}
            if target_cookie not in cookies:
                continue
            expires = cookies[target_cookie].expires or 0
            selected = {k: c.value for k, c in cookies.items() if k in allowed_set}
            cookie_str = "; ".join(f"{k}={v}" for k, v in selected.items())
            candidates.append((expires, cookie_str))
        except Exception:
            pass
    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[0], len(x[1])), reverse=True)
    return candidates[0][1]


def detect_cookies_for_provider(provider_key: str) -> CookieDetectResult:
    """Read cookies for a provider in the current process."""
    target = COOKIE_DETECTION_TARGETS.get(provider_key)
    if not target:
        return CookieDetectResult(
            provider_key=provider_key,
            status="error",
            error_type="KeyError",
            detail="Unsupported provider key",
        )
    if not _BROWSER_COOKIE3_OK:
        return CookieDetectResult(
            provider_key=provider_key,
            status="error",
            error_type="ImportError",
            detail="browser_cookie3 is not installed",
        )
    domain, target_cookie, _ = target
    try:
        cookie_str = _detect_cookies_once(domain, target_cookie, provider_key)
    except Exception as e:
        log.debug(
            "cookie-detect helper provider=%s failed type=%s",
            provider_key, e.__class__.__name__,
        )
        return CookieDetectResult(
            provider_key=provider_key,
            status="error",
            error_type=e.__class__.__name__,
            detail=str(e)[:120],
        )
    if cookie_str:
        return CookieDetectResult(
            provider_key=provider_key,
            status="ok",
            cookie_str=cookie_str,
        )
    return CookieDetectResult(provider_key=provider_key, status="not_found")


def run_cookie_detection_cli(provider_key: str) -> int:
    """CLI entrypoint used by the app bundle to isolate cookie reads."""
    result = detect_cookies_for_provider(provider_key)
    payload = {
        "provider_key": result.provider_key,
        "status": result.status,
    }
    if result.cookie_str:
        payload["cookie_str"] = result.cookie_str
    if result.error_type:
        payload["error_type"] = result.error_type
    if result.detail:
        payload["detail"] = result.detail
    print(json.dumps(payload))
    return 0 if result.status in {"ok", "not_found"} else 1


def _frozen_app_executable() -> str | None:
    resource_path = os.environ.get("RESOURCEPATH")
    argvzero = os.environ.get("ARGVZERO")
    if not resource_path or not argvzero:
        return None
    candidate = os.path.abspath(
        os.path.join(resource_path, "..", "MacOS", os.path.basename(argvzero))
    )
    if os.path.exists(candidate) and os.access(candidate, os.X_OK):
        return candidate
    return None


def detect_cookies_with_helper(provider_key: str) -> CookieDetectResult:
    """Run cookie detection in a helper process outside the GUI boot path."""
    if provider_key not in COOKIE_DETECTION_TARGETS:
        return CookieDetectResult(
            provider_key=provider_key,
            status="error",
            error_type="KeyError",
            detail="Unsupported provider key",
        )
    if not _BROWSER_COOKIE3_OK:
        return CookieDetectResult(
            provider_key=provider_key,
            status="error",
            error_type="ImportError",
            detail="browser_cookie3 is not installed",
        )

    frozen_executable = (
        _frozen_app_executable() if getattr(sys, "frozen", None) == "macosx_app" else None
    )
    if frozen_executable:
        cmd = [frozen_executable, "--detect-cookies", provider_key]
    else:
        main_path = getattr(sys.modules.get("__main__"), "__file__", None) or sys.argv[0]
        if main_path and os.path.exists(main_path):
            cmd = [sys.executable, main_path, "--detect-cookies", provider_key]
        else:
            cmd = [sys.executable, "-m", "aiquotabar", "--detect-cookies", provider_key]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=75,
        )
    except subprocess.TimeoutExpired:
        log.debug("cookie-detect helper provider=%s timed out", provider_key)
        return CookieDetectResult(
            provider_key=provider_key,
            status="error",
            error_type="TimeoutExpired",
            detail="Cookie detection helper timed out",
        )
    except Exception as e:
        log.debug(
            "cookie-detect helper provider=%s launch failed type=%s",
            provider_key, e.__class__.__name__,
        )
        return CookieDetectResult(
            provider_key=provider_key,
            status="error",
            error_type=e.__class__.__name__,
            detail=str(e)[:120],
        )

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    if not stdout:
        err_type = "EmptyOutput"
        log.debug(
            "cookie-detect helper provider=%s rc=%s status=%s stderr=%s",
            provider_key, proc.returncode, err_type, stderr[:120],
        )
        return CookieDetectResult(
            provider_key=provider_key,
            status="error",
            error_type=err_type,
            detail=stderr[:120] or "Cookie detection helper produced no output",
            returncode=proc.returncode,
        )

    try:
        payload = json.loads(stdout.splitlines()[-1])
    except json.JSONDecodeError:
        err_type = "JSONDecodeError"
        log.debug(
            "cookie-detect helper provider=%s rc=%s status=%s stdout=%s",
            provider_key, proc.returncode, err_type, stdout[:120],
        )
        return CookieDetectResult(
            provider_key=provider_key,
            status="error",
            error_type=err_type,
            detail="Cookie detection helper returned invalid JSON",
            returncode=proc.returncode,
        )

    result = CookieDetectResult(
        provider_key=provider_key,
        status=payload.get("status") or "error",
        cookie_str=payload.get("cookie_str"),
        error_type=payload.get("error_type"),
        detail=payload.get("detail"),
        returncode=proc.returncode,
    )
    log.debug(
        "cookie-detect helper provider=%s rc=%s status=%s found=%s error_type=%s",
        provider_key,
        proc.returncode,
        result.status,
        result.cookie_str is not None,
        result.error_type,
    )
    return result


def _auto_detect_cookies() -> str | None:
    """Detect claude.ai session cookies from the browser (crash-safe subprocess)."""
    if not _BROWSER_COOKIE3_OK:
        return None
    _warn_keychain_once()
    result = detect_cookies_with_helper("cookie_str")
    return result.cookie_str if result.status == "ok" else None


def _auto_detect_chatgpt_cookies() -> str | None:
    """Detect chatgpt.com session cookies from the browser (crash-safe subprocess)."""
    if not _BROWSER_COOKIE3_OK:
        return None
    result = detect_cookies_with_helper("chatgpt_cookies")
    return result.cookie_str if result.status == "ok" else None


def _auto_detect_copilot_cookies() -> str | None:
    """Detect github.com session cookies from the browser (crash-safe subprocess)."""
    if not _BROWSER_COOKIE3_OK:
        return None
    result = detect_cookies_with_helper("copilot_cookies")
    return result.cookie_str if result.status == "ok" else None


def _auto_detect_cursor_cookies() -> str | None:
    """Detect cursor.com session cookies from the browser (crash-safe subprocess)."""
    if not _BROWSER_COOKIE3_OK:
        return None
    result = detect_cookies_with_helper("cursor_cookies")
    return result.cookie_str if result.status == "ok" else None


COOKIE_DETECTORS = {
    "chatgpt_cookies": (_auto_detect_chatgpt_cookies, "ChatGPT"),
    "copilot_cookies": (_auto_detect_copilot_cookies, "Copilot"),
    "cursor_cookies": (_auto_detect_cursor_cookies, "Cursor"),
}
