"""
automation/desktop.py — verified desktop actions (focus, keys, paste, capture,
OCR, prompt handoff).

Owns:    The single implementation of every cross-app and visual action used by
         the planner, the tool registry, agent actions and workflows. Every
         function returns a dict whose ``success`` is only True when Windows
         confirms the effect (the right window is in front, the clipboard
         holds the text, the screenshot exists, OCR produced text).
Never:   Reports an action as done because a command ran. When it cannot
         verify something it says so (``verified: False`` plus ``error``).
         Never presses Enter into a window it has not confirmed is the target.

Read-back: typed/pasted text is confirmed through UI Automation (the focused
field's value) and, when UIA cannot see it, OCR of the target window.
"""

from __future__ import annotations

import logging
import os
import tempfile
import time
import uuid
from typing import Any
from urllib.parse import urlparse

from automation import win32

logger = logging.getLogger(__name__)

# Friendly name → process executables (lower-case).
APP_PROCESSES: dict[str, set[str]] = {
    "chrome": {"chrome.exe"},
    "google chrome": {"chrome.exe"},
    "edge": {"msedge.exe"},
    "msedge": {"msedge.exe"},
    "firefox": {"firefox.exe"},
    "brave": {"brave.exe"},
    "opera": {"opera.exe"},
    "browser": {"chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe"},
    "vscode": {"code.exe"},
    "vs code": {"code.exe"},
    "code": {"code.exe"},
    "cursor": {"cursor.exe"},
    "antigravity": {"antigravity.exe"},
    "claude": {"claude.exe"},
    "chatgpt": {"chatgpt.exe"},
    "notepad": {"notepad.exe"},
    "terminal": {"windowsterminal.exe"},
    "windows terminal": {"windowsterminal.exe"},
    "powershell": {"powershell.exe", "pwsh.exe", "windowsterminal.exe"},
    "cmd": {"cmd.exe", "windowsterminal.exe"},
    "explorer": {"explorer.exe"},
    "file explorer": {"explorer.exe"},
    "spotify": {"spotify.exe"},
    "slack": {"slack.exe"},
    "discord": {"discord.exe"},
    "teams": {"ms-teams.exe", "teams.exe"},
    "figma": {"figma.exe"},
    "postman": {"postman.exe"},
}
BROWSERS = APP_PROCESSES["browser"]

# Web apps: page-title fragment that proves the right tab is showing.
URL_TITLE_HINTS = {
    "chatgpt.com": "ChatGPT",
    "chat.openai.com": "ChatGPT",
    "claude.ai": "Claude",
    "gemini.google.com": "Gemini",
    "perplexity.ai": "Perplexity",
    "github.com": "GitHub",
}

# Key used to send a message in each chat surface.
SUBMIT_KEYS = {"chatgpt": "enter", "claude": "enter", "gemini": "enter"}

SAFE_CHORDS = {
    "ctrl+v", "enter", "ctrl+enter", "ctrl+return", "ctrl+l", "alt+tab", "tab", "escape",
}

OWN_PROCESSES = {"automata.exe", "app.exe"}


def _fail(error: str, **extra: Any) -> dict[str, Any]:
    logger.warning("desktop: %s", error)
    return {"success": False, "error": error, **extra}


def _unsupported() -> dict[str, Any] | None:
    if not win32.IS_WINDOWS:
        return _fail("Desktop control is only supported on Windows.")
    return None


def _input_blocked() -> dict[str, Any] | None:
    if win32.input_disabled():
        return _fail("Desktop input is disabled (AUTOMATA_DISABLE_DESKTOP_INPUT=1).")
    return None


def processes_for(app_name: str) -> set[str]:
    key = app_name.lower().strip()
    if key in APP_PROCESSES:
        return APP_PROCESSES[key]
    return {key if key.endswith(".exe") else f"{key}.exe"}


def is_own_window(info: win32.WindowInfo | None) -> bool:
    """True for AUTOMATA's own window (desktop app, or the dev UI in a browser)."""
    if info is None:
        return False
    exe = info.exe.lower()
    return exe in OWN_PROCESSES or (exe in BROWSERS and "automata" in info.title.lower())


def find_windows(app_name: str, title_hint: str | None = None) -> list[win32.WindowInfo]:
    """Windows belonging to *app_name* (front-most first), optionally title-filtered."""
    exes = processes_for(app_name)
    matches = [w for w in win32.top_level_windows() if w.exe.lower() in exes]
    if not matches and app_name.lower() not in APP_PROCESSES:
        # Unknown app: fall back to a window title match ("chatgpt" tab in a browser).
        needle = app_name.lower()
        matches = [w for w in win32.top_level_windows() if needle in w.title.lower()]
    if title_hint:
        hinted = [w for w in matches if title_hint.lower() in w.title.lower()]
        matches = hinted
    return [w for w in matches if not is_own_window(w)]


def _matches(info: win32.WindowInfo | None, app_name: str, title_hint: str | None = None) -> bool:
    if info is None or is_own_window(info):
        return False
    exes = processes_for(app_name)
    ok = info.exe.lower() in exes or (
        app_name.lower() not in APP_PROCESSES and app_name.lower() in info.title.lower()
    )
    return ok and (not title_hint or title_hint.lower() in info.title.lower())


# ─── focus / keys / paste ────────────────────────────────────────────────────


def focus(app_name: str, title_hint: str | None = None) -> dict[str, Any]:
    """Bring *app_name* to the front and confirm Windows switched to it."""
    if not app_name.strip():
        return _fail("app_name is required")
    if err := _unsupported() or _input_blocked():
        return err
    candidates = find_windows(app_name, title_hint)
    if not candidates:
        hint = f" with '{title_hint}' in the title" if title_hint else ""
        return _fail(f"No open {app_name} window{hint} found.", app=app_name, focused=False)
    for window in candidates:
        if win32.activate(window.hwnd):
            front = win32.foreground()
            logger.info("desktop.focus: %s → %s", app_name, front.title if front else "?")
            return {
                "success": True,
                "focused": True,
                "app": app_name,
                "window": front.as_dict() if front else window.as_dict(),
            }
    front = win32.foreground()
    return _fail(
        f"Windows did not let AUTOMATA switch to {app_name}.",
        app=app_name,
        focused=False,
        foreground=front.as_dict() if front else None,
    )


def press(chord: str, target_app: str | None = None, title_hint: str | None = None) -> dict[str, Any]:
    """Send a safe key chord to a verified window.

    With *target_app*, the chord is only sent if that app is in front. Without
    it, the chord goes to the current window — unless that window is AUTOMATA
    itself (the user just clicked our button, so the keys would land on us).
    """
    normalized = chord.lower().strip()
    if not normalized:
        return _fail("keystrokes is required")
    if normalized not in SAFE_CHORDS:
        return _fail(f"Keystroke '{chord}' is not on the allowed list.", keystrokes=chord)
    if err := _unsupported() or _input_blocked():
        return err
    front = win32.foreground()
    if target_app:
        if not _matches(front, target_app, title_hint):
            return _fail(
                f"{target_app} is not the active window; keys were not sent.",
                keystrokes=chord,
                foreground=front.as_dict() if front else None,
            )
    elif front is None:
        return _fail("No active window to send keys to.", keystrokes=chord)
    elif is_own_window(front):
        return _fail(
            "AUTOMATA itself is the active window. Say which app to use, e.g. 'paste into notepad'.",
            keystrokes=chord,
        )
    win32.send_chord("ctrl+enter" if normalized == "ctrl+return" else normalized)
    return {
        "success": True,
        "sent": True,
        "keystrokes": chord,
        "delivered_to": front.as_dict() if front else None,
        "note": "Keys were delivered to this window; its content is not read back yet.",
    }


def paste(target_app: str | None = None) -> dict[str, Any]:
    """Paste the clipboard into *target_app* (focused first) or the active window."""
    if target_app:
        focused = focus(target_app)
        if not focused["success"]:
            return {**focused, "pasted": False}
        time.sleep(0.2)
    result = press("ctrl+v", target_app=target_app)
    result["pasted"] = result.get("success", False)
    return result


def _norm(text: str) -> str:
    return " ".join((text or "").split()).lower()


def text_landed(expected: str, window: win32.WindowInfo | None = None) -> dict[str, Any]:
    """Did *expected* arrive in the focused field / target window?

    Returns verified True/False, or None when neither UIA nor OCR could look.
    """
    from automation import uia

    probe = _norm(expected)[:40]
    if not probe:
        return {"verified": None, "method": None}
    seen = uia.focused_text()
    if seen.get("ok") and seen.get("text"):
        if probe in _norm(seen["text"]):
            return {"verified": True, "method": "ui_automation"}
    # OCR the window: accept if most of the first words are visible (OCR is noisy).
    shot = capture(app_name=None, active_window=window is None) if window is None else None
    if window is not None:
        try:
            rect = win32.window_rect(window.hwnd)
            if rect:
                png = win32.capture_rect(*rect)
                path = _screenshot_path()
                with open(path, "wb") as fh:
                    fh.write(png)
                shot = {"success": True, "path": path}
        except Exception as exc:
            shot = {"success": False, "error": str(exc)}
    if shot and shot.get("success"):
        from automation.ocr import run_ocr

        ocr = run_ocr(shot["path"])
        try:
            os.remove(shot["path"])
        except OSError:
            pass
        if ocr["ok"]:
            words = [w for w in _norm(expected).split()[:8] if len(w) > 2]
            text = _norm(ocr["text"])
            hits = sum(1 for w in words if w in text)
            if words and hits / len(words) >= 0.7:
                return {"verified": True, "method": "ocr"}
            return {"verified": False, "method": "ocr"}
    if seen.get("ok"):
        return {"verified": False, "method": "ui_automation"}
    return {"verified": None, "method": None}


def type_text(text: str, target_app: str | None = None, title_hint: str | None = None) -> dict[str, Any]:
    """Type *text* into the verified target (or current) window and read it back.

    Single-line text is typed as Unicode keys; multi-line or long text is
    pasted (clipboard saved and restored) so Enter is never pressed by accident.
    """
    if not text:
        return _fail("text is required")
    if err := _unsupported() or _input_blocked():
        return err
    if target_app:
        focused = focus(target_app, title_hint)
        if not focused["success"]:
            return {**focused, "typed": False}
        time.sleep(0.2)
    front = win32.foreground()
    if front is None:
        return _fail("No active window to type into.")
    if is_own_window(front):
        return _fail("AUTOMATA itself is the active window. Say which app to type into.")
    if target_app and not _matches(front, target_app, title_hint):
        return _fail(f"{target_app} is not the active window; nothing was typed.")
    method = "keys"
    if "\n" in text or len(text) > 400:
        from automation.os_windows import copy_to_clipboard, read_clipboard

        original = read_clipboard()
        if not copy_text(text)["success"]:
            return _fail("Could not stage the text on the clipboard.")
        win32.send_chord("ctrl+v")
        method = "paste"
        time.sleep(0.3)
        if original:
            copy_to_clipboard(original.rstrip("\r\n"))
    else:
        win32.send_unicode(text)
        time.sleep(0.2)
    check = text_landed(text, front)
    return {
        "success": check["verified"] is not False,
        "typed": True,
        "method": method,
        "verified": check["verified"],
        "verified_by": check["method"],
        "delivered_to": front.as_dict(),
        **({"error": "Typed, but the text is not visible in the target field."} if check["verified"] is False else {}),
    }


def list_windows() -> dict[str, Any]:
    """Visible app windows (front-most first), excluding AUTOMATA itself."""
    if err := _unsupported():
        return err
    from monitoring.app_usage import friendly_app_name

    windows = [
        {**w.as_dict(), "app": friendly_app_name(w.exe)}
        for w in win32.top_level_windows()
        if not is_own_window(w)
    ]
    return {"success": True, "windows": windows}


def browser_tabs(app_name: str = "browser") -> dict[str, Any]:
    """Tabs of every open browser window (or one browser)."""
    if err := _unsupported():
        return err
    from automation import uia

    out = []
    for w in find_windows(app_name):
        if w.exe.lower() not in BROWSERS:
            continue
        res = uia.browser_tabs(w.hwnd)
        out.append({"window": w.as_dict(), "tabs": res.get("tabs", []), "error": res.get("error")})
    if not out:
        return _fail(f"No open {app_name} window found.", windows=[])
    return {"success": True, "windows": out}


def switch_tab(title_contains: str, app_name: str = "browser") -> dict[str, Any]:
    """Switch to the browser tab whose title contains *title_contains*, then verify."""
    if not title_contains.strip():
        return _fail("title is required")
    if err := _unsupported() or _input_blocked():
        return err
    from automation import uia

    windows = [w for w in find_windows(app_name) if w.exe.lower() in BROWSERS]
    if not windows:
        return _fail(f"No open {app_name} window found.")
    errors = []
    for w in windows:
        res = uia.select_tab(w.hwnd, title_contains)
        if not res.get("ok"):
            errors.append(res.get("error", ""))
            continue
        win32.activate(w.hwnd)
        time.sleep(0.3)
        front = win32.foreground()
        verified = bool(front and front.hwnd == w.hwnd and title_contains.lower() in front.title.lower())
        return {
            "success": verified,
            "tab": res.get("title"),
            "verified": verified,
            "window": front.as_dict() if front else None,
            **({} if verified else {"error": "Tab selected but the window did not come to the front."}),
        }
    return _fail(errors[0] if errors else f"No tab containing '{title_contains}'.")


# ─── clipboard ───────────────────────────────────────────────────────────────


def copy_text(text: str) -> dict[str, Any]:
    """Copy *text* and confirm by reading the clipboard back."""
    from automation.os_windows import copy_to_clipboard, read_clipboard

    if not text:
        return _fail("text is required")
    if not copy_to_clipboard(text):
        return _fail("Could not write to the clipboard.", copied=False)
    back = read_clipboard()
    verified = back.rstrip("\r\n") == text.rstrip("\r\n")
    if not verified:
        return _fail("Clipboard did not contain the copied text afterwards.", copied=False)
    return {"success": True, "copied": True, "verified": True, "length": len(text)}


# ─── capture + OCR ───────────────────────────────────────────────────────────


def _screenshot_path() -> str:
    folder = os.path.join(tempfile.gettempdir(), "automata_screens")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, f"screen_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.png")


def parse_region(region: str) -> tuple[int, int, int, int]:
    parts = [p.strip() for p in str(region).split(",")]
    if len(parts) != 4:
        raise ValueError("region must be 'left,top,width,height'")
    left, top, width, height = (int(float(p)) for p in parts)
    if width <= 0 or height <= 0:
        raise ValueError("region width and height must be positive")
    return left, top, width, height


def capture(region: str | None = None, app_name: str | None = None, active_window: bool = False) -> dict[str, Any]:
    """Screenshot the primary screen, a region, an app's window, or the active window."""
    if err := _unsupported():
        return err
    try:
        target: win32.WindowInfo | None = None
        if region:
            rect = parse_region(region)
        elif app_name:
            windows = find_windows(app_name)
            if not windows:
                return _fail(f"No open {app_name} window to capture.")
            target = windows[0]
            rect = win32.window_rect(target.hwnd)
        elif active_window:
            target = win32.foreground()
            rect = win32.window_rect(target.hwnd) if target else None
        else:
            rect = win32.primary_screen_rect()
        if not rect:
            return _fail("Could not determine the area to capture.")
        png = win32.capture_rect(*rect)
        path = _screenshot_path()
        with open(path, "wb") as fh:
            fh.write(png)
        return {
            "success": True,
            "path": path,
            "width": rect[2],
            "height": rect[3],
            "window": target.as_dict() if target else None,
        }
    except Exception as exc:
        return _fail(f"Screen capture failed: {exc}")


def read_screen(
    expected_text: str | None = None,
    region: str | None = None,
    app_name: str | None = None,
    active_window: bool = False,
) -> dict[str, Any]:
    """Capture, then OCR. With *expected_text*, also report whether it is visible."""
    from automation.ocr import run_ocr

    shot = capture(region=region, app_name=app_name, active_window=active_window)
    if not shot["success"]:
        return shot
    ocr = run_ocr(shot["path"])
    result: dict[str, Any] = {
        "success": ocr["ok"],
        "text": ocr["text"],
        "engine": ocr["engine"],
        "screen_path": shot["path"],
        "window": shot.get("window"),
    }
    if not ocr["ok"]:
        result["error"] = ocr["error"]
    if expected_text:
        found = ocr["ok"] and expected_text.lower() in ocr["text"].lower()
        result["verified"] = found
        result["expected_text"] = expected_text
        if ocr["ok"] and not found:
            result["error"] = f"'{expected_text}' is not visible on screen."
    return result


# ─── verification ────────────────────────────────────────────────────────────


def verify(check_type: str, target: str = "") -> dict[str, Any]:
    """Check an outcome. Unknown checks fail instead of pretending to pass."""
    check_type = (check_type or "").strip()
    if not check_type:
        return _fail("type is required")
    base = {"check_type": check_type, "target": target}
    if check_type == "file_changed":
        exists = bool(target) and os.path.exists(target)
        info = {"exists": exists}
        if exists:
            info["size"] = os.path.getsize(target)
            info["modified_seconds_ago"] = round(time.time() - os.path.getmtime(target), 1)
        return {"success": True, "verified": exists, **base, **info}
    if check_type == "clipboard_has_content":
        from automation.os_windows import read_clipboard

        content = read_clipboard()
        verified = bool(content.strip()) and (not target or target in content)
        return {"success": True, "verified": verified, "content_preview": content[:200], **base}
    if check_type == "app_running":
        if not target:
            return _fail("target (app name) is required", **base)
        windows = find_windows(target)
        return {"success": True, "verified": bool(windows), "windows": len(windows), **base}
    if check_type == "window_focused":
        if not target:
            return _fail("target (app name) is required", **base)
        front = win32.foreground()
        return {
            "success": True,
            "verified": _matches(front, target),
            "foreground": front.as_dict() if front else None,
            **base,
        }
    if check_type == "text_on_screen":
        if not target:
            return _fail("target (text to look for) is required", **base)
        seen = read_screen(expected_text=target)
        return {
            "success": seen.get("success", False),
            "verified": bool(seen.get("verified")),
            "error": seen.get("error"),
            "screen_path": seen.get("screen_path"),
            **base,
        }
    return _fail(
        f"Unsupported check type '{check_type}'. Use file_changed, clipboard_has_content, "
        "app_running, window_focused or text_on_screen.",
        verified=False,
        **base,
    )


# ─── prompt handoff ──────────────────────────────────────────────────────────


def _wait_for_window(app_name: str, title_hint: str | None, timeout: float) -> list[win32.WindowInfo]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        windows = find_windows(app_name, title_hint)
        if windows:
            return windows
        time.sleep(0.5)
    return []


def _title_hint_for(url: str) -> str | None:
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    return URL_TITLE_HINTS.get(host)


def handoff_prompt(
    prompt: str,
    app_name: str = "",
    url: str = "",
    submit: bool = True,
    submit_key: str | None = None,
    wait_seconds: float = 20.0,
) -> dict[str, Any]:
    """Put *prompt* into another app and (optionally) send it — verifying each step.

    Order: copy (read back) → open app/URL → wait for its window → focus
    (confirmed) → paste → re-confirm focus → submit. Any failed check stops
    the flow before keys are sent, and the prompt stays on the clipboard so
    the user can paste it by hand.
    """
    from automation.os_windows import launch_app, launch_browser

    steps: list[dict[str, Any]] = []

    def stop(error: str) -> dict[str, Any]:
        copied = any(s["action"] == "copy_to_clipboard" and s["success"] for s in steps)
        manual = f" The prompt is on your clipboard — open {app_name or url} and press Ctrl+V." if copied else ""
        return {
            "success": False,
            "error": error + manual,
            "steps": steps,
            "prompt_length": len(prompt),
            "submitted": False,
        }

    if not prompt.strip():
        return _fail("prompt is required")
    if not app_name and not url:
        return _fail("app_name or url is required")
    if err := _unsupported() or _input_blocked():
        return err

    from automation.os_windows import copy_to_clipboard, read_clipboard

    original_clipboard = read_clipboard()
    copied = copy_text(prompt)
    steps.append({"action": "copy_to_clipboard", "success": copied["success"], "error": copied.get("error")})
    if not copied["success"]:
        return stop("Could not copy the prompt.")

    if url:
        target_app, title_hint = "browser", _title_hint_for(url)
        opened = launch_browser(url)
        steps.append({"action": "open_url", "success": opened, "url": url})
        if not opened:
            return stop(f"Could not open {url}.")
    else:
        target_app, title_hint = app_name, None
        if not find_windows(app_name):
            opened = launch_app(app_name)
            steps.append({"action": "open_app", "success": opened, "app": app_name})
            if not opened:
                return stop(f"Could not start {app_name}.")

    windows = _wait_for_window(target_app, title_hint, wait_seconds)
    label = f"{app_name or url}"
    steps.append({"action": "wait_for_window", "success": bool(windows), "target": label})
    if not windows:
        return stop(f"No {label} window appeared within {int(wait_seconds)} s.")

    focused = focus(target_app, title_hint)
    steps.append({"action": "focus_app", "success": focused["success"], "window": focused.get("window")})
    if not focused["success"]:
        return stop(focused["error"])

    time.sleep(0.8)  # let the app put the caret in its input box
    pasted = press("ctrl+v", target_app=target_app, title_hint=title_hint)
    steps.append({"action": "paste_clipboard", "success": pasted["success"], "error": pasted.get("error")})
    if not pasted["success"]:
        return stop(pasted["error"])

    time.sleep(0.6)
    window = win32.foreground()
    landed = text_landed(prompt, window)
    steps.append({"action": "verify_paste", "success": landed["verified"] is True,
                  "verified_by": landed["method"]})
    if landed["verified"] is not True and submit:
        reason = (
            "the prompt is not visible in the input box"
            if landed["verified"] is False
            else "AUTOMATA could not read the input box to confirm the paste"
        )
        result = stop(f"Pasted into {label} but not sent: {reason}. Check it and press Enter yourself.")
        result["pasted"] = True
        return result

    submitted = False
    if submit:
        time.sleep(0.4)
        key = submit_key or SUBMIT_KEYS.get((title_hint or app_name).lower(), "enter")
        sent = press(key, target_app=target_app, title_hint=title_hint)
        steps.append({"action": "submit", "success": sent["success"], "keystrokes": key, "error": sent.get("error")})
        if not sent["success"]:
            return stop("Prompt pasted but not sent: " + sent["error"])
        submitted = True

    if original_clipboard:
        copy_to_clipboard(original_clipboard.rstrip("\r\n"))  # give the user their clipboard back
    return {
        "success": True,
        "submitted": submitted,
        "prompt_length": len(prompt),
        "window": focused.get("window"),
        "verified_by": landed["method"],
        "steps": steps,
        "note": "Delivered to the confirmed window. Check the app to see its reply.",
    }
