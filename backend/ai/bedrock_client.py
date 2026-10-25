"""
ai/bedrock_client.py — AUTOMATA Reasoning Engine: LLM and embedding client.

Owns:    All calls to an LLM backend — text generation (reasoning, summaries,
           commit messages, next-task suggestions) and embedding generation.
           Centralized retry logic, timeout limits, and graceful fallback.
Never:   Must not execute OS actions (→ automation/).
           Must not write to CockroachDB (→ db/client.py).
           Must not accept raw credential values — uses env-var or IAM-role
           authentication only (see SKILLS.md §8).
Ref:     ARCHITECTURE.md §3.4, §3.2b, TECH_STACK.md "AI".
"""

import logging
import time

logger = logging.getLogger(__name__)

# Cooldown: if invoke_embedding returned None within this window, skip backend
# calls entirely to avoid hammering failing APIs (e.g., WinError 10048, bad keys).
# Reset automatically when a backend succeeds or becomes newly available.
# See SKILLS.md §4 — idempotent, graceful degradation.
_EMBEDDING_COOLDOWN_SECONDS = 30.0
_last_embedding_fail_time: float = 0.0

# Timeout for a single LLM invocation (seconds).
LLM_TIMEOUT_SECONDS = 30

# Maximum retry attempts on transient errors.
LLM_MAX_RETRIES = 3

# Cooldown for reasoning (LLM chat) calls — mirrors the embedding cooldown.
# If all LLM backends were exhausted within this window, skip backend attempts
# in invoke_reasoning too, so chat routes return the "no backend" message
# instantly instead of waiting for timeouts on each provider.
_LLM_COOLDOWN_SECONDS = 30.0
_last_llm_fail_time: float = 0.0

# ─── Ollama Configuration ──────────────────────────────────────────────
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:7b"
OLLAMA_EMBEDDING_MODEL = "nomic-embed-text"


def _get_ollama_available() -> bool:
    """Check if Ollama is running and reachable."""
    try:
        import urllib.request

        req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            if resp.status == 200:
                return True
    except Exception as exc:
        logger.debug("Ollama health check failed — %s", exc)
    return False


def _invoke_ollama_chat(system_prompt: str, user_message: str) -> str | None:
    """Call Ollama for text generation."""
    import json
    import urllib.error
    import urllib.request

    try:
        payload = json.dumps(
            {
                "model": OLLAMA_MODEL,
                "system": system_prompt,
                "prompt": user_message,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 512,
                },
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            f"{OLLAMA_BASE_URL}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=LLM_TIMEOUT_SECONDS) as resp:
            if resp.status == 200:
                body = json.loads(resp.read().decode("utf-8"))
                response_text = body.get("response", "")
                if response_text:
                    logger.info("LLM: Ollama succeeded")
                    return response_text
                logger.warning("Ollama chat returned empty response")
    except urllib.error.HTTPError as exc:
        logger.warning("Ollama chat call failed — HTTP %s", exc.code)
    except Exception as exc:
        logger.warning("Ollama chat call failed — %s", exc)
    return None


def _invoke_ollama_embedding(text: str) -> list[float] | None:
    """Call Ollama for embedding generation."""
    import json
    import urllib.request

    try:
        payload = json.dumps(
            {
                "model": OLLAMA_EMBEDDING_MODEL,
                "prompt": text,
                "options": {
                    "num_ctx": 8192,
                },
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            f"{OLLAMA_BASE_URL}/api/embeddings",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=LLM_TIMEOUT_SECONDS) as resp:
            if resp.status == 200:
                body = json.loads(resp.read().decode("utf-8"))
                embedding = body.get("embedding")
                if embedding:
                    return embedding
    except Exception as exc:
        logger.warning("Ollama embedding call failed — %s", exc)
    return None


# ─── Gemini API Configuration ───────────────────────────────────────────
def _invoke_gemini_chat(api_key: str, system_prompt: str, user_message: str) -> str | None:
    """Call Gemini API for text generation."""
    import json
    import urllib.error
    import urllib.request

    candidate_models = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
    candidate_versions = ["v1beta", "v1"]

    for model_name in candidate_models:
        for version in candidate_versions:
            payload = json.dumps(
                {
                    "contents": [{"role": "user", "parts": [{"text": user_message}]}],
                    "systemInstruction": {"parts": [{"text": system_prompt}]},
                    "generationConfig": {
                        "temperature": 0.3,
                        "maxOutputTokens": 512,
                    },
                }
            ).encode("utf-8")

            try:
                req = urllib.request.Request(
                    f"https://generativelanguage.googleapis.com/{version}/models/{model_name}:generateContent?key={api_key}",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=LLM_TIMEOUT_SECONDS) as resp:
                    if resp.status == 200:
                        body = json.loads(resp.read().decode("utf-8"))
                        candidates = body.get("candidates", [])
                        if candidates:
                            return (
                                candidates[0]
                                .get("content", {})
                                .get("parts", [{}])[0]
                                .get("text", "")
                            )
            except urllib.error.HTTPError as exc:
                logger.debug("Gemini chat attempt failed for %s/%s — %s", model_name, version, exc)
                continue
            except Exception as exc:
                logger.warning("Gemini chat call failed — %s", exc)
                continue

    logger.warning("Gemini chat call failed for all configured model candidates")
    return None


def _invoke_gemini_embedding(api_key: str, text: str) -> list[float] | None:
    """Call Gemini API for embedding generation."""
    import json
    import urllib.error
    import urllib.request

    candidate_models = ["embedding-001", "text-embedding-004"]
    for model_name in candidate_models:
        try:
            payload = json.dumps(
                {
                    "content": {"parts": [{"text": text}]},
                }
            ).encode("utf-8")

            req = urllib.request.Request(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:embedContent?key={api_key}",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=LLM_TIMEOUT_SECONDS) as resp:
                if resp.status == 200:
                    body = json.loads(resp.read().decode("utf-8"))
                    values = body.get("embedding", {}).get("values", [])
                    if values:
                        return values
        except urllib.error.HTTPError as exc:
            logger.debug("Gemini embedding attempt failed for %s — %s", model_name, exc)
            continue
        except Exception as exc:
            logger.warning("Gemini embedding call failed — %s", exc)
            continue

    logger.warning("Gemini embedding call failed for all configured model candidates")
    return None


# ─── Minimax API Configuration ────────────────────────────────────────
def _invoke_minimax_chat(api_key: str, system_prompt: str, user_message: str) -> str | None:
    """Call Minimax API for text generation."""
    import json
    import urllib.request

    try:
        payload = json.dumps(
            {
                "model": "glm-4",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                "max_tokens": 512,
                "temperature": 0.3,
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            "https://api.minimax.chat/v1/text/chatcompletion",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=LLM_TIMEOUT_SECONDS) as resp:
            if resp.status == 200:
                body = json.loads(resp.read().decode("utf-8"))
                choices = body.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
    except Exception as exc:
        logger.warning("Minimax chat call failed — %s", exc)
    return None


# ─── OpenRouter API Configuration ──────────────────────────────
def _invoke_openrouter_chat(api_key: str, system_prompt: str, user_message: str) -> str | None:
    """Call OpenRouter API for text generation."""
    import json
    import os
    import urllib.error
    import urllib.request

    primary_model = os.getenv("OPENROUTER_MODEL", "poolside/laguna-s-2.1:free")
    candidate_models = [
        primary_model,
        "openai/gpt-4o-mini",
        "anthropic/claude-3.5-sonnet",
        "google/gemini-2.0-flash",
        "meta-llama/llama-3.3-70b-instruct",
        "mistralai/mistral-small-3.1-24b-instruct",
    ]
    # Remove duplicate entries while maintaining priority order
    seen = set()
    deduped_models = []
    for model in candidate_models:
        if model not in seen:
            seen.add(model)
            deduped_models.append(model)

    for model_name in deduped_models:
        payload = json.dumps(
            {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                "max_tokens": 512,
                "temperature": 0.3,
            }
        ).encode("utf-8")

        try:
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": "http://localhost:5173",
                    "X-Title": "AUTOMATA",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=LLM_TIMEOUT_SECONDS) as resp:
                if resp.status == 200:
                    body = json.loads(resp.read().decode("utf-8"))
                    choices = body.get("choices", [])
                    if choices:
                        return choices[0].get("message", {}).get("content", "")
        except urllib.error.HTTPError as exc:
            logger.debug("OpenRouter chat attempt failed for %s — %s", model_name, exc)
            continue
        except Exception as exc:
            logger.warning("OpenRouter chat call failed — %s", exc)
            continue

    logger.warning("OpenRouter chat call failed for all configured model candidates")
    return None


# ─── Cohere API Configuration ────────────────────────────
def _invoke_cohere_chat(api_key: str, system_prompt: str, user_message: str) -> str | None:
    """Call Cohere API for text generation."""
    import json
    import urllib.error
    import urllib.request

    candidate_models = ["command-a-03-2025", "command-r-plus", "command-r"]
    for model_name in candidate_models:
        payload = json.dumps(
            {
                "model": model_name,
                "message": user_message,
                "preamble": system_prompt,
                "max_tokens": 512,
                "temperature": 0.3,
            }
        ).encode("utf-8")

        try:
            req = urllib.request.Request(
                "https://api.cohere.ai/v1/chat",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=LLM_TIMEOUT_SECONDS) as resp:
                if resp.status == 200:
                    body = json.loads(resp.read().decode("utf-8"))
                    text = body.get("text", "")
                    if text:
                        return text
        except urllib.error.HTTPError as exc:
            logger.debug("Cohere chat attempt failed for %s — %s", model_name, exc)
            continue
        except Exception as exc:
            logger.warning("Cohere chat call failed — %s", exc)
            continue

    logger.warning("Cohere chat call failed for all configured model candidates")
    return None


def _invoke_cohere_embedding(text: str) -> list[float] | None:
    """Call Cohere API for embedding generation."""
    import json
    import urllib.error
    import urllib.request

    from config import settings

    api_key = getattr(settings, "cohere_api_key", "")
    if not api_key:
        logger.warning("Cohere embedding call failed — no API key configured")
        return None

    max_retries = 3
    for attempt in range(max_retries):
        try:
            payload = json.dumps(
                {
                    "texts": [text[:2048]],
                    "model": "embed-english-v3.0",
                    "input_type": "search_query",
                }
            ).encode("utf-8")

            req = urllib.request.Request(
                "https://api.cohere.ai/v1/embed",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=LLM_TIMEOUT_SECONDS) as resp:
                if resp.status == 200:
                    body = json.loads(resp.read().decode("utf-8"))
                    embeddings = body.get("embeddings", [])
                    if isinstance(embeddings, dict):
                        float_embs = embeddings.get("float", [])
                        if float_embs:
                            logger.info("Embedding: Cohere succeeded")
                            return float_embs[0]
                    elif isinstance(embeddings, list) and embeddings:
                        logger.info("Embedding: Cohere succeeded")
                        return embeddings[0]
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < max_retries - 1:
                wait = 2**attempt
                logger.warning("Cohere embedding rate limited (429) — retrying in %ds", wait)
                time.sleep(wait)
                continue
            logger.warning("Cohere embedding call failed — HTTP %s", exc.code)
            break
        except Exception as exc:
            logger.warning("Cohere embedding call failed — %s", exc)
            break
    return None


def _invoke_cohere_embedding_legacy(api_key: str, text: str) -> list[float] | None:
    """Legacy Cohere embedding implementation for backward compatibility."""
    import json
    import urllib.error
    import urllib.request

    candidate_models = ["embed-english-v3.0", "embed-multilingual-v3.0", "embed-english-light-v3.0"]
    for model_name in candidate_models:
        payload = json.dumps(
            {
                "texts": [text],
                "model": model_name,
                "input_type": "search_document",
            }
        ).encode("utf-8")

        try:
            req = urllib.request.Request(
                "https://api.cohere.com/v1/embed",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=LLM_TIMEOUT_SECONDS) as resp:
                if resp.status == 200:
                    body = json.loads(resp.read().decode("utf-8"))
                    embeddings = body.get("embeddings", [])
                    if isinstance(embeddings, dict):
                        float_embs = embeddings.get("float", [])
                        if float_embs:
                            return float_embs[0]
                    elif isinstance(embeddings, list) and embeddings:
                        return embeddings[0]
        except urllib.error.HTTPError as exc:
            logger.debug("Cohere embedding attempt failed for %s — %s", model_name, exc)
            continue
        except Exception as exc:
            logger.warning("Cohere embedding call failed — %s", exc)
            continue

    logger.warning("Cohere embedding call failed for all configured model candidates")
    return None


# ─── NVIDIA API Configuration ───────────────────────────────────
def _invoke_nvidia_chat(api_key: str, system_prompt: str, user_message: str) -> str | None:
    """Call NVIDIA NIM API for text generation (Nemotron-3-Ultra-550B)."""
    import json
    import urllib.request

    try:
        payload = json.dumps(
            {
                "model": "nvidia/nemotron-3-ultra-550b-a55b",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                "temperature": 0.3,
                "top_p": 0.95,
                "max_tokens": 8192,
                "stream": False,
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=LLM_TIMEOUT_SECONDS) as resp:
            if resp.status == 200:
                body = json.loads(resp.read().decode("utf-8"))
                choices = body.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
    except Exception as exc:
        logger.warning("NVIDIA chat call failed — %s", exc)
    return None


# ─── Groq API Configuration ──────────────────────────────────────────────
def _invoke_groq_chat(api_key: str, system_prompt: str, user_message: str) -> str | None:
    """Call Groq API for text generation."""
    import json
    import urllib.error
    import urllib.request

    candidate_models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "llama3-70b-8192"]
    for model_name in candidate_models:
        payload = json.dumps(
            {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                "max_tokens": 512,
                "temperature": 0.3,
            }
        ).encode("utf-8")

        try:
            req = urllib.request.Request(
                "https://api.groq.com/openai/v1/chat/completions",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                    "User-Agent": "AUTOMATA/1.0",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=LLM_TIMEOUT_SECONDS) as resp:
                if resp.status == 200:
                    body = json.loads(resp.read().decode("utf-8"))
                    choices = body.get("choices", [])
                    if choices:
                        return choices[0].get("message", {}).get("content", "")
        except urllib.error.HTTPError as exc:
            logger.debug("Groq chat attempt failed for %s — %s", model_name, exc)
            continue
        except Exception as exc:
            logger.warning("Groq chat call failed — %s", exc)
            continue

    logger.warning("Groq chat call failed for all configured model candidates")
    return None


def _invoke_groq_embedding(api_key: str, text: str) -> list[float] | None:
    """Call Groq API for embedding generation."""
    import json
    import urllib.error
    import urllib.request

    candidate_models = ["llama-3.2-1b-preview", "llama-3.1-8b-instant"]
    for model_name in candidate_models:
        payload = json.dumps(
            {
                "model": model_name,
                "input": text,
            }
        ).encode("utf-8")

        try:
            req = urllib.request.Request(
                "https://api.groq.com/openai/v1/embeddings",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                    "User-Agent": "AUTOMATA/1.0",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=LLM_TIMEOUT_SECONDS) as resp:
                if resp.status == 200:
                    body = json.loads(resp.read().decode("utf-8"))
                    data = body.get("data", [])
                    if data:
                        return data[0].get("embedding", [])
        except urllib.error.HTTPError as exc:
            logger.debug("Groq embedding attempt failed for %s — %s", model_name, exc)
            continue
        except Exception as exc:
            logger.warning("Groq embedding call failed — %s", exc)
            continue

    logger.warning("Groq embedding call failed for all configured model candidates")
    return None


# ─── Bedrock Configuration ──────────────────────────────────────────────
def _invoke_bedrock_chat(
    system_prompt: str,
    user_message: str,
    retrieved_memories: list[dict] | None = None,
) -> str | None:
    """Call Amazon Bedrock to generate a grounded response."""
    import json

    from config import settings

    try:
        import boto3
        from botocore.config import Config
    except ImportError:
        logger.warning("Bedrock chat failed — boto3 not installed")
        return None

    if not settings.aws_region or not settings.aws_bedrock_model_id:
        logger.warning("Bedrock chat failed — AWS region or model ID not configured")
        return None

    try:
        client = boto3.client(
            "bedrock-runtime",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id or None,
            aws_secret_access_key=settings.aws_secret_access_key or None,
            config=Config(
                retries={"max_attempts": 2, "mode": "standard"},
                connect_timeout=10,
                read_timeout=30,
            ),
        )

        payload = json.dumps(
            {
                "messages": [{"role": "user", "content": [{"text": user_message}]}],
                "system": [{"text": system_prompt}],
                "maxTokens": 512,
                "temperature": 0.3,
            }
        ).encode("utf-8")

        response = client.invoke_model(
            modelId=settings.aws_bedrock_model_id,
            body=payload,
            accept="application/json",
            contentType="application/json",
        )

        body = json.loads(response["body"].read().decode("utf-8"))
        content = (
            body.get("outputs", [])[0].get("message", {}).get("content", [{}])[0].get("text", "")
            if body.get("outputs")
            else ""
        )
        return content or None
    except Exception as exc:
        logger.warning("Bedrock chat call failed — %s", exc)
    return None


def invoke_reasoning(
    system_prompt: str,
    user_message: str,
    retrieved_memories: list[dict] | None = None,
    reasoning_mode: str | None = None,
) -> str | None:
    """Generate a grounded response using the configured LLM backend.

    Uses a cooldown: if all backends failed within the last
    ``_LLM_COOLDOWN_SECONDS``, returns ``None`` immediately so the caller's
    fallback message is shown without waiting for per-provider timeouts.
    """
    global _last_llm_fail_time
    from config import settings

    # Cooldown: if we just failed, return None immediately so the route can
    # show the "no backend" message without hanging on retries.
    elapsed = time.monotonic() - _last_llm_fail_time
    if elapsed < _LLM_COOLDOWN_SECONDS:
        logger.debug(
            "invoke_reasoning: skipping (cooldown active, %.1fs elapsed, %.1fs remaining)",
            elapsed,
            _LLM_COOLDOWN_SECONDS - elapsed,
        )
        return None

    grounded_prompt = _build_grounded_prompt(system_prompt, user_message, retrieved_memories)

    mode = (reasoning_mode or getattr(settings, "reasoning_mode", "auto")).lower()

    def _try_provider(name: str, fn, api_key: str | None = None) -> str | None:
        if not api_key and name not in {"bedrock", "ollama"}:
            return None
        logger.info("LLM: trying %s", name)
        if name == "bedrock":
            result = fn(system_prompt, grounded_prompt, retrieved_memories)
        elif name == "ollama":
            result = fn(system_prompt, grounded_prompt)
        else:
            result = fn(api_key, system_prompt, grounded_prompt)
        if result:
            logger.info("LLM: %s succeeded", name)
            return result
        logger.warning("LLM: %s failed", name)
        return None

    def _get_local_help() -> str:
        return (
            "Ollama is not available. Install it from https://ollama.com/ and run:\n"
            "  1. ollama pull qwen2.5:7b\n"
            "  2. ollama serve"
        )

    if mode == "local":
        if not _get_ollama_available():
            logger.warning("invoke_reasoning: local mode selected but Ollama is unavailable")
            logger.warning(_get_local_help())
            _all_llm_backends_exhausted()
            return None
        result = _try_provider("ollama", _invoke_ollama_chat)
        if result:
            _last_llm_fail_time = 0.0
            return result
        _all_llm_backends_exhausted()
        return None

    # Groq first: it answers in under 5s. OpenRouter's free model takes
    # 30-60s, so it must never delay a fast provider.
    cloud_providers = [
        ("Groq", getattr(settings, "groq_api_key", ""), _invoke_groq_chat),
        ("OpenRouter", getattr(settings, "openrouter_api_key", ""), _invoke_openrouter_chat),
        ("Gemini", getattr(settings, "gemini_api_key", ""), _invoke_gemini_chat),
        ("Cohere", getattr(settings, "cohere_api_key", ""), _invoke_cohere_chat),
        ("NVIDIA", getattr(settings, "nvidia_api_key", ""), _invoke_nvidia_chat),
        ("Minimax", getattr(settings, "minimax_api_key", ""), _invoke_minimax_chat),
    ]
    for provider_name, api_key, func in cloud_providers:
        if api_key:
            result = _try_provider(provider_name, func, api_key)
            if result:
                _last_llm_fail_time = 0.0
                return result

    if settings.bedrock_available:
        result = _try_provider("bedrock", _invoke_bedrock_chat)
        if result:
            _last_llm_fail_time = 0.0
            return result

    # auto mode falls back to local Ollama; cloud mode never does.
    if mode != "cloud" and _get_ollama_available():
        result = _try_provider("ollama", _invoke_ollama_chat)
        if result:
            _last_llm_fail_time = 0.0
            return result

    logger.warning("invoke_reasoning: No LLM backend available")
    _all_llm_backends_exhausted()
    return None


def _all_backends_exhausted():
    """Mark that all embedding backends have been tried and failed.

    Sets a cooldown timestamp so subsequent calls within the cooldown window
    skip backend attempts entirely, preventing continuous retry spam (e.g.
    WinError 10048 socket exhaustion). The cooldown auto-expires.
    """
    global _last_embedding_fail_time
    _last_embedding_fail_time = time.monotonic()
    logger.info(
        "Embedding cooldown set for %.0fs — all backends exhausted",
        _EMBEDDING_COOLDOWN_SECONDS,
    )


def _all_llm_backends_exhausted():
    """Mark that all LLM backends have been tried and failed.

    Sets a cooldown timestamp so subsequent ``invoke_reasoning`` calls within
    the cooldown window return ``None`` immediately instead of retrying all
    providers and waiting on per-provider timeouts.
    """
    global _last_llm_fail_time
    _last_llm_fail_time = time.monotonic()
    logger.info(
        "LLM cooldown set for %.0fs — all backends exhausted",
        _LLM_COOLDOWN_SECONDS,
    )


def reset_embedding_cooldown():
    """Clear the embedding cooldown so backends will be retried immediately.

    Call this when the user configures new API keys or starts a local LLM.
    """
    global _last_embedding_fail_time
    _last_embedding_fail_time = 0.0
    logger.info("Embedding cooldown reset — backends will be retried on next call")


def reset_llm_cooldown():
    """Clear the LLM reasoning cooldown so backends will be retried immediately."""
    global _last_llm_fail_time
    _last_llm_fail_time = 0.0
    logger.info("LLM cooldown reset — backends will be retried on next call")


def invoke_embedding(text: str) -> list[float] | None:
    """Generate a vector embedding for the given text.

    Uses a cooldown: if all backends failed within the last
    ``_EMBEDDING_COOLDOWN_SECONDS``, returns ``None`` immediately
    without attempting any backend calls. This prevents continuous
    retry spam when no backend is reachable.
    """
    global _last_embedding_fail_time
    from config import settings

    # Cooldown: skip backend calls if we just failed within the cooldown window.
    elapsed = time.monotonic() - _last_embedding_fail_time
    if elapsed < _EMBEDDING_COOLDOWN_SECONDS:
        logger.debug(
            "invoke_embedding: skipping (cooldown active, %.1fs elapsed, %.1fs remaining)",
            elapsed,
            _EMBEDDING_COOLDOWN_SECONDS - elapsed,
        )
        return None

    mode = getattr(settings, "reasoning_mode", "auto").lower()

    # Local mode: only Ollama
    if mode == "local":
        if _get_ollama_available():
            logger.info("Embedding: trying Ollama (%s)", OLLAMA_EMBEDDING_MODEL)
            result = _invoke_ollama_embedding(text)
            if result:
                logger.info("Embedding: Ollama succeeded")
                _last_embedding_fail_time = 0.0
                return result
            logger.warning("Embedding: Ollama failed")
        logger.warning("invoke_embedding: local mode but Ollama unavailable")
        _all_backends_exhausted()
        return None

    # Cloud mode: try cloud embeddings only
    if mode == "cloud":
        logger.info("Embedding: trying Cohere")
        result = _invoke_cohere_embedding(text)
        if result:
            logger.info("Embedding: Cohere succeeded")
            _last_embedding_fail_time = 0.0
            return result
        logger.warning("Embedding: Cohere failed")

        cohere_key = getattr(settings, "cohere_api_key", "")
        if cohere_key:
            logger.info("Embedding: trying Cohere (legacy)")
            result = _invoke_cohere_embedding_legacy(cohere_key, text)
            if result:
                logger.info("Embedding: Cohere succeeded")
                _last_embedding_fail_time = 0.0
                return result
            logger.warning("Embedding: Cohere failed")

        groq_emb_key = getattr(settings, "groq_embedding_api_key", "")
        groq_key = getattr(settings, "groq_api_key", "")
        if groq_emb_key:
            logger.info("Embedding: trying Groq")
            result = _invoke_groq_embedding(groq_emb_key, text)
            if result:
                logger.info("Embedding: Groq succeeded")
                _last_embedding_fail_time = 0.0
                return result
            logger.warning("Embedding: Groq failed")
        elif groq_key:
            logger.info("Embedding: trying Groq (chat key)")
            result = _invoke_groq_embedding(groq_key, text)
            if result:
                logger.info("Embedding: Groq (chat key) succeeded")
                _last_embedding_fail_time = 0.0
                return result
            logger.warning("Embedding: Groq (chat key) failed")

        gemini_key = getattr(settings, "gemini_api_key", "")
        if gemini_key:
            logger.info("Embedding: trying Gemini")
            result = _invoke_gemini_embedding(gemini_key, text)
            if result:
                logger.info("Embedding: Gemini succeeded")
                _last_embedding_fail_time = 0.0
                return result
            logger.warning("Embedding: Gemini failed")

        logger.warning("invoke_embedding: No cloud embedding backend available")
        _all_backends_exhausted()
        return None

    # Auto mode: Ollama first, then cloud embeddings
    # Primary: Ollama (free, local)
    if _get_ollama_available():
        logger.info("Embedding: trying Ollama (%s)", OLLAMA_EMBEDDING_MODEL)
        result = _invoke_ollama_embedding(text)
        if result:
            logger.info("Embedding: Ollama succeeded")
            _last_embedding_fail_time = 0.0
            return result
        logger.warning("Embedding: Ollama failed")

    # Try cloud embeddings - Cohere as fallback
    logger.info("Embedding: trying Cohere")
    result = _invoke_cohere_embedding(text)
    if result:
        logger.info("Embedding: Cohere succeeded")
        _last_embedding_fail_time = 0.0
        return result
    logger.warning("Embedding: Cohere failed")

    cohere_key = getattr(settings, "cohere_api_key", "")
    if cohere_key:
        logger.info("Embedding: trying Cohere (legacy)")
        result = _invoke_cohere_embedding_legacy(cohere_key, text)
        if result:
            logger.info("Embedding: Cohere succeeded")
            _last_embedding_fail_time = 0.0
            return result
        logger.warning("Embedding: Cohere failed")

    groq_emb_key = getattr(settings, "groq_embedding_api_key", "")
    groq_key = getattr(settings, "groq_api_key", "")
    if groq_emb_key:
        logger.info("Embedding fallback: trying Groq")
        result = _invoke_groq_embedding(groq_emb_key, text)
        if result:
            logger.info("Embedding fallback: Groq succeeded")
            _last_embedding_fail_time = 0.0
            return result
        logger.warning("Embedding fallback: Groq failed")
    elif groq_key:
        logger.info("Embedding fallback: trying Groq (chat key)")
        result = _invoke_groq_embedding(groq_key, text)
        if result:
            logger.info("Embedding fallback: Groq (chat key) succeeded")
            _last_embedding_fail_time = 0.0
            return result
        logger.warning("Embedding fallback: Groq (chat key) failed")

    gemini_key = getattr(settings, "gemini_api_key", "")
    if gemini_key:
        logger.info("Embedding fallback: trying Gemini")
        result = _invoke_gemini_embedding(gemini_key, text)
        if result:
            logger.info("Embedding fallback: Gemini succeeded")
            _last_embedding_fail_time = 0.0
            return result
        logger.warning("Embedding fallback: Gemini failed")

    logger.warning("invoke_embedding: No embedding backend available")
    _all_backends_exhausted()
    return None


def _load_prompt_template(name: str) -> str:
    """Load a prompt template from backend/ai/prompts/<name>.txt."""
    try:
        from pathlib import Path

        template_path = Path(__file__).parent / "prompts" / f"{name}.txt"
        return template_path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.warning("_load_prompt_template: failed to load %s — %s", name, exc)
        return ""


def _build_grounded_prompt(
    system_prompt: str,
    user_message: str,
    retrieved_memories: list[dict] | None,
) -> str:
    """Build a grounded prompt that includes retrieved memories."""
    if not retrieved_memories:
        return user_message

    memory_context = "\n".join(
        f"- [{m.get('table', 'unknown')}] {m.get('content', str(m))} | {m.get('timestamp', '')}"
        for m in retrieved_memories[:10]
    )
    template = _load_prompt_template("grounded_answer")
    if not template:
        template = (
            "Memory sources (table | content | timestamp):\n{memory_context}\n\n"
            "Question: {user_message}\n\n"
            "Answer using ONLY the memory entries above. Be direct. No filler."
        )
    return template.format(memory_context=memory_context, user_message=user_message)
