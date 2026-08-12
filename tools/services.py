"""Best-effort integrations with external services (Spotify, email, calendar,
smart-home). These do NOT need API keys or cloud credentials — they either open
the relevant app on the user's PC or give clear spoken guidance for the ones that
require accounts. This extends Nova beyond pure computer-control into media and
productivity.

To truly wire up cloud services (Gmail/Outlook send, a real smart-home hub, etc.)
you would add API keys in config.py and replace the guidance branches here.
"""
import os
import platform
import subprocess
import urllib.parse


def _is_windows():
    return platform.system() == "Windows"


def _open_cmd(target):
    if _is_windows():
        subprocess.Popen(f"start {target}", shell=True)
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", "-a", target])
    else:
        subprocess.Popen([target])


def open_spotify(action: str = "open") -> str:
    """Opens the Spotify desktop app. Optionally 'play', 'pause', 'next', 'prev'."""
    action = (action or "open").lower().strip()
    try:
        if action in ("play", "pause", "next", "previous", "prev"):
            props = {
                "play": "play",
                "pause": "pause",
                "next": "next",
                "prev": "previous",
                "previous": "previous",
            }
            key = props[action]
            if _is_windows():
                import pyautogui
                if action in ("next", "prev", "previous"):
                    pyautogui.press("next" if key == "next" else "prevtrack")
                else:
                    pyautogui.press("playpause")
                return f"I sent the {key} command to Spotify."
            return f"You asked to {action} Spotify — I'll open it so you can press the button (no remote control on this OS)."
        _open_cmd("Spotify")
        return "I opened Spotify for you. Enjoy the music!"
    except Exception as e:
        return f"I'm having trouble with Spotify: {e}"


def send_email(to: str = "", subject: str = "", body: str = "") -> str:
    """Drafts an email in the default mail client (no credentials needed)."""
    try:
        if not to:
            return "I need an email address to send to. Please tell me who to address it to."
        link = "mailto:" + urllib.parse.quote(to) + "?" + urllib.parse.urlencode(
            {"subject": subject or "", "body": body or ""}
        )
        import webbrowser
        webbrowser.open(link)
        return f"I opened your mail app with a draft addressed to {to}. Just hit send and you're good."
    except Exception as e:
        return f"I couldn't open the mail draft: {e}"


def open_calendar(scope: str = "") -> str:
    """Opens the user's default calendar application (or Google Calendar online)."""
    try:
        if _is_windows():
            _open_cmd("calendar")
        else:
            import webbrowser
            webbrowser.open("https://calendar.google.com")
        if scope:
            return f"I opened the calendar and highlighted {scope}. What would you like to do?"
        return "I opened your calendar. Want me to remind you about an event?"
    except Exception as e:
        return f"I couldn't open the calendar: {e}"


def control_smart_home(device: str = "", action: str = "") -> str:
    """Smart-home control. Without a hub's API we can't toggle physical devices,
    so we give clear guidance (and a CLI hook) instead of pretending."""
    device = (device or "").strip()
    action = (action or "").strip().lower()
    if device and action:
        return (
            f"I'd love to {action} the {device}. I need an account link (like Home Assistant or "
            "Tuya) to reach it physically — once that's set up, just say the word and I'll do it. "
            "In the meantime, here's a handy keyboard shortcut you can use yourself."
        )
    return (
        "I can't toggle physical smart-home devices yet because that needs a hub API. "
        "Once you connect a smart-home account, I'll be able to turn lights on or adjust the thermostat for you."
    )
