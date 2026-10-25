"""
monitoring/system_metrics.py — background host resource sampler.

Owns:    Periodic CPU / GPU / RAM / disk / network sampling with a short
         in-memory history, plus an on-demand top-process scan.
Never:   Blocks request handlers. Routes read the latest cached snapshot.

Cost model (measured on the dev laptop): CPU/RAM/NVML reads take well under
1 ms, a full process scan takes ~200 ms. The sampler therefore runs fast only
while a client is actively reading metrics, and scans processes only on demand.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
from typing import Any

logger = logging.getLogger(__name__)

try:  # psutil is a hard dependency, but keep import failures non-fatal.
    import psutil
except Exception:  # pragma: no cover - exercised only on broken installs
    psutil = None  # type: ignore[assignment]

FAST_INTERVAL_S = 2.0  # while someone is looking at the metrics
IDLE_INTERVAL_S = 15.0  # background history only
DEMAND_WINDOW_S = 30.0  # a read keeps the sampler fast for this long
PROCESS_SCAN_TTL_S = 8.0
HISTORY_POINTS = 180  # 6 min at the fast interval
TOP_PROCESS_COUNT = 8
GPU_STALE_S = 15.0  # how long a cached GPU reading may stand in for a failed read


class _GpuReader:
    """Reads NVIDIA GPU stats through NVML. Other vendors report unavailable."""

    def __init__(self) -> None:
        self._nvml = None
        self._handles: list[Any] = []
        self._error: str | None = None
        # Laptop (Optimus) GPUs intermittently raise NVMLError_Unknown while
        # switching power states; reuse a recent good reading instead of None.
        self._last_good: dict[tuple[int, str], tuple[Any, float]] = {}
        try:
            import pynvml

            pynvml.nvmlInit()
            count = pynvml.nvmlDeviceGetCount()
            self._handles = [pynvml.nvmlDeviceGetHandleByIndex(i) for i in range(count)]
            self._nvml = pynvml
        except Exception as exc:
            self._error = f"NVIDIA driver/NVML not available ({type(exc).__name__})"

    @property
    def available(self) -> bool:
        return self._nvml is not None and bool(self._handles)

    @property
    def error(self) -> str | None:
        return self._error

    def read(self) -> list[dict[str, Any]]:
        if not self.available:
            return []
        nv = self._nvml
        gpus: list[dict[str, Any]] = []
        for index, handle in enumerate(self._handles):
            entry: dict[str, Any] = {"index": index}
            for key, fn in (
                ("name", lambda h: nv.nvmlDeviceGetName(h)),
                ("utilization_percent", lambda h: nv.nvmlDeviceGetUtilizationRates(h).gpu),
                ("temperature_c", lambda h: nv.nvmlDeviceGetTemperature(h, 0)),
                ("power_watts", lambda h: round(nv.nvmlDeviceGetPowerUsage(h) / 1000, 1)),
            ):
                try:
                    value = fn(handle)
                    entry[key] = value.decode() if isinstance(value, bytes) else value
                    self._last_good[(index, key)] = (entry[key], time.monotonic())
                except Exception:
                    cached = self._last_good.get((index, key))
                    fresh = cached is not None and time.monotonic() - cached[1] < GPU_STALE_S
                    entry[key] = cached[0] if fresh else None
            try:
                mem = nv.nvmlDeviceGetMemoryInfo(handle)
                entry["memory_used_mb"] = round(mem.used / 2**20)
                entry["memory_total_mb"] = round(mem.total / 2**20)
                entry["memory_percent"] = round(mem.used / mem.total * 100, 1) if mem.total else 0
            except Exception:
                entry["memory_used_mb"] = entry["memory_total_mb"] = entry["memory_percent"] = None
            gpus.append(entry)
        return gpus

    def close(self) -> None:
        if self._nvml is not None:
            try:
                self._nvml.nvmlShutdown()
            except Exception:
                pass


def _system_drive() -> str:
    if os.name == "nt":
        return os.environ.get("SystemDrive", "C:") + "\\"
    return "/"


class SystemSampler(threading.Thread):
    """Daemon thread that keeps the latest host snapshot and a short history."""

    def __init__(self) -> None:
        super().__init__(name="system-sampler", daemon=True)
        self._stop_event = threading.Event()
        self._wake = threading.Event()
        self._lock = threading.Lock()
        self._latest: dict[str, Any] = {}
        self._history: deque[dict[str, Any]] = deque(maxlen=HISTORY_POINTS)
        self._last_demand = 0.0
        self._processes: list[dict[str, Any]] = []
        self._processes_at = 0.0
        self._process_lock = threading.Lock()
        self._prev_disk: tuple[float, Any] | None = None
        self._prev_net: tuple[float, Any] | None = None
        self._gpu: _GpuReader | None = None

    # ── lifecycle ────────────────────────────────────────────────────────────

    def run(self) -> None:
        if psutil is None:
            logger.warning("system sampler disabled: psutil is not installed")
            return
        self._gpu = _GpuReader()
        if not self._gpu.available:
            logger.info("system sampler: GPU metrics unavailable — %s", self._gpu.error)
        psutil.cpu_percent(None, percpu=True)  # prime: the first reading is always 0
        self._stop_event.wait(0.5)
        logger.info("system sampler started")
        while not self._stop_event.is_set():
            try:
                self._sample()
            except Exception as exc:
                logger.warning("system sampler: sample failed — %s", exc)
            fast = time.monotonic() - self._last_demand < DEMAND_WINDOW_S
            self._wake.wait(FAST_INTERVAL_S if fast else IDLE_INTERVAL_S)
            self._wake.clear()
        self._gpu.close()

    def stop(self) -> None:
        self._stop_event.set()
        self._wake.set()

    # ── sampling ─────────────────────────────────────────────────────────────

    def _rate(self, prev_attr: str, counters: Any, fields: tuple[str, str]) -> dict[str, float]:
        now = time.monotonic()
        prev = getattr(self, prev_attr)
        setattr(self, prev_attr, (now, counters))
        if prev is None or counters is None:
            return {fields[0]: 0.0, fields[1]: 0.0}
        elapsed = max(now - prev[0], 1e-3)
        old = prev[1]
        if fields[0].startswith("read"):
            a = (counters.read_bytes - old.read_bytes) / elapsed
            b = (counters.write_bytes - old.write_bytes) / elapsed
        else:
            a = (counters.bytes_recv - old.bytes_recv) / elapsed
            b = (counters.bytes_sent - old.bytes_sent) / elapsed
        return {fields[0]: round(max(a, 0.0)), fields[1]: round(max(b, 0.0))}

    def _sample(self) -> None:
        now = time.time()
        vm = psutil.virtual_memory()
        swap = psutil.swap_memory()
        per_core = psutil.cpu_percent(None, percpu=True)
        cpu_total = round(sum(per_core) / len(per_core), 1) if per_core else 0.0
        freq = None
        try:
            f = psutil.cpu_freq()
            freq = round(f.current) if f else None
        except Exception:
            pass

        try:
            disk = psutil.disk_usage(_system_drive())
            disk_info = {
                "mount": _system_drive(),
                "used_gb": round(disk.used / 2**30, 1),
                "total_gb": round(disk.total / 2**30, 1),
                "percent": disk.percent,
            }
        except Exception:
            disk_info = {
                "mount": _system_drive(),
                "used_gb": None,
                "total_gb": None,
                "percent": None,
            }
        try:
            disk_io = psutil.disk_io_counters()
        except Exception:
            disk_io = None
        disk_info.update(self._rate("_prev_disk", disk_io, ("read_bps", "write_bps")))

        try:
            net_io = psutil.net_io_counters()
        except Exception:
            net_io = None
        net_info = self._rate("_prev_net", net_io, ("recv_bps", "sent_bps"))

        battery = None
        try:
            b = psutil.sensors_battery()
            if b is not None:
                battery = {"percent": round(b.percent), "plugged_in": bool(b.power_plugged)}
        except Exception:
            pass

        gpus = self._gpu.read() if self._gpu else []
        primary_gpu = gpus[0] if gpus else None

        snapshot = {
            "timestamp": now,
            "cpu": {
                "percent": cpu_total,
                "per_core": [round(c, 1) for c in per_core],
                "cores_logical": psutil.cpu_count(logical=True),
                "cores_physical": psutil.cpu_count(logical=False),
                "frequency_mhz": freq,
            },
            "memory": {
                "percent": vm.percent,
                "used_gb": round((vm.total - vm.available) / 2**30, 2),
                "total_gb": round(vm.total / 2**30, 2),
                "available_gb": round(vm.available / 2**30, 2),
                "swap_percent": swap.percent,
            },
            "gpu": {
                "available": bool(gpus),
                "reason": None if gpus else (self._gpu.error if self._gpu else "not sampled"),
                "devices": gpus,
            },
            "disk": disk_info,
            "network": net_info,
            "battery": battery,
            "uptime_seconds": round(now - psutil.boot_time()),
        }
        point = {
            "t": round(now),
            "cpu": cpu_total,
            "ram": vm.percent,
            "gpu": primary_gpu.get("utilization_percent") if primary_gpu else None,
            "vram": primary_gpu.get("memory_percent") if primary_gpu else None,
        }
        with self._lock:
            self._latest = snapshot
            self._history.append(point)

    def _scan_processes(self) -> list[dict[str, Any]]:
        """Aggregate CPU/RAM by process name (Chrome's 30 helpers count as one)."""
        logical = psutil.cpu_count(logical=True) or 1
        totals: dict[str, dict[str, Any]] = {}
        for proc in psutil.process_iter(["name", "memory_info"]):
            try:
                name = proc.info.get("name") or "unknown"
                if name in {"System Idle Process", "Idle"}:
                    continue
                cpu = proc.cpu_percent(None) / logical
                mem = proc.info["memory_info"].rss if proc.info.get("memory_info") else 0
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            entry = totals.setdefault(
                name, {"name": name, "cpu_percent": 0.0, "memory_mb": 0.0, "count": 0}
            )
            entry["cpu_percent"] += cpu
            entry["memory_mb"] += mem / 2**20
            entry["count"] += 1
        rows = [
            {**e, "cpu_percent": round(e["cpu_percent"], 1), "memory_mb": round(e["memory_mb"])}
            for e in totals.values()
        ]
        by_cpu = sorted(rows, key=lambda r: r["cpu_percent"], reverse=True)[:TOP_PROCESS_COUNT]
        by_mem = sorted(rows, key=lambda r: r["memory_mb"], reverse=True)[:TOP_PROCESS_COUNT]
        merged = {r["name"]: r for r in by_cpu + by_mem}
        return sorted(
            merged.values(), key=lambda r: (r["cpu_percent"], r["memory_mb"]), reverse=True
        )

    def top_processes(self) -> list[dict[str, Any]]:
        if psutil is None:
            return []
        with self._process_lock:
            if self._processes_at == 0.0:
                # Per-process CPU needs two readings; prime once so the very
                # first table is not all zeros.
                try:
                    self._scan_processes()
                    time.sleep(0.4)
                except Exception:
                    pass
            if time.monotonic() - self._processes_at > PROCESS_SCAN_TTL_S:
                try:
                    self._processes = self._scan_processes()
                except Exception as exc:
                    logger.warning("system sampler: process scan failed — %s", exc)
                self._processes_at = time.monotonic()
            return list(self._processes)

    # ── reads ────────────────────────────────────────────────────────────────

    def snapshot(self, include_processes: bool = False) -> dict[str, Any]:
        was_idle = time.monotonic() - self._last_demand >= DEMAND_WINDOW_S
        self._last_demand = time.monotonic()
        if was_idle:
            self._wake.set()  # switch to the fast interval right away
        with self._lock:
            latest = dict(self._latest)
            history = list(self._history)
        if not latest:
            return {"available": False, "reason": "Sampler is starting", "history": history}
        result = {"available": True, **latest, "history": history}
        if include_processes:
            result["processes"] = self.top_processes()
        return result


_sampler: SystemSampler | None = None
_sampler_lock = threading.Lock()


def start_sampler() -> SystemSampler | None:
    """Start the process-wide sampler once. Safe to call repeatedly."""
    global _sampler
    if psutil is None:
        return None
    with _sampler_lock:
        if _sampler is None or not _sampler.is_alive():
            _sampler = SystemSampler()
            _sampler.start()
        return _sampler


def stop_sampler() -> None:
    global _sampler
    with _sampler_lock:
        if _sampler is not None:
            _sampler.stop()
            _sampler = None


def get_system_metrics(include_processes: bool = False) -> dict[str, Any]:
    """Latest host snapshot. Starts the sampler lazily if needed."""
    if psutil is None:
        return {"available": False, "reason": "psutil is not installed", "history": []}
    sampler = start_sampler()
    if sampler is None:
        return {"available": False, "reason": "Sampler unavailable", "history": []}
    snap = sampler.snapshot(include_processes)
    if not snap.get("available"):
        # First request right after startup: wait briefly for the first sample.
        for _ in range(10):
            time.sleep(0.1)
            snap = sampler.snapshot(include_processes)
            if snap.get("available"):
                break
    if not snap.get("available"):
        try:
            sampler._sample()
            snap = sampler.snapshot(include_processes)
        except Exception as exc:
            return {"available": False, "reason": str(exc), "history": []}
    return snap
