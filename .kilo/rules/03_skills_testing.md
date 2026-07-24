# AUTOMATA — Testing Skill (SKILLS.md §1)

**Apply before marking any feature done. Apply before every commit to `backend/` or `frontend/`.**

## Checklist
- [ ] Unit tests for pure logic — **no live DB or Bedrock calls**
- [ ] Integration tests use a local/test CockroachDB — never point at production data
- [ ] Mock Bedrock responses in Reasoning Engine tests — don't burn real API calls in CI
- [ ] Automation Layer tests use the stubbed OS interface — never actually launch apps in CI
- [ ] At least one end-to-end test per demo step (`PROJECT.md §13`), run manually before milestone
- [ ] After any schema change: re-run retrieval tests to confirm vector search returns expected top-k

## Where tests live
- `backend/tests/` — pytest, no live network calls
- Frontend: Vitest (to be added in Phase 6)

## Run tests
```powershell
cd backend && uv run pytest tests/ -v --tb=short
```

## Common failure modes to AVOID
- Tests that only check "no exception thrown" — check actual returned content
- Flaky tests due to real network calls — mock/fixture everything external
- Skipping retrieval-quality testing — a vector search that returns wrong memories is worse than one that visibly fails
