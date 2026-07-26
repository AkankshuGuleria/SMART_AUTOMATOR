#!/usr/bin/env python3
import sys
sys.path.insert(0, 'backend')
from db.client import get_projects

def main():
    projects = get_projects()
    if projects:
        print("Existing projects:")
        for project in projects:
            print(f"  - {project['id']} ({project['name']})")
    else:
        print("No projects found")

if __name__ == "__main__":
    main()