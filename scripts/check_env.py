"""
scripts/check_env.py - AUTOMATA local environment readiness check.

Owns:    Developer-facing validation for local .env setup before starting
         backend services or applying the database schema.
Never:   Prints secret values or writes credentials anywhere.
Ref:     docs/DEVELOPMENT.md (configuration), docs/TECH_STACK.md.
         For a full health check of a running agent use Setup & health
         in the app, or GET /system/self-check.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ENV = ROOT / "backend" / ".env"

REQUIRED_BY_PHASE = {
    "phase0": (),
    "phase1": ("COCKROACHDB_CONNECTION_STRING",),
    "phase2": (
        "AWS_REGION",
        "AWS_BEDROCK_MODEL_ID",
        "EMBEDDING_MODEL_ID",
        "EMBEDDING_DIMENSION",
    ),
}

OPTIONAL_SECRET_KEYS = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")


def _load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _is_filled(value: str | None) -> bool:
    return bool(value) and not value.startswith("REPLACE_")


def collect_status(phase: str, env_path: Path = BACKEND_ENV) -> tuple[list[str], list[str]]:
    file_values = _load_env_file(env_path)

    def lookup(key: str) -> str | None:
        # A non-empty process variable wins; an empty one falls back to the file.
        return os.environ.get(key) or file_values.get(key)

    required: list[str] = []
    for name, keys in REQUIRED_BY_PHASE.items():
        required.extend(keys)
        if name == phase:
            break

    ok: list[str] = []
    missing: list[str] = []
    for key in required:
        value = lookup(key)
        if _is_filled(value):
            ok.append(key)
        else:
            missing.append(key)

    for key in OPTIONAL_SECRET_KEYS:
        value = lookup(key)
        if _is_filled(value):
            ok.append(key)

    return ok, missing


def main() -> int:
    parser = argparse.ArgumentParser(description="Check AUTOMATA local environment readiness.")
    parser.add_argument(
        "--phase",
        choices=tuple(REQUIRED_BY_PHASE),
        default="phase1",
        help="Readiness level to check. Default: phase1.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=BACKEND_ENV,
        help="Path to the backend .env file.",
    )
    args = parser.parse_args()

    ok, missing = collect_status(args.phase, args.env_file)

    print(f"AUTOMATA environment check ({args.phase})")
    print(f"env file: {args.env_file}")
    print("")

    if ok:
        print("Configured:")
        for key in ok:
            print(f"  - {key}")
        print("")

    if missing:
        print("Missing or still using REPLACE_ placeholder:")
        for key in missing:
            print(f"  - {key}")
        print("")
        print("Create backend/.env from backend/.env.example and fill only the missing keys.")
        return 1

    print("Ready for this phase. No secret values were printed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
