from __future__ import annotations

from datetime import datetime, timedelta, timezone

import aiquotabar.history as history


def test_append_history_prunes_old_entries():
    now = datetime.now(timezone.utc).timestamp()
    old = now - history.HISTORY_MAX_AGE - 10
    recent = now - 60
    data = {"claude": [{"t": old, "pct": 10}, {"t": recent, "pct": 20}]}

    history._append_history(data, "claude", 30)

    assert [entry["pct"] for entry in data["claude"]] == [20, 30]


def test_append_history_clears_history_on_large_reset_drop():
    now = datetime.now(timezone.utc).timestamp()
    data = {"claude": [{"t": now - 60, "pct": 90}]}

    history._append_history(data, "claude", 40)

    assert len(data["claude"]) == 1
    assert data["claude"][0]["pct"] == 40


def test_calc_burn_rate_returns_none_for_insufficient_data():
    assert history._calc_burn_rate({}, "claude") is None
    assert history._calc_burn_rate({"claude": [{"t": 1, "pct": 10}]}, "claude") is None


def test_calc_burn_rate_returns_none_for_short_span():
    now = datetime.now(timezone.utc).timestamp()
    data = {"claude": [{"t": now - 120, "pct": 10}, {"t": now, "pct": 30}]}

    assert history._calc_burn_rate(data, "claude") is None


def test_calc_burn_rate_is_positive_for_rising_usage():
    now = datetime.now(timezone.utc).timestamp()
    data = {
        "claude": [
            {"t": now - 900, "pct": 10},
            {"t": now - 600, "pct": 25},
            {"t": now - 300, "pct": 40},
            {"t": now, "pct": 55},
        ]
    }

    rate = history._calc_burn_rate(data, "claude")

    assert rate is not None
    assert rate > 0


def test_calc_eta_minutes_uses_burn_rate(monkeypatch):
    data = {"claude": [{"t": 1, "pct": 40}]}
    monkeypatch.setattr(history, "_calc_burn_rate", lambda *_args, **_kwargs: 2.0)

    assert history._calc_eta_minutes(data, "claude") == 30


def test_calc_eta_minutes_returns_none_for_negative_or_distant_eta(monkeypatch):
    data = {"claude": [{"t": 1, "pct": 10}]}
    monkeypatch.setattr(history, "_calc_burn_rate", lambda *_args, **_kwargs: -1.0)
    assert history._calc_eta_minutes(data, "claude") is None

    monkeypatch.setattr(history, "_calc_burn_rate", lambda *_args, **_kwargs: 0.1)
    assert history._calc_eta_minutes(data, "claude") is None


def test_fmt_eta_formats_minutes_and_hours():
    assert history._fmt_eta(47) == "47 min"
    assert history._fmt_eta(90) == "1h 30 min"


def test_sparkline_handles_empty_flat_and_varied_data():
    assert history._sparkline({}, "claude") == ""
    flat = {"claude": [{"t": 1, "pct": 20}, {"t": 2, "pct": 20}, {"t": 3, "pct": 21}]}
    assert history._sparkline(flat, "claude") == ""

    varied = {"claude": [{"t": 1, "pct": 10}, {"t": 2, "pct": 40}, {"t": 3, "pct": 70}]}
    sparkline = history._sparkline(varied, "claude")
    assert sparkline
    assert len(sparkline) == 3


def test_weekly_sparkline_handles_flat_and_varied_data():
    assert history._weekly_sparkline([]) == ""
    assert history._weekly_sparkline([{"peak_pct": 20}, {"peak_pct": 21}]) == ""

    sparkline = history._weekly_sparkline(
        [{"peak_pct": 10}, {"peak_pct": 35}, {"peak_pct": 70}]
    )
    assert sparkline
    assert len(sparkline) == 3


def test_init_record_and_fetch_today_stats():
    conn = history._init_history_db()
    history._record_sample(conn, "claude", 42)
    conn.commit()

    today = history._get_today_stats(conn)

    assert today["claude"]["peak_pct"] == 42
    assert today["claude"]["avg_pct"] == 42
    assert today["claude"]["samples"] == 1


def test_rollup_and_week_queries():
    conn = history._init_history_db()
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).timestamp()
    older = (datetime.now(timezone.utc) - timedelta(days=3)).timestamp()

    conn.execute("INSERT INTO samples (ts, key, pct) VALUES (?, ?, ?)", (older, "claude", 80))
    conn.execute(
        "INSERT INTO samples (ts, key, pct) VALUES (?, ?, ?)",
        (older + 60, "claude", 97),
    )
    conn.execute(
        "INSERT INTO samples (ts, key, pct) VALUES (?, ?, ?)",
        (yesterday, "claude", 50),
    )
    conn.execute(
        "INSERT INTO samples (ts, key, pct) VALUES (?, ?, ?)",
        (yesterday + 60, "claude", 60),
    )
    conn.commit()

    history._rollup_daily_stats(conn)

    weekly = history._get_weekly_stats(conn, "claude")
    hits = history._get_week_limit_hits(conn, "claude")

    assert len(weekly) >= 2
    assert any(day["peak_pct"] == 97 for day in weekly)
    assert hits >= 1


def test_fetch_history_data_returns_summary_and_provider_rollups():
    conn = history._init_history_db()
    two_days_ago = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d")

    conn.execute(
        "INSERT INTO daily_stats (date, key, peak_pct, avg_pct, limit_hits, samples) VALUES (?, ?, ?, ?, ?, ?)",
        (two_days_ago, "chatgpt_rate_limit", 70, 50, 1, 3),
    )
    now = datetime.now(timezone.utc).timestamp()
    conn.execute("INSERT INTO samples (ts, key, pct) VALUES (?, ?, ?)", (now, "claude", 40))
    conn.commit()

    data = history._fetch_history_data(conn)

    assert data is not None
    assert data["summary"]["total_days"] >= 1
    labels = {provider["label"] for provider in data["providers"]}
    assert "Claude" in labels
    assert "ChatGPT Rate Limit" in labels
    assert data["summary"]["highest"][1] >= data["summary"]["lowest"][1]
