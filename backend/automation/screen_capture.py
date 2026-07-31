"""
automation/screen_capture.py — AUTOMATA Visual Feedback Layer: Screen Capture.

Owns:    Capturing screenshots of the full screen, active window, or selected
         region on Windows. Used by the visual feedback tools and the
         decision engine's visual action executors.
Never:   Must not write to CockroachDB. Must not call Bedrock.
         Must not be called from Memory Engine or Reasoning Engine code.
Ref:     ARCHITECTURE.md §3.2c, FEATURES_PHASE.md §9 (Visual Feedback Layer).
"""

import logging
import os
import tempfile
from datetime import datetime

from automation.os_windows import capture_screen

logger = logging.getLogger(__name__)


def capture_full_screen() -> str:
    """Capture the full screen and return the path to the saved image."""
    path = capture_screen()
    if path:
        logger.info("screen_capture.capture_full_screen: captured | path=%s", path)
    else:
        logger.warning("screen_capture.capture_full_screen: capture failed")
    return path


def capture_active_window() -> str:
    """Capture the active window and return the path to the saved image."""
    # On Windows, capturing the active window requires finding its handle.
    # For the MVP, we capture the full screen as a fallback.
    logger.info("screen_capture.capture_active_window: using full-screen fallback")
    return capture_full_screen()


def capture_region(left: int, top: int, width: int, height: int) -> str:
    """Capture a specific screen region and return the path to the saved image."""
    region = f"{left},{top},{width},{height}"
    path = capture_screen(region)
    if path:
        logger.info("screen_capture.capture_region: captured | path=%s", path)
    else:
        logger.warning("screen_capture.capture_region: capture failed")
    return path


def capture_temp_screenshot(region: str | None = None) -> str:
    """Capture a screenshot and save to a temp file. Returns the file path."""
    path = capture_screen(region)
    if not path:
        logger.error("screen_capture.capture_temp_screenshot: failed to capture screen")
    return path
