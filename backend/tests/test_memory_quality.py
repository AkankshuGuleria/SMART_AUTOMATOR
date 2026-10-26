"""
tests/test_memory_quality.py — memory must stay duplicate-free and answer the right thing.

Regression tests for the 2026-10-26 audit:
  H1  terminal capture re-imported the whole PowerShell history on every start;
  H2  "what did I change in the desktop automation code?" returned five copies of
      "# Change to project folder" instead of the desktop.py edits.

In-memory SQLite only; no DB, network, providers or real history file.
"""

import time

import pytest

from memory import local_store
from memory.capture import TerminalCaptureThread
from memory.local_store import LocalStore

PID = "p1"
DAY = 86400


@pytest.fixture
def store():
    s = LocalStore(":memory:")
    local_store.set_store(s)
    s.upsert_project({"id": PID, "name": "Demo", "repo_path": r"D:\Demo"})
    yield s
    local_store.set_store(None)
    s.close()


def _realistic_memory(s: LocalStore) -> None:
    """A slice of a real developer's memory: lots of terminal noise, a few relevant edits."""
    now = time.time()
    for i in range(40):  # terminal noise, including the line that used to win
        s.record(PID, "terminal", "# Change to project folder", created_at=now - i * 60)
        s.record(PID, "terminal", f"cd D:\\Demo\\sub{i % 5}", created_at=now - i * 60)
        s.record(PID, "terminal", "git status", created_at=now - i * 60)
    s.record(PID, "terminal", "Set-Location D:\\Demo  # change dir", created_at=now - 300)
    s.record(PID, "file_edit", r"Edited backend\automation\desktop.py", created_at=now - 3600)
    s.record(PID, "file_edit", r"Edited backend\automation\win32.py", created_at=now - 3700)
    s.record(PID, "file_edit", r"Edited frontend\src\screens\Dashboard.tsx", created_at=now - 3800)
    s.record(PID, "file_edit", r"Edited backend\memory\local_store.py", created_at=now - 3900)
    s.record(PID, "commit", "Commit 1a2b3c4d: Phase 0: verified desktop focus, paste and OCR read-back",
             ref="1a2b3c4d", created_at=now - 7200)
    s.record(PID, "commit", "Commit 5e6f7a8b: Add app usage tracker", ref="5e6f7a8b", created_at=now - 9000)
    s.record(PID, "decision", "Decision: Planned action: update_project_summary — commit detected",
             created_at=now - 100)


# ── H2: retrieval quality ────────────────────────────────────────────────────


def test_question_about_desktop_automation_finds_the_edits_not_terminal_noise(store):
    _realistic_memory(store)
    hits = store.search("What did I change in the desktop automation code recently?", project_id=PID, limit=6)
    top3 = [h["content"] for h in hits[:3]]
    assert r"Edited backend\automation\desktop.py" in top3
    assert any("desktop focus" in c for c in top3)
    assert not any(c.startswith("#") for c in top3), top3


def test_search_results_never_repeat_the_same_memory(store):
    _realistic_memory(store)
    # Simulate rows that slipped in before de-duplication existed.
    for _ in range(5):
        store._conn.execute(
            "INSERT INTO memories(project_id, kind, content, created_at) VALUES (?, 'terminal', ?, ?)",
            (PID, "git status", time.time()),
        )
    hits = store.search("git status", project_id=PID, limit=8)
    contents = [h["content"] for h in hits]
    assert contents.count("git status") == 1
    assert len(contents) == len(set(contents))


def test_terminal_rows_rank_first_when_the_question_is_about_commands(store):
    _realistic_memory(store)
    hits = store.search("which git command did I run?", project_id=PID, limit=3)
    assert hits[0]["content"] == "git status"


def test_unrelated_question_finds_nothing(store):
    _realistic_memory(store)
    assert store.search("kubernetes helm chart for billing", project_id=PID) == []


def test_grounded_query_sends_distinct_relevant_memories_to_the_model(store, monkeypatch):
    import api.server as server

    _realistic_memory(store)
    seen = {}

    def fake_reasoning(system_prompt, user_message, retrieved_memories, reasoning_mode=None):
        seen["memories"] = retrieved_memories
        return "You edited desktop.py and win32.py."

    monkeypatch.setattr("ai.bedrock_client.invoke_reasoning", fake_reasoning)
    # Cloud returns a copy of a local row plus duplicates of noise: none may repeat.
    monkeypatch.setattr(
        "memory.retrieval.retrieve_by_vector",
        lambda *a, **k: [{"content": "# Change to project folder", "relevance": 0.99}] * 3
        + [{"content": r"Edited backend\automation\desktop.py", "relevance": 0.9}],
    )
    reply, sources, ok = server._grounded_query("What did I change in the desktop automation code recently?", PID)
    contents = [" ".join(str(m.get("content")).split()).lower() for m in seen["memories"]]
    assert ok is True
    assert len(contents) == len(set(contents)), contents
    assert any("desktop.py" in c for c in contents[:3])


# ── de-duplicated writes ─────────────────────────────────────────────────────


def test_same_terminal_command_is_stored_once_and_its_time_moves_forward(store):
    first = store.record(PID, "terminal", "npm test", created_at=time.time() - DAY)
    again = store.record(PID, "terminal", "npm   test")
    assert first is not None and again is None
    rows = store.recent(PID, kinds=["terminal"])
    assert len(rows) == 1 and rows[0]["created_at"] > time.time() - 60


def test_file_edits_are_kept_once_per_day(store):
    now = time.time()
    store.record(PID, "file_edit", r"Edited src\app.py", created_at=now)
    store.record(PID, "file_edit", r"File modified: D:\Demo\src\app.py", created_at=now)  # cloud wording
    store.record(PID, "file_edit", r"Edited src\app.py", created_at=now - 3 * DAY)
    assert store.counts(PID)["file_edit"] == 2


def test_local_and_cloud_copies_of_a_commit_merge_but_different_commits_do_not(store):
    store.record(PID, "commit", "Commit 1a2b3c4d: wip", ref="1a2b3c4d9")
    store.record(PID, "commit", "Commit 1a2b3c4d: wip", ref="db:commits:uuid-1")  # cloud mirror
    store.record(PID, "commit", "Commit 99887766: wip", ref="99887766aa")  # same message, other commit
    assert store.counts(PID)["commit"] == 2


def test_chat_turns_are_not_deduplicated(store):
    store.record(PID, "chat", "User: what's next?")
    store.record(PID, "chat", "User: what's next?")
    assert store.counts(PID)["chat"] == 2


def test_migration_removes_existing_duplicates_once(tmp_path):
    path = tmp_path / "memory.db"
    old = LocalStore(path)
    old.upsert_project({"id": PID, "name": "Demo", "repo_path": r"D:\Demo"})
    old._conn.execute("DELETE FROM kv WHERE key = 'migration:dedup_v1'")
    rows = [("terminal", "git status")] * 6 + [("terminal", "npm test")] * 2 + [
        ("commit", "Commit 1a2b3c4d: Add login"), ("commit", "Commit: Add login"),
        ("commit", "Commit: Other change"), ("chat", "hi"), ("chat", "hi"),
    ]
    for i, (kind, content) in enumerate(rows):
        old._conn.execute(
            "INSERT INTO memories(project_id, kind, content, created_at) VALUES (?, ?, ?, ?)",
            (PID, kind, content, 1000.0 + i),
        )
    old.close()

    s = LocalStore(path)
    assert s.counts(PID) == {"terminal": 2, "commit": 2, "chat": 2}
    commits = sorted(r["content"] for r in s.recent(PID, kinds=["commit"]))
    assert commits == ["Commit 1a2b3c4d: Add login", "Commit: Other change"]
    newest_git = [r for r in s.recent(PID, kinds=["terminal"]) if r["content"] == "git status"][0]
    assert newest_git["created_at"] == 1005.0  # moved to the latest occurrence
    assert s.get_value("migration:dedup_v1")["removed"] == 7  # 5 + 1 terminal, 1 hashless commit
    s.close()
    assert LocalStore(path).counts(PID)["terminal"] == 2  # second open is a no-op


# ── H1: terminal capture only takes new history lines ────────────────────────


class _Capture(TerminalCaptureThread):
    def __init__(self):
        super().__init__(project_id=PID, project_path=r"D:\Demo")
        self.written: list[str] = []

    def _write_command(self, command: str) -> None:
        self.written.append(command)


def test_first_run_does_not_import_old_history(store, tmp_path):
    hist = tmp_path / "ConsoleHost_history.txt"
    hist.write_text("git status\nnpm test\n", encoding="utf-8")
    cap = _Capture()
    cap._poll(hist)
    assert cap.written == []
    hist.write_text("git status\nnpm test\nuv run pytest\n", encoding="utf-8")
    cap._poll(hist)
    assert cap.written == ["uv run pytest"]


def test_restarting_capture_does_not_reimport(store, tmp_path):
    hist = tmp_path / "ConsoleHost_history.txt"
    hist.write_text("a1\n", encoding="utf-8")
    first = _Capture()
    first._poll(hist)
    hist.write_text("a1\ngit log\n", encoding="utf-8")
    first._poll(hist)
    assert first.written == ["git log"]

    restarted = _Capture()  # app restart / project switch
    restarted._poll(hist)
    assert restarted.written == []
    hist.write_text("a1\ngit log\nnpm run build\n", encoding="utf-8")
    restarted._poll(hist)
    assert restarted.written == ["npm run build"]


def test_trimmed_history_continues_after_last_read_line(store, tmp_path):
    hist = tmp_path / "ConsoleHost_history.txt"
    hist.write_text("old1\nold2\nlast-read\n", encoding="utf-8")
    cap = _Capture()
    cap._poll(hist)
    # PSReadLine trimmed the oldest lines and two new commands were added.
    hist.write_text("last-read\nnew one\nnew two\n", encoding="utf-8")
    cap._poll(hist)
    assert cap.written == ["new one", "new two"]


def test_shell_comments_are_not_captured(store, tmp_path):
    hist = tmp_path / "ConsoleHost_history.txt"
    hist.write_text("", encoding="utf-8")
    cap = _Capture()
    cap._poll(hist)
    hist.write_text("# Change to project folder\ncd D:\\Demo\n", encoding="utf-8")
    cap._poll(hist)
    assert cap.written == ["cd D:\\Demo"]
