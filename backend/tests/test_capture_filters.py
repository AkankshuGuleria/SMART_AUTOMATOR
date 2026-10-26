"""
tests/test_capture_filters.py — file watcher must ignore generated folders.

Regression: the watcher recorded every file under node_modules/.venv/.git,
so one `npm install` produced thousands of file_edits rows.
"""

import os
import time

from memory.capture import FileWatcherThread, is_ignored_path

ROOT = os.path.join("D:", os.sep, "proj")


def p(*parts):
    return os.path.join(ROOT, *parts)


def test_generated_and_vendor_paths_are_ignored():
    for path in (
        p("frontend", "node_modules", "react", "index.js"),
        p("backend", ".venv", "Lib", "site-packages", "x.py"),
        p(".git", "config.json"),
        p("frontend", "dist", "assets", "index.js"),
        p("frontend", "src-tauri", "target", "release", "a.json"),
        p("backend", "__pycache__", "m.py"),
        p("frontend", "package-lock.json"),
        p("frontend", "dist2", "bundle.min.js"),
    ):
        assert is_ignored_path(path, ROOT), path


def test_source_paths_are_kept():
    for path in (
        p("backend", "api", "server.py"),
        p("frontend", "src", "App.tsx"),
        p("docs", "README.md"),
        p("distribution.py"),  # name only resembles "dist"
    ):
        assert not is_ignored_path(path, ROOT), path


def test_watcher_debounces_and_filters(monkeypatch):
    watcher = FileWatcherThread(project_id="p", project_path=ROOT)
    written = []
    monkeypatch.setattr(watcher, "_write_file_edit", lambda path, summary: written.append(path))
    monkeypatch.setattr("memory.capture.os.path.getmtime", lambda path: time.time())

    watcher._on_file_changed(p("frontend", "node_modules", "a.js"))
    watcher._on_file_changed(p("src", "app.py"))
    watcher._on_file_changed(p("src", "app.py"))  # saved again within the window
    watcher._on_file_changed(p("src", "image.png"))  # unwatched extension

    assert written == [p("src", "app.py")]


def test_watcher_ignores_events_where_content_did_not_change(monkeypatch):
    # Windows reports last-access / attribute updates as "modified" when a file
    # is merely read (project scans, grep, indexers). Those are not edits.
    watcher = FileWatcherThread(project_id="p", project_path=ROOT)
    written = []
    monkeypatch.setattr(watcher, "_write_file_edit", lambda path, summary: written.append(path))
    monkeypatch.setattr("memory.capture.os.path.getmtime", lambda path: time.time() - 3600)
    watcher._on_file_changed(p("docs", "README.md"))
    assert written == []


def test_tauri_generated_schemas_are_ignored():
    assert is_ignored_path(p("frontend", "src-tauri", "gen", "schemas", "desktop-schema.json"), ROOT)
    assert not is_ignored_path(p("frontend", "src-tauri", "src", "lib.rs"), ROOT)
