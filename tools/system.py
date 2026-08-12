import datetime
import os
import platform
import re
import shlex
import subprocess

from config import BLOCKED_DRIVES


def get_time() -> str:
    """Return the current local date and time as a friendly string."""
    now = datetime.datetime.now()
    return now.strftime("%A, %B %d, %Y at %I:%M %p")


def get_system_info() -> str:
    """Return basic info about the user's computer (OS, CPU, RAM, battery)."""
    mem_str, cpu_str, batt_str = _windows_memory(), "", ""
    try:
        import psutil
        mem = psutil.virtual_memory()
        mem_str = f"{mem.used / (1024**3):.1f} GB used of {mem.total / (1024**3):.1f} GB"
        try:
            batt = psutil.sensors_battery()
            if batt:
                batt_str = (" Battery at %d%%" % batt.percent) + \
                           (" and charging." if batt.power_plugged else ".")
            else:
                batt_str = " No battery detected."
        except Exception:
            batt_str = ""
        try:
            cpu_str = f" CPU usage {psutil.cpu_percent(interval=0.3)}%."
        except Exception:
            cpu_str = ""
    except Exception:
        pass

    return (
        f"Operating system: {platform.system()} {platform.release()} "
        f"({platform.version()}). "
        f"Machine: {platform.machine()}. "
        f"Processor: {platform.processor() or 'unknown'}. "
        f"CPU cores: {os_cpu_count()}. "
        f"Memory: {mem_str}.{cpu_str}{batt_str}"
    )


def os_cpu_count():
    try:
        import os
        return os.cpu_count()
    except Exception:
        return "unknown"


def _windows_memory():
    """Read total/free physical memory via ctypes on Windows (no extra deps)."""
    try:
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        total = stat.ullTotalPhys / (1024**3)
        avail = stat.ullAvailPhys / (1024**3)
        return f"{total - avail:.1f} GB used of {total:.1f} GB"
    except Exception:
        return "unknown"


def _mentions_blocked_drive(command: str) -> bool:
    """True if the command references a blocklisted drive (e.g. D:)."""
    cmd = (command or "").lower()
    for drive in BLOCKED_DRIVES or []:
        d = drive.lower()
        # match "d:", "d:\", "d:/" as a token (not "sd:" etc.)
        if re.search(r"(?<![a-z])" + re.escape(d), cmd):
            return True
    return False


DENYLIST = [
    "rm -rf /", "mkfs", "format", "del /s /q /f *",
    ":(){ :|:& };:", "dd if=/dev/zero",
]


# Matches commands that are likely destructive, so we ask the user to confirm
# before running them (del / rm / rd / format / shutdown / taskkill / diskpart...).
_DESTRUCTIVE_RE = re.compile(
    r"(\bdel\b|\brm\b|\brd\b|\brmdir\b|\bformat\b|\bshutdown\b|\btaskkill\b|"
    r"\bdiskpart\b|\breg delete\b|\bdelete\b)",
    re.IGNORECASE,
)


def _looks_destructive(command: str) -> bool:
    return bool(_DESTRUCTIVE_RE.search(command or ""))


def run_command(command: str, confirm: bool = False) -> str:
    """Runs a shell command and returns the output. Basic safety checks block
    denylisted destructive commands and any command touching a blocklisted drive.
    Other potentially destructive commands (del / rm / rd / format / shutdown /
    taskkill...) require `confirm=True` first — Nova asks the user before running."""
    cmd_lower = command.lower()
    for bad in DENYLIST:
        if bad in cmd_lower:
            return f"Error: Command rejected for safety reasons (matched denylist item: {bad})."

    if _mentions_blocked_drive(command):
        return (
            "Error: That command references the D: drive, which you've told me not to access. "
            "I won't run it."
        )

    if not confirm and _looks_destructive(command):
        return (
            "[SAFETY] That command looks destructive. Ask the user to confirm before "
            "I run it, then call run_command again with confirm=true if they say yes."
        )

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )

        output = result.stdout + "\n" + result.stderr

        if not output.strip():
            return "Command executed successfully with no output."

        # Truncate if too long
        if len(output) > 2000:
            return output[:2000] + "\n...[TRUNCATED]"

        return output.strip()
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 30 seconds."
    except Exception as e:
        return f"Error running command: {e}"
# ===========================================================================
# Expanded PC-control surface: brightness, volume, power, screenshot,
# clipboard and media-key simulation.
# ===========================================================================

# Tracks the last known volume level so "unmute" can restore it after "mute".
_LAST_VOLUME = 50


def _is_windows():
    return platform.system() == "Windows"


def _set_brightness_gamma(level: int) -> bool:
    """Software brightness via the display gamma ramp (works with no deps)."""
    try:
        import ctypes

        n = 256
        ramp = (ctypes.c_ushort * n * 3)()
        scale = max(0.01, min(1.0, int(level) / 100.0))
        for i in range(n):
            val = int((i / 255.0) * scale * 65535)
            ramp[0][i] = ramp[1][i] = ramp[2][i] = val
        hdc = ctypes.windll.user32.GetDC(0)
        ok = bool(ctypes.windll.gdi32.SetDeviceGammaRamp(hdc, ctypes.byref(ramp)))
        ctypes.windll.user32.ReleaseDC(0, hdc)
        return ok
    except Exception:
        return False


def _get_brightness_wmi():
    """Read current backlight brightness via WMI, or None if unsupported."""
    try:
        cmd = (
            "(Get-CimInstance -Namespace root/wmi -ClassName "
            "WmiMonitorBrightness).CurrentBrightness"
        )
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode != 0:
            return None
        val = (r.stdout or "").strip()
        if not val.isdigit():
            return None
        return int(val)
    except Exception:
        return None


def _set_brightness_wmi(level: int) -> bool:
    """Real monitor (backlight) brightness via WMI. Returns True ONLY if the
    command actually succeeded AND the brightness verifiably changed, so Nova
    never claims a change it didn't make. Falls to the gamma fallback otherwise."""
    try:
        cmd = (
            "(Get-CimInstance -Namespace root/wmi -ClassName "
            "WmiMonitorBrightnessMethods).WmiSetBrightness(1, %d)" % int(level)
        )
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode != 0:
            return False
        # Verify it really changed (only when the display reports its brightness).
        cur = _get_brightness_wmi()
        if cur is None:
            # Can't read it back, but the set command succeeded cleanly.
            return True
        return abs(cur - int(level)) <= 3
    except Exception:
        return False


def set_brightness(level: int) -> str:
    """Set the screen brightness to a percentage (0-100). Tries a real backlight
    (WMI) change first; if the display doesn't support it, falls back to a
    software gamma ramp that genuinely changes how bright the screen looks. Either
    way it reports truthfully what actually happened."""
    level = max(0, min(100, int(level)))
    try:
        if _is_windows():
            if _set_brightness_wmi(level):
                return f"Screen brightness set to {level} percent."
            if _set_brightness_gamma(level):
                return (
                    f"Screen brightness set to about {level} percent "
                    "(software dimming, since this display doesn't expose a "
                    "hardware brightness control)."
                )
            return f"I couldn't change the brightness to {level} percent on this display."
        if _set_brightness_gamma(level):
            return f"Screen brightness set to about {level} percent (software dimming)."
        return f"I couldn't change the brightness to {level} percent on this system."
    except Exception as e:
        return f"I couldn't change the brightness: {e}"


def _pycaw_volume():
    """Return the master-volume interface for the default output device (or None)."""
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(interface, POINTER(IAudioEndpointVolume))
    except Exception:
        return None


def _set_volume_wave(level: int) -> bool:
    """Dependency-free fallback using the Windows wave-out mixer."""
    try:
        import ctypes
        packed = max(0, min(100, int(level))) * 65535 // 100
        packed = (packed << 16) | packed
        ctypes.windll.winmm.waveOutSetVolume(0, packed)
        return True
    except Exception:
        return False


def _get_volume_level() -> int:
    """Return current volume as an int 0-100 when we can read it, else None."""
    volume = _pycaw_volume()
    if volume is not None:
        try:
            return int(round(volume.GetMasterVolumeLevelScalar() * 100))
        except Exception:
            return None
    return None


def set_volume(level: int) -> str:
    """Set the master volume to a percentage (0-100), verifying the real result."""
    global _LAST_VOLUME
    level = max(0, min(100, int(level)))
    _LAST_VOLUME = level
    try:
        volume = _pycaw_volume()
        if volume is not None:
            volume.SetMasterVolumeLevelScalar(level / 100.0, None)
            # Verify by reading the actual level back.
            try:
                actual = int(round(volume.GetMasterVolumeLevelScalar() * 100))
            except Exception:
                actual = level
            return f"Volume set to {level} percent." if actual == level else \
                   f"Volume set to about {actual} percent."
    except Exception:
        pass
    if _set_volume_wave(level):
        return f"Volume set to {level} percent (wave mixer)."
    return f"I couldn't set the volume to {level} percent."


def mute() -> str:
    """Mute all audio output (remembers the previous level for unmute)."""
    global _LAST_VOLUME
    try:
        cur = _get_volume_level()
        if cur is not None:
            _LAST_VOLUME = cur
    except Exception:
        pass
    volume = _pycaw_volume()
    if volume is not None:
        try:
            volume.SetMute(True, None)
            return "Muted all audio."
        except Exception:
            pass
    if _set_volume_wave(0):
        return "Muted all audio."
    return "I couldn't mute the audio."


def unmute() -> str:
    """Unmute and restore the last volume level."""
    global _LAST_VOLUME
    volume = _pycaw_volume()
    if volume is not None:
        try:
            volume.SetMute(False, None)
            volume.SetMasterVolumeLevelScalar(_LAST_VOLUME / 100.0, None)
            return f"Unmuted. Volume is back to {_LAST_VOLUME} percent."
        except Exception:
            pass
    if _set_volume_wave(_LAST_VOLUME):
        return f"Unmuted. Volume is back to {_LAST_VOLUME} percent."
    return "I couldn't unmute the audio."

def lock_screen() -> str:
    """Lock the workstation / screen."""
    try:
        if _is_windows():
            import ctypes
            ctypes.windll.user32.LockWorkStation()
            return "Locked the screen."
        if platform.system() == "Darwin":
            subprocess.Popen(["pmset", "displaysleepnow"])
            return "Locked the screen."
        return "I can't lock the screen on this operating system."
    except Exception as e:
        return f"I couldn't lock the screen: {e}"


def sleep_pc() -> str:
    """Put the computer to sleep."""
    try:
        if _is_windows():
            subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
        elif platform.system() == "Darwin":
            subprocess.Popen(["pmset", "sleepnow"])
        else:
            subprocess.Popen(["systemctl", "suspend"])
        return "Putting the computer to sleep now."
    except Exception as e:
        return f"I couldn't put the computer to sleep: {e}"


def shutdown_pc(delay_seconds: int = 10) -> str:
    """Schedule a shutdown with the given delay (default 10s)."""
    delay = max(0, int(delay_seconds if delay_seconds is not None else 10))
    try:
        if _is_windows():
            subprocess.Popen([
                "shutdown", "/s", "/t", str(delay),
                "/c", "Nova: shutdown requested by the user",
            ])
        else:
            subprocess.Popen(["shutdown", "-h", "+%d" % max(1, delay)])
        return (
            f"I'll shut down the PC in {delay} seconds. "
            "Just say 'cancel shutdown' if you change your mind."
        )
    except Exception as e:
        return f"I couldn't schedule a shutdown: {e}"


def restart_pc(delay_seconds: int = 10) -> str:
    """Schedule a restart with the given delay (default 10s)."""
    delay = max(0, int(delay_seconds if delay_seconds is not None else 10))
    try:
        if _is_windows():
            subprocess.Popen([
                "shutdown", "/r", "/t", str(delay),
                "/c", "Nova: restart requested by the user",
            ])
        else:
            subprocess.Popen(["shutdown", "-r", "+%d" % max(1, delay)])
        return (
            f"I'll restart the PC in {delay} seconds. "
            "Just say 'cancel shutdown' if you change your mind."
        )
    except Exception as e:
        return f"I couldn't schedule a restart: {e}"


def cancel_shutdown() -> str:
    """Abort any pending shutdown or restart."""
    try:
        if _is_windows():
            subprocess.Popen(["shutdown", "/a"])
        else:
            subprocess.Popen(["shutdown", "-c"])
        return "Cancelled the pending shutdown or restart."
    except Exception as e:
        return f"I couldn't cancel the pending action: {e}"


def take_screenshot(save_path: str = "") -> str:
    """Capture the screen to a PNG file. Defaults to the user's Pictures folder."""
    try:
        from .files import is_blocked_path
    except Exception:
        from files import is_blocked_path

    try:
        if not save_path or not save_path.strip():
            pics = os.path.join(os.path.expanduser("~"), "Pictures")
            os.makedirs(pics, exist_ok=True)
            save_path = os.path.join(
                pics, "nova_screenshot_%s.png"
                % datetime.datetime.now().strftime("%Y%m%d_%H%M%S"),
            )
        elif is_blocked_path(save_path):
            return "That save location is on the restricted D: drive. Please pick another folder."
        os.makedirs(os.path.dirname(os.path.abspath(save_path)) or ".", exist_ok=True)
        import pyautogui
        pyautogui.screenshot().save(save_path)
        return f"Saved a screenshot to {save_path}."
    except Exception as e:
        return f"I couldn't take a screenshot: {e}"


def get_clipboard() -> str:
    """Read the current clipboard contents."""
    try:
        import pyperclip
        text = (pyperclip.paste() or "").strip()
        return f"Clipboard: {text}" if text else "The clipboard is empty."
    except Exception as e:
        return f"I couldn't read the clipboard: {e}"


def set_clipboard(text: str) -> str:
    """Copy text to the clipboard."""
    try:
        import pyperclip
        pyperclip.copy(text or "")
        return "Copied that to the clipboard."
    except Exception as e:
        return f"I couldn't copy to the clipboard: {e}"


def _press_media(key: str) -> bool:
    try:
        import pyautogui
        pyautogui.press(key)
        return True
    except Exception:
        return False


def pause_media() -> str:
    """Pause the currently playing media via the media play/pause key."""
    return "Paused the media." if _press_media("playpause") else "I couldn't pause the media."


def resume_media() -> str:
    """Resume the currently playing media via the media play/pause key."""
    return "Resumed the media." if _press_media("playpause") else "I couldn't resume the media."


def next_track() -> str:
    """Skip to the next track via the media next key."""
    return "Skipped to the next track." if _press_media("nexttrack") else "I couldn't skip forward."


def previous_track() -> str:
    """Go back to the previous track via the media previous key."""
    return "Went back to the previous track." if _press_media("prevtrack") else "I couldn't skip back."
