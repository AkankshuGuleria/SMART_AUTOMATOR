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
from typing import Optional

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
    logger.info("os_windows.checkout_git_branch: Phase 0 stub | repo=%s branch=%s", repo_path, branch)
    return False  # stub — no real checkout


def open_terminal(cwd: str = "") -> bool:
    """
    Open a new Windows Terminal / PowerShell window in the given directory.

    Phase 3 implementation:
        subprocess.Popen(["wt", "-d", cwd], shell=False)
        Fall back to: subprocess.Popen(["powershell", "-NoExit", "-Command", f"cd '{cwd}'"])
    """
    logger.info("os_windows.open_terminal: Phase 0 stub | cwd=%s", cwd)
    return False


def open_terminal_with_command(command: str, cwd: str = "") -> Optional[int]:
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
    logger.info(
        "os_windows.open_terminal_with_command: Phase 0 stub | cmd='%s' cwd=%s",
        command[:80],
        cwd,
    )
    return None


def launch_editor(project_path: str, editor: str = "code") -> bool:
    """
    Launch the configured editor (VS Code by default) for the project.

    Phase 3 implementation:
        subprocess.Popen([editor, project_path], shell=False)
    """
    logger.info("os_windows.launch_editor: Phase 0 stub | editor=%s path=%s", editor, project_path)
    return False


def launch_browser(url: str) -> bool:
    """
    Open a URL in the default browser.

    Phase 3 implementation:
        import webbrowser; webbrowser.open(url)
    """
    logger.info("os_windows.launch_browser: Phase 0 stub | url=%s", url)
    return False
