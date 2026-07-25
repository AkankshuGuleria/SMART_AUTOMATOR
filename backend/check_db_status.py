import logging
from db.client import get_session
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)

def main():
    with get_session() as session:
        if session is None:
            print("DB is not configured or unavailable")
            return
        
        # Get projects
        projects = session.execute(
            text("SELECT id, name, repo_path, remote_url FROM projects")
        ).fetchall()
        print("Projects in database:")
        for p in projects:
            print(f"  - ID: {p[0]} | Name: {p[1]} | Path: {p[2]} | URL: {p[3]}")
            
        # Get sessions
        sessions = session.execute(
            text("SELECT id, project_id, started_at, ended_at FROM sessions")
        ).fetchall()
        print("Sessions in database:")
        for s in sessions:
            print(f"  - ID: {s[0]} | Project ID: {s[1]} | Started: {s[2]} | Ended: {s[3]}")

        # Get counts for other tables
        for table in ["commits", "file_edits", "terminal_commands", "todos"]:
            count = session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            print(f"Total {table}: {count}")

if __name__ == "__main__":
    # Test comment version 2 to trigger file watcher
    main()
