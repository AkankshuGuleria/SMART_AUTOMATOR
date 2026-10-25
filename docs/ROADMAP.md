# MVP stabilization roadmap

## Current phase

**MVP stabilization and verification.** Feature implementations exist across
the frontend and backend, but the project needs repeatable end-to-end
verification before all features can be described as working. This pass
replaces project documentation and leaves runtime code unchanged.

## Completed in this documentation pass

- [x] Replaced hackathon-era overview and progress material with product
  scope, current architecture, data, API, security, setup, user, and QA docs.
- [x] Documented the current source layout and module boundaries without
  moving runtime files.
- [x] Recorded the distinction between implemented code paths and verified
  MVP behavior.
- [x] Cleared all old tests; new tests to be written for upcoming features.

## Next work

1. **Establish a repeatable local baseline**
   - Set up a disposable CockroachDB database and test project.
   - Confirm backend health, frontend connectivity, and the supported start
     commands from `docs/DEVELOPMENT.md`.
2. **Verify one product surface at a time**
   - Use `docs/QA_CHECKLIST.md` to capture reproducible steps, expected result,
     actual result, and evidence for each screen/feature.
   - Fix and test a single reported defect before moving to the next.
3. **Close MVP reliability gaps**
   - Validate capture/retrieval quality, approval gates, restore reporting,
     provider/database degraded states, and Windows desktop behavior.
4. **Release readiness**
   - Complete the security and manual acceptance checks.
   - Remove stale, redundant UI paths only after confirming their callers and
     tests.

## Known boundaries

- Windows is the only documented OS automation target.
- The backend needs configured persistence for durable memory.
- Model and OCR integrations depend on local services, credentials, or
  platform tools.
- This repository does not document a production deployment or authenticated
  multi-user API.

Do not mark a roadmap item complete based only on a module, route, or screen
existing in the repository.
