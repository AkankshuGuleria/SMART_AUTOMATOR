"""
tests/test_assist.py — work bar / quick commands, chat-app hand-off, no-console guard.

No real keys, windows, Spotify or model: every OS effect is faked.
"""

import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from api.server import app
from assist import commands

client = TestClient(app)


@pytest.mark.parametrize("text,name,args", [
    ("pause", "pause", {}),
    ("pause the music", "pause", {}),
    ("play", "resume", {}),
    ("resume spotify", "resume", {}),
    ("next song", "next", {}),
    ("skip", "next", {}),
    ("previous track", "previous", {}),
    ("volume up", "volume_up", {}),
    ("turn it down", "volume_down", {}),
    ("mute", "mute", {}),
    ("what's playing?", "now_playing", {}),
    ("play arijit singh on spotify", "spotify_play", {"q": "arijit singh"}),
    ("spotify play lofi beats", "spotify_play", {"q": "lofi beats"}),
    ("search for fastapi websockets", "search", {"q": "fastapi websockets"}),
    ("search react hooks on youtube", "search", {"q": "react hooks", "engine": "youtube"}),
    ("search github for tauri tray", "search", {"q": "tauri tray", "engine": "github"}),
    ("google weather in delhi", "search", {"q": "weather in delhi"}),
    ("what's on my screen?", "screen", {}),
    ("explain the error on my screen", "screen", {}),
])
def test_quick_commands_are_recognised(text, name, args):
    found = commands.match(text)
    assert found is not None, text
    assert found[0] == name
    for k, v in args.items():
        assert found[1][k] == v


@pytest.mark.parametrize("text", [
    "run tests", "what did I work on yesterday?", "using antigravity build a landing page",
    "find the auth code", "explain this repo", "open vscode",
])
def test_project_requests_are_left_to_chat(text):
    assert commands.match(text) is None


def test_play_without_spotify_word_uses_spotify_when_installed(monkeypatch):
    monkeypatch.setattr(commands, "_spotify_installed", lambda: True)
    assert commands.match("play some lofi") == ("spotify_play", {"q": "some lofi"})
    assert commands.match("play the tests") is None
    monkeypatch.setattr(commands, "_spotify_installed", lambda: False)
    assert commands.match("play some lofi") is None


def test_chat_runs_quick_commands_without_a_project(monkeypatch):
    monkeypatch.setattr("assist.media.control", lambda action: {"success": True, "message": f"did {action}"})
    body = client.post("/chat", json={"message": "next song"}).json()
    assert body["intent"] == "assist_next" and body["reply"] == "did next"


def test_assist_endpoint_falls_back_to_chat():
    body = client.post("/assist", json={"text": "hello there"}).json()
    assert body["handled_by"] == "chat"


def test_search_opens_the_right_url(monkeypatch):
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda url, new=0: opened.append(url) or True)
    r = commands.run("search react hooks on youtube")
    assert r["success"] and opened == ["https://www.youtube.com/results?search_query=react+hooks"]


def test_media_keys_refused_when_input_disabled():
    from assist import media

    r = media.control("next")  # conftest sets AUTOMATA_DISABLE_DESKTOP_INPUT=1
    assert r["success"] is False and "disabled" in r["error"]


def test_screen_analysis_reads_the_window_behind_automata(monkeypatch):
    from assist import screen
    from automation import win32

    windows = [
        win32.WindowInfo(hwnd=1, title="AUTOMATA", exe="app.exe", pid=1),
        win32.WindowInfo(hwnd=2, title="main.py - VS Code", exe="Code.exe", pid=2),
    ]
    monkeypatch.setattr(win32, "top_level_windows", lambda: windows)
    monkeypatch.setattr(win32, "IS_WINDOWS", True)
    monkeypatch.setattr(win32, "capture_window", lambda hwnd: b"png-of-%d" % hwnd)
    monkeypatch.setattr("automation.ocr.run_ocr", lambda path: {"ok": True, "text": "NameError: name 'x' is not defined"})
    asked = {}

    def fake_reasoning(system, user, memories, reasoning_mode=None):
        asked["user"] = user
        return "x is used before it is assigned; define it first."

    monkeypatch.setattr("ai.bedrock_client.invoke_reasoning", fake_reasoning)
    r = screen.analyze("explain the error")
    assert r["success"] and r["window"]["title"] == "main.py - VS Code"
    assert "NameError" in asked["user"] and "explain the error" in asked["user"]


# ─── chat-app hand-off ───────────────────────────────────────────────────────


def test_chat_app_delivery_refuses_when_input_disabled():
    from automation import chat_apps

    r = chat_apps.deliver("antigravity", "build it", folder=None)
    assert r["success"] is False and "disabled" in r["error"]


def test_antigravity_handoff_uses_the_verified_chat_box(monkeypatch):
    from automation import agent_bridge, chat_apps

    monkeypatch.setattr(chat_apps, "installed", lambda key: key == "antigravity")
    calls = {}

    def fake_deliver(key, prompt, folder=None, submit=False):
        calls.update(key=key, folder=folder, submit=submit)
        return {"success": True, "submitted": True, "steps": ["Focused the chat box", "Sent with enter"]}

    monkeypatch.setattr(chat_apps, "deliver", fake_deliver)
    r = agent_bridge.AgentBridge().send_prompt("antigravity", "Build a page", {"repo_path": "D:\\p"})
    assert r.status == "ok" and r.executed is True and "Sent to Antigravity IDE" in r.output
    assert calls == {"key": "antigravity", "folder": "D:\\p", "submit": True}


def test_failed_handoff_is_reported_and_prompt_copied(monkeypatch):
    from automation import agent_bridge, chat_apps

    monkeypatch.setattr(chat_apps, "installed", lambda key: key == "antigravity")
    monkeypatch.setattr(chat_apps, "deliver", lambda *a, **k: {
        "success": False, "error": "Could not find the chat box in Antigravity IDE.", "steps": []})
    monkeypatch.setattr("automation.desktop.copy_text", lambda text: {"success": True})
    r = agent_bridge.AgentBridge().send_prompt("antigravity", "Build a page", {})
    assert r.status == "error" and "chat box" in r.output and "clipboard" in r.output


def test_contains_prompt_is_whitespace_insensitive():
    from automation.chat_apps import _contains_prompt

    assert _contains_prompt("# Task\r\n  Build   a page\n\nmore", "# Task\nBuild a page\n\nmore")
    assert not _contains_prompt("\n", "# Task\nBuild a page")


# ─── no console windows ──────────────────────────────────────────────────────


def test_creation_flags_hide_consoles_but_keep_requested_ones():
    from automation.no_console import CREATE_NO_WINDOW, creation_flags

    assert creation_flags(0) == CREATE_NO_WINDOW
    assert creation_flags(0x10) == 0x10  # CREATE_NEW_CONSOLE asked for: visible terminal stays
    assert creation_flags(0x8) == 0x8  # DETACHED_PROCESS


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_installed_guard_applies_to_every_popen(monkeypatch):
    from automation import no_console

    assert no_console.install() is True  # api.server already installed it; idempotent
    seen = {}
    real = subprocess.Popen._execute_child

    def spy(self, args, executable, preexec_fn, close_fds, pass_fds, cwd, env, startupinfo,
            creationflags, *rest):
        seen["flags"] = creationflags
        return real(self, args, executable, preexec_fn, close_fds, pass_fds, cwd, env, startupinfo,
                    creationflags, *rest)

    monkeypatch.setattr(subprocess.Popen, "_execute_child", spy)
    subprocess.run(["cmd", "/c", "exit 0"], capture_output=True)
    assert seen["flags"] & no_console.CREATE_NO_WINDOW
