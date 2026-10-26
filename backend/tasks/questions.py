"""
tasks/questions.py — what to ask the developer before handing work to an agent.

Owns:    The "Ask what's needed" step: where the work should live (this project's
         folder, or where to save a new project), the stack for a new project,
         must-have features, design direction, anything else — plus up to two
         request-specific questions from the model when one is reachable.
         Validates answers (the folder is created only after the user picks it).
Never:   Blocks on the model: its questions are optional and time-boxed.
"""

from __future__ import annotations

import logging
import os
import re
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

STACKS = ["Let the agent choose", "Plain HTML, CSS and JavaScript", "React + Vite", "Next.js",
          "Python (FastAPI)", "Node.js (Express)"]
_UI_WORDS = re.compile(r"\b(website|site|landing|page|ui|dashboard|app|frontend|portfolio|design|form|screen)\b", re.I)
MODEL_TIMEOUT_S = 8.0


def _slug(text: str) -> str:
    words = re.findall(r"[a-z0-9]+", text.lower())
    stop = {"a", "an", "the", "for", "my", "me", "to", "of", "and", "with", "can", "you", "please", "using",
            "use", "via", "in", "make", "create", "build", "simple", "new",
            "antigravity", "claude", "cursor", "vscode", "vs", "code", "chatgpt"}
    kept = [w for w in words if w not in stop][:4]
    return "-".join(kept) or "new-project"


def default_projects_dir() -> str:
    """D:\\Projects when a D: drive exists (C: is often full), else ~/Projects."""
    if os.name == "nt" and os.path.isdir("D:\\"):
        return "D:\\Projects"
    return str(Path.home() / "Projects")


def build_questions(request: str, repo_path: str | None, project_name: str | None = None) -> list[dict[str, Any]]:
    """The fixed questions for a delegation (no model needed)."""
    questions: list[dict[str, Any]] = []
    if repo_path:
        questions.append({
            "id": "folder", "kind": "folder", "required": True, "default": repo_path,
            "question": "Where should the agent work?",
            "help": f"Default: this project's folder ({project_name or Path(repo_path).name}). "
                    "Pick another folder to start a separate project there.",
        })
    else:
        questions.append({
            "id": "folder", "kind": "folder", "required": True,
            "default": os.path.join(default_projects_dir(), _slug(request)),
            "question": "Where should the new project be saved?",
            "help": "The folder is created if it does not exist. The agent works only inside it.",
        })
        questions.append({
            "id": "stack", "kind": "choice", "required": False, "options": STACKS, "default": STACKS[0],
            "question": "Which stack should it use?",
        })
    questions.append({
        "id": "features", "kind": "text", "required": False, "default": "",
        "question": "What must it include?",
        "help": "Pages, features, integrations, data — one per line is fine.",
    })
    if _UI_WORDS.search(request):
        questions.append({
            "id": "style", "kind": "text", "required": False, "default": "",
            "question": "Any design direction?",
            "help": "Colours, mood, fonts, sites you like.",
        })
    questions.append({
        "id": "extra", "kind": "text", "required": False, "default": "",
        "question": "Anything else the agent should know?",
        "help": "Constraints, accounts you already have, things to avoid.",
    })
    return questions


def model_questions(request: str, context: str, timeout: float = MODEL_TIMEOUT_S) -> list[dict[str, Any]]:
    """Up to two request-specific questions from the model; [] if it is slow or unavailable."""
    out: list[str] = []

    def ask() -> None:
        try:
            from ai.bedrock_client import invoke_reasoning

            reply = invoke_reasoning(
                "You help a developer brief a coding agent. List at most 2 short questions whose "
                "answers would change what the agent builds and that are NOT about the folder, the "
                "stack, features, design or 'anything else' (those are already asked). One question "
                "per line, each ending with '?'. If nothing important is missing, reply NONE.",
                f"Task: {request}\n\nProject:\n{context[:1500]}",
                [],
            )
            for line in str(reply or "").splitlines():
                line = line.strip().lstrip("-*0123456789. ").strip()
                if line.endswith("?") and 10 <= len(line) <= 160:
                    out.append(line)
        except Exception as exc:
            logger.debug("model questions skipped — %s", exc)

    t = threading.Thread(target=ask, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        return []
    return [{"id": f"q{i + 1}", "kind": "text", "required": False, "default": "", "question": q,
             "from_model": True} for i, q in enumerate(out[:2])]


def validate_answers(questions: list[dict[str, Any]], answers: dict[str, Any]) -> tuple[dict[str, str], str | None]:
    """Fill defaults, check the folder. Returns (answers, error)."""
    clean: dict[str, str] = {}
    for q in questions:
        value = answers.get(q["id"])
        value = (str(value).strip() if value is not None else "") or str(q.get("default") or "")
        if q.get("kind") == "choice" and value and q.get("options") and value not in q["options"]:
            value = value[:200]  # custom answer typed instead of an option
        clean[q["id"]] = value[:2000]
    folder = clean.get("folder", "")
    if folder:
        path = Path(os.path.expandvars(os.path.expanduser(folder)))
        if not path.is_absolute():
            return clean, "Give the full folder path, e.g. D:\\Projects\\my-site."
        if not Path(path.anchor).exists():
            return clean, f"Drive {path.anchor} does not exist."
        if path.exists() and not path.is_dir():
            return clean, f"{path} is a file, not a folder."
        clean["folder"] = str(path)
    return clean, None


def ensure_folder(folder: str) -> str | None:
    """Create the chosen folder. Returns an error message or None."""
    try:
        os.makedirs(folder, exist_ok=True)
        return None
    except OSError as exc:
        return f"Could not create {folder}: {exc}"


def requirements_section(questions: list[dict[str, Any]], answers: dict[str, str]) -> str:
    """Prompt section with the developer's answers (skips empty ones)."""
    lines = []
    for q in questions:
        if q["id"] == "folder":
            continue
        value = (answers.get(q["id"]) or "").strip()
        if value and not (q["id"] == "stack" and value == STACKS[0]):
            lines.append(f"- {q['question']} {value}")
    return "\n".join(lines)
