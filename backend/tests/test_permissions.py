"""
tests/test_permissions.py — AUTOMATA asks before it controls the PC.

Approvals are server-issued, single-use, bound to the exact action, and expire;
"always allow" is per category. Also: Resume reopens the editor the user last used.
"""

import time

import pytest
from fastapi.testclient import TestClient

from api.server import app
from memory import local_store
from memory.local_store import LocalStore
from security import permissions

client = TestClient(app)


@pytest.fixture(autouse=True)
def store():
    s = LocalStore(":memory:")
    local_store.set_store(s)
    permissions.reset_for_tests()
    yield s
    local_store.set_store(None)
    s.close()


def test_every_category_asks_by_default():
    assert all(p["mode"] == "ask" for p in permissions.get_policies())
    req = permissions.check("media", "Pause what is playing")
    assert req and req["label"] == "Control music and volume" and req["id"]


def test_approval_is_single_use_and_bound_to_the_action():
    req = permissions.check("launch", "Open https://a.example in your browser")
    assert not permissions.consume(req["id"], "launch", "Open https://evil.example in your browser")
    assert not permissions.consume(req["id"], "screen", "Open https://a.example in your browser")
    assert permissions.consume(req["id"], "launch", "Open https://a.example in your browser")
    assert not permissions.consume(req["id"], "launch", "Open https://a.example in your browser")


def test_made_up_ids_are_rejected():
    assert permissions.check("system", "Run `rm -rf /`", permission_id="approved") is not None


def test_approvals_expire(monkeypatch):
    req = permissions.check("screen", "Read the screen")
    real = time.time
    monkeypatch.setattr(permissions.time, "time", lambda: real() + permissions.REQUEST_TTL_S + 1)
    assert not permissions.consume(req["id"], "screen", "Read the screen")


def test_always_allow_per_category():
    permissions.set_policy("media", "allow")
    assert permissions.check("media", "Pause") is None
    assert permissions.check("screen", "Read the screen") is not None
    with pytest.raises(ValueError):
        permissions.set_policy("everything", "allow")


def test_planner_policy_follows_the_users_choice():
    assert permissions.effective_policy("chat_open_app", "auto_execute") == "confirm_once"
    permissions.set_policy("launch", "allow")
    assert permissions.effective_policy("chat_open_app", "auto_execute") == "auto_execute"
    assert permissions.effective_policy("submit_prompt_to_app", "require_approval") == "require_approval"
    assert permissions.effective_policy("chat_query_memory", "auto_execute") == "auto_execute"


def test_permissions_api_round_trip():
    body = client.get("/permissions").json()["permissions"]
    assert {p["category"] for p in body} == set(permissions.CATEGORIES)
    assert client.post("/permissions", json={"category": "media", "mode": "allow"}).json()["mode"] == "allow"
    assert client.post("/permissions", json={"category": "media", "mode": "yes"}).status_code == 422


@pytest.mark.parametrize("path,payload,category", [
    ("/desktop/focus", {"app": "notepad"}, "app_control"),
    ("/desktop/type", {"text": "hi", "app": "notepad"}, "app_control"),
    ("/desktop/tabs/switch", {"title": "GitHub"}, "app_control"),
    ("/desktop/read", {"app": "notepad"}, "screen"),
    ("/assist/media", {"action": "next"}, "media"),
    ("/assist/screen", {}, "screen"),
    ("/execute/open_browser", {"url": "https://example.com"}, "launch"),
])
def test_desktop_routes_ask_first(path, payload, category, monkeypatch):
    # Anything that would really act must not run before approval.
    monkeypatch.setattr("automation.desktop.focus", lambda *a, **k: pytest.fail("focused without permission"))
    monkeypatch.setattr("automation.desktop.type_text", lambda *a, **k: pytest.fail("typed without permission"))
    monkeypatch.setattr("automation.os_windows.launch_browser", lambda *a, **k: pytest.fail("opened without permission"))
    body = client.post(path, json=payload).json()
    assert body["needs_permission"]["category"] == category


def test_external_agent_prompt_ignores_self_approval(monkeypatch):
    monkeypatch.setattr("automation.agent_bridge.AgentBridge.send_prompt",
                        lambda *a, **k: pytest.fail("sent without the user's approval"))
    body = client.post("/external-agents/claude/prompt", json={"prompt": "hi", "approved": True}).json()
    assert body["needs_permission"]["category"] == "app_control"


def test_command_execution_needs_the_users_approval(monkeypatch):
    ran = []
    monkeypatch.setattr("automation.command_executor.subprocess.run", lambda *a, **k: ran.append(a) or pytest.fail())
    body = client.post("/commands/execute", json={"command": "echo hi", "project_id": "p", "allow_execute": True}).json()
    assert body["status"] == "needs_permission" and ran == []


# ─── Resume reopens the editor the user last used ────────────────────────────


def test_workspace_folder_from_editor_titles(tmp_path):
    from workspace.snapshot import _workspace_folder

    (tmp_path / "vite-project").mkdir()
    repo = str(tmp_path)
    name = tmp_path.name
    assert _workspace_folder(f"App.css - {name} - Visual Studio Code", repo) == repo
    assert _workspace_folder("vite-project - Antigravity IDE - App.jsx", repo) == str(tmp_path / "vite-project")
    assert _workspace_folder("● main.py - other - Visual Studio Code", repo) is None


def test_last_editor_prefers_newest_usage_history(tmp_path, monkeypatch):
    import sqlite3

    from workspace import snapshot

    db = tmp_path / "usage.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE usage_segments (id INTEGER PRIMARY KEY, app TEXT, exe TEXT, title TEXT, "
                 "category TEXT, started_at REAL, ended_at REAL)")
    repo = tmp_path / "shop"
    repo.mkdir()
    now = time.time()
    conn.executemany("INSERT INTO usage_segments(app, exe, title, category, started_at, ended_at) VALUES (?,?,?,?,?,?)", [
        ("VS Code", "Code.exe", "index.ts - shop - Visual Studio Code", "Code", now - 7200, now - 7000),
        ("Antigravity IDE", "Antigravity IDE.exe", "shop - Antigravity IDE - app.ts", "Code", now - 600, now - 500),
        ("VS Code", "Code.exe", "notes - other - Visual Studio Code", "Code", now - 60, now - 30),
    ])
    conn.commit()
    conn.close()
    monkeypatch.setattr("monitoring.app_usage.default_db_path", lambda: db)
    monkeypatch.setattr(snapshot, "_editor_windows", lambda: [])
    found = snapshot.last_editor("p1", str(repo))
    assert found["app"] == "Antigravity IDE" and found["folder"] == str(repo)


# ─── Local-only API guard ────────────────────────────────────────────────────


def test_dns_rebinding_host_is_refused():
    r = client.get("/health", headers={"host": "attacker.example"})
    assert r.status_code == 403


def test_foreign_origin_is_refused_even_without_a_body():
    r = client.post("/workspace/snapshot-active", headers={"origin": "https://evil.example"})
    assert r.status_code == 403
    r = client.get("/memory/stats", headers={"origin": "https://evil.example"})
    assert r.status_code == 403


def test_cross_site_fetch_metadata_is_refused():
    r = client.get("/health", headers={"sec-fetch-site": "cross-site"})
    assert r.status_code == 403


def test_the_app_and_local_tools_still_work():
    assert client.get("/health", headers={"origin": "http://tauri.localhost"}).status_code == 200
    assert client.get("/health", headers={"origin": "http://localhost:5173"}).status_code == 200
    assert client.get("/health").status_code == 200  # curl / tray menu: no Origin
    pre = client.options("/health", headers={"origin": "http://tauri.localhost",
                                             "access-control-request-method": "GET"})
    assert pre.headers.get("access-control-allow-origin") == "http://tauri.localhost"
    assert "access-control-allow-credentials" not in pre.headers


def test_oversized_bodies_are_refused():
    r = client.post("/assist", content=b"x", headers={"content-length": str(20 * 1024 * 1024),
                                                      "content-type": "application/json"})
    assert r.status_code == 413


def test_websocket_from_a_foreign_site_is_refused():
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws", headers={"origin": "https://evil.example"}) as ws:
            ws.receive_text()


def test_workflow_checkpoint_ids_cannot_escape_the_folder():
    from workflow_engine.checkpoint_store import load_checkpoint

    assert load_checkpoint(r"..\..\windows", "x") is None
    assert load_checkpoint("run1", "../../etc/passwd") is None


# ─── .env writing cannot inject extra variables ──────────────────────────────


def test_env_values_cannot_inject_lines(tmp_path):
    from tasks.needs import _write_env

    env = tmp_path / ".env"
    with pytest.raises(ValueError):
        _write_env(str(env), "API_KEY", "abc\nNODE_OPTIONS=--require=evil.js")
    with pytest.raises(ValueError):
        _write_env(str(env), "BAD NAME", "x")
    with pytest.raises(ValueError):
        _write_env(str(tmp_path / "config.py"), "API_KEY", "x")
    _write_env(str(env), "API_KEY", r'p"a\ss word')
    assert env.read_text() == r'API_KEY="p\"a\\ss word"' + "\n"
