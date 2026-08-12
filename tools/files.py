import os
import shutil

from config import BLOCKED_DRIVES


# ---------------------------------------------------------------------------
# PC-access guard. Nova may touch the whole computer EXCEPT the blocked drives
# (the user asked to exclude the D: volume).
# ---------------------------------------------------------------------------
def is_blocked_path(path: str) -> bool:
    """Return True if a path resolves inside a drive/folder Nova must not touch."""
    if not path:
        return False
    try:
        normalized = os.path.normcase(os.path.abspath(os.path.expanduser(path)))
    except Exception:
        normalized = os.path.normcase(str(path))

    for drive in BLOCKED_DRIVES or []:
        d = os.path.normcase(drive)
        if normalized == d or normalized.startswith(d + os.sep) or normalized.startswith(d + "/"):
            return True
    return False


def _guard(path: str):
    """Raise a friendly error if the path is on a blocked drive."""
    if is_blocked_path(path):
        raise PermissionError(
            "That location is on the D: drive, which you've told me not to access. "
            "Please choose a folder on another drive, like C:."
        )


def read_file(filepath: str) -> str:
    """Reads content from a file."""
    try:
        _guard(filepath)
        if not os.path.exists(filepath):
            return f"Error: File '{filepath}' does not exist."

        # Limit read to 10KB to avoid overwhelming the context window
        max_bytes = 10240
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read(max_bytes)

        if len(content) == max_bytes:
            content += "\n...[TRUNCATED due to length]"

        return content
    except PermissionError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error reading file: {e}"


def write_file(filepath: str, content: str) -> str:
    """Writes content to a file."""
    try:
        _guard(filepath)
        # Create directories if they don't exist
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully wrote to {filepath}"
    except PermissionError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error writing to file: {e}"


def list_directory(path: str = "") -> str:
    """Lists the contents (files and folders) of a directory. Defaults to the
    home folder if no path or an empty path is given."""
    try:
        if not path or not path.strip():
            path = os.path.expanduser("~")
        _guard(path)
        if not os.path.isdir(path):
            return f"Error: '{path}' is not a folder."

        entries = sorted(os.listdir(path))
        if not entries:
            return f"The folder {path} is empty."

        folders = [e for e in entries if os.path.isdir(os.path.join(path, e))]
        files = [e for e in entries if not os.path.isdir(os.path.join(path, e))]
        lines = [f"Folder: {os.path.abspath(path)}"]
        if folders:
            lines.append(f"Folders ({len(folders)}): " + ", ".join(folders[:40]))
        if files:
            lines.append(f"Files ({len(files)}): " + ", ".join(files[:60]))
        if len(folders) > 40 or len(files) > 60:
            lines.append("(showing the first few — say the name of one to open it)")
        return "\n".join(lines)
    except PermissionError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error listing directory: {e}"


def create_folder(path: str) -> str:
    """Creates a folder (and any missing parents) at the given path."""
    try:
        _guard(path)
        os.makedirs(path, exist_ok=True)
        return f"Created the folder {path}."
    except PermissionError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error creating folder: {e}"


def delete_file(path: str) -> str:
    """Deletes a single file (not a folder with contents)."""
    try:
        _guard(path)
        if os.path.isdir(path):
            return f"Error: {path} is a folder. I can only delete files to keep things safe."
        if not os.path.exists(path):
            return f"Error: '{path}' does not exist."
        os.remove(path)
        return f"Deleted the file {path}."
    except PermissionError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error deleting file: {e}"


def search_files(pattern: str, start: str = "") -> str:
    """Searches for files/directories whose name contains `pattern`, starting
    from `start` (defaults to the user's home folder on drive C)."""
    try:
        if not start or not start.strip():
            start = os.path.expanduser("~")
        _guard(start)
        if not os.path.isdir(start):
            return f"Error: '{start}' is not a folder."

        found = []
        for root, dirs, files in os.walk(start):
            # Never descend into blocked drives
            if is_blocked_path(root):
                dirs[:] = []
                continue
            for name in list(dirs) + files:
                if pattern.lower() in name.lower():
                    found.append(os.path.join(root, name))
            if len(found) >= 20:
                break
        if not found:
            return f"I couldn't find anything matching '{pattern}' under {start}."
        lines = [f"Found {len(found)} match(es) for '{pattern}':"] + found[:20]
        return "\n".join(lines)
    except PermissionError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error searching files: {e}"


def get_drives() -> str:
    """Lists the available drives on the PC (excluding any blocked ones)."""
    try:
        if os.name == "nt":
            import string
            from ctypes import windll
            drives = []
            bitmask = windll.kernel32.GetLogicalDrives()
            for i, letter in enumerate(string.ascii_uppercase):
                if bitmask & (1 << i):
                    drives.append(f"{letter}:\\")
        else:
            drives = [os.path.abspath(os.sep)]
        visible = [d for d in drives if not is_blocked_path(d)]
        blocked = [d for d in drives if is_blocked_path(d)]
        msg = "Drives available: " + (", ".join(visible) if visible else "none")
        if blocked:
            msg += f". (Excluded: {', '.join(blocked)})"
        return msg
    except Exception as e:
        return f"Error listing drives: {e}"


def open_file_explorer(path: str = "") -> str:
    """Opens a File Explorer / Finder window at the given path."""
    try:
        if not path or not path.strip():
            path = os.path.expanduser("~")
        _guard(path)
        if os.name == "nt":
            os.startfile(path)  # opens the OS explorer window
        elif os.name == "posix":
            import subprocess
            subprocess.Popen(["xdg-open", path])
        return f"Opened the folder {path} in File Explorer."
    except PermissionError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error opening folder: {e}"


def delete_folder(path: str) -> str:
    """Deletes a folder (and all of its contents). Blocks drive roots."""
    try:
        _guard(path)
        if not os.path.isdir(path):
            return f"Error: '{path}' is not a folder or does not exist."
        root = os.path.dirname(os.path.abspath(path))
        if os.path.abspath(path) == root:
            return "Error: I won't delete a drive root."
        shutil.rmtree(path)
        return f"Deleted the folder {path} and everything inside it."
    except PermissionError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error deleting folder: {e}"


def copy_file(src: str, dst: str) -> str:
    """Copies a file from src to dst (D: drive is restricted)."""
    try:
        _guard(src)
        _guard(dst)
        if not os.path.isfile(src):
            return f"Error: source '{src}' is not a file."
        os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
        shutil.copy2(src, dst)
        return f"Copied {src} to {dst}."
    except PermissionError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error copying file: {e}"


def move_file(src: str, dst: str) -> str:
    """Moves a file from src to dst (D: drive is restricted)."""
    try:
        _guard(src)
        _guard(dst)
        if not os.path.exists(src):
            return f"Error: source '{src}' does not exist."
        os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
        shutil.move(src, dst)
        return f"Moved {src} to {dst}."
    except PermissionError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error moving file: {e}"


def rename_file(path: str, new_name: str) -> str:
    """Renames a file or folder, keeping it in the same directory."""
    try:
        _guard(path)
        new_name = (new_name or "").strip()
        if not new_name:
            return "Error: I need a new name for the file."
        if os.sep in new_name or ("/" in new_name):
            return "Error: Please give just a new name, not a full path."
        new_path = os.path.join(os.path.dirname(os.path.abspath(path)), new_name)
        _guard(new_path)
        if not os.path.exists(path):
            return f"Error: '{path}' does not exist."
        os.rename(path, new_path)
        return f"Renamed {path} to {new_name}."
    except PermissionError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error renaming file: {e}"
