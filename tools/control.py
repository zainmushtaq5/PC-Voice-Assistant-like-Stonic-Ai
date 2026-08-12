import pyautogui

# Failsafe: moving mouse to corner aborts pyautogui
pyautogui.FAILSAFE = True

def type_text(text: str) -> str:
    """Types the given text using the keyboard."""
    try:
        pyautogui.write(text, interval=0.01)
        return f"Successfully typed the text."
    except Exception as e:
        return f"Error typing text: {e}"

def press_key(key: str) -> str:
    """Presses a specific keyboard key (e.g., 'enter', 'win', 'ctrl')."""
    try:
        pyautogui.press(key)
        return f"Successfully pressed '{key}'."
    except Exception as e:
        return f"Error pressing key: {e}"

def click_at(x: int, y: int) -> str:
    """Clicks the mouse at the specified (x, y) coordinates."""
    try:
        pyautogui.click(x=x, y=y)
        return f"Successfully clicked at ({x}, {y})."
    except Exception as e:
        return f"Error clicking: {e}"


def simulate_typing(text: str) -> str:
    """Types the given text using the keyboard (alias of type_text)."""
    return type_text(text)


def simulate_click(x: int, y: int) -> str:
    """Clicks the mouse at the specified (x, y) coordinates (alias of click_at)."""
    return click_at(x, y)
