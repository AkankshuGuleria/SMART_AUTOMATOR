"""
tests/test_tasks.py — Phase 4: delegation tasks, approval gates and the Needs inbox.

Runs the task engine inline (AUTOMATA_TASKS_SYNC=1). The agent, build commands
and Credential Manager are faked; the "agent" edits a file in a temp repo.
"""

import json
import subprocess
import types

import pytest
from fastapi.testclient import TestClient

from api.server import app
from memory import local_store
from memory.local_store import LocalStore
from tasks import engine, store as task_store_mod
from tasks.store import TaskStore

client = TestClient(app)


@pytest.fixture
def env(tmp_path, monkeypatch):
    repo = tmp_path / "shop"
    repo.mkdir()
    (repo / "package.json").write_text(json.dumps({
        "scripts": {"dev": "vite", "build": "vite build"},
        "dependencies": {"react": "19", "stripe": "16"}, "devDependencies": {"vite": "6"},
    }))
    (repo / ".env.example").write_text("STRIPE_SECRET_KEY=\nDATABASE_URL=\n")
    (repo / "src").mkdir()
    (repo / "src" / "main.tsx").write_text("export {}")
    subprocess.run(["git", "init", "-q"], cwd=repo)
    (repo / ".gitignore").write_text(".env\n")

    ls = LocalStore(":memory:")
    ls.upsert_project({"id": "p1", "name": "shop", "repo_path": str(repo)}, source="local")
    local_store.set_store(ls)
    ts = TaskStore(":memory:")
    task_store_mod.set_task_store(ts)
    monkeypatch.setenv("AUTOMATA_TASKS_SYNC", "1")
    monkeypatch.setenv("AUTOMATA_TASK_WATCH_MAX", "3")
    monkeypatch.setenv("AUTOMATA_TASK_WATCH_QUIET", "0.2")
    monkeypatch.setenv("AUTOMATA_TASK_WATCH_POLL", "0.1")
    monkeypatch.setenv("AUTOMATA_TASK_MODEL_QUESTIONS", "0")  # no model calls in tests

    sent = {}

    def fake_send(self, tool, prompt, params=None):
        sent.update(tool=tool, prompt=prompt, params=params)
        (repo / "src" / "Landing.tsx").write_text("export const Landing = () => null")  # the agent's work
        from automation.agent_bridge import BridgeResult

        return BridgeResult(tool=tool, status="ok", output="Done. Set RESEND_API_KEY for emails.", executed=True)

    monkeypatch.setattr("automation.agent_bridge.AgentBridge.send_prompt", fake_send)

    ran = []

    class FakeExec:
        def __init__(self, cwd="", allow_auto_execute=False):
            self.cwd = cwd

        def execute(self, cmd, context="", session_id=None):
            ran.append((cmd, self.cwd))
            return types.SimpleNamespace(status="ok", exit_code=0, stdout="built in 1.2s", stderr="")

    monkeypatch.setattr("automation.command_executor.CommandExecutor", FakeExec)
    yield types.SimpleNamespace(repo=repo, sent=sent, ran=ran, store=ts)
    local_store.set_store(None)
    task_store_mod.set_task_store(None)


def test_delegation_task_full_flow(env):
    res = client.post("/tasks", json={"project_id": "p1", "agent": "antigravity",
                                      "request": "using antigravity create a landing page"}).json()
    task = res["task"]
    assert task["title"] == "Create a landing page"
    assert task["status"] == "waiting_input"  # asks its questions first
    clarify = {s["kind"]: s for s in task["steps"]}["clarify"]
    asked = {q["id"]: q for q in clarify["output"]["questions"]}
    assert asked["folder"]["default"] == str(env.repo)  # existing project: its own folder
    assert "stack" not in asked  # stack is known for an existing project
    assert "style" in asked  # a landing page is UI work

    client.post(f"/tasks/{task['id']}/answer", json={"answers": {"features": "pricing table\nFAQ"}})
    task = client.get(f"/tasks/{task['id']}").json()["task"]
    assert task["status"] == "waiting_approval"  # stopped before the hand-off
    assert env.sent == {}  # nothing was sent before approval
    steps = {s["kind"]: s for s in task["steps"]}
    assert steps["context"]["status"] == "done" and steps["prompt"]["status"] == "done"
    prompt = steps["prompt"]["output"]["prompt"]
    assert "landing page" in prompt and "Stack:" in prompt and "STRIPE_SECRET_KEY" in prompt
    assert "pricing table" in prompt and f"All files go in: {env.repo}" in prompt

    client.post(f"/tasks/{task['id']}/approve")  # approve hand-off → watch → stops at verify
    task = client.get(f"/tasks/{task['id']}").json()["task"]
    assert env.sent["tool"] == "antigravity" and env.sent["params"]["repo_path"] == str(env.repo)
    steps = {s["kind"]: s for s in task["steps"]}
    assert steps["watch"]["output"]["changed_files"] == ["src\\Landing.tsx"] or steps["watch"]["output"]["changed_files"] == ["src/Landing.tsx"]
    assert task["status"] == "waiting_approval" and steps["verify"]["status"] == "waiting_approval"
    assert env.ran == []  # build not run before approval

    client.post(f"/tasks/{task['id']}/approve")
    task = client.get(f"/tasks/{task['id']}").json()["task"]
    assert task["status"] == "done"
    assert env.ran == [("npm run build", str(env.repo))]
    needs = {n["var"] for n in task["needs"]}
    assert {"STRIPE_SECRET_KEY", "DATABASE_URL", "RESEND_API_KEY"} <= needs
    report = {s["kind"]: s for s in task["steps"]}["report"]["output"]["message"]
    assert "1 files changed" in report and "STRIPE_SECRET_KEY" in report


def test_cancel_stops_waiting_task(env):
    task = client.post("/tasks", json={"project_id": "p1", "agent": "claude", "request": "add auth with claude"}).json()["task"]
    assert client.post(f"/tasks/{task['id']}/cancel").json()["success"] is True
    assert client.post(f"/tasks/{task['id']}/approve").status_code == 409
    assert env.sent == {}


def test_new_project_asks_where_to_save_and_uses_the_answers(env, tmp_path):
    task = client.post("/tasks", json={"agent": "antigravity",
                                       "request": "using antigravity make a portfolio website"}).json()["task"]
    assert task["status"] == "waiting_input"
    asked = {q["id"]: q for q in {s["kind"]: s for s in task["steps"]}["clarify"]["output"]["questions"]}
    assert asked["folder"]["question"] == "Where should the new project be saved?"
    assert asked["folder"]["default"].endswith("portfolio-website")
    assert "stack" in asked

    # Bad answers are refused and the task keeps waiting.
    bad = client.post(f"/tasks/{task['id']}/answer", json={"answers": {"folder": "relative\\path"}})
    assert bad.status_code == 422 and "full folder path" in bad.json()["detail"]
    assert env.sent == {}

    target = tmp_path / "Projects" / "folio"
    ok = client.post(f"/tasks/{task['id']}/answer", json={"answers": {
        "folder": str(target), "stack": "React + Vite", "style": "dark, minimal", "features": "",
    }}).json()
    assert ok["success"] is True and target.is_dir()  # folder created after the user chose it
    task = client.get(f"/tasks/{task['id']}").json()["task"]
    steps = {s["kind"]: s for s in task["steps"]}
    prompt = steps["prompt"]["output"]["prompt"]
    assert f"All files go in: {target}" in prompt
    assert "React + Vite" in prompt and "dark, minimal" in prompt
    assert "New project in" in prompt
    client.post(f"/tasks/{task['id']}/approve")
    assert env.sent["params"]["repo_path"] == str(target)


def test_answer_only_when_waiting(env):
    task = client.post("/tasks", json={"project_id": "p1", "agent": "claude", "request": "add auth"}).json()["task"]
    assert client.post(f"/tasks/{task['id']}/answer", json={}).json()["success"] is True  # defaults
    again = client.post(f"/tasks/{task['id']}/answer", json={})
    assert again.status_code == 422


@pytest.mark.parametrize("request_text,title", [
    ("using antigravity create a single hello.html page with a heading", "Create a single hello.html page with a heading"),
    ("add login with google using claude code", "Add login with google"),
    ("in vs code add a dark mode toggle", "Add a dark mode toggle"),
])
def test_titles_drop_only_the_agent_phrase(request_text, title):
    assert engine._title(request_text, "x") == title


def test_unknown_agent_rejected(env):
    assert client.post("/tasks", json={"project_id": "p1", "agent": "notepad", "request": "x"}).status_code == 422


def test_resolve_need_into_env_file_and_keyring(env, monkeypatch):
    from tasks.needs import collect_needs

    needs = {n["var"]: n for n in collect_needs("p1")}
    saved = {}
    monkeypatch.setattr("keyring.set_password", lambda svc, var, value: saved.update({(svc, var): value}))

    body = client.post(f"/needs/{needs['STRIPE_SECRET_KEY']['id']}/resolve",
                       json={"save_to": "both", "value": "sk_test_123"}).json()
    assert body["success"] is True and body["warnings"] == []
    assert saved == {("AUTOMATA:p1", "STRIPE_SECRET_KEY"): "sk_test_123"}
    assert "STRIPE_SECRET_KEY=sk_test_123" in (env.repo / ".env").read_text()
    # value never stored in AUTOMATA's own databases
    dumped = json.dumps(env.store.list_needs(project_id="p1", status=None))
    assert "sk_test_123" not in dumped
    # once set, a rescan no longer reports it
    assert "STRIPE_SECRET_KEY" not in {n["var"] for n in collect_needs("p1")}


def test_resolve_need_manual_and_validation(env):
    from tasks.needs import collect_needs

    need = next(n for n in collect_needs("p1") if n["var"] == "DATABASE_URL")
    assert client.post(f"/needs/{need['id']}/resolve", json={"save_to": "env_file"}).status_code == 422
    assert client.post(f"/needs/{need['id']}/resolve", json={"save_to": "done"}).json()["resolution"] == "manual"


def test_chat_delegation_creates_task(env, monkeypatch):
    body = client.post("/chat", json={"project_id": "p1", "message": "using antigravity build a pricing page"}).json()
    assert body["intent"] == "delegate_task"
    assert "Created task" in body["reply"]
    assert env.store.list_tasks("p1")[0]["agent"] == "antigravity"


def test_interrupted_tasks_are_paused(env):
    tid = env.store.create_task("p1", "t", "r", "claude", [{"kind": "report", "title": "Report"}])
    env.store.update_task(tid, status="running")
    engine.recover_interrupted()
    assert env.store.get_task(tid)["status"] == "paused"


def test_stale_needs_close_and_settings_are_not_needs(env):
    from tasks.needs import collect_needs

    first = {n["var"] for n in collect_needs("p1")}
    assert "STRIPE_SECRET_KEY" in first
    # the project stops using Stripe
    (env.repo / ".env.example").write_text("DATABASE_URL=\nAPP_PORT=\n")
    second = {n["var"] for n in collect_needs("p1")}
    assert "STRIPE_SECRET_KEY" not in second
    assert "APP_PORT" not in second  # plain setting, not a need
    assert "DATABASE_URL" in second
