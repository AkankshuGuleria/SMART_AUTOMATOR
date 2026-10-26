"""
tasks/engine.py — run delegation tasks step by step.

A delegation ("using antigravity build a landing page") becomes:

    clarify   (input)     ask where to work / save, stack, features, design,
                          anything else (tasks/questions.py); waits for answers
  0 context   (auto)      project profile + relevant memories
  1 prompt    (auto)      a complete, self-contained prompt for the agent
  2 handoff   (approval)  send it to the agent (IDE chat CLI / Claude CLI /
                          verified UI handoff / clipboard fallback)
  3 watch     (auto)      wait for the agent to change files in the project
  4 verify    (approval)  run the project's build/test commands
  5 needs     (auto)      API keys, connection strings, accounts still needed
  6 report    (auto)      summary saved to memory

Approval steps pause the task (status ``waiting_approval``) until approve().
Every step records what really happened; failures stop the task honestly.
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
from pathlib import Path
from typing import Any

from tasks.store import TERMINAL, get_task_store

logger = logging.getLogger(__name__)

WATCH_MAX_S = 20 * 60
WATCH_QUIET_S = 90
WATCH_POLL_S = 5
AGENT_LABELS = {"antigravity": "Antigravity", "kilo": "Kilo Code", "claude": "Claude", "cursor": "Cursor",
                "vscode": "VS Code", "chatgpt": "ChatGPT"}
CHAT_ONLY = {"chatgpt"}  # agents that cannot edit files in the project folder

_runners: dict[str, threading.Thread] = {}
_approvals: dict[str, threading.Event] = {}
_cancel: dict[str, threading.Event] = {}


def _broadcast(task_id: str) -> None:
    try:
        from api.server import broadcast_sync

        task = get_task_store().get_task(task_id)
        broadcast_sync({"type": "task_update", "data": {"id": task_id, "status": task["status"] if task else None},
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")})
    except Exception:
        pass


# "using antigravity", "with claude code", "in vs code" … — only agent names, so
# "add login with google" keeps its meaning.
_AGENT_PHRASE = re.compile(
    r"\b(?:using|use|with|in|via|through|on|open|launch|start)\s+(?:the\s+)?"
    r"(?:kilo(?:\s*code)?|antigravity(?:\s+ide)?|claude(?:\s+code)?|cursor|vs\s*code|vscode|"
    r"visual\s+studio\s+code|chatgpt)(?:\s+ai)?(?:\s+agent)?\b",
    re.I,
)
_LEADING_JOINERS = re.compile(r"^(?:\s*(?:and|then|to|,)\b)+\s*", re.I)


def clean_request(request: str) -> str:
    """The request without the 'open/using <agent>' parts (the agent doesn't need them)."""
    text = re.sub(r"\s+", " ", _AGENT_PHRASE.sub(" ", request))
    text = re.sub(r"\s+(?:and\s+)+(?=to\b)", " ", text)  # "… and  to make" → "… to make"
    text = _LEADING_JOINERS.sub("", text).strip(" ,.")
    return text or request.strip()


def _title(request: str, agent: str) -> str:
    text = clean_request(request)
    return (text[:1].upper() + text[1:])[:80]


def create_delegation_task(project_id: str | None, request: str, agent: str) -> dict[str, Any]:
    agent = (agent or "").lower().strip()
    if agent not in AGENT_LABELS:
        return {"success": False, "error": f"Unknown agent '{agent}'. Use Antigravity, Claude, Cursor, VS Code or ChatGPT."}
    if not request.strip():
        return {"success": False, "error": "Describe what the agent should do."}
    label = AGENT_LABELS[agent]
    steps = [
        {"kind": "clarify", "title": "Ask what's needed", "policy": "input"},
        {"kind": "context", "title": "Gather project context", "policy": "auto"},
        {"kind": "prompt", "title": f"Write the prompt for {label}", "policy": "auto"},
        {"kind": "handoff", "title": f"Hand the task to {label}", "policy": "approval"},
        {"kind": "watch", "title": "Watch the project for changes", "policy": "auto"},
        {"kind": "verify", "title": "Run build / tests", "policy": "approval"},
        {"kind": "needs", "title": "List what is still needed from you", "policy": "auto"},
        {"kind": "report", "title": "Report", "policy": "auto"},
    ]
    if agent in CHAT_ONLY:
        for s in steps:
            if s["kind"] in {"watch", "verify"}:
                s["detail"] = "skip"
    store = get_task_store()
    task_id = store.create_task(project_id, _title(request, agent), request, agent, steps)
    start(task_id)
    return {"success": True, "task": store.get_task(task_id)}


def start(task_id: str) -> None:
    if task_id in _runners and _runners[task_id].is_alive():
        return
    _approvals.setdefault(task_id, threading.Event())
    _cancel.setdefault(task_id, threading.Event())
    if os.environ.get("AUTOMATA_TASKS_SYNC") == "1":  # tests: run inline
        _run(task_id)
        return
    t = threading.Thread(target=_run, args=(task_id,), name=f"task-{task_id}", daemon=True)
    _runners[task_id] = t
    t.start()


def approve(task_id: str) -> dict[str, Any]:
    store = get_task_store()
    task = store.get_task(task_id)
    if not task:
        return {"success": False, "error": "Task not found"}
    if task["status"] not in {"waiting_approval", "paused"}:
        return {"success": False, "error": f"Task is {task['status']}, nothing to approve"}
    for step in task["steps"]:
        if step["status"] == "waiting_approval":
            store.update_step(task_id, step["idx"], status="approved")
            break
    _approvals.setdefault(task_id, threading.Event()).set()
    if task["status"] == "paused" or task_id not in _runners or not _runners[task_id].is_alive():
        start(task_id)
    return {"success": True}


def answer(task_id: str, answers: dict[str, Any] | None = None) -> dict[str, Any]:
    """Store the developer's answers to the clarify step and continue the task.

    Empty answers mean "use the defaults" (the suggested folder, agent picks the stack).
    """
    from tasks.questions import validate_answers

    store = get_task_store()
    task = store.get_task(task_id)
    if not task:
        return {"success": False, "error": "Task not found"}
    step = next((s for s in task["steps"] if s["kind"] == "clarify"), None)
    if not step or step["status"] != "waiting_input":
        return {"success": False, "error": "This task is not waiting for answers"}
    questions = (step.get("output") or {}).get("questions", [])
    clean, error = validate_answers(questions, answers or {})
    if error:
        return {"success": False, "error": error}
    store.update_step(task_id, step["idx"], status="answered", output={"questions": questions, "answers": clean})
    _approvals.setdefault(task_id, threading.Event()).set()
    if task_id not in _runners or not _runners[task_id].is_alive():
        start(task_id)
    return {"success": True, "answers": clean}


def cancel(task_id: str) -> dict[str, Any]:
    store = get_task_store()
    task = store.get_task(task_id)
    if not task:
        return {"success": False, "error": "Task not found"}
    if task["status"] in TERMINAL:
        return {"success": False, "error": f"Task already {task['status']}"}
    _cancel.setdefault(task_id, threading.Event()).set()
    _approvals.setdefault(task_id, threading.Event()).set()  # wake a waiting runner
    store.update_task(task_id, status="cancelled")
    _broadcast(task_id)
    return {"success": True}


def recover_interrupted() -> None:
    """Tasks that were running when the backend stopped are paused, not lost."""
    store = get_task_store()
    for tid in store.interrupted():
        store.update_task(tid, status="paused")


# ─── runner ──────────────────────────────────────────────────────────────────


def _run(task_id: str) -> None:
    store = get_task_store()
    ctx: dict[str, Any] = {}
    task = store.get_task(task_id)
    if not task:
        return
    # Rebuild context from finished steps (resume after approval/restart).
    for step in task["steps"]:
        if step["status"] == "done" and isinstance(step["output"], dict):
            ctx[step["kind"]] = step["output"]
    store.update_task(task_id, status="running")
    _broadcast(task_id)
    for step in task["steps"]:
        if _cancel.get(task_id) and _cancel[task_id].is_set():
            return
        if step["status"] in {"done", "skipped"}:
            continue
        idx = step["idx"]
        store.update_task(task_id, current_step=idx)
        if step.get("detail") == "skip":
            store.update_step(task_id, idx, status="skipped", detail="Not applicable for this agent")
            continue
        if step["policy"] == "input" and step["status"] != "answered":
            questions = (step.get("output") or {}).get("questions") or ask_questions(task)
            ev = _approvals.setdefault(task_id, threading.Event())
            ev.clear()
            store.update_step(task_id, idx, status="waiting_input", output={"questions": questions},
                              detail=f"{len(questions)} questions — answer them to continue")
            store.update_task(task_id, status="waiting_input")
            _notify_input(task)
            _broadcast(task_id)
            if os.environ.get("AUTOMATA_TASKS_SYNC") == "1":
                return  # tests resume via answer()
            ev.wait()
            if _cancel[task_id].is_set():
                return
            step = next(s for s in store.get_task(task_id)["steps"] if s["idx"] == idx)
            store.update_task(task_id, status="running")
        if step["policy"] == "approval" and step["status"] != "approved":
            ev = _approvals.setdefault(task_id, threading.Event())
            ev.clear()
            store.update_step(task_id, idx, status="waiting_approval")
            store.update_task(task_id, status="waiting_approval")
            _broadcast(task_id)
            if os.environ.get("AUTOMATA_TASKS_SYNC") == "1":
                return  # tests resume via approve()
            ev.wait()
            if _cancel[task_id].is_set():
                return
            store.update_step(task_id, idx, status="approved")
            store.update_task(task_id, status="running")
        if step["kind"] == "clarify":
            ctx["clarify_input"] = step.get("output") or {}
        store.update_step(task_id, idx, status="running", started_at=time.time())
        _broadcast(task_id)
        try:
            output = STEP_RUNNERS[step["kind"]](task, ctx)
        except Exception as exc:
            logger.exception("task %s step %s failed", task_id, step["kind"])
            output = {"ok": False, "error": str(exc)}
        ok = output.get("ok", True)
        store.update_step(
            task_id, idx, status="done" if ok else "failed", output=output,
            detail=output.get("message") or output.get("error") or "", finished_at=time.time(),
        )
        ctx[step["kind"]] = output
        if not ok and not output.get("continue"):
            store.update_task(task_id, status="failed", summary=output.get("error"))
            _broadcast(task_id)
            return
    store.update_task(task_id, status="done", summary=ctx.get("report", {}).get("message"))
    _broadcast(task_id)


# ─── steps ───────────────────────────────────────────────────────────────────


def _repo(task: dict[str, Any]) -> str | None:
    if not task.get("project_id"):
        return None
    from db.client import get_project

    project = get_project(task["project_id"])
    path = str((project or {}).get("repo_path") or "")
    return path if os.path.isdir(path) else None


def ask_questions(task: dict[str, Any]) -> list[dict[str, Any]]:
    """Fixed questions plus up to two request-specific ones from the model."""
    from tasks.questions import build_questions, model_questions

    repo = _repo(task)
    name = None
    context = ""
    if repo and task.get("project_id"):
        from db.client import get_project
        from intelligence.profile import prompt_context

        name = (get_project(task["project_id"]) or {}).get("name")
        try:
            context = prompt_context(task["project_id"], 1200)
        except Exception:
            context = ""
    questions = build_questions(task["request"], repo, name)
    if os.environ.get("AUTOMATA_TASK_MODEL_QUESTIONS", "1") != "0":
        questions[-1:-1] = model_questions(task["request"], context)  # before "anything else"
    return questions


def _notify_input(task: dict[str, Any]) -> None:
    try:
        from api.server import broadcast_sync

        broadcast_sync({"type": "task_needs_input", "data": {"id": task["id"], "title": task["title"]},
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")})
    except Exception:
        pass


def step_clarify(task: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    from tasks.questions import ensure_folder

    data = ctx.get("clarify_input") or {}
    questions, answers = data.get("questions", []), data.get("answers", {})
    folder = answers.get("folder") or _repo(task)
    if folder:
        if err := ensure_folder(folder):
            return {"ok": False, "error": err}
    filled = sum(1 for k, v in answers.items() if v and k != "folder")
    return {
        "ok": True, "questions": questions, "answers": answers, "folder": folder,
        "message": (f"Working in {folder}" if folder else "No folder chosen")
                   + (f"; {filled} answers added to the prompt" if filled else ""),
    }


def step_context(task: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    from intelligence.profile import prompt_context
    from memory.local_store import get_store

    pid = task.get("project_id")
    folder = ctx.get("clarify", {}).get("folder") or _repo(task)
    own_folder = _repo(task)
    if folder and own_folder and os.path.normcase(folder) == os.path.normcase(own_folder):
        profile_text = prompt_context(pid) if pid else ""
    elif folder:
        empty = not any(Path(folder).iterdir()) if os.path.isdir(folder) else True
        profile_text = (f"New project in {folder} (empty folder) — set it up from scratch."
                        if empty else f"Existing folder {folder}; read its files to learn the stack.")
    else:
        profile_text = "No project selected — the agent will start from scratch."
    memories = get_store().search(task["request"], project_id=pid, limit=6) if pid and folder == own_folder else []
    return {
        "ok": True,
        "profile": profile_text,
        "memories": [m["content"][:300] for m in memories],
        "repo_path": folder,
        "message": f"{len(memories)} related memories; " + (profile_text.splitlines()[1] if "\n" in profile_text else profile_text)[:160],
    }


def build_prompt(request: str, profile: str, memories: list[str], requirements: str = "",
                 folder: str | None = None) -> str:
    history = "\n".join(f"- {m}" for m in memories) or "- (no related history recorded)"
    where = f"# Where to work\nAll files go in: {folder}\n\n" if folder else ""
    reqs = f"# Requirements from the developer\n{requirements}\n\n" if requirements else ""
    return (
        f"# Task\n{request.strip()}\n\n"
        f"{where}{reqs}"
        f"# Project context (detected by AUTOMATA from the project files)\n{profile}\n\n"
        f"# Relevant history from this project\n{history}\n\n"
        "# How to work\n"
        "- Work inside the project folder and follow its existing stack, structure and conventions.\n"
        "- Never hard-code secrets. Read them from environment variables and add each new variable "
        "to .env.example with an empty or placeholder value.\n"
        "- Keep changes focused on the task; do not rewrite unrelated code.\n\n"
        "# When you finish, reply with\n"
        "1. Files created or changed.\n"
        "2. How to run and test it.\n"
        "3. Every API key, connection string, account or manual step the developer must provide.\n"
    )


def step_prompt(task: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    from tasks.questions import requirements_section

    c = ctx.get("context", {})
    clarify = ctx.get("clarify", {})
    reqs = requirements_section(clarify.get("questions", []), clarify.get("answers", {}))
    prompt = build_prompt(clean_request(task["request"]), c.get("profile", ""), c.get("memories", []), reqs,
                          c.get("repo_path"))
    return {"ok": True, "prompt": prompt, "message": f"{len(prompt)} characters, grounded in the project profile"}


def _snapshot_mtimes(repo: str) -> dict[str, float]:
    from intelligence.profile import _walk

    out = {}
    for f in _walk(Path(repo)):
        try:
            out[str(f)] = f.stat().st_mtime
        except OSError:
            pass
    return out


def _baseline_path(task_id: str) -> str:
    from config import data_dir

    folder = os.path.join(data_dir(), "task_baselines")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, f"{task_id}.json")


def step_handoff(task: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    import json

    from automation.agent_bridge import AgentBridge

    prompt = ctx.get("prompt", {}).get("prompt", "")
    repo = ctx.get("context", {}).get("repo_path")
    baseline = _snapshot_mtimes(repo) if repo else {}
    baseline_file = _baseline_path(task["id"])
    with open(baseline_file, "w", encoding="utf-8") as fh:
        json.dump(baseline, fh)
    agent = task["agent"]
    if agent == "chatgpt":
        from automation.desktop import handoff_prompt

        res = handoff_prompt(prompt, url="https://chatgpt.com/")
        ok = res.get("success", False)
        return {"ok": ok, "via": "browser", "baseline_files": len(baseline), "baseline_path": baseline_file,
                "message": "Sent to ChatGPT" if ok else res.get("error"), "error": None if ok else res.get("error")}
    result = AgentBridge().send_prompt(agent, prompt, {"repo_path": repo})
    ok = result.status == "ok"
    # Fallback already copied the prompt to the clipboard when no path exists.
    manual = result.status in {"unsupported", "unavailable"}
    return {
        "ok": ok or manual,
        "via": "manual" if manual else agent,
        "manual": manual,
        "message": result.output[:400],
        "baseline_path": baseline_file,
        "baseline_files": len(baseline),
        "error": None if ok or manual else result.output[:400],
        "continue": manual,
    }


def step_watch(task: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    repo = ctx.get("context", {}).get("repo_path")
    if not repo:
        return {"ok": True, "changed_files": [], "message": "No project folder to watch."}
    import json

    baseline: dict[str, float] = {}
    path = ctx.get("handoff", {}).get("baseline_path")
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            baseline = json.load(fh)
    deadline = time.monotonic() + float(os.environ.get("AUTOMATA_TASK_WATCH_MAX", WATCH_MAX_S))
    quiet = float(os.environ.get("AUTOMATA_TASK_WATCH_QUIET", WATCH_QUIET_S))
    poll = float(os.environ.get("AUTOMATA_TASK_WATCH_POLL", WATCH_POLL_S))
    changed: set[str] = set()
    last_change = None
    cancel = _cancel.get(task["id"])
    waited_for_agent = False
    while time.monotonic() < deadline:
        if cancel and cancel.is_set():
            return {"ok": False, "error": "Cancelled"}
        current = _snapshot_mtimes(repo)
        newly = {p for p, m in current.items() if baseline.get(p) != m} - changed
        if newly:
            changed |= newly
            last_change = time.monotonic()
        if last_change and time.monotonic() - last_change >= quiet:
            # Agents pause to think between edits: a quiet folder is not "done"
            # while the agent says it is still working.
            if _agent_busy(task, repo):
                waited_for_agent = True
                time.sleep(poll)
                continue
            break
        time.sleep(poll)
    rel = sorted(os.path.relpath(p, repo) for p in changed)
    if not rel:
        return {"ok": True, "changed_files": [], "continue": True,
                "message": "No file changes seen yet — the agent may still be working or waiting for you."}
    still = _agent_busy(task, repo)
    note = " (the agent is still working — check it before building)" if still else (
        " after the agent finished" if waited_for_agent else "")
    return {"ok": True, "changed_files": rel[:200], "agent_busy": bool(still),
            "message": f"{len(rel)} files changed{note}"}


def _agent_busy(task: dict[str, Any], repo: str | None) -> bool:
    """True only when the agent's app clearly shows it is still working."""
    try:
        from automation.chat_apps import agent_busy

        return agent_busy(task.get("agent", ""), repo) is True
    except Exception:
        return False


def step_verify(task: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    from automation.command_executor import CommandExecutor
    from intelligence.profile import detect

    repo = ctx.get("context", {}).get("repo_path")
    if not repo:
        return {"ok": True, "results": [], "message": "No project folder — nothing to build."}
    profile = detect(repo)
    results = []
    for entry in profile.get("run_book", []):
        cmd = entry["commands"].get("build") or entry["commands"].get("test")
        if not cmd:
            continue
        cwd = os.path.join(repo, entry["path"]) if entry["path"] != "." else repo
        r = CommandExecutor(cwd=cwd, allow_auto_execute=True).execute(cmd, context=f"task {task['id']} verify")
        results.append({
            "path": entry["path"], "command": cmd, "status": r.status, "exit_code": r.exit_code,
            "output_tail": ((r.stdout or "") + (r.stderr or ""))[-1200:],
        })
    failed = [r for r in results if r["status"] != "ok"]
    if not results:
        return {"ok": True, "results": [], "message": "No build or test command detected."}
    return {
        "ok": True,  # a failing build is a finding, not a crash; the report shows it
        "results": results,
        "passed": not failed,
        "message": "All checks passed" if not failed else f"{len(failed)} of {len(results)} checks failed",
    }


_ENV_NAME = re.compile(r"\b([A-Z][A-Z0-9]*_(?:[A-Z0-9]+_)*(?:KEY|SECRET|TOKEN|URL|URI|DSN|ID|PASSWORD))\b")


def step_needs(task: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    from tasks.needs import collect_needs

    extra = set(_ENV_NAME.findall(ctx.get("handoff", {}).get("message", "") or ""))
    needs = collect_needs(task.get("project_id"), task["id"], extra_vars=extra)
    return {"ok": True, "needs": [n["var"] for n in needs],
            "message": f"{len(needs)} things needed from you" if needs else "Nothing else needed"}


def step_report(task: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    from memory.local_store import remember

    changed = ctx.get("watch", {}).get("changed_files", [])
    verify = ctx.get("verify", {})
    needs = ctx.get("needs", {}).get("needs", [])
    parts = [f"Task '{task['title']}' via {AGENT_LABELS.get(task['agent'], task['agent'])}."]
    if ctx.get("handoff", {}).get("manual"):
        parts.append("Prompt copied for you to paste (no automatic hand-off path for this app).")
    parts.append(f"{len(changed)} files changed." if changed else "No file changes detected.")
    if verify.get("results"):
        parts.append(verify.get("message", ""))
    if needs:
        parts.append("Still needed from you: " + ", ".join(needs[:8]) + ".")
    message = " ".join(p for p in parts if p)
    if task.get("project_id"):
        remember(task["project_id"], "task", message, ref=f"task:{task['id']}")
    return {"ok": True, "message": message, "changed_files": changed[:50], "needs": needs}


STEP_RUNNERS = {
    "clarify": step_clarify,
    "context": step_context,
    "prompt": step_prompt,
    "handoff": step_handoff,
    "watch": step_watch,
    "verify": step_verify,
    "needs": step_needs,
    "report": step_report,
}
