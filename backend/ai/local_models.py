"""
ai/local_models.py — set up on-device AI (Ollama models, offline embeddings).

Owns:    Recommending a local model that fits this machine, pulling models
         through Ollama's HTTP API with progress, launching the Ollama
         installer when the user asks, and remembering the chosen model.
Never:   Downloads or installs anything on its own — every download/install
         starts from an explicit API call made by a user action in the UI.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import threading
import time
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

MODELS = [
    {"name": "qwen2.5-coder:7b", "size_gb": 4.7, "min_vram_gb": 6, "use": "chat", "label": "Best quality (needs 6 GB+ VRAM)"},
    {"name": "qwen2.5-coder:3b", "size_gb": 1.9, "min_vram_gb": 3, "use": "chat", "label": "Balanced — fits 4 GB GPUs"},
    {"name": "qwen2.5-coder:1.5b", "size_gb": 1.0, "min_vram_gb": 0, "use": "chat", "label": "Fast, low memory"},
    {"name": "nomic-embed-text", "size_gb": 0.3, "min_vram_gb": 0, "use": "embedding", "label": "Semantic memory search"},
]

_pull: dict[str, Any] = {"model": None, "status": "idle", "completed": 0, "total": 0, "error": None, "started": None}
_pull_lock = threading.Lock()


def models_dir() -> str:
    return os.environ.get("OLLAMA_MODELS") or os.path.join(os.path.expanduser("~"), ".ollama", "models")


def _free_gb(path: str) -> float | None:
    probe = path
    while probe and not os.path.exists(probe):
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        probe = parent
    try:
        return round(shutil.disk_usage(probe).free / 2**30, 1)
    except Exception:
        return None


def recommend() -> dict[str, Any]:
    """Pick the best chat model for this GPU and disk."""
    vram_gb = 0.0
    try:
        from monitoring.system_metrics import get_system_metrics

        gpu = (get_system_metrics().get("gpu") or {}).get("devices") or []
        if gpu and gpu[0].get("memory_total_mb"):
            vram_gb = gpu[0]["memory_total_mb"] / 1024
    except Exception:
        pass
    free = _free_gb(models_dir())
    chat = next(m for m in MODELS if m["use"] == "chat" and vram_gb >= m["min_vram_gb"])
    needed = chat["size_gb"] + MODELS[-1]["size_gb"] + 1.0
    warning = None
    if free is not None and free < needed:
        warning = (
            f"Only {free} GB free where Ollama stores models ({models_dir()}). "
            f"Free up space or set the OLLAMA_MODELS environment variable to a folder on a larger drive."
        )
    return {
        "chat_model": chat["name"],
        "embedding_model": "nomic-embed-text",
        "reason": f"{chat['label']}; detected {round(vram_gb, 1)} GB GPU memory",
        "vram_gb": round(vram_gb, 1),
        "models_dir": models_dir(),
        "free_gb": free,
        "needed_gb": round(needed, 1),
        "warning": warning,
        "catalog": MODELS,
    }


def pull_status() -> dict[str, Any]:
    with _pull_lock:
        state = dict(_pull)
    state["percent"] = round(state["completed"] / state["total"] * 100, 1) if state["total"] else 0.0
    return state


def start_pull(model: str) -> dict[str, Any]:
    """Pull *model* in the background through Ollama's /api/pull (streams progress)."""
    from ai.bedrock_client import _ollama_url, ollama_status

    if not ollama_status()["running"]:
        return {"success": False, "error": "Ollama is not running. Install/start Ollama first."}
    with _pull_lock:
        if _pull["status"] == "pulling":
            return {"success": False, "error": f"Already pulling {_pull['model']}"}
        _pull.update(model=model, status="pulling", completed=0, total=0, error=None, started=time.time())

    def worker() -> None:
        try:
            req = urllib.request.Request(  # noqa: S310 — URL from _ollama_url(), restricted to http(s)
                f"{_ollama_url()}/api/pull",
                data=json.dumps({"name": model, "stream": True}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=3600) as resp:  # noqa: S310 — URL from _ollama_url(), restricted to http(s)
                for raw in resp:
                    if not raw.strip():
                        continue
                    event = json.loads(raw)
                    with _pull_lock:
                        if event.get("error"):
                            _pull.update(status="error", error=event["error"])
                            return
                        if event.get("total"):
                            _pull.update(total=event["total"], completed=event.get("completed", 0))
                        if event.get("status") == "success":
                            _pull.update(status="done", completed=_pull["total"])
            with _pull_lock:
                if _pull["status"] == "pulling":
                    _pull["status"] = "done"
        except Exception as exc:
            with _pull_lock:
                _pull.update(status="error", error=str(exc))

    threading.Thread(target=worker, name=f"ollama-pull-{model}", daemon=True).start()
    return {"success": True, **pull_status()}


def select_chat_model(model: str) -> dict[str, Any]:
    from memory.local_store import get_store

    get_store().set_value("ollama_chat_model", model)
    return {"success": True, "chat_model": model}


def set_offline_embeddings(enabled: bool) -> dict[str, Any]:
    from ai.bedrock_client import fastembed_status
    from memory.local_store import get_store

    status = fastembed_status()
    if enabled and not status["installed"]:
        return {
            "success": False,
            "error": "The offline embedding package is not installed. Run: cd backend; uv sync --extra local-ai",
            **status,
        }
    get_store().set_value("fastembed_enabled", bool(enabled))
    return {"success": True, **fastembed_status()}


def launch_ollama_installer() -> dict[str, Any]:
    """Open a visible terminal running the official winget install (user watches it)."""
    if os.name != "nt":
        return {"success": False, "error": "Automatic install is only available on Windows. See https://ollama.com/download"}
    if not shutil.which("winget"):
        return {"success": False, "error": "winget not found. Download Ollama from https://ollama.com/download"}
    cmd = "winget install --id Ollama.Ollama -e & pause"  # winget shows its own terms prompt
    subprocess.Popen(["cmd", "/c", cmd], creationflags=subprocess.CREATE_NEW_CONSOLE)
    return {"success": True, "detail": "Installer opened in a new window. Start Ollama when it finishes."}
