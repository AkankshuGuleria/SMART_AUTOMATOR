"""
tests/test_restore_reporting.py — restore must report failures honestly and
must not launch apps when the project folder is missing. OS calls are mocked.
"""

from unittest.mock import patch

from automation import restore


def test_missing_folder_stops_before_launching_anything():
    with (
        patch.object(
            restore, "get_project", return_value={"id": "p", "repo_path": "SAM_MOTO_FINAL"}
        ),
        patch.object(restore, "open_terminal") as term,
        patch.object(restore, "start_project_dev_servers") as servers,
    ):
        result = restore.restore_workspace("p")
    assert result["overall"] == "error"
    assert result["steps"][0]["status"] == "error"
    assert "Repo path not found" in result["steps"][0]["detail"]
    assert {s["status"] for s in result["steps"][1:]} == {"skipped"}
    term.assert_not_called()
    servers.assert_not_called()


def test_dev_server_detail_is_readable_and_all_skipped_is_not_error(tmp_path):
    servers = [
        {"server": "frontend", "status": "skipped", "detail": "no package.json found"},
        {"server": "backend", "status": "skipped", "detail": "no pyproject.toml found"},
    ]
    with (
        patch.object(restore, "get_project", return_value={"id": "p", "repo_path": str(tmp_path)}),
        patch.object(restore, "open_terminal", return_value=True),
        patch.object(restore, "start_project_dev_servers", return_value=servers),
        patch.object(restore, "launch_editor", return_value=True, create=True),
    ):
        result = restore.restore_workspace("p")
    dev = next(s for s in result["steps"] if s["step"] == "dev_servers")
    assert dev["status"] == "skipped"
    assert (
        dev["detail"]
        == "frontend: skipped (no package.json found); backend: skipped (no pyproject.toml found)"
    )
    assert "[{" not in dev["detail"]
