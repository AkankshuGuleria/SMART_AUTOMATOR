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
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


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

def explain_repository(project_id: str, repo_path: str) -> dict[str, Any]:
    from explain_repository import synthesize_explanation
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
        f"- [{m.get('table','memory')}] {m.get('content','')}"
        for m in memories[:10]
        if m.get("content")
    )

    system_prompt = (
        "You are AUTOMATA's Reasoning Engine. Generate a concise, imperative commit message "
        "grounded ONLY in the provided git diff and recent project memory. "
        "Output ONLY the commit message subject line, no explanation."
    )
    user_message = (
        f"Recent project memory:\n{context}\n\n"
        f"Git diff (first 6000 chars):\n{diff_text[:6000]}"
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
        "auth", "jwt", "login", "session", "token", "oauth",
        "password", "credential", "sso",
    ]
    scored: list[tuple[float, dict[str, Any]]] = []
    for memory in memories:
        content = str(memory.get("content", ""))
        raw_path = str(memory.get("raw", {}).get("file_path", ""))
        text = " ".join([content, raw_path])
        score = memory.get("score", 1.0)
        if any(k in text.lower() for k in keywords):
            score -= 0.2
        scored.append((score, memory))
    scored.sort(key=lambda x: x[0])
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
            + "\n".join(f"- {t.get('description','')}" for t in pending_todos[:5])
        )
    if recent:
        context_parts.append(
            "Recent memory:\n"
            + "\n".join(
                f"- [{m.get('table','memory')}] {m.get('content','')}"
                for m in recent[:8]
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
        f"- [{m.get('table','memory')}] {m.get('content','')}"
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
                    task_id, action, exc,
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
    raise ValueError(f"Unknown cross-app action: {action}")


def _build_web_app(params: dict[str, Any]) -> dict[str, Any]:
    project_path = params.get("project_path", "")
    framework = params.get("framework", "vite")
    if not project_path or not Path(project_path).is_dir():
        return {"status": "error", "detail": f"Invalid project path: {project_path}"}

    commands = {
        "vite": ["npm", "run", "dev"],
        "next": ["npm", "run", "dev"],
        "vite_alt": ["npm", "run", "dev"],
    }
    command = commands.get(framework, ["npm", "run", "dev"])
    cwd = project_path

    try:
        import subprocess
        proc = subprocess.Popen(  # noqa: S603
            command,
            cwd=cwd,
            shell=False,
            creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0) if os.name == "nt" else 0,
        )
        return {"status": "started", "pid": proc.pid, "command": command, "cwd": cwd}
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
            import subprocess
            proc = subprocess.Popen(command, cwd=cwd, shell=True)  # noqa: S602
            return {"status": "started", "pid": proc.pid}
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
