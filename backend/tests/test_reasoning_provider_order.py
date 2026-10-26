import io
import types
import urllib.error

import pytest

from ai import bedrock_client
import config


@pytest.fixture(autouse=True)
def _reset_bedrock_cooldowns():
    bedrock_client._last_llm_fail_time = 0.0
    bedrock_client._last_embedding_fail_time = 0.0
    yield
    bedrock_client._last_llm_fail_time = 0.0
    bedrock_client._last_embedding_fail_time = 0.0



def test_gemini_chat_retries_with_alternate_model(monkeypatch):
    calls = []

    class DummyResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"candidates":[{"content":{"parts":[{"text":"ok"}]}}]}'

    def fake_urlopen(req, timeout):
        calls.append(req.full_url)
        if len(calls) == 1:
            raise urllib.error.HTTPError(req.full_url, 404, "not found", hdrs=None, fp=io.BytesIO(b'{}'))
        return DummyResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = bedrock_client._invoke_gemini_chat("fake-key", "system", "user")

    assert result == "ok"
    assert len(calls) == 2
    assert any("gemini-2.0-flash" in url for url in calls)


def test_invoke_reasoning_falls_back_from_groq_to_gemini(monkeypatch):
    calls = []

    def fake_groq_chat(*args, **kwargs):
        calls.append("groq")
        return None

    def fake_gemini_chat(*args, **kwargs):
        calls.append("gemini")
        return "fallback reply"

    monkeypatch.setattr(bedrock_client, "_get_ollama_available", lambda: False)
    monkeypatch.setattr(bedrock_client, "_invoke_groq_chat", fake_groq_chat)
    monkeypatch.setattr(bedrock_client, "_invoke_gemini_chat", fake_gemini_chat)
    monkeypatch.setattr(bedrock_client, "_invoke_nvidia_chat", lambda *args, **kwargs: None)
    monkeypatch.setattr(bedrock_client, "_invoke_minimax_chat", lambda *args, **kwargs: None)
    monkeypatch.setattr(bedrock_client, "_invoke_openrouter_chat", lambda *args, **kwargs: None)
    monkeypatch.setattr(bedrock_client, "_invoke_cohere_chat", lambda *args, **kwargs: None)
    monkeypatch.setattr(bedrock_client, "_invoke_bedrock_chat", lambda *args, **kwargs: None)
    import sys
    monkeypatch.setattr(
        sys.modules["config"],
        "settings",
        types.SimpleNamespace(
            bedrock_available=False,
            groq_api_key="groq-key",
            gemini_api_key="gemini-key",
            nvidia_api_key="",
            minimax_api_key="",
            openrouter_api_key="",
            cohere_api_key="",
        ),
    )

    result = bedrock_client.invoke_reasoning("system", "user", [])

    assert result == "fallback reply"
    assert calls == ["groq", "gemini"]


def test_invoke_reasoning_tries_cloud_providers_before_bedrock_and_ollama(monkeypatch):
    calls = []

    def fake_groq_chat(*args, **kwargs):
        calls.append("groq")
        return None

    def fake_gemini_chat(*args, **kwargs):
        calls.append("gemini")
        return None

    def fake_nvidia_chat(*args, **kwargs):
        calls.append("nvidia")
        return None

    def fake_minimax_chat(*args, **kwargs):
        calls.append("minimax")
        return None

    def fake_openrouter_chat(*args, **kwargs):
        calls.append("openrouter")
        return None

    def fake_cohere_chat(*args, **kwargs):
        calls.append("cohere")
        return None

    def fake_bedrock_chat(*args, **kwargs):
        calls.append("bedrock")
        return None

    def fake_ollama_chat(*args, **kwargs):
        calls.append("ollama")
        return None

    monkeypatch.setattr(bedrock_client, "_get_ollama_available", lambda: True)
    monkeypatch.setattr(bedrock_client, "_invoke_groq_chat", fake_groq_chat)
    monkeypatch.setattr(bedrock_client, "_invoke_gemini_chat", fake_gemini_chat)
    monkeypatch.setattr(bedrock_client, "_invoke_nvidia_chat", fake_nvidia_chat)
    monkeypatch.setattr(bedrock_client, "_invoke_minimax_chat", fake_minimax_chat)
    monkeypatch.setattr(bedrock_client, "_invoke_openrouter_chat", fake_openrouter_chat)
    monkeypatch.setattr(bedrock_client, "_invoke_cohere_chat", fake_cohere_chat)
    monkeypatch.setattr(bedrock_client, "_invoke_bedrock_chat", fake_bedrock_chat)
    monkeypatch.setattr(bedrock_client, "_invoke_ollama_chat", fake_ollama_chat)
    import sys
    monkeypatch.setattr(
        sys.modules["config"],
        "settings",
        types.SimpleNamespace(
            bedrock_available=True,
            reasoning_mode="auto",
            groq_api_key="groq-key",
            gemini_api_key="gemini-key",
            nvidia_api_key="nvidia-key",
            minimax_api_key="minimax-key",
            openrouter_api_key="openrouter-key",
            cohere_api_key="cohere-key",
        ),
    )

    result = bedrock_client.invoke_reasoning("system", "user", [])

    assert result is None
    assert calls == ["groq", "openrouter", "gemini", "cohere", "nvidia", "minimax", "bedrock", "ollama"]


def test_invoke_reasoning_local_mode_uses_only_ollama(monkeypatch):
    calls = []

    def fake_ollama_chat(*args, **kwargs):
        calls.append("ollama")
        return "local reply"

    monkeypatch.setattr(bedrock_client, "_get_ollama_available", lambda: True)
    monkeypatch.setattr(bedrock_client, "_invoke_ollama_chat", fake_ollama_chat)
    monkeypatch.setattr(bedrock_client, "_invoke_groq_chat", lambda *args, **kwargs: None)
    monkeypatch.setattr(bedrock_client, "_invoke_gemini_chat", lambda *args, **kwargs: None)
    monkeypatch.setattr(bedrock_client, "_invoke_nvidia_chat", lambda *args, **kwargs: None)
    monkeypatch.setattr(bedrock_client, "_invoke_minimax_chat", lambda *args, **kwargs: None)
    monkeypatch.setattr(bedrock_client, "_invoke_openrouter_chat", lambda *args, **kwargs: None)
    monkeypatch.setattr(bedrock_client, "_invoke_cohere_chat", lambda *args, **kwargs: None)
    monkeypatch.setattr(bedrock_client, "_invoke_bedrock_chat", lambda *args, **kwargs: None)
    import sys
    monkeypatch.setattr(
        sys.modules["config"],
        "settings",
        types.SimpleNamespace(
            bedrock_available=True,
            reasoning_mode="local",
            groq_api_key="groq-key",
            gemini_api_key="gemini-key",
            nvidia_api_key="",
            minimax_api_key="",
            openrouter_api_key="",
            cohere_api_key="",
        ),
    )

    result = bedrock_client.invoke_reasoning("system", "user", [])

    assert result == "local reply"
    assert calls == ["ollama"]


def test_invoke_reasoning_cloud_mode_skips_ollama(monkeypatch):
    calls = []

    def fake_groq_chat(*args, **kwargs):
        calls.append("groq")
        return "cloud reply"

    monkeypatch.setattr(bedrock_client, "_get_ollama_available", lambda: True)
    monkeypatch.setattr(bedrock_client, "_invoke_groq_chat", fake_groq_chat)
    monkeypatch.setattr(bedrock_client, "_invoke_gemini_chat", lambda *args, **kwargs: None)
    monkeypatch.setattr(bedrock_client, "_invoke_nvidia_chat", lambda *args, **kwargs: None)
    monkeypatch.setattr(bedrock_client, "_invoke_minimax_chat", lambda *args, **kwargs: None)
    monkeypatch.setattr(bedrock_client, "_invoke_openrouter_chat", lambda *args, **kwargs: None)
    monkeypatch.setattr(bedrock_client, "_invoke_cohere_chat", lambda *args, **kwargs: None)
    monkeypatch.setattr(bedrock_client, "_invoke_bedrock_chat", lambda *args, **kwargs: None)
    monkeypatch.setattr(bedrock_client, "_invoke_ollama_chat", lambda *args, **kwargs: None)
    import sys
    monkeypatch.setattr(
        sys.modules["config"],
        "settings",
        types.SimpleNamespace(
            bedrock_available=True,
            reasoning_mode="cloud",
            groq_api_key="groq-key",
            gemini_api_key="",
            nvidia_api_key="",
            minimax_api_key="",
            openrouter_api_key="",
            cohere_api_key="",
        ),
    )

    result = bedrock_client.invoke_reasoning("system", "user", [])

    assert result == "cloud reply"
    assert calls == ["groq"]
