"""
security/defender.py — notice when Windows Defender blocks an app AUTOMATA started.

Owns:    Reading Microsoft Defender's own event log (Controlled Folder Access
         blocks, event 1123) so AUTOMATA can explain a "Unauthorized changes
         blocked" popup instead of leaving the user guessing.
Never:   Changes Defender settings, adds exclusions or allows apps. That is the
         user's decision; AUTOMATA only explains how to do it.
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from typing import Any

logger = logging.getLogger(__name__)

HOW_TO_ALLOW = (
    "Windows Security → Virus & threat protection → Ransomware protection → "
    "Manage ransomware protection → Allow an app through Controlled folder access → Add an allowed app"
)

_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$since = (Get-Date).AddSeconds(-[int]$env:AUTOMATA_DEFENDER_SECONDS)
try {
  $events = Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-Windows Defender/Operational'; Id=1123; StartTime=$since} -MaxEvents 50
} catch { '[]'; exit 0 }
$out = foreach ($e in $events) {
  $x = [xml]$e.ToXml()
  $d = @{}
  foreach ($n in $x.Event.EventData.Data) { $d[$n.Name] = $n.'#text' }
  [pscustomobject]@{ time = $e.TimeCreated.ToString('o'); process = $d['Process Name']; path = $d['Path'] }
}
@($out) | ConvertTo-Json -Compress
"""


def recent_blocks(seconds: int = 120) -> list[dict[str, Any]]:
    """Controlled Folder Access blocks in the last *seconds* (newest first)."""
    import os
    import sys

    if sys.platform != "win32":
        return []
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", _SCRIPT],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
            env={**os.environ, "AUTOMATA_DEFENDER_SECONDS": str(int(seconds))},
        )
        data = json.loads((out.stdout or "").strip() or "[]")
    except Exception as exc:
        logger.debug("defender: could not read the event log — %s", exc)
        return []
    if isinstance(data, dict):
        data = [data]
    return [d for d in data if d.get("process")]


def _app_name(process_path: str) -> str:
    import os

    return os.path.splitext(os.path.basename(process_path or ""))[0] or "an app"


def explain_block(process_hint: str, seconds: int = 60) -> str | None:
    """A plain explanation if Defender just blocked a process matching *process_hint*."""
    hint = process_hint.lower()
    for block in recent_blocks(seconds):
        if hint in (block.get("process") or "").lower():
            app = _app_name(block["process"])
            folder = block.get("path") or "a protected folder"
            return (f"Windows Defender blocked {app} from writing to {folder} (Controlled folder access). "
                    f"That popup comes from Windows, not AUTOMATA. To stop it, allow {app} yourself: {HOW_TO_ALLOW}.")
    return None


def summary(days: int = 7) -> dict[str, Any]:
    """Apps Defender blocked recently (for Setup & health)."""
    blocks = recent_blocks(days * 86400)
    apps: dict[str, dict[str, Any]] = {}
    for b in blocks:
        name = _app_name(b["process"])
        entry = apps.setdefault(name, {"app": name, "count": 0, "last": b.get("time"), "folders": set()})
        entry["count"] += 1
        if b.get("path"):
            entry["folders"].add(b["path"])
    rows = [{**a, "folders": sorted(a["folders"])} for a in apps.values()]
    return {"blocked_apps": sorted(rows, key=lambda r: -r["count"]), "how_to_allow": HOW_TO_ALLOW,
            "checked_at": time.time()}
