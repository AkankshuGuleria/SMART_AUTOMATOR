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

logger = logging.getLogger(__name__)

# Timeout for a single LLM invocation (seconds).
LLM_TIMEOUT_SECONDS = 30

# Maximum retry attempts on transient errors.
LLM_MAX_RETRIES = 3

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
    import urllib.request
    try:
        payload = json.dumps({
            "model": OLLAMA_MODEL,
            "system": system_prompt,
            "prompt": user_message,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_predict": 512,
            },
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{OLLAMA_BASE_URL}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=LLM_TIMEOUT_SECONDS) as resp:
            if resp.status == 200:
                body = json.loads(resp.read().decode("utf-8"))
                return body.get("response", "")
    except Exception as exc:
        logger.warning("Ollama chat call failed — %s", exc)
    return None


def _invoke_ollama_embedding(text: str) -> list[float] | None:
    """Call Ollama for embedding generation."""
    import json
    import urllib.request
    try:
        payload = json.dumps({
            "model": OLLAMA_EMBEDDING_MODEL,
            "prompt": text,
            "options": {
                "num_ctx": 8192,
            },
        }).encode("utf-8")

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
    import urllib.request
    try:
        payload = json.dumps({
            "system_instruction": system_prompt,
            "contents": [{"parts": [{"text": user_message}]}],
            "generation_config": {
                "temperature": 0.3,
                "max_output_tokens": 512,
            },
        }).encode("utf-8")

        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=LLM_TIMEOUT_SECONDS) as resp:
            if resp.status == 200:
                body = json.loads(resp.read().decode("utf-8"))
                candidates = body.get("candidates", [])
                if candidates:
                    return candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    except Exception as exc:
        logger.warning("Gemini chat call failed — %s", exc)
    return None


def _invoke_gemini_embedding(api_key: str, text: str) -> list[float] | None:
    """Call Gemini API for embedding generation."""
    import json
    import urllib.request
    try:
        payload = json.dumps({
            "model": "embedding-001",
            "content": {"parts": [{"text": text}]},
        }).encode("utf-8")

        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/embedding-001:embedContent?key={api_key}",
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
    except Exception as exc:
        logger.warning("Gemini embedding call failed — %s", exc)
    return None


# ─── Minimax API Configuration ────────────────────────────────────────
def _invoke_minimax_chat(api_key: str, system_prompt: str, user_message: str) -> str | None:
    """Call Minimax API for text generation."""
    import json
    import urllib.request
    try:
        payload = json.dumps({
            "model": "glm-4",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "max_tokens": 512,
            "temperature": 0.3,
        }).encode("utf-8")

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


# ─── NVIDIA API Configuration ───────────────────────────────────────────
def _invoke_nvidia_chat(api_key: str, system_prompt: str, user_message: str) -> str | None:
    """Call NVIDIA API for text generation (Minimax model via NVIDIA endpoint)."""
    import json
    import urllib.request
    try:
        payload = json.dumps({
            "model": "minimaxai/minimax-m3",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.3,
            "top_p": 0.95,
            "max_tokens": 8192,
            "stream": False,
        }).encode("utf-8")

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
    import urllib.request
    try:
        payload = json.dumps({
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "max_tokens": 512,
            "temperature": 0.3,
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
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
        logger.warning("Groq chat call failed — %s", exc)
    return None


def _invoke_groq_embedding(api_key: str, text: str) -> list[float] | None:
    """Call Groq API for embedding generation."""
    import json
    import urllib.request
    try:
        payload = json.dumps({
            "model": "embedding-model",
            "input": text,
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/embeddings",
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
                data = body.get("data", [])
                if data:
                    return data[0].get("embedding", [])
    except Exception as exc:
        logger.warning("Groq embedding call failed — %s", exc)
    return None


# ─── Bedrock Configuration ──────────────────────────────────────────────
def _invoke_bedrock_chat(
    system_prompt: str,
    user_message: str,
    retrieved_memories: list[dict] | None = None,
) -> str | None:
    """Call Amazon Bedrock to generate a grounded response."""
    import json
    import urllib.request

    from config import settings
    try:
        payload = json.dumps({
            "messages": [{"role": "user", "content": [{"text": user_message}]}],
            "system": [{"text": system_prompt}],
            "maxTokens": 512,
            "temperature": 0.3,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"https://bedrock-runtime.{settings.aws_region}.amazonaws.com/model/amazon.titan-text-lite-v1/invoke",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"AWS4-HMAC-SHA256 Credential={settings.aws_access_key_id}/{date}/{settings.aws_region}/bedrock/aws4_request",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=LLM_TIMEOUT_SECONDS) as resp:
            if resp.status == 200:
                body = json.loads(resp.read().decode("utf-8"))
                content = (
                    body.get("output", {})
                    .get("message", {})
                    .get("content", [{}])[0]
                    .get("text", "")
                )
                return content
    except Exception as exc:
        logger.warning("Bedrock chat call failed — %s", exc)
    return None


def invoke_reasoning(
    system_prompt: str,
    user_message: str,
    retrieved_memories: list[dict] | None = None,
) -> str | None:
    """Generate a grounded response using the configured LLM backend."""
    from config import settings

    grounded_prompt = _build_grounded_prompt(system_prompt, user_message, retrieved_memories)

    # Try Bedrock first (if configured)
    if settings.bedrock_available:
        logger.info("LLM fallback: trying Bedrock (%s)", settings.aws_bedrock_model_id)
        result = _invoke_bedrock_chat(system_prompt, grounded_prompt, retrieved_memories)
        if result:
            logger.info("LLM fallback: Bedrock succeeded")
            return result
        logger.warning("LLM fallback: Bedrock failed")

    # Try NVIDIA (if configured)
    nvidia_key = getattr(settings, "nvidia_api_key", "")
    if nvidia_key:
        logger.info("LLM fallback: trying NVIDIA")
        result = _invoke_nvidia_chat(nvidia_key, system_prompt, grounded_prompt)
        if result:
            logger.info("LLM fallback: NVIDIA succeeded")
            return result
        logger.warning("LLM fallback: NVIDIA failed")

    # Try Groq (if configured)
    groq_key = getattr(settings, "groq_api_key", "")
    if groq_key:
        logger.info("LLM fallback: trying Groq")
        result = _invoke_groq_chat(groq_key, system_prompt, grounded_prompt)
        if result:
            logger.info("LLM fallback: Groq succeeded")
            return result
        logger.warning("LLM fallback: Groq failed")

    # Try Gemini (if configured)
    gemini_key = getattr(settings, "gemini_api_key", "")
    if gemini_key:
        logger.info("LLM fallback: trying Gemini")
        result = _invoke_gemini_chat(gemini_key, system_prompt, grounded_prompt)
        if result:
            logger.info("LLM fallback: Gemini succeeded")
            return result
        logger.warning("LLM fallback: Gemini failed")

    # Try Minimax (if configured)
    minimax_key = getattr(settings, "minimax_api_key", "")
    if minimax_key:
        logger.info("LLM fallback: trying Minimax")
        result = _invoke_minimax_chat(minimax_key, system_prompt, grounded_prompt)
        if result:
            logger.info("LLM fallback: Minimax succeeded")
            return result
        logger.warning("LLM fallback: Minimax failed")

    # Fallback to Ollama (free, local)
    if _get_ollama_available():
        logger.info("LLM fallback: trying Ollama (%s)", OLLAMA_MODEL)
        result = _invoke_ollama_chat(system_prompt, grounded_prompt)
        if result:
            logger.info("LLM fallback: Ollama succeeded")
            return result
        logger.warning("LLM fallback: Ollama failed")

    logger.warning("invoke_reasoning: No LLM backend available")
    return None


def invoke_embedding(text: str) -> list[float] | None:
    """Generate a vector embedding for the given text."""
    from config import settings

    # Try Groq embedding (if configured)
    groq_emb_key = getattr(settings, "groq_embedding_api_key", "")
    groq_key = getattr(settings, "groq_api_key", "")
    if groq_emb_key:
        logger.info("Embedding fallback: trying Groq")
        result = _invoke_groq_embedding(groq_emb_key, text)
        if result:
            logger.info("Embedding fallback: Groq succeeded")
            return result
        logger.warning("Embedding fallback: Groq failed")
    elif groq_key:
        # Fallback to chat key if embedding key not set
        logger.info("Embedding fallback: trying Groq (chat key)")
        result = _invoke_groq_embedding(groq_key, text)
        if result:
            logger.info("Embedding fallback: Groq (chat key) succeeded")
            return result
        logger.warning("Embedding fallback: Groq (chat key) failed")

    # Try Gemini (if configured)
    gemini_key = getattr(settings, "gemini_api_key", "")
    if gemini_key:
        logger.info("Embedding fallback: trying Gemini")
        result = _invoke_gemini_embedding(gemini_key, text)
        if result:
            logger.info("Embedding fallback: Gemini succeeded")
            return result
        logger.warning("Embedding fallback: Gemini failed")

    # Fallback to Ollama (free, local)
    if _get_ollama_available():
        logger.info("Embedding fallback: trying Ollama (%s)", OLLAMA_EMBEDDING_MODEL)
        result = _invoke_ollama_embedding(text)
        if result:
            logger.info("Embedding fallback: Ollama succeeded")
            return result
        logger.warning("Embedding fallback: Ollama failed")

    logger.warning("invoke_embedding: No embedding backend available")
    return None


def _build_grounded_prompt(
    system_prompt: str,
    user_message: str,
    retrieved_memories: list[dict] | None,
) -> str:
    """Build a grounded prompt that includes retrieved memories."""
    if not retrieved_memories:
        return user_message

    memory_context = "\n".join(
        f"- [{m.get('table', 'unknown')}] {m.get('content', str(m))}"
        for m in retrieved_memories[:10]
    )
    return (
        f"Use the following retrieved memories as context. "
        f"Answer based only on these memories — do not fabricate facts not present.\n\n"
        f"Memories:\n{memory_context}\n\n"
        f"Question: {user_message}"
    )