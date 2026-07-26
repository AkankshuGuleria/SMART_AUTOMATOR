"""
automation/agent_bridge.py — AUTOMATA External Agent Bridge.

Owns:    Optional integrations with external AI/coding tools.
Never:   Does not replace core memory/retrieval logic.
         Does not modify core chat/decision flow when integrations are unavailable.
Ref:     ARCHITECTURE.md §"Automation Layer", PROJECT.md §"Driving other AI coding tools"
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ToolStatus:
    tool: str
    connected: bool
    version: Optional[str] = None
    error: Optional[str] = None


@dataclass
class BridgeResult:
    tool: str
    status: str
    output: str = ""
    prompt_log_id: Optional[str] = None
    executed: bool = False
    suggested: bool = False
    suggestion_reason: str = ""


class AgentBridge:
    """Facade for optional external tool integrations."""

    def __init__(self) -> None:
        self._status: dict[str, ToolStatus] = {}

    def status(self) -> list[ToolStatus]:
        return list(self._status.values())

    def check_tool(self, tool: str) -> ToolStatus:
        status = ToolStatus(tool=tool, connected=False)
        if tool == "claude":
            status.connected = shutil.which("claude") is not None
            if status.connected:
                try:
                    ver = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=10)
                    status.version = ver.stdout.strip() or ver.stderr.strip() or "unknown"
                except Exception as exc:
                    status.error = str(exc)
        elif tool == "cursor":
            status.connected = shutil.which("cursor") is not None or shutil.which("code") is not None
            if status.connected:
                status.version = "detected"
        elif tool == "antigravity":
            status.connected = shutil.which("antigravity") is not None
            if status.connected:
                status.version = "detected"
        else:
            status.error = "Unknown tool"

        self._status[tool] = status
        return status

    def send_prompt(self, tool: str, prompt: str, params: dict | None = None) -> BridgeResult:
        check = self.check_tool(tool)
        if not check.connected:
            return BridgeResult(tool=tool, status="unavailable", output=f"{tool} is not connected or not installed.", suggested=True, suggestion_reason=f"{tool} integration unavailable.")

        logger.info("AgentBridge: sending prompt to %s | prompt=%s", tool, prompt)
        if tool == "claude":
            return self._run_cli(tool, ["claude", "-p", prompt])
        if tool == "cursor":
            return self._run_cli(tool, ["cursor", "--cli", "--prompt", prompt])
        if tool == "antigravity":
            return self._run_cli(tool, ["antigravity", "run", prompt])

        return BridgeResult(tool=tool, status="unsupported", output=f"No integration path for {tool}.")

    def _run_cli(self, tool: str, cmd: list[str]) -> BridgeResult:
        try:
            completed = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=os.getcwd())
            output = completed.stdout or completed.stderr or ""
            logger.info("AgentBridge: %s result status=%s length=%s", tool, completed.returncode, len(output))
            return BridgeResult(tool=tool, status="ok" if completed.returncode == 0 else "error", output=output, executed=True)
        except subprocess.TimeoutExpired:
            return BridgeResult(tool=tool, status="timeout", output="Timed out waiting for response.", suggested=True, suggestion_reason="External tool timed out.")
        except Exception as exc:
            return BridgeResult(tool=tool, status="error", output=str(exc), suggested=True, suggestion_reason="Unexpected error running external tool.")
