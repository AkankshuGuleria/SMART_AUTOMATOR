"""
scripts/seed_project.py — register AUTOMATA itself as a tracked project with initial architecture notes.

Run from the repo root:  uv run --project backend python scripts/seed_project.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from db.client import insert_architecture_note, insert_project  # noqa: E402

PROJECT_NAME = "AUTOMATA"
REPO_PATH = str(ROOT)


def _existing_project_id() -> str | None:
    """Return the id of an existing project with the same name, if any."""
    try:
        from db.client import get_projects

        for project in get_projects() or []:
            if project.get("name") == PROJECT_NAME:
                return str(project["id"])
    except Exception as exc:
        print(f"Failed to check for existing project — {exc}")
    return None


def seed() -> None:
    existing_id = _existing_project_id()
    if existing_id:
        print(f"Project {PROJECT_NAME!r} already exists with id {existing_id}; skipping insert")
        project_id = existing_id
    else:
        project_id = insert_project(PROJECT_NAME, REPO_PATH)
        if project_id is None:
            print("Failed to insert project")
            return

        print(f"Inserted project {PROJECT_NAME!r} with id {project_id}")

    notes = [
        (
            "AUTOMATA overview",
            "AUTOMATA is a persistent memory developer agent. The backend is a FastAPI service "
            "that exposes memory query, brief, restore, and soon agent action endpoints "
            "over HTTP/WebSocket. The frontend is a React/Tauri shell.",
        ),
        (
            "Memory layer",
            "Backend memory lives in backend/memory/: capture.py (file watcher, git poller, "
            "terminal capture), retrieval.py (vector + recent retrieval), and embeddings.py. "
            "CockroachDB stores projects, sessions, commits, file edits, terminal commands, "
            "todos, architecture notes, daily briefs, taste preferences, credential refs, "
            "decision log, and mistake log.",
        ),
        (
            "Reasoning layer",
            "backend/ai/bedrock_client.py wraps Ollama as the default free backend, with "
            "Bedrock, Groq, Gemini, Minimax, OpenRouter, Cohere, and NVIDIA as fallback chains. Embeddings and "
            "chat both route through invoke_embedding and invoke_reasoning.",
        ),
        (
            "Automation layer",
            "backend/automation/: os_windows.py owns Windows OS actions; restore.py "
            "implements workspace restoration; dev_servers.py handles dev server orchestration.",
        ),
        (
            "API surface",
            "FastAPI routes in backend/api/server.py: /health, /projects (GET/POST), "
            "/projects/{id}/brief, /projects/{id}/restore, /query, /explain-repository, "
            "and a WebSocket /ws.",
        ),
    ]

    inserted = 0
    for title, content in notes:
        note_id = insert_architecture_note(project_id, title, content)
        if note_id:
            inserted += 1
        else:
            print(f"Failed to insert note {title!r}")

    print(f"Inserted {inserted}/{len(notes)} architecture notes")


if __name__ == "__main__":
    seed()
