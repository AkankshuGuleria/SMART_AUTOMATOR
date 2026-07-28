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
    OPEN_APP = "open_app"
    OPEN_BROWSER = "open_browser"
    SYSTEM_COMMAND = "system_command"
    QUERY_MEMORY = "query_memory"
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
    """Rule-based intent parser for MVP chat routing.

    Patterns are ordered by specificity — more-specific patterns must appear
    before broader catch-alls that share keywords.
    """

    # (IntentType, compiled_pattern)
    _patterns = [
        # ── App / browser opening ──────────────────────────────────────────────
        (
            IntentType.OPEN_BROWSER,
            re.compile(
                r"\b(?:open|run|go to|navigate to|launch|visit)\s+"
                r"(?:browser|chrome|firefox|edge|safari|web|"
                r"chatgpt|gpt|openai|claude|github|google|youtube|"
                r"https?://\S+|www\.\S+)",
                re.IGNORECASE,
            ),
        ),
        (
            IntentType.OPEN_APP,
            re.compile(
                r"\b(?:open|run|launch|start)\s+"
                r"(?:app\s+)?(?:vscode|vs\s*code|notepad|calculator|"
                r"explorer|file\s*explorer|terminal|cmd|powershell|"
                r"slack|discord|spotify|figma|postman|git\s*bash|"
                r"task\s*manager|settings)\b",
                re.IGNORECASE,
            ),
        ),
        (
            IntentType.OPEN_APP,
            re.compile(
                r"\b(?:open|run|launch|start)\s+(.+?)(?:\s+app(?:lication)?)?$",
                re.IGNORECASE,
            ),
        ),
        # ── Project operations ─────────────────────────────────────────────────
        (
            IntentType.OPEN_PROJECT,
            re.compile(
                r"\b(?:open|switch to|go to)\s+(?:project\s+)?(.+)",
                re.IGNORECASE,
            ),
        ),
        (
            IntentType.RESUME_PROJECT,
            re.compile(
                r"\b(?:resume|continue|restore|pick up)\s+(?:where I left off|work|project)?",
                re.IGNORECASE,
            ),
        ),
        # ── Morning brief / context ────────────────────────────────────────────
        (
            IntentType.MORNING_BRIEF,
            re.compile(
                r"\b(?:morning\s+brief|good\s+morning|what did I do|"
                r"yesterday|catch\s+me\s+up|what('s| was) I working on|"
                r"recap|remind me)",
                re.IGNORECASE,
            ),
        ),
        # ── Tests ─────────────────────────────────────────────────────────────
        (
            IntentType.RUN_TESTS,
            re.compile(
                r"\b(?:run\s+tests?|execute\s+tests?|pytest|npm\s+test|"
                r"dotnet\s+test|cargo\s+test|run\s+unit\s+tests?)\b",
                re.IGNORECASE,
            ),
        ),
        # ── Debugging ─────────────────────────────────────────────────────────
        (
            IntentType.DEBUG_FAILURE,
            re.compile(
                r"\b(?:why is this failing|fix\s+this|debug|failing\s+test|"
                r"broken|not working|crash|exception)\b",
                re.IGNORECASE,
            ),
        ),
        # ── Project creation ───────────────────────────────────────────────────
        (
            IntentType.CREATE_PROJECT,
            re.compile(
                r"\b(?:create|new)\s+(?:a\s+)?project\s+(?:called\s+|named\s+)?(.+)",
                re.IGNORECASE,
            ),
        ),
        # ── Dev environment ────────────────────────────────────────────────────
        (
            IntentType.START_DEV_ENV,
            re.compile(
                r"\b(?:start|launch|run)\s+(?:dev\s+)?(?:server|environment|env)\b",
                re.IGNORECASE,
            ),
        ),
        (
            IntentType.STOP_DEV_ENV,
            re.compile(
                r"\b(?:stop|kill|shutdown)\s+(?:dev\s+)?(?:server|environment|env)\b",
                re.IGNORECASE,
            ),
        ),
        # ── Repository ────────────────────────────────────────────────────────
        (
            IntentType.EXPLAIN_REPO,
            re.compile(
                r"\b(?:explain|describe|summarize|what is this|"
                r"tell me about)\s+(?:the\s+)?(?:repo|repository|project|codebase|code)\b",
                re.IGNORECASE,
            ),
        ),
        # ── Commit message ─────────────────────────────────────────────────────
        (
            IntentType.GENERATE_COMMIT_MESSAGE,
            re.compile(
                r"\b(?:generate|write|create)\s+(?:a\s+)?commit\s+message\b",
                re.IGNORECASE,
            ),
        ),
        # ── Auth code search ───────────────────────────────────────────────────
        (
            IntentType.FIND_AUTH,
            re.compile(
                r"\b(?:find|locate|where is|show me)\s+(?:auth|authentication|login|jwt|token)\b",
                re.IGNORECASE,
            ),
        ),
        # ── Continue / next task ───────────────────────────────────────────────
        (
            IntentType.CONTINUE_WORK,
            re.compile(
                r"\b(?:continue|next\s+task|what('s| is) next|"
                r"suggest\s+(?:a\s+)?task|what should I (?:do|work on)|"
                r"pick up where)\b",
                re.IGNORECASE,
            ),
        ),
        # ── Arbitrary command ──────────────────────────────────────────────────
        (
            IntentType.RUN_COMMAND,
            re.compile(
                r"^(?:run|execute|do)\s+(?:command\s+)?['\"`]?(.+)['\"`]?$",
                re.IGNORECASE,
            ),
        ),
        # ── System commands (install, setup, env vars) ──────────────
        (
            IntentType.SYSTEM_COMMAND,
            re.compile(
                r"\b(?:install|setup|configure|set up|add |"
                r"set\s+(?:environment|env|path|variable)|"
                r"download|uninstall|remove\s+software|"
                r"update\s+(?:system|software|package)|"
                r"upgrade|pip\s+install|npm\s+install|"
                r"apt\s+install|winget\s+install|choco\s+install|"
                r"java\s+install|jdk\s+install|sdk\s+install|"
                r"setup\s+(?:dev\s+)?env(?:ironment)?|dev\s+env\s+setup|"
                r"set\s+java|set\s+path|set\s+env)\b",
                re.IGNORECASE,
            ),
        ),

        # ── Memory query (broad — keep near bottom) ────────────────────────────
        (
            IntentType.QUERY_MEMORY,
            re.compile(
                r"\b(?:what|when|where|how|who|find|show|tell me|list|"
                r"search for|look up)\b",
                re.IGNORECASE,
            ),
        ),
    ]

    def parse(self, message: str, active_project_id: Optional[str] = None) -> ParsedIntent:
        text = message.strip()
        lowered = text.lower()

        for intent, pattern in self._patterns:
            m = pattern.search(text)
            if m:
                # Extract the first capture group as a hint if present
                project_hint = None
                if m.groups():
                    try:
                        project_hint = m.group(1)
                    except IndexError:
                        pass

                # For open_browser / open_app, extract the full target from the raw message
                target = project_hint or ""
                if intent in (IntentType.OPEN_BROWSER, IntentType.OPEN_APP):
                    # Use the full raw message as the target so agent_actions can parse it
                    target = text

                # Confidence is lower for broad patterns near the bottom
                broad_intents = {
                    IntentType.RESUME_PROJECT,
                    IntentType.MORNING_BRIEF,
                    IntentType.GENERAL_CHAT,
                    IntentType.QUERY_MEMORY,
                    IntentType.OPEN_APP,
                }
                confidence = 0.7 if intent in broad_intents else 0.9

                return ParsedIntent(
                    intent=intent,
                    confidence=confidence,
                    project_id=active_project_id,
                    params={
                        "raw": text,
                        "project_hint": project_hint or "",
                        "target": target,
                    },
                    raw=text,
                )

        if lowered in {"help", "hi", "hello", "what can you do", "hey"}:
            return ParsedIntent(intent=IntentType.GENERAL_CHAT, confidence=0.6, raw=text)

        return ParsedIntent(intent=IntentType.UNKNOWN, confidence=0.0, raw=text)
