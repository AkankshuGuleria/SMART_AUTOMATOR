"""
tests/test_monitoring.py — system metrics, app-usage tracking, autostart.

All OS access is faked: the foreground-window probe is a stub, the usage store
is an in-memory SQLite DB, and autostart writes into a temp APPDATA.
"""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from api.server import app
from monitoring import app_usage
from monitoring.app_usage import (
    AppUsageTracker,
    ForegroundApp,
    UsageStore,
    app_category,
    friendly_app_name,
    summarize,
)


class FakeProbe:
    def __init__(self):
        self.idle = 0.0
        self.app: ForegroundApp | None = ForegroundApp("Code.exe", "main.py - AUTOMATA")

    def idle_seconds(self):
        return self.idle

    def foreground(self):
        return self.app


@pytest.fixture
def store():
    s = UsageStore(":memory:")
    yield s
    s.close()


def _rows(store):
    return store.segments_between(0, 4e9)


# ─── Naming ──────────────────────────────────────────────────────────────────


def test_friendly_names_and_categories():
    assert friendly_app_name("Code.exe") == "VS Code"
    assert friendly_app_name("chrome.exe") == "Chrome"
    assert friendly_app_name("my_tool.exe") == "My Tool"
    assert app_category("VS Code") == "Development"
    assert app_category("Chrome") == "Browser"
    assert app_category("My Tool") == "Other"


# ─── Tracker state machine ───────────────────────────────────────────────────


def test_tracker_records_one_segment_per_focus_period(store):
    probe = FakeProbe()
    tracker = AppUsageTracker(store, probe=probe)
    t0 = 1_000_000.0
    for i in range(5):
        tracker.tick(t0 + i)
    probe.app = ForegroundApp("chrome.exe", "Docs")
    tracker.tick(t0 + 5)
    tracker.tick(t0 + 9)
    tracker._close_segment(t0 + 10)

    rows = _rows(store)
    assert [r["app"] for r in rows] == ["VS Code", "Chrome"]
    assert rows[0]["ended_at"] - rows[0]["started_at"] == pytest.approx(5)
    assert rows[1]["ended_at"] - rows[1]["started_at"] == pytest.approx(5)
    assert rows[0]["category"] == "Development"


def test_idle_time_is_not_counted(store):
    probe = FakeProbe()
    tracker = AppUsageTracker(store, probe=probe, idle_threshold=120)
    t0 = 2_000_000.0
    tracker.tick(t0)
    tracker.tick(t0 + 30)
    # User walked away at t0+30; at t0+200 the probe reports 170 s idle.
    probe.idle = 170
    tracker.tick(t0 + 200)
    assert tracker.idle is True
    rows = _rows(store)
    assert len(rows) == 1
    assert rows[0]["ended_at"] == pytest.approx(t0 + 30)

    # Activity resumes → a fresh segment opens.
    probe.idle = 0
    tracker.tick(t0 + 210)
    tracker._close_segment(t0 + 220)
    assert len(_rows(store)) == 2


def test_pause_stops_recording(store):
    probe = FakeProbe()
    tracker = AppUsageTracker(store, probe=probe)
    tracker.tick(10_000.0)
    tracker.tick(10_010.0)
    tracker.pause()
    tracker.tick(10_100.0)
    assert tracker.current is None
    assert len(_rows(store)) == 1


def test_window_titles_are_redacted(store):
    probe = FakeProbe()
    probe.app = ForegroundApp(
        "powershell.exe", "export TOKEN=ghp_abcdefghijklmnopqrstuvwxyz0123456789"  # pragma: allowlist secret
    )
    tracker = AppUsageTracker(store, probe=probe)
    tracker.tick(50_000.0)
    tracker._close_segment(50_010.0)
    title = _rows(store)[0]["title"]
    assert "ghp_abcdefghijklmnopqrstuvwxyz0123456789" not in title  # pragma: allowlist secret


def test_very_short_segments_are_dropped(store):
    probe = FakeProbe()
    tracker = AppUsageTracker(store, probe=probe)
    tracker.tick(70_000.0)
    probe.app = ForegroundApp("chrome.exe", "x")
    tracker.tick(70_000.5)  # VS Code had focus for 0.5 s
    tracker._close_segment(70_010.0)
    assert [r["app"] for r in _rows(store)] == ["Chrome"]


# ─── Summaries ───────────────────────────────────────────────────────────────


def test_summarize_clips_to_today_and_ranks_apps():
    now = datetime(2026, 10, 25, 15, 0, 0)
    midnight = datetime(2026, 10, 25).timestamp()
    segments = [
        # Started yesterday 23:00, ended today 01:00 → only 1 h counts today.
        {
            "app": "VS Code",
            "category": "Development",
            "title": "a.py",
            "started_at": midnight - 3600,
            "ended_at": midnight + 3600,
        },
        {
            "app": "Chrome",
            "category": "Browser",
            "title": "docs",
            "started_at": midnight + 7200,
            "ended_at": midnight + 7200 + 1800,
        },
        {
            "app": "VS Code",
            "category": "Development",
            "title": "b.py",
            "started_at": midnight + 10800,
            "ended_at": midnight + 10800 + 1800,
        },
    ]
    out = summarize(segments, "today", now)
    assert out["total_seconds"] == 3600 + 1800 + 1800
    assert [a["app"] for a in out["apps"]] == ["VS Code", "Chrome"]
    assert out["apps"][0]["seconds"] == 5400
    assert out["apps"][0]["sessions"] == 2
    assert out["focus_percent"] == pytest.approx(75.0)
    assert out["hourly"][0]["seconds"] == 3600
    assert out["hourly"][2]["seconds"] == 1800
    assert out["app_switches"] == 2
    assert out["longest_session"]["app"] == "VS Code"
    assert {c["category"] for c in out["categories"]} == {"Development", "Browser"}


def test_summarize_week_has_seven_daily_buckets():
    now = datetime(2026, 10, 25, 12, 0)
    seg_day = datetime(2026, 10, 22, 10, 0).timestamp()
    out = summarize(
        [
            {
                "app": "Slack",
                "category": "Communication",
                "title": "",
                "started_at": seg_day,
                "ended_at": seg_day + 600,
            }
        ],
        "week",
        now,
    )
    assert len(out["daily"]) == 7
    by_day = {d["day"]: d["seconds"] for d in out["daily"]}
    assert by_day["2026-10-22"] == 600
    assert out["daily"][0]["day"] == (now - timedelta(days=6)).strftime("%Y-%m-%d")


def test_summarize_uses_live_segment_instead_of_stale_row():
    now = datetime(2026, 10, 25, 12, 0)
    start = now.timestamp() - 300
    stale = {
        "app": "VS Code",
        "category": "Development",
        "title": "",
        "started_at": start,
        "ended_at": start + 30,
    }
    live = {
        "app": "VS Code",
        "category": "Development",
        "title": "",
        "started_at": start,
        "ended_at": now.timestamp(),
    }
    out = summarize([stale], "today", now, live)
    assert out["total_seconds"] == 300


def test_empty_summary_reports_zero_not_invented_data():
    out = summarize([], "month", datetime(2026, 10, 25, 9, 0))
    assert out["total_seconds"] == 0
    assert out["apps"] == []
    assert len(out["daily"]) == 30


# ─── API ─────────────────────────────────────────────────────────────────────


def test_usage_routes(monkeypatch, store):
    now = datetime.now().timestamp()
    store.open_segment("VS Code", "Code.exe", "x", now - 120)
    seg = store.open_segment("Chrome", "chrome.exe", "y", now - 60)
    store.extend_segment(seg, now - 10)
    monkeypatch.setattr(app_usage, "_store", store)
    monkeypatch.setattr(app_usage, "_tracker", None)

    client = TestClient(app)
    body = client.get("/usage/summary?range=today").json()
    assert body["total_seconds"] == 50
    assert body["apps"][0]["app"] == "Chrome"
    assert body["tracking"]["running"] is False

    assert client.get("/usage/summary?range=year").status_code == 422
    timeline = client.get("/usage/timeline").json()
    assert [s["app"] for s in timeline["segments"]] == ["Chrome"]
    assert client.post("/usage/tracking", json={"enabled": "yes"}).status_code == 422


def test_system_metrics_route_returns_live_numbers():
    body = TestClient(app).get("/system/metrics?processes=true").json()
    assert body["available"] is True
    assert 0 <= body["cpu"]["percent"] <= 100
    assert body["memory"]["total_gb"] > 0
    assert 0 <= body["memory"]["percent"] <= 100
    assert "devices" in body["gpu"]
    assert isinstance(body["processes"], list)
    assert body["history"], "history should contain at least the first sample"


# ─── Autostart ───────────────────────────────────────────────────────────────


def test_autostart_toggle_writes_and_removes_launcher(tmp_path, monkeypatch):
    import sys

    from automation import autostart

    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(sys, "platform", "win32")
    on = autostart.set_autostart(True)
    assert on["enabled"] is True
    launcher = (
        tmp_path
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
        / autostart.LAUNCHER_NAME
    )
    text = launcher.read_text(encoding="utf-8")
    assert "main.py" in text and ", 0, False" in text  # hidden window, no wait
    off = autostart.set_autostart(False)
    assert off["enabled"] is False
    assert not launcher.exists()


def test_app_percentages_never_exceed_100_for_short_sessions():
    now = datetime(2026, 10, 25, 12, 0)
    t = now.timestamp() - 3.6
    out = summarize(
        [
            {
                "app": "Claude",
                "category": "AI Assistants",
                "title": "",
                "started_at": t,
                "ended_at": now.timestamp(),
            }
        ],
        "today",
        now,
    )
    assert out["apps"][0]["percent"] == 100.0
