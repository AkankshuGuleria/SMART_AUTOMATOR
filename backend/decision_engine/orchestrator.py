"""
decision_engine/orchestrator.py — AUTOMATA Brain: Agent Orchestration Loop.

Owns:    The plan → act → observe → reflect loop that turns a goal into a
         sequence of real tool calls. This is the core differentiator — without
         it, AUTOMATA is a grounded chatbot, not an agent.
Never:   Must not bypass the Agent Loop. Must not call Bedrock directly
         (→ ai/bedrock_client.py). Must not write to CockroachDB directly
         (→ db/client.py). Must not import action implementations directly
         — it goes through the tool registry.
Ref:     ARCHITECTURE.md §2.3, PROJECT.md §9, SKILLS.md §5 (Retrieval Quality),
         SKILLS.md §10 (Mistake Memory).
"""

from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import dataclass, field
from typing import Any

from decision_engine.tools import execute_tool, get_tool

logger = logging.getLogger(__name__)

# Hard caps — prevent runaway loops from burning budget.
MAX_ITERATIONS: int = 15
MAX_TOOL_CALLS: int = 10


# ─── Result types ─────────────────────────────────────────────────────────────


@dataclass
class StepResult:
    step_index: int
    tool: str
    params: dict[str, Any]
    observation: dict[str, Any]
    success: bool
    plan_snapshot: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class OrchestratorResult:
    goal: str
    success: bool
    steps: list[StepResult] = field(default_factory=list)
    final_response: str = ""
    stopped_reason: str = ""
    needs_approval: bool = False
    pending_step: dict[str, Any] | None = None
    decision_log_id: str | None = None


# ─── Main entry point ─────────────────────────────────────────────────────────


def run_orchestrator(
    goal: str,
    project_id: str | None = None,
    context: dict[str, Any] | None = None,
) -> OrchestratorResult:
    """
    Execute the agent orchestration loop for *goal*.

    1. RECEIVE the goal.
    2. PLAN — retrieve memory + past mistakes, ask LLM for a structured plan.
    3. ACT — execute the next step's tool call.
    4. OBSERVE — capture the real result.
    5. REFLECT — feed observation back to the LLM; decide continue / retry /
       revise / stop.
    6. LOOP until the goal is met, the plan is exhausted, user approval is
       required, or a hard ceiling is hit.
    7. RECORD — write the outcome to `decision_log`; on failure, also write
       to `mistake_log`.
    """
    context = context or {}
    result = OrchestratorResult(goal=goal, success=False)

    iteration = 0
    tool_calls = 0
    plan_steps: list[dict[str, Any]] = []
    step_index = 0
    all_observations: list[dict[str, Any]] = []

    # Log the start of the orchestrator run.
    decision_id = _record_decision(
        project_id,
        f"Orchestrator started: {goal}",
        f"Context: {json.dumps(context, default=str)[:500]}",
    )
    result.decision_log_id = decision_id

    while iteration < MAX_ITERATIONS and tool_calls < MAX_TOOL_CALLS:
        iteration += 1

        # ── PLAN ───────────────────────────────────────────────────────────────
        if not plan_steps:
            memories = _retrieve_memories(goal, project_id)
            mistakes = _retrieve_mistakes(project_id, goal)
            available_tools = _get_filtered_tool_descriptions()
            plan_text = _call_planner(goal, memories, mistakes, available_tools, context)
            plan_steps = _parse_plan(plan_text)

            if not plan_steps:
                result.stopped_reason = "could_not_generate_plan"
                result.final_response = _fallback_answer(goal, memories)
                break

            # Check if any step explicitly asks for user input.
            ask_user = plan_steps[0].get("ask_user") if plan_steps else None
            if ask_user:
                result.stopped_reason = "needs_user_input"
                result.needs_approval = True
                result.final_response = str(ask_user)
                break

            # Check if any step requires approval that hasn't been pre-approved.
            for step in plan_steps:
                tool = get_tool(step.get("tool", ""))
                if tool and tool.requires_approval:
                    result.stopped_reason = f"user_approval_needed:{tool.name}"
                    result.needs_approval = True
                    result.pending_step = step
                    result.final_response = (
                        f"I need your approval to {step.get('reasoning', 'run ' + tool.name)}. "
                        f"Risk: {tool.risk}. {f'Undo hint: {tool.description}' if tool.reversible else 'This may be hard to undo.'}"
                    )
                    break
            if result.needs_approval:
                break

        # ── EXHAUSTED? ─────────────────────────────────────────────────────────
        if step_index >= len(plan_steps):
            result.success = True
            result.stopped_reason = "plan_exhausted"
            result.final_response = _build_success_response(goal, result.steps)
            break

        # ── ACT ─────────────────────────────────────────────────────────────────
        step = plan_steps[step_index]
        tool_name = str(step.get("tool", "")).strip()
        params = step.get("params", {}) or {}

        if not tool_name:
            observation = {"success": False, "error": "step has no tool name"}
        else:
            observation = execute_tool(tool_name, params)
        tool_calls += 1

        step_result = StepResult(
            step_index=step_index,
            tool=tool_name,
            params=params,
            observation=observation,
            success=observation.get("success", False),
            plan_snapshot=[s.copy() for s in plan_steps],
        )
        result.steps.append(step_result)
        all_observations.append(observation)

        _record_decision(
            project_id,
            f"Step {step_index + 1}/{len(plan_steps)}: {tool_name}",
            f"Params: {json.dumps(params, default=str)[:300]}. "
            f"Observation success={observation.get('success')}",
        )

        # ── REFLECT ─────────────────────────────────────────────────────────────
        reflection_text = _call_reflector(goal, plan_steps, step_index, observation, context)
        reflection = _parse_reflection(reflection_text)
        action = str(reflection.get("action", "continue")).lower()

        if action == "retry":
            step["params"] = reflection.get("params", params)
            # stay on the same step_index
        elif action == "revise":
            revised = reflection.get("revised_plan", {})
            if isinstance(revised, dict):
                plan_steps = revised.get("steps", [])
            elif isinstance(revised, list):
                plan_steps = revised
            else:
                plan_steps = []
            step_index = 0
            all_observations.clear()
        elif action == "stop":
            result.success = bool(reflection.get("success", observation.get("success", False)))
            result.stopped_reason = "reflector_stop"
            result.final_response = str(reflection.get("response") or "")
            break
        else:  # continue
            step_index += 1

    # ── CEILING? ──────────────────────────────────────────────────────────────
    if iteration >= MAX_ITERATIONS:
        result.stopped_reason = "max_iterations_reached"
        result.final_response = (
            f"Stopped after {MAX_ITERATIONS} planning iterations. "
            f"Goal: {goal}. Completed {len(result.steps)} step(s)."
        )
    elif tool_calls >= MAX_TOOL_CALLS:
        result.stopped_reason = "max_tool_calls_reached"
        result.final_response = (
            f"Stopped after {MAX_TOOL_CALLS} tool calls. "
            f"Goal: {goal}. Completed {len(result.steps)} step(s)."
        )

    # ── RECORD OUTCOME ────────────────────────────────────────────────────────
    outcome = "succeeded" if result.success else "failed"
    _record_decision(
        project_id,
        f"Orchestrator {outcome}: {goal}",
        f"Steps: {len(result.steps)}. Stopped: {result.stopped_reason}.",
    )
    if not result.success:
        _record_mistake(
            project_id,
            f"Orchestrator could not complete goal: {goal}",
            f"Stopped reason: {result.stopped_reason}",
            "Review plan generation, missing tools, or unhandled observation.",
        )

    return result


# ─── Context retrieval ────────────────────────────────────────────────────────


def _retrieve_memories(goal: str, project_id: str | None) -> list[dict[str, Any]]:
    """Pull relevant memories from vector search + recent retrieval."""
    memories: list[dict[str, Any]] = []
    if not project_id:
        return memories
    try:
        from memory.retrieval import retrieve_by_vector, retrieve_recent

        vector_tables = ["commits", "todos", "architecture_notes", "decision_log", "mistake_log"]
        memories = retrieve_by_vector(goal, vector_tables, project_id=project_id, top_k=8)
        if not memories:
            for table in ("commits", "todos", "file_edits", "architecture_notes"):
                memories.extend(retrieve_recent(project_id, table, limit=3))
    except Exception as exc:
        logger.warning("_retrieve_memories failed — %s", exc)
    return memories


def _retrieve_mistakes(project_id: str | None, goal: str) -> list[dict[str, Any]]:
    """Pull recent mistakes for the project so the planner can avoid them."""
    mistakes: list[dict[str, Any]] = []
    if not project_id:
        return mistakes
    try:
        from db.client import get_mistakes

        mistakes = get_mistakes(project_id) or []
    except Exception as exc:
        logger.warning("_retrieve_mistakes failed — %s", exc)
    return mistakes


def _get_filtered_tool_descriptions() -> list[dict[str, Any]]:
    """Return descriptions for tools whose config requirements are met."""
    try:
        from decision_engine.tools import filter_tools_by_config

        tools = filter_tools_by_config()
    except Exception:
        from decision_engine.tools import get_available_tools

        tools = get_available_tools()
    return [
        {
            "name": t.name,
            "description": t.description,
            "input_schema": t.input_schema,
            "risk": t.risk,
            "requires_approval": t.requires_approval,
        }
        for t in tools
    ]


# ─── LLM planning ─────────────────────────────────────────────────────────────

_PLANNER_SYSTEM_PROMPT = (
    "You are AUTOMATA's Planner. Your job is to create a concise, ordered plan of "
    "tool calls to achieve the developer's goal using ONLY the tools listed below. "
    "Never invent tools. Never claim to have done something without making the tool call. "
    "If the goal is already achievable from the provided memory alone, respond with "
    '{"steps": [], "ask_user": null} and explain in reasoning.'
)


def _call_planner(
    goal: str,
    memories: list[dict[str, Any]],
    mistakes: list[dict[str, Any]],
    available_tools: list[dict[str, Any]],
    context: dict[str, Any],
) -> str | None:
    """Ask the reasoning model for a structured plan. Returns raw text or None."""
    memory_summary = (
        "\n".join(f"- [{m.get('table', 'unknown')}] {m.get('content', '')}" for m in memories[:12])
        or "(no relevant memory found)"
    )

    mistake_summary = (
        "\n".join(f"- {m.get('symptom', '')}: {m.get('fix', '')}" for m in mistakes[:5])
        or "(no recorded mistakes)"
    )

    tools_json = json.dumps(available_tools, default=str, indent=2)[:4000]

    user_message = (
        f"Goal: {goal}\n\n"
        f"Context: {json.dumps(context, default=str)[:1000]}\n\n"
        f"Retrieved memories:\n{memory_summary}\n\n"
        f"Past mistakes to avoid:\n{mistake_summary}\n\n"
        f"Available tools:\n{tools_json}\n\n"
        "Return a JSON plan with this exact shape:\n"
        '{"steps": [{"tool": "tool_name", "params": {"key": "value"}, "reasoning": "why", '
        '"ask_user": null or "question"}], "ask_user": null}\n'
        "Rules:\n"
        "- Use ONLY listed tools.\n"
        "- If you need human input, set the top-level 'ask_user' string.\n"
        "- Do not include markdown fences or extra prose.\n"
        "- Keep steps minimal — prefer fewer, higher-impact steps.\n"
    )
    return _invoke_structured(_PLANNER_SYSTEM_PROMPT, user_message)


# ─── LLM reflection ───────────────────────────────────────────────────────────

_REFLECTOR_SYSTEM_PROMPT = (
    "You are AUTOMATA's Reflector. Given the goal, plan, and observation from the "
    "last step, decide what the orchestrator should do next. Return ONLY valid JSON."
)


def _call_reflector(
    goal: str,
    plan_steps: list[dict[str, Any]],
    step_index: int,
    observation: dict[str, Any],
    context: dict[str, Any],
) -> str | None:
    """Ask the reasoning model how to proceed after an observation."""
    remaining = plan_steps[step_index + 1 : step_index + 4]  # show a window
    last_step = plan_steps[step_index] if step_index < len(plan_steps) else {}

    user_message = (
        f"Goal: {goal}\n\n"
        f"Context: {json.dumps(context, default=str)[:500]}\n\n"
        f"Last executed step:\n"
        f"- tool: {last_step.get('tool')}\n"
        f"- params: {json.dumps(last_step.get('params', {}), default=str)[:500]}\n"
        f"- reasoning: {last_step.get('reasoning', '')}\n\n"
        f"Observation:\n"
        f"- success: {observation.get('success')}\n"
        f"- output: {str(observation.get('result') or observation.get('output') or observation.get('error') or '')[:1200]}\n\n"
        f"Remaining plan (next few steps):\n{json.dumps(remaining, default=str, indent=2)[:1500]}\n\n"
        "Return JSON:\n"
        '{"action": "continue|retry|revise|stop", "reason": "...", '
        '"params": {"modified": "params"}, '
        '"revised_plan": {"steps": [...]}, '
        '"response": "final message if stopping"}\n'
        "Rules:\n"
        '- "continue": proceed to next step.\n'
        '- "retry": retry current step; include modified params.\n'
        '- "revise": abandon remaining plan; include a full revised_plan.\n'
        '- "stop": finish early; set success=true/false and a response.\n'
    )
    return _invoke_structured(_REFLECTOR_SYSTEM_PROMPT, user_message)


# ─── JSON helper for LLM calls ───────────────────────────────────────────────

# Hard wall-clock timeout for a single LLM reasoning call (seconds).
# Prevents a slow or hung provider from blocking the orchestrator indefinitely.
_LLM_CALL_TIMEOUT: float = 20.0


def _invoke_structured(system_prompt: str, user_message: str, retries: int = 2) -> str | None:
    """Call the reasoning model, retrying if it does not return JSON.

    Each attempt is wrapped in a daemon thread with a hard timeout so a
    slow/unreachable provider cannot block the orchestrator loop.
    """
    from ai.bedrock_client import invoke_reasoning

    for attempt in range(retries):
        text = _call_with_timeout(
            invoke_reasoning,
            system_prompt=system_prompt,
            user_message=user_message,
            retrieved_memories=None,
        )
        if not text:
            logger.warning("_invoke_structured: empty response on attempt %d", attempt + 1)
            continue
        parsed = _extract_json(text)
        if parsed is not None:
            return text
        logger.warning(
            "_invoke_structured: parse failed on attempt %d — %s", attempt + 1, text[:200]
        )
        user_message = (
            "The previous response could not be parsed as JSON. "
            "Return ONLY valid JSON, no markdown fences, no extra text.\n\n" + user_message
        )
    return None


def _call_with_timeout(fn, **kwargs) -> Any:
    """Run *fn* in a daemon thread and return its result, or None on timeout."""
    result_box: dict[str, Any] = {}
    done = threading.Event()

    def _target() -> None:
        try:
            result_box["value"] = fn(**kwargs)
        except Exception as exc:
            result_box["error"] = exc
        finally:
            done.set()

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    if not done.wait(timeout=_LLM_CALL_TIMEOUT):
        logger.warning(
            "_call_with_timeout: %s timed out after %.1fs", fn.__name__, _LLM_CALL_TIMEOUT
        )
        return None
    if "error" in result_box:
        logger.warning("_call_with_timeout: %s raised — %s", fn.__name__, result_box["error"])
        return None
    return result_box.get("value")


def _extract_json(text: str) -> dict[str, Any] | None:
    """Extract the first valid JSON object from *text*, tolerating markdown
    fences, leading prose, and long/truncated parser outputs."""
    if not text:
        return None
    stripped = re.sub(r"```(?:json)?\s*", "", text)
    stripped = re.sub(r"\s*```", "", stripped)

    search_from = 0
    while True:
        start = stripped.find("{", search_from)
        if start == -1:
            return None

        depth = 0
        in_string = False
        escape_next = False

        for i in range(start, len(stripped)):
            char = stripped[i]
            if escape_next:
                escape_next = False
                continue
            if char == "\\" and in_string:
                escape_next = True
                continue
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    candidate = stripped[start : i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        search_from = i + 1
                        break
        else:
            return None


def _parse_plan(text: str | None) -> list[dict[str, Any]]:
    """Parse the LLM plan text into a list of step dicts."""
    if not text:
        return []
    parsed = _extract_json(text)
    if not isinstance(parsed, dict):
        return []
    steps = parsed.get("steps", [])
    if not isinstance(steps, list):
        return []
    normalized: list[dict[str, Any]] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        tool_name = str(step.get("tool", "")).strip()
        if not tool_name:
            continue
        tool = get_tool(tool_name) if tool_name else None
        if tool is None:
            logger.warning("_parse_plan: LLM proposed unknown tool '%s' — skipping", tool_name)
            continue
        normalized.append(
            {
                "tool": tool_name,
                "params": step.get("params") or {},
                "reasoning": str(step.get("reasoning", ""))[:500],
            }
        )
    return normalized


def _parse_reflection(text: str | None) -> dict[str, Any]:
    """Parse reflector output into an action dict."""
    if not text:
        return {"action": "stop", "success": False, "response": "Reasoning unavailable."}
    parsed = _extract_json(text)
    if not isinstance(parsed, dict):
        return {"action": "stop", "success": False, "response": "Could not parse reflection."}
    return parsed


# ─── Response builders ────────────────────────────────────────────────────────


def _build_success_response(goal: str, steps: list[StepResult]) -> str:
    """Build a concise success message from executed steps."""
    if not steps:
        return f"Goal reached: {goal}"
    parts = [f"Goal reached: {goal}"]
    for i, s in enumerate(steps, 1):
        obs = s.observation
        if s.success:
            parts.append(f"{i}. {s.tool} — ok")
        else:
            err_msg = str(obs.get("error") or obs.get("stderr") or "unknown")[:120]
            parts.append(f"{i}. {s.tool} — failed: {err_msg}")
    return "\n".join(parts)


def _fallback_answer(goal: str, memories: list[dict[str, Any]]) -> str:
    """When planning fails, return raw retrieved context without fake reasoning."""
    if not memories:
        return "I could not generate a plan, and no relevant memory was found."
    bullets = "\n".join(
        f"- [{m.get('table', 'memory')}] {m.get('content', '')}"
        for m in memories[:8]
        if m.get("content")
    )
    return (
        f"Planning is currently unavailable. Here is the most relevant memory I found:\n\n{bullets}"
    )


# ─── Decision / mistake logging ───────────────────────────────────────────────


def _record_decision(project_id: str | None, decision: str, rationale: str) -> str | None:
    """Insert a decision_log row with embedding. Returns the new decision UUID or None."""
    try:
        from agent_actions import record_agent_decision

        if project_id:
            record_agent_decision(project_id, decision, rationale)
        from db.client import insert_decision

        return insert_decision(project_id, decision, rationale)
    except Exception as exc:
        logger.warning("_record_decision failed — %s", exc)
        return None


def _record_mistake(
    project_id: str | None,
    symptom: str,
    root_cause: str,
    fix: str,
) -> str | None:
    """Insert a mistake_log row with embedding. Returns the new mistake UUID or None."""
    try:
        from agent_actions import record_agent_mistake

        if project_id:
            record_agent_mistake(project_id, symptom, root_cause, fix)
        from db.client import insert_mistake

        return insert_mistake(project_id, symptom, root_cause, fix, module="decision_engine")
    except Exception as exc:
        logger.warning("_record_mistake failed — %s", exc)
        return None
