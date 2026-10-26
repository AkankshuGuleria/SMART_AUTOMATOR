"""
intelligence/profile.py — detect what a project is from its files.

Owns:    Languages, frameworks, package managers, databases, infrastructure,
         run book (install/dev/build/test), ports, environment requirements
         (names + set/missing, never values), and project-specific modules
         with an explained readiness score.
Never:   Executes project code, reads secret values, or follows symlinks out of
         the repo. Scans are bounded (file count, file size, depth).
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MAX_FILES = 20000
MAX_SOURCE_SCAN = 1500
MAX_SOURCE_BYTES = 200_000
CACHE_TTL_S = 600
PROFILE_VERSION = 5  # bump when detection logic changes so cached profiles refresh

IGNORED_DIRS = {
    "node_modules", ".git", ".venv", "venv", "env", "__pycache__", "dist", "build", "target",
    "out", ".next", ".nuxt", ".svelte-kit", ".turbo", ".cache", ".parcel-cache", ".vite",
    "coverage", ".pytest_cache", ".pytest-tmp", ".ruff_cache", ".mypy_cache", ".tox", ".idea",
    ".vscode", ".kilo", ".cursor", ".claude", "site-packages", "vendor", ".gradle", "bin", "obj",
}

LANGUAGES = {
    ".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript", ".js": "JavaScript", ".jsx": "JavaScript",
    ".mjs": "JavaScript", ".cjs": "JavaScript", ".rs": "Rust", ".go": "Go", ".java": "Java", ".kt": "Kotlin",
    ".cs": "C#", ".cpp": "C++", ".cc": "C++", ".c": "C", ".h": "C/C++", ".rb": "Ruby", ".php": "PHP",
    ".swift": "Swift", ".dart": "Dart", ".vue": "Vue", ".svelte": "Svelte", ".html": "HTML",
    ".css": "CSS", ".scss": "SCSS", ".sql": "SQL", ".sh": "Shell", ".ps1": "PowerShell",
}
SOURCE_EXTS = {e for e in LANGUAGES if e not in {".html", ".css", ".scss", ".sql"}}

JS_FRAMEWORKS = {
    "next": "Next.js", "react": "React", "vue": "Vue", "nuxt": "Nuxt", "svelte": "Svelte",
    "@sveltejs/kit": "SvelteKit", "@angular/core": "Angular", "solid-js": "Solid", "vite": "Vite",
    "express": "Express", "fastify": "Fastify", "@nestjs/core": "NestJS", "koa": "Koa", "hono": "Hono",
    "electron": "Electron", "@tauri-apps/cli": "Tauri", "@tauri-apps/api": "Tauri",
    "react-native": "React Native", "expo": "Expo", "tailwindcss": "Tailwind CSS",
    "prisma": "Prisma", "@prisma/client": "Prisma", "drizzle-orm": "Drizzle", "mongoose": "Mongoose",
    "typeorm": "TypeORM", "sequelize": "Sequelize", "@supabase/supabase-js": "Supabase",
    "firebase": "Firebase", "stripe": "Stripe", "next-auth": "NextAuth", "@clerk/nextjs": "Clerk",
    "jest": "Jest", "vitest": "Vitest", "mocha": "Mocha", "@playwright/test": "Playwright",
    "cypress": "Cypress", "socket.io": "Socket.IO", "graphql": "GraphQL", "@apollo/client": "Apollo",
    "three": "Three.js", "framer-motion": "Framer Motion", "redux": "Redux", "zustand": "Zustand",
    "recharts": "Recharts",
}
PY_FRAMEWORKS = {
    "fastapi": "FastAPI", "django": "Django", "flask": "Flask", "starlette": "Starlette",
    "sqlalchemy": "SQLAlchemy", "pydantic": "Pydantic", "celery": "Celery", "pytest": "pytest",
    "langchain": "LangChain", "openai": "OpenAI SDK", "anthropic": "Anthropic SDK", "boto3": "AWS SDK",
    "streamlit": "Streamlit", "torch": "PyTorch", "tensorflow": "TensorFlow", "pandas": "pandas",
    "uvicorn": "Uvicorn", "watchdog": "watchdog", "psutil": "psutil",
}
DB_HINTS = {
    "PostgreSQL": {"pg", "postgres", "psycopg2", "psycopg2-binary", "psycopg", "asyncpg", "@neondatabase/serverless"},
    "MySQL": {"mysql", "mysql2", "pymysql", "mysqlclient"},
    "MongoDB": {"mongoose", "mongodb", "pymongo", "motor"},
    "Redis": {"redis", "ioredis", "@upstash/redis"},
    "SQLite": {"sqlite3", "better-sqlite3", "aiosqlite"},
}
LOCKFILES = {
    "package-lock.json": "npm", "pnpm-lock.yaml": "pnpm", "yarn.lock": "yarn", "bun.lockb": "bun",
    "uv.lock": "uv", "poetry.lock": "poetry", "Pipfile.lock": "pipenv", "Cargo.lock": "cargo",
    "go.sum": "go modules", "composer.lock": "composer", "Gemfile.lock": "bundler",
}
MANIFESTS = {
    "package.json", "pyproject.toml", "requirements.txt", "Pipfile", "Cargo.toml", "go.mod",
    "pom.xml", "build.gradle", "build.gradle.kts", "composer.json", "Gemfile", "pubspec.yaml",
}
ENV_EXAMPLES = {".env.example", ".env.sample", ".env.template", ".env.local.example", ".env.dist"}
ENV_FILES = {".env", ".env.local", ".env.development", ".env.development.local"}
DEFAULT_PORTS = {"Vite": 5173, "Next.js": 3000, "Nuxt": 3000, "SvelteKit": 5173, "Angular": 4200,
                 "Express": 3000, "FastAPI": 8000, "Django": 8000, "Flask": 5000, "Streamlit": 8501}
MODULE_HINTS = {
    "components": "UI components", "pages": "Pages", "app": "App routes", "routes": "Routes",
    "api": "API", "server": "Server", "services": "Services", "lib": "Library", "utils": "Utilities",
    "hooks": "Hooks", "store": "State", "models": "Data models", "db": "Database", "prisma": "Database schema",
    "auth": "Auth", "middleware": "Middleware", "tests": "Tests", "test": "Tests", "__tests__": "Tests",
    "screens": "Screens", "styles": "Styles", "migrations": "Migrations", "scripts": "Scripts", "docs": "Docs",
    "src-tauri": "Desktop shell (Tauri)", "src": "App entry", "public": "Static assets",
}
ENV_REF = re.compile(
    r"(?:process\.env\.|import\.meta\.env\.|os\.getenv\(\s*['\"]|os\.environ(?:\.get)?\(?\s*\[?\s*['\"]|"
    r"env\(\s*['\"]|getenv\(\s*['\"])([A-Z][A-Z0-9_]{2,})"
)
PLACEHOLDER = re.compile(r"^(replace|your[_-]|xxx|changeme|<|\$\{|todo|example)", re.I)
TODO_RE = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b")
TEST_FILE = re.compile(r"(^test_.*\.py$|_test\.py$|\.test\.[jt]sx?$|\.spec\.[jt]sx?$|_test\.go$|Test\.java$)")


def _walk(root: Path) -> list[Path]:
    out: list[Path] = []
    stack = [(root, 0)]
    while stack and len(out) < MAX_FILES:
        folder, depth = stack.pop()
        try:
            entries = list(os.scandir(folder))
        except OSError:
            continue
        for e in entries:
            if e.is_symlink():
                continue
            if e.is_dir():
                if e.name not in IGNORED_DIRS and not e.name.startswith(".") and depth < 8:
                    stack.append((Path(e.path), depth + 1))
                elif e.name == ".github":
                    stack.append((Path(e.path), depth + 1))
            elif e.is_file():
                out.append(Path(e.path))
    return out


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def _python_deps(folder: Path) -> set[str]:
    deps: set[str] = set()
    for name in ("requirements.txt", "requirements-dev.txt"):
        f = folder / name
        if f.exists():
            for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                m = re.match(r"\s*([A-Za-z0-9_.\-]+)", line)
                if m and not line.strip().startswith("#"):
                    deps.add(m.group(1).lower())
    py = folder / "pyproject.toml"
    if py.exists():
        text = py.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"['\"]([A-Za-z0-9_.\-]+)(?:\[[^\]]*\])?\s*[<>=~!;'\"]", text):
            deps.add(m.group(1).lower())
    return deps


def _env_keys(path: Path) -> dict[str, bool]:
    """KEY -> has a real (non-placeholder) value. Values are never returned."""
    keys: dict[str, bool] = {}
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.replace("export ", "").strip()
            value = value.split(" #")[0].strip().strip("'\"")
            if re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
                keys[key] = bool(value) and not PLACEHOLDER.match(value)
    except OSError:
        pass
    return keys


def detect(repo_path: str) -> dict[str, Any]:
    """Build a full profile for the project at *repo_path*."""
    from intelligence.providers import describe

    root = Path(repo_path)
    if not root.is_dir():
        return {"ok": False, "error": f"Project folder not found: {repo_path}"}
    started = time.perf_counter()
    files = _walk(root)
    rel = lambda p: p.relative_to(root).as_posix()  # noqa: E731

    lang_bytes: Counter[str] = Counter()
    lang_files: Counter[str] = Counter()
    for f in files:
        lang = LANGUAGES.get(f.suffix.lower())
        if lang:
            lang_files[lang] += 1
            try:
                lang_bytes[lang] += f.stat().st_size
            except OSError:
                pass
    total_bytes = sum(lang_bytes.values()) or 1
    languages = [
        {"name": name, "files": lang_files[name], "percent": round(b / total_bytes * 100, 1)}
        for name, b in lang_bytes.most_common(8)
    ]

    names = {f.name for f in files}
    manifests = sorted({rel(f) for f in files if f.name in MANIFESTS})
    package_managers = sorted({pm for lock, pm in LOCKFILES.items() if lock in names})

    frameworks: list[str] = []
    databases: set[str] = set()
    apps: list[dict[str, Any]] = []
    run_book: list[dict[str, Any]] = []
    ports: set[int] = set()

    def add(fw: str) -> None:
        if fw not in frameworks:
            frameworks.append(fw)

    for pkg_path in sorted((f for f in files if f.name == "package.json"), key=lambda p: len(p.parts)):
        data = _read_json(pkg_path)
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        found = [fw for key, fw in JS_FRAMEWORKS.items() if key in deps]
        for fw in found:
            add(fw)
        for db, hints in DB_HINTS.items():
            if hints & set(deps):
                databases.add(db)
        folder = pkg_path.parent
        pm = next((pm for lock, pm in LOCKFILES.items() if (folder / lock).exists() and pm in {"npm", "pnpm", "yarn", "bun"}), "npm")
        run = "npm run" if pm == "npm" else pm
        scripts = data.get("scripts", {}) or {}
        cwd = rel(folder) if folder != root else "."
        commands = {"install": f"{pm} install"}
        for key in ("dev", "start", "build", "test", "lint", "preview"):
            script = scripts.get(key)
            if script and "no test specified" not in script:
                commands[key] = f"{run} {key}" if key not in {"start", "test"} or pm != "npm" else f"npm {key}"
                for m in re.finditer(r"(?:--port[ =]|PORT=)(\d{2,5})", script):
                    ports.add(int(m.group(1)))
        for fw in found:
            if fw in DEFAULT_PORTS and ("dev" in commands or "start" in commands):
                ports.add(DEFAULT_PORTS[fw])
                break
        kind = "frontend" if any(f in found for f in ("React", "Vue", "Svelte", "Angular", "Next.js", "Solid", "Nuxt")) else "node"
        apps.append({"path": cwd, "kind": kind, "manifest": rel(pkg_path), "frameworks": found})
        run_book.append({"path": cwd, "language": "JavaScript/TypeScript", "commands": commands})

    for folder in sorted({f.parent for f in files if f.name in {"pyproject.toml", "requirements.txt"}}, key=lambda p: len(p.parts)):
        deps = _python_deps(folder)
        found = [fw for key, fw in PY_FRAMEWORKS.items() if key in deps]
        for fw in found:
            add(fw)
        for db, hints in DB_HINTS.items():
            if hints & deps:
                databases.add(db)
        if "cockroach" in " ".join(deps) or any("COCKROACH" in k for k in _env_keys(folder / ".env.example")):
            databases.add("CockroachDB")
        cwd = rel(folder) if folder != root else "."
        uv = (folder / "uv.lock").exists()
        poetry = (folder / "poetry.lock").exists()
        prefix = "uv run " if uv else ("poetry run " if poetry else "")
        commands = {"install": "uv sync" if uv else ("poetry install" if poetry else "pip install -r requirements.txt")}
        if (folder / "manage.py").exists():
            commands["dev"] = f"{prefix}python manage.py runserver"
            ports.add(8000)
        elif (folder / "main.py").exists():
            commands["dev"] = f"{prefix}python main.py"
            if "FastAPI" in found or "Uvicorn" in found:
                ports.add(8000)
        elif (folder / "app.py").exists():
            commands["dev"] = f"{prefix}python app.py"
            if "Flask" in found:
                ports.add(5000)
        if "pytest" in found or (folder / "tests").is_dir():
            commands["test"] = f"{prefix}pytest"
        kind = "backend" if any(f in found for f in ("FastAPI", "Django", "Flask", "Starlette")) else "python"
        apps.append({"path": cwd, "kind": kind, "manifest": rel(folder / ("pyproject.toml" if (folder / "pyproject.toml").exists() else "requirements.txt")), "frameworks": found})
        run_book.append({"path": cwd, "language": "Python", "commands": commands})

    for f in files:
        if f.name == "Cargo.toml":
            text = f.read_text(encoding="utf-8", errors="replace")
            if "tauri" in text:
                add("Tauri")
            if "axum" in text:
                add("Axum")
            if "actix-web" in text:
                add("Actix")
        elif f.name == "go.mod":
            text = f.read_text(encoding="utf-8", errors="replace")
            for key, fw in (("gin-gonic", "Gin"), ("labstack/echo", "Echo"), ("gofiber", "Fiber")):
                if key in text:
                    add(fw)
        elif f.name in {"pom.xml", "build.gradle", "build.gradle.kts"}:
            if "spring-boot" in f.read_text(encoding="utf-8", errors="replace"):
                add("Spring Boot")
        elif f.name == "schema.prisma":
            m = re.search(r'provider\s*=\s*"(postgresql|mysql|sqlite|mongodb|cockroachdb)"', f.read_text(encoding="utf-8", errors="replace"))
            if m:
                databases.add({"postgresql": "PostgreSQL", "mysql": "MySQL", "sqlite": "SQLite",
                               "mongodb": "MongoDB", "cockroachdb": "CockroachDB"}[m.group(1)])

    infra: list[str] = []
    compose = [f for f in files if f.name in {"docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"}]
    if any(f.name == "Dockerfile" for f in files):
        infra.append("Docker")
    if compose:
        infra.append("Docker Compose")
        for c in compose:
            text = c.read_text(encoding="utf-8", errors="replace").lower()
            for img, db in (("postgres", "PostgreSQL"), ("mysql", "MySQL"), ("mongo", "MongoDB"), ("redis", "Redis")):
                if f"image: {img}" in text or f"image: \"{img}" in text:
                    databases.add(db)
            for m in re.finditer(r"['\"]?(\d{2,5}):\d{2,5}['\"]?", text):
                ports.add(int(m.group(1)))
    if any(".github/workflows" in rel(f) for f in files):
        infra.append("GitHub Actions")
    for name, label in (("vercel.json", "Vercel"), ("netlify.toml", "Netlify"), ("fly.toml", "Fly.io"),
                        ("render.yaml", "Render"), ("railway.json", "Railway")):
        if name in names:
            infra.append(label)

    # Environment requirements: declared in examples + referenced in code; set if a real .env has a value.
    declared: dict[str, str] = {}
    present: dict[str, bool] = {}
    defaults: set[str] = set()
    for f in files:
        if f.name in ENV_EXAMPLES:
            for key, has_default in _env_keys(f).items():
                declared.setdefault(key, rel(f))
                if has_default:
                    defaults.add(key)  # example ships a working value (e.g. a localhost URL)
        elif f.name in ENV_FILES:
            for key, has_value in _env_keys(f).items():
                present[key] = present.get(key, False) or has_value
    referenced: dict[str, str] = {}
    scanned = 0
    for f in files:
        if scanned >= MAX_SOURCE_SCAN:
            break
        if f.suffix.lower() not in SOURCE_EXTS:
            continue
        # Test files and fixtures mention variables the app does not need.
        if TEST_FILE.search(f.name) or any(p in {"tests", "test", "__tests__", "fixtures"} for p in f.parts):
            continue
        try:
            if f.stat().st_size > MAX_SOURCE_BYTES:
                continue
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        scanned += 1
        for m in ENV_REF.finditer(text):
            referenced.setdefault(m.group(1), rel(f))
    ignore_env = {"NODE_ENV", "PATH", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP",
                  "PORT", "DEV", "PROD", "MODE", "BASE_URL", "SSR", "CI", "SystemDrive"}
    env_vars = []
    for key in sorted(set(declared) | set(referenced)):
        if key in ignore_env or key.startswith(("AUTOMATA_", "VITE_USER_")):
            continue
        info = describe(key)
        env_vars.append({
            "name": key,
            "set": bool(present.get(key) or os.environ.get(key) or key in defaults),
            "has_default": key in defaults,
            "declared_in": declared.get(key),
            "used_in": referenced.get(key),
            "provider": info["provider"],
            "kind": info["kind"],
        })

    modules = _modules(root, files, apps)
    project_type = classify(files, root, apps, frameworks, sorted(databases), languages,
                            [v["name"] for v in env_vars])
    profile = {
        "ok": True,
        "repo_path": str(root),
        "name": root.name,
        "summary": _summary(apps, frameworks, sorted(databases), infra),
        "type": project_type,
        "languages": languages,
        "frameworks": frameworks,
        "databases": sorted(databases),
        "package_managers": package_managers,
        "infrastructure": infra,
        "apps": apps,
        "run_book": run_book,
        "ports": sorted(p for p in ports if 1000 <= p <= 65535),
        "env": {
            "variables": env_vars,
            "missing": [v["name"] for v in env_vars if not v["set"]],
            "env_file_found": any(f.name in ENV_FILES for f in files),
        },
        "modules": modules,
        "tests": {"files": sum(1 for f in files if TEST_FILE.search(f.name)), "frameworks": [f for f in frameworks if f in {"pytest", "Jest", "Vitest", "Mocha", "Playwright", "Cypress"}]},
        "manifests": manifests,
        "file_count": len(files),
        "truncated": len(files) >= MAX_FILES,
        "scan_ms": round((time.perf_counter() - started) * 1000),
        "generated_at": time.time(),
    }
    return profile


AI_SDKS = {"OpenAI SDK", "Anthropic SDK", "LangChain"}
AI_JS = {"openai", "@anthropic-ai/sdk", "langchain", "@langchain/core", "ai", "@google/generative-ai"}
FRONTEND_FW = {"React", "Vue", "Svelte", "SvelteKit", "Angular", "Next.js", "Nuxt", "Solid"}
BACKEND_FW = {"FastAPI", "Django", "Flask", "Starlette", "Express", "Fastify", "NestJS", "Koa", "Hono",
              "Spring Boot", "Gin", "Echo", "Fiber", "Axum", "Actix"}
FOCUS = {
    "static_website": ["pages & content", "styles", "assets", "SEO / accessibility", "deployment"],
    "web_app": ["components / pages", "state & routing", "API calls", "tests", "build"],
    "full_stack": ["frontend", "API", "database", "auth", "tests", "deployment"],
    "api_service": ["endpoints", "data layer", "auth", "tests", "deployment"],
    "desktop_app": ["UI", "native shell", "backend / IPC", "packaging"],
    "mobile_app": ["screens", "navigation", "API calls", "builds"],
    "data_ml": ["data", "notebooks / pipelines", "models", "evaluation"],
    "library_cli": ["public API / commands", "tests", "docs", "packaging"],
    "scripts": ["scripts", "inputs / outputs"],
    "empty": [],
}


LLM_ENV = re.compile(r"^(OPENAI|ANTHROPIC|GROQ|GEMINI|OPENROUTER|COHERE|MISTRAL|OLLAMA|AWS_BEDROCK|HUGGINGFACE|HF)_")


def classify(files: list[Path], root: Path, apps: list[dict], frameworks: list[str],
             databases: list[str], languages: list[dict], env_names: list[str] | None = None) -> dict[str, Any]:
    """What kind of project this is, with the evidence behind the call.

    Returns {kind, label, ai, reasons, focus}. `focus` lists what matters for
    this kind of project so the UI and prompts talk about the right things (a
    static site has no API or database to report on).
    """
    fw = set(frameworks)
    names = {f.name.lower() for f in files}
    exts = Counter(f.suffix.lower() for f in files)
    reasons: list[str] = []
    js_deps: set[str] = set()
    for f in files:
        if f.name == "package.json":
            data = _read_json(f)
            js_deps |= set(data.get("dependencies", {})) | set(data.get("devDependencies", {}))

    front = sorted(fw & FRONTEND_FW)
    back = sorted(fw & BACKEND_FW)
    has_backend = bool(back) or any(a["kind"] == "backend" for a in apps)
    ai_used = sorted((fw & AI_SDKS) | (js_deps & AI_JS))
    pretty = {"AWS": "Bedrock", "HF": "Hugging Face", "HUGGINGFACE": "Hugging Face", "OPENAI": "OpenAI",
              "OPENROUTER": "OpenRouter"}
    llm_keys = sorted({pretty.get(n.split("_")[0], n.split("_")[0].title())
                       for n in (env_names or []) if LLM_ENV.match(n)})
    html_only = exts.get(".html", 0) > 0 and not apps and not front and not back

    if "Tauri" in fw or "Electron" in fw:
        kind, label = "desktop_app", "Desktop app"
        reasons.append(("Tauri" if "Tauri" in fw else "Electron") + " shell found")
        if front or back:
            reasons.append("inside: " + ", ".join([*front, *back]))
    elif fw & {"React Native", "Expo"} or "pubspec.yaml" in names:
        kind, label = "mobile_app", "Mobile app"
        reasons.append("React Native / Expo / Flutter project files found")
    elif html_only:
        kind, label = "static_website", "Static website"
        reasons.append(f"{exts.get('.html', 0)} HTML file(s) and no framework or server manifest")
    elif front and has_backend:
        kind, label = "full_stack", "Full-stack web app"
        reasons.append(f"frontend ({', '.join(front)}) and backend ({', '.join(back) or 'server app'})")
    elif front:
        kind, label = "web_app", "Web app (frontend)"
        reasons.append(f"frontend framework: {', '.join(front)}; no server framework")
    elif has_backend:
        kind, label = "api_service", "API / backend service"
        reasons.append(f"server framework: {', '.join(back) or 'Python/Node server'}; no UI framework")
    elif fw & {"PyTorch", "TensorFlow", "pandas", "Streamlit"} or exts.get(".ipynb", 0):
        kind, label = "data_ml", "Data / ML project"
        reasons.append("data or ML libraries / notebooks found")
    elif apps:
        kind, label = "library_cli", "Library / CLI / script"
        reasons.append("package manifest without a web, server or UI framework")
    elif languages:
        kind, label = "scripts", "Scripts / source files"
        reasons.append(f"mostly {languages[0]['name']} files, no package manifest")
    else:
        kind, label = "empty", "Empty or unrecognised"
        reasons.append("no source files recognised")

    focus = list(FOCUS[kind])
    if (ai_used or llm_keys) and kind != "empty":
        label = "AI / LLM " + label[0].lower() + label[1:]
        if ai_used:
            reasons.append("uses " + ", ".join(ai_used))
        if llm_keys:
            reasons.append("calls LLM APIs: " + ", ".join(llm_keys[:5]))
        focus += ["prompts & model calls", "API keys"]
    if databases:
        reasons.append("database: " + ", ".join(databases))
    return {"kind": kind, "label": label, "ai": bool(ai_used or llm_keys), "reasons": reasons, "focus": focus}


def _summary(apps: list[dict], frameworks: list[str], databases: list[str], infra: list[str]) -> str:
    parts = []
    for app in apps[:4]:
        main = [f for f in app["frameworks"] if f not in {"Tailwind CSS", "pytest", "Pydantic", "Jest", "Vitest", "Uvicorn", "Framer Motion", "Recharts", "watchdog", "psutil"}][:2]
        label = {"frontend": "frontend", "backend": "backend", "node": "Node app", "python": "Python app"}[app["kind"]]
        where = "" if app["path"] == "." else f" ({app['path']})"
        parts.append(f"{' + '.join(main) or app['kind'].title()} {label}{where}")
    if "Tauri" in frameworks:
        parts.append("Tauri desktop shell")
    if databases:
        parts.append(" / ".join(databases))
    if infra:
        parts.append(", ".join(infra[:2]))
    return "; ".join(parts) or "No recognised stack (no manifest files found)"


def _modules(root: Path, files: list[Path], apps: list[dict]) -> list[dict[str, Any]]:
    """Modules = notable folders inside each app (or top-level source folders)."""
    by_dir: dict[str, list[Path]] = {}
    app_roots = [root / a["path"] if a["path"] != "." else root for a in apps] or [root]
    for f in files:
        if f.suffix.lower() not in LANGUAGES:
            continue
        for app_root in sorted(app_roots, key=lambda p: len(p.parts), reverse=True):
            try:
                parts = f.relative_to(app_root).parts
            except ValueError:
                continue
            if len(parts) < 2:
                key = app_root
            else:
                first = parts[0]
                if first in {"src", "app", "lib"} and len(parts) >= 3:
                    key = app_root / first / parts[1]
                else:
                    key = app_root / first
            by_dir.setdefault(str(key), []).append(f)
            break
    modules = []
    for path_str, mfiles in by_dir.items():
        path = Path(path_str)
        if len(mfiles) < 2 and path not in app_roots:
            continue
        label = MODULE_HINTS.get(path.name.lower(), path.name.replace("_", " ").replace("-", " ").title())
        tests = sum(1 for f in mfiles if TEST_FILE.search(f.name) or "test" in f.parent.name.lower())
        todos = 0
        for f in mfiles[:300]:
            if f.suffix.lower() in SOURCE_EXTS:
                try:
                    if f.stat().st_size <= MAX_SOURCE_BYTES:
                        todos += len(TODO_RE.findall(f.read_text(encoding="utf-8", errors="ignore")))
                except OSError:
                    pass
        modules.append({
            "name": label,
            "path": path.relative_to(root).as_posix() if path != root else ".",
            "files": len(mfiles),
            "test_files": tests,
            "todos": todos,
            "languages": [n for n, _ in Counter(LANGUAGES[f.suffix.lower()] for f in mfiles).most_common(2)],
        })
    modules.sort(key=lambda m: m["files"], reverse=True)
    return modules[:14]


def score_modules(profile: dict[str, Any], project_id: str | None) -> list[dict[str, Any]]:
    """Readiness 0-100 per module from tests, TODOs and recent activity (explained in `basis`)."""
    recent: Counter[str] = Counter()
    if project_id:
        try:
            from memory.local_store import get_store

            for m in get_store().recent(project_id, ["file_edit"], limit=500, since=time.time() - 7 * 86400):
                fp = ((m.get("meta") or {}).get("file_path") or "").replace("\\", "/")
                for mod in profile.get("modules", []):
                    if mod["path"] != "." and f"/{mod['path']}/" in f"/{fp}" .replace(str(profile.get('repo_path', '')).replace('\\', '/'), ""):
                        recent[mod["path"]] += 1
        except Exception:
            pass
    project_has_tests = bool(profile.get("tests", {}).get("files"))
    out = []
    for mod in profile.get("modules", []):
        edits = recent.get(mod["path"], 0)
        tests = mod["test_files"] > 0 or mod["name"] == "Tests"
        score = 40 + (30 if tests else (10 if project_has_tests else 0)) + min(20, edits * 4)
        score -= min(30, mod["todos"] * 3)
        score += 10 if mod["files"] >= 3 else 0
        score = max(0, min(100, score))
        basis = [
            f"{mod['files']} files",
            f"{mod['test_files']} test files" if mod["test_files"] else ("covered by project tests" if project_has_tests else "no tests"),
            f"{mod['todos']} TODO/FIXME" if mod["todos"] else "no TODOs",
            f"{edits} edits in 7 days",
        ]
        out.append({**mod, "pct": score, "recent_edits": edits, "basis": ", ".join(basis)})
    return out


def get_profile(project_id: str, refresh: bool = False) -> dict[str, Any]:
    """Cached profile for a registered project (recomputed after 10 minutes or on refresh)."""
    from db.client import get_project
    from memory.local_store import get_store

    project = get_project(project_id)
    if not project:
        return {"ok": False, "error": "Project not found"}
    repo = str(project.get("repo_path") or "")
    store = get_store()
    key = f"profile:{PROFILE_VERSION}:{project_id}"
    cached = store.get_value(key)
    if cached and not refresh and cached.get("repo_path") == str(Path(repo)) and time.time() - cached.get("generated_at", 0) < CACHE_TTL_S:
        profile = cached
    else:
        profile = detect(repo)
        if profile.get("ok"):
            store.set_value(key, profile)
    if profile.get("ok"):
        profile = {**profile, "modules": score_modules(profile, project_id), "project_id": project_id}
    return profile


def prompt_context(project_id: str | None, max_chars: int = 1200) -> str:
    """Compact, factual project description for prompts (stack, run book, missing env)."""
    if not project_id:
        return "No project is selected."
    profile = get_profile(project_id)
    if not profile.get("ok"):
        return f"Project folder unavailable: {profile.get('error')}"
    ptype = profile.get("type") or {}
    lines = [
        f"Project: {profile['name']} at {profile['repo_path']}",
        f"Type: {ptype.get('label', 'unknown')} ({'; '.join(ptype.get('reasons', [])[:2])})",
        f"Stack: {profile['summary']}",
    ]
    for entry in profile["run_book"][:3]:
        cmds = ", ".join(f"{k}: `{v}`" for k, v in entry["commands"].items())
        lines.append(f"Run ({entry['path']}): {cmds}")
    if profile["env"]["missing"]:
        lines.append("Env vars not set yet: " + ", ".join(profile["env"]["missing"][:12]))
    mods = ", ".join(f"{m['name']} ({m['path']})" for m in profile["modules"][:8])
    if mods:
        lines.append(f"Main modules: {mods}")
    return "\n".join(lines)[:max_chars]
