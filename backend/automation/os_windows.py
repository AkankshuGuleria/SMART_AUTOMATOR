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
import subprocess

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
            repo_path, branch,
        )
        return True
    except Exception as exc:
        logger.error(
            "os_windows.checkout_git_branch: failed | repo=%s branch=%s error=%s",
            repo_path, branch, exc,
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
            cwd, exc,
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
            proc.pid, command[:80], cwd,
        )
        return proc.pid
    except FileNotFoundError:
        pass  # wt not available
    except Exception as exc:
        logger.error(
            "os_windows.open_terminal_with_command: failed | cmd='%s' cwd=%s error=%s",
            command[:80], cwd, exc,
        )
    return None


def launch_editor(project_path: str, editor: str = "code") -> bool:
    """
    Launch the configured editor (VS Code by default) for the project.

    Phase 3 implementation:
        subprocess.Popen([editor, project_path], shell=False)
    """
    try:
        subprocess.Popen(
            [editor, project_path],
            shell=False,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
        logger.info("os_windows.launch_editor: launched | editor=%s path=%s", editor, project_path)
        return True
    except FileNotFoundError:
        logger.warning("os_windows.launch_editor: editor not found — %s", editor)
        return False
    except Exception as exc:
        logger.error(
            "os_windows.launch_editor: failed | editor=%s path=%s error=%s",
            editor, project_path, exc,
        )
        return False


def launch_browser(url: str) -> bool:
    """
    Open a URL in the default browser.
    """
    try:
        import webbrowser
        webbrowser.open(url)
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
    if exe.startswith("ms-"):
        try:
            import webbrowser
            webbrowser.open(exe)
            logger.info("os_windows.launch_app: protocol launch | target=%s", exe)
            return True
        except Exception as exc:
            logger.error("os_windows.launch_app: protocol launch failed | target=%s error=%s", exe, exc)
            return False
    try:
        subprocess.Popen(
            [exe],
            shell=False,
            creationflags=subprocess.CREATE_NEW_CONSOLE if hasattr(subprocess, "CREATE_NEW_CONSOLE") else 0,
        )
        logger.info("os_windows.launch_app: launched | app=%s exe=%s", app_name, exe)
        return True
    except FileNotFoundError:
        # Try with shell=True as a fallback (handles PATH-dependent programs)
        try:
            subprocess.Popen(exe, shell=True)  # noqa: S602
            logger.info("os_windows.launch_app: shell fallback launched | app=%s", app_name)
            return True
        except Exception as exc2:
            logger.warning("os_windows.launch_app: shell fallback failed | app=%s error=%s", app_name, exc2)
            return False
    except Exception as exc:
        logger.error("os_windows.launch_app: failed | app=%s exe=%s error=%s", app_name, exe, exc)
        return False
