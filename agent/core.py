import json
import os
import re
import threading

from .llm import check_connection, chat_with_tools, CancellationError
from . import memory
from tools import TOOL_SCHEMAS, TOOL_FUNCTIONS
from config import (
    SYSTEM_PROMPT, MAX_TOOL_HOPS, MAX_HISTORY,
    MEMORY_TURNS, MEMORY_FACTS, DEBUG_LLM, TOOL_EXAMPLES,
)


# ---------------------------------------------------------------------------
# Human-tone cleanup. Local models sometimes slip markdown / bullets / emojis
# into their reply, which reads badly when spoken. We strip that so the output
# stays natural and conversational for TTS.
# ---------------------------------------------------------------------------
def humanize(text):
    """Make LLM output read naturally when spoken aloud."""
    if not text:
        return text
    text = re.sub(r"```[a-zA-Z0-9_]*\n?.*?```", "", text, flags=re.DOTALL)  # code fences
    text = re.sub(r"`([^`]*)`", r"\1", text)                                 # inline code
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)                           # bold
    text = re.sub(r"(?<!\w)\*([^*]+)\*(?!\w)", r"\1", text)                  # italic
    text = re.sub(r"(?m)^\s*[-*•▪]\s+", "", text)                            # dash bullets
    text = re.sub(r"(?m)^\s*\d+[.)]\s+", "", text)                           # numbered bullets
    text = re.sub(r"[#]{1,6}\s*", "", text)                                  # markdown headers
    text = re.sub(r"^[=\-]{3,}\s*$", "", text, flags=re.MULTILINE)           # hr lines
    # Strip non-ASCII that isn't Urdu/Arabic script (removes emojis/symbols but
    # keeps Urdu replies intact).
    text = re.sub(r"[^\x00-\x7F\u0600-\u06FF\u0750-\u077F]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:?!])", r"\1", text)  # no space before punctuation
    return text


def _debug_dump(messages, label=""):
    """When DEBUG_LLM is on, print the exact message roles/shape sent to the API so
    you can inspect conversation history (e.g. tool-call pairing)."""
    if not DEBUG_LLM:
        return
    print(f"--- LLM-DEBUG {label} ({len(messages)} messages) ---")
    for i, m in enumerate(messages or []):
        role = m.get("role")
        extra = ""
        if m.get("tool_calls"):
            names = ",".join(
                (t.get("function") or {}).get("name", "?")
                for t in m["tool_calls"]
            )
            extra = f"tool_calls=[{names}] ids=" + ",".join(
                str(t.get("id", "")) for t in m["tool_calls"]
            )
        elif m.get("tool_call_id"):
            extra = f"tool_call_id={m.get('tool_call_id')}"
        cort = m.get("content") or ""
        if len(cort) > 40:
            cort = cort[:40] + "..."
        print(f"  [{i}] {role}: {extra} | {cort!r}")


# ---------------------------------------------------------------------------
# Deterministic intent router.
#
# Small local models (e.g. qwen2.5-coder:3b) are unreliable at *proactively*
# calling tools from natural language. For the most common commands we route
# them directly in Python so the assistant always responds correctly, and let
# the LLM + tools handle everything else.
# ---------------------------------------------------------------------------
def _extract_fact(text):
    """Pull a user fact out of 'remember ...' style phrasing, or None."""
    t = text.strip()
    m = re.match(r"(?:please\s+)?remember\s+(?:that\s+)?(.+)", t)
    if m:
        return m.group(1).strip().strip(".").strip()
    m = re.match(r"call me\s+(.+)", t)
    if m:
        return "The user prefers to be called " + m.group(1).strip().strip(".")
    m = re.match(r"my name is\s+(.+)", t)
    if m:
        return "The user's name is " + m.group(1).strip().strip(".")
    m = re.match(r"i live in\s+(.+)", t)
    if m:
        return "The user lives in " + m.group(1).strip().strip(".")
    m = re.match(r"i(?:'?m|\s+am)\s+from\s+(.+)", t)
    if m:
        return "The user is from " + m.group(1).strip().strip(".")
    return None


def _route_intent(text):
    """Return (tool_name, args) for a clearly-recognisable command, else None."""
    t = text.lower().strip()

    # Compound/multi-step commands (e.g. "open chrome and search X", "open
    # whatsapp and send message to Y") must NOT be hijacked by a single regex
    # below — let them fall through to the LLM agent loop, which can chain
    # multiple tool calls together.
    if re.search(r"\b(and then|,?\s+and\s+\w|\bthen\b)\s", t):
        return None

    # Window-level overview commands must be caught before the looser patterns
    # below (e.g. "show the desktop" would otherwise be read as list_directory).
    if re.search(r"\b(show (?:the )?desktop|go to desktop|show my desktop)\b", t):
        return "show_desktop", {}
    if re.search(r"\b(minimize all|minimize every|hide all windows)\b", t):
        return "minimize_all", {}

    # ---- Persistent-memory commands ---------------------------------------
    if re.search(r"\b(what do you remember|do you (even )?remember|what (facts|things) "
                 r"(do you know|have you)|recall|any memories|what do you know about me)\b", t):
        return "get_memory", {}
    if re.search(r"\b(remember|note (that|this)|don'?t forget|keep in mind|call me|my name is|i live in)\b", t):
        fact = _extract_fact(text)
        if fact:
            return "remember_fact", {"fact": fact}

    # ---- PC / file access -------------------------------------------------
    if re.search(r"\b(what|which|my|list|show|all)\b.{0,20}\bdrives?\b", t):
        return "get_drives", {}
    if re.search(r"\b(list|show|what'?s in|what is in|contents of|browse)\b", t) and \
       re.search(r"\b(folder|directory|files?|documents?|desktop|downloads?)\b", t):
        m = re.search(r"\b(?:in|of|inside)\s+(.+?)[?.!]*$", t)
        path = m.group(1).strip().strip("\"'") if m else ""
        if path.lower() in ("home", "my computer", "pc", "this pc", "computer"):
            path = ""
        return "list_directory", {"path": path}
    if re.search(r"\b(find|search for|locate)\b", t) and re.search(r"\b(file|folder|directory)\b", t):
        pattern = ""
        pat = re.search(r"\b(?:named|called|for)\s+(.+?)(?:\s+in\s+.+)?[?.!]*$", t)
        if pat:
            pattern = pat.group(1).strip().strip("\"'")
        if not pattern:
            m = re.search(r"\b(?:find|search for|locate)\s+(?:a |the |my )?(?:file|folder)?\s*(.+?)[?.!]*$", t)
            if m:
                pattern = m.group(1).strip().strip("\"'")
        if pattern:
            return "search_files", {"pattern": pattern}
    if re.search(r"\b(create|make|new)\b", t) and re.search(r"\b(folder|directory)\b", t):
        m = re.search(r"\b(?:called|named)\s+(.+?)[?.!]*$", t)
        folder = m.group(1).strip().strip("\"'") if m else "new_folder"
        return "create_folder", {"path": os.path.join(os.path.expanduser("~"), folder)}

    # Play something on YouTube (checked before plain web search so "... on
    # youtube" isn't treated as a normal search query).
    if re.search(r"\byoutube\b", t):
        q = ""
        m = re.search(r"\b(?:play|search|find|look up)\s+(?:for\s+|the\s+)?(.+?)\s+on\s+youtube[?.!]*$", t)
        if m:
            q = m.group(1).strip()
        else:
            m = re.search(r"\byoutube\s+(?:for\s+|search\s+)?(.+?)[?.!]*$", t)
            if m:
                q = m.group(1).strip()
        if not q:
            m = re.search(r"\bplay\s+(.+?)[?.!]*$", t)
            if m:
                q = re.sub(r"\s*\.\s*$", "", m.group(1)).strip()
        q = re.sub(r"\s+on\s+youtube\s*$", "", q).strip()
        if q:
            return "play_youtube", {"query": q}

    # Media-key transport control (pause / resume / next / previous).
    if re.search(r"\b(pause|hold)\b", t) and re.search(r"\b(music|song|video|media|playback|track|it)\b", t):
        return "pause_media", {}
    if re.search(r"\b(resume|unpause|continue playing|play it (again|from where))\b", t):
        return "resume_media", {}
    if re.search(r"\bnext\b", t) and re.search(r"\b(track|song|video|one)\b", t):
        return "next_track", {}
    if re.search(r"\b(previous|go ?back)\b", t) and re.search(r"\b(track|song|video)\b", t):
        return "previous_track", {}

    # ---- External services -------------------------------------------------
    if re.search(r"\b(spotify|play music|play a song|next song|music)\b", t):
        action = "open"
        if re.search(r"\b(play|start)\b", t):
            action = "play"
        elif re.search(r"\b(next|skip)\b", t):
            action = "next"
        return "open_spotify", {"action": action}
    if re.search(r"\b(send|write|draft|compose)\b", t) and re.search(r"\bemail\b", t):
        m = re.search(r"\bto\s+([\w.+-]+@[\w.-]+\.\w+)\b", t)
        to = m.group(1).strip() if m else ""
        if to:
            return "send_email", {"to": to}
    if re.search(r"\b(calendar|schedule)\b", t):
        return "open_calendar", {}

    # Weather (live, free — reads the answer back)
    if re.search(r"\bweather\b", t):
        m = re.search(r"\bweather\b(?:\\s+in|\\s+for|\\s+at)?\s+([a-z][\w\s-]+?)[?.!]*$", t)
        loc = m.group(1).strip() if m else ""
        loc = re.sub(r"\b(right now|at the moment|today|tomorrow|tonight|now|currently|"
                     r"please|this week|this weekend)\b", " ", loc)
        loc = re.sub(r"\s+", " ", loc).strip()
        return "get_weather", {"location": loc}

    # Current time / date
    if (re.search(r"\b(what|current|the|is it|give|tell|know)\b.{0,25}\b(time|clock)\b", t) or
            re.search(r"\b(today'?s date|what date|what'?s the date|current date|the date|what day is)\b", t)):
        return "get_time", {}

    # Computer / system info
    if (re.search(r"(system info|system information|computer info|about my (pc|computer|machine)|"
                  r"how much (ram|memory)|my specs|specs of)", t) or
            re.search(r"\b(ram|memory|cpu|processor|operating system)\b", t)):
        if not re.search(r"\b(open|search|look up|website|time)\b", t) or \
                re.search(r"how much (ram|memory)", t) or re.search(r"my (ram|cpu|processor|memory)", t):
            return "get_system_info", {}

    # Live web search (returns readable text so Nova can answer aloud)
    m = re.search(r"^\s*(?:please\s+)?(?:search (?:the (?:web|internet)|web|for)|google|look up|find)\s+(.+?)[?.!]*$", t)
    if m:
        query = re.sub(r"^(?:(?:the|for|about|a|web|internet)\s+)*", "", m.group(1).strip())
        if len(query) > 2:
            return "web_search", {"query": query}

    # ---- Apps & window management -------------------------------------------
    if re.search(r"\b(close|quit|exit|kill|terminate)\b", t) and not re.search(
            r"\b(shutdown|shut ?down|power ?off|turn (?:the )?(?:pc|computer|system) off|the assistant)\b", t):
        m = re.search(r"\b(?:close|quit|exit|kill|terminate)\s+(?:the |this |that )?"
                      r"(?:app|application|program|window|tab)?\s*(.+?)[?.!]*$", t)
        target = (m.group(1) if m else "").strip()
        if target and target.lower() not in ("me", "now", "please", "down", "the program", "the app"):
            return "close_app", {"name": target}

    if re.search(r"\b(switch (?:(?:the )?window|to)|focus (?:on|the)|bring (?:up|to front))\b", t):
        m = re.search(r"\b(?:switch (?:to|(?:the )?window (?:to|on)?)|focus (?:on|the)|bring up|bring to front)\s+"
                      r"(?:the |a |to |my )?(.+?)[?.!]*$", t)
        target = (m.group(1) if m else "").strip()
        if target:
            return "switch_window", {"name": target}

    if re.search(r"\b(minimize all|minimize every|hide all windows)\b", t):
        return "minimize_all", {}
    if re.search(r"\b(show (?:the )?desktop|go to desktop|show my desktop)\b", t):
        return "show_desktop", {}

    # ---- Display / brightness -------------------------------------------
    if re.search(r"\bbrightness\b", t):
        m = re.search(r"\b(?:to\s+|at\s+|of\s+)?(\d{1,3})\s*(?:%|percent)?", t)
        level = int(m.group(1)) if m else 50
        return "set_brightness", {"level": level}

    # ---- Volume & mute ---------------------------------------------------
    if re.search(r"\bun ?mute\b", t):
        return "unmute", {}
    if re.search(r"\bmute\b", t) or (re.search(r"\b(volume|sound)\b", t) and re.search(r"\boff\b", t)):
        return "mute", {}
    if re.search(r"\bvolume\b", t) or re.search(r"\b(louder|quieter)\b", t):
        m = re.search(r"\b(?:to\s+|at\s+)?(\d{1,3})\s*(?:%|percent)?", t)
        level = int(m.group(1)) if m else None
        if level is not None and 0 <= level <= 100:
            return "set_volume", {"level": level}

    # ---- Screen / power / clipboard --------------------------------------
    if re.search(r"\b(lock (?:the )?(?:screen|computer|pc)|lock it|lock my (?:computer|pc))\b", t):
        return "lock_screen", {}
    if re.search(r"\b(?:sleep|sleep mode|go to sleep)\b", t) and re.search(r"\b(pc|computer|laptop|system)\b", t):
        return "sleep_pc", {}
    if re.search(r"\b(screenshot|screen ?shot|capture (?:the )?screen|print screen)\b", t):
        return "take_screenshot", {}

    if re.search(r"\b(cancel|abort|stop)\b", t) and re.search(r"\b(shutdown|shut ?down|restart|reboot|power ?off)\b", t):
        return "cancel_shutdown", {}
    if re.search(r"\b(shut ?down|turn off|power off|switch off|shut it down)\b", t) and re.search(
            r"\b(pc|computer|laptop|machine|system)\b", t):
        return "shutdown_pc", {"delay_seconds": 10}
    if re.search(r"\b(restart|re ?boot|reboot)\b", t) and re.search(
            r"\b(pc|computer|laptop|machine|system)\b", t):
        return "restart_pc", {"delay_seconds": 10}

    if re.search(r"\bclipboard\b", t):
        if re.search(r"\b(copy|save|set|put|store)\b", t):
            m = re.search(r"\b(?:copy|save|set|put|store)\s*(?:this |that |the following |to clipboard|onto clipboard)?\s*(.+?)\s*(?:to |onto |into |on |to the )?clipboard[?.!]*$", text, re.IGNORECASE)
            value = (m.group(1) if m else "").strip()
            if value:
                return "set_clipboard", {"text": value}
        return "get_clipboard", {}

    # ---- File operations --------------------------------------------------
    # Destructive operations route only when a concrete path is present;
    # otherwise they defer to the LLM (which is told to ask for clarification
    # rather than guess).
    if re.search(r"\b(read|open|show|display)\b", t) and re.search(r"\bfile\b", t):
        m = re.search(r"([a-zA-Z]:[\\/][^\s;]+|/[/\w .-]+\.\w+|~[/\\][^\s;]+)", text)
        if m:
            return "read_file", {"filepath": re.sub(r"[.,;!?]+$", "", m.group(1))}

    if re.search(r"\b(write|save|create)\b", t) and re.search(r"\bfile\b", t):
        m = re.search(r"\b(?:write|save|create)\s+(?:a |the |this |new )?file\s+(?:called |named )?([^ ]+)\s+(?:with |containing |saying |that |that says |:)\s*(.+?)[?.!]*$", text, re.IGNORECASE)
        if m:
            return "write_file", {"filepath": m.group(1).strip(), "content": m.group(2).strip()}

    if re.search(r"\b(copy|duplicate)\b", t):
        paths = re.findall(r"[a-zA-Z]:[\\/][^\s;,]+", text)
        if len(paths) >= 2:
            return "copy_file", {"src": paths[0].rstrip(",.;"), "dst": paths[1].rstrip(",.;")}
    if re.search(r"\bmove\b", t):
        paths = re.findall(r"[a-zA-Z]:[\\/][^\s;,]+", text)
        if len(paths) >= 2:
            return "move_file", {"src": paths[0].rstrip(",.;"), "dst": paths[1].rstrip(",.;")}
    if re.search(r"\brename\b", t):
        paths = re.findall(r"[a-zA-Z]:[\\/][^\s;,]+", text)
        m = re.search(r"\bto\s+([\w .-]+?)[?.!]*$", text)
        if paths and m:
            return "rename_file", {"path": paths[0].rstrip(",.;"), "new_name": m.group(1).strip()}

    if re.search(r"\b(delete|remove|erase|get rid of)\b", t) and re.search(r"\bfile\b", t):
        m = re.search(r"([a-zA-Z]:[\\/][^\s;]+|/[/\w .-]+\.\w+|~[/\\][^\s;]+)", text)
        if m:
            return "delete_file", {"path": re.sub(r"[.,;!?]+$", "", m.group(1))}
    if re.search(r"\b(delete|remove|erase|get rid of)\b", t) and re.search(r"\b(folder|directory)\b", t):
        m = re.search(r"([a-zA-Z]:[\\/][^\s;]+|/[/\w .-]+|~[/\\][^\s;]+)", text)
        if m:
            return "delete_folder", {"path": re.sub(r"[.,;!?]+$", "", m.group(1))}

    # ---- Input simulation -------------------------------------------------
    qt = re.search(r"[\"'\u201c\u201d]([^\"'\u201c\u201d]+)[\"'\u201c\u201d]", text)
    if re.search(r"\bsimulate typing\b", t) and qt:
        return "simulate_typing", {"text": qt.group(1)}
    m = re.search(r"^\s*(?:please\s+)?(?:type(?: out)?|key in|enter|write)\s+(?:the (?:following )?(?:text|sentence|word|phrase)\s+)?(.+?)[?.!]*$", t)
    if m and m.group(1).strip():
        return "simulate_typing", {"text": m.group(1).strip().strip("\"'")}
    if re.search(r"\bsimulate click\b|\bclick at\b", t):
        c = re.search(r"\b(\d{1,4})\s*[,; ]\s*(\d{1,4})", t)
        if c:
            return "simulate_click", {"x": int(c.group(1)), "y": int(c.group(2))}

    # Open an application or website
    m = re.search(r"\b(?:open|start|launch|go to)\s+(.+?)[?.!]*$", t)
    if m:
        target = m.group(1).strip().strip("'\"")
        if target and not re.search(r"a (file|document|folder|tab)", target):
            dom = re.search(r"([a-z0-9-]+\.)+[a-z]{2,}", target)
            if dom:
                return "open_website", {"url": dom.group(0)}
            if target.lower() in ("youtube", "google", "facebook", "twitter", "reddit", "netflix", "github", "chatgpt", "gmail"):
                return "open_website", {"url": target + ".com"}
            return "open_app", {"app_name": target}

    return None


def _find_json_object(text):
    """Return the text of the first top-level-looking {...} block, or None."""
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]
    return None


def _extract_tool_call(content):
    """Try to parse a JSON tool call that a model may have written as plain text
    (instead of Ollama's native tool_calls field). Returns (name, args) or None."""
    if not content:
        return None
    text = content.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        candidates = [fenced.group(1).strip(), text]
    else:
        candidates = [text, _find_json_object(text)]
    seen = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            obj = json.loads(candidate)
        except Exception:
            continue
        if isinstance(obj, dict) and "name" in obj:
            return obj["name"], obj.get("arguments") or {}
    return None


def _coerce_args(args):
    """Some models emit arguments like {"a": {"type": "integer", "value": 2}}.
    Normalize them into plain values, and un-JSON strings that are themselves JSON."""
    if not isinstance(args, dict):
        return {}
    out = {}
    for key, value in args.items():
        if isinstance(value, dict) and "value" in value:
            out[key] = value["value"]
        elif isinstance(value, str):
            try:
                out[key] = json.loads(value)
            except Exception:
                out[key] = value
        else:
            out[key] = value
    return out


def _is_chat(text):
    """Heuristic: is this conversational small-talk rather than a command that
    should trigger a tool? Chat goes to the plain LLM (no tools) so it answers
    naturally instead of spuriously calling a tool (e.g. answering the time when
    the user just asked \"are you listening?\")."""
    t = re.sub(r"\s+", " ", (text or "").strip().lower()).strip("?!. ")
    if not t:
        return False
    # Real time/date requests must NOT be treated as chat.
    if re.search(r"\b(what time|what'?s the time|what is the time|the time now|current time|"
                 r"what date|today'?s date|what day is|tell me the time|give me the time)\b", t):
        return False
    if re.search(r"\b(can you hear|are you hearing|are you listening|do you hear|are you there|"
                 r"can you understand|can you hear me|are you awake|are you online|are you alive)\b", t):
        return True
    if re.search(r"\b(how are you|how '?s it going|what'?s up|how do you do|how have you been)\b", t):
        return True
    if re.search(r"\b(thank you|thanks|thank you so much|appreciate it|thx)\b", t):
        return True
    if re.search(r"\b(what('?s| is) your name|who are you|what are you|what can you do|what do you do)\b", t):
        return True
    if re.search(r"^(hi|hii+|heyy?|hello|hey|yo|good (morning|afternoon|evening)|good night|good day)\b[\s!.]*$", t):
        return True
    return False


class Agent:
    def __init__(self):
        check_connection()
        self.messages = self._build_initial_context()
        # Signalled when the user wants to interrupt the current turn (Stop button).
        self.cancel_event = threading.Event()

    def cancel(self):
        """Ask the agent to stop the in-progress generation/execution."""
        self.cancel_event.set()

    def _build_initial_context(self):
        """Rebuild the LLM context from persistent memory: remembered facts go
        into the system prompt, and recent conversation turns are reloaded so
        Nova remembers earlier parts of the chat (and across restarts)."""
        system = SYSTEM_PROMPT
        facts = memory.get_facts(MEMORY_FACTS)
        if facts:
            system += (
                "\n\nWhat you currently remember about the user (from past sessions):\n"
                + "\n".join("- " + f for f in facts)
            )
        system += "\n" + TOOL_EXAMPLES
        msgs = [{"role": "system", "content": system}]
        for turn in memory.load_recent_turns(MEMORY_TURNS):
            if turn.get("role") in ("user", "assistant") and turn.get("content"):
                msgs.append({"role": turn["role"], "content": turn["content"]})
        return msgs

    def _trim_history(self):
        """Keep the system message plus the most recent MAX_HISTORY messages, but
        trim on a safe boundary so a 'tool' result is never left at the head
        without its matching assistant tool_call (APIs reject that with 'tool
        message has no preceding assistant tool call'), and no assistant tool-call
        dangles at the tail with its tool results trimmed away."""
        if len(self.messages) <= MAX_HISTORY:
            return
        sys_msg = self.messages[0]
        rest = self.messages[1:]
        if len(rest) > (MAX_HISTORY - 1):
            rest = rest[-(MAX_HISTORY - 1):]
        # Drop any leading messages that aren't a turn opener. This removes an
        # orphaned 'tool' result (or dangling assistant tool_call) left at the head
        # after slicing, which is what broke the pairing on every request.
        while rest and rest[0].get("role") not in ("user", "system"):
            rest.pop(0)
        # Drop a trailing assistant that requests tools but whose tool results
        # were trimmed away (would otherwise dangle with no tool reply).
        while len(rest) > 1 and rest[-1].get("role") == "assistant" and rest[-1].get("tool_calls"):
            rest.pop()
        self.messages = [sys_msg] + rest

    def _chat_reply(self, user_text: str, language: str = "en") -> str:
        """Answer conversational small-talk with the plain LLM (no tools), so it
        replies naturally and never spuriously calls a tool. Falls back to a
        friendly canned line if the model is unavailable."""
        try:
            if language == "ur":
                self.messages.append({
                    "role": "user",
                    "content": (
                        "قدرتی اور گفتگو کے انداز میں جواب دیں۔ صارف اردو بول رہا ہے، "
                        "اس لیے عام بول چال کی اردو رسم الخط (اردو) میں مختصر اور دوستانہ جواب دیں۔"
                    ),
                })
            self.messages.append({"role": "user", "content": user_text})
            self._trim_history()
            _debug_dump(self.messages, "chat-reply")
            msg = chat_with_tools(self.messages, [], cancel_event=self.cancel_event)
            self.messages.append(msg)
            content = (msg.get("content") or "").strip()
            if content:
                return content
        except Exception as exc:
            print(f"[Agent] Chat reply error: {exc}")

        low = user_text.lower()
        if re.search(r"\b(hear|listen|there|awake|understand|online|alive)\b", low):
            return "Yes, I can hear you loud and clear! How can I help?"
        if re.search(r"\b(thank|thanks)\b", low):
            return "You're very welcome!"
        if re.search(r"\b(how are you|how '?s it going)\b", low):
            return "I'm doing great, thanks for asking! How can I help you?"
        return "Hello! How can I help you today?"

    def process_input(self, user_text: str = "", language: str = "en") -> str:
        """Run the user's text through the LLM (and tools), returning the final
        spoken answer. Common commands are handled deterministically first.
        `language` ('en'/'ur') tells the agent which language to reply in.
        Each exchange is saved to persistent long-term memory."""
        user_text = (user_text or "").strip()
        if not user_text:
            return ""

        # New turn -> clear any leftover cancel flag (e.g. from a previous stop).
        self.cancel_event.clear()

        try:
            reply = self._handle(user_text, language=language)
        except CancellationError:
            print("[Agent] Generation cancelled by user.")
            return "Okay, I've stopped."

        # Persist for long-term memory (survives restarts).
        try:
            memory.add_exchange(user_text, reply)
        except Exception as exc:
            print(f"[Memory] Could not persist exchange: {exc}")

        return humanize(reply)

    def _handle(self, user_text: str, language: str = "en") -> str:
        # 0) Conversational small-talk -> plain LLM (no tools) so it can't
        #    spuriously call a tool (e.g. answering the time to "are you there?").
        if _is_chat(user_text):
            return self._chat_reply(user_text, language)

        # 1) Deterministic intent routing for common commands. For Urdu input we
        #    skip the English fast-path so the LLM replies in Urdu (it can still
        #    call tools using the schemas).
        routed = _route_intent(user_text)
        if routed and language != "ur":
            name, args = routed
            print(f"[Route] Direct tool call: {name}{args}")
            if name in TOOL_FUNCTIONS:
                try:
                    return str(TOOL_FUNCTIONS[name](**args))
                except Exception as exc:
                    return f"Sorry, I had trouble with that: {exc}"

        # 2) Fall back to the LLM agent loop (with tools).
        if language == "ur":
            self.messages.append({
                "role": "user",
                "content": (
                    "جواب اردو میں، اردو رسم الخط (اردو) میں دیں کیونکہ صارف اردو بول رہا ہے۔ "
                    "بالکل قدرتی، گرم اور دوستانہ گفتگو کے انداز میں بولے جیسے ایک حقیقی انسان باتیں کر رہا ہو — "
                    "عام بول چال کی اردو استعمال کریں، نہ کہ رسمی یا مشینی ترجمہ۔ "
                    "جملے چھوٹے اور دل سے نکلیں۔ مارک ڈاؤن، بلٹ، ایموجی یا نمبر والی فہرست بالکل استعمال نہ کریں۔ "
                    "آپ اپنے ٹولز بھی استعمال کر سکتے ہیں۔"
                ),
            })
        self.messages.append({"role": "user", "content": user_text})

        hops = 0
        blank_retries = 0
        while hops < MAX_TOOL_HOPS:
            if self.cancel_event.is_set():
                raise CancellationError("Stopped before next step.")
            hops += 1
            self._trim_history()

            _debug_dump(self.messages, "agent-loop")
            response_msg = chat_with_tools(self.messages, TOOL_SCHEMAS,
                                           cancel_event=self.cancel_event)
            self.messages.append(response_msg)
            content = response_msg.get("content") or ""
            native_tool_calls = bool(response_msg.get("tool_calls"))
            tool_calls = list(response_msg.get("tool_calls") or [])

            # Fallback: some local models write the tool call as JSON in content
            # instead of using Ollama's native tool_calls field.
            if not tool_calls:
                parsed = _extract_tool_call(content)
                if parsed:
                    name, args = parsed
                    tool_calls = [{"function": {"name": name, "arguments": args}}]

            # Blank-response guard: if the model returned nothing (no text AND no
            # tool call), drop the empty assistant message and retry instead of
            # silently returning "" to the user.
            if not content.strip() and not tool_calls:
                self.messages.pop()
                blank_retries += 1
                print(f"[Agent] Empty model response (retry {blank_retries}).")
                if blank_retries >= 3:
                    return ("Sorry, the model returned an empty response. "
                            "Could you rephrase that?")
                continue

            if not tool_calls:
                return content

            # Execute tools
            pending = []
            for tc in tool_calls:
                if self.cancel_event.is_set():
                    raise CancellationError("Stopped before running tools.")
                fn = tc.get("function", {})
                name = fn.get("name")
                tool_id = tc.get("id")   # OpenAI/OpenRouter format includes an id
                args = _coerce_args(fn.get("arguments") or {})
                print(f"[Agent] Calling tool: {name}{args}")

                if name in TOOL_FUNCTIONS:
                    try:
                        result = TOOL_FUNCTIONS[name](**args)
                    except TypeError as te:
                        result = (
                            f"Tool '{name}' was called with missing/invalid arguments "
                            f"({te}). Call {name} again with the correct arguments."
                        )
                    except Exception as exc:
                        result = f"Error executing {name}: {exc}"
                else:
                    result = f"Error: unknown tool '{name}'."

                print(f"[Agent] Tool result: {str(result)[:300]}")
                pending.append((name, args, result, tool_id))

            if self.cancel_event.is_set():
                raise CancellationError("Stopped after running tools.")

            # Feed results back to the model on the next hop. Native Ollama/OpenRouter
            # tool calls expect the "tool" role (with tool_call_id for the OpenAI
            # format); for the JSON-in-content fallback we use a plain user summary.
            for name, args, result, tool_id in pending:
                if native_tool_calls:
                    tool_msg = {"role": "tool", "content": str(result)}
                    if tool_id:
                        tool_msg["tool_call_id"] = tool_id
                    self.messages.append(tool_msg)
                else:
                    self.messages.append({
                        "role": "user",
                        "content": (
                            f"[Tool result for {name}{args}]: {result}. "
                            "Now give your final concise, conversational answer to the user."
                        ),
                    })

        return "I stopped because I reached the maximum number of steps. Please try again."