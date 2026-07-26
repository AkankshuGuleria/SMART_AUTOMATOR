"""
create_sample_project.py — Insert a sample project and output its UUID.

Owns:   Helper to create a project record for placeholder replacement.
Never:  Does not modify any other data.
Ref:    DATABASE_SCHEMA.md §23 (projects table), ARCHITECTECTURE.md §3.2.
"""
from db.client import insert_project

def main():
    # Use placeholder values; adjust repo_path as needed.
    name = "sample-project"
    repo_path = "C:/Users/Developer/projects/sample-project"
    remote_url = "https://github.com/example/sample-project.git"

    project_id = insert_project(name, repo_path, remote_url)
    if project_id:
        print(project_id)
    else:
        print("Failed to insert project")

if __name__ == "__main__":
    main()
