"""
agent_actions.py — AUTOMATA Agent Actions: Phase 4 action implementations.

Owns:    Concrete implementations for explain repository, generate commit message,
         find authentication code, continue previous work, generate project summary,
         start development environment, and cross-app task execution helpers.
Never:   Must not write to CockroachDB except where explicitly noted.
         Must not bypass module boundaries.
Ref:     ROADMAP.md Phase 4, PROJECT.md §4 (Agent Actions).
"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _wait_for_app_window(app: str, timeout: float = 12.0) -> str | None:
    """Title of the launched app's window once it appears, else None."""
    import os

    from automation import win32
    from automation.os_windows import resolve_executable

    if not win32.IS_WINDOWS:
        return None
    path = resolve_executable(app) or app
    exe = os.path.basename(path).lower()
    if exe.endswith((".cmd", ".bat")):  # launcher script: the GUI exe has the app's name
        exe = os.path.splitext(exe)[0] + ".exe"
    if not exe.endswith(".exe"):
        exe += ".exe"
    names = {exe, exe.replace("-", " ")}  # antigravity-ide.exe → "antigravity ide.exe"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for w in win32.top_level_windows():
            if w.exe.lower() in names and w.title:
                return w.title
        time.sleep(0.5)
    return None


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _get_project(project_id: str) -> dict | None:
    from db.client import get_project

    return get_project(project_id)


def _recent_memories(project_id: str) -> list[dict[str, Any]]:
    from memory.retrieval import retrieve_recent

    memories: list[dict[str, Any]] = []
    for table in ("commits", "file_edits", "todos", "architecture_notes", "decision_log"):
        try:
            memories.extend(retrieve_recent(project_id, table, limit=5))
        except Exception as exc:
            logger.warning("agent_actions: retrieve_recent failed for %s — %s", table, exc)
    return memories


def _invoke_reasoning(
    system_prompt: str,
    user_message: str,
    memories: list[dict[str, Any]],
) -> str | None:
    from ai.bedrock_client import invoke_reasoning

    return invoke_reasoning(
        system_prompt=system_prompt,
        user_message=user_message,
        retrieved_memories=memories,
    )


# ─── Actions ──────────────────────────────────────────────────────────────────

# Maps friendly app names to launch targets (app path or URL).
# Keys are matched case-insensitively via substring check.
_APP_NAME_MAP: dict[str, str] = {
    # Browsers
    "browser": "",  # default browser, no URL
    "chrome": "chrome",
    "firefox": "firefox",
    "edge": "msedge",
    "safari": "safari",
    "opera": "opera",
    "brave": "brave",
    # Editors & IDEs
    "vscode": "code",
    "vs code": "code",
    "vs-code": "code",
    "code": "code",
    "visual studio code": "code",
    "antigravity": "antigravity-ide",
    "antigravity ide": "antigravity-ide",
    "antigravity app": "antigravity",
    "kilo code": "antigravity-ide",  # Kilo Code runs inside Antigravity IDE here
    "kilo": "antigravity-ide",
    "cursor": "cursor",
    "intellij": "idea64",
    "intellij idea": "idea64",
    "idea": "idea64",
    "pycharm": "pycharm64",
    "pycharm community": "pycharm64",
    "pycharm professional": "pycharm64",
    "eclipse": "eclipse",
    "android studio": "studio64",
    "xcode": "xcode",
    "sublime": "sublime_text",
    "sublime text": "sublime_text",
    "notepad": "notepad",
    "notepad++": "notepad++",
    # Dev tools
    "terminal": "wt",
    "windows terminal": "wt",
    "powershell": "powershell",
    "pwsh": "pwsh",
    "cmd": "cmd",
    "command prompt": "cmd",
    "git bash": "git-bash",
    "gitbash": "git-bash",
    "git": "git-bash",
    "docker": "docker-desktop",
    "kubernetes": "kubernetes",
    "kubectl": "kubectl",
    "ansible": "ansible",
    "terraform": "terraform",
    "vmware": "vmware",
    "virtualbox": "virtualbox",
    # Communication & productivity
    "slack": "slack",
    "discord": "discord",
    "teams": "teams",
    "zoom": "zoom",
    "outlook": "outlook",
    "onenote": "onenote",
    "onenote web": "https://www.onenote.com",
    # Media
    "spotify": "spotify",
    "youtube": "https://youtube.com",
    "yt": "https://youtube.com",
    "vlc": "vlc",
    "spotify web": "https://open.spotify.com",
    # Design & creative
    "figma": "https://figma.com",
    "postman": "https://web.postman.co",
    "canva": "https://canva.com",
    "photoshop": "photoshop",
    "illustrator": "illustrator",
    # System
    "task manager": "taskmgr",
    "taskmanager": "taskmgr",
    "settings": "ms-settings:",
    "control panel": "control",
    "file explorer": "explorer",
    "explorer": "explorer",
    "calculator": "calc",
    "calc": "calc",
    "environment variables": "rundll32 sysdm.cpl,EditEnvironmentVariables",
    "environment variable": "rundll32 sysdm.cpl,EditEnvironmentVariables",
    "env variables": "rundll32 sysdm.cpl,EditEnvironmentVariables",
    "env var": "rundll32 sysdm.cpl,EditEnvironmentVariables",
    "system properties": "SystemPropertiesAdvanced",
    "systemproperty": "SystemPropertiesAdvanced",
    "advanced system settings": "SystemPropertiesAdvanced",
    # AI / Chat
    "chatgpt": "https://chatgpt.com",
    "chat gpt": "https://chatgpt.com",
    "chat gpt app": "https://chatgpt.com",
    "claude": "https://claude.ai",
    "claude ai": "https://claude.ai",
    "openai": "https://platform.openai.com",
    "openai chat": "https://chatgpt.com",
    "perplexity": "https://perplexity.ai",
    "perplexity ai": "https://perplexity.ai",
    "gemini": "https://gemini.google.com",
    "google ai": "https://gemini.google.com",
    "github copilot": "https://github.com/features/copilot",
    "copilot": "https://github.com/features/copilot",
    # Development platforms
    "github": "https://github.com",
    "gitlab": "https://gitlab.com",
    "bitbucket": "https://bitbucket.org",
    "stack overflow": "https://stackoverflow.com",
    "stackoverflow": "https://stackoverflow.com",
    "docs": "https://docs.google.com",
    "google docs": "https://docs.google.com",
    "drive": "https://drive.google.com",
    "google drive": "https://drive.google.com",
    # Cloud & DevOps
    "aws": "https://console.aws.amazon.com",
    "aws console": "https://console.aws.amazon.com",
    "azure": "https://portal.azure.com",
    "azure portal": "https://portal.azure.com",
    "gcp": "https://console.cloud.google.com",
    "google cloud": "https://console.cloud.google.com",
    "cloud": "https://console.cloud.google.com",
}

# Fuzzy name mappings for common variations
_FUZZY_ALIASES: dict[str, str] = {
    "chat gpt": "chatgpt",
    "chatgpt app": "chatgpt",
    "gpt": "chatgpt",
    "openai chat": "chatgpt",
    "google gemini": "gemini",
    "google ai": "gemini",
    "visual studio": "vscode",
    "vs code": "vscode",
    "vs-code": "vscode",
    "vscode": "vscode",
    "intellij idea": "intellij",
    "pycharm community edition": "pycharm",
    "pycharm professional edition": "pycharm",
    "android studio": "android studio",
    "web browser": "browser",
    "file manager": "file explorer",
    "task manager": "task manager",
    "control panel": "settings",
    "video player": "vlc",
    "music player": "spotify",
    "spotify web player": "spotify web",
    "youtube music": "https://music.youtube.com",
    "google docs": "docs",
    "google sheets": "https://sheets.google.com",
    "google slides": "https://slides.google.com",
}


def _resolve_app_target(raw: str) -> tuple[str, str]:
    """Return (kind, target) where kind is 'url', 'editor', or 'app'."""
    raw = raw.strip()
    lowered = raw.lower()

    # Strip leading filler words
    for prefix in ("open ", "run ", "launch ", "start ", "navigate to ", "go to ", "visit "):
        if lowered.startswith(prefix):
            raw = raw[len(prefix) :].strip()
            lowered = raw.lower()
            break

    # Strip "browser to " prefix for browser intent messages
    for prefix in ("browser to ", "open browser to ", "launch browser to "):
        if lowered.startswith(prefix):
            raw = raw[len(prefix) :].strip()
            lowered = raw.lower()
            break

    # Only the app phrase: "antigravity and use kilo code to …" → "antigravity".
    # Otherwise a word later in the sentence ("kilo *code*") picks the wrong app.
    head = re.split(r"\s+(?:and|then|to|so|for|with|,)\s+|,", lowered, maxsplit=1)[0].strip()
    if head and head != lowered:
        raw, lowered = raw[: len(head)], head

    # Check fuzzy aliases first (e.g. "chat gpt" → "chatgpt")
    for alias, canonical in _FUZZY_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", lowered):
            lowered = lowered.replace(alias, canonical)
            raw = raw.replace(alias, canonical)
            break

    # Whole-word matches only; the earliest app named wins, then the longest name.
    best: tuple[int, int, str] | None = None
    for key, target in _APP_NAME_MAP.items():
        m = re.search(rf"(?<![\w-]){re.escape(key)}(?![\w-])", lowered)
        if m and (best is None or (m.start(), -len(key)) < (best[0], best[1])):
            best = (m.start(), -len(key), target)
    if best is not None:
        target = best[2]
        return ("url" if target.startswith("http") else "app"), target or raw

    # If it looks like a URL (has a dot and no spaces, or starts with http/www)
    if raw.startswith(("http://", "https://", "www.")):
        url = raw if raw.startswith("http") else f"https://{raw}"
        return "url", url
    if "." in raw and " " not in raw:
        # Looks like a domain name without protocol
        url = raw if raw.startswith("http") else f"https://{raw}"
        return "url", url

    # Treat as an app name / executable
    return "app", lowered


def open_app_or_url(target: str) -> dict[str, Any]:
    """Open a browser URL or a named desktop application.

    Returns a result dict. On exact matches the action is auto-executed. When
    the target is ambiguous, ``success`` is ``False`` and ``suggested`` is
    ``True`` so the UI can present the options and ask the user.
    """
    from automation.os_windows import launch_app, launch_browser

    kind, resolved = _resolve_app_target(target)

    # "browser" maps to empty string — open default browser
    if kind == "app" and (not resolved or resolved == "browser"):
        success = launch_browser("")
        return {
            "action": "open_browser",
            "target": resolved or "default browser",
            "success": success,
            "message": "Opened default browser." if success else "Failed to open browser.",
        }

    if kind == "url":
        success = launch_browser(resolved)
        return {
            "action": "open_browser",
            "target": resolved,
            "success": success,
            "message": f"Opened {resolved} in the default browser."
            if success
            else f"Failed to open browser for {resolved}.",
        }

    # Exact app match
    app_success = launch_app(resolved)
    if app_success:
        title = _wait_for_app_window(resolved)
        from security.defender import explain_block

        blocked = explain_block(resolved.split("-")[0], seconds=30)
        message = (f"Opened {title}." if title else
                   f"Started {resolved}, but no window has appeared yet — it may still be loading.")
        return {
            "action": "open_app",
            "target": resolved,
            "success": True,
            "verified": title is not None,
            "window": title,
            "defender": blocked,
            "message": message + (f" Note: {blocked}" if blocked else ""),
        }

    # Exact launch failed — fall back to ambiguous search
    candidates = _search_app_candidates(target)
    if candidates:
        return {
            "action": "open_app",
            "target": resolved,
            "success": False,
            "suggested": True,
            "message": f"I couldn't find an exact match for '{target}'. Did you mean one of these?",
            "options": candidates,
            "suggestion_reason": "app_ambiguous",
        }

    return {
        "action": "open_app",
        "target": resolved,
        "success": False,
        "suggested": True,
        "message": f"Could not find or launch '{resolved}'. Check the app name.",
        "suggestion_reason": "app_not_found",
        "options": [],
    }


def _search_app_candidates(raw: str) -> list[dict[str, str]]:
    """Return a short list of likely app matches for *raw*."""
    lowered = raw.lower()
    scored: list[tuple[int, str, str]] = []

    # Build a combined lookup of map keys + aliases
    lookup: dict[str, str] = {}
    for key, target in _APP_NAME_MAP.items():
        lookup[key] = target
    for alias, canonical in _FUZZY_ALIASES.items():
        lookup[alias] = _APP_NAME_MAP.get(canonical, canonical)

    for key, target in lookup.items():
        score = 0
        if lowered == key:
            score = 100
        elif lowered in key or key in lowered:
            score = 60
        elif any(token in key for token in lowered.split()):
            score = 40
        if score > 0:
            scored.append((score, key, target))

    scored.sort(key=lambda item: (-item[0], item[1]))
    seen: set[str] = set()
    results: list[dict[str, str]] = []
    for _, key, target in scored[:6]:
        if target in seen:
            continue
        seen.add(target)
        results.append({"name": key, "target": target})
    return results


def execute_system_command(message: str) -> dict[str, Any]:
    """Execute a system-level command (install, setup, env vars) with safety checks."""
    from automation.command_executor import CommandExecutor

    # Determine the command to run based on the user's message
    command = _parse_system_command(message)
    if not command:
        return {
            "action": "system_command",
            "success": False,
            "message": "I couldn't determine what system command to run. Try something like 'install Java JDK' or 'setup dev environment'.",
        }

    # Check if this is a dangerous operation that needs confirmation
    dangerous_patterns = [
        "install",
        "uninstall",
        "remove",
        "delete",
        "format",
        "shutdown",
        "set env",
        "set path",
        "set java",
        "set variable",
        "configure system",
    ]
    is_dangerous = any(p in message.lower() for p in dangerous_patterns)

    if is_dangerous:
        return {
            "action": "system_command",
            "command": command,
            "success": False,
            "suggested": True,
            "message": (
                f"I can run this command, but it will make system-level changes. "
                f"Please confirm: `{command}`"
            ),
            "undo_hint": "Reverse the command or restore system state manually",
        }

    executor = CommandExecutor(allow_auto_execute=True)
    result = executor.execute(command, context="system_command")

    return {
        "action": "system_command",
        "command": command,
        "success": result.status == "ok",
        "message": (
            f"Command executed successfully: `{command}`"
            if result.status == "ok"
            else f"Command failed: `{command}` — {result.stderr or result.status}"
        ),
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.exit_code,
    }


def _parse_system_command(message: str) -> str:
    """Parse a user message to determine the system command to run."""
    lowered = message.lower().strip()

    # Specific install phrases first so bare keywords (e.g. "python", "git",
    # "node") do not shadow more specific intent in ambiguous messages.
    install_phrases = [
        ("java install", "winget install Microsoft.JavaRuntime --accept-package-agreements"),
        ("jdk install", "winget install Microsoft.JavaRuntime --accept-package-agreements"),
        ("node install", "winget install OpenJS.NodeJS.LTS --accept-package-agreements"),
        ("nodejs install", "winget install OpenJS.NodeJS.LTS --accept-package-agreements"),
        ("python install", "winget install Python.Python.3.12 --accept-package-agreements"),
        ("python3 install", "winget install Python.Python.3.12 --accept-package-agreements"),
        ("git install", "winget install Git.Git --accept-package-agreements"),
        ("docker install", "winget install Docker.DockerDesktop --accept-package-agreements"),
        (
            "vs code install",
            "winget install Microsoft.VisualStudioCode --accept-package-agreements",
        ),
        (
            "visual studio code install",
            "winget install Microsoft.VisualStudioCode --accept-package-agreements",
        ),
        (
            "idea install",
            "winget install JetBrains.IntelliJIDEA.Community --accept-package-agreements",
        ),
        (
            "jetbrains install",
            "winget install JetBrains.IntelliJIDEA.Community --accept-package-agreements",
        ),
        ("chrome install", "winget install Google.Chrome --accept-package-agreements"),
        ("google chrome install", "winget install Google.Chrome --accept-package-agreements"),
        ("browser install", "winget install Google.Chrome --accept-package-agreements"),
    ]
    for phrase, command in install_phrases:
        if phrase in lowered:
            return command

    # Explicit package-manager commands the user typed take priority.
    if "winget install" in lowered:
        return message.strip()
    if "pip install" in lowered:
        return message.strip()
    if "npm install" in lowered:
        return message.strip()
    if "choco install" in lowered:
        return message.strip()

    # Bare keywords — checked after specific phrases.
    if any(k in lowered for k in ["java", "jdk"]):
        return "winget install Microsoft.JavaRuntime --accept-package-agreements"
    if any(k in lowered for k in ["node", "node.js", "nodejs"]):
        return "winget install OpenJS.NodeJS.LTS --accept-package-agreements"
    if any(k in lowered for k in ["python", "python3"]):
        return "winget install Python.Python.3.12 --accept-package-agreements"
    if any(k in lowered for k in ["git"]):
        return "winget install Git.Git --accept-package-agreements"
    if any(k in lowered for k in ["docker"]):
        return "winget install Docker.DockerDesktop --accept-package-agreements"
    if any(k in lowered for k in ["vscode", "visual studio code", "vs code"]):
        return "winget install Microsoft.VisualStudioCode --accept-package-agreements"
    if any(k in lowered for k in ["intellij", "idea", "jetbrains"]):
        return "winget install JetBrains.IntelliJIDEA.Community --accept-package-agreements"
    if any(k in lowered for k in ["chrome", "google chrome", "browser"]):
        return "winget install Google.Chrome --accept-package-agreements"

    # Environment variable setup
    if any(k in lowered for k in ["set env", "set path", "set java", "set variable"]):
        # Extract the variable name and value
        return f"setx {message}"

    # Dev environment setup
    if any(k in lowered for k in ["dev env", "dev environment", "setup dev", "setup env"]):
        return "winget install Microsoft.VisualStudioCode Git.Git Python.Python.3.12 --accept-package-agreements"

    return message.strip()


def run_tests_action(project_id: str, command: str = "") -> dict[str, Any]:
    """Suggest running tests for the project, returning the suggested command."""
    project = _get_project(project_id)
    if project is None:
        return {"error": "Project not found", "suggested_command": None}

    repo_path = project.get("repo_path", "")

    # Auto-detect test runner if no command provided
    if not command:
        detected = "pytest"  # default
        if repo_path:
            rp = Path(repo_path)
            if (rp / "package.json").exists():
                detected = "npm test"
            elif (rp / "Cargo.toml").exists():
                detected = "cargo test"
            elif any(rp.glob("*.csproj")):
                detected = "dotnet test"
        command = detected

    return {
        "project_id": project_id,
        "suggested_command": command,
        "repo_path": repo_path,
        "message": f"Run `{command}` in `{repo_path}` to execute tests.",
        "error": None,
    }


def explain_repository(project_id: str, repo_path: str) -> dict[str, Any]:
    try:
        from explain_repository import synthesize_explanation
    except ImportError:
        return {
            "project_id": project_id,
            "repo_path": repo_path,
            "error": "explain_repository module is not available",
            "explanation": None,
            "readme_summary": "",
            "folder_structure": [],
            "architecture_notes": [],
        }

    recent = _recent_memories(project_id)
    return synthesize_explanation(project_id, repo_path, recent_memories=recent)


def generate_commit_message(project_id: str, repo_path: str, staged: bool = True) -> dict[str, Any]:
    project = _get_project(project_id)
    if project is None:
        return {"error": "Project not found", "commit_message": None}

    if not repo_path or not Path(repo_path).is_dir():
        return {"error": f"Repo path not found: {repo_path}", "commit_message": None}

    diff_text = ""
    try:
        import git

        repo = git.Repo(repo_path)
        if staged:
            diff_text = repo.git.diff("--cached", "--no-color", "--unified=3")
        else:
            diff_text = repo.git.diff("--no-color", "--unified=3")
    except Exception as exc:
        logger.warning("agent_actions: git diff failed — %s", exc)
        return {"error": f"Failed to read git diff: {exc}", "commit_message": None, "diff": ""}

    if not diff_text.strip():
        missing = "staged" if staged else "uncommitted"
        return {
            "error": f"No {missing} changes found.",
            "commit_message": None,
            "diff": "",
        }

    memories = _recent_memories(project_id)
    context = "\n".join(
        f"- [{m.get('table', 'memory')}] {m.get('content', '')}"
        for m in memories[:10]
        if m.get("content")
    )

    system_prompt = (
        "You are AUTOMATA's Reasoning Engine. Generate a concise, imperative commit message "
        "grounded ONLY in the provided git diff and recent project memory. "
        "Output ONLY the commit message subject line, no explanation."
    )
    user_message = (
        f"Recent project memory:\n{context}\n\nGit diff (first 6000 chars):\n{diff_text[:6000]}"
    )

    answer = _invoke_reasoning(system_prompt, user_message, memories)
    commit_message = (answer or "").strip().splitlines()[0] if answer else None
    if not commit_message:
        commit_message = "chore: update project files"

    return {
        "project_id": project_id,
        "repo_path": repo_path,
        "staged": staged,
        "commit_message": commit_message,
        "diff": diff_text[:4000],
        "error": None,
    }


def find_authentication_code(project_id: str, query: str = "authentication") -> dict[str, Any]:
    project = _get_project(project_id)
    if project is None:
        return {"error": "Project not found", "results": []}

    from memory.retrieval import retrieve_by_vector, retrieve_recent

    memories: list[dict[str, Any]] = []
    try:
        memories.extend(
            retrieve_by_vector(
                query,
                ["file_edits", "architecture_notes", "commits"],
                project_id=project_id,
                top_k=8,
            )
        )
    except Exception as exc:
        logger.warning("agent_actions: vector search failed — %s", exc)

    if not memories:
        for table in ("file_edits", "architecture_notes", "commits"):
            try:
                memories.extend(retrieve_recent(project_id, table, limit=5))
            except Exception as exc:
                logger.warning("agent_actions: recent retrieval failed for %s — %s", table, exc)

    keywords = [
        "auth",
        "jwt",
        "login",
        "session",
        "token",
        "oauth",
        "password",
        "credential",
        "sso",
    ]
    scored: list[tuple[float, dict[str, Any]]] = []
    for memory in memories:
        content = str(memory.get("content", ""))
        raw_path = str(memory.get("raw", {}).get("file_path", ""))
        text = " ".join([content, raw_path])
        score = memory.get("score", 1.0)
        if any(k in text.lower() for k in keywords):
            score += 0.2  # Boost auth-related items so they rank higher
        scored.append((score, memory))
    scored.sort(key=lambda x: x[0], reverse=True)  # Sort descending (higher scores first)
    results = [m for _, m in scored[:10]]

    return {
        "project_id": project_id,
        "query": query,
        "results": results,
        "error": None if results else "No authentication-related memory found.",
    }


def continue_previous_work(project_id: str) -> dict[str, Any]:
    project = _get_project(project_id)
    if project is None:
        return {"error": "Project not found", "suggestion": None}

    from db.client import get_active_session, get_todos

    session = get_active_session(project_id)
    pending_todos = get_todos(project_id, status="pending")
    recent = _recent_memories(project_id)

    context_parts = []
    if session:
        context_parts.append(
            f"Active session: {session.get('id')} started at {session.get('started_at')}"
        )
    if pending_todos:
        context_parts.append(
            "Pending TODOs:\n"
            + "\n".join(f"- {t.get('description', '')}" for t in pending_todos[:5])
        )
    if recent:
        context_parts.append(
            "Recent memory:\n"
            + "\n".join(
                f"- [{m.get('table', 'memory')}] {m.get('content', '')}" for m in recent[:8]
            )
        )

    context = "\n\n".join(context_parts) or "No recent memory available."
    system_prompt = (
        "You are AUTOMATA's Reasoning Engine. Based ONLY on the context below, "
        "suggest the most likely next engineering task to continue previous work. "
        "Be specific and actionable."
    )
    user_message = f"Context:\n{context}\n\nSuggest the next step."

    suggestion = _invoke_reasoning(system_prompt, user_message, recent)
    return {
        "project_id": project_id,
        "active_session": session,
        "pending_todos_count": len(pending_todos),
        "suggestion": suggestion
        or "No suggestion available — the reasoning backend is unavailable.",
        "error": None,
    }


def generate_project_summary(project_id: str) -> dict[str, Any]:
    project = _get_project(project_id)
    if project is None:
        return {"error": "Project not found", "summary": None}

    recent = _recent_memories(project_id)
    context = "\n".join(
        f"- [{m.get('table', 'memory')}] {m.get('content', '')}"
        for m in recent[:12]
        if m.get("content")
    )
    system_prompt = (
        "You are AUTOMATA's Reasoning Engine. Summarize the project state using ONLY "
        "the provided memory. Keep it to 3-6 short bullets."
    )
    user_message = (
        f"Project: {project.get('name')}\nRepo: {project.get('repo_path')}\n\nMemory:\n{context}"
    )

    summary = _invoke_reasoning(system_prompt, user_message, recent)
    return {
        "project_id": project_id,
        "project_name": project.get("name"),
        "summary": summary or "No summary available.",
        "error": None,
    }


def start_development_environment(project_id: str) -> dict[str, Any]:
    project = _get_project(project_id)
    if project is None:
        return {"error": "Project not found", "steps": []}

    repo_path = project.get("repo_path", "")
    if not repo_path or not Path(repo_path).is_dir():
        return {"error": f"Repo path not found: {repo_path}", "steps": []}

    from automation.dev_servers import start_dev_servers

    result = start_dev_servers(project_id)
    return {
        "project_id": project_id,
        "repo_path": repo_path,
        "servers": result.get("servers", []),
        "status": result.get("status", "error"),
        "error": None,
    }


# ─── Cross-App Task Execution Engine ──────────────────────────────────────────


class CrossAppTaskEngine:
    """
    Asynchronous background execution for building web apps, executing OS actions,
    and driving tools across other applications.

    Runs tasks in background daemon threads so it never blocks the API server.
    """

    def __init__(self) -> None:
        self._tasks: dict[str, dict[str, Any]] = {}

    def submit(self, task_id: str, action: str, params: dict[str, Any]) -> dict[str, Any]:
        if task_id in self._tasks:
            return {"task_id": task_id, "status": "already_running"}

        task: dict[str, Any] = {
            "id": task_id,
            "action": action,
            "params": params,
            "status": "queued",
            "result": None,
            "error": None,
        }
        self._tasks[task_id] = task

        def _run() -> None:
            task["status"] = "running"
            try:
                result = _dispatch_cross_app_action(action, params)
                task["result"] = result
                task["status"] = "completed"
            except Exception as exc:
                logger.error(
                    "cross_app_task: failed | task=%s action=%s error=%s",
                    task_id,
                    action,
                    exc,
                )
                task["error"] = str(exc)
                task["status"] = "error"

        import threading

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        task["thread"] = thread
        return {"task_id": task_id, "status": "queued"}

    def status(self, task_id: str) -> dict[str, Any]:
        task = self._tasks.get(task_id)
        if task is None:
            return {"error": "Task not found"}
        return {
            "task_id": task_id,
            "action": task.get("action"),
            "status": task.get("status"),
            "result": task.get("result"),
            "error": task.get("error"),
        }

    def active_tasks(self) -> list[dict[str, Any]]:
        return [
            {"task_id": k, "action": v.get("action"), "status": v.get("status")}
            for k, v in self._tasks.items()
            if v.get("status") in ("queued", "running")
        ]


_cross_app_engine = CrossAppTaskEngine()


def submit_cross_app_task(task_id: str, action: str, params: dict[str, Any]) -> dict[str, Any]:
    return _cross_app_engine.submit(task_id, action, params)


def cross_app_task_status(task_id: str) -> dict[str, Any]:
    return _cross_app_engine.status(task_id)


def active_cross_app_tasks() -> list[dict[str, Any]]:
    return _cross_app_engine.active_tasks()


def _dispatch_cross_app_action(action: str, params: dict[str, Any]) -> Any:
    if action == "build_web_app":
        return _build_web_app(params)
    if action == "execute_os_action":
        return _execute_os_action(params)
    if action == "drive_tool":
        return _drive_tool(params)
    if action == "copy_to_clipboard":
        return copy_to_clipboard_action(str(params.get("text", "")))
    if action == "paste_clipboard":
        return paste_clipboard_action(str(params.get("target_app") or "") or None)
    if action == "focus_app":
        return focus_app_action(str(params.get("app_name", params.get("app", ""))))
    if action == "send_keystroke":
        return send_keystroke_action(
            str(params.get("keystrokes", "")), str(params.get("target_app") or "") or None
        )
    if action == "submit_prompt_to_app":
        return submit_prompt_to_app_action(
            app_name=str(params.get("app_name", "")),
            prompt_text=str(params.get("prompt", params.get("prompt_text", ""))),
            url=str(params.get("url", "")),
        )
    if action == "verify_result":
        return verify_result_action(
            check_type=str(params.get("type", params.get("check_type", ""))),
            target=str(params.get("target", "")),
        )
    if action in ("open_url", "open_app"):
        return open_app_or_url(
            str(params.get("url", params.get("app_name", params.get("target", ""))))
        )
    raise ValueError(f"Unknown cross-app action: {action}")


def _build_web_app(params: dict[str, Any]) -> dict[str, Any]:
    project_path = params.get("project_path", "")
    framework = params.get("framework", "vite")
    if not project_path or not Path(project_path).is_dir():
        return {"status": "error", "detail": f"Invalid project path: {project_path}"}

    commands = {
        "vite": "npm run dev",
        "next": "npm run dev",
        "vite_alt": "npm run dev",
    }
    command = commands.get(framework, "npm run dev")
    cwd = project_path

    try:
        from automation.os_windows import open_terminal_with_command

        pid = open_terminal_with_command(command, cwd)
        if pid is not None:
            return {"status": "started", "pid": pid, "command": command, "cwd": cwd}
        else:
            return {"status": "error", "detail": "Failed to launch terminal"}
    except Exception as exc:
        logger.error("cross_app: build_web_app failed — %s", exc)
        return {"status": "error", "detail": str(exc)}


def _execute_os_action(params: dict[str, Any]) -> dict[str, Any]:
    action_type = params.get("type", "")
    if action_type == "open_terminal":
        from automation.os_windows import open_terminal

        success = open_terminal(params.get("cwd", ""))
        return {"status": "ok" if success else "error", "detail": "open_terminal"}
    if action_type == "launch_editor":
        from automation.os_windows import launch_editor

        success = launch_editor(params.get("path", ""))
        return {"status": "ok" if success else "error", "detail": "launch_editor"}
    if action_type == "run_command":
        command = params.get("command", "")
        cwd = params.get("cwd", "")
        try:
            from automation.os_windows import open_terminal_with_command

            pid = open_terminal_with_command(command, cwd)
            if pid is not None:
                return {"status": "started", "pid": pid}
            else:
                return {"status": "error", "detail": "Failed to launch terminal"}
        except Exception as exc:
            return {"status": "error", "detail": str(exc)}
    return {"status": "error", "detail": f"Unknown OS action: {action_type}"}


def _drive_tool(params: dict[str, Any]) -> dict[str, Any]:
    tool = params.get("tool", "")
    if tool == "git":
        return _drive_git(params)
    if tool == "npm":
        return _drive_npm(params)
    return {"status": "error", "detail": f"Unknown tool: {tool}"}


def _drive_git(params: dict[str, Any]) -> dict[str, Any]:
    repo_path = params.get("repo_path", "")
    command = params.get("command", "status")
    if not repo_path or not Path(repo_path).is_dir():
        return {"status": "error", "detail": f"Invalid repo path: {repo_path}"}
    try:
        import git

        repo = git.Repo(repo_path)
        if command == "status":
            return {"status": "ok", "output": repo.git.status()}
        if command == "pull":
            return {"status": "ok", "output": repo.git.pull()}
        return {"status": "error", "detail": f"Unsupported git command: {command}"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


def _drive_npm(params: dict[str, Any]) -> dict[str, Any]:
    cwd = params.get("cwd", "")
    command = params.get("command", "install")
    if not cwd or not Path(cwd).is_dir():
        return {"status": "error", "detail": f"Invalid cwd: {cwd}"}
    try:
        import subprocess

        args = ["npm"]
        if command == "install":
            args.extend(["install"])
        elif command == "run":
            script = params.get("script", "dev")
            args.extend(["run", script])
        else:
            args.append(command)
        proc = subprocess.Popen(args, cwd=cwd, shell=False)  # noqa: S603
        return {"status": "started", "pid": proc.pid, "command": args}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


# ─── Taste Preferences Pipeline ────────────────────────────────────────────────


def analyze_taste_preferences(project_id: str, developer_id: str | None = None) -> dict:
    """
    Phase 2: Infer developer taste preferences from commit history and TODOs.

    Heuristics (no external API calls):
    - Naming style: camelCase vs snake_case vs PascalCase from commit messages
      and edited file paths.
    - Test framework: pytest vs jest vs mocha from existing test file paths.
    - Conventions: Conventional Commits vs free-form from commit message patterns.
    - Risk tolerance: large vs small commits from commit message length/stats.

    Stores inferred preferences in taste_preferences via db/client.
    """
    if developer_id is None:
        developer_id = project_id

    try:
        from db.client import get_commits, get_todos, insert_taste_preference

        commits = get_commits(project_id, limit=50) or []
        todos = get_todos(project_id, status="pending") or []
    except Exception as exc:
        logger.warning("analyze_taste_preferences: failed to load data — %s", exc)
        return {"status": "error", "detail": str(exc)}

    inferred: list[dict[str, Any]] = []

    # 1. Naming convention detector
    snake = sum(1 for c in commits if "_" in str(c.get("message", "")))
    camel = sum(
        1
        for c in commits
        if any(w in str(c.get("message", "")).lower() for w in ["camel", "js", "ts", "react"])
    )
    if snake > camel:
        inferred.append(
            {
                "category": "naming",
                "description": "Prefers snake_case naming (observed in commit messages)",
                "confidence": min(0.95, 0.5 + snake * 0.05),
                "evidence_count": snake,
            }
        )
    elif camel > snake:
        inferred.append(
            {
                "category": "naming",
                "description": "Prefers camelCase naming (observed in commit messages and file paths)",
                "confidence": min(0.95, 0.5 + camel * 0.05),
                "evidence_count": camel,
            }
        )

    # 2. Test framework detector
    test_files = [
        c.get("message", "") for c in commits if "test" in str(c.get("message", "")).lower()
    ]
    if any("pytest" in m.lower() for m in test_files):
        inferred.append(
            {
                "category": "testing",
                "description": "Uses pytest for testing",
                "confidence": 0.85,
                "evidence_count": sum(1 for m in test_files if "pytest" in m.lower()),
            }
        )
    elif any("jest" in m.lower() for m in test_files):
        inferred.append(
            {
                "category": "testing",
                "description": "Uses Jest for testing",
                "confidence": 0.85,
                "evidence_count": sum(1 for m in test_files if "jest" in m.lower()),
            }
        )

    # 3. Commit style detector
    conventional = sum(
        1
        for c in commits
        if str(c.get("message", "")).startswith(("feat:", "fix:", "docs:", "chore:", "refactor:"))
    )
    if conventional > len(commits) * 0.5:
        inferred.append(
            {
                "category": "commits",
                "description": "Uses Conventional Commits format",
                "confidence": min(0.95, 0.5 + conventional * 0.05),
                "evidence_count": conventional,
            }
        )

    # 4. TODO density -> risk tolerance proxy
    if len(todos) > 10:
        inferred.append(
            {
                "category": "risk",
                "description": "High TODO density — may prefer iterative small changes over big refactors",
                "confidence": 0.6,
                "evidence_count": len(todos),
            }
        )

    # Persist inferred preferences
    saved = 0
    for pref in inferred:
        try:
            ok = insert_taste_preference(
                developer_id=developer_id,
                category=pref["category"],
                description=pref["description"],
                confidence=float(pref["confidence"]),
                evidence_count=int(pref["evidence_count"]),
            )
            if ok:
                saved += 1
        except Exception as exc:
            logger.warning("analyze_taste_preferences: insert failed — %s", exc)

    return {"status": "ok", "saved": saved, "total_inferred": len(inferred)}


def get_developer_tastes(developer_id: str) -> dict:
    """Return a concise taste summary for use in prompts/reasoning."""
    try:
        from db.client import get_taste_preferences

        prefs = get_taste_preferences(developer_id)
        if not prefs:
            return {"available": False, "summary": ""}
        lines = []
        for p in prefs[:8]:
            pct = int(float(p.get("confidence", 0)) * 100)
            lines.append(f"- {p.get('description', '')} ({pct}% confidence)")
        return {"available": True, "summary": "\n".join(lines)}
    except Exception as exc:
        logger.warning("get_developer_tastes failed — %s", exc)
        return {"available": False, "summary": ""}


# ─── Decision / Mistake Dogfooding Helpers ─────────────────────────────────────


def record_agent_decision(project_id: str, decision: str, rationale: str) -> None:
    """Log an autonomous agent decision to decision_log with embedding for future retrieval."""
    try:
        from db.client import insert_decision
        from memory.embeddings import generate_embedding_for_capture

        emb = generate_embedding_for_capture(f"{decision}. {rationale}")
        insert_decision(project_id, decision, rationale, rationale_embedding=emb)
    except Exception as exc:
        logger.warning("record_agent_decision failed — %s", exc)


def record_agent_mistake(project_id: str, symptom: str, root_cause: str, fix: str) -> None:
    """Log an agent mistake to mistake_log with embedding for future retrieval."""
    try:
        from db.client import insert_mistake
        from memory.embeddings import generate_embedding_for_capture

        emb = generate_embedding_for_capture(f"{symptom}. {root_cause}. {fix}")
        insert_mistake(
            project_id, symptom, root_cause, fix, module="decision_engine", root_cause_embedding=emb
        )
    except Exception as exc:
        logger.warning("record_agent_mistake failed — %s", exc)


# ─── Cross-App Control Actions ──────────────────────────────────────────


def copy_to_clipboard_action(text: str) -> dict[str, Any]:
    """Copy generated text to the clipboard (verified by reading it back)."""
    from automation.desktop import copy_text

    return {**copy_text(text), "action": "copy_to_clipboard"}


def paste_clipboard_action(target_app: str | None = None) -> dict[str, Any]:
    """Paste the clipboard into a verified target window."""
    from automation.desktop import paste

    return {**paste(target_app), "action": "paste_clipboard"}


def focus_app_action(app_name: str) -> dict[str, Any]:
    """Bring an app window to the front (confirmed by Windows)."""
    from automation.desktop import focus

    return {**focus(app_name), "action": "focus_app"}


def send_keystroke_action(keystrokes: str, target_app: str | None = None) -> dict[str, Any]:
    """Send an allowed chord to a verified window."""
    from automation.desktop import press

    return {**press(keystrokes, target_app=target_app), "action": "send_keystroke"}


def submit_prompt_to_app_action(app_name: str, prompt_text: str, url: str = "") -> dict[str, Any]:
    """Hand a prompt to another app (Claude, ChatGPT, Cursor…) with verified steps."""
    from automation.desktop import handoff_prompt

    if not prompt_text.strip():
        return {"success": False, "action": "submit_prompt_to_app", "error": "prompt is required"}
    return {**handoff_prompt(prompt_text, app_name=app_name, url=url), "action": "submit_prompt_to_app"}


def _project_context_for_prompt(project_id: str | None) -> str:
    """Short, factual description of the selected project for external prompts."""
    try:
        from intelligence.profile import prompt_context

        return prompt_context(project_id)
    except Exception as exc:
        logger.debug("profile prompt context unavailable — %s", exc)
    project = _get_project(project_id) if project_id else None
    if not project:
        return "No project is selected; keep the prompt project-agnostic."
    repo = Path(str(project.get("repo_path") or ""))
    markers = {
        "package.json": "Node/JavaScript", "pyproject.toml": "Python", "requirements.txt": "Python",
        "Cargo.toml": "Rust", "go.mod": "Go", "pom.xml": "Java (Maven)", "build.gradle": "Java/Kotlin (Gradle)",
        "composer.json": "PHP", "Gemfile": "Ruby", "docker-compose.yml": "Docker Compose",
    }
    found = sorted({label for name, label in markers.items() if repo.is_dir() and any(
        (repo / sub / name).exists() for sub in ("", "frontend", "backend", "app", "server", "client")
    )})
    stack = ", ".join(found) if found else "not detected"
    return f"Project: {project.get('name', 'unnamed')} at {repo}. Detected stack: {stack}."


def generate_prompt_for_app(
    request_description: str,
    app_name: str,
    project_id: str | None = None,
) -> str | None:
    """Generate a detailed, self-contained prompt for an external AI app.

    Given the developer's natural-language request (e.g. "open claude and
    generate a prompt to create a UI/UX fix .md file"), use the reasoning
    engine to produce a well-structured prompt that can be pasted directly
    into Claude, ChatGPT, or another AI assistant.

    Returns the generated prompt text, or None on failure.
    """
    # Deliberately pass an empty memories list — we want the LLM to generate
    # a fresh prompt, not answer a factual question from stored memory.
    memories: list[dict[str, Any]] = []

    system_prompt = (
        "You are a prompt engineer. Based on the developer's request, "
        f"generate a detailed, well-structured prompt that they can paste "
        f"into {app_name} to accomplish the task. The prompt should be clear, "
        "specific, actionable, and self-contained — include all necessary "
        "context about the project structure, file locations, and desired "
        "output format. Do not reference that you are an AI or that you were "
        "asked to generate a prompt. Output ONLY the prompt itself, no "
        "explanation or preamble."
    )

    user_message = (
        f"The developer wants to submit a prompt to {app_name}. "
        f"Generate a prompt they can give to {app_name} to accomplish this task:\n\n"
        f"Request: {request_description}\n\n"
        f"{_project_context_for_prompt(project_id)}"
    )

    return _invoke_reasoning(system_prompt, user_message, memories)


def verify_result_action(check_type: str, target: str = "") -> dict[str, Any]:
    """Check an outcome; unknown check types fail instead of passing."""
    from automation.desktop import verify

    return {**verify(check_type, target), "action": "verify_result"}


# ─── Visual Feedback Actions ─────────────────────────────────────────────


def capture_screen_action(region: str | None = None) -> dict[str, Any]:
    """Capture the screen or a region."""
    from automation.desktop import capture

    return {**capture(region=region), "action": "capture_screen"}


def ocr_image_action(image_path: str) -> dict[str, Any]:
    """Extract text from a screenshot/image."""
    from automation.ocr import run_ocr

    result = run_ocr(image_path)
    return {
        "success": result["ok"],
        "action": "ocr_image",
        "text": result["text"],
        "engine": result["engine"],
        "error": result["error"],
    }


def read_visible_context_action() -> dict[str, Any]:
    """Capture and OCR the current screen."""
    from automation.desktop import read_screen

    return {**read_screen(), "action": "read_visible_context"}


def diagnose_visible_error_action() -> dict[str, Any]:
    """Read visible error text from the screen."""
    from automation.desktop import read_screen

    return {**read_screen(), "action": "diagnose_visible_error"}


def review_visible_design_action() -> dict[str, Any]:
    """Read the visible UI text for a design review."""
    from automation.desktop import read_screen

    return {**read_screen(), "action": "review_visible_design"}


def generate_prompt_from_screen_action() -> dict[str, Any]:
    """Read the visible screen text to ground a prompt."""
    from automation.desktop import read_screen

    return {**read_screen(), "action": "generate_prompt_from_screen"}


def verify_visible_result_action(expected_text: str = "") -> dict[str, Any]:
    """Check whether *expected_text* is visible on screen."""
    from automation.desktop import read_screen

    if not expected_text.strip():
        return {"success": False, "action": "verify_visible_result", "verified": False,
                "error": "expected_text is required"}
    return {**read_screen(expected_text=expected_text), "action": "verify_visible_result"}


