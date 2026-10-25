"""workflow_engine/context.py — AUTOMATA Workflow Engine: execution context.

Owns:    ExecutionContext accumulation, redaction hooks, serialization.
Never:   Must not call Bedrock or CockroachDB directly.
Ref:     WORKFLOW_ENGINE.md §3, §6.
"""

from __future__ import annotations

import logging
from typing import Any

from memory.capture import redact_secrets
from workflow_engine.schema import ExecutionContext as _ExecutionContext

# Re-export ExecutionContext for consumers that import from context
ExecutionContext = _ExecutionContext

logger = logging.getLogger(__name__)


def check_privacy_guardrail(content: str) -> bool:
    """
    Check if content contains secrets, code, or private URLs
    that should trigger escalation (per FEATURES_PHASE.md §5).

    Returns True if content is flagged (contains potential secrets).
    """
    if not content:
        return False
    secret_patterns = [
        "ghp_",
        "akia",
        "sk-",
        "key=",
        "token=",
        "password=",
        "bearer ",
        "api_key",
        "secret",
        "credential",
    ]
    lowered = content.lower()
    return any(pattern in lowered for pattern in secret_patterns)


def redact_content(content: str) -> tuple[str, bool]:
    """
    Redact secrets from content. Returns (redacted_content, was_redacted).
    """
    redacted = redact_secrets(content)
    was_redacted = redacted != content
    if was_redacted:
        logger.info("context: redacted sensitive workflow content")
    return redacted, was_redacted


def redact_inputs(inputs: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Redact string values without changing the shape of tool inputs."""

    changed = False

    def _redact(value: Any) -> Any:
        nonlocal changed
        if isinstance(value, str):
            redacted, was_redacted = redact_content(value)
            changed = changed or was_redacted
            return redacted
        if isinstance(value, dict):
            return {key: _redact(item) for key, item in value.items()}
        if isinstance(value, list):
            return [_redact(item) for item in value]
        return value

    return _redact(inputs), changed


def resolve_template(template: str, context: dict[str, Any]) -> str:
    """
    Resolve a templated string like '{{ steps.read_diff.output.changed_files }}'
    against the ExecutionContext.

    Supports:
    - {{ inputs.<key> }}
    - {{ steps.<step_id>.output.<field> }}
    """
    import re

    result = template

    # Resolve {{ inputs.<key> }}
    for match in re.finditer(r"\{\{\s*inputs\.(\w+)\s*\}\}", template):
        key = match.group(1)
        value = str(context.get("inputs", {}).get(key, ""))
        result = result.replace(match.group(0), value)

    # Resolve {{ steps.<step_id>.output.<field> }}
    for match in re.finditer(r"\{\{\s*steps\.(\w+)\.output\.(\w+)\s*\}\}", template):
        step_id = match.group(1)
        field = match.group(2)
        step_output = context.get("step_outputs", {}).get(step_id, {})
        value = str(step_output.get(field, ""))
        result = result.replace(match.group(0), value)

    return result
