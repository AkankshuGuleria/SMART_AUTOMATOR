"""
automation/ocr.py — AUTOMATA Visual Feedback Layer: OCR text extraction.

Owns:    Extracting text from screenshots and images, then redacting
         secret-shaped strings before the text is stored or sent to a model.
Never:   Writes to CockroachDB, calls Bedrock, or touches the user's clipboard.
         Never returns an engine status message as if it were recognised text.

Engines, in order:
1. Windows built-in OCR (Windows.Media.Ocr) via automation/windows_ocr.ps1 —
   ships with Windows 10/11; needs an OCR language pack (English is default).
2. Tesseract via pytesseract, if both are installed.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
from typing import TypedDict

logger = logging.getLogger(__name__)

_PS_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "windows_ocr.ps1")
_TIMEOUT_S = 30


class OcrResult(TypedDict):
    ok: bool
    text: str
    engine: str | None
    error: str | None


def run_ocr(image_path: str) -> OcrResult:
    """OCR *image_path*. ``ok`` is False (with ``error``) when no engine succeeded."""
    if not image_path or not os.path.exists(image_path):
        return {"ok": False, "text": "", "engine": None, "error": f"Image not found: {image_path}"}

    errors: list[str] = []
    for engine, fn in (("windows", _ocr_windows), ("tesseract", _ocr_tesseract)):
        text, error = fn(image_path)
        if error is None:
            text = redact_secrets(text)
            logger.info("ocr: %s extracted %d chars from %s", engine, len(text), image_path)
            return {"ok": True, "text": text, "engine": engine, "error": None}
        errors.append(f"{engine}: {error}")
    message = "No OCR engine could read the image (" + "; ".join(errors) + ")"
    logger.warning("ocr: %s", message)
    return {"ok": False, "text": "", "engine": None, "error": message}


def ocr_image(image_path: str) -> str:
    """Backward-compatible helper: recognised text, or '' when OCR failed."""
    return run_ocr(image_path)["text"]


def _ocr_windows(image_path: str) -> tuple[str, str | None]:
    if sys.platform != "win32":
        return "", "Windows OCR is only available on Windows"
    env = {**os.environ, "AUTOMATA_OCR_PATH": os.path.abspath(image_path)}
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", _PS_SCRIPT],
            capture_output=True,
            timeout=_TIMEOUT_S,
            env=env,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return "", f"timed out after {_TIMEOUT_S}s"
    except Exception as exc:
        return "", str(exc)
    stdout = completed.stdout.decode("utf-8", errors="replace").strip()
    stderr = completed.stderr.decode("utf-8", errors="replace").strip()
    if completed.returncode != 0:
        return "", stderr.splitlines()[-1] if stderr else f"exit code {completed.returncode}"
    return stdout, None


def _ocr_tesseract(image_path: str) -> tuple[str, str | None]:
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return "", "pytesseract/Pillow not installed"
    try:
        with Image.open(image_path) as img:
            return pytesseract.image_to_string(img).strip(), None
    except Exception as exc:
        return "", str(exc)


def redact_secrets(text: str) -> str:
    """Redact secret-shaped strings from OCR text before storage or model handoff."""
    if not text:
        return text

    patterns = [
        (r"ghp_[A-Za-z0-9]{36}", "[REDACTED_GITHUB_TOKEN]"),
        (r"AKIA[A-Z0-9]{16}", "[REDACTED_AWS_KEY]"),
        (r"sk-[A-Za-z0-9]{48,}", "[REDACTED_OPENAI_KEY]"),
        (r"key=[^\s]+", "key=[REDACTED]"),
        (r"token=[^\s]+", "token=[REDACTED]"),
        (r"password=[^\s]+", "password=[REDACTED]"),
        (r"Bearer [A-Za-z0-9._-]+", "Bearer [REDACTED]"),
    ]

    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    return text
