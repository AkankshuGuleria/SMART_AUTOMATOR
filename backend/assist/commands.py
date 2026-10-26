"""
assist/commands.py — recognise quick everyday commands and run them.

Used first by POST /chat and by the work bar (POST /assist). Anything not
recognised here returns None and goes to the normal chat path (project
questions, delegation, intents).

  play <x> [on spotify] · pause · resume · next · previous · volume up/down · mute
  what's playing · search <x> [on youtube|github|…] · google <x>
  open spotify|youtube|… (handled by the existing open-app intent)
  what's on my screen · explain the error on my screen · read <app>
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import webbrowser
from typing import Any
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

SEARCH_ENGINES = {
    "google": "https://www.google.com/search?q={}",
    "youtube": "https://www.youtube.com/results?search_query={}",
    "github": "https://github.com/search?q={}&type=repositories",
    "bing": "https://www.bing.com/search?q={}",
    "duckduckgo": "https://duckduckgo.com/?q={}",
    "stackoverflow": "https://stackoverflow.com/search?q={}",
    "stack overflow": "https://stackoverflow.com/search?q={}",
    "npm": "https://www.npmjs.com/search?q={}",
    "pypi": "https://pypi.org/search/?q={}",
    "maps": "https://www.google.com/maps/search/{}",
    "amazon": "https://www.amazon.in/s?k={}",
    "wikipedia": "https://en.wikipedia.org/w/index.php?search={}",
}
_ENGINES = "|".join(sorted((re.escape(k) for k in SEARCH_ENGINES), key=len, reverse=True))
_MUSIC = r"(?:\s+(?:the\s+)?(?:music|song|track|spotify|playback|player))?"

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("now_playing", re.compile(r"^(?:what(?:'s| is)\s+(?:playing|this song)|now playing|current song|which song is (?:this|playing))\??$", re.I)),
    ("pause", re.compile(rf"^(?:pause|stop){_MUSIC}$", re.I)),
    ("resume", re.compile(rf"^(?:resume|unpause|continue){_MUSIC}$|^play(?:\s+(?:the\s+)?(?:music|spotify))?$", re.I)),
    ("next", re.compile(r"^(?:next|skip)(?:\s+(?:the\s+)?(?:song|track))?(?:\s+on\s+spotify)?$|^play (?:the )?next (?:song|track)$", re.I)),
    ("previous", re.compile(r"^(?:previous|prev|last|go back)(?:\s+(?:song|track))?$|^play (?:the )?previous (?:song|track)$", re.I)),
    ("volume_up", re.compile(r"^(?:volume up|louder|turn (?:it|the volume) up|increase (?:the )?volume)$", re.I)),
    ("volume_down", re.compile(r"^(?:volume down|quieter|softer|turn (?:it|the volume) down|decrease (?:the )?volume|lower (?:the )?volume)$", re.I)),
    ("mute", re.compile(r"^(?:mute|unmute)(?:\s+(?:the\s+)?(?:sound|audio|volume))?$", re.I)),
    ("spotify_play", re.compile(r"^(?:play|put on|start)\s+(?P<q>.+?)\s+(?:on|in|using|from)\s+spotify$|^spotify\s+play\s+(?P<q2>.+)$", re.I)),
    ("search", re.compile(
        rf"^search\s+(?P<engine2>{_ENGINES})\s+for\s+(?P<q2>.+)$"
        rf"|^(?:search|look up|google)\s+(?:for\s+)?(?P<q>.+?)(?:\s+on\s+(?P<engine>{_ENGINES}))?$", re.I)),
    ("screen", re.compile(
        r"\b(?:on|in)\s+(?:my|the|this)\s+screen\b|\b(?:read|analy[sz]e|look at|check|scan)\s+(?:my|the|this)\s+screen\b"
        r"|^what(?:'s| is)\s+on\s+screen\??$", re.I)),
]
# "play <x>" without "on spotify" means Spotify when it is installed.
_PLAY_ANY = re.compile(r"^(?:play|put on)\s+(?P<q>.+)$", re.I)


def _spotify_installed() -> bool:
    """Store install exposes a `Spotify.exe` alias on PATH; the classic installer lives in %APPDATA%."""
    return bool(shutil.which("spotify")) or os.path.exists(os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe"))


def match(text: str) -> tuple[str, dict[str, str]] | None:
    """(command, args) for a quick command, or None."""
    t = " ".join((text or "").strip().rstrip(".!").split())
    if not t:
        return None
    for name, pattern in PATTERNS:
        m = pattern.search(t) if name == "screen" else pattern.match(t)
        if m:
            args = {k: v for k, v in m.groupdict().items() if v}
            if "q2" in args:
                args["q"] = args.pop("q2")
            if "engine2" in args:
                args["engine"] = args.pop("engine2")
            if name == "screen":
                args["q"] = t
                app = re.search(r"\b(?:read|in|on)\s+(?!my\b|the\b|this\b)([\w .-]+?)(?:\s+window)?$", t, re.I)
                if app and "screen" not in app.group(1).lower():
                    args["app"] = app.group(1)
            return name, args
    m = _PLAY_ANY.match(t)
    if m and _spotify_installed() and not re.search(r"\b(test|tests|build|server|script|video)\b", t, re.I):
        return "spotify_play", {"q": m.group("q")}
    return None


def web_search(query: str, engine: str | None = None) -> dict[str, Any]:
    engine = (engine or "google").lower()
    url = SEARCH_ENGINES.get(engine, SEARCH_ENGINES["google"]).format(quote_plus(query))
    try:
        opened = webbrowser.open(url, new=2)
    except Exception as exc:
        return {"success": False, "error": f"Could not open the browser: {exc}"}
    if not opened:
        return {"success": False, "error": "No default browser responded."}
    return {"success": True, "url": url, "message": f"Searching {engine.title()} for “{query}”."}


def run(text: str, project_id: str | None = None) -> dict[str, Any] | None:
    """Run a quick command. Returns {intent, reply, success, result} or None if not one."""
    found = match(text)
    if not found:
        return None
    name, args = found
    from assist import media

    try:
        if name in media.KEYS or name in {"resume"}:
            result = media.control(name)
        elif name == "now_playing":
            np = media.now_playing()
            result = {"success": np.get("ok", False), "now_playing": np, "error": np.get("error"),
                      "message": ("Now playing: " if np.get("playing") else "Paused: ") + media._describe(np)
                      if np.get("title") else "Nothing is playing."}
        elif name == "spotify_play":
            result = media.spotify_play(args.get("q", ""))
        elif name == "search":
            result = web_search(args["q"], args.get("engine"))
        elif name == "screen":
            from assist import screen

            result = screen.analyze(args.get("q", ""), args.get("app"))
            if result.get("success"):
                result["message"] = result["answer"] + f"\n\n_Read from: {result['window']['title']}_"
        else:
            return None
    except Exception as exc:
        logger.exception("assist command %s failed", name)
        result = {"success": False, "error": str(exc)}
    reply = result.get("message") if result.get("success") else f"Couldn't do that: {result.get('error', 'unknown error')}"
    return {"intent": f"assist_{name}", "reply": reply, "success": bool(result.get("success")), "result": result}
