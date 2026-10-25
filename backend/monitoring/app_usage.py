"""
monitoring/app_usage.py — background foreground-app usage tracker.

Owns:    Recording which application has focus and for how long, plus the
         daily/weekly/monthly usage analysis served to the UI.
Never:   Stores keystrokes, screen content, or anything beyond the focused
         app's name and (redacted, truncated) window title. Nothing leaves
         this machine.

Storage: a local SQLite file (default %LOCALAPPDATA%\\AUTOMATA\\usage.db).
One row per continuous focus segment, so a full working day is a few hundred
rows, not tens of thousands of samples. The open segment is checkpointed
every FLUSH_INTERVAL_S so a crash loses at most that much time.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

POLL_INTERVAL_S = 1.0
IDLE_THRESHOLD_S = 120.0  # no keyboard/mouse input for 2 min → idle, not counted
FLUSH_INTERVAL_S = 30.0
MIN_SEGMENT_S = 1.0
TITLE_MAX = 160

# Friendly names for common executables (lower-case exe → label).
_APP_NAMES: dict[str, str] = {
    "code.exe": "VS Code",
    "cursor.exe": "Cursor",
    "windsurf.exe": "Windsurf",
    "devenv.exe": "Visual Studio",
    "pycharm64.exe": "PyCharm",
    "idea64.exe": "IntelliJ IDEA",
    "webstorm64.exe": "WebStorm",
    "sublime_text.exe": "Sublime Text",
    "notepad++.exe": "Notepad++",
    "notepad.exe": "Notepad",
    "windowsterminal.exe": "Windows Terminal",
    "wt.exe": "Windows Terminal",
    "powershell.exe": "PowerShell",
    "pwsh.exe": "PowerShell",
    "cmd.exe": "Command Prompt",
    "mintty.exe": "Git Bash",
    "chrome.exe": "Chrome",
    "msedge.exe": "Edge",
    "firefox.exe": "Firefox",
    "brave.exe": "Brave",
    "opera.exe": "Opera",
    "explorer.exe": "File Explorer",
    "slack.exe": "Slack",
    "discord.exe": "Discord",
    "teams.exe": "Teams",
    "ms-teams.exe": "Teams",
    "zoom.exe": "Zoom",
    "whatsapp.exe": "WhatsApp",
    "telegram.exe": "Telegram",
    "outlook.exe": "Outlook",
    "olk.exe": "Outlook",
    "winword.exe": "Word",
    "excel.exe": "Excel",
    "powerpnt.exe": "PowerPoint",
    "onenote.exe": "OneNote",
    "notion.exe": "Notion",
    "obsidian.exe": "Obsidian",
    "figma.exe": "Figma",
    "spotify.exe": "Spotify",
    "vlc.exe": "VLC",
    "steam.exe": "Steam",
    "postman.exe": "Postman",
    "docker desktop.exe": "Docker Desktop",
    "githubdesktop.exe": "GitHub Desktop",
    "claude.exe": "Claude",
    "chatgpt.exe": "ChatGPT",
    "automata.exe": "AUTOMATA",
    "app.exe": "AUTOMATA",
}

_CATEGORIES: dict[str, str] = {
    **{
        name: "Development"
        for name in (
            "VS Code",
            "Cursor",
            "Windsurf",
            "Visual Studio",
            "PyCharm",
            "IntelliJ IDEA",
            "WebStorm",
            "Sublime Text",
            "Notepad++",
            "Windows Terminal",
            "PowerShell",
            "Command Prompt",
            "Git Bash",
            "Postman",
            "Docker Desktop",
            "GitHub Desktop",
            "AUTOMATA",
        )
    },
    **{name: "Browser" for name in ("Chrome", "Edge", "Firefox", "Brave", "Opera")},
    **{
        name: "Communication"
        for name in ("Slack", "Discord", "Teams", "Zoom", "WhatsApp", "Telegram", "Outlook")
    },
    **{
        name: "Productivity"
        for name in (
            "Word",
            "Excel",
            "PowerPoint",
            "OneNote",
            "Notion",
            "Obsidian",
            "Figma",
            "Notepad",
            "File Explorer",
        )
    },
    **{name: "AI Assistants" for name in ("Claude", "ChatGPT")},
    **{name: "Entertainment" for name in ("Spotify", "VLC", "Steam")},
}

RANGE_DAYS = {"today": 1, "week": 7, "month": 30}


def friendly_app_name(exe: str) -> str:
    key = (exe or "").lower()
    if key in _APP_NAMES:
        return _APP_NAMES[key]
    base = key[:-4] if key.endswith(".exe") else key
    return base.replace("_", " ").replace("-", " ").title() or "Unknown"


def app_category(app: str) -> str:
    return _CATEGORIES.get(app, "Other")


def default_db_path() -> Path:
    override = os.environ.get("AUTOMATA_DATA_DIR")
    if override:
        base = Path(override)
    elif os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "AUTOMATA"
    else:
        base = Path.home() / ".automata"
    base.mkdir(parents=True, exist_ok=True)
    return base / "usage.db"


# ─── Storage ──────────────────────────────────────────────────────────────────


class UsageStore:
    """Thread-safe SQLite store for focus segments."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = str(path or default_db_path())
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            if self.path != ":memory:":
                self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS usage_segments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    app TEXT NOT NULL,
                    exe TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    category TEXT NOT NULL DEFAULT 'Other',
                    started_at REAL NOT NULL,
                    ended_at REAL NOT NULL
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_usage_ended ON usage_segments(ended_at)"
            )

    def open_segment(self, app: str, exe: str, title: str, started_at: float) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO usage_segments(app, exe, title, category, started_at, ended_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (app, exe, title, app_category(app), started_at, started_at),
            )
            return int(cur.lastrowid)

    def extend_segment(self, segment_id: int, ended_at: float, title: str | None = None) -> None:
        with self._lock:
            if title is None:
                self._conn.execute(
                    "UPDATE usage_segments SET ended_at = ? WHERE id = ?", (ended_at, segment_id)
                )
            else:
                self._conn.execute(
                    "UPDATE usage_segments SET ended_at = ?, title = ? WHERE id = ?",
                    (ended_at, title, segment_id),
                )

    def drop_segment(self, segment_id: int) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM usage_segments WHERE id = ?", (segment_id,))

    def segments_between(self, start: float, end: float) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT app, exe, title, category, started_at, ended_at FROM usage_segments "
                "WHERE ended_at > ? AND started_at < ? ORDER BY started_at",
                (start, end),
            ).fetchall()
        return [dict(r) for r in rows]

    def prune_older_than(self, cutoff: float) -> int:
        with self._lock:
            cur = self._conn.execute("DELETE FROM usage_segments WHERE ended_at < ?", (cutoff,))
            return cur.rowcount or 0

    def close(self) -> None:
        with self._lock:
            self._conn.close()


# ─── Foreground window probe (Windows) ────────────────────────────────────────


@dataclass
class ForegroundApp:
    exe: str
    title: str


class _WindowsProbe:
    """Minimal ctypes wrapper: foreground window owner + seconds since last input."""

    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes

        self._ctypes = ctypes
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

        self._lii = LASTINPUTINFO()
        self._lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        self._pid_cache: dict[int, str] = {}
        self._wintypes = wintypes

    def idle_seconds(self) -> float:
        if not self._user32.GetLastInputInfo(self._ctypes.byref(self._lii)):
            return 0.0
        tick = self._kernel32.GetTickCount() & 0xFFFFFFFF
        return max(0.0, ((tick - self._lii.dwTime) & 0xFFFFFFFF) / 1000.0)

    def foreground(self) -> ForegroundApp | None:
        hwnd = self._user32.GetForegroundWindow()
        if not hwnd:
            return None
        pid = self._wintypes.DWORD()
        self._user32.GetWindowThreadProcessId(hwnd, self._ctypes.byref(pid))
        length = self._user32.GetWindowTextLengthW(hwnd)
        buf = self._ctypes.create_unicode_buffer(min(length, 512) + 1)
        self._user32.GetWindowTextW(hwnd, buf, len(buf))
        exe = self._exe_for_pid(int(pid.value))
        if not exe:
            return None
        return ForegroundApp(exe=exe, title=buf.value)

    def _exe_for_pid(self, pid: int) -> str:
        if pid in self._pid_cache:
            return self._pid_cache[pid]
        name = ""
        try:
            import psutil

            name = psutil.Process(pid).name()
        except Exception:
            name = ""
        if len(self._pid_cache) > 512:
            self._pid_cache.clear()
        self._pid_cache[pid] = name
        return name


def _clean_title(title: str) -> str:
    try:
        from memory.capture import redact_secrets

        title = redact_secrets(title)
    except Exception:
        pass
    title = " ".join(title.split())
    return title[:TITLE_MAX]


# ─── Tracker thread ───────────────────────────────────────────────────────────


class AppUsageTracker(threading.Thread):
    """Daemon thread that records continuous focus segments."""

    def __init__(
        self, store: UsageStore, probe: Any | None = None, idle_threshold: float = IDLE_THRESHOLD_S
    ) -> None:
        super().__init__(name="app-usage-tracker", daemon=True)
        self.store = store
        self._probe = probe
        self._idle_threshold = idle_threshold
        self._stop_event = threading.Event()
        self._paused = threading.Event()
        self._state_lock = threading.Lock()
        self._segment_id: int | None = None
        self._segment_key: str | None = None
        self._segment_started = 0.0
        self._segment_title = ""
        self._last_flush = 0.0
        self.current: dict[str, Any] | None = None
        self.idle = False
        self.error: str | None = None

    @property
    def paused(self) -> bool:
        return self._paused.is_set()

    def pause(self) -> None:
        self._paused.set()
        self._close_segment(time.time())

    def resume(self) -> None:
        self._paused.clear()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        if self._probe is None:
            try:
                self._probe = _WindowsProbe()
            except Exception as exc:
                self.error = f"Foreground tracking unsupported here ({type(exc).__name__})"
                logger.info("app usage tracker disabled: %s", self.error)
                return
        logger.info("app usage tracker started | db=%s", self.store.path)
        # Keep the file small: drop anything older than 90 days at startup.
        try:
            self.store.prune_older_than(time.time() - 90 * 86400)
        except Exception:
            pass
        while not self._stop_event.wait(POLL_INTERVAL_S):
            try:
                self.tick(time.time())
            except Exception as exc:
                logger.debug("app usage tick failed — %s", exc)
        self._close_segment(time.time())

    def tick(self, now: float) -> None:
        """One poll: extend, switch, or close the current focus segment."""
        if self._paused.is_set():
            return
        idle_for = self._probe.idle_seconds()
        if idle_for >= self._idle_threshold:
            if not self.idle:
                # Idle started idle_for seconds ago; do not count that time.
                self._close_segment(now - idle_for)
                self.idle = True
            return
        self.idle = False

        fg = self._probe.foreground()
        if fg is None:
            self._close_segment(now)
            return
        app = friendly_app_name(fg.exe)
        key = fg.exe.lower()
        title = _clean_title(fg.title)
        with self._state_lock:
            same = key == self._segment_key and self._segment_id is not None
        if same:
            if title != self._segment_title or now - self._last_flush >= FLUSH_INTERVAL_S:
                self.store.extend_segment(self._segment_id, now, title)
                self._segment_title = title
                self._last_flush = now
        else:
            self._close_segment(now)
            with self._state_lock:
                self._segment_id = self.store.open_segment(app, fg.exe, title, now)
                self._segment_key = key
                self._segment_started = now
                self._segment_title = title
                self._last_flush = now
        self.current = {
            "app": app,
            "category": app_category(app),
            "title": title,
            "since": self._segment_started,
        }

    def _close_segment(self, ended_at: float) -> None:
        with self._state_lock:
            seg_id, started = self._segment_id, self._segment_started
            self._segment_id = None
            self._segment_key = None
            self.current = None
        if seg_id is None:
            return
        ended_at = max(ended_at, started)
        if ended_at - started < MIN_SEGMENT_S:
            self.store.drop_segment(seg_id)
        else:
            self.store.extend_segment(seg_id, ended_at)

    def live_segment(self, now: float) -> dict[str, Any] | None:
        """The open segment extended to *now* (DB row lags by up to FLUSH_INTERVAL_S)."""
        with self._state_lock:
            if self._segment_id is None or self.current is None:
                return None
            return {
                "app": self.current["app"],
                "category": self.current["category"],
                "title": self._segment_title,
                "started_at": self._segment_started,
                "ended_at": now,
                "segment_id": self._segment_id,
            }


# ─── Analysis ─────────────────────────────────────────────────────────────────


def _range_start(range_name: str, now: datetime) -> datetime:
    days = RANGE_DAYS.get(range_name, 1)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight - timedelta(days=days - 1)


def summarize(
    segments: list[dict[str, Any]],
    range_name: str,
    now: datetime | None = None,
    live: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Aggregate focus segments into per-app, per-category and time-bucket totals.

    Times are local. Segments are clipped to the range, so a session that
    started before midnight only counts its part inside today.
    """
    now = now or datetime.now()
    start_dt = _range_start(range_name, now)
    start, end = start_dt.timestamp(), now.timestamp()

    rows = list(segments)
    if live:
        # Replace the stale DB copy of the open segment with the live one.
        rows = [
            r
            for r in rows
            if not (r["started_at"] == live["started_at"] and r["app"] == live["app"])
        ]
        rows.append(live)

    per_app: dict[str, dict[str, Any]] = {}
    per_category: dict[str, float] = {}
    hourly = [0.0] * 24
    days = RANGE_DAYS.get(range_name, 1)
    daily: dict[str, float] = {
        (start_dt + timedelta(days=i)).strftime("%Y-%m-%d"): 0.0 for i in range(days)
    }
    longest: dict[str, Any] | None = None
    total = 0.0
    switches = 0

    for seg in rows:
        s = max(float(seg["started_at"]), start)
        e = min(float(seg["ended_at"]), end)
        if e <= s:
            continue
        dur = e - s
        total += dur
        switches += 1
        app = seg["app"]
        entry = per_app.setdefault(
            app,
            {
                "app": app,
                "category": seg.get("category") or app_category(app),
                "seconds": 0.0,
                "sessions": 0,
                "top_title": "",
                "_titles": {},
            },
        )
        entry["seconds"] += dur
        entry["sessions"] += 1
        title = seg.get("title") or ""
        if title:
            entry["_titles"][title] = entry["_titles"].get(title, 0.0) + dur
        per_category[entry["category"]] = per_category.get(entry["category"], 0.0) + dur
        if longest is None or dur > longest["seconds"]:
            longest = {"app": app, "seconds": round(dur), "started_at": s}

        # Spread the segment over hour/day buckets.
        cursor = s
        while cursor < e:
            local = datetime.fromtimestamp(cursor)
            bucket_end = (
                local.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            ).timestamp()
            chunk_end = min(bucket_end, e)
            hourly[local.hour] += chunk_end - cursor
            day_key = local.strftime("%Y-%m-%d")
            if day_key in daily:
                daily[day_key] += chunk_end - cursor
            cursor = chunk_end

    apps = []
    for entry in sorted(per_app.values(), key=lambda x: x["seconds"], reverse=True):
        titles = entry.pop("_titles")
        if titles:
            entry["top_title"] = max(titles.items(), key=lambda kv: kv[1])[0]
        entry["percent"] = round(entry["seconds"] / total * 100, 1) if total else 0.0
        entry["seconds"] = round(entry["seconds"])
        apps.append(entry)

    categories = [
        {
            "category": cat,
            "seconds": round(sec),
            "percent": round(sec / total * 100, 1) if total else 0.0,
        }
        for cat, sec in sorted(per_category.items(), key=lambda kv: kv[1], reverse=True)
    ]
    dev_seconds = per_category.get("Development", 0.0)
    return {
        "range": range_name if range_name in RANGE_DAYS else "today",
        "start": start,
        "end": end,
        "total_seconds": round(total),
        "focus_percent": round(dev_seconds / total * 100, 1) if total else 0.0,
        "app_switches": max(0, switches - 1),
        "longest_session": longest,
        "apps": apps[:20],
        "categories": categories,
        "hourly": [{"hour": h, "seconds": round(v)} for h, v in enumerate(hourly)],
        "daily": [{"day": d, "seconds": round(v)} for d, v in daily.items()],
    }


# ─── Process-wide singleton ───────────────────────────────────────────────────

_tracker: AppUsageTracker | None = None
_store: UsageStore | None = None
_singleton_lock = threading.Lock()


def tracking_disabled_by_env() -> bool:
    return os.environ.get("AUTOMATA_DISABLE_USAGE_TRACKER", "").strip() in {"1", "true", "yes"}


def start_tracker() -> AppUsageTracker | None:
    """Start the background tracker once (Windows only)."""
    global _tracker, _store
    if tracking_disabled_by_env():
        logger.info("app usage tracker disabled by AUTOMATA_DISABLE_USAGE_TRACKER")
        return None
    with _singleton_lock:
        if _tracker is not None and _tracker.is_alive():
            return _tracker
        if sys.platform != "win32":
            logger.info("app usage tracker: foreground tracking is Windows-only")
            return None
        try:
            _store = _store or UsageStore()
        except Exception as exc:
            logger.warning("app usage tracker: cannot open store — %s", exc)
            return None
        _tracker = AppUsageTracker(_store)
        _tracker.start()
        return _tracker


def stop_tracker() -> None:
    global _tracker
    with _singleton_lock:
        if _tracker is not None:
            _tracker.stop()
            _tracker.join(timeout=3)
            _tracker = None


def get_store() -> UsageStore | None:
    global _store
    with _singleton_lock:
        if _store is None:
            try:
                _store = UsageStore()
            except Exception as exc:
                logger.warning("app usage store unavailable — %s", exc)
                return None
        return _store


def tracker_status() -> dict[str, Any]:
    t = _tracker
    running = bool(t and t.is_alive())
    return {
        "supported": sys.platform == "win32",
        "running": running,
        "paused": bool(t and t.paused),
        "idle": bool(t and t.idle),
        "current": t.current if running and t else None,
        "disabled_by_env": tracking_disabled_by_env(),
        "error": t.error if t else None,
        "db_path": _store.path if _store else None,
        "idle_threshold_seconds": IDLE_THRESHOLD_S,
    }


def set_tracking(enabled: bool) -> dict[str, Any]:
    t = _tracker
    if enabled:
        if t is None or not t.is_alive():
            start_tracker()
        elif t.paused:
            t.resume()
    elif t is not None:
        t.pause()
    return tracker_status()


def usage_summary(range_name: str = "today") -> dict[str, Any]:
    store = get_store()
    now = datetime.now()
    live = _tracker.live_segment(now.timestamp()) if _tracker else None
    if store is None:
        result = summarize([], range_name, now, live)
        result["error"] = "Usage store unavailable"
        return result
    start = _range_start(range_name, now).timestamp()
    segments = store.segments_between(start, now.timestamp())
    result = summarize(segments, range_name, now, live)
    result["tracking"] = tracker_status()
    return result


def usage_timeline(day: str | None = None, limit: int = 500) -> dict[str, Any]:
    """Raw focus segments for one local day (for a timeline strip)."""
    store = get_store()
    try:
        base = datetime.strptime(day, "%Y-%m-%d") if day else datetime.now()
    except ValueError:
        base = datetime.now()
    start_dt = base.replace(hour=0, minute=0, second=0, microsecond=0)
    start, end = start_dt.timestamp(), (start_dt + timedelta(days=1)).timestamp()
    segments = store.segments_between(start, end) if store else []
    live = _tracker.live_segment(time.time()) if _tracker else None
    if live and start <= live["started_at"] < end:
        segments = [s for s in segments if s["started_at"] != live["started_at"]]
        segments.append({k: v for k, v in live.items() if k != "segment_id"})
    out = []
    for seg in segments[-limit:]:
        s, e = max(seg["started_at"], start), min(seg["ended_at"], end)
        if e > s:
            out.append(
                {
                    "app": seg["app"],
                    "category": seg.get("category") or app_category(seg["app"]),
                    "title": seg.get("title", ""),
                    "start": s,
                    "end": e,
                    "seconds": round(e - s),
                }
            )
    return {"day": start_dt.strftime("%Y-%m-%d"), "segments": out}
