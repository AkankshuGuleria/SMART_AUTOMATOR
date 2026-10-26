"""
tests/test_profile.py — Phase 2: project profile is derived from each project's files.
"""

import json

import pytest
from fastapi.testclient import TestClient

from intelligence.profile import detect, prompt_context, score_modules
from intelligence.providers import describe


def write(root, rel, text=""):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def next_app(tmp_path):
    write(tmp_path, "package.json", json.dumps({
        "scripts": {"dev": "next dev --port 3001", "build": "next build", "test": "vitest"},
        "dependencies": {"next": "15", "react": "19", "@prisma/client": "5", "stripe": "16"},
        "devDependencies": {"prisma": "5", "vitest": "2", "tailwindcss": "4"},
    }))
    write(tmp_path, "pnpm-lock.yaml")
    write(tmp_path, "prisma/schema.prisma", 'datasource db {\n  provider = "postgresql"\n}')
    write(tmp_path, ".env.example", "DATABASE_URL=\nSTRIPE_SECRET_KEY=your_key\nNEXT_PUBLIC_SITE_URL=http://localhost:3001\n")
    write(tmp_path, ".env", "DATABASE_URL=postgresql://u:p@localhost/db\nSTRIPE_SECRET_KEY=\n")
    write(tmp_path, "src/app/page.tsx", "export default function P(){ return null } // TODO hero")
    write(tmp_path, "src/app/api/checkout/route.ts", "const k = process.env.STRIPE_SECRET_KEY; const w = process.env.STRIPE_WEBHOOK_SECRET")
    write(tmp_path, "src/components/Button.tsx", "export const B = 1")
    write(tmp_path, "src/components/Card.tsx", "export const C = 1")
    write(tmp_path, "src/components/Card.test.tsx", "test('x', () => {})")
    write(tmp_path, "node_modules/react/index.js", "process.env.SHOULD_NOT_APPEAR")
    write(tmp_path, ".github/workflows/ci.yml", "on: push")
    write(tmp_path, "Dockerfile", "FROM node")
    return tmp_path


def test_next_prisma_app_profile(next_app):
    p = detect(str(next_app))
    assert p["ok"] is True
    assert {"Next.js", "React", "Prisma", "Stripe", "Vitest", "Tailwind CSS"} <= set(p["frameworks"])
    assert p["databases"] == ["PostgreSQL"]
    assert p["package_managers"] == ["pnpm"]
    assert "Docker" in p["infrastructure"] and "GitHub Actions" in p["infrastructure"]
    assert 3001 in p["ports"]
    cmds = p["run_book"][0]["commands"]
    assert cmds["install"] == "pnpm install" and cmds["dev"] == "pnpm dev" and cmds["test"] == "pnpm test"
    assert "Next.js + React frontend" in p["summary"]


def test_env_requirements_names_only_and_set_status(next_app):
    env = {v["name"]: v for v in detect(str(next_app))["env"]["variables"]}
    assert env["DATABASE_URL"]["set"] is True
    assert env["STRIPE_SECRET_KEY"]["set"] is False  # empty in .env
    assert env["STRIPE_WEBHOOK_SECRET"]["set"] is False  # only referenced in code
    assert env["STRIPE_WEBHOOK_SECRET"]["used_in"] == "src/app/api/checkout/route.ts"
    assert env["STRIPE_SECRET_KEY"]["provider"] == "Stripe"
    assert "SHOULD_NOT_APPEAR" not in env  # node_modules ignored
    blob = json.dumps(detect(str(next_app)))
    assert "postgresql://u:p@" not in blob  # values never leave the file


def test_modules_follow_project_structure(next_app):
    p = detect(str(next_app))
    names = {m["path"]: m for m in p["modules"]}
    assert "src/components" in names and names["src/components"]["test_files"] == 1
    assert "src/app" not in names or names["src/app"]["name"] in {"App routes", "App"}
    assert all("Memory Engine" != m["name"] for m in p["modules"])
    scored = score_modules(p, None)
    comp = next(m for m in scored if m["path"] == "src/components")
    assert 0 <= comp["pct"] <= 100 and "test files" in comp["basis"]


def test_django_project_profile(tmp_path):
    write(tmp_path, "requirements.txt", "Django==5.0\npsycopg2-binary\npytest\n")
    write(tmp_path, "manage.py", "import os\nos.environ.get('DJANGO_SECRET_KEY')")
    write(tmp_path, "shop/models.py", "x = 1")
    write(tmp_path, "shop/views.py", "x = 1")
    p = detect(str(tmp_path))
    assert "Django" in p["frameworks"] and "PostgreSQL" in p["databases"]
    assert p["run_book"][0]["commands"]["dev"] == "python manage.py runserver"
    assert 8000 in p["ports"]
    assert any(v["name"] == "DJANGO_SECRET_KEY" for v in p["env"]["variables"])


def test_empty_folder_is_honest(tmp_path):
    p = detect(str(tmp_path))
    assert p["ok"] and p["frameworks"] == [] and p["summary"].startswith("No recognised stack")


def test_missing_folder_is_an_error():
    assert detect("Z:/does/not/exist")["ok"] is False


def test_provider_instructions():
    assert describe("STRIPE_SECRET_KEY")["provider"] == "Stripe"
    assert describe("DATABASE_URL")["kind"] == "connection_string"
    assert describe("MY_CUSTOM_TOKEN")["kind"] == "secret"
    assert describe("FEATURE_FLAG")["kind"] == "config"


def test_profile_route_and_prompt_context(next_app):
    from api.server import app
    from memory import local_store
    from memory.local_store import LocalStore

    store = LocalStore(":memory:")
    store.upsert_project({"id": "np", "name": "shop", "repo_path": str(next_app)}, source="local")
    local_store.set_store(store)
    try:
        body = TestClient(app).get("/projects/np/profile").json()
        assert "Next.js" in body["frameworks"] and body["project_id"] == "np"
        ctx = prompt_context("np")
        assert "Stack:" in ctx and "STRIPE_SECRET_KEY" in ctx and "pnpm dev" in ctx
    finally:
        local_store.set_store(None)


def test_example_defaults_are_not_missing(tmp_path):
    write(tmp_path, "requirements.txt", "fastapi\n")
    write(tmp_path, ".env.example", "OLLAMA_BASE_URL=http://localhost:11434\nOPENAI_API_KEY=\n")
    env = {v["name"]: v for v in detect(str(tmp_path))["env"]["variables"]}
    assert env["OLLAMA_BASE_URL"]["set"] is True and env["OLLAMA_BASE_URL"]["has_default"] is True
    assert env["OPENAI_API_KEY"]["set"] is False



@pytest.mark.parametrize("files,kind,ai", [
    ({"index.html": "<h1>Hi</h1>", "css/site.css": "h1{}", "js/app.js": "1"}, "static_website", False),
    ({"package.json": json.dumps({"dependencies": {"react": "19", "vite": "6"}}), "src/App.tsx": "x"}, "web_app", False),
    ({"requirements.txt": "fastapi\nopenai\n", "main.py": "x"}, "api_service", True),
    ({"package.json": json.dumps({"dependencies": {"next": "15", "react": "19", "express": "4"}}), "src/a.ts": "x"}, "full_stack", False),
    ({"pyproject.toml": "[project]\ndependencies=['click']\n", "cli.py": "x"}, "library_cli", False),
])
def test_project_type_classification(tmp_path, files, kind, ai):
    for rel, text in files.items():
        write(tmp_path, rel, text)
    ptype = detect(str(tmp_path))["type"]
    assert ptype["kind"] == kind
    assert ptype["ai"] is ai
    assert ptype["reasons"]


def test_static_site_profile_has_no_backend_claims(tmp_path):
    write(tmp_path, "index.html", "<h1>Hi</h1>")
    write(tmp_path, "about.html", "<h1>About</h1>")
    write(tmp_path, "styles/main.css", "body{}")
    p = detect(str(tmp_path))
    assert p["type"]["label"] == "Static website"
    assert p["databases"] == [] and p["run_book"] == []
    assert "API" not in p["type"]["focus"]
