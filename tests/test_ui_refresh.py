from __future__ import annotations

from datetime import datetime

import aiquotabar.ui as ui
from aiquotabar.providers import LimitRow, ProviderData, UsageData


def test_fetch_snapshot_sets_last_updated_when_only_optional_provider_succeeds():
    fake = type("FakeApp", (), {})()
    fake._fetch_claude_snapshot = lambda: (
        None,
        {},
        ui.ProviderRefreshStatus(
            name="Claude",
            state="autodetect_failed",
            summary="No Claude browser session was found.",
            configured=False,
        ),
        False,
        None,
    )
    fake._fetch_providers = lambda: (
        [ProviderData("ChatGPT", spent=25.0, limit=100.0, currency="")],
        {
            "ChatGPT": ui.ProviderRefreshStatus(
                name="ChatGPT",
                state="ok",
                summary="Tracking normally.",
                configured=True,
            )
        },
    )

    snapshot = ui.AIQuotaBarApp._fetch_snapshot(fake)

    assert snapshot.claude_data is None
    assert [pd.name for pd in snapshot.provider_data] == ["ChatGPT"]
    assert snapshot.statuses["Claude"].state == "autodetect_failed"
    assert snapshot.statuses["ChatGPT"].state == "ok"
    assert isinstance(snapshot.last_updated, datetime)


def test_fetch_snapshot_preserves_optional_provider_data_when_claude_auth_fails():
    fake = type("FakeApp", (), {})()
    fake._fetch_claude_snapshot = lambda: (
        None,
        {},
        ui.ProviderRefreshStatus(
            name="Claude",
            state="auth_failed",
            summary="Claude session expired or was rejected.",
            configured=True,
        ),
        True,
        403,
    )
    fake._fetch_providers = lambda: (
        [ProviderData("Copilot", spent=75.0, limit=100.0, currency="")],
        {
            "Copilot": ui.ProviderRefreshStatus(
                name="Copilot",
                state="ok",
                summary="Tracking normally.",
                configured=True,
            )
        },
    )

    snapshot = ui.AIQuotaBarApp._fetch_snapshot(fake)

    assert snapshot.claude_auth_failed is True
    assert snapshot.claude_http_status == 403
    assert [pd.name for pd in snapshot.provider_data] == ["Copilot"]
    assert snapshot.statuses["Claude"].state == "auth_failed"
    assert snapshot.statuses["Copilot"].state == "ok"
    assert snapshot.last_updated is not None


def test_available_bar_segments_support_partial_success_without_claude():
    provider_data = [
        ProviderData("ChatGPT", spent=10.0, limit=100.0, currency=""),
        ProviderData("OpenAI", error="bad key"),
    ]
    provider_data[0]._rows = [LimitRow("Codex Tasks", 42, "resets soon")]

    available = ui._available_bar_segments(None, provider_data)

    assert available == {"ChatGPT": ("ChatGPT", 42, "")}


def test_available_bar_segments_include_claude_and_optional_providers():
    data = UsageData(
        session=LimitRow("Current Session", 35, "resets soon"),
        weekly_all=LimitRow("All Models", 96, "resets tomorrow"),
    )
    provider_data = [ProviderData("Copilot", spent=12.0, limit=300.0, currency="")]

    available = ui._available_bar_segments(data, provider_data)

    assert available["Claude"] == ("Claude", 35, " ·")
    assert available["Copilot"] == ("Copilot", 4, "")


def test_diagnostic_sections_include_grouped_missing_providers_and_configured_errors():
    statuses = {
        "Claude": ui.ProviderRefreshStatus(
            name="Claude",
            state="autodetect_failed",
            summary="No Claude browser session was found.",
            configured=False,
        ),
        "ChatGPT": ui.ProviderRefreshStatus(
            name="ChatGPT",
            state="missing_credentials",
            summary="ChatGPT is not enabled yet.",
            configured=False,
        ),
        "Cursor": ui.ProviderRefreshStatus(
            name="Cursor",
            state="fetch_failed",
            summary="Cursor request failed.",
            configured=True,
        ),
    }

    sections = ui._diagnostic_sections(statuses, include_missing=True)

    assert sections[0][0] == "Claude"
    assert sections[1][0] == "Cursor"
    assert sections[2][0] == "More Providers"
    assert "ChatGPT" in sections[2][2][1]


def test_diagnostic_sections_skip_missing_unconfigured_providers_when_data_exists():
    statuses = {
        "ChatGPT": ui.ProviderRefreshStatus(
            name="ChatGPT",
            state="missing_credentials",
            summary="ChatGPT is not enabled yet.",
            configured=False,
        ),
        "Cursor": ui.ProviderRefreshStatus(
            name="Cursor",
            state="fetch_failed",
            summary="Cursor request failed.",
            configured=True,
        ),
    }

    sections = ui._diagnostic_sections(statuses, include_missing=False)

    assert [name for name, _color, _lines in sections] == ["Cursor"]


def test_footer_metadata_lines_include_updated_and_version(monkeypatch):
    monkeypatch.setattr(ui, "get_display_version", lambda: "v1.6.1-29-gbb15f3e-dirty")

    updated_line, version_line = ui._footer_metadata_lines(datetime(2026, 4, 20, 14, 32))

    assert updated_line == "Updated 14:32"
    assert version_line == "Version v1.6.1-29-gbb15f3e-dirty"
