"""
automation/no_console.py — stop background processes from flashing console windows.

The agent runs windowless (pythonw.exe). On Windows, every console program it
starts — PowerShell for OCR/clipboard, `git`, `code --version`, `netstat` — then
gets a brand-new console window, which pops up over whatever the user is doing.

install() makes CREATE_NO_WINDOW the default for every subprocess in this
process (subprocess, asyncio and libraries such as GitPython all go through
subprocess.Popen). A launch that is meant to be visible — a terminal, the Ollama
installer, dev servers — keeps working by passing CREATE_NEW_CONSOLE (or
DETACHED_PROCESS) explicitly; those calls are left untouched. GUI apps (VS Code,
Spotify, the browser) are unaffected: CREATE_NO_WINDOW only concerns consoles.
"""

from __future__ import annotations

import subprocess
import sys

CREATE_NO_WINDOW = 0x08000000
_CONSOLE_FLAGS = 0x00000010 | 0x00000008  # CREATE_NEW_CONSOLE | DETACHED_PROCESS

_installed = False


def creation_flags(flags: int) -> int:
    """Flags to use for a launch: add CREATE_NO_WINDOW unless a console was asked for."""
    if flags & _CONSOLE_FLAGS:
        return flags
    return flags | CREATE_NO_WINDOW


def install() -> bool:
    """Patch subprocess.Popen once. Returns True if active (Windows only)."""
    global _installed
    if sys.platform != "win32":
        return False
    if _installed:
        return True
    original_init = subprocess.Popen.__init__

    def __init__(self, *args, **kwargs):  # noqa: N807 - matching Popen's signature
        kwargs["creationflags"] = creation_flags(int(kwargs.get("creationflags") or 0))
        original_init(self, *args, **kwargs)

    subprocess.Popen.__init__ = __init__  # type: ignore[method-assign]
    _installed = True
    return True
