import os
import re

# Real UUID from API
real_uuid = "0f90c2f9-0d9a-4787-ab07-8d4699fb4b13"
placeholder = "11111111-1111-1111-1111-111111111111"

# Files to process
files = [
    "frontend/src/App.tsx",
    "backend/main.py"
]

for file_rel in files:
    file_path = os.path.join(os.getcwd(), file_rel)
    with open(file_path, 'r') as f:
        content = f.read()

    # Replace placeholder with real UUID (including quotes)
    content = re.sub(rf"'{placeholder}'", f"'{real_uuid}'", content)

    with open(file_path, 'w') as f:
        f.write(content)

    print(f"Updated {file_rel}")
