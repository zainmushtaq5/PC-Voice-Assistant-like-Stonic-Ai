"""General-purpose primitives the LLM can combine to handle almost any task, so
Nova doesn't need a new hardcoded function for every app/site/action.

These are registered as tools alongside the specific ones (open_app, close_app,
...). For anything not explicitly covered the model should construct the right
command, URL, or file action and call the appropriate primitive here.
"""
import os
import re
import webbrowser


def open_url(url: str) -> str:
    """Open any URL in the default browser. Works for websites, Google search
    (https://www.google.com/search?q=...), WhatsApp (https://wa.me/<num>?text=...),
    and any web link. Puts a tiny amount of smarts into building it if the caller
    passes a bare site name."""
    url = (url or "").strip()
    if not url:
        return "I need a URL to open."
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        if os.name == "nt":
            os.startfile(url)    # opens the default browser on Windows
        else:
            webbrowser.open(url)
        return f"Opened {url}"
    except Exception as e:
        return f"Couldn't open URL: {e}"


def file_operation(action: str, path: str, content: str = "",
                   confirm: bool = False) -> str:
    """Generic file operation. `action` is one of:
    'read' | 'write' | 'append' | 'delete' | 'list'.
    'delete' is destructive, so it requires `confirm=True` and will NOT run until
    the user has told Nova to go ahead."""
    action = (action or "").strip().lower()
    path = (path or "").strip()
    try:
        if action == "read":
            with open(path, "r", encoding="utf-8") as f:
                return f.read()[:1000]
        if action == "write":
            with open(path, "w", encoding="utf-8") as f:
                f.write(content or "")
            return f"Wrote to {path}"
        if action == "append":
            with open(path, "a", encoding="utf-8") as f:
                f.write(content or "")
            return f"Appended to {path}"
        if action == "delete":
            if not confirm:
                return (
                    "[SAFETY] Deleting is destructive. Ask the user to confirm they "
                    f"really want to delete '{path}', then call file_operation again "
                    "with confirm=true if they say yes."
                )
            os.remove(path)
            return f"Deleted {path}"
        if action == "list":
            return "\n".join(os.listdir(path))
        return f"Unknown action: {action}"
    except FileNotFoundError:
        return f"Not found: {path}"
    except Exception as e:
        return f"File operation failed: {e}"
