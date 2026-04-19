from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone

import aiquotabar.providers as providers


class FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        base = cls(2026, 4, 18, 12, 0, 0)
        if tz is not None:
            return base.replace(tzinfo=tz)
        return base


class FakeResponse:
    def __init__(self, payload=None, *, raise_error=None, json_error=None):
        self._payload = payload if payload is not None else {}
        self._raise_error = raise_error
        self._json_error = json_error

    def raise_for_status(self):
        if self._raise_error is not None:
            raise self._raise_error

    def json(self):
        if self._json_error is not None:
            raise self._json_error
        return self._payload


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


def test_warn_keychain_once_opens_setup_dialog_with_learn_more(monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return None

    monkeypatch.setattr(providers, "_keychain_warned", False)
    monkeypatch.setattr(providers.subprocess, "run", fake_run)

    providers._warn_keychain_once()
    providers._warn_keychain_once()

    assert len(calls) == 1
    args, kwargs = calls[0]
    script = " ".join(args)
    assert args[0] == "osascript"
    assert providers.COOKIE_PERMISSION_DOC_URL in script
    assert 'buttons {"Learn More", "Continue"}' in script
    assert '\\"Always Allow\\"' in script
    assert kwargs == {"capture_output": True, "timeout": 60}


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


def test_fetch_openai_returns_spend_limit_and_expected_billing_window(monkeypatch):
    calls = []

    def fake_api_get(url, headers, cookies=None):
        calls.append((url, headers, cookies))
        if url.endswith("/subscription"):
            return {"hard_limit_usd": 25}
        return {"total_usage": 1234}

    monkeypatch.setattr(providers, "_api_get", fake_api_get)
    monkeypatch.setattr(providers, "datetime", FixedDateTime)

    data = providers.fetch_openai("sk-test")

    assert data.name == "OpenAI"
    assert data.spent == 12.34
    assert data.limit == 25.0
    assert data.currency == "USD"
    assert data.period == "this month"
    assert len(calls) == 2
    assert calls[0][0] == "https://api.openai.com/v1/dashboard/billing/subscription"
    assert calls[1][0] == (
        "https://api.openai.com/v1/dashboard/billing/usage"
        "?start_date=2026-04-01&end_date=2026-04-19"
    )
    assert calls[0][1]["Authorization"] == "Bearer sk-test"
    assert calls[1][1]["Authorization"] == "Bearer sk-test"
    assert calls[0][2] is None
    assert calls[1][2] is None


def test_fetch_openai_uses_system_limit_and_defaults_missing_usage(monkeypatch):
    calls = []

    def fake_api_get(url, headers, cookies=None):
        calls.append(url)
        if url.endswith("/subscription"):
            return {"system_hard_limit_usd": 15}
        return {}

    monkeypatch.setattr(providers, "_api_get", fake_api_get)
    monkeypatch.setattr(providers, "datetime", FixedDateTime)

    data = providers.fetch_openai("sk-test")

    assert data.limit == 15.0
    assert data.spent == 0.0
    assert len(calls) == 2


def test_fetch_openai_returns_none_limit_when_hard_limit_is_zero(monkeypatch):
    def fake_api_get(url, headers, cookies=None):
        if url.endswith("/subscription"):
            return {"hard_limit_usd": 0}
        return {"total_usage": 500}

    monkeypatch.setattr(providers, "_api_get", fake_api_get)
    monkeypatch.setattr(providers, "datetime", FixedDateTime)

    data = providers.fetch_openai("sk-test")

    assert data.spent == 5.0
    assert data.limit is None


def test_fetch_openai_returns_truncated_error_when_api_call_fails(monkeypatch):
    message = "x" * 120

    def fake_api_get(url, headers, cookies=None):
        raise RuntimeError(message)

    monkeypatch.setattr(providers, "_api_get", fake_api_get)

    data = providers.fetch_openai("sk-test")

    assert data.name == "OpenAI"
    assert data.error == message[:80]


def test_fetch_copilot_parses_response_and_strips_cf_cookies(monkeypatch):
    captured = {}

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return FakeResponse(
            {"discountQuantity": 12, "userPremiumRequestEntitlement": 300}
        )

    monkeypatch.setattr(providers.requests, "get", fake_get)

    data = providers.fetch_copilot(
        "user_session=abc; logged_in=yes; cf_clearance=cf; __cf_bm=bm"
    )

    assert data.name == "Copilot"
    assert data.spent == 12.0
    assert data.limit == 300.0
    assert data.currency == ""
    assert data.period == "this month"
    assert captured["url"] == "https://github.com/settings/billing/copilot_usage_card"
    assert captured["kwargs"]["headers"]["Accept"] == "application/json"
    assert (
        captured["kwargs"]["headers"]["Referer"]
        == "https://github.com/settings/billing/premium_requests_usage"
    )
    assert captured["kwargs"]["timeout"] == 10
    assert captured["kwargs"]["impersonate"] == providers._IMPERSONATE
    assert captured["kwargs"]["cookies"] == {
        "user_session": "abc",
        "logged_in": "yes",
    }


def test_fetch_copilot_defaults_missing_values_and_zero_limit(monkeypatch):
    monkeypatch.setattr(providers.requests, "get", lambda *args, **kwargs: FakeResponse({}))

    data = providers.fetch_copilot("user_session=abc")

    assert data.spent == 0.0
    assert data.limit is None


def test_fetch_copilot_returns_error_from_http_or_json_failures(monkeypatch):
    monkeypatch.setattr(
        providers.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(raise_error=RuntimeError("request failed")),
    )
    http_data = providers.fetch_copilot("user_session=abc")
    assert http_data.error == "request failed"

    monkeypatch.setattr(
        providers.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(json_error=RuntimeError("bad json")),
    )
    json_data = providers.fetch_copilot("user_session=abc")
    assert json_data.error == "bad json"


def test_fetch_cursor_parses_rows_and_request_metadata(monkeypatch):
    captured = {}
    future = (datetime.now(timezone.utc) + timedelta(days=3, hours=4)).isoformat()

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return FakeResponse(
            {
                "individualUsage": {
                    "plan": {
                        "autoPercentUsed": 12.6,
                        "apiPercentUsed": 67.6,
                        "totalPercentUsed": 45.5,
                    }
                },
                "billingCycleEnd": future,
            }
        )

    monkeypatch.setattr(providers.requests, "get", fake_get)

    data = providers.fetch_cursor(
        "WorkosCursorSessionToken=abc; cf_clearance=cf; __cf_bm=bm"
    )

    assert data.name == "Cursor"
    assert data.spent == 46.0
    assert data.limit == 100.0
    assert data.currency == ""
    assert [row.label for row in data._rows] == ["Auto", "API"]
    assert [row.pct for row in data._rows] == [13, 68]
    assert data._rows[0].reset_str
    assert data._rows[1].reset_str == data._rows[0].reset_str
    assert captured["url"] == "https://cursor.com/api/usage-summary"
    assert captured["kwargs"]["headers"]["Accept"] == "application/json"
    assert (
        captured["kwargs"]["headers"]["Referer"]
        == "https://cursor.com/dashboard?tab=usage"
    )
    assert captured["kwargs"]["timeout"] == 10
    assert captured["kwargs"]["impersonate"] == providers._IMPERSONATE
    assert captured["kwargs"]["cookies"] == {"WorkosCursorSessionToken": "abc"}


def test_fetch_cursor_defaults_to_zeroes_when_plan_missing(monkeypatch):
    monkeypatch.setattr(
        providers.requests,
        "get",
        lambda *args, **kwargs: FakeResponse({"billingCycleEnd": None}),
    )

    data = providers.fetch_cursor("WorkosCursorSessionToken=abc")

    assert data.error is None
    assert data.spent == 0.0
    assert data.limit == 100.0
    assert [row.pct for row in data._rows] == [0, 0]
    assert [row.reset_str for row in data._rows] == ["", ""]


def test_fetch_cursor_ignores_invalid_or_past_billing_cycle_end(monkeypatch):
    monkeypatch.setattr(
        providers.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(
            {
                "individualUsage": {"plan": {"autoPercentUsed": 10, "apiPercentUsed": 20}},
                "billingCycleEnd": "not-a-date",
            }
        ),
    )
    invalid = providers.fetch_cursor("WorkosCursorSessionToken=abc")
    assert [row.reset_str for row in invalid._rows] == ["", ""]

    past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    monkeypatch.setattr(
        providers.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(
            {
                "individualUsage": {"plan": {"autoPercentUsed": 10, "apiPercentUsed": 20}},
                "billingCycleEnd": past,
            }
        ),
    )
    past_data = providers.fetch_cursor("WorkosCursorSessionToken=abc")
    assert [row.reset_str for row in past_data._rows] == ["", ""]


def test_fetch_cursor_returns_error_from_http_or_json_failures(monkeypatch):
    monkeypatch.setattr(
        providers.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(raise_error=RuntimeError("cursor failed")),
    )
    http_data = providers.fetch_cursor("WorkosCursorSessionToken=abc")
    assert http_data.error == "cursor failed"

    monkeypatch.setattr(
        providers.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(json_error=RuntimeError("bad cursor json")),
    )
    json_data = providers.fetch_cursor("WorkosCursorSessionToken=abc")
    assert json_data.error == "bad cursor json"


def test_detect_cookies_for_provider_reports_success_and_not_found(monkeypatch):
    monkeypatch.setattr(providers, "_BROWSER_COOKIE3_OK", True)
    monkeypatch.setattr(
        providers,
        "_detect_cookies_once",
        lambda domain, target, provider_key: "sessionKey=abc" if provider_key == "cookie_str" else None,
    )

    success = providers.detect_cookies_for_provider("cookie_str")
    not_found = providers.detect_cookies_for_provider("chatgpt_cookies")

    assert success.status == "ok"
    assert success.cookie_str == "sessionKey=abc"
    assert not_found.status == "not_found"
    assert not_found.cookie_str is None


def test_detect_cookies_for_provider_reports_unsupported_and_helper_errors(monkeypatch):
    monkeypatch.setattr(providers, "_BROWSER_COOKIE3_OK", True)

    unsupported = providers.detect_cookies_for_provider("nope")

    def boom(*_args, **_kwargs):
        raise RuntimeError("cookie store unavailable")

    monkeypatch.setattr(providers, "_detect_cookies_once", boom)
    failed = providers.detect_cookies_for_provider("cookie_str")

    assert unsupported.status == "error"
    assert unsupported.error_type == "KeyError"
    assert failed.status == "error"
    assert failed.error_type == "RuntimeError"


def test_run_cookie_detection_cli_prints_json(monkeypatch, capsys):
    monkeypatch.setattr(
        providers,
        "detect_cookies_for_provider",
        lambda provider_key: providers.CookieDetectResult(
            provider_key=provider_key,
            status="ok",
            cookie_str="sessionKey=abc",
        ),
    )

    rc = providers.run_cookie_detection_cli("cookie_str")
    payload = json.loads(capsys.readouterr().out.strip())

    assert rc == 0
    assert payload == {
        "provider_key": "cookie_str",
        "status": "ok",
        "cookie_str": "sessionKey=abc",
    }


def test_detect_cookies_with_helper_parses_success_and_error_payloads(monkeypatch):
    monkeypatch.setattr(providers, "_BROWSER_COOKIE3_OK", True)
    monkeypatch.setattr(providers.sys, "executable", "/tmp/fake-python")

    outputs = [
        subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({"status": "ok", "cookie_str": "sessionKey=abc"}),
            stderr="",
        ),
        subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout=json.dumps({"status": "error", "error_type": "RuntimeError"}),
            stderr="traceback",
        ),
    ]

    def fake_run(*args, **kwargs):
        return outputs.pop(0)

    monkeypatch.setattr(providers.subprocess, "run", fake_run)

    success = providers.detect_cookies_with_helper("cookie_str")
    failed = providers.detect_cookies_with_helper("cookie_str")

    assert success.status == "ok"
    assert success.cookie_str == "sessionKey=abc"
    assert failed.status == "error"
    assert failed.error_type == "RuntimeError"
    assert failed.returncode == 1


def test_detect_cookies_with_helper_distinguishes_invalid_json_and_timeout(monkeypatch):
    monkeypatch.setattr(providers, "_BROWSER_COOKIE3_OK", True)

    invalid = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout="not-json",
        stderr="",
    )

    monkeypatch.setattr(providers.subprocess, "run", lambda *args, **kwargs: invalid)
    invalid_result = providers.detect_cookies_with_helper("cookie_str")

    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd=["python"], timeout=75)

    monkeypatch.setattr(providers.subprocess, "run", timeout)
    timeout_result = providers.detect_cookies_with_helper("cookie_str")

    assert invalid_result.status == "error"
    assert invalid_result.error_type == "JSONDecodeError"
    assert timeout_result.status == "error"
    assert timeout_result.error_type == "TimeoutExpired"


def test_detect_cookies_with_helper_uses_app_executable_in_frozen_mode(monkeypatch):
    monkeypatch.setattr(providers, "_BROWSER_COOKIE3_OK", True)
    monkeypatch.setattr(providers.sys, "frozen", "macosx_app", raising=False)
    monkeypatch.setenv("RESOURCEPATH", "/tmp/MyApp.app/Contents/Resources")
    monkeypatch.setenv("ARGVZERO", "/tmp/MyApp.app/Contents/MacOS/AIQuotaBar")

    captured = {}

    def fake_exists(path):
        return path == "/tmp/MyApp.app/Contents/MacOS/AIQuotaBar"

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout=json.dumps({"status": "not_found"}),
            stderr="",
        )

    monkeypatch.setattr(providers.os.path, "exists", fake_exists)
    monkeypatch.setattr(providers.os, "access", lambda path, mode: path == "/tmp/MyApp.app/Contents/MacOS/AIQuotaBar")
    monkeypatch.setattr(providers.subprocess, "run", fake_run)

    result = providers.detect_cookies_with_helper("cookie_str")

    assert captured["cmd"] == [
        "/tmp/MyApp.app/Contents/MacOS/AIQuotaBar",
        "--detect-cookies",
        "cookie_str",
    ]
    assert result.status == "not_found"
