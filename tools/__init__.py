from .apps import (
    open_app, open_chrome, open_vscode, close_app, switch_window,
    minimize_all, show_desktop,
)
from .web import (
    search_web, open_website, web_search, get_weather, play_youtube,
)
from .files import (
    read_file, write_file, list_directory, create_folder, delete_file,
    delete_folder, copy_file, move_file, rename_file, search_files,
    get_drives, open_file_explorer,
)
from .system import (
    run_command, get_time, get_system_info, set_brightness, set_volume,
    mute, unmute, lock_screen, sleep_pc, shutdown_pc, restart_pc,
    cancel_shutdown, take_screenshot, get_clipboard, set_clipboard,
    pause_media, resume_media, next_track, previous_track,
)
from .control import (
    type_text, press_key, click_at, simulate_typing, simulate_click,
)
from .services import (
    open_spotify, send_email, open_calendar, control_smart_home,
)
from .primitives import open_url, file_operation
from .memory_tools import remember_fact, get_memory

TOOL_FUNCTIONS = {
    "open_app": open_app,
    "open_chrome": open_chrome,
    "open_vscode": open_vscode,
    "close_app": close_app,
    "switch_window": switch_window,
    "minimize_all": minimize_all,
    "show_desktop": show_desktop,
    "search_web": search_web,
    "open_website": open_website,
    "web_search": web_search,
    "get_weather": get_weather,
    "play_youtube": play_youtube,
    "pause_media": pause_media,
    "resume_media": resume_media,
    "next_track": next_track,
    "previous_track": previous_track,
    "read_file": read_file,
    "write_file": write_file,
    "list_directory": list_directory,
    "create_folder": create_folder,
    "delete_file": delete_file,
    "delete_folder": delete_folder,
    "copy_file": copy_file,
    "move_file": move_file,
    "rename_file": rename_file,
    "search_files": search_files,
    "get_drives": get_drives,
    "open_file_explorer": open_file_explorer,
    "run_command": run_command,
    "open_url": open_url,
    "file_operation": file_operation,
    "get_time": get_time,
    "get_system_info": get_system_info,
    "set_brightness": set_brightness,
    "set_volume": set_volume,
    "mute": mute,
    "unmute": unmute,
    "lock_screen": lock_screen,
    "sleep_pc": sleep_pc,
    "shutdown_pc": shutdown_pc,
    "restart_pc": restart_pc,
    "cancel_shutdown": cancel_shutdown,
    "take_screenshot": take_screenshot,
    "get_clipboard": get_clipboard,
    "set_clipboard": set_clipboard,
    "type_text": type_text,
    "press_key": press_key,
    "click_at": click_at,
    "simulate_typing": simulate_typing,
    "simulate_click": simulate_click,
    "open_spotify": open_spotify,
    "send_email": send_email,
    "open_calendar": open_calendar,
    "control_smart_home": control_smart_home,
    "remember_fact": remember_fact,
    "get_memory": get_memory,
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Opens a general application by name (e.g., 'calculator', 'notepad', 'Chrome').",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "The name of the application to open."}
                },
                "required": ["app_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "close_app",
            "description": "Terminates a running application by name (e.g., 'notepad', 'chrome').",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "The name of the application to close."}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "switch_window",
            "description": "Brings an already-open window to the front by matching its title.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name or part of the window title to focus."}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "minimize_all",
            "description": "Minimizes every open window.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "show_desktop",
            "description": "Shows the desktop by minimizing all windows.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_chrome",
            "description": "Opens the Google Chrome browser.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_vscode",
            "description": "Opens Visual Studio Code.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "play_youtube",
            "description": "Searches YouTube for a query and opens/autoplays the first result.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The song/video to search for on YouTube."}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "pause_media",
            "description": "Pauses the currently playing media via the media key.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "resume_media",
            "description": "Resumes playback via the media key.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "next_track",
            "description": "Skips to the next track or video via the media key.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "previous_track",
            "description": "Goes back to the previous track or video via the media key.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Opens the default browser and performs a Google search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query to look up on Google."}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_website",
            "description": "Opens a specific website or URL in the default browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The website or URL to open (e.g., 'youtube.com')."}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Performs a live web search and returns readable text results to answer current questions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query."}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Returns current weather for a location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City or location for the weather (blank for current location)."}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Reads the text content of a file at the specified path (D: drive is restricted).",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "The absolute or relative path to the file to read."}
                },
                "required": ["filepath"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Writes text content to a file at the specified path (D: drive is restricted).",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "The absolute or relative path to the file to write."},
                    "content": {"type": "string", "description": "The text content to write into the file."}
                },
                "required": ["filepath", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "Lists the files and folders inside a directory on this PC (D: drive is restricted).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Folder path to browse, e.g. 'C:/Users'. Blank for home."}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_folder",
            "description": "Creates a folder (and parent folders) at a path on this PC (D: drive is restricted).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path of the folder to create."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Deletes a single file (not a folder) at a path on this PC (D: drive is restricted). ONLY call when the user clearly names the exact file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path of the file to delete."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_folder",
            "description": "Deletes a folder (and all its contents) on this PC (D: drive is restricted). ONLY call when the user clearly names the exact folder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path of the folder to delete."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "copy_file",
            "description": "Copies a file from one path to another on this PC (D: drive is restricted).",
            "parameters": {
                "type": "object",
                "properties": {
                    "src": {"type": "string", "description": "Source file path."},
                    "dst": {"type": "string", "description": "Destination file path."}
                },
                "required": ["src", "dst"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "move_file",
            "description": "Moves a file from one path to another on this PC (D: drive is restricted).",
            "parameters": {
                "type": "object",
                "properties": {
                    "src": {"type": "string", "description": "Source file path."},
                    "dst": {"type": "string", "description": "Destination file path."}
                },
                "required": ["src", "dst"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rename_file",
            "description": "Renames a file or folder within the same directory on this PC (D: drive is restricted).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Current absolute path of the file/folder."},
                    "new_name": {"type": "string", "description": "The new name (just the name, not a path)."}
                },
                "required": ["path", "new_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Searches for files and folders by name under a start folder (D: drive is restricted).",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Text to match in the file or folder name."},
                    "start": {"type": "string", "description": "Folder to start searching from. Blank = home folder."}
                },
                "required": ["pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_drives",
            "description": "Lists the available drives on this PC (excluding the restricted D: volume).",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_file_explorer",
            "description": "Opens a File Explorer window at a folder on this PC (D: drive is restricted).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Folder path to open in File Explorer. Blank = home folder."}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "General-purpose: run any Windows/PowerShell/shell command and return its output. Use this for launching apps, system settings, file tasks or anything not covered by a specific tool. Destructive commands (del/rm/rd/format/shutdown/taskkill...) need confirm=true after asking the user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The command to run."},
                    "confirm": {"type": "boolean", "description": "Set true ONLY after the user has confirmed a destructive command."}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_url",
            "description": "General-purpose: open any website/URL in the default browser. Also for Google search (https://www.google.com/search?q=QUERY), WhatsApp (https://wa.me/PHONE?text=MSG), or any link.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The full URL or website name/link to open."}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "file_operation",
            "description": "General-purpose: read / write / append / delete / list a file. action is 'read'|'write'|'append'|'delete'|'list'. Deleting requires confirm=true only after the user agrees.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["read", "write", "append", "delete", "list"], "description": "What to do."},
                    "path": {"type": "string", "description": "File or folder path."},
                    "content": {"type": "string", "description": "Content to write/append (for write/append)."},
                    "confirm": {"type": "boolean", "description": "Set true ONLY after the user confirms a delete."}
                },
                "required": ["action", "path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Returns the current local date and time.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_info",
            "description": "Returns info about the PC: OS, CPU, RAM/memory, and battery.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_brightness",
            "description": "Sets the screen brightness to a percentage (0-100).",
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {"type": "integer", "description": "Brightness percentage from 0 to 100."}
                },
                "required": ["level"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_volume",
            "description": "Sets the master volume to a percentage (0-100).",
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {"type": "integer", "description": "Volume percentage from 0 to 100."}
                },
                "required": ["level"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mute",
            "description": "Mutes all audio output.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "unmute",
            "description": "Unmutes audio output and restores the last volume.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lock_screen",
            "description": "Locks the screen / workstation.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "sleep_pc",
            "description": "Puts the computer to sleep.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "shutdown_pc",
            "description": "Schedules a shutdown (always uses a 10-second delay so it can be cancelled).",
            "parameters": {
                "type": "object",
                "properties": {
                    "delay_seconds": {"type": "integer", "description": "Delay in seconds before shutdown (default 10)."}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "restart_pc",
            "description": "Schedules a restart (always uses a 10-second delay so it can be cancelled).",
            "parameters": {
                "type": "object",
                "properties": {
                    "delay_seconds": {"type": "integer", "description": "Delay in seconds before restart (default 10)."}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_shutdown",
            "description": "Aborts any pending shutdown or restart.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "take_screenshot",
            "description": "Captures the screen to a PNG file. Blank path saves to Pictures.",
            "parameters": {
                "type": "object",
                "properties": {
                    "save_path": {"type": "string", "description": "Optional absolute path to save the PNG. Blank = Pictures folder."}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_clipboard",
            "description": "Returns whatever text is currently on the clipboard.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_clipboard",
            "description": "Copies the given text onto the clipboard.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The text to copy."}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Types the given text using the keyboard.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The text to type."}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "press_key",
            "description": "Presses a specific keyboard key (e.g., 'enter', 'win', 'ctrl').",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "The key name to press."}
                },
                "required": ["key"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "click_at",
            "description": "Clicks the mouse at the given (x, y) screen coordinates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "The X coordinate on the screen."},
                    "y": {"type": "integer", "description": "The Y coordinate on the screen."}
                },
                "required": ["x", "y"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "simulate_typing",
            "description": "Simulates typing the given text on the keyboard.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The text to type."}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "simulate_click",
            "description": "Simulates a mouse click at the given (x, y) screen coordinates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "The X coordinate on the screen."},
                    "y": {"type": "integer", "description": "The Y coordinate on the screen."}
                },
                "required": ["x", "y"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_spotify",
            "description": "Opens Spotify (or sends play/pause/next/previous when possible).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "Optional action: open, play, pause, next, prev."}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Opens the mail app with a draft email (no credentials needed).",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email address."},
                    "subject": {"type": "string", "description": "Email subject line."},
                    "body": {"type": "string", "description": "Email body text."}
                },
                "required": ["to"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_calendar",
            "description": "Opens the user's calendar application.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scope": {"type": "string", "description": "Optional focus, e.g. 'today' or 'this week'."}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "control_smart_home",
            "description": "Guides smart-home control (physical devices need a hub API).",
            "parameters": {
                "type": "object",
                "properties": {
                    "device": {"type": "string", "description": "The device, e.g. 'living room lights'."},
                    "action": {"type": "string", "description": "The action, e.g. 'turn on'."}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "remember_fact",
            "description": "Saves a fact about the user so Nova remembers it across sessions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fact": {"type": "string", "description": "The fact to remember."}
                },
                "required": ["fact"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_memory",
            "description": "Recalls what Nova remembers about the user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Optional keyword to narrow the search."}
                },
                "required": []
            }
        }
    },
]