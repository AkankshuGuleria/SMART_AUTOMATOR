"""
automation/chat_apps.py — hand a prompt to an AI app's chat box, verified at every step.

Owns:    Per-app recipes (which window, how to open the agent/chat panel, what the
         chat box is called) and the delivery sequence:
           find or launch the window (in the project folder for IDEs)
           → bring it to the front (confirmed by Windows)
           → find the chat box by its accessible name (open the panel if hidden)
           → focus it through UI Automation (no mouse clicks)
           → paste, then read the text back (UIA Text pattern, OCR fallback)
           → only if allowed: press the send key and confirm the box emptied.
Never:   Types into a box that already holds the user's draft, presses Enter
         before the paste is confirmed, or reports "sent" without seeing it.

The chat-box names come from probing the real apps (Antigravity IDE 2.5 and the
Antigravity desktop app 2.2 both call it "Message input"). Apps whose chat box
has no distinctive name (VS Code's Copilot chat is a generic editor field) are
not listed here; agent_bridge uses their CLI instead.
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from automation import win32

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChatApp:
    key: str
    label: str
    exes: frozenset[str]
    input_names: tuple[str, ...]  # substrings of the chat box's accessible name (lower-case)
    open_chat_chords: tuple[str, ...] = ()  # pressed one at a time until the box appears
    open_chat_buttons: tuple[str, ...] = ()  # accessible names of a panel button to invoke first
    focus_first_chord: str | None = None  # moves focus out of another chat box before the chord
    # Some apps fold a long paste into a chip like "[Pasted ~26 lines]"; group 1 = line count.
    paste_chip: str | None = None
    new_chat_buttons: tuple[str, ...] = ()  # accessible names of a "new conversation" button
    folder_aware: bool = False  # opens a project folder (window title shows the folder)
    launch_paths: tuple[str, ...] = field(default_factory=tuple)  # exe/cli candidates
    submit_chord: str = "enter"


def _local(*parts: str) -> str:
    return str(Path(os.environ.get("LOCALAPPDATA", "")).joinpath(*parts))


APPS: dict[str, ChatApp] = {
    "antigravity": ChatApp(
        key="antigravity",
        label="Antigravity IDE",
        exes=frozenset({"antigravity ide.exe"}),
        input_names=("message input",),
        open_chat_chords=("ctrl+l",),  # toggles the Agent panel and focuses its input
        folder_aware=True,
        launch_paths=(_local("Programs", "Antigravity IDE", "bin", "antigravity-ide.cmd"),),
    ),
    # Kilo Code extension inside Antigravity IDE. Its chat box is named
    # "Type a message, @ to mention files... (Ctrl+Shift+A to type)" — distinct from
    # Antigravity's own agent box ("Message input") in the same window.
    "kilo": ChatApp(
        key="kilo",
        label="Kilo Code (in Antigravity IDE)",
        exes=frozenset({"antigravity ide.exe"}),
        input_names=("type a message, @ to mention",),
        open_chat_buttons=("kilo code",),  # its activity-bar icon (works whatever has focus)
        focus_first_chord="ctrl+1",  # Antigravity's own agent box swallows Ctrl+Shift+A
        open_chat_chords=("ctrl+shift+a",),  # kilo-code.new.focusChatInput
        new_chat_buttons=("new task",),
        paste_chip=r"\[pasted ~?(\d+) lines?\]",
        folder_aware=True,
        launch_paths=(_local("Programs", "Antigravity IDE", "bin", "antigravity-ide.cmd"),),
    ),
    "antigravity_app": ChatApp(
        key="antigravity_app",
        label="Antigravity",
        exes=frozenset({"antigravity.exe"}),
        input_names=("message input",),
        new_chat_buttons=("new conversation",),
        launch_paths=(_local("Programs", "Antigravity", "Antigravity.exe"),),
    ),
    "cursor": ChatApp(
        key="cursor",
        label="Cursor",
        exes=frozenset({"cursor.exe"}),
        input_names=("message input", "chat input", "plan, search", "ask", "add a follow-up"),
        open_chat_chords=("ctrl+l", "ctrl+i"),
        folder_aware=True,
        launch_paths=(_local("Programs", "cursor", "resources", "app", "bin", "cursor.cmd"),
                      _local("Programs", "cursor", "Cursor.exe")),
    ),
    "claude": ChatApp(
        key="claude",
        label="Claude",
        exes=frozenset({"claude.exe"}),
        input_names=("write your prompt", "prompt", "reply to claude", "message"),
        open_chat_chords=("ctrl+shift+o",),  # new chat
        launch_paths=(_local("AnthropicClaude", "claude.exe"), _local("Programs", "Claude", "Claude.exe")),
    ),
    "chatgpt": ChatApp(
        key="chatgpt",
        label="ChatGPT",
        exes=frozenset({"chatgpt.exe"}),
        input_names=("message chatgpt", "ask anything", "message"),
        open_chat_chords=("ctrl+shift+o",),
    ),
}


# Kilo Code marks its session tab with a spinner glyph while it works and ✓ when done.
_BUSY_GLYPHS = "◔◑◒◓◐◴◵◶◷⟳"
_DONE_GLYPHS = "✓✔"


def agent_busy(key: str, folder: str | None = None) -> bool | None:
    """Is the agent still working? True/False when the app shows it, None when unknown."""
    app = APPS.get(key)
    if app is None or not win32.IS_WINDOWS or key != "kilo":
        return None
    try:
        from automation import uia

        window = next(iter(_windows(app, folder)), None)
        u, mod = uia._client(), uia._mod()
        if window is None or u is None:
            return None
        tabs = u.ElementFromHandle(window.hwnd).FindAll(
            mod.TreeScope_Descendants,
            u.CreatePropertyCondition(mod.UIA_ControlTypePropertyId, mod.UIA_TabItemControlTypeId))
        names = [(tabs.GetElement(i).CurrentName or "").strip() for i in range(tabs.Length)]
        names.append(window.title)
        if any(n[:1] in _BUSY_GLYPHS for n in names if n) or any(f"- {g}" in window.title for g in _BUSY_GLYPHS):
            return True
        if any(n[:1] in _DONE_GLYPHS for n in names if n):
            return False
    except Exception as exc:
        logger.debug("agent_busy(%s) unknown — %s", key, exc)
    return None


def kilo_installed() -> bool:
    """Kilo Code extension present in Antigravity IDE's extension folder."""
    ext = Path.home() / ".antigravity-ide" / "extensions"
    return ext.is_dir() and any(p.name.startswith("kilocode.kilo-code") for p in ext.iterdir())


def installed(key: str) -> bool:
    app = APPS.get(key)
    if key == "kilo" and not kilo_installed():
        return False
    return bool(app) and any(Path(p).exists() for p in app.launch_paths)


def running(key: str) -> bool:
    app = APPS.get(key)
    return bool(app) and any(w.exe.lower() in app.exes for w in win32.top_level_windows())


# ─── UI Automation helpers ───────────────────────────────────────────────────


def _focusable(hwnd: int, attempts: int = 6):
    """Keyboard-focusable elements of a window. Chromium apps build their
    accessibility tree only after the first request, so retry briefly."""
    from automation import uia

    u, mod = uia._client(), uia._mod()
    if u is None:
        return []
    out = []
    for i in range(attempts):
        root = u.ElementFromHandle(hwnd)
        found = root.FindAll(mod.TreeScope_Descendants,
                             u.CreatePropertyCondition(mod.UIA_IsKeyboardFocusablePropertyId, True))
        out = [found.GetElement(j) for j in range(found.Length)]
        if len(out) > 5:
            break
        time.sleep(0.4 + 0.3 * i)
    return out


def _find_named(hwnd: int, names: tuple[str, ...], attempts: int = 6):
    for el in _focusable(hwnd, attempts):
        try:
            name = (el.CurrentName or "").lower()
            if name and any(n in name for n in names) and not el.CurrentIsOffscreen:
                return el
        except Exception:
            continue
    return None


def _invoke(el) -> bool:
    from automation import uia

    mod = uia._mod()
    for pattern_id, iface, method in (
        (mod.UIA_InvokePatternId, mod.IUIAutomationInvokePattern, "Invoke"),
        (mod.UIA_SelectionItemPatternId, mod.IUIAutomationSelectionItemPattern, "Select"),  # tabs (activity bar)
        (mod.UIA_LegacyIAccessiblePatternId, mod.IUIAutomationLegacyIAccessiblePattern, "DoDefaultAction"),
    ):
        try:
            getattr(el.GetCurrentPattern(pattern_id).QueryInterface(iface), method)()
            return True
        except Exception:
            continue
    return False


def _is_focused(el) -> bool:
    from automation import uia

    u = uia._client()
    try:
        return bool(u.CompareElements(u.GetFocusedElement(), el))
    except Exception:
        return False


def _box_text(el) -> str:
    from automation import uia

    return uia.visible_text(uia._element_text(el, include_name=False))


def _norm(text: str) -> str:
    from automation.uia import visible_text

    return " ".join(visible_text(text).split()).lower()


def _contains_prompt(box: str, prompt: str, chip: str | None = None) -> bool:
    probe = _norm(prompt)[:60]
    if probe and probe in _norm(box):
        return True
    if chip:  # "[Pasted ~26 lines]": accept when the line count matches the prompt's
        import re

        m = re.search(chip, box or "", re.IGNORECASE)
        if m:
            lines = len(prompt.strip().splitlines())
            return abs(int(m.group(1)) - lines) <= max(3, lines // 10)
    return False


# ─── window ──────────────────────────────────────────────────────────────────


def _windows(app: ChatApp, folder: str | None):
    wins = [w for w in win32.top_level_windows() if w.exe.lower() in app.exes]
    if folder and app.folder_aware:
        name = Path(folder).name.lower()
        wins = [w for w in wins if name in w.title.lower()]
    return wins


def _launch(app: ChatApp, folder: str | None) -> str | None:
    exe = next((p for p in app.launch_paths if Path(p).exists()), None)
    if not exe:
        return f"{app.label} is not installed."
    args = [exe] + ([folder] if folder and app.folder_aware else [])
    try:
        subprocess.Popen(args, cwd=folder if folder and os.path.isdir(folder) else None)
    except Exception as exc:
        return f"Could not start {app.label}: {exc}"
    return None


def _wait_window(app: ChatApp, folder: str | None, timeout: float):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        wins = _windows(app, folder)
        if wins:
            return wins[0]
        time.sleep(0.5)
    return None


# ─── delivery ────────────────────────────────────────────────────────────────


def deliver(key: str, prompt: str, folder: str | None = None, submit: bool = False,
            launch_timeout: float = 45.0, new_conversation: bool = True) -> dict[str, Any]:
    """Put *prompt* in the app's chat box (and send it if *submit*), verifying each step.

    Returns {success, pasted, submitted, verified_by, steps, error?}. ``success``
    means the prompt is confirmed in the box (and, with submit, confirmed sent).
    """
    steps: list[str] = []

    def fail(error: str, **extra: Any) -> dict[str, Any]:
        logger.warning("chat_apps.deliver(%s): %s", key, error)
        return {"success": False, "pasted": False, "submitted": False, "error": error, "steps": steps, **extra}

    app = APPS.get(key)
    if app is None:
        return fail(f"No chat recipe for '{key}'.")
    if not win32.IS_WINDOWS:
        return fail("Desktop control is only supported on Windows.")
    if win32.input_disabled():
        return fail("Desktop input is disabled (AUTOMATA_DISABLE_DESKTOP_INPUT=1).")
    if not prompt.strip():
        return fail("Empty prompt.")

    window = next(iter(_windows(app, folder)), None)
    launched = window is None
    if window is None:
        err = _launch(app, folder)
        if err:
            return fail(err)
        steps.append(f"Opened {app.label}" + (f" in {folder}" if folder and app.folder_aware else ""))
        window = _wait_window(app, folder, launch_timeout)
        if window is None:
            return fail(f"{app.label} did not open a window within {int(launch_timeout)} s.")
        time.sleep(2.5)  # let the UI finish loading
    if not win32.activate(window.hwnd):
        return fail(f"Windows did not let AUTOMATA bring {app.label} to the front.")
    steps.append(f"Brought '{window.title}' to the front")

    box = _find_named(window.hwnd, app.input_names)
    # Open the panel. A just-opened window may still be loading its extensions,
    # so keep trying for a while (button first: it doesn't depend on keyboard focus).
    deadline = time.monotonic() + (20.0 if launched else 8.0)
    while box is None and (app.open_chat_buttons or app.open_chat_chords) and time.monotonic() < deadline:
        button = _find_named(window.hwnd, app.open_chat_buttons, attempts=1) if app.open_chat_buttons else None
        if button is not None and _invoke(button):
            steps.append(f"Opened the {app.label} panel")
            box = _find_named(window.hwnd, app.input_names, attempts=3)
            if box is not None:
                break
        for chord in app.open_chat_chords:
            front = win32.foreground()
            if not front or front.hwnd != window.hwnd:
                return fail(f"{app.label} lost focus before its chat panel could be opened.")
            if app.focus_first_chord:
                win32.send_chord(app.focus_first_chord)
                time.sleep(0.3)
            win32.send_chord(chord)
            if f"Pressed {chord} to open the chat panel" not in steps:
                steps.append(f"Pressed {chord} to open the chat panel")
            time.sleep(1.2)
            box = _find_named(window.hwnd, app.input_names, attempts=3)
            if box is not None:
                break
        if box is None:
            time.sleep(1.5)
    if box is None:
        return fail(f"Could not find the chat box in {app.label}. Open its agent/chat panel and try again.")

    # Start a fresh conversation (the button only exists once the panel is open),
    # so the task doesn't land in the middle of an older chat.
    if app.new_chat_buttons and new_conversation:
        button = _find_named(window.hwnd, app.new_chat_buttons, attempts=2)
        if button is not None and _invoke(button):
            steps.append("Started a new conversation")
            time.sleep(1.2)
            box = _find_named(window.hwnd, app.input_names, attempts=4) or box

    draft = _box_text(box).strip()
    if draft:
        return fail(f"The {app.label} chat box already has text in it; AUTOMATA did not overwrite your draft.")
    try:
        box.SetFocus()
    except Exception:
        pass
    time.sleep(0.3)
    if not _is_focused(box):
        return fail(f"Could not put the cursor in the {app.label} chat box.")
    steps.append("Focused the chat box")

    from automation.desktop import copy_text, text_landed
    from automation.os_windows import copy_to_clipboard, read_clipboard

    original = read_clipboard()
    try:
        if not copy_text(prompt).get("success"):
            return fail("Could not put the prompt on the clipboard.")
        front = win32.foreground()
        if not front or front.hwnd != window.hwnd or not _is_focused(box):
            return fail(f"{app.label} lost focus; the prompt was not pasted.")
        win32.send_chord("ctrl+v")
        time.sleep(0.8)
    finally:
        if original:
            copy_to_clipboard(original.rstrip("\r\n"))

    verified_by = None
    if _contains_prompt(_box_text(box), prompt, app.paste_chip):
        verified_by = "ui_automation"
    else:
        check = text_landed(prompt, window)
        if check.get("verified"):
            verified_by = check.get("method")
    if not verified_by:
        return fail(f"Pasted into {app.label}, but the text is not visible in the chat box.", pasted=False)
    steps.append(f"Prompt is in the chat box (checked by {verified_by.replace('_', ' ')})")

    if not submit:
        return {"success": True, "pasted": True, "submitted": False, "verified_by": verified_by,
                "steps": steps, "window": window.title}

    front = win32.foreground()
    if not front or front.hwnd != window.hwnd or not _is_focused(box):
        return fail(f"{app.label} lost focus; the prompt is in the box but was not sent.", pasted=True)
    win32.send_chord(app.submit_chord)
    time.sleep(1.5)
    # Sent = the chat box no longer holds the prompt (it moved into the conversation).
    still = _find_named(window.hwnd, app.input_names, attempts=2)
    remaining = _box_text(still) if still is not None else ""
    if _contains_prompt(remaining, prompt, app.paste_chip):
        return fail(f"Pressed {app.submit_chord} but {app.label} kept the prompt in the box; send it yourself.",
                    pasted=True)
    steps.append(f"Sent with {app.submit_chord}; the chat box is empty again")
    return {"success": True, "pasted": True, "submitted": True, "verified_by": verified_by,
            "steps": steps, "window": window.title}
