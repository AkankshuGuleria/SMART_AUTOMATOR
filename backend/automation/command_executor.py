"""
automation/command_executor.py — AUTOMATA System Command Execution.

Owns:    Executing safe, reversible system commands requested via chat,
         logging full provenance, and enforcing suggest-vs-execute policy.
Never:   Does not write to CockroachDB directly; uses db/client.py.
         Does not call Bedrock directly; uses ai/bedrock_client.py.
Ref:     ARCHITECTURE.md §"Automation Layer", SKILLS.md §10, PROJECT.md §9
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


@dataclass
class CommandResult:
    command: str
    status: str
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    executed: bool = False
    suggested: bool = False
    suggestion_reason: str = ""
    executed_at: str | None = None
    undo_hint: str | None = None


@dataclass
class ExecutionPolicy:
    auto_execute: bool = False
    reversible: bool = False
    risk: str = "low"
    requires_confirmation: bool = False
    undo_hint: str | None = None


class CommandExecutor:
    """Execute system commands with provenance and safety checks."""

    _POLICIES: dict[str, ExecutionPolicy] = {
        "run_tests": ExecutionPolicy(
            auto_execute=True,
            reversible=False,
            risk="low",
            undo_hint="Rerun previous command or restore workspace state",
        ),
        "start_dev_env": ExecutionPolicy(
            auto_execute=False,
            reversible=True,
            risk="medium",
            requires_confirmation=True,
            undo_hint="Stop dev environment",
        ),
        "stop_dev_env": ExecutionPolicy(
            auto_execute=False,
            reversible=True,
            risk="medium",
            requires_confirmation=True,
            undo_hint="Restart dev environment",
        ),
        "npm_install": ExecutionPolicy(
            auto_execute=False,
            reversible=True,
            risk="medium",
            requires_confirmation=True,
            undo_hint="npm uninstall <package>",
        ),
        "git_checkout": ExecutionPolicy(
            auto_execute=False,
            reversible=True,
            risk="medium",
            requires_confirmation=True,
            undo_hint="git checkout <previous_branch>",
        ),
        "git_commit": ExecutionPolicy(
            auto_execute=False,
            reversible=True,
            risk="medium",
            requires_confirmation=True,
            undo_hint="git reset --soft HEAD~1",
        ),
        "run_command": ExecutionPolicy(
            auto_execute=False,
            reversible=False,
            risk="high",
            requires_confirmation=True,
            undo_hint="Process-specific; often not reversible",
        ),
    }

    def __init__(self, cwd: str = "", allow_auto_execute: bool = False) -> None:
        self.cwd = cwd or os.getcwd()
        self.allow_auto_execute = allow_auto_execute

    def execute(
        self, command: str, context: str = "", session_id: str | None = None
    ) -> CommandResult:
        policy = self._POLICIES.get(
            self._match_policy(command),
            ExecutionPolicy(
                auto_execute=False, reversible=False, risk="high", requires_confirmation=True
            ),
        )
        result = CommandResult(
            command=command,
            status="suggested"
            if policy.requires_confirmation and not self.allow_auto_execute
            else "executed",
            suggested=policy.requires_confirmation and not self.allow_auto_execute,
            suggestion_reason=policy.requires_confirmation
            and not self.allow_auto_execute
            and "This command requires confirmation before execution."
            or "",
            undo_hint=policy.undo_hint,
        )

        from memory.capture import redact_secrets

        log_payload = {
            "command": redact_secrets(command),
            "policy": policy.risk,
            "context": context,
            "session_id": session_id,
            "suggested": result.suggested,
            "executed_at": datetime.now(UTC).isoformat(),
        }
        logger.info("CommandExecutor: %s", log_payload)

        if result.suggested:
            return result

        try:
            # Shell on purpose: the user's own command, approved via permission 'system'.
            completed = subprocess.run(  # noqa: S602
                command,
                shell=True,  # nosec B602 — the user's own command, approved via permission "system"
                cwd=self.cwd,
                capture_output=True,
                text=True,
                timeout=300,
            )
            result.stdout = completed.stdout or ""
            result.stderr = completed.stderr or ""
            result.exit_code = completed.returncode
            result.executed = True
            result.executed_at = datetime.now(UTC).isoformat()
            result.status = "ok" if completed.returncode == 0 else "error"
        except subprocess.TimeoutExpired:
            result.status = "timeout"
            result.stderr = "Command timed out"
            result.executed = False
        except Exception as exc:
            result.status = "error"
            result.stderr = str(exc)
            result.executed = False

        logger.info(
            "CommandExecutor result: %s",
            {
                "command": command,
                "status": result.status,
                "executed": result.executed,
                "undo_hint": result.undo_hint,
            },
        )
        return result

    @staticmethod
    def _match_policy(command: str) -> str:
        lowered = command.lower()
        if any(k in lowered for k in ["pytest", "npm test", "dotnet test", "cargo test"]):
            return "run_tests"
        if any(
            k in lowered for k in ["npm run dev", "npm start", "uvicorn", "dotnet run", "cargo run"]
        ):
            return "start_dev_env"
        if any(k in lowered for k in ["npm install", "pip install", "dotnet add", "cargo add"]):
            return "npm_install"
        if lowered.startswith("git checkout"):
            return "git_checkout"
        if lowered.startswith("git commit"):
            return "git_commit"
        if any(k in lowered for k in ["stop", "kill", "taskkill", "pkill"]):
            return "stop_dev_env"
        return "run_command"
