"""workflow_engine/registry.py — AUTOMATA Workflow Engine: definition registry.

Owns:    Loading, validating, and listing workflow definitions from YAML/JSON files.
Never:   Must not call Bedrock or CockroachDB directly.
Ref:     WORKFLOW_ENGINE.md §4, §9.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from workflow_engine.schema import StepDefinition, WorkflowDefinition

logger = logging.getLogger(__name__)

_DEFINITIONS_DIR = Path(__file__).parent / "definitions"


def load_definition(path: str) -> WorkflowDefinition:
    """Load a workflow definition from a YAML or JSON file."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Workflow definition not found: {path}")

    with open(file_path, encoding="utf-8") as f:
        if path.endswith(".json"):
            data = json.load(f)
        else:
            data = yaml.safe_load(f)

    return _parse_definition(data)


def load_all_definitions() -> list[WorkflowDefinition]:
    """Load all workflow definitions from the definitions directory."""
    definitions: list[WorkflowDefinition] = []
    if not _DEFINITIONS_DIR.exists():
        logger.warning("No definitions directory found at %s", _DEFINITIONS_DIR)
        return definitions

    for file_path in sorted(_DEFINITIONS_DIR.iterdir()):
        if file_path.suffix in (".yaml", ".yml", ".json"):
            try:
                definition = load_definition(str(file_path))
                definitions.append(definition)
                logger.info("Loaded workflow definition: %s v%d", definition.id, definition.version)
            except Exception as exc:
                logger.error("Failed to load definition %s: %s", file_path.name, exc)

    return definitions


def get_definition(workflow_id: str) -> WorkflowDefinition | None:
    """Get a specific workflow definition by ID."""
    for definition in load_all_definitions():
        if definition.id == workflow_id:
            return definition
    return None


def list_definitions() -> list[dict[str, Any]]:
    """List all available workflow definitions (metadata only)."""
    return [
        {
            "id": d.id,
            "name": d.name,
            "description": d.description,
            "version": d.version,
            "step_count": len(d.steps),
        }
        for d in load_all_definitions()
    ]


def _parse_definition(data: dict[str, Any]) -> WorkflowDefinition:
    """Parse raw YAML/JSON data into a WorkflowDefinition."""
    steps = [
        StepDefinition(
            id=s.get("id", ""),
            tool=s.get("tool", ""),
            inputs=s.get("inputs", {}),
            on_error=s.get("on_error", "abort"),
        )
        for s in data.get("steps", [])
    ]

    return WorkflowDefinition(
        id=data.get("id", ""),
        name=data.get("name", ""),
        description=data.get("description", ""),
        version=int(data.get("version", 1)),
        inputs=data.get("inputs", []),
        steps=steps,
        outputs=data.get("outputs", []),
    )
