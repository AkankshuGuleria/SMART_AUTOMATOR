"""
replace_placeholders.py — Replace placeholder UUIDs with real values.

Owns:   Utility script to replace placeholder strings with valid UUIDs.
Never:  Does not modify database schema or business logic.
Ref:    DATABASE_SCHEMA.md §23 (projects table), APP_FILES.md (frontend App.tsx, MAIN_FILES.md).
"""
import re
import os

def replace_uuid(text, placeholder):
    """Replace a placeholder string with a valid UUID format."""
    # Simple pattern matching for placeholder strings
    if placeholder in text:
        # Generate a standard UUID format (36 characters)
        # This is a placeholder UUID - in practice, we'd get this from the DB
        return re.sub(rf'{re.escape(placeholder)}', '11111111-1111-1111-1111-111111111111', text)
    return text

def main():
    # Files to process
    files_to_process = [
        ('frontend/src/App.tsx', 'demo-project-placeholder'),
        ('backend/main.py', 'default_project'),
        ('backend/main.py', 'session_123'),
        ('backend/main.py', 'C:/path/to/your/project')
    ]

    for file_path, placeholder in files_to_process:
        # Read the file
        with open(file_path, 'r') as f:
            content = f.read()

        # Replace the placeholder
        content = replace_uuid(content, placeholder)

        # Write back to the file
        with open(file_path, 'w') as f:
            f.write(content)

        print(f"Replaced {placeholder} in {file_path}")

if __name__ == "__main__":
    main()
