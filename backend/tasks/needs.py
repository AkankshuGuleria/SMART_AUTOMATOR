"""
tasks/needs.py — the "Needs from you" inbox.

Owns:    Turning missing env vars (from the project profile or an agent's
         reply) into actionable items with instructions, and resolving them.
Never:   Stores a secret value in AUTOMATA's databases or logs. A value is
         written only to Windows Credential Manager (keyring) and/or the
         project's own .env, whichever the user picks.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

from tasks.store import get_task_store

logger = logging.getLogger(__name__)

KEYRING_SERVICE = "AUTOMATA"


def collect_needs(project_id: str | None, task_id: str | None = None,
                  extra_vars: set[str] | None = None, refresh: bool = True) -> list[dict[str, Any]]:
    """Create open needs for every required-but-unset variable; return the open list."""
    from intelligence.profile import get_profile
    from intelligence.providers import describe

    store = get_task_store()
    if project_id:
        profile = get_profile(project_id, refresh=refresh)
        if profile.get("ok"):
            repo = profile["repo_path"]
            required = {v["name"] for v in profile["env"]["variables"] if not v["set"] and v["kind"] != "config"}
            # Close items that are now set or no longer referenced by the project
            # (task-specific extras stay until the user handles them).
            for need in store.list_needs(project_id=project_id):
                if need["var"] not in required and not need.get("task_id"):
                    store.resolve_need(need["id"], "no_longer_needed", status="resolved")
            for var in profile["env"]["variables"]:
                # Plain settings (ports, feature flags, optional URLs) usually have
                # defaults; only keys, secrets and connection strings need the user.
                if var["set"] or var["kind"] == "config":
                    continue
                declared = var.get("declared_in")
                target = os.path.join(repo, os.path.dirname(declared), ".env") if declared else os.path.join(repo, ".env")
                store.add_need(project_id, task_id, var["name"], describe(var["name"]), target)
            for name in extra_vars or set():
                if not any(v["name"] == name for v in profile["env"]["variables"]):
                    store.add_need(project_id, task_id, name, describe(name), os.path.join(repo, ".env"))
    return store.list_needs(project_id=project_id) if project_id else store.list_needs(task_id=task_id)


def _write_env(path: str, var: str, value: str) -> None:
    """Set VAR=value in a .env file (replacing an existing line); make sure git ignores it."""
    env = Path(path)
    lines = env.read_text(encoding="utf-8").splitlines() if env.exists() else []
    safe = value if re.fullmatch(r"[^\s'\"#]+", value) else '"' + value.replace('"', '\\"') + '"'
    pattern = re.compile(rf"^\s*(export\s+)?{re.escape(var)}\s*=")
    for i, line in enumerate(lines):
        if pattern.match(line):
            lines[i] = f"{var}={safe}"
            break
    else:
        lines.append(f"{var}={safe}")
    env.parent.mkdir(parents=True, exist_ok=True)
    env.write_text("\n".join(lines) + "\n", encoding="utf-8")


def env_is_gitignored(env_path: str) -> bool:
    import subprocess

    folder = os.path.dirname(env_path) or "."
    try:
        out = subprocess.run(["git", "check-ignore", "-q", env_path], cwd=folder,
                             capture_output=True, timeout=5)
        return out.returncode == 0
    except Exception:
        return False


def resolve(need_id: str, value: str | None, save_to: str) -> dict[str, Any]:
    """save_to: 'keyring' | 'env_file' | 'both' | 'done' (handled manually) | 'dismiss'."""
    store = get_task_store()
    need = store.get_need(need_id)
    if not need:
        return {"success": False, "error": "Item not found"}
    if need["status"] != "open":
        return {"success": False, "error": f"Already {need['status']}"}
    if save_to == "dismiss":
        store.resolve_need(need_id, "dismissed", status="dismissed")
        return {"success": True, "status": "dismissed"}
    if save_to == "done":
        store.resolve_need(need_id, "manual")
        return {"success": True, "status": "resolved", "resolution": "manual"}
    if save_to not in {"keyring", "env_file", "both"}:
        return {"success": False, "error": "save_to must be keyring, env_file, both, done or dismiss"}
    if not value or not value.strip():
        return {"success": False, "error": "A value is required"}
    value = value.strip()
    saved = []
    warnings = []
    if save_to in {"keyring", "both"}:
        try:
            import keyring

            keyring.set_password(f"{KEYRING_SERVICE}:{need.get('project_id') or 'global'}", need["var"], value)
            saved.append("Windows Credential Manager")
            try:
                from db.client import insert_credential_ref

                insert_credential_ref(need.get("project_id"), need["var"], f"Needed by task {need.get('task_id')}")
            except Exception:
                pass  # the label is optional bookkeeping
        except Exception as exc:
            return {"success": False, "error": f"Could not save to Credential Manager: {exc}"}
    if save_to in {"env_file", "both"}:
        target = need.get("target_file")
        if not target:
            return {"success": False, "error": "No .env location known for this project"}
        if not env_is_gitignored(target):
            warnings.append(f"{target} is not ignored by git — add '.env' to .gitignore before committing.")
        try:
            _write_env(target, need["var"], value)
            saved.append(target)
        except OSError as exc:
            return {"success": False, "error": f"Could not write {target}: {exc}"}
    store.resolve_need(need_id, save_to)
    logger.info("needs: %s resolved via %s", need["var"], save_to)  # never log the value
    return {"success": True, "status": "resolved", "saved_to": saved, "warnings": warnings}
