from __future__ import annotations

from datetime import datetime, timedelta, timezone

import aiquotabar.providers as providers


def test_parse_cookie_string_accepts_bare_session_key():
    assert providers.parse_cookie_string("abc123") == {"sessionKey": "abc123"}


def test_parse_cookie_string_parses_pairs_and_ignores_malformed_parts():
    raw = " sessionKey = abc123 ; malformed ; lastActiveOrg = org_1 ; x=y=z "

    parsed = providers.parse_cookie_string(raw)

    assert parsed == {
        "sessionKey": "abc123",
        "lastActiveOrg": "org_1",
        "x": "y=z",
    }


def test_minimize_cookie_map_and_string_use_provider_allowlists():
    cookies = {
        "sessionKey": "abc",
        "lastActiveOrg": "org_1",
        "routingHint": "route_1",
        "cf_clearance": "cf",
        "ignored": "nope",
    }

    minimized = providers.minimize_cookie_map("cookie_str", cookies)
    minimized_str = providers.minimize_cookie_string(
        "chatgpt_cookies",
        "__Secure-next-auth.session-token=token; ignored=value",
    )

    assert minimized == {
        "sessionKey": "abc",
        "lastActiveOrg": "org_1",
        "routingHint": "route_1",
        "cf_clearance": "cf",
    }
    assert minimized_str == "__Secure-next-auth.session-token=token"


def test_minimize_cookie_map_passthrough_for_unknown_provider():
    cookies = {"a": "1", "b": "2"}
    assert providers.minimize_cookie_map("unknown", cookies) == cookies


def test_strip_cf_cookies_removes_cloudflare_values():
    cookies = {
        "sessionKey": "abc",
        "cf_clearance": "cf",
        "__cf_bm": "bm",
        "_cfuvid": "uv",
    }
    assert providers._strip_cf_cookies(cookies) == {"sessionKey": "abc"}


def test_fmt_reset_handles_past_near_and_distant_times():
    now = datetime.now(timezone.utc)

    assert providers._fmt_reset((now - timedelta(minutes=1)).timestamp()) == "resets soon"

    near = providers._fmt_reset((now + timedelta(hours=2, minutes=5)).timestamp())
    assert near.startswith("resets in 2h")

    distant = providers._fmt_reset((now + timedelta(days=2)).timestamp())
    assert distant.startswith("resets ")
    assert ":" in distant


def test_row_builds_limit_row_and_handles_missing_buckets():
    row = providers._row(
        {"five_hour": {"utilization": 12.6, "resets_at": None}},
        "five_hour",
        "Current Session",
    )

    assert row is not None
    assert row.label == "Current Session"
    assert row.pct == 13
    assert row.reset_str == ""
    assert providers._row({}, "five_hour", "Current Session") is None


def test_parse_wham_window_and_usage_build_rows():
    payload = {
        "rate_limit": {
            "primary_window": {
                "used_percent": 42,
                "reset_at": (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp(),
            }
        },
        "code_review_rate_limit": {
            "primary_window": {
                "used_percent": 65,
                "reset_at": (datetime.now(timezone.utc) + timedelta(hours=2)).timestamp(),
            }
        },
        "additional_rate_limits": [
            {
                "name": "daily_bonus",
                "primary_window": {
                    "used_percent": 10,
                    "reset_at": (
                        datetime.now(timezone.utc) + timedelta(hours=3)
                    ).timestamp(),
                },
            }
        ],
    }

    row = providers._parse_wham_window(payload["rate_limit"], "Codex Tasks")
    data = providers._parse_wham_usage(payload)

    assert row is not None
    assert row.label == "Codex Tasks"
    assert row.pct == 42
    assert data.name == "ChatGPT"
    assert data.spent == 65.0
    assert data.limit == 100.0
    assert [r.label for r in data._rows] == [
        "Codex Tasks",
        "Code Review",
        "Daily Bonus",
    ]


def test_parse_wham_usage_returns_error_when_no_rows():
    data = providers._parse_wham_usage({})
    assert data.error == "No rate limit data in response"


def test_fetch_chatgpt_returns_not_logged_in_when_token_missing(monkeypatch):
    monkeypatch.setattr(providers, "_chatgpt_access_token", lambda _cookies: None)

    data = providers.fetch_chatgpt("__Secure-next-auth.session-token=token")

    assert data.name == "ChatGPT"
    assert data.error == "Not logged in"


def test_fetch_chatgpt_uses_token_and_parses_response(monkeypatch):
    captured = {}

    def fake_api_get(url, headers, cookies=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["cookies"] = cookies
        return {
            "rate_limit": {
                "primary_window": {
                    "used_percent": 20,
                    "reset_at": (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp(),
                }
            },
            "code_review_rate_limit": {
                "primary_window": {
                    "used_percent": 75,
                    "reset_at": (datetime.now(timezone.utc) + timedelta(hours=2)).timestamp(),
                }
            },
        }

    monkeypatch.setattr(providers, "_chatgpt_access_token", lambda _cookies: "bearer-token")
    monkeypatch.setattr(providers, "_api_get", fake_api_get)

    data = providers.fetch_chatgpt("__Secure-next-auth.session-token=token")

    assert data.error is None
    assert data.spent == 75.0
    assert captured["url"] == "https://chatgpt.com/backend-api/wham/usage"
    assert captured["headers"]["Authorization"] == "Bearer bearer-token"
    assert captured["cookies"] == {"__Secure-next-auth.session-token": "token"}
