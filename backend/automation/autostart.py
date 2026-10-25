"""
automation/autostart.py — start the AUTOMATA agent when the user signs in.

Owns:    Creating/removing a per-user Startup-folder launcher on Windows that
         runs the backend hidden (pythonw), so usage tracking and capture keep
         running in the background without a console window.
Never:   Touches machine-wide settings, the registry, or other users. The
         launcher is a single file the user can delete by hand.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

LAUNCHER_NAME = "AUTOMATA Agent.vbs"
BACKEND_DIR = Path(__file__).resolve().parents[1]


def _startup_dir() -> Path | None:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def launcher_path() -> Path | None:
    folder = _startup_dir()
    return folder / LAUNCHER_NAME if folder else None


def _pythonw() -> Path:
    venv = BACKEND_DIR / ".venv" / "Scripts" / "pythonw.exe"
    if venv.exists():
        return venv
    exe = Path(sys.executable)
    candidate = exe.with_name("pythonw.exe")
    return candidate if candidate.exists() else exe


def _launcher_script() -> str:
    def vbs(s: str) -> str:
        return s.replace('"', '""')

    pyw = vbs(str(_pythonw()))
    main = vbs(str(BACKEND_DIR / "main.py"))
    cwd = vbs(str(BACKEND_DIR))
    return (
        "' Starts the AUTOMATA background agent hidden at sign-in.\r\n"
        "' Delete this file (or use AUTOMATA Settings) to stop it.\r\n"
        'Set sh = CreateObject("WScript.Shell")\r\n'
        f'sh.CurrentDirectory = "{cwd}"\r\n'
        f'sh.Run """{pyw}"" ""{main}""", 0, False\r\n'
    )


def autostart_status() -> dict:
    path = launcher_path()
    supported = sys.platform == "win32" and path is not None
    return {
        "supported": supported,
        "enabled": bool(supported and path and path.exists()),
        "launcher": str(path) if path else None,
        "command": f'"{_pythonw()}" "{BACKEND_DIR / "main.py"}"',
    }


def set_autostart(enabled: bool) -> dict:
    status = autostart_status()
    if not status["supported"]:
        return {**status, "error": "Autostart is only supported on Windows."}
    path = launcher_path()
    assert path is not None
    if enabled:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_launcher_script(), encoding="utf-8")
    elif path.exists():
        path.unlink()
    return autostart_status()
