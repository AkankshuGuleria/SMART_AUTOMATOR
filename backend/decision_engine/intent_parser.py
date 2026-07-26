"""
decision_engine/intent_parser.py — AUTOMATA Intent Parser.

Owns:    Mapping natural-language chat messages to structured intents and
         extracting required parameters for downstream execution.
Never:   Does not execute actions directly; delegates to planner/automation.
Ref:     ARCHITECTURE.md §"Decision Engine", PROJECT.md §"Chat-driven capabilities"
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class IntentType(str, Enum):
    OPEN_PROJECT = "open_project"
    RESUME_PROJECT = "resume_project"
    MORNING_BRIEF = "morning_brief"
    RUN_TESTS = "run_tests"
    RUN_COMMAND = "run_command"
    CREATE_PROJECT = "create_project"
    DEBUG_FAILURE = "debug_failure"
    EXPLAIN_REPO = "explain_repo"
    GENERATE_COMMIT_MESSAGE = "generate_commit_message"
    FIND_AUTH = "find_auth"
    CONTINUE_WORK = "continue_work"
    START_DEV_ENV = "start_dev_env"
    STOP_DEV_ENV = "stop_dev_env"
    GENERAL_CHAT = "general_chat"
    UNKNOWN = "unknown"


@dataclass
class ParsedIntent:
    intent: IntentType
    confidence: float
    project_id: Optional[str] = None
    params: dict[str, str] | None = None
    raw: str = ""


class IntentParser:
    """Lightweight rule-based intent parser for MVP chat routing."""

    _patterns = [
        (IntentType.OPEN_PROJECT, re.compile(r"\b(?:open|switch to|go to)\s+(?:project\s+)?(.+)", re.IGNORECASE)),
        (IntentType.RESUME_PROJECT, re.compile(r"\b(?:resume|continue|restore|pick up)\s+(?:where I left off|work|project)?", re.IGNORECASE)),
        (IntentType.MORNING_BRIEF, re.compile(r"\b(?:morning\s+brief|good\s+morning|what did I do|yesterday|catch\s+me\s+up)", re.IGNORECASE)),
        (IntentType.RUN_TESTS, re.compile(r"\b(?:run\s+tests?|execute\s+tests?|pytest|npm\s+test|dotnet\s+test)\b", re.IGNORECASE)),
        (IntentType.DEBUG_FAILURE, re.compile(r"\b(?:why is this failing|fix\s+this|debug|failing\s+test|error)\b", re.IGNORECASE)),
        (IntentType.CREATE_PROJECT, re.compile(r"\b(?:create|new)\s+(?:a\s+)?project\s+(?:called\s+|named\s+)?(.+)", re.IGNORECASE)),
        (IntentType.START_DEV_ENV, re.compile(r"\b(?:start|launch|run)\s+(?:dev\s+)?(?:server|environment|env)\b", re.IGNORECASE)),
        (IntentType.STOP_DEV_ENV, re.compile(r"\b(?:stop|kill|shutdown)\s+(?:dev\s+)?(?:server|environment|env)\b", re.IGNORECASE)),
        (IntentType.EXPLAIN_REPO, re.compile(r"\b(?:explain|describe|summarize)\s+(?:the\s+)?(?:repo|repository|project|codebase)\b", re.IGNORECASE)),
        (IntentType.GENERATE_COMMIT_MESSAGE, re.compile(r"\b(?:generate|write|create)\s+(?:a\s+)?commit\s+message\b", re.IGNORECASE)),
        (IntentType.FIND_AUTH, re.compile(r"\b(?:find|locate|where is)\s+(?:auth|authentication|login|jwt|token)\b", re.IGNORECASE)),
        (IntentType.CONTINUE_WORK, re.compile(r"\b(?:continue|next\s+task|what('s| is) next|suggest\s+task)\b", re.IGNORECASE)),
    ]

    def parse(self, message: str, active_project_id: Optional[str] = None) -> ParsedIntent:
        text = message.strip()
        lowered = text.lower()

        for intent, pattern in self._patterns:
            m = pattern.search(text)
            if m:
                project_hint = m.group(1) if m.groups() else None
                confidence = 0.9 if intent not in {IntentType.RESUME_PROJECT, IntentType.MORNING_BRIEF, IntentType.GENERAL_CHAT} else 0.7
                return ParsedIntent(
                    intent=intent,
                    confidence=confidence,
                    project_id=active_project_id,
                    params={"raw": text, "project_hint": project_hint or ""},
                    raw=text,
                )

        if lowered in {"help", "hi", "hello", "what can you do"}:
            return ParsedIntent(intent=IntentType.GENERAL_CHAT, confidence=0.6, raw=text)

        return ParsedIntent(intent=IntentType.UNKNOWN, confidence=0.0, raw=text)
