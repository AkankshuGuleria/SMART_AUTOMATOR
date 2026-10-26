"""
automation/win32.py — thin ctypes layer over the Win32 calls AUTOMATA needs.

Owns:    Window enumeration, foreground switching, keyboard chords, and
         DPI-correct screen capture to PNG, all in-process (no PowerShell).
Never:   Decides *whether* an action is allowed or reports success to the
         user — that is automation/desktop.py's job. Functions here return
         facts (handles, rectangles, booleans read back from Windows).
"""

from __future__ import annotations

import ctypes
import struct
import sys
import time
import zlib
from dataclasses import dataclass

IS_WINDOWS = sys.platform == "win32"


@dataclass
class WindowInfo:
    hwnd: int
    pid: int
    exe: str
    title: str

    def as_dict(self) -> dict:
        return {"hwnd": self.hwnd, "pid": self.pid, "exe": self.exe, "title": self.title}


if IS_WINDOWS:
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
    try:
        dwmapi = ctypes.WinDLL("dwmapi")
    except OSError:  # pragma: no cover - dwmapi ships with every supported Windows
        dwmapi = None

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    # 64-bit handles: declare restypes so pointers are not truncated to int32.
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindow.restype = wintypes.HWND
    user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.BringWindowToTop.argtypes = [wintypes.HWND]
    user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetDC.argtypes = [wintypes.HWND]
    user32.GetDC.restype = ctypes.c_void_p
    user32.ReleaseDC.argtypes = [wintypes.HWND, ctypes.c_void_p]
    user32.keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ctypes.c_void_p]
    user32.PrintWindow.argtypes = [wintypes.HWND, ctypes.c_void_p, wintypes.UINT]
    user32.PrintWindow.restype = wintypes.BOOL
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD

    gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
    gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
    gdi32.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    gdi32.CreateCompatibleBitmap.restype = ctypes.c_void_p
    gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    gdi32.SelectObject.restype = ctypes.c_void_p
    gdi32.BitBlt.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                             ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                             wintypes.DWORD]
    gdi32.GetDIBits.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT, wintypes.UINT,
                                ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]
    gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
    gdi32.DeleteDC.argtypes = [ctypes.c_void_p]

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
            ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD),
            ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD),
            ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
            ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD),
        ]

GW_OWNER = 4
SW_RESTORE = 9
VK = {
    "ctrl": 0x11, "shift": 0x10, "alt": 0x12, "win": 0x5B, "enter": 0x0D, "return": 0x0D,
    "tab": 0x09, "escape": 0x1B, "esc": 0x1B, "space": 0x20, "backspace": 0x08,
    "delete": 0x2E, "home": 0x24, "end": 0x23, "up": 0x26, "down": 0x28,
    "left": 0x25, "right": 0x27,
    # media / volume keys work system-wide (Spotify, browsers, any player)
    "media_play_pause": 0xB3, "media_next": 0xB0, "media_prev": 0xB1, "media_stop": 0xB2,
    "volume_up": 0xAF, "volume_down": 0xAE, "volume_mute": 0xAD,
    **{chr(c): c - 32 for c in range(ord("a"), ord("z") + 1)},  # 'a' → 0x41 …
    **{str(d): 0x30 + d for d in range(10)},
    **{f"f{n}": 0x6F + n for n in range(1, 13)},  # f1 → 0x70 …
}
KEYEVENTF_KEYUP = 0x0002
SRCCOPY = 0x00CC0020
CAPTUREBLT = 0x40000000
DWMWA_EXTENDED_FRAME_BOUNDS = 9
DWMWA_CLOAKED = 14

_dpi_set = False


def input_disabled() -> bool:
    """True when synthetic input is switched off (always in the test suite)."""
    import os

    return os.environ.get("AUTOMATA_DISABLE_DESKTOP_INPUT", "").strip() in {"1", "true", "yes"}


def ensure_dpi_aware() -> None:
    """Make coordinates physical pixels (fixes 1536x864 captures at 125 % scaling).

    The backend has no UI, so per-monitor awareness for the whole process is safe.
    """
    global _dpi_set
    if _dpi_set or not IS_WINDOWS:
        return
    _dpi_set = True
    try:
        if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):  # PER_MONITOR_AWARE_V2
            return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.WinDLL("shcore").SetProcessDpiAwareness(2)
        return
    except (AttributeError, OSError):
        pass
    try:
        user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass


# ─── windows ─────────────────────────────────────────────────────────────────

_exe_cache: dict[int, str] = {}


def _exe_for_pid(pid: int) -> str:
    if pid in _exe_cache:
        return _exe_cache[pid]
    try:
        import psutil

        name = psutil.Process(pid).name()
    except Exception:
        name = ""
    if len(_exe_cache) > 1024:
        _exe_cache.clear()
    _exe_cache[pid] = name
    return name


def _title(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(min(length, 1024) + 1)
    user32.GetWindowTextW(hwnd, buf, len(buf))
    return buf.value


def _pid(hwnd: int) -> int:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value)


def _is_cloaked(hwnd: int) -> bool:
    if dwmapi is None:
        return False
    cloaked = wintypes.DWORD()
    res = dwmapi.DwmGetWindowAttribute(
        wintypes.HWND(hwnd), DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
    )
    return res == 0 and cloaked.value != 0


def window_info(hwnd: int) -> WindowInfo | None:
    if not IS_WINDOWS or not hwnd or not user32.IsWindow(hwnd):
        return None
    pid = _pid(hwnd)
    return WindowInfo(hwnd=int(hwnd), pid=pid, exe=_exe_for_pid(pid), title=_title(hwnd))


def foreground() -> WindowInfo | None:
    if not IS_WINDOWS:
        return None
    return window_info(user32.GetForegroundWindow())


def top_level_windows() -> list[WindowInfo]:
    """Visible, titled, unowned, non-cloaked top-level windows in Z-order (front first)."""
    if not IS_WINDOWS:
        return []
    found: list[WindowInfo] = []

    def _cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd) or user32.GetWindow(hwnd, GW_OWNER):
            return True
        title = _title(hwnd)
        if not title or _is_cloaked(hwnd):
            return True
        pid = _pid(hwnd)
        found.append(WindowInfo(hwnd=int(hwnd), pid=pid, exe=_exe_for_pid(pid), title=title))
        return True

    user32.EnumWindows(WNDENUMPROC(_cb), 0)
    return found


def activate(hwnd: int, timeout: float = 1.5) -> bool:
    """Bring *hwnd* to the foreground and return whether Windows actually did it.

    Windows refuses SetForegroundWindow from background processes, so this
    attaches to the foreground thread's input queue and, if that is not
    enough, taps ALT (which grants the calling process foreground rights).
    """
    if not IS_WINDOWS or input_disabled() or not user32.IsWindow(hwnd):
        return False
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)

    def _try(tap_alt: bool) -> bool:
        current = kernel32.GetCurrentThreadId()
        fg = user32.GetForegroundWindow()
        fg_thread = user32.GetWindowThreadProcessId(fg, None) if fg else 0
        target_thread = user32.GetWindowThreadProcessId(hwnd, None)
        attached = []
        for thread in {fg_thread, target_thread}:
            if thread and thread != current and user32.AttachThreadInput(current, thread, True):
                attached.append(thread)
        try:
            if tap_alt:
                user32.keybd_event(VK["alt"], 0, 0, None)
                user32.keybd_event(VK["alt"], 0, KEYEVENTF_KEYUP, None)
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
        finally:
            for thread in attached:
                user32.AttachThreadInput(current, thread, False)
        deadline = time.monotonic() + timeout / 2
        while time.monotonic() < deadline:
            if int(user32.GetForegroundWindow() or 0) == int(hwnd):
                return True
            time.sleep(0.05)
        return False

    return _try(tap_alt=False) or _try(tap_alt=True)


def send_chord(chord: str) -> None:
    """Press a chord like 'ctrl+v' or 'enter' with keybd_event (modifiers released last)."""
    if input_disabled():
        raise PermissionError("Synthetic keyboard input is disabled (AUTOMATA_DISABLE_DESKTOP_INPUT)")
    keys = [VK[part] for part in chord.lower().split("+")]
    for vk in keys:
        user32.keybd_event(vk, 0, 0, None)
    for vk in reversed(keys):
        user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, None)


# ─── capture ─────────────────────────────────────────────────────────────────


def window_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    """(left, top, width, height) of the visible frame in physical pixels."""
    ensure_dpi_aware()
    rect = wintypes.RECT()
    ok = False
    if dwmapi is not None:
        ok = dwmapi.DwmGetWindowAttribute(
            wintypes.HWND(hwnd), DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(rect), ctypes.sizeof(rect)
        ) == 0
    if not ok and not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    width, height = rect.right - rect.left, rect.bottom - rect.top
    if width <= 0 or height <= 0:
        return None
    return rect.left, rect.top, width, height


def primary_screen_rect() -> tuple[int, int, int, int]:
    ensure_dpi_aware()
    return 0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def capture_rect(left: int, top: int, width: int, height: int) -> bytes:
    """Return PNG bytes of a screen rectangle (physical pixels)."""
    ensure_dpi_aware()
    if width <= 0 or height <= 0:
        raise ValueError("capture region must have a positive width and height")
    screen_dc = user32.GetDC(None)
    mem_dc = gdi32.CreateCompatibleDC(screen_dc)
    bitmap = gdi32.CreateCompatibleBitmap(screen_dc, width, height)
    old = gdi32.SelectObject(mem_dc, bitmap)
    try:
        if not gdi32.BitBlt(mem_dc, 0, 0, width, height, screen_dc, left, top, SRCCOPY | CAPTUREBLT):
            raise OSError("BitBlt failed")
        header = BITMAPINFOHEADER()
        header.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        header.biWidth, header.biHeight = width, -height  # negative = top-down rows
        header.biPlanes, header.biBitCount = 1, 32
        buf = ctypes.create_string_buffer(width * height * 4)
        # BITMAPINFO = header + colour table; 16 spare bytes keep GetDIBits happy.
        bmi = ctypes.create_string_buffer(bytes(header) + b"\x00" * 16)
        if not gdi32.GetDIBits(mem_dc, bitmap, 0, height, buf, bmi, 0):
            raise OSError("GetDIBits failed")
    finally:
        gdi32.SelectObject(mem_dc, old)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(None, screen_dc)
    return encode_png_bgra(buf.raw, width, height)


# ─── clipboard (Unicode, no PowerShell) ──────────────────────────────────────

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

if IS_WINDOWS:
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = ctypes.c_void_p
    user32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p
    user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalFree.argtypes = [ctypes.c_void_p]


def _open_clipboard(attempts: int = 10) -> bool:
    """The clipboard is a shared lock; another app may hold it for a moment."""
    for _ in range(attempts):
        if user32.OpenClipboard(None):
            return True
        time.sleep(0.05)
    return False


def set_clipboard_text(text: str) -> bool:
    """Put *text* on the clipboard as CF_UNICODETEXT (any characters, any length)."""
    if not IS_WINDOWS or not _open_clipboard():
        return False
    try:
        user32.EmptyClipboard()
        data = (text + "\0").encode("utf-16-le")
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not handle:
            return False
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            kernel32.GlobalFree(handle)
            return False
        ctypes.memmove(ptr, data, len(data))
        kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            kernel32.GlobalFree(handle)  # ownership passes to Windows only on success
            return False
        return True
    finally:
        user32.CloseClipboard()


def get_clipboard_text() -> str | None:
    """Clipboard text, '' when it holds no text, None if it could not be opened."""
    if not IS_WINDOWS or not _open_clipboard():
        return None
    try:
        if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
            return ""
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return ""
        try:
            return ctypes.wstring_at(ptr)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def capture_window(hwnd: int) -> bytes:
    """PNG of one window's own content via PrintWindow — correct even when other
    windows (AUTOMATA's bar, say) are on top of it. Falls back to a screen grab."""
    ensure_dpi_aware()
    win = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(win)):
        raise OSError("window not found")
    width, height = win.right - win.left, win.bottom - win.top
    if width <= 0 or height <= 0:
        raise OSError("window has no size")
    screen_dc = user32.GetDC(None)
    mem_dc = gdi32.CreateCompatibleDC(screen_dc)
    bitmap = gdi32.CreateCompatibleBitmap(screen_dc, width, height)
    old = gdi32.SelectObject(mem_dc, bitmap)
    try:
        PW_RENDERFULLCONTENT = 0x2  # needed for Chromium/Electron and DirectX content
        if not user32.PrintWindow(hwnd, mem_dc, PW_RENDERFULLCONTENT):
            raise OSError("PrintWindow failed")
        header = BITMAPINFOHEADER()
        header.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        header.biWidth, header.biHeight = width, -height
        header.biPlanes, header.biBitCount = 1, 32
        buf = ctypes.create_string_buffer(width * height * 4)
        bmi = ctypes.create_string_buffer(bytes(header) + b"\x00" * 16)
        if not gdi32.GetDIBits(mem_dc, bitmap, 0, height, buf, bmi, 0):
            raise OSError("GetDIBits failed")
    except OSError:
        rect = window_rect(hwnd)
        if not rect:
            raise
        return capture_rect(*rect)
    finally:
        gdi32.SelectObject(mem_dc, old)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(None, screen_dc)
    if not any(buf.raw[i] for i in range(0, min(len(buf.raw), 400_000), 97)):
        rect = window_rect(hwnd)  # all black: the app refused PrintWindow
        if rect:
            return capture_rect(*rect)
    return encode_png_bgra(buf.raw, width, height)


def encode_png_bgra(bgra: bytes, width: int, height: int) -> bytes:
    """Encode top-down BGRA pixels as an RGB PNG (no Pillow needed)."""
    rgb = bytearray(width * height * 3)
    rgb[0::3] = bgra[2::4]
    rgb[1::3] = bgra[1::4]
    rgb[2::3] = bgra[0::4]
    stride = width * 3
    raw = b"".join(b"\x00" + bytes(rgb[y * stride:(y + 1) * stride]) for y in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 3))
        + chunk(b"IEND", b"")
    )


# ─── unicode typing ──────────────────────────────────────────────────────────

if IS_WINDOWS:
    ULONG_PTR = ctypes.c_size_t

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class _INPUTUNION(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]

    user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    user32.SendInput.restype = wintypes.UINT

KEYEVENTF_UNICODE = 0x0004
INPUT_KEYBOARD = 1


def send_unicode(text: str) -> int:
    """Type *text* as Unicode key events (single-line; no Enter). Returns events sent."""
    if input_disabled():
        raise PermissionError("Synthetic keyboard input is disabled (AUTOMATA_DISABLE_DESKTOP_INPUT)")
    units = text.encode("utf-16-le")
    codes = [int.from_bytes(units[i:i + 2], "little") for i in range(0, len(units), 2)]
    events = []
    for code in codes:
        for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
            inp = INPUT(type=INPUT_KEYBOARD)
            inp.u.ki = KEYBDINPUT(0, code, flags, 0, 0)
            events.append(inp)
    sent = 0
    for start in range(0, len(events), 200):
        chunk = events[start:start + 200]
        arr = (INPUT * len(chunk))(*chunk)
        sent += user32.SendInput(len(chunk), arr, ctypes.sizeof(INPUT))
        time.sleep(0.01)
    return sent
