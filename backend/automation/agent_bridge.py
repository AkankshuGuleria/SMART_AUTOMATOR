"""
automation/agent_bridge.py — AUTOMATA External Agent Bridge.

Owns:    Detecting external AI/coding tools (Claude, Cursor, Antigravity) and
         handing them a prompt through the most reliable path available.
Never:   Invents CLI flags, or pastes into an IDE window where the text would
         land in an open file instead of the agent panel. When no verified
         path exists it says so and leaves the prompt on the clipboard.
Ref:     docs/SMART_WORKSPACE_PLAN.md (Phase 0 / Phase 4).
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ToolStatus:
    tool: str
    connected: bool  # True when a prompt can be delivered (cli or verified ui path)
    version: str | None = None
    error: str | None = None
    installed: bool = False
    prompt_via: str | None = None  # "cli" | "ide_chat" | "ui" | None
    cli_path: str | None = None
    app_path: str | None = None


@dataclass
class BridgeResult:
    tool: str
    status: str
    output: str = ""
    prompt_log_id: str | None = None
    executed: bool = False
    suggested: bool = False
    suggestion_reason: str = ""


def _first_existing(*paths: str | Path | None) -> str | None:
    for p in paths:
        if p and Path(p).exists():
            return str(p)
    return None


def _local(*parts: str) -> Path:
    return Path(os.environ.get("LOCALAPPDATA", "")).joinpath(*parts)


def _roaming(*parts: str) -> Path:
    return Path(os.environ.get("APPDATA", "")).joinpath(*parts)


def _detect(tool: str) -> ToolStatus:
    from automation import chat_apps

    status = ToolStatus(tool=tool, connected=False)
    if tool == "claude":
        # Claude Code CLI is scriptable (`claude -p`); the desktop app is a chat window.
        status.cli_path = shutil.which("claude") or _first_existing(_roaming("npm", "claude.cmd"))
        status.app_path = _first_existing(
            _local("AnthropicClaude", "claude.exe"), _local("Programs", "Claude", "Claude.exe")
        )
        if status.cli_path:
            status.prompt_via = "cli"
        elif status.app_path or _running("claude.exe"):
            status.prompt_via = "app_chat"
    elif tool == "cursor":
        status.cli_path = shutil.which("cursor-agent")  # Cursor's agent CLI (`cursor-agent -p`)
        status.app_path = shutil.which("cursor") or _first_existing(
            _local("Programs", "cursor", "Cursor.exe"),
            _local("Programs", "cursor", "resources", "app", "bin", "cursor.cmd"),
        )
        status.prompt_via = "cli" if status.cli_path else ("app_chat" if status.app_path else None)
    elif tool == "antigravity":
        # Its `chat` CLI opens VS Code's stock chat view, not Antigravity's agent,
        # so the prompt goes into the Agent panel's "Message input" instead.
        status.cli_path = shutil.which("antigravity-ide") or _first_existing(
            _local("Programs", "Antigravity IDE", "bin", "antigravity-ide.cmd")
        )
        status.app_path = status.cli_path or _first_existing(_local("Programs", "Antigravity", "Antigravity.exe"))
        if chat_apps.installed("antigravity") or chat_apps.installed("antigravity_app"):
            status.prompt_via = "app_chat"
    elif tool == "vscode":
        status.cli_path = shutil.which("code") or _first_existing(
            _local("Programs", "Microsoft VS Code", "bin", "code.cmd")
        )
        status.app_path = status.cli_path
        status.prompt_via = "ide_chat" if status.cli_path else None
    else:
        status.error = "Unknown tool"
        return status

    status.installed = bool(status.cli_path or status.app_path or status.prompt_via)
    status.connected = status.prompt_via is not None
    if status.installed and not status.connected:
        status.error = (
            f"{tool} is installed but has no verified way to receive a prompt yet; "
            "AUTOMATA will copy the prompt for you to paste into its agent panel."
        )
    return status


def _running(exe: str) -> bool:
    try:
        import psutil

        return any((p.info.get("name") or "").lower() == exe for p in psutil.process_iter(["name"]))
    except Exception:
        return False


class AgentBridge:
    """Facade for optional external tool integrations."""

    def __init__(self) -> None:
        self._status: dict[str, ToolStatus] = {}

    def status(self) -> list[ToolStatus]:
        return list(self._status.values())

    def check_tool(self, tool: str) -> ToolStatus:
        status = _detect(tool)
        if status.prompt_via == "cli" and status.cli_path:
            try:
                ver = subprocess.run(
                    [status.cli_path, "--version"], capture_output=True, text=True, timeout=10
                )
                status.version = (ver.stdout or ver.stderr).strip() or "unknown"
            except Exception as exc:
                status.error = str(exc)
        elif status.installed:
            status.version = "installed"
        self._status[tool] = status
        return status

    def send_prompt(self, tool: str, prompt: str, params: dict | None = None) -> BridgeResult:
        from memory.capture import redact_secrets

        prompt = redact_secrets(prompt)
        check = self.check_tool(tool)

        if check.prompt_via == "cli" and check.cli_path:
            logger.info("AgentBridge: %s via CLI | prompt_length=%d", tool, len(prompt))
            return self._run_cli(tool, [check.cli_path, "-p", prompt])

        if check.prompt_via == "ide_chat" and check.cli_path:
            return self._ide_chat(tool, check.cli_path, prompt, (params or {}).get("repo_path"))

        if check.prompt_via == "app_chat":
            return self._app_chat(tool, prompt, params or {})

        # Installed but no verified path, or not installed at all: copy and explain.
        copied = False
        if check.installed:
            from automation.desktop import copy_text

            copied = copy_text(prompt).get("success", False)
        reason = check.error or f"{tool} is not installed."
        if copied:
            reason += " The prompt is on your clipboard."
        return BridgeResult(
            tool=tool,
            status="unsupported" if check.installed else "unavailable",
            output=reason,
            suggested=True,
            suggestion_reason=reason,
        )

    def _app_chat(self, tool: str, prompt: str, params: dict) -> BridgeResult:
        """Verified hand-off into the app's chat box (see automation/chat_apps.py)."""
        from automation import chat_apps
        from automation.desktop import copy_text

        key = tool
        folder = params.get("repo_path")
        if tool == "antigravity" and not chat_apps.installed("antigravity"):
            key = "antigravity_app"  # only the desktop agent app is installed
        result = chat_apps.deliver(key, prompt, folder=folder, submit=params.get("submit", True))
        steps = "; ".join(result.get("steps", []))
        if result["success"]:
            done = "Sent to" if result.get("submitted") else "Pasted into"
            return BridgeResult(tool=tool, status="ok", executed=bool(result.get("submitted")),
                                output=f"{done} {chat_apps.APPS[key].label}. {steps}".strip())
        # Leave the prompt where the user can paste it themselves.
        copied = copy_text(prompt).get("success", False)
        reason = result.get("error", "Hand-off failed.") + (" The prompt is on your clipboard." if copied else "")
        return BridgeResult(tool=tool, status="error", output=f"{reason} ({steps})" if steps else reason,
                            suggested=True, suggestion_reason=reason)

    def _ide_chat(self, tool: str, cli: str, prompt: str, repo_path: str | None) -> BridgeResult:
        """Open the project in the IDE, then start an agent chat with *prompt*.

        The prompt goes through stdin (`chat <intro> -`) so long prompts are not
        cut by the Windows command-line limit. The CLI returns once the IDE has
        the request; the agent then works inside the IDE.
        """
        try:
            if repo_path and os.path.isdir(repo_path):
                subprocess.run([cli, repo_path], capture_output=True, text=True, timeout=60)
            completed = subprocess.run(
                [cli, "chat", "--mode", "agent", "--reuse-window", "Complete the task below.", "-"],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=120,
            )
            ok = completed.returncode == 0
            return BridgeResult(
                tool=tool,
                status="ok" if ok else "error",
                output=(
                    f"Asked {tool} to open its chat with the prompt"
                    + (f" in {repo_path}" if repo_path else "")
                    + ". The IDE accepted the command, but AUTOMATA cannot see its chat box to confirm"
                    " the agent received it — check the chat panel."
                    if ok
                    else (completed.stderr or completed.stdout or "IDE chat command failed").strip()
                ),
                executed=ok,
            )
        except subprocess.TimeoutExpired:
            return BridgeResult(tool=tool, status="timeout", output=f"{tool} did not accept the prompt in time.",
                                suggested=True, suggestion_reason="IDE did not respond.")
        except Exception as exc:
            return BridgeResult(tool=tool, status="error", output=str(exc), suggested=True,
                                suggestion_reason="Could not run the IDE command.")

    def _run_cli(self, tool: str, cmd: list[str]) -> BridgeResult:
        try:
            completed = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300, cwd=os.getcwd()
            )
            output = completed.stdout or completed.stderr or ""
            logger.info(
                "AgentBridge: %s result status=%s length=%s",
                tool,
                completed.returncode,
                len(output),
            )
            return BridgeResult(
                tool=tool,
                status="ok" if completed.returncode == 0 else "error",
                output=output,
                executed=True,
            )
        except subprocess.TimeoutExpired:
            return BridgeResult(
                tool=tool,
                status="timeout",
                output="Timed out waiting for response.",
                suggested=True,
                suggestion_reason="External tool timed out.",
            )
        except Exception as exc:
            return BridgeResult(
                tool=tool,
                status="error",
                output=str(exc),
                suggested=True,
                suggestion_reason="Unexpected error running external tool.",
            )
