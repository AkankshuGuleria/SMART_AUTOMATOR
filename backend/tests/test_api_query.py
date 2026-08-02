"""
tests/test_api_query.py - Query API regression tests.

These tests keep the memory-query route useful without requiring a live
CockroachDB, Ollama, or Bedrock service.
"""

import os

import pytest
from fastapi.testclient import TestClient

_ENV_KEYS = (
    "COCKROACHDB_CONNECTION_STRING",
    "AWS_REGION",
    "AWS_BEDROCK_MODEL_ID",
    "EMBEDDING_MODEL_ID",
    "EMBEDDING_DIMENSION",
)


@pytest.fixture
def client():
    before = {key: os.environ.get(key) for key in _ENV_KEYS}

    from api.server import app

    yield TestClient(app)

    for key, value in before.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def test_query_rejects_empty_question(client: TestClient) -> None:
    response = client.post("/query", json={"question": "   "})

    assert response.status_code == 200
    body = response.json()
    assert body["grounded"] is False
    assert body["memories"] == []
    assert "Ask a question" in body["answer"]


def test_query_without_project_does_not_crash(client: TestClient) -> None:
    response = client.post("/query", json={"question": "What did I finish yesterday?"})

    assert response.status_code == 200
    body = response.json()
    assert body["grounded"] is False
    assert body["memories"] == []
    assert "No project selected" in body["answer"]
