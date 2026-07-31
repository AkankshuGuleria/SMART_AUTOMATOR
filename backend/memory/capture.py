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
 
Phase 1: Implement FileWatcherThread, GitPollerThread, TerminalCaptureThread.
          Wire threads in main.py → _start_background_watchers().
"""

import logging
import os
import re
import threading
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler

logger = logging.getLogger(__name__)

_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bghp_[A-Za-z0-9_]{20,}\b"), "ghp_[REDACTED]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AKIA[REDACTED]"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"), "sk-[REDACTED]"),
    (
        re.compile(r"(?i)\b(key|token|password)\s*=\s*([^\s;&|]+)"),
        r"\1=[REDACTED]",
    ),
    (re.compile(r"(?i)\bBearer\s+([A-Za-z0-9._~+/=-]+)"), "Bearer [REDACTED]"),
)

# File extensions to watch for changes
_WATCHED_EXTENSIONS = frozenset({
    ".py", ".ts", ".tsx", ".js", ".jsx", ".html", ".css",
    ".md", ".json", ".yaml", ".yml", ".toml", ".txt", ".rst",
    ".cfg", ".ini", ".lock",
})

# Polling intervals (seconds)
_GIT_POLL_INTERVAL = 30
_TERMINAL_POLL_INTERVAL = 5


class FileWatcherThread(threading.Thread):
    """
    Watches the active project directory for file changes and writes events
    to the `file_edits` table via db/client.get_session().

    Uses the `watchdog` library (Observer + EventHandler pattern).
    Duplicate events within a short debounce window are filtered before writing.

    Phase 1 implementation:
    - Uses watchdog.observers.Observer with a custom FileSystemEventHandler.
    - Debounce: skip duplicate events on the same file within 500ms.
    - Write path: db/client.get_session() → INSERT INTO file_edits.
    - Redaction: file diffs (if captured) pass through the redaction step in
      memory/capture.py before any write (see SKILLS.md §6).
    """

    def __init__(
        self,
        project_id: str = "",
        project_path: str = "",
        session_id: str | None = None,
        daemon: bool = True,
    ) -> None:
        super().__init__(name="FileWatcherThread", daemon=daemon)
        self.project_id = project_id
        self.project_path = project_path
        self.session_id = session_id
        self._stop_event = threading.Event()
        self._debounce: dict[str, float] = {}
        self._debounce_window = 0.5  # seconds

    def run(self) -> None:
        if not self.project_path or not os.path.isdir(self.project_path):
            logger.warning(
                "FileWatcherThread: project path not found — %s", self.project_path
            )
            return

        try:
            from watchdog.observers import Observer
        except ImportError:
            logger.error("FileWatcherThread: watchdog not installed — cannot watch files")
            return

        handler = _FileChangeHandler(self)
        observer = Observer()
        observer.schedule(handler, self.project_path, recursive=True)
        observer.start()
        logger.info(
            "FileWatcherThread started | project=%s path=%s",
            self.project_id, self.project_path,
        )

        try:
            while not self._stop_event.is_set():
                self._stop_event.wait(1)
        finally:
            observer.stop()
            observer.join()
            logger.info("FileWatcherThread stopped")

    def stop(self) -> None:
        self._stop_event.set()

    def _on_file_changed(self, file_path: str) -> None:
        """Handle a file change event — debounce then write to DB."""
        now = time.time()
        last_seen = self._debounce.get(file_path, 0)
        if now - last_seen < self._debounce_window:
            return
        self._debounce[file_path] = now

        ext = Path(file_path).suffix.lower()
        if ext not in _WATCHED_EXTENSIONS:
            return

        change_summary = f"File modified: {file_path}"
        self._write_file_edit(file_path, change_summary)

    def _write_file_edit(self, file_path: str, change_summary: str) -> None:
        """Write a file_edits row via db/client."""
        from db.client import get_session

        embedding = None
        try:
            from memory.embeddings import generate_embedding_for_capture
            embedding = generate_embedding_for_capture(change_summary)
        except Exception as exc:
            logger.debug("FileWatcherThread: embedding generation skipped — %s", exc)

        with get_session() as session:
            if session is None:
                logger.debug("FileWatcherThread: DB not available — skipping file edit")
                return
            try:
                from sqlalchemy import text
                session.execute(
                    text(
                        "INSERT INTO file_edits "
                        "(project_id, session_id, file_path, change_summary) "
                        "VALUES (:project_id, :session_id, :file_path, :change_summary)"
                    ),
                    {
                        "project_id": self.project_id,
                        "session_id": self.session_id,
                        "file_path": file_path,
                        "change_summary": change_summary,
                    },
                )
                session.commit()
                logger.debug("FileWatcherThread: recorded edit | %s", file_path)
            except Exception as exc:
                session.rollback()
                logger.error("FileWatcherThread: failed to write file edit — %s", exc)


class _FileChangeHandler(FileSystemEventHandler):
    """watchdog FileSystemEventHandler that delegates to FileWatcherThread."""

    def __init__(self, watcher: FileWatcherThread) -> None:
        super().__init__()
        self.watcher = watcher

    def on_modified(self, event):
        if event.is_directory:
            return
        self.watcher._on_file_changed(event.src_path)

    def on_created(self, event):
        if event.is_directory:
            return
        self.watcher._on_file_changed(event.src_path)


class GitPollerThread(threading.Thread):
    """
    Polls the active project's git repository for new commits and writes them
    to the `commits` table via db/client.get_session().

    Uses GitPython (`git.Repo`) to read the git log.
    Idempotent: uses (project_id, commit_hash) UNIQUE constraint to prevent
    duplicate rows on re-poll.

    Phase 1 implementation:
    - Poll interval: 30s (configurable via env var in Phase 1).
    - Capture: commit hash, message, author, committed_at.
    - Trigger: also fires the Decision Engine on_commit trigger (Phase 4.5).
    """

    def __init__(
        self,
        project_id: str = "",
        project_path: str = "",
        session_id: str | None = None,
        daemon: bool = True,
    ) -> None:
        super().__init__(name="GitPollerThread", daemon=daemon)
        self.project_id = project_id
        self.project_path = project_path
        self.session_id = session_id
        self._stop_event = threading.Event()
        self._last_commit_hash: str | None = None

    def run(self) -> None:
        if not self.project_path or not os.path.isdir(self.project_path):
            logger.warning(
                "GitPollerThread: project path not found — %s", self.project_path
            )
            return

        try:
            import git
        except ImportError:
            logger.error("GitPollerThread: GitPython not installed — cannot poll git")
            return

        try:
            repo = git.Repo(self.project_path)
        except git.InvalidGitRepositoryError:
            logger.warning(
                "GitPollerThread: not a git repo — %s", self.project_path
            )
            return

        logger.info(
            "GitPollerThread started | project=%s path=%s",
            self.project_id, self.project_path,
        )

        while not self._stop_event.is_set():
            try:
                self._poll(repo)
            except Exception as exc:
                logger.error("GitPollerThread: poll error — %s", exc)

            self._stop_event.wait(_GIT_POLL_INTERVAL)

        logger.info("GitPollerThread stopped")

    def stop(self) -> None:
        self._stop_event.set()

    def _poll(self, repo) -> None:
        """Poll for new commits since the last seen commit hash."""
        try:
            commits = list(repo.iter_commits(max_count=10))
        except Exception as exc:
            logger.error("GitPollerThread: failed to read git log — %s", exc)
            return

        if not commits:
            return

        # If we have a last seen hash, skip commits until we find it
        new_commits = commits
        if self._last_commit_hash:
            for i, commit in enumerate(commits):
                if commit.hexsha == self._last_commit_hash:
                    new_commits = commits[:i]
                    break

        if not new_commits:
            return

        # Process newest first (reverse order so oldest is inserted first)
        for commit in reversed(new_commits):
            self._write_commit(commit)

        # Update last seen hash to the most recent commit
        self._last_commit_hash = commits[0].hexsha

    def _write_commit(self, commit) -> None:
        """Write a commits row via db/client."""
        from db.client import get_session

        message_embedding = None
        try:
            from memory.embeddings import generate_embedding_for_capture
            message_embedding = generate_embedding_for_capture(commit.message.strip()[:500])
        except Exception as exc:
            logger.debug("GitPollerThread: embedding generation skipped — %s", exc)

        with get_session() as session:
            if session is None:
                logger.debug("GitPollerThread: DB not available — skipping commit")
                return
            try:
                from sqlalchemy import text
                session.execute(
                    text(
                        "INSERT INTO commits "
                        "(project_id, session_id, commit_hash, message, author, committed_at, message_embedding) "
                        "VALUES (:project_id, :session_id, :commit_hash, "
                        ":message, :author, :committed_at, :message_embedding) "
                        "ON CONFLICT (project_id, commit_hash) DO NOTHING"
                    ),
                    {
                        "project_id": self.project_id,
                        "session_id": self.session_id,
                        "commit_hash": commit.hexsha,
                        "message": commit.message.strip()[:500],
                        "author": commit.author.name or "",
                        "committed_at": commit.committed_datetime,
                        "message_embedding": message_embedding,
                    },
                )
                logger.debug(
                    "GitPollerThread: recorded commit | hash=%s msg='%s...'",
                    commit.hexsha[:8],
                    commit.message.strip()[:40],
                )

                # Fire the on_commit trigger for the Decision Engine (Phase 4.5)
                self._fire_on_commit_trigger(commit)
            except Exception as exc:
                session.rollback()
                logger.error("GitPollerThread: failed to write commit — %s", exc, exc_info=True)

    def _fire_on_commit_trigger(self, commit) -> None:
        """Fire the on_commit trigger for the Decision Engine."""
        try:
            from decision_engine.triggers import on_commit
            on_commit(self.project_id, commit.hexsha, commit.message.strip())
        except Exception as exc:
            logger.debug("GitPollerThread: on_commit trigger skipped — %s", exc)


class TerminalCaptureThread(threading.Thread):
    """
    Captures terminal commands run in the context of the active project and
    writes them to the `terminal_commands` table via db/client.get_session().

    IMPORTANT: Every captured command MUST pass through `redact_secrets()`
    before being written to CockroachDB or sent to the Reasoning Engine.
    See SKILLS.md §6, §8.

    Phase 1 implementation:
    - Mechanism: PowerShell history file polling on Windows
      (~/AppData/Roaming/Microsoft/Windows/PowerShell/PSReadLine/ConsoleHost_history.txt)
    - Redaction patterns: ghp_, AKIA, sk-, key=, token=, password=, Bearer .
    - Write path: db/client.get_session() → INSERT INTO terminal_commands.
    """

    def __init__(
        self,
        project_id: str = "",
        session_id: str | None = None,
        daemon: bool = True,
    ) -> None:
        super().__init__(name="TerminalCaptureThread", daemon=daemon)
        self.project_id = project_id
        self.session_id = session_id
        self._stop_event = threading.Event()
        self._seen_commands: set[str] = set()

    def run(self) -> None:
        history_file = self._get_history_file()
        if history_file is None:
            logger.warning(
                "TerminalCaptureThread: PowerShell history file not found — "
                "terminal capture unavailable on this system"
            )
            return

        logger.info("TerminalCaptureThread started | history=%s", history_file)

        while not self._stop_event.is_set():
            try:
                self._poll(history_file)
            except Exception as exc:
                logger.error("TerminalCaptureThread: poll error — %s", exc)

            self._stop_event.wait(_TERMINAL_POLL_INTERVAL)

        logger.info("TerminalCaptureThread stopped")

    def stop(self) -> None:
        self._stop_event.set()

    def _get_history_file(self) -> Path | None:
        """Return the path to the PowerShell ConsoleHost history file on Windows."""
        home = Path.home()
        candidate = (
            home / "AppData" / "Roaming" / "Microsoft" / "Windows"
            / "PowerShell" / "PSReadLine" / "ConsoleHost_history.txt"
        )
        if candidate.exists():
            return candidate
        return None

    def _poll(self, history_file: Path) -> None:
        """Read the history file and capture new commands."""
        try:
            lines = history_file.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception as exc:
            logger.error("TerminalCaptureThread: failed to read history — %s", exc)
            return

        for line in lines:
            line = line.strip()
            if not line or line in self._seen_commands:
                continue

            # Skip non-command lines (comments, empty, very short)
            if len(line) < 2:
                continue

            self._seen_commands.add(line)
            self._write_command(line)

    def _write_command(self, command: str) -> None:
        """Write a terminal_commands row via db/client."""
        from db.client import get_session

        redacted = redact_secrets(command)

        command_embedding = None
        try:
            from memory.embeddings import generate_embedding_for_capture
            command_embedding = generate_embedding_for_capture(redacted)
        except Exception as exc:
            logger.debug("TerminalCaptureThread: embedding generation skipped — %s", exc)

        with get_session() as session:
            if session is None:
                logger.debug("TerminalCaptureThread: DB not available — skipping command")
                return
            try:
                from sqlalchemy import text
                session.execute(
                    text(
                        "INSERT INTO terminal_commands "
                        "(project_id, session_id, command, cwd, exit_code, command_embedding) "
                        "VALUES (:project_id, :session_id, :command, :cwd, :exit_code, :command_embedding)"
                    ),
                    {
                        "project_id": self.project_id,
                        "session_id": self.session_id,
                        "command": redacted,
                        "cwd": os.getcwd(),
                        "exit_code": None,
                        "command_embedding": command_embedding,
                    },
                )
                session.commit()
                logger.debug("TerminalCaptureThread: recorded command | %s...", redacted[:60])
            except Exception:
                session.rollback()
                # Fallback: insert without command_embedding column
                # (handles older DB schemas that don't have the column yet)
                try:
                    from sqlalchemy import text
                    session.execute(
                        text(
                            "INSERT INTO terminal_commands "
                            "(project_id, session_id, command, cwd, exit_code) "
                            "VALUES (:project_id, :session_id, :command, :cwd, :exit_code)"
                        ),
                        {
                            "project_id": self.project_id,
                            "session_id": self.session_id,
                            "command": redacted,
                            "cwd": os.getcwd(),
                            "exit_code": None,
                        },
                    )
                    session.commit()
                    logger.debug("TerminalCaptureThread: recorded command (no embedding) | %s...", redacted[:60])
                except Exception as exc:
                    session.rollback()
                    logger.error("TerminalCaptureThread: failed to write command — %s", exc)


def redact_secrets(text: str) -> str:
    """
    Redact secret-shaped strings from captured terminal commands, file diffs,
    and any other text before it is stored in CockroachDB or sent to Bedrock.

    Phase 0: Returns the input unchanged — patterns implemented in Phase 1.
    Phase 1: Add regex patterns for: ghp_, AKIA, sk-, key=<value>,
             token=<value>, password=<value>, Bearer <token>.
    See SKILLS.md §6, §8.
    """
    redacted = text
    for pattern, replacement in _SECRET_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted
