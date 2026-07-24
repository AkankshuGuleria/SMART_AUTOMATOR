# SETUP.md — Local Development Environment

> This file reflects the actual current setup — not just the aspirational plan.
> Update it immediately when a setup step changes.

## 1. Prerequisites

- **Node.js** (version: 22.x LTS recommended) + **npm** (bundled with Node)
- **Rust toolchain** (required by Tauri 2.x) — install via `rustup`:
  ```
  winget install Rustlang.Rustup
  ```
  Then: `rustup default stable`
- **Python 3.12** — install from python.org or `winget install Python.Python.3.12`
- **uv** (Python package manager) — installed via:
  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
  Then add `C:\Users\<you>\.local\bin` to PATH (see uv installer output).
- **Git** — `winget install Git.Git`
- **CockroachDB** — cloud cluster (free tier at cockroachlabs.com) OR local binary:
  ```
  winget install CockroachLabs.CockroachDB
  ```
- **AWS account** with Bedrock access enabled in your target region (TBD — see TECH_STACK.md)

---

## 2. Clone & scaffold

```
git clone <repo-url> D:\AUTOMATA
cd D:\AUTOMATA
```

Repo layout is already fully scaffolded — matches `CONVENTIONS.md §1` exactly.

---

## 3. Environment variables

```powershell
# In backend/
Copy-Item .env.example .env
# Then open .env and fill in real values — see TECH_STACK.md for what each var does.
# NEVER commit .env
```

---

## 4. Backend setup

```powershell
cd D:\AUTOMATA\backend
uv sync --all-extras        # installs all deps into .venv, creates uv.lock
uv run python main.py       # starts FastAPI on http://127.0.0.1:8000
```

For hot-reload during development:
```powershell
uv run uvicorn api.server:app --reload --host 127.0.0.1 --port 8000
```

---

## 5. CockroachDB setup

Once CockroachDB is provisioned, create the schema:

```powershell
# Cloud cluster (fill in your connection string):
$env:CONN = "postgresql+psycopg2://user:pass@host:26257/defaultdb?sslmode=verify-full"

# Run schema (requires psql or cockroach sql):
cockroach sql --url $env:CONN < backend/db/schema.sql

# Or via psql:
psql $env:CONN -f backend/db/schema.sql
```

**Note:** `VECTOR(1024)` in schema.sql is a placeholder dimension.
Update it to match `EMBEDDING_DIMENSION` in `.env` once the model is decided.

---

## 6. Frontend setup

```powershell
cd D:\AUTOMATA\frontend
npm install
npm run dev        # Vite dev server at http://localhost:5173
```

Tauri desktop shell (requires Rust toolchain + WebView2):
```powershell
npm run tauri dev  # Phase 2+ — set up Tauri first with: npm install @tauri-apps/cli
```

---

## 7. Running tests

```powershell
# Backend
cd D:\AUTOMATA\backend
uv run pytest tests/ -v

# Frontend
cd D:\AUTOMATA\frontend
npm test
```

---

## 8. Verifying the setup works

- [ ] `uv run python main.py` starts without crashing; logs "DB not connected" warning (not a crash).
- [ ] `npm run dev` serves the React app at `http://localhost:5173`.
- [ ] `http://127.0.0.1:8000/health` returns `{"api": "ok", ...}` when backend is running.
- [ ] Swagger UI at `http://127.0.0.1:8000/docs` shows all routes.
- [ ] `uv run pytest tests/ -v` passes all tests (Phase 0: test_config.py).
- [ ] After provisioning CockroachDB + filling `.env`: backend logs "db_available=True".
- [ ] After schema is applied: a test file edit produces a row in `file_edits` (Phase 1 milestone).

---

## 9. Common setup issues

- **`uv` not found after install** → restart PowerShell, or run: `$env:Path = "C:\Users\<you>\.local\bin;$env:Path"`
- **Bedrock access denied** → confirm the Bedrock model is enabled in the AWS console for your account/region, not just IAM permissions.
- **CockroachDB vector index errors** → confirm your CockroachDB version supports Distributed Vector Indexing; check `TECH_STACK.md`.
- **Tauri build failing** → confirm Rust + WebView2 are installed (`winget install Microsoft.EdgeWebView2Runtime`).
- **psycopg2-binary on Python 3.12** → uv resolves the correct wheel automatically; if you see binary incompatibility errors, confirm Python is 3.12.
