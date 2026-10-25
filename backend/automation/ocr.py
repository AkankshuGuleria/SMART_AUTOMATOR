"""
automation/ocr.py — AUTOMATA Visual Feedback Layer: OCR text extraction.

Owns:    Extracting text from screenshots and images using OCR.
         Redacts secret-shaped strings before storage or model handoff.
Never:   Must not write to CockroachDB. Must not call Bedrock.
         Must not be called from Memory Engine or Reasoning Engine code.
Ref:     ARCHITECTURE.md §3.2c, FEATURES_PHASE.md §9 (Visual Feedback Layer).
"""

import logging
import os
import re

logger = logging.getLogger(__name__)


def ocr_image(image_path: str) -> str:
    """
    Extract text from an image using OCR.

    Tries pytesseract first (requires Tesseract + tesseract-ocr),
    falls back to a PowerShell-based approach, and returns empty
    string if neither is available.

    The extracted text is passed through redact_secrets() before
    being returned, to prevent secrets from being stored or
    handed off to models.
    """
    if not image_path or not os.path.exists(image_path):
        logger.warning("ocr.ocr_image: file not found | path=%s", image_path)
        return ""

    text = _ocr_with_tesseract(image_path)
    if not text:
        text = _ocr_with_powershell(image_path)

    # Redact secrets before returning
    text = redact_secrets(text)

    logger.info("ocr.ocr_image: extracted %d chars from %s", len(text), image_path)
    return text


def _ocr_with_tesseract(image_path: str) -> str:
    """Try OCR using pytesseract (requires Tesseract OCR installed)."""
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(image_path)
        text = pytesseract.image_to_string(img)
        return text.strip()
    except ImportError:
        logger.debug("ocr._ocr_with_tesseract: pytesseract or Pillow not available")
    except Exception as exc:
        logger.debug("ocr._ocr_with_tesseract: failed — %s", exc)
    return ""


def _ocr_with_powershell(image_path: str) -> str:
    """
    Fallback OCR using PowerShell and Windows OCR capabilities.

    Uses the Windows.Media.Ocr API via PowerShell to extract text.
    This requires Windows 10+ with the OCR language pack installed.
    """
    try:
        script = (
            f"Add-Type -AssemblyName System.Windows.Forms; "
            f"Add-Type -AssemblyName System.Drawing; "
            f'$img = [System.Drawing.Image]::FromFile("{image_path}"); '
            f"$clipboard = [System.Windows.Forms.Clipboard]; "
            f"$clipboard.SetImage($img); "
            f"Start-Sleep -Milliseconds 500; "
            f"Add-Type -AssemblyName Windows.Media.Ocr; "
            f"$ocrEngine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage("
            f'  [Windows.Globalization.Language]::new("en-US")); '
            f'if ($null -eq $ocrEngine) {{ Write-Output "ocr_unavailable"; exit }} '
            f"$bitmap = [Windows.Graphics.Imaging.SoftwareBitmap]::CreateCopyFromBuffer("
            f"  [Windows.Graphics.Imaging.BitmapDecoder]::Create("
            f'    [System.IO.File]::OpenRead("{image_path}"), '
            f"    [Windows.Graphics.Imaging.BitmapPixelFormat]::Bgra8, "
            f"    [Windows.Graphics.Imaging.BitmapAlphaMode]::Premultiplied), "
            f"  [Windows.Graphics.Imaging.BitmapBufferAccessMode]::Read); "
            f"$result = $ocrEngine.RecognizeAsync($bitmap); "
            f'$text = ""; '
            f"foreach ($line in $result.Lines) {{ "
            f'  foreach ($word in $line.Words) {{ $text += $word.Text + " " }}; '
            f'  $text += "`n" '
            f"}}; "
            f"$text.Trim()"
        )
        import subprocess

        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            shell=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if completed.returncode == 0 and completed.stdout.strip():
            return completed.stdout.strip()
    except Exception as exc:
        logger.debug("ocr._ocr_with_powershell: failed — %s", exc)
    return ""


def redact_secrets(text: str) -> str:
    """
    Redact secret-shaped strings from OCR text before storage or model handoff.

    Patterns redacted:
    - GitHub tokens: ghp_
    - AWS keys: AKIA
    - OpenAI keys: sk-
    - Generic key=value patterns
    - Generic token= patterns
    - Generic password= patterns
    - Bearer tokens
    """
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
