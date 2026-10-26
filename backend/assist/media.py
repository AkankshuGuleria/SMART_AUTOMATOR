"""
assist/media.py — play/pause/next/previous/volume for whatever is playing, and Spotify search-and-play.

Owns:    Media keys (system-wide: they reach Spotify, YouTube in a browser or any
         player without focusing it), "now playing" from the Windows media
         session, and Spotify "play <something>": open a Spotify search, press
         the top result's Play button through UI Automation, confirm playback.
Never:   Claims a song started without seeing the player switch to playing.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

from automation import win32

logger = logging.getLogger(__name__)

_SCRIPT = Path(__file__).with_name("media_session.ps1")
KEYS = {
    "play_pause": "media_play_pause", "pause": "media_play_pause", "play": "media_play_pause",
    "resume": "media_play_pause", "next": "media_next", "previous": "media_prev",
    "stop": "media_stop", "volume_up": "volume_up", "volume_down": "volume_down", "mute": "volume_mute",
}
SPOTIFY_EXE = "spotify.exe"


def now_playing() -> dict[str, Any]:
    """{ok, app, title, artist, status} from the Windows media session."""
    if not win32.IS_WINDOWS:
        return {"ok": False, "error": "Only available on Windows."}
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(_SCRIPT)],
            capture_output=True, text=True, timeout=10, encoding="utf-8", errors="replace",
        )
        data = json.loads((out.stdout or "").strip() or "{}")
    except Exception as exc:
        return {"ok": False, "error": f"Could not read the media session: {exc}"}
    if data.get("none") or not data:
        return {"ok": True, "playing": False, "title": None, "status": "none"}
    data["ok"] = True
    data["playing"] = data.get("status") == "Playing"
    return data


def _describe(np: dict[str, Any]) -> str:
    if not np.get("title"):
        return "Nothing is playing."
    who = f" — {np['artist']}" if np.get("artist") else ""
    app = " (Spotify)" if "spotify" in str(np.get("app", "")).lower() else ""
    return f"{np['title']}{who}{app}"


def control(action: str) -> dict[str, Any]:
    """Press a media/volume key and report the player's new state when it can be read."""
    key = KEYS.get(action)
    if key is None:
        return {"success": False, "error": f"Unknown media action '{action}'."}
    if win32.input_disabled():
        return {"success": False, "error": "Desktop input is disabled (AUTOMATA_DISABLE_DESKTOP_INPUT=1)."}
    before = now_playing() if action not in {"volume_up", "volume_down", "mute"} else {}
    if action in {"play", "resume"} and before.get("playing"):
        return {"success": True, "message": f"Already playing: {_describe(before)}", "now_playing": before}
    if action == "pause" and before.get("ok") and not before.get("playing"):
        return {"success": True, "message": "Already paused.", "now_playing": before}
    times = 5 if action in {"volume_up", "volume_down"} else 1  # one press is ~2 %
    for _ in range(times):
        win32.send_chord(key)
    if action in {"volume_up", "volume_down", "mute"}:
        return {"success": True, "message": {"volume_up": "Volume up.", "volume_down": "Volume down.",
                                             "mute": "Toggled mute."}[action]}
    time.sleep(0.9)
    after = now_playing()
    if not after.get("ok") or not after.get("title"):
        return {"success": True, "verified": False, "message": "Sent the media key (no player reported its state)."}
    changed = (after.get("status") != before.get("status")) or (after.get("title") != before.get("title"))
    verb = {"next": "Next", "previous": "Previous"}.get(action, "Playing" if after.get("playing") else "Paused")
    return {"success": True, "verified": changed, "now_playing": after,
            "message": f"{verb}: {_describe(after)}" if changed else f"No change reported — {_describe(after)}"}


# ─── Spotify ────────────────────────────────────────────────────────────────


def _spotify_window():
    return next((w for w in win32.top_level_windows() if w.exe.lower() == SPOTIFY_EXE), None)


def _buttons(hwnd: int):
    from automation import uia

    u, mod = uia._client(), uia._mod()
    root = u.ElementFromHandle(hwnd)
    found = root.FindAll(mod.TreeScope_Descendants,
                         u.CreatePropertyCondition(mod.UIA_ControlTypePropertyId, mod.UIA_ButtonControlTypeId))
    return [found.GetElement(i) for i in range(found.Length)]


def _player_state(hwnd: int) -> str | None:
    """'playing' / 'paused' from the player bar's Play/Pause button (bottom of the window)."""
    rect = win32.window_rect(hwnd)
    bottom = (rect[1] + rect[3]) if rect else 10**6
    for b in _buttons(hwnd):
        try:
            name = (b.CurrentName or "").strip().lower()
            r = b.CurrentBoundingRectangle
            if name in {"play", "pause"} and r.top > bottom - 160 and not b.CurrentIsOffscreen:
                return "playing" if name == "pause" else "paused"
        except Exception:
            continue
    return None


def _top_result_play(hwnd: int):
    """The first Play button in the search results (reading order), not the player bar's."""
    rect = win32.window_rect(hwnd)
    bottom = (rect[1] + rect[3]) if rect else 10**6
    found = []
    for b in _buttons(hwnd):
        try:
            name = (b.CurrentName or "").strip()
            r = b.CurrentBoundingRectangle
            if (name == "Play" or name.startswith("Play ")) and not b.CurrentIsOffscreen and r.top < bottom - 160:
                found.append((r.top, r.left, name, b))
        except Exception:
            continue
    found.sort(key=lambda x: (x[0], x[1]))
    return (found[0][2], found[0][3]) if found else (None, None)


def spotify_play(query: str, wait: float = 12.0) -> dict[str, Any]:
    """Search Spotify for *query* and play the top result, verified by the player state."""
    query = (query or "").strip()
    if not query:
        return control("play")
    if not win32.IS_WINDOWS:
        return {"success": False, "error": "Only available on Windows."}
    if win32.input_disabled():
        return {"success": False, "error": "Desktop input is disabled (AUTOMATA_DISABLE_DESKTOP_INPUT=1)."}
    try:
        os.startfile(f"spotify:search:{quote(query)}")  # type: ignore[attr-defined]
    except OSError as exc:
        return {"success": False, "error": f"Spotify is not installed or did not open: {exc}"}
    deadline = time.monotonic() + wait
    window, name, button = None, None, None
    while time.monotonic() < deadline:
        window = _spotify_window()
        if window:
            name, button = _top_result_play(window.hwnd)
            if button is not None:
                break
        time.sleep(0.7)
    if window is None:
        return {"success": False, "error": "Spotify did not open."}
    if button is None:
        return {"success": False, "error": f"Spotify opened the search for '{query}', but no result had a Play button."}
    from automation.chat_apps import _invoke

    if not _invoke(button):
        return {"success": False, "error": "Found the result but could not press its Play button."}
    for _ in range(8):
        time.sleep(0.6)
        if _player_state(window.hwnd) == "playing":
            np = now_playing()
            return {"success": True, "verified": True, "now_playing": np,
                    "message": f"Playing on Spotify: {_describe(np)}" if np.get("title") else
                               f"Playing '{name.removeprefix('Play ') if name else query}' on Spotify."}
    return {"success": False, "verified": False,
            "error": f"Pressed Play on '{name}', but Spotify did not start playing."}
