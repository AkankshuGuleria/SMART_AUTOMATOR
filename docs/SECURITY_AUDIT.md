# AUTOMATA — security audit

Date: 2026-10-26 · Branch `chore/project-review-monitoring` · Scope: the whole
repository (Python agent, React UI, Tauri shell, git history) and the running
desktop app on Windows 11.

## 1. Result

All findings that could be exploited were fixed and have regression tests.
Every scanner now reports **no known vulnerabilities** and **no high-severity
code findings**:

| Check | Tool | Result |
| --- | --- | --- |
| Python dependencies (runtime, optional, dev) | `pip-audit` | ✅ No known vulnerabilities (was 31 advisories) |
| JavaScript dependencies | `npm audit` | ✅ 0 vulnerabilities (was 8, 4 high) |
| Rust dependencies (desktop shell) | `cargo audit` | ✅ 0 vulnerabilities; 5 informational warnings (Linux-only / build-time crates) |
| Python static analysis | `bandit` | ✅ 0 high (was 4); 27 medium reviewed — see §4 |
| Python security lint | `ruff` (flake8-bandit `S` rules) | ✅ All checks passed |
| Secrets in the whole git history | custom scan (patterns + real `.env` values) | ✅ None. 16 pattern hits are documented fake keys in redaction tests |
| Live attack probes against the running API | manual (curl / PowerShell) | ✅ Cross-site, rebinding, oversized and foreign-WebSocket requests refused |
| UI script injection | review + test | ✅ Chat renders text only (no HTML) |

Tests: 395 backend (`uv run pytest`), 6 frontend (`npm test`), type-check and lint clean.

## 2. Threat model

AUTOMATA is a single-user desktop app. The agent listens on `127.0.0.1:8000`
and can control the PC (type, paste, launch apps, run commands, read the screen).
The realistic attackers are therefore:

1. **A web page you visit** — browsers can send requests to `127.0.0.1`.
2. **Hostile content AUTOMATA reads** — commit messages, file names, OCR'd
   screen text, model replies that end up in the UI or in prompts.
3. **Tampered local files** — checkpoints, snapshots, `.env` values.
4. **Vulnerable dependencies.**

Another program already running as the same Windows user is out of scope: it
can do anything the user can.

## 3. Findings and fixes

| # | Severity | Finding | Fix | Test |
| --- | --- | --- | --- | --- |
| S1 | **High** | **DNS rebinding:** the API answered any `Host` header, so a site could point its own domain at 127.0.0.1 and read memory, projects and app usage as "same-origin". Verified live. | `security/http_guard.py` refuses unknown `Host` headers | `test_dns_rebinding_host_is_refused` |
| S2 | **High** | **Cross-site actions:** CORS stops a page *reading* replies, not *sending* requests. Body-less POSTs (e.g. `/ai/local/install-ollama`, `/workspace/snapshot-active`) and WebSocket subscriptions worked from any site. | The guard refuses requests whose `Origin` is not the AUTOMATA UI, `Sec-Fetch-Site: cross-site`, foreign WebSocket origins, and bodies over 10 MB. CORS no longer allows credentials; methods/headers narrowed | `test_foreign_origin_is_refused_even_without_a_body`, `test_websocket_from_a_foreign_site_is_refused`, `test_oversized_bodies_are_refused` |
| S3 | **High** | **Self-approved actions:** `/commands/execute` ran a shell command whenever the caller sent `allow_execute: true`; `/external-agents/{tool}/prompt` trusted `approved: true`. | Server-side permission system (`security/permissions.py`): single-use approvals issued by the server and bound to the exact action | `test_command_execution_needs_the_users_approval`, `test_external_agent_prompt_ignores_self_approval` |
| S4 | **High** | **No consent before controlling the PC:** opening apps/URLs, clipboard, media keys, Spotify, screen reading, Resume and dev servers ran without asking. | Every such action asks first (Allow once / Always allow / Deny); per-category choices in Settings → Permissions | `test_desktop_routes_ask_first` (7 routes), chat and work-bar tests |
| S5 | **High** | **Unsafe deserialisation:** workflow checkpoints were loaded with `pickle` (a tampered file runs code), from file names built from API input (path traversal). | Checkpoints are JSON in the data folder; run/step ids allow only `[A-Za-z0-9_.-]` | `test_workflow_checkpoint_ids_cannot_escape_the_folder` |
| S6 | **High** | **Vulnerable dependencies:** GitPython 3.1.55 (23 advisories, used on your repositories), urllib3, certifi, cryptography, filelock, virtualenv, werkzeug; vite (4 high), vitest. | Upgraded: GitPython 3.2.1 (floor raised in `pyproject.toml`), urllib3 2.8.0, certifi 2026.10.23, cryptography 50.0.2, filelock 4.2.4, virtualenv 21.14.13, werkzeug 3.1.9, vite 8.3.5, vitest 4.1.12, tokio 1.54.1 | audits in §1 |
| S7 | Medium | **`.env` injection:** a value with a line break written by the Needs inbox could add variables (e.g. `NODE_OPTIONS=--require=…`) to your project. | Values with line breaks/control characters are refused; names validated; only `.env*` files; backslashes escaped | `test_env_values_cannot_inject_lines` |
| S8 | Medium | **Shell commands from stored data:** Resume restarted dev servers by running a saved command line with `shell=True`. | Resume uses the project's run book (`npm run dev`) derived by AUTOMATA; still asks permission | `test_resume_reports_each_step_and_skips_running_servers` |
| S9 | Medium | **No Content Security Policy** in the desktop app (`csp: null`). | Strict CSP: scripts only from the app, network only to the local API and Google Fonts, no objects/frames/forms | verified live: app loads and works |
| S10 | Medium | **SQL built from values:** `INTERVAL '{days} days'`; dynamic column names in the task store. | `int(days)`; column allow-lists in `tasks/store.py` | full suite |
| S11 | Low | Shell commands were logged verbatim (a `Bearer …` header would reach the log). | Commands are redacted before logging | — |
| S12 | Low | Chat rendered replies through `innerHTML` (safe today because escaped first, but fragile). | Rewritten as React text elements — markup cannot be injected | `AIChatScreen.test.tsx` |
| S13 | Low | `OLLAMA_BASE_URL` could be a `file://` URL. | Only http(s) accepted | — |
| S14 | Info | Four em dashes in `api.ts` comments were garbled by an earlier encoding mistake (committed in `9c6d919`). | Fixed; repo scanned for other damage (none) | — |

## 4. Accepted, reviewed items

| Item | Why it is acceptable |
| --- | --- |
| 3 × `shell=True` (command runner, run-book dev servers) | Needed to run `npm`/shell commands; only after the user approves (permission `system` / `workspace`). Marked `# noqa: S602  # nosec B602` with the reason. |
| 15 × Bandit B310 (`urlopen`) | Fixed provider endpoints and the Ollama URL (http(s) only). |
| 12 × Bandit B608 (SQL strings) | Interpolate only `?` placeholders, allow-listed names or `int()`; each line carries the reason. |
| 5 × `cargo audit` warnings | `glib`/`zbus`/`zvariant` are Linux-only and not built on Windows; `proc-macro-error` runs at build time only. |
| No API token | The guard limits callers to the AUTOMATA UI and programs already running as you; a token would not stop the latter. Revisit before any network exposure. |
| Windows Defender "Controlled folder access" blocks Spotify | Windows protecting your Music folder from Spotify, not AUTOMATA. AUTOMATA explains the popup and how to allow the app, and never changes security settings. |

## 5. Re-running the audit

```powershell
cd backend
uv export --no-hashes --format requirements-txt --all-extras > reqs.txt
uvx pip-audit -r reqs.txt
uvx bandit -r . -x ./.venv,./tests -lll
uv run ruff check .        # includes bandit (S) rules; reviewed ignores in pyproject.toml
uv run pytest tests/ -q
cd ../frontend; npm audit; npx tsc -b; npx oxlint src; npm test
cd src-tauri; cargo audit
```
