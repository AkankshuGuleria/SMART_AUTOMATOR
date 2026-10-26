"""
tests/test_desktop.py — Phase 0: desktop actions must verify, and fail honestly.

Every Win32 call is faked: no real window is focused, no key is pressed and
the screen is never read.
"""

from unittest.mock import MagicMock

import pytest

from automation import desktop, ocr, win32
from automation.win32 import WindowInfo

NOTEPAD = WindowInfo(hwnd=101, pid=11, exe="notepad.exe", title="notes.txt - Notepad")
CHROME_CHATGPT = WindowInfo(hwnd=202, pid=22, exe="chrome.exe", title="ChatGPT - Google Chrome")
AUTOMATA_UI = WindowInfo(hwnd=303, pid=33, exe="msedge.exe", title="AUTOMATA - Edge")
TERMINAL = WindowInfo(hwnd=404, pid=44, exe="WindowsTerminal.exe", title="PowerShell")


@pytest.fixture
def fake_desktop(monkeypatch):
    """A scriptable desktop: set .windows, .front, and whether activate works."""
    state = MagicMock()
    state.windows = [NOTEPAD, CHROME_CHATGPT, TERMINAL]
    state.front = TERMINAL
    state.activate_ok = True
    state.keys = []

    def activate(hwnd, timeout=1.5):
        if state.activate_ok:
            state.front = next(w for w in state.windows if w.hwnd == hwnd)
        return state.activate_ok

    monkeypatch.setattr(win32, "IS_WINDOWS", True)
    monkeypatch.setattr(win32, "input_disabled", lambda: False)
    monkeypatch.setattr(win32, "top_level_windows", lambda: list(state.windows))
    monkeypatch.setattr(win32, "foreground", lambda: state.front)
    monkeypatch.setattr(win32, "activate", activate)
    monkeypatch.setattr(win32, "send_chord", lambda chord: state.keys.append((chord, state.front.exe)))
    monkeypatch.setattr(desktop.time, "sleep", lambda s: None)
    return state


# ─── focus ───────────────────────────────────────────────────────────────────


def test_focus_succeeds_only_when_windows_confirms(fake_desktop):
    result = desktop.focus("notepad")
    assert result["success"] is True
    assert result["window"]["exe"] == "notepad.exe"


def test_focus_reports_failure_when_windows_refuses(fake_desktop):
    fake_desktop.activate_ok = False
    result = desktop.focus("notepad")
    assert result["success"] is False
    assert "did not let" in result["error"]
    assert result["foreground"]["exe"] == "WindowsTerminal.exe"


def test_focus_missing_app_is_an_error(fake_desktop):
    result = desktop.focus("spotify")
    assert result["success"] is False
    assert "No open spotify window" in result["error"]


def test_focus_matches_multi_process_apps_by_window(fake_desktop):
    # Chrome runs many processes; only the one with a real window matters.
    assert desktop.focus("chrome")["window"]["hwnd"] == 202


# ─── keys / paste ────────────────────────────────────────────────────────────


def test_press_refuses_when_target_not_in_front(fake_desktop):
    result = desktop.press("ctrl+v", target_app="notepad")
    assert result["success"] is False
    assert fake_desktop.keys == []


def test_press_never_types_into_automata_itself(fake_desktop):
    fake_desktop.front = AUTOMATA_UI
    result = desktop.press("ctrl+v")
    assert result["success"] is False
    assert "AUTOMATA itself" in result["error"]
    assert fake_desktop.keys == []


def test_press_rejects_unlisted_chords(fake_desktop):
    assert desktop.press("alt+f4")["success"] is False
    assert fake_desktop.keys == []


def test_paste_into_named_app_focuses_then_pastes(fake_desktop):
    result = desktop.paste("notepad")
    assert result["success"] is True
    assert result["delivered_to"]["exe"] == "notepad.exe"
    assert fake_desktop.keys == [("ctrl+v", "notepad.exe")]


def test_paste_stops_when_focus_fails(fake_desktop):
    fake_desktop.activate_ok = False
    result = desktop.paste("notepad")
    assert result["success"] is False
    assert result["pasted"] is False
    assert fake_desktop.keys == []


def test_kill_switch_blocks_all_input(monkeypatch, fake_desktop):
    monkeypatch.setattr(win32, "input_disabled", lambda: True)
    assert desktop.press("enter")["success"] is False
    assert desktop.focus("notepad")["success"] is False
    assert fake_desktop.keys == []


# ─── prompt handoff ──────────────────────────────────────────────────────────


@pytest.fixture
def clipboard_ok(monkeypatch):
    monkeypatch.setattr(desktop, "copy_text", lambda text: {"success": True, "copied": True})
    monkeypatch.setattr("automation.os_windows.read_clipboard", lambda: "")
    monkeypatch.setattr("automation.os_windows.copy_to_clipboard", lambda text: True)
    # Paste confirmation (UIA/OCR) — individual tests override this.
    monkeypatch.setattr(desktop, "text_landed", lambda expected, window=None: {"verified": True, "method": "test"})


def test_handoff_pastes_and_submits_into_verified_window(fake_desktop, clipboard_ok, monkeypatch):
    monkeypatch.setattr("automation.os_windows.launch_app", lambda name: True)
    result = desktop.handoff_prompt("Build a landing page", app_name="notepad")
    assert result["success"] is True
    assert result["submitted"] is True
    assert fake_desktop.keys == [("ctrl+v", "notepad.exe"), ("enter", "notepad.exe")]


def test_handoff_does_not_submit_when_paste_cannot_be_confirmed(fake_desktop, clipboard_ok, monkeypatch):
    monkeypatch.setattr("automation.os_windows.launch_app", lambda name: True)
    monkeypatch.setattr(desktop, "text_landed", lambda expected, window=None: {"verified": None, "method": None})
    result = desktop.handoff_prompt("Build a landing page", app_name="notepad")
    assert result["success"] is False and result["pasted"] is True
    assert result["submitted"] is False
    assert fake_desktop.keys == [("ctrl+v", "notepad.exe")]  # pasted, Enter never pressed
    assert "press Enter yourself" in result["error"]


def test_handoff_never_presses_enter_if_focus_fails(fake_desktop, clipboard_ok):
    fake_desktop.activate_ok = False
    result = desktop.handoff_prompt("Build a landing page", app_name="notepad")
    assert result["success"] is False
    assert result["submitted"] is False
    assert fake_desktop.keys == []
    assert "clipboard" in result["error"]  # tells the user how to finish by hand


def test_handoff_waits_for_the_right_browser_tab(fake_desktop, clipboard_ok, monkeypatch):
    monkeypatch.setattr("automation.os_windows.launch_browser", lambda url: True)
    fake_desktop.windows = [WindowInfo(1, 1, "chrome.exe", "New Tab - Google Chrome")]
    result = desktop.handoff_prompt("hi", url="https://chatgpt.com/", wait_seconds=0.01)
    assert result["success"] is False
    assert "No https://chatgpt.com/ window appeared" in result["error"]
    assert fake_desktop.keys == []


def test_handoff_stops_if_focus_moves_before_submit(fake_desktop, clipboard_ok, monkeypatch):
    monkeypatch.setattr("automation.os_windows.launch_app", lambda name: True)
    real_send = win32.send_chord

    def send_and_lose_focus(chord):
        real_send(chord)
        fake_desktop.front = TERMINAL  # user clicked elsewhere after the paste

    monkeypatch.setattr(win32, "send_chord", send_and_lose_focus)
    result = desktop.handoff_prompt("text", app_name="notepad")
    assert result["success"] is False
    assert result["submitted"] is False
    assert fake_desktop.keys == [("ctrl+v", "notepad.exe")]


def test_handoff_requires_prompt_and_target():
    assert desktop.handoff_prompt("", app_name="notepad")["error"] == "prompt is required"
    assert desktop.handoff_prompt("x")["error"] == "app_name or url is required"


# ─── verify ──────────────────────────────────────────────────────────────────


def test_unknown_verify_check_fails_instead_of_passing():
    result = desktop.verify("vibes", "anything")
    assert result["success"] is False
    assert result["verified"] is False


def test_verify_window_focused(fake_desktop):
    assert desktop.verify("window_focused", "terminal")["verified"] is True
    assert desktop.verify("window_focused", "notepad")["verified"] is False


def test_verify_file_changed(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("x")
    assert desktop.verify("file_changed", str(f))["verified"] is True
    assert desktop.verify("file_changed", str(tmp_path / "nope"))["verified"] is False


# ─── OCR / capture ───────────────────────────────────────────────────────────


def test_ocr_failure_is_an_error_not_fake_text(tmp_path, monkeypatch):
    img = tmp_path / "x.png"
    img.write_bytes(b"not really a png")
    monkeypatch.setattr(ocr, "_ocr_windows", lambda p: ("", "No Windows OCR language pack installed"))
    monkeypatch.setattr(ocr, "_ocr_tesseract", lambda p: ("", "pytesseract/Pillow not installed"))
    result = ocr.run_ocr(str(img))
    assert result["ok"] is False
    assert result["text"] == ""
    assert "language pack" in result["error"]
    assert ocr.ocr_image(str(img)) == ""


def test_ocr_text_is_redacted(tmp_path, monkeypatch):
    img = tmp_path / "x.png"
    img.write_bytes(b"png")
    monkeypatch.setattr(ocr, "_ocr_windows", lambda p: ("password=hunter2 visible", None))
    result = ocr.run_ocr(str(img))
    assert result["ok"] is True and result["engine"] == "windows"
    assert "hunter2" not in result["text"]


def test_read_screen_checks_expected_text(monkeypatch):
    monkeypatch.setattr(desktop, "capture", lambda **k: {"success": True, "path": "p.png"})
    monkeypatch.setattr(ocr, "run_ocr", lambda p: {"ok": True, "text": "Build succeeded", "engine": "windows", "error": None})
    assert desktop.read_screen(expected_text="build succeeded")["verified"] is True
    missing = desktop.read_screen(expected_text="All tests passed")
    assert missing["verified"] is False and "not visible" in missing["error"]


def test_region_parsing():
    assert desktop.parse_region("10, 20, 300, 400") == (10, 20, 300, 400)
    with pytest.raises(ValueError):
        desktop.parse_region("10,20,0,5")
    with pytest.raises(ValueError):
        desktop.parse_region("1,2,3")


def test_png_encoder_produces_valid_png():
    import struct
    import zlib

    png = win32.encode_png_bgra(bytes([255, 0, 0, 255]) * 4, 2, 2)  # 2x2 blue (BGRA)
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    width, height = struct.unpack(">II", png[16:24])
    assert (width, height) == (2, 2)
    idat_len = struct.unpack(">I", png[33:37])[0]
    raw = zlib.decompress(png[41:41 + idat_len])
    assert raw[:4] == b"\x00\x00\x00\xff"  # filter byte + first pixel RGB = (0,0,255)


# ─── external agent bridge ───────────────────────────────────────────────────


def test_bridge_installed_without_prompt_path_copies_instead_of_guessing(monkeypatch):
    from automation import agent_bridge

    monkeypatch.setattr(
        agent_bridge,
        "_detect",
        lambda tool: agent_bridge.ToolStatus(
            tool=tool, connected=False, installed=True, app_path="x.cmd",
            error="antigravity is installed but has no verified way to receive a prompt yet;",
        ),
    )
    copied = []
    monkeypatch.setattr("automation.desktop.copy_text", lambda text: copied.append(text) or {"success": True})
    ran = []
    monkeypatch.setattr(agent_bridge.subprocess, "run", lambda *a, **k: ran.append(a))
    result = agent_bridge.AgentBridge().send_prompt("antigravity", "build it")
    assert result.status == "unsupported"
    assert result.executed is False
    assert copied == ["build it"]
    assert ran == []  # no invented CLI call
    assert "clipboard" in result.output


def test_bridge_not_installed_is_unavailable(monkeypatch):
    from automation import agent_bridge

    monkeypatch.setattr(agent_bridge, "_detect", lambda tool: agent_bridge.ToolStatus(tool=tool, connected=False))
    result = agent_bridge.AgentBridge().send_prompt("cursor", "x")
    assert result.status == "unavailable"
    assert result.executed is False


def test_type_text_reads_back_and_reports(fake_desktop, monkeypatch):
    typed = []
    monkeypatch.setattr(win32, "send_unicode", lambda text: typed.append((text, fake_desktop.front.exe)) or len(text) * 2)
    monkeypatch.setattr(desktop, "text_landed", lambda expected, window=None: {"verified": True, "method": "ui_automation"})
    result = desktop.type_text("hello world", target_app="notepad")
    assert result["success"] is True and result["verified"] is True
    assert typed == [("hello world", "notepad.exe")]


def test_type_text_flags_text_that_did_not_arrive(fake_desktop, monkeypatch):
    monkeypatch.setattr(win32, "send_unicode", lambda text: 0)
    monkeypatch.setattr(desktop, "text_landed", lambda expected, window=None: {"verified": False, "method": "ocr"})
    result = desktop.type_text("hello", target_app="notepad")
    assert result["success"] is False and "not visible" in result["error"]


def test_type_text_refuses_automata_window(fake_desktop):
    fake_desktop.front = AUTOMATA_UI
    assert desktop.type_text("hi")["success"] is False


def test_switch_tab_verifies_window_title(fake_desktop, monkeypatch):
    from automation import uia

    def select(hwnd, needle):
        fake_desktop.windows[1] = WindowInfo(202, 22, "chrome.exe", "GitHub - Google Chrome")
        return {"ok": True, "title": "GitHub"}

    monkeypatch.setattr(uia, "select_tab", select)
    result = desktop.switch_tab("github", "chrome")
    assert result["success"] is True and result["verified"] is True
    assert result["window"]["title"].startswith("GitHub")


def test_switch_tab_missing_tab(fake_desktop, monkeypatch):
    from automation import uia

    monkeypatch.setattr(uia, "select_tab", lambda hwnd, needle: {"ok": False, "error": "No tab containing 'jira'"})
    result = desktop.switch_tab("jira", "chrome")
    assert result["success"] is False and "jira" in result["error"]


def test_text_landed_uses_ui_automation_first(monkeypatch):
    from automation import uia

    monkeypatch.setattr(uia, "focused_text", lambda: {"ok": True, "text": "Build   a landing page please"})
    assert desktop.text_landed("Build a landing page please")["method"] == "ui_automation"


def test_bridge_ide_chat_opens_repo_then_sends_prompt_via_stdin(monkeypatch, tmp_path):
    from automation import agent_bridge

    monkeypatch.setattr(
        agent_bridge, "_detect",
        lambda tool: agent_bridge.ToolStatus(tool=tool, connected=True, installed=True,
                                             cli_path="ag.cmd", prompt_via="ide_chat"),
    )
    calls = []

    class Done:
        returncode, stdout, stderr = 0, "", ""

    monkeypatch.setattr(agent_bridge.subprocess, "run", lambda cmd, **kw: calls.append((cmd, kw.get("input"))) or Done())
    result = agent_bridge.AgentBridge().send_prompt("antigravity", "x" * 20000, {"repo_path": str(tmp_path)})
    assert result.status == "ok" and result.executed is True
    assert calls[0][0] == ["ag.cmd", str(tmp_path)]
    assert calls[1][0][:3] == ["ag.cmd", "chat", "--mode"] and calls[1][0][-1] == "-"
    assert len(calls[1][1]) == 20000  # full prompt via stdin, not argv
