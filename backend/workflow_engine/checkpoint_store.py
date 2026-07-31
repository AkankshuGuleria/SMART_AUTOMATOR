"""workflow_engine/checkpoint_store.py — AUTOMATA Workflow Engine: checkpoint persistence.

Owns:    Persisting and restoring ExecutionContext snapshots per step.
Never:   Must not call Bedrock directly. Checkpoint data is stored in-memory
         for the MVP; persistence to CockroachDB is a Phase B enhancement.
Ref:     WORKFLOW_ENGINE.md §7.
"""

from __future__ import annotations

import logging
import os
import pickle
from pathlib import Path
from typing import Any

from workflow_engine.context import ExecutionContext

logger = logging.getLogger(__name__)

_CHECKPOINT_DIR = Path(os.path.join(os.path.dirname(__file__), "..", "tmp", "checkpoints"))


def save_checkpoint(run_id: str, step_id: str, context: ExecutionContext) -> str:
    """
    Persist an ExecutionContext snapshot for a given run and step.

    Returns the checkpoint file path.
    """
    _CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    checkpoint_path = _CHECKPOINT_DIR / f"{run_id}_{step_id}.ckpt"

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
        with open(checkpoint_path, "wb") as f:
            pickle.dump(data, f)
        logger.info("checkpoint_store: saved | run=%s step=%s path=%s", run_id, step_id, checkpoint_path)
    except Exception as exc:
        logger.error("checkpoint_store: failed to save | run=%s step=%s error=%s", run_id, step_id, exc)

    return str(checkpoint_path)


def load_checkpoint(run_id: str, step_id: str) -> ExecutionContext | None:
    """
    Restore an ExecutionContext from a checkpoint.

    Returns None if no checkpoint exists.
    """
    checkpoint_path = _CHECKPOINT_DIR / f"{run_id}_{step_id}.ckpt"
    if not checkpoint_path.exists():
        return None

    try:
        with open(checkpoint_path, "rb") as f:
            data = pickle.load(f)  # noqa: S301
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
        logger.error("checkpoint_store: failed to load | run=%s step=%s error=%s", run_id, step_id, exc)
        return None


def list_checkpoints(run_id: str) -> list[str]:
    """List all checkpoints for a given run."""
    checkpoints = sorted(_CHECKPOINT_DIR.glob(f"{run_id}_*.ckpt"))
    return [str(p) for p in checkpoints]


def cleanup_checkpoints(run_id: str) -> None:
    """Remove all checkpoints for a given run."""
    for checkpoint in _CHECKPOINT_DIR.glob(f"{run_id}_*.ckpt"):
        try:
            checkpoint.unlink()
        except OSError:
            logger.warning("checkpoint_store: failed to delete %s", checkpoint)
