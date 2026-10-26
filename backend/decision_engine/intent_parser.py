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
    GIT_LOG = "git_log"
    OPEN_APP = "open_app"
    OPEN_BROWSER = "open_browser"
    SYSTEM_COMMAND = "system_command"
    QUERY_MEMORY = "query_memory"
    GENERAL_CHAT = "general_chat"
    # Cross-app control intents
    COPY_TO_CLIPBOARD = "copy_to_clipboard"
    PASTE_CLIPBOARD = "paste_clipboard"
    FOCUS_APP = "focus_app"
    SEND_KEYSTROKE = "send_keystroke"
    SUBMIT_PROMPT = "submit_prompt"
    VERIFY_RESULT = "verify_result"
    # Visual feedback intents
    CAPTURE_SCREEN = "capture_screen"
    OCR_IMAGE = "ocr_image"
    READ_VISIBLE_CONTEXT = "read_visible_context"
    DIAGNOSE_VISIBLE_ERROR = "diagnose_visible_error"
    REVIEW_VISIBLE_DESIGN = "review_visible_design"
    GENERATE_PROMPT_FROM_SCREEN = "generate_prompt_from_screen"
    VERIFY_VISIBLE_RESULT = "verify_visible_result"
    # Workspace intents (smart-workspace plan, phases 3–4)
    DELEGATE_TASK = "delegate_task"
    SWITCH_TAB = "switch_tab"
    TYPE_TEXT = "type_text"
    LIST_WINDOWS = "list_windows"
    UNKNOWN = "unknown"


@dataclass
class ParsedIntent:
    intent: IntentType
    confidence: float
    project_id: str | None = None
    params: dict[str, str] | None = None
    raw: str = ""


class IntentParser:
    """Rule-based intent parser for MVP chat routing.

    Patterns are ordered by specificity — more-specific patterns must appear
    before broader catch-alls that share keywords.
    """

    # (IntentType, compiled_pattern)
    _AGENT_APPS = r"(antigravity|claude(?:\s+code)?|cursor|vs\s*code|vscode|chatgpt|chat\s*gpt)"
    _WORK_VERBS = r"(?:build|create|make|implement|develop|fix|add|write|refactor|design|generate|set\s*up|scaffold)"

    _patterns = [
        # ── Delegate a multi-step task to another AI app ─────────────────────────
        # "using antigravity create a website", "build a landing page with claude"
        (
            IntentType.DELEGATE_TASK,
            re.compile(
                r"\b(?:using|use|with|in|via|through|ask|tell|get)\s+" + _AGENT_APPS + r"\b.*?\b" + _WORK_VERBS + r"\b",
                re.IGNORECASE,
            ),
        ),
        (
            IntentType.DELEGATE_TASK,
            re.compile(
                r"\b" + _WORK_VERBS + r"\b.+?\b(?:using|with|in|via|through)\s+" + _AGENT_APPS + r"\b",
                re.IGNORECASE,
            ),
        ),
        # ── Window / tab control ─────────────────────────────────────────────────
        (
            IntentType.SWITCH_TAB,
            re.compile(r"\b(?:switch|go|change|jump)\s+to\s+(?:the\s+|my\s+)?(.+?)\s+tab\b", re.IGNORECASE),
        ),
        (
            IntentType.LIST_WINDOWS,
            re.compile(
                r"\b(?:list|show|which|what)\b.*\b(?:open\s+)?(windows|tabs|apps)\b.*\b(?:open|running)?\b"
                r"|\bwhat(?:'s| is)\s+open\b",
                re.IGNORECASE,
            ),
        ),
        (
            IntentType.TYPE_TEXT,
            re.compile(
                r"\btype\s+[\"'“‘](.+?)[\"'”’]\s+(?:in|into)\s+(?:the\s+)?(.+?)\s*$"
                r"|\btype\s+(.+?)\s+(?:in|into)\s+(?:the\s+)?(.+?)\s*$",
                re.IGNORECASE,
            ),
        ),
        # ── Compound: "open [ai_tool] and generate/give/send a prompt" ──────────
        # Must appear BEFORE OPEN_BROWSER so that compound requests like
        # "open claude and generate a prompt..." are routed to SUBMIT_PROMPT
        # instead of being swallowed by the generic browser launcher.
        (
            IntentType.SUBMIT_PROMPT,
            re.compile(
                r"\b(?:open|launch)\s+(?:browser\s+(?:to\s+)?)?"
                r"(claude|chatgpt|chat gpt|gpt|gemini|perplexity|copilot|openai|openai chat)\b"
                r"\s+(?:and\s+(?:also\s+)?"
                r"(?:"
                r"(?:generate|genareate|create|write|draft|give|send|submit|prepare|make|hand\s*off|request|instruct)\b"
                r"|ask\s+(?:it\s+)?(?:to\s+)?\w+"
                r"|tell\s+(?:it\s+)?(?:to\s+)?\w+"
                r"|instruct\s+(?:it\s+)?(?:to\s+)?\w+"
                r"|have\s+(?:it\s+)?(?:to\s+)?\w+"
                r"))\b",
                re.IGNORECASE,
            ),
        ),
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
        # ── Git history queries ───────────────────────────────────────────────────
        (
            IntentType.GIT_LOG,
            re.compile(
                r"\b(?:last\s+commit|recent\s+commits|what\s+did\s+I\s+commit|"
                r"what\s+was\s+(?:my\s+)?last\s+commit|git\s+log|"
                r"show\s+me\s+(?:my\s+)?commits?|"
                r"latest\s+commit|most\s+recent\s+commit|"
                r"what\s+did\s+I\s+push|what\s+did\s+I\s+merge|"
                r"when\s+did\s+I\s+commit|who\s+am\s+I\s+on\s+git)\b",
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
        # ── Cross-app control intents ──────────────────────────────────────────
        (
            IntentType.COPY_TO_CLIPBOARD,
            re.compile(
                r"\b(?:copy|clipboard|copy to clipboard|copy this|"
                r"copy the prompt|copy the text|copy the content)\b",
                re.IGNORECASE,
            ),
        ),
        (
            IntentType.PASTE_CLIPBOARD,
            re.compile(
                r"\b(?:paste|paste clipboard|paste it|paste there|"
                r"paste it there|paste the prompt)\b",
                re.IGNORECASE,
            ),
        ),
        (
            IntentType.FOCUS_APP,
            re.compile(
                r"\b(?:focus|bring to front|activate|switch to)\s+"
                r"(.+)",
                re.IGNORECASE,
            ),
        ),
        (
            IntentType.SEND_KEYSTROKE,
            re.compile(
                r"\b(?:press|type|send|keystroke|keyboard)\s+"
                r"(.+)",
                re.IGNORECASE,
            ),
        ),
        (
            IntentType.SUBMIT_PROMPT,
            re.compile(
                r"\b(?:submit|give|send|deliver|ask|tell|instruct|request|hand off|handoff|"
                r"send the prompt|submit the prompt|give the prompt|"
                r"give it|send it|ask it to)\b",
                re.IGNORECASE,
            ),
        ),
        (
            IntentType.VERIFY_RESULT,
            re.compile(
                r"\b(?:verify|check|confirm|did it work|is it done|"
                r"did the|did they|check if)\b",
                re.IGNORECASE,
            ),
        ),
        # ── Visual feedback intents ────────────────────────────────────────────
        (
            IntentType.CAPTURE_SCREEN,
            re.compile(
                r"\b(?:screenshot|screen capture|capture screen|"
                r"take a screenshot|screen shot|capture this|"
                r"what do i see|what is on screen)\b",
                re.IGNORECASE,
            ),
        ),
        (
            IntentType.OCR_IMAGE,
            re.compile(
                r"\b(?:read text|extract text|ocr|read what'\s?s on|"
                r"what does it say|read the text)\b",
                re.IGNORECASE,
            ),
        ),
        (
            IntentType.READ_VISIBLE_CONTEXT,
            re.compile(
                r"\b(?:read the screen|what do i see|look at|check the|"
                r"review the|look at the|preview the)\b",
                re.IGNORECASE,
            ),
        ),
        (
            IntentType.DIAGNOSE_VISIBLE_ERROR,
            re.compile(
                r"\b(?:diagnose|debug|fix this error|what went wrong|"
                r"why is this|error on screen|fix the error)\b",
                re.IGNORECASE,
            ),
        ),
        (
            IntentType.REVIEW_VISIBLE_DESIGN,
            re.compile(
                r"\b(?:review.*design|design.*review|look at the.*design|"
                r"improve.*design|design.*improve|ui.*review|preview.*review)\b",
                re.IGNORECASE,
            ),
        ),
        (
            IntentType.GENERATE_PROMPT_FROM_SCREEN,
            re.compile(
                r"\b(?:prompt from|write a prompt|draft a prompt|"
                r"create a prompt.*screen|prompt.*based on.*screen)\b",
                re.IGNORECASE,
            ),
        ),
        (
            IntentType.VERIFY_VISIBLE_RESULT,
            re.compile(
                r"\b(?:verify.*visible|check.*visible|confirm.*result|"
                r"did the.*appear|is the.*there|check if.*visible)\b",
                re.IGNORECASE,
            ),
        ),
    ]

    def parse(self, message: str, active_project_id: str | None = None) -> ParsedIntent:
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
                app_name = ""
                url = ""
                prompt_text = ""
                if intent in (IntentType.OPEN_BROWSER, IntentType.OPEN_APP):
                    # Use the full raw message as the target so agent_actions can parse it
                    target = text
                elif intent == IntentType.DELEGATE_TASK:
                    app_name = re.sub(r"\s+", "", (m.group(1) or "").lower()).replace("claudecode", "claude")
                    app_name = {"vscode": "vscode", "chatgpt": "chatgpt"}.get(app_name, app_name)
                    target = text
                    prompt_text = text
                elif intent == IntentType.TYPE_TEXT:
                    groups = [g for g in m.groups() if g]
                    prompt_text = groups[0].strip() if groups else ""
                    app_name = groups[1].strip().lower() if len(groups) > 1 else ""
                    target = prompt_text
                elif intent == IntentType.SUBMIT_PROMPT:
                    # Extract app_name and prompt from the compound message
                    # Pattern: "open <app> and <action> <prompt>"
                    import re as _re

                    target = text
                    # Extract app name from first capture group
                    if m.groups():
                        app_match = m.group(1)
                        if app_match:
                            app_name = app_match.lower()
                    # Extract the prompt - everything after the trigger phrase
                    # Match: ask (it) (to)? <rest>, tell (it) (to)? <rest>, etc.
                    prompt_match = _re.search(
                        r"\band\s+(?:also\s+)?"
                        r"(?:"
                        r"(?:generate|create|write|draft|give|send|submit|prepare|make|hand\s*off|request|instruct)\b\s*(.+)"
                        r"|ask\s+(?:it\s+)?(?:to\s+)?\w+\s+(.+)"
                        r"|tell\s+(?:it\s+)?(?:to\s+)?\w+\s+(.+)"
                        r"|instruct\s+(?:it\s+)?(?:to\s+)?\w+\s+(.+)"
                        r"|have\s+(?:it\s+)?(?:to\s+)?\w+\s+(.+)"
                        r")",
                        text,
                        _re.IGNORECASE,
                    )
                    if prompt_match:
                        # Find the first non-None group
                        for g in prompt_match.groups():
                            if g:
                                prompt_text = g.strip()
                                break

                # Confidence is lower for broad patterns near the bottom
                broad_intents = {
                    IntentType.RESUME_PROJECT,
                    IntentType.MORNING_BRIEF,
                    IntentType.GENERAL_CHAT,
                    IntentType.QUERY_MEMORY,
                    IntentType.OPEN_APP,
                    IntentType.GIT_LOG,
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
                        "app_name": app_name,
                        "url": url,
                        "prompt": prompt_text,
                    },
                    raw=text,
                )

        if lowered in {"help", "hi", "hello", "what can you do", "hey"}:
            return ParsedIntent(intent=IntentType.GENERAL_CHAT, confidence=0.6, raw=text)

        return ParsedIntent(intent=IntentType.UNKNOWN, confidence=0.0, raw=text)


def parse_intent(message: str, active_project_id: str | None = None) -> ParsedIntent:
    """Parse a chat message through the shared MVP intent parser.

    Keeping this module-level entry point makes API callers independent of the
    parser implementation while preserving the parser's project context.
    """
    return IntentParser().parse(message, active_project_id=active_project_id)
