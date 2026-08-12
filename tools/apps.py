import difflib
import os
import subprocess
import platform

# Friendly app names -> likely process image name, so close_app can terminate
# the right process (with a fallback to <name>.exe).
APP_IMAGE = {
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "notepad": "notepad.exe",
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "vscode": "code.exe",
    "visual studio code": "code.exe",
    "code": "code.exe",
    "paint": "mspaint.exe",
    "mspaint": "mspaint.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "word": "winword.exe",
    "excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "spotify": "Spotify.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "powershell": "powershell.exe",
    "task manager": "Taskmgr.exe",
    "settings": "SystemSettings.exe",
    "wordpad": "write.exe",
    "snipping tool": "SnippingTool.exe",
}


# Windows-friendly launch targets for open_app. Keys are normalized (lowercase);
# values are either an executable/path (run directly) or a shell/URI token that
# must be launched via `start` (things ending in ':').
APP_COMMANDS = {
    "settings": "ms-settings:",
    "setting": "ms-settings:",
    "windows settings": "ms-settings:",
    "control panel": "control",
    "whatsapp": "whatsapp:",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "notepad": "notepad.exe",
    "paint": "mspaint.exe",
    "mspaint": "mspaint.exe",
    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "google chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "vscode": "code",
    "visual studio code": "code",
    "word": "winword.exe",
    "excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "powershell": "powershell.exe",
    "task manager": "taskmgr.exe",
    "snipping tool": "SnippingTool.exe",
}


def _resolve_app(name: str):
    """Resolve a spoken app name to (command, label) via exact then fuzzy lookup,
    or (None, None) if no match — so we never blindly run raw text as a command."""
    key = (name or "").strip().lower()
    if not key:
        return None, None
    if key in APP_COMMANDS:
        return APP_COMMANDS[key], key
    matches = difflib.get_close_matches(key, list(APP_COMMANDS.keys()),
                                        n=1, cutoff=0.6)
    if matches:
        return APP_COMMANDS[matches[0]], matches[0]
    return None, None


def open_app(app_name: str) -> str:
    """Opens an application by name, resolving it through APP_COMMANDS (with fuzzy
    matching) instead of blindly passing raw text to the shell. Returns a clear
    error if the app isn't mapped, so Nova never says 'opened' when it didn't."""
    cmd, label = _resolve_app(app_name)
    if cmd is None:
        return f"I don't know how to open '{app_name}' yet."
    sys_os = platform.system()
    try:
        if sys_os == "Windows":
            if cmd.endswith(":") or cmd.startswith("ms-settings:"):
                # Shell/URI target (e.g. ms-settings:, whatsapp:) needs `start`.
                subprocess.Popen(f"start {cmd}", shell=True)
            else:
                subprocess.Popen(cmd)
        elif sys_os == "Darwin":
            subprocess.Popen(["open", "-a", cmd])
        else:
            subprocess.Popen([cmd])
        return f"Opening {label}."
    except Exception as e:
        return f"I couldn't open {label}: {e}"



def _image_for(name: str) -> str:
    """Resolve a friendly app name to a process image name (e.g. notepad.exe)."""
    n = (name or "").strip().lower()
    if n in APP_IMAGE:
        return APP_IMAGE[n]
    if n.endswith(".exe"):
        return n
    return n + ".exe"


def close_app(name: str) -> str:
    """Terminate a running application by name."""
    image = _image_for(name)
    try:
        if platform.system() == "Windows":
            res = subprocess.run(
                ["taskkill", "/IM", image, "/F"],
                capture_output=True, text=True, timeout=15,
            )
            if res.returncode == 0:
                return f"Closed {name}."
            if _close_by_title(name):
                return f"Closed {name}."
            return f"I couldn't close {name}. Is it running?"
        subprocess.run(["pkill", "-f", image], capture_output=True, text=True, timeout=15)
        return f"Closed {name}."
    except Exception as e:
        return f"Error closing {name}: {e}"


def _close_by_title(name: str) -> bool:
    """Windows-only: send WM_CLOSE to visible windows whose title contains the
    name. Returns True if at least one window was closed."""
    try:
        import ctypes

        user32 = ctypes.windll.user32
        closed = []

        def _enum_callback(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            if buf.value and name.lower() in buf.value.lower():
                user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
                closed.append(hwnd)
            return True

        cb = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(_enum_callback)
        user32.EnumWindows(cb, 0)
        return bool(closed)
    except Exception:
        return False


def switch_window(name: str) -> str:
    """Focus / bring to front an open window whose title matches `name`."""
    name = (name or "").strip()
    if not name:
        return "Tell me which window you'd like me to switch to."
    if platform.system() == "Windows":
        try:
            import ctypes

            user32 = ctypes.windll.user32
            found = []

            def _enum_callback(hwnd, _lparam):
                if not user32.IsWindowVisible(hwnd):
                    return True
                length = user32.GetWindowTextLengthW(hwnd)
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value
                if title and name.lower() in title.lower():
                    found.append(hwnd)
                return True

            cb = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(_enum_callback)
            user32.EnumWindows(cb, 0)
            if found:
                hwnd = found[0]
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                user32.SetForegroundWindow(hwnd)
                return f"Switched to the '{name}' window."
            return f"I couldn't find an open window named '{name}'."
        except Exception as e:
            return f"I couldn't switch windows: {e}"
    return "Switching windows is only supported on Windows for now."


def minimize_all() -> str:
    """Minimize every open window (Win+M)."""
    try:
        import pyautogui
        pyautogui.hotkey("win", "m")
        return "Minimized all windows."
    except Exception as e:
        return f"I couldn't minimize all windows: {e}"


def show_desktop() -> str:
    """Show the desktop (Win+D)."""
    try:
        import pyautogui
        pyautogui.hotkey("win", "d")
        return "Showing the desktop."
    except Exception as e:
        return f"I couldn't show the desktop: {e}"


def open_chrome() -> str:
    """Opens Google Chrome."""
    sys_os = platform.system()
    try:
        if sys_os == "Windows":
            subprocess.Popen("start chrome", shell=True)
        elif sys_os == "Darwin":
            subprocess.Popen(["open", "-a", "Google Chrome"])
        else:
            subprocess.Popen(["google-chrome"])
        return "Successfully opened Chrome."
    except Exception as e:
        return f"Error opening Chrome: {e}"

def open_vscode() -> str:
    """Opens Visual Studio Code."""
    sys_os = platform.system()
    try:
        if sys_os == "Windows":
            subprocess.Popen("code", shell=True)
        elif sys_os == "Darwin":
            subprocess.Popen(["open", "-a", "Visual Studio Code"])
        else:
            subprocess.Popen(["code"])
        return "Successfully opened VS Code."
    except Exception as e:
        return f"Error opening VS Code: {e}"
