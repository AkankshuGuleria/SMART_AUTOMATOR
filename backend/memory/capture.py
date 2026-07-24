"""
memory/capture.py — AUTOMATA Persistent Memory Engine: capture pipeline.

Owns:    Observing developer activity: file system changes, git commits,
         terminal commands, TODOs from code comments.
         Writes captured events through db/client.py ONLY — never directly
         to CockroachDB from this module.
Never:   Must not contain retrieval logic (→ retrieval.py).
         Must not call Bedrock or generate embeddings (→ embeddings.py).
         Must not execute OS actions (→ automation/).
Ref:     ARCHITECTURE.md §3.2a, §4 (capture data flow), DATABASE_SCHEMA.md.

Phase 0: This module is a stub. Thread classes are defined but do not start.
Phase 1: Implement FileWatcherThread, GitPollerThread, TerminalCaptureThread.
         Wire threads in main.py → _start_background_watchers().
"""

import logging
import threading

logger = logging.getLogger(__name__)


class FileWatcherThread(threading.Thread):
    """
    Watches the active project directory for file changes and writes events
    to the `file_edits` table via db/client.get_session().

    Uses the `watchdog` library (Observer + EventHandler pattern).
    Duplicate events within a short debounce window are filtered before writing.

    Phase 1 implementation notes:
    - Use watchdog.observers.Observer with a custom FileSystemEventHandler.
    - Debounce: skip duplicate events on the same file within 500ms.
    - Write path: db/client.get_session() → INSERT INTO file_edits.
    - Redaction: file diffs (if captured) pass through the redaction step in
      memory/capture.py before any write (see SKILLS.md §6).
    """

    def __init__(self, project_path: str = "", daemon: bool = True) -> None:
        super().__init__(name="FileWatcherThread", daemon=daemon)
        self.project_path = project_path
        logger.debug("FileWatcherThread initialized (stub) | path=%s", project_path)

    def run(self) -> None:  # pragma: no cover — stub
        logger.info("FileWatcherThread.run() — Phase 0 stub, not implemented yet")


class GitPollerThread(threading.Thread):
    """
    Polls the active project's git repository for new commits and writes them
    to the `commits` table via db/client.get_session().

    Uses GitPython (`git.Repo`) to read the git log.
    Idempotent: uses (project_id, commit_hash) UNIQUE constraint to prevent
    duplicate rows on re-poll.

    Phase 1 implementation notes:
    - Poll interval: 30s (configurable via env var in Phase 1).
    - Capture: commit hash, message, author, committed_at.
    - Trigger: also fires the Decision Engine on_commit trigger (Phase 4.5).
    """

    def __init__(self, project_path: str = "", daemon: bool = True) -> None:
        super().__init__(name="GitPollerThread", daemon=daemon)
        self.project_path = project_path
        logger.debug("GitPollerThread initialized (stub) | path=%s", project_path)

    def run(self) -> None:  # pragma: no cover — stub
        logger.info("GitPollerThread.run() — Phase 0 stub, not implemented yet")


class TerminalCaptureThread(threading.Thread):
    """
    Captures terminal commands run in the context of the active project and
    writes them to the `terminal_commands` table via db/client.get_session().

    IMPORTANT: Every captured command MUST pass through `redact_secrets()`
    before being written to CockroachDB or sent to the Reasoning Engine.
    See SKILLS.md §6, §8.

    Phase 1 implementation notes:
    - Mechanism: shell history file polling or PTY interception (Windows-specific
      approach in automation/os_windows.py).
    - Redaction patterns: ghp_, AKIA, sk-, key=, token=, password=, Bearer .
    - Write path: db/client.get_session() → INSERT INTO terminal_commands.
    """

    def __init__(self, daemon: bool = True) -> None:
        super().__init__(name="TerminalCaptureThread", daemon=daemon)
        logger.debug("TerminalCaptureThread initialized (stub)")

    def run(self) -> None:  # pragma: no cover — stub
        logger.info("TerminalCaptureThread.run() — Phase 0 stub, not implemented yet")


def redact_secrets(text: str) -> str:
    """
    Redact secret-shaped strings from captured terminal commands, file diffs,
    and any other text before it is stored in CockroachDB or sent to Bedrock.

    Phase 0: Returns the input unchanged — patterns implemented in Phase 1.
    Phase 1: Add regex patterns for: ghp_, AKIA, sk-, key=<value>,
             token=<value>, password=<value>, Bearer <token>.
    See SKILLS.md §6, §8.
    """
    # TODO (Phase 1): implement redaction patterns
    return text
