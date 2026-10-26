"""
automation/os_windows.py — AUTOMATA Automation Layer: Windows OS interface.

Owns:    All Windows-specific OS automation primitives used by restore.py
          and dev_servers.py. This is the ONLY file that calls Windows APIs
          directly — all other automation modules call this interface.
Never:   Must not write to CockroachDB. Must not call Bedrock.
          Must not be called from Memory Engine or Reasoning Engine code.
Ref:     ARCHITECTURE.md §3.2c, §6 (Windows primary OS), TECH_STACK.md.

Primary OS: Windows (decided — see ARCHITECTURE.md §6).
API strategy: subprocess + PowerShell for process control; win32api/pywin32
for credential vault integration (deferred to Phase 1 — keyring abstracts this).

Phase 0: All functions are stubs that log and return safely.
Phase 3: Implement real Windows OS calls.
"""

import logging
import os
import re
import subprocess
import tempfile

logger = logging.getLogger(__name__)


def checkout_git_branch(repo_path: str, branch: str) -> bool:
    """
    Checkout the specified git branch in the given repository.

    Returns True on success, False on failure.
    Failures are logged — callers must degrade gracefully per ARCHITECTURE.md §10.

    Phase 3 implementation:
        import git
        repo = git.Repo(repo_path)
        repo.git.checkout(branch)
    """
    try:
        import git

        repo = git.Repo(repo_path)
        repo.git.checkout(branch)
        logger.info(
            "os_windows.checkout_git_branch: success | repo=%s branch=%s",
            repo_path,
            branch,
        )
        return True
    except Exception as exc:
        logger.error(
            "os_windows.checkout_git_branch: failed | repo=%s branch=%s error=%s",
            repo_path,
            branch,
            exc,
        )
        return False


def open_terminal(cwd: str = "") -> bool:
    """
    Open a new Windows Terminal / PowerShell window in the given directory.

    Phase 3 implementation:
        subprocess.Popen(["wt", "-d", cwd], shell=False)
        Fall back to: subprocess.Popen(["powershell", "-NoExit", "-Command", f"cd '{cwd}'"])
    """
    try:
        # Try Windows Terminal first
        subprocess.Popen(
            ["wt", "-d", cwd],
            shell=False,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
        logger.info("os_windows.open_terminal: opened Windows Terminal | cwd=%s", cwd)
        return True
    except FileNotFoundError:
        pass  # wt not available, fall through
    except Exception as exc:
        logger.warning("os_windows.open_terminal: wt failed — %s", exc)

    try:
        # Fall back to PowerShell
        subprocess.Popen(
            ["powershell", "-NoExit", "-Command", f"cd '{cwd}'"],
            shell=False,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
        logger.info("os_windows.open_terminal: opened PowerShell | cwd=%s", cwd)
        return True
    except Exception as exc:
        logger.error(
            "os_windows.open_terminal: failed to open terminal | cwd=%s error=%s",
            cwd,
            exc,
        )
        return False


def open_terminal_with_command(command: str, cwd: str = "") -> int | None:
    """
    Open a Windows Terminal window and execute the given command.

    Returns the PID of the launched process, or None on failure.
    Used by dev_servers.py to start each server in its own terminal window.

    Phase 3 implementation:
        proc = subprocess.Popen(
            ["wt", "-d", cwd, "powershell", "-NoExit", "-Command", command],
            shell=False,
        )
        return proc.pid
    """
    try:
        proc = subprocess.Popen(
            ["wt", "-d", cwd, "powershell", "-NoExit", "-Command", command],
            shell=False,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
        logger.info(
            "os_windows.open_terminal_with_command: started | pid=%d cmd='%s' cwd=%s",
            proc.pid,
            command[:80],
            cwd,
        )
        return proc.pid
    except FileNotFoundError:
        pass  # wt not available
    except Exception as exc:
        logger.error(
            "os_windows.open_terminal_with_command: failed | cmd='%s' cwd=%s error=%s",
            command[:80],
            cwd,
            exc,
        )
    return None


def launch_editor(project_path: str, editor: str = "code") -> bool:
    """
    Launch the configured editor (VS Code by default) for the project.

    Phase 3 implementation:
        subprocess.Popen([editor, project_path], shell=False)
    """
    try:
        # The editor is a GUI app; its `code.cmd`-style launcher must not get a
        # console window of its own (no_console adds CREATE_NO_WINDOW).
        subprocess.Popen([editor, project_path], shell=False)
        logger.info("os_windows.launch_editor: launched | editor=%s path=%s", editor, project_path)
        return True
    except FileNotFoundError:
        logger.warning("os_windows.launch_editor: editor not found — %s", editor)
        return False
    except Exception as exc:
        logger.error(
            "os_windows.launch_editor: failed | editor=%s path=%s error=%s",
            editor,
            project_path,
            exc,
        )
        return False


def launch_browser(url: str) -> bool:
    """
    Open a URL in the default browser.
    """
    try:
        if not url:
            url = "https://www.google.com"
        os.startfile(url)  # type: ignore[attr-defined]
        logger.info("os_windows.launch_browser: opened | url=%s", url)
        return True
    except Exception as exc:
        logger.error("os_windows.launch_browser: failed | url=%s error=%s", url, exc)
        return False


# Maps common friendly names to Windows executable names
_EXECUTABLE_MAP: dict[str, str] = {
    "code": "code",
    "vscode": "code",
    "notepad": "notepad",
    "notepad++": "notepad++",
    "calc": "calc",
    "calculator": "calc",
    "explorer": "explorer",
    "chrome": "chrome",
    "firefox": "firefox",
    "msedge": "msedge",
    "edge": "msedge",
    "wt": "wt",
    "terminal": "wt",
    "powershell": "powershell",
    "cmd": "cmd",
    "taskmgr": "taskmgr",
    "task manager": "taskmgr",
    "slack": "slack",
    "discord": "discord",
    "spotify": "spotify",
    "figma": "figma",
    "postman": "Postman",
}


def launch_app(app_name: str) -> bool:
    """
    Launch a named desktop application by executable name or common alias.

    Looks up `app_name` in the executable map first, then tries it directly
    as an executable. Falls back gracefully and logs the failure.
    """
    exe = _EXECUTABLE_MAP.get(app_name.lower().strip(), app_name.strip())
    # Handle special protocol URLs (ms-settings: etc.)
    if exe.startswith(("ms-", "http://", "https://")):
        try:
            os.startfile(exe)  # type: ignore[attr-defined]
            logger.info("os_windows.launch_app: protocol launch | target=%s", exe)
            return True
        except Exception as exc:
            logger.error(
                "os_windows.launch_app: protocol launch failed | target=%s error=%s", exe, exc
            )
            return False

    _run_timeout = 8

    # If the mapped value looks like a composite shell command
    # (e.g. "rundll32 sysdm.cpl,EditEnvironmentVariables"), execute it
    # directly via PowerShell -Command. Wrapping it in Start-Process
    # -FilePath makes PowerShell look for one non-existent executable.
    if re.search(r"\s|,|&|\|", exe):
        try:
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-Command", exe],
                shell=False,
                capture_output=True,
                text=True,
                timeout=_run_timeout,
            )
            if completed.returncode != 0:
                stderr = (completed.stderr or completed.stdout or "").strip()
                logger.warning(
                    "os_windows.launch_app: shell command failed | app=%s exe=%s error=%s",
                    app_name,
                    exe,
                    stderr,
                )
                return False
            logger.info("os_windows.launch_app: launched | app=%s exe=%s", app_name, exe)
            return True
        except Exception as exc:
            logger.error(
                "os_windows.launch_app: failed | app=%s exe=%s error=%s", app_name, exe, exc
            )
            return False

    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f'Start-Process -FilePath "{exe}"',
            ],
            shell=False,
            capture_output=True,
            text=True,
            timeout=_run_timeout,
        )
        if completed.returncode != 0:
            stderr = (completed.stderr or completed.stdout or "").strip()
            logger.warning(
                "os_windows.launch_app: Start-Process failed | app=%s exe=%s error=%s",
                app_name,
                exe,
                stderr,
            )
            return False
        logger.info("os_windows.launch_app: launched | app=%s exe=%s", app_name, exe)
        return True
    except Exception as exc:
        logger.error("os_windows.launch_app: failed | app=%s exe=%s error=%s", app_name, exe, exc)
        return False


# ─── Cross-app control primitives ──────────────────────────────────────

_CLIPBOARD_CMDLINE_LIMIT = 8000


def copy_to_clipboard(text: str) -> bool:
    """
    Copy the given text to the Windows clipboard.

    For text exceeding the Windows command-line length limit (~8191 chars),
    a temp file is written and piped via ``Get-Content -Raw | Set-Clipboard``
    so that arbitrarily large prompts are delivered intact.

    Returns True on success, False on failure.
    """
    if not text:
        logger.warning("os_windows.copy_to_clipboard: empty text provided")
        return False
    # Native Win32 first: exact Unicode (em dashes, emoji, any language), no
    # PowerShell process, no code-page round-trip.
    from automation import win32

    if win32.IS_WINDOWS and win32.set_clipboard_text(text):
        return True
    try:
        if len(text) <= _CLIPBOARD_CMDLINE_LIMIT:
            # Short text — pass directly as a command-line argument
            escaped = text.replace("'", "''")
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-Command", f"Set-Clipboard -Value '{escaped}'"],
                shell=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
        else:
            # Large text — write to a temp file and stream via Get-Content
            # to avoid hitting Windows' ~8191 char command-line limit.
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".txt", prefix="automata_clip_")
            try:
                with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
                    fh.write(text)
                completed = subprocess.run(
                    [
                        "powershell",
                        "-NoProfile",
                        "-Command",
                        f"Get-Content -Path '{tmp_path}' -Raw | Set-Clipboard",
                    ],
                    shell=False,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        if completed.returncode != 0:
            stderr = (completed.stderr or completed.stdout or "").strip()
            logger.warning("os_windows.copy_to_clipboard: Set-Clipboard failed — %s", stderr)
            return False
        logger.info("os_windows.copy_to_clipboard: copied %d chars to clipboard", len(text))
        return True
    except Exception as exc:
        logger.error("os_windows.copy_to_clipboard: failed — %s", exc)
        return False


def read_clipboard() -> str:
    """
    Retrieve the current clipboard content via PowerShell Get-Clipboard.

    Returns the clipboard text on success, or an empty string on failure.
    """
    from automation import win32

    if win32.IS_WINDOWS:
        native = win32.get_clipboard_text()
        if native is not None:
            return native
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-Clipboard -Raw"],
            shell=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        if completed.returncode != 0:
            stderr = (completed.stderr or completed.stdout or "").strip()
            logger.warning("os_windows.paste_clipboard: Get-Clipboard failed — %s", stderr)
            return ""
        return completed.stdout
    except Exception as exc:
        logger.error("os_windows.read_clipboard: failed — %s", exc)
        return ""


def paste_clipboard(target_app: str | None = None) -> bool:
    """Paste into *target_app* (or the active window) — True only when delivered
    to a verified window. See automation/desktop.py for the detailed result."""
    from automation.desktop import paste

    return bool(paste(target_app)["success"])


def focus_app(app_name: str) -> bool:
    """Bring *app_name* to the foreground; True only if Windows confirms the switch."""
    from automation.desktop import focus

    return bool(focus(app_name)["success"])


def send_keystrokes(keystrokes: str, target_app: str | None = None) -> bool:
    """Send an allowed chord; refuses when the target (or AUTOMATA itself) is wrong."""
    from automation.desktop import press

    return bool(press(keystrokes, target_app=target_app)["success"])


def capture_screen(region: str | None = None) -> str:
    """Screenshot the primary screen or a 'left,top,width,height' region.

    Returns the PNG path, or '' on failure. DPI-correct and uniquely named.
    """
    from automation.desktop import capture

    result = capture(region=region)
    return result["path"] if result["success"] else ""


