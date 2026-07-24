# Testing Skill — AUTOMATA (SKILLS.md §1)

## When to use
Before marking any feature done. Before every commit touching `backend/` or `frontend/`.

## Checklist
- [ ] Unit tests: pure logic only — **zero live DB or Bedrock calls**
- [ ] Integration tests: use local/test CockroachDB — never production data
- [ ] Reasoning Engine tests: mock Bedrock — no real API calls in CI
- [ ] Automation Layer tests: use stubbed OS interface — never actually launch apps
- [ ] End-to-end: at least one test per demo step (`PROJECT.md §13`), run manually before milestone
- [ ] After schema change: re-run retrieval tests to confirm vector search top-k results unchanged

## Run
```powershell
cd backend && uv run pytest tests/ -v --tb=short
```

## Failure modes to avoid
- Checking only "no exception thrown" — check actual content
- Flaky tests from real network calls — mock everything external
- Skipping retrieval quality testing — wrong memories are worse than visible failures
