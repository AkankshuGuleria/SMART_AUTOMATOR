"""
assist/screen.py — read and explain what is on screen, only when the user asks.

Owns:    "What's on my screen?" / "explain this error on screen": capture the
         app window the user is looking at (the front-most window that is not
         AUTOMATA, via PrintWindow so AUTOMATA's own bar never covers it), OCR
         it, redact secrets, and answer the question from that text.
Never:   Runs on its own or on a timer; keeps the screenshot (deleted after
         OCR) or sends the image anywhere — only redacted OCR text reaches the model.
"""

from __future__ import annotations

import logging
import os
import tempfile
import uuid
from typing import Any

from automation import win32

logger = logging.getLogger(__name__)

MAX_TEXT = 6000


def target_window(app: str | None = None):
    """The window to read: a named app, else the front-most non-AUTOMATA window."""
    from automation.desktop import find_windows, is_own_window

    if app:
        wins = find_windows(app)
        return wins[0] if wins else None
    for w in win32.top_level_windows():  # front-most first
        if not is_own_window(w) and w.exe.lower() not in {"explorer.exe", "textinputhost.exe"} and w.title:
            return w
    return None


def read(app: str | None = None) -> dict[str, Any]:
    """OCR the target window. Returns {ok, text, window} or {ok: False, error}."""
    if not win32.IS_WINDOWS:
        return {"ok": False, "error": "Screen reading is only available on Windows."}
    window = target_window(app)
    if window is None:
        return {"ok": False, "error": f"No {app} window is open." if app else "No app window to read."}
    path = os.path.join(tempfile.gettempdir(), f"automata-screen-{uuid.uuid4().hex}.png")
    try:
        with open(path, "wb") as fh:
            fh.write(win32.capture_window(window.hwnd))
        from automation.ocr import run_ocr

        ocr = run_ocr(path)  # redacts secrets
    except Exception as exc:
        return {"ok": False, "error": f"Could not capture {window.title or 'the window'}: {exc}"}
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    if not ocr.get("ok"):
        return {"ok": False, "error": ocr.get("error") or "OCR failed."}
    text = (ocr.get("text") or "").strip()
    return {"ok": True, "text": text[:MAX_TEXT], "window": {"title": window.title, "exe": window.exe}}


def analyze(question: str, app: str | None = None) -> dict[str, Any]:
    """Answer *question* about what is visible in the target window."""
    seen = read(app)
    if not seen["ok"]:
        return {"success": False, "error": seen["error"]}
    title = seen["window"]["title"]
    if not seen["text"]:
        return {"success": True, "answer": f"I couldn't read any text in '{title}'.", "window": seen["window"]}
    from ai.bedrock_client import invoke_reasoning

    answer = invoke_reasoning(
        "You are AUTOMATA's screen assistant. You get OCR text from the app window the developer "
        "is looking at. Answer their question from that text only. OCR can garble characters; "
        "say so if it matters. Be short and concrete: explain errors and give the fix steps.",
        f"Window: {title}\n\nQuestion: {question or 'What is on my screen?'}\n\nOCR text:\n{seen['text']}",
        [],
    )
    return {"success": True, "answer": str(answer or "").strip(), "window": seen["window"],
            "chars_read": len(seen["text"])}
