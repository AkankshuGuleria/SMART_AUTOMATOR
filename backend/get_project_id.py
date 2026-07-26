"""
get_project_id.py — Retrieve a project UUID from CockroachDB for use in placeholders.

Owns:   Helper script to fetch a real project ID.
Never:  Does not modify the DB, only reads.
Ref:    DATABASE_SCHEMA.md §23 (projects table), ARCHITECTURE.md §3.2.
"""
from sqlalchemy import text

from db.client import get_session


def main():
    with get_session() as session:
        # Fetch the first project ID (any project is fine for placeholder replacement)
        result = session.execute(text("SELECT id FROM projects LIMIT 1"))
        project_id = result.scalar()
        if project_id:
            print(project_id)
        else:
            print("No projects found")

if __name__ == "__main__":
    main()