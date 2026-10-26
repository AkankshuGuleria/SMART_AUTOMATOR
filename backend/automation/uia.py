"""
automation/uia.py — Windows UI Automation helpers (via comtypes).

Owns:    Reading what is inside other apps' windows (focused field text, browser
         tabs) and selecting a browser tab — the "read back" that turns blind
         keystrokes into verified actions.
Never:   Sends keystrokes or clicks by coordinates. Every function degrades to
         an explicit "unavailable" result when UIA cannot answer.
"""

from __future__ import annotations

import logging
import sys
import threading
from typing import Any

logger = logging.getLogger(__name__)

_local = threading.local()


def available() -> bool:
    return sys.platform == "win32" and _client() is not None


def _client():
    """Per-thread IUIAutomation (COM must be initialised in each thread)."""
    if sys.platform != "win32":
        return None
    cached = getattr(_local, "uia", None)
    if cached is not None:
        return cached
    try:
        import comtypes
        import comtypes.client

        try:
            comtypes.CoInitialize()
        except OSError:
            pass  # already initialised in this thread
        mod = comtypes.client.GetModule("UIAutomationCore.dll")
        uia = comtypes.client.CreateObject(mod.CUIAutomation, interface=mod.IUIAutomation)
        _local.uia, _local.mod = uia, mod
        return uia
    except Exception as exc:
        logger.debug("UI Automation unavailable — %s", exc)
        _local.uia = None
        return None


def _mod():
    _client()
    return getattr(_local, "mod", None)


def _element_text(el, include_name: bool = True) -> str:
    """Best-effort text of an element: Value, then Text pattern, then Name.

    Rich chat inputs (contenteditable in Electron apps) keep a stale "\\n" in
    the Value pattern while the Text pattern has the real content, so
    whitespace-only answers fall through to the next source.
    """
    mod = _mod()
    getters = [
        lambda: el.GetCurrentPattern(mod.UIA_ValuePatternId).QueryInterface(mod.IUIAutomationValuePattern).CurrentValue,
        lambda: el.GetCurrentPattern(mod.UIA_TextPatternId).QueryInterface(mod.IUIAutomationTextPattern).DocumentRange.GetText(20000),
    ]
    if include_name:
        getters.append(lambda: el.CurrentName)
    for getter in getters:
        try:
            text = getter()
            if text and visible_text(str(text)):
                return str(text)
        except Exception:
            continue
    return ""


# Invisible characters rich editors put in "empty" boxes: object replacement
# (Kilo Code's placeholder span), zero-width space/joiners, BOM.
_INVISIBLE = dict.fromkeys(map(ord, "￼​‌‍﻿"), None)


def visible_text(text: str) -> str:
    """*text* without invisible placeholder characters and surrounding whitespace."""
    return (text or "").translate(_INVISIBLE).strip()


def focused_text() -> dict[str, Any]:
    """Text of the keyboard-focused element (e.g. a chat input box)."""
    uia = _client()
    if uia is None:
        return {"ok": False, "error": "UI Automation unavailable"}
    try:
        el = uia.GetFocusedElement()
        return {
            "ok": True,
            "text": _element_text(el),
            "control_type": int(el.CurrentControlType),
            "name": el.CurrentName or "",
        }
    except Exception as exc:
        return {"ok": False, "error": f"Could not read the focused element: {exc}"}


def browser_tabs(hwnd: int) -> dict[str, Any]:
    """Tab titles in a browser window (Chrome, Edge, Brave, Firefox)."""
    uia, mod = _client(), _mod()
    if uia is None:
        return {"ok": False, "error": "UI Automation unavailable", "tabs": []}
    try:
        root = uia.ElementFromHandle(hwnd)
        cond = uia.CreatePropertyCondition(mod.UIA_ControlTypePropertyId, mod.UIA_TabItemControlTypeId)
        found = root.FindAll(mod.TreeScope_Descendants, cond)
        tabs = []
        for i in range(found.Length):
            item = found.GetElement(i)
            selected = False
            try:
                pat = item.GetCurrentPattern(mod.UIA_SelectionItemPatternId)
                selected = bool(pat.QueryInterface(mod.IUIAutomationSelectionItemPattern).CurrentIsSelected)
            except Exception:
                pass
            name = (item.CurrentName or "").strip()
            if name:
                tabs.append({"index": len(tabs), "title": name, "selected": selected})
        return {"ok": True, "tabs": tabs}
    except Exception as exc:
        return {"ok": False, "error": f"Could not read tabs: {exc}", "tabs": []}


def select_tab(hwnd: int, title_contains: str) -> dict[str, Any]:
    """Select the first tab whose title contains *title_contains* (case-insensitive)."""
    uia, mod = _client(), _mod()
    if uia is None:
        return {"ok": False, "error": "UI Automation unavailable"}
    needle = title_contains.lower().strip()
    try:
        root = uia.ElementFromHandle(hwnd)
        cond = uia.CreatePropertyCondition(mod.UIA_ControlTypePropertyId, mod.UIA_TabItemControlTypeId)
        found = root.FindAll(mod.TreeScope_Descendants, cond)
        for i in range(found.Length):
            item = found.GetElement(i)
            name = item.CurrentName or ""
            if needle and needle in name.lower():
                for pattern_id, iface, method in (
                    (mod.UIA_SelectionItemPatternId, mod.IUIAutomationSelectionItemPattern, "Select"),
                    (mod.UIA_InvokePatternId, mod.IUIAutomationInvokePattern, "Invoke"),
                    (mod.UIA_LegacyIAccessiblePatternId, mod.IUIAutomationLegacyIAccessiblePattern, "DoDefaultAction"),
                ):
                    try:
                        pat = item.GetCurrentPattern(pattern_id).QueryInterface(iface)
                        getattr(pat, method)()
                        return {"ok": True, "title": name}
                    except Exception:
                        continue
                return {"ok": False, "error": f"Tab '{name}' cannot be selected through UI Automation"}
        return {"ok": False, "error": f"No tab containing '{title_contains}'"}
    except Exception as exc:
        return {"ok": False, "error": f"Could not switch tabs: {exc}"}
