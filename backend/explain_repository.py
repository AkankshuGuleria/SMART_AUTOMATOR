"""
explain_repository.py — AUTOMATA Agent Actions: explain repository.

Owns:    Synthesizing a grounded explanation of a project's architecture, folder
         structure, and recent activity from README content, on-disk layout, and
         stored architecture notes in CockroachDB.
Never:   Must not write to CockroachDB (read-only).
Ref:     ROADMAP.md Phase 4 TASK-044, PROJECT.md §4 (Agent Actions).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DIR_MARKER_FILES = {
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "go.mod",
    "Cargo.toml",
    "README.md",
    "ARCHITECTURE.md",
    "DATABASE_SCHEMA.md",
    "src",
    "backend",
    "frontend",
    "lib",
    "cmd",
    "internal",
    "pkg",
    "app",
    "tests",
    "docs",
    ".env",
    ".env.example",
}

_WATCHED_EXTENSIONS = frozenset({
    ".py", ".ts", ".tsx", ".js", ".jsx", ".html", ".css",
    ".md", ".json", ".yaml", ".yml", ".toml", ".txt", ".rst",
    ".cfg", ".ini", ".lock",
})

_IGNORED_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "env",
    ".env",
    "dist",
    "build",
    "target",
    "tmp",
    "tmpfs",
    ".idea",
    ".vscode",
    ".mypy_cache",
    ".pytest_cache",
    ".next",
    ".turbo",
}


def _read_readme(repo_path: str) -> str:
    """Return the contents of README.md (case-insensitive) under repo_path."""
    root = Path(repo_path)
    for candidate in ("README.md", "README.MD", "readme.md"):
        if (root / candidate).exists():
            try:
                return (root / candidate).read_text(encoding="utf-8")
            except Exception as exc:
                logger.warning("explain_repository: failed to read README — %s", exc)
    return ""


def _scan_folder_structure(repo_path: str, max_depth: int = 2) -> list[dict[str, Any]]:
    """
    Scan top-level (and one level deeper) folders/files for a coarse structural summary.
    Returns a compact list of dicts: {path, type, notable}.
    """
    root = Path(repo_path)
    entries: list[dict[str, Any]] = []

    def _walk(path: Path, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            children = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except PermissionError:
            return

        for child in children:
            if child.name in _IGNORED_DIRS:
                continue

            notable_exts = {
                ".py", ".ts", ".tsx", ".js", ".rs", ".go",
                ".toml", ".yaml", ".yml", ".json", ".md",
            }
            notable = child.name in _DIR_MARKER_FILES or child.suffix in notable_exts

            entries.append({
                "path": str(child.relative_to(root)),
                "type": "dir" if child.is_dir() else "file",
                "notable": notable,
            })

            if child.is_dir():
                _walk(child, depth + 1)

    _walk(root, 0)
    return entries


def _get_architecture_notes(project_id: str) -> list[dict[str, Any]]:
    """Return stored architecture notes from the database (read-only)."""
    from db.client import get_architecture_notes

    try:
        return get_architecture_notes(project_id)
    except Exception as exc:
        logger.warning("explain_repository: failed to fetch architecture notes — %s", exc)
        return []


def _build_fallback_explanation(
    readme_text: str,
    folder: list[dict[str, Any]],
    notes: list[dict[str, Any]],
) -> str:
    """Build a concise structured explanation when no LLM backend is available."""
    parts: list[str] = []

    if readme_text:
        first_line = readme_text.splitlines()[0].strip()
        if first_line.startswith("#"):
            first_line = first_line.lstrip("# ").strip()
        parts.append(f"# {first_line}")

    notable = [e for e in folder if e.get("notable")]
    if notable:
        parts.append("\nNotable files/dirs:")
        parts.extend(f"- {e['path']} ({e['type']})" for e in notable[:40])

    if notes:
        parts.append("\nArchitecture notes:")
        parts.extend(f"- {n.get('title','(untitled)')}: {n.get('content','')}" for n in notes[:5])

    if not parts:
        return "No README, notable files, or architecture notes were found for this project."

    return "\n".join(parts)


def synthesize_explanation(
    project_id: str,
    repo_path: str,
    recent_memories: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Produce a bounded explanation of the repository grounded in README, folder
    structure, and stored architecture notes. Returns a dict:

    {
        "project_id": str,
        "repo_path": str,
        "readme_summary": str,
        "folder_structure": list[dict],
        "architecture_notes": list[dict],
        "explanation": str | None,
        "error": str | None,
    }
    """
    if not project_id or not repo_path:
        return {
            "project_id": project_id,
            "repo_path": repo_path,
            "readme_summary": "",
            "folder_structure": [],
            "architecture_notes": [],
            "explanation": None,
            "error": "project_id and repo_path are required",
        }

    readme_text = _read_readme(repo_path)
    folder = _scan_folder_structure(repo_path)
    notes = _get_architecture_notes(project_id)

    context_parts: list[str] = []
    if readme_text:
        context_parts.append(f"README (first 4000 chars):\n{readme_text[:4000]}")

    if folder:
        notable = [e for e in folder if e.get("notable")]
        if notable:
            context_parts.append(
                "Notable top-level files/dirs:\n"
                + "\n".join(f"- {e['path']} ({e['type']})" for e in notable[:40])
            )

    if notes:
        note_bits = [f"- {n.get('title','(untitled)')}: {n.get('content','')}" for n in notes[:5]]
        context_parts.append("Stored architecture notes:\n" + "\n".join(note_bits))

    if recent_memories:
        mem_lines = [
            f"- [{m.get('table','memory')}] {m.get('content','')}"
            for m in recent_memories[:8]
        ]
        context_parts.append("Recent project memory:\n" + "\n".join(mem_lines))

    context = "\n\n".join(context_parts)

    system_prompt = (
        "You are AUTOMATA's Reasoning Engine. Explain this repository concisely and factually, "
        "grounded ONLY in the context provided below. Do not fabricate files, folders, or behavior "
        "not present in the context. Use short bullets if helpful."
    )
    user_message = (
        "Explain this repository: what it does, how it is organized, key modules, and any "
        "notable architecture points. Keep it tight — one or two short sections max."
    )

    explanation: str | None = None
    try:
        from ai.bedrock_client import invoke_reasoning
        explanation = invoke_reasoning(
            system_prompt=system_prompt,
            user_message=user_message,
            retrieved_memories=[{"table": "readme+folder+notes", "content": context}],
        )
    except Exception as exc:
        logger.warning("explain_repository: reasoning failed — %s", exc)

    if not explanation:
        explanation = _build_fallback_explanation(readme_text, folder, notes)

    return {
        "project_id": project_id,
        "repo_path": repo_path,
        "readme_summary": readme_text[:600],
        "folder_structure": folder,
        "architecture_notes": notes,
        "explanation": explanation,
        "error": None,
    }
