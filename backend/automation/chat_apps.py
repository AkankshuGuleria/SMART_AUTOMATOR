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


def installed(key: str) -> bool:
    app = APPS.get(key)
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

    return uia._element_text(el, include_name=False)


def _norm(text: str) -> str:
    return " ".join((text or "").split()).lower()


def _contains_prompt(box: str, prompt: str) -> bool:
    probe = _norm(prompt)[:60]
    return bool(probe) and probe in _norm(box)


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
            launch_timeout: float = 45.0) -> dict[str, Any]:
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

    if app.new_chat_buttons:
        button = _find_named(window.hwnd, app.new_chat_buttons)
        if button is not None and _invoke(button):
            steps.append("Started a new conversation")
            time.sleep(1.0)

    box = _find_named(window.hwnd, app.input_names)
    for chord in app.open_chat_chords if box is None else ():
        front = win32.foreground()
        if not front or front.hwnd != window.hwnd:
            return fail(f"{app.label} lost focus before its chat panel could be opened.")
        win32.send_chord(chord)
        steps.append(f"Pressed {chord} to open the chat panel")
        time.sleep(1.2)
        box = _find_named(window.hwnd, app.input_names, attempts=3)
        if box is not None:
            break
    if box is None:
        return fail(f"Could not find the chat box in {app.label}. Open its agent/chat panel and try again.")

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
    if _contains_prompt(_box_text(box), prompt):
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
    if _contains_prompt(remaining, prompt):
        return fail(f"Pressed {app.submit_chord} but {app.label} kept the prompt in the box; send it yourself.",
                    pasted=True)
    steps.append(f"Sent with {app.submit_chord}; the chat box is empty again")
    return {"success": True, "pasted": True, "submitted": True, "verified_by": verified_by,
            "steps": steps, "window": window.title}
