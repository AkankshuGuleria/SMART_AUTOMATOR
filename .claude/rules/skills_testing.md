# Testing skill — AUTOMATA

## When to use
Before marking any feature done and before every commit touching `backend/` or `frontend/`.

## Checklist
- [ ] Unit tests: pure logic, **no live DB, model provider, keyboard or screen** —
      `backend/tests/conftest.py` isolates these; mock `automation.win32` / `desktop.capture`
- [ ] Assert real outputs and failure states, not just "no exception thrown"
- [ ] Security-relevant change → regression test in `backend/tests/test_permissions.py`
- [ ] Retrieval change → `backend/tests/test_memory_quality.py` still green (wrong memories are worse than none)
- [ ] UI change → `npx tsc -b`, `npx oxlint src`, `npm test`; check it in the running app
- [ ] Desktop-control change → also verify live against a throwaway window/folder

## Run
```powershell
cd backend;  uv run pytest tests/ -q
cd frontend; npx tsc -b; npx oxlint src; npm test
```

## Failure modes to avoid
- Flaky tests from real network calls — mock everything external
- Tests that press real keys or read the real screen (the kill switch
  `AUTOMATA_DISABLE_DESKTOP_INPUT=1` is set in conftest; keep it)
