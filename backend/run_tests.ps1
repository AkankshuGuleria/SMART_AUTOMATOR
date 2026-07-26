cd D:\AUTOMATA\backend
uv run pytest tests/ -v --tb=short 2>&1 | Tee-Object -FilePath pytest_output.txt
Get-Content pytest_output.txt