"""
security/permissions.py — ask the user before AUTOMATA controls the PC.

Owns:    The permission categories (control other apps, music/volume, open apps
         and websites, read the screen, reopen the workspace, run commands), the
         user's choice per category ("ask" every time, or "allow" always), and
         single-use approvals for one specific request.
Never:   Treats a request as approved because the caller says so. An approval is
         a server-issued, single-use id bound to the category and the exact
         action text; it expires after a few minutes.

Flow for direct calls (work bar, desktop routes):
  1. check(category, action) → None when allowed, else a permission request
     {id, category, label, action} that the UI shows (Allow once / Always / Deny).
  2. The UI resends the call with permission_id=<id>; consume(id, category,
     action) succeeds once. "Always" first calls set_policy(category, "allow").
Chat actions reuse the existing approval cards: effective_policy() turns these
action types into "confirm_once" unless the category is always allowed.
"""

from __future__ import annotations

import secrets
import threading
import time
from typing import Any

CATEGORIES: dict[str, dict[str, str]] = {
    "app_control": {"label": "Control other apps",
                    "help": "Switch windows and tabs, type, paste, press keys, use the clipboard."},
    "media": {"label": "Control music and volume",
              "help": "Play, pause, skip, change volume, and play songs on Spotify."},
    "launch": {"label": "Open apps and websites",
               "help": "Start programs, open web searches and links in your browser."},
    "screen": {"label": "Read your screen",
               "help": "Take a screenshot of a window and read its text (OCR). The image is deleted right after."},
    "workspace": {"label": "Reopen your workspace",
                  "help": "Open your editor with recent files, a terminal and your dev servers."},
    "system": {"label": "Run commands",
               "help": "Run shell commands in your project."},
}

# Chat/planner action types → category.
ACTION_CATEGORY: dict[str, str] = {
    "chat_open_app": "launch", "chat_open_browser": "launch", "open_url": "launch",
    "copy_to_clipboard": "app_control", "paste_clipboard": "app_control", "focus_app": "app_control",
    "send_keystroke": "app_control", "switch_tab": "app_control", "type_text": "app_control",
    "submit_prompt_to_app": "app_control",
    "capture_screen": "screen", "read_visible_context": "screen", "diagnose_visible_error": "screen",
    "review_visible_design": "screen",
    "restore_workspace": "workspace",
    "chat_system_command": "system", "chat_run_tests": "system",
}

REQUEST_TTL_S = 5 * 60
_lock = threading.Lock()
_pending: dict[str, dict[str, Any]] = {}


def _policies() -> dict[str, str]:
    try:
        from memory.local_store import get_store

        saved = get_store().get_value("permissions", {}) or {}
    except Exception:
        saved = {}
    return {c: ("allow" if saved.get(c) == "allow" else "ask") for c in CATEGORIES}


def get_policies() -> list[dict[str, str]]:
    pol = _policies()
    return [{"category": c, "mode": pol[c], **meta} for c, meta in CATEGORIES.items()]


def set_policy(category: str, mode: str) -> dict[str, str]:
    if category not in CATEGORIES:
        raise ValueError(f"Unknown permission '{category}'.")
    if mode not in {"ask", "allow"}:
        raise ValueError("mode must be 'ask' or 'allow'.")
    from memory.local_store import get_store

    store = get_store()
    saved = dict(store.get_value("permissions", {}) or {})
    saved[category] = mode
    store.set_value("permissions", saved)
    return {"category": category, "mode": mode}


def allowed(category: str) -> bool:
    return _policies().get(category) == "allow"


def _sweep(now: float) -> None:
    for pid in [p for p, r in _pending.items() if now - r["created"] > REQUEST_TTL_S]:
        _pending.pop(pid, None)


def check(category: str, action: str, permission_id: str | None = None) -> dict[str, Any] | None:
    """None when the action may run now; otherwise the permission request to show."""
    if category not in CATEGORIES:
        raise ValueError(f"Unknown permission '{category}'.")
    if allowed(category):
        return None
    if permission_id and consume(permission_id, category, action):
        return None
    now = time.time()
    with _lock:
        _sweep(now)
        pid = secrets.token_urlsafe(16)
        _pending[pid] = {"category": category, "action": action, "created": now}
    meta = CATEGORIES[category]
    return {"id": pid, "category": category, "label": meta["label"], "help": meta["help"], "action": action}


def consume(permission_id: str, category: str, action: str) -> bool:
    """Use an approval once. It must match the category and the same action text."""
    now = time.time()
    with _lock:
        _sweep(now)
        req = _pending.get(permission_id)
        if not req or req["category"] != category or req["action"] != action:
            return False
        del _pending[permission_id]
        return True


def effective_policy(action_type: str, policy: str | None) -> str:
    """Planner policy after the user's permission choices.

    Gated categories become "confirm_once" (an approval card) unless always
    allowed; stricter policies ("require_approval", "suggest") are kept.
    """
    category = ACTION_CATEGORY.get(action_type)
    if not category:
        return policy or "suggest"
    if policy in {"require_approval", "suggest"}:
        return policy
    return "auto_execute" if allowed(category) else "confirm_once"


def needs_card(action_type: str) -> bool:
    return action_type in ACTION_CATEGORY


def reset_for_tests() -> None:
    with _lock:
        _pending.clear()
