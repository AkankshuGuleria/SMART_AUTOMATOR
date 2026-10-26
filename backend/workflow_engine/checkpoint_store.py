"""workflow_engine/checkpoint_store.py — AUTOMATA Workflow Engine: checkpoint persistence.

Owns:    Persisting and restoring ExecutionContext snapshots per step.
Never:   Must not call Bedrock directly. Never unpickles: checkpoints are JSON,
         so a tampered file cannot run code, and run/step ids are restricted to
         safe characters so they cannot point outside the checkpoint folder.
Ref:     WORKFLOW_ENGINE.md §7.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from workflow_engine.context import ExecutionContext

logger = logging.getLogger(__name__)

_SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")


def _checkpoint_dir() -> Path:
    from config import data_dir

    return Path(data_dir()) / "workflow_checkpoints"


def _path(run_id: str, step_id: str) -> Path:
    if not _SAFE_ID.match(str(run_id)) or not _SAFE_ID.match(str(step_id)) or ".." in f"{run_id}{step_id}":
        raise ValueError("Invalid run or step id")
    return _checkpoint_dir() / f"{run_id}_{step_id}.json"


def save_checkpoint(run_id: str, step_id: str, context: ExecutionContext) -> str:
    """
    Persist an ExecutionContext snapshot for a given run and step.

    Returns the checkpoint file path.
    """
    checkpoint_path = _path(run_id, step_id)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        data = {
            "run_id": run_id,
            "step_id": step_id,
            "context": {
                "inputs": context.inputs,
                "step_outputs": context.step_outputs,
                "retrieved_memories": context.retrieved_memories,
                "redactions": context.redactions,
                "timing": context.timing,
            },
        }
        checkpoint_path.write_text(json.dumps(data, default=str), encoding="utf-8")
        logger.info(
            "checkpoint_store: saved | run=%s step=%s path=%s", run_id, step_id, checkpoint_path
        )
    except Exception as exc:
        logger.error(
            "checkpoint_store: failed to save | run=%s step=%s error=%s", run_id, step_id, exc
        )

    return str(checkpoint_path)


def load_checkpoint(run_id: str, step_id: str) -> ExecutionContext | None:
    """
    Restore an ExecutionContext from a checkpoint.

    Returns None if no checkpoint exists (or the ids are not valid).
    """
    try:
        checkpoint_path = _path(run_id, step_id)
    except ValueError:
        logger.warning("checkpoint_store: rejected unsafe id | run=%r step=%r", run_id, step_id)
        return None
    if not checkpoint_path.exists():
        return None

    try:
        data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        ctx_data = data.get("context", {})
        context = ExecutionContext(
            inputs=ctx_data.get("inputs", {}),
            step_outputs=ctx_data.get("step_outputs", {}),
            retrieved_memories=ctx_data.get("retrieved_memories", []),
            redactions=ctx_data.get("redactions", []),
            timing=ctx_data.get("timing", {}),
        )
        logger.info("checkpoint_store: loaded | run=%s step=%s", run_id, step_id)
        return context
    except Exception as exc:
        logger.error(
            "checkpoint_store: failed to load | run=%s step=%s error=%s", run_id, step_id, exc
        )
        return None


def list_checkpoints(run_id: str) -> list[str]:
    """List all checkpoints for a given run."""
    if not _SAFE_ID.match(str(run_id)):
        return []
    checkpoints = sorted(
        _checkpoint_dir().glob(f"{run_id}_*.json"),
        key=lambda path: path.stat().st_mtime,
    )
    return [str(p) for p in checkpoints]


def cleanup_checkpoints(run_id: str) -> None:
    """Remove all checkpoints for a given run."""
    if not _SAFE_ID.match(str(run_id)):
        return
    for checkpoint in _checkpoint_dir().glob(f"{run_id}_*.json"):
        try:
            checkpoint.unlink()
        except OSError:
            logger.warning("checkpoint_store: failed to delete %s", checkpoint)
