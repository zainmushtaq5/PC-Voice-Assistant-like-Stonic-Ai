"""Persistent long-term memory for Nova, backed by a local SQLite database.

This replaces the old "only MAX_HISTORY in RAM" behaviour with real storage that
survives restarts. It stores:
  * conversation turns (user + assistant), so Nova remembers earlier conversation
  * facts about the user (e.g. "I live in London", "call me Sam")

Nothing leaves the machine — it's a plain file under memory/nova_memory.db.
"""
import os
import sqlite3
import threading
from datetime import datetime

from config import MEMORY_DB_PATH

_lock = threading.Lock()
_conn = None


def _ts():
    return datetime.now().isoformat(timespec="seconds")


def _get_conn():
    """Lazily open (and initialise) the SQLite connection. Thread-safe."""
    global _conn
    with _lock:
        if _conn is None:
            os.makedirs(os.path.dirname(MEMORY_DB_PATH) or ".", exist_ok=True)
            _conn = sqlite3.connect(MEMORY_DB_PATH, check_same_thread=False)
            _init_tables()
    return _conn


def _init_tables():
    c = _conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS turns (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               role TEXT NOT NULL,
               content TEXT NOT NULL,
               ts TEXT NOT NULL
           )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS facts (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               fact TEXT NOT NULL UNIQUE,
               ts TEXT NOT NULL
           )"""
    )
    _conn.commit()


# ---------------------------------------------------------------------------
# Conversation turns
# ---------------------------------------------------------------------------
def add_turn(role: str, content: str):
    """Append a single message to the conversation history."""
    if not content:
        return
    try:
        conn = _get_conn()
        with _lock:
            conn.execute(
                "INSERT INTO turns (role, content, ts) VALUES (?, ?, ?)",
                (role, content, _ts()),
            )
            conn.commit()
    except Exception as exc:
        print(f"[Memory] Failed to save turn: {exc}")


def add_exchange(user_text: str, assistant_text: str):
    """Convenience: store one completed user -> assistant exchange."""
    add_turn("user", user_text)
    add_turn("assistant", assistant_text)


def load_recent_turns(limit: int = 20):
    """Return the most recent `limit` turns as a list of {role, content} dicts
    in chronological order (oldest first), suitable for rebuilding the LLM context."""
    try:
        conn = _get_conn()
        with _lock:
            rows = conn.execute(
                "SELECT role, content FROM ("
                " SELECT role, content FROM turns ORDER BY id DESC LIMIT ?"
                ") ORDER BY id ASC",
                (limit,),
            ).fetchall()
        return [{"role": r[0], "content": r[1]} for r in rows]
    except Exception as exc:
        print(f"[Memory] Failed to load turns: {exc}")
        return []


def clear_history():
    """Wipe the conversation history (keeps facts)."""
    try:
        conn = _get_conn()
        with _lock:
            conn.execute("DELETE FROM turns")
            conn.commit()
    except Exception as exc:
        print(f"[Memory] Failed to clear history: {exc}")


# ---------------------------------------------------------------------------
# Facts about the user
# ---------------------------------------------------------------------------
def remember_fact(fact: str):
    """Persist a fact about the user (deduplicated by content)."""
    fact = (fact or "").strip()
    if not fact:
        return "Nothing to remember."
    try:
        conn = _get_conn()
        with _lock:
            conn.execute(
                "INSERT OR IGNORE INTO facts (fact, ts) VALUES (?, ?)",
                (fact, _ts()),
            )
            conn.commit()
        return f"Okay, I'll remember that: {fact}"
    except Exception as exc:
        return f"I had trouble remembering that: {exc}"


def get_facts(limit: int = 25):
    """Return the most recent facts (newest first) as a list of strings."""
    try:
        conn = _get_conn()
        with _lock:
            rows = conn.execute(
                "SELECT fact FROM facts ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [r[0] for r in rows]
    except Exception as exc:
        print(f"[Memory] Failed to load facts: {exc}")
        return []


def search_facts(query: str, limit: int = 10):
    """Return facts loosely matching a keyword query."""
    q = f"%{query}%"
    try:
        conn = _get_conn()
        with _lock:
            rows = conn.execute(
                "SELECT fact FROM facts WHERE fact LIKE ? ORDER BY id DESC LIMIT ?",
                (q, limit),
            ).fetchall()
        return [r[0] for r in rows]
    except Exception as exc:
        print(f"[Memory] Failed to search facts: {exc}")
        return []


def clear_facts():
    try:
        conn = _get_conn()
        with _lock:
            conn.execute("DELETE FROM facts")
            conn.commit()
    except Exception as exc:
        print(f"[Memory] Failed to clear facts: {exc}")


def summary():
    """Human-readable summary of what Nova currently remembers."""
    turns = len(load_recent_turns(100000))
    facts = get_facts(100000)
    return f"I'm remembering {len(facts)} facts about you, and the last {turns} messages of our conversation."
