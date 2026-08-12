"""Tools that let the LLM read and write Nova's persistent memory."""
from agent import memory


def remember_fact(fact: str) -> str:
    """Save a fact about the user so Nova remembers it across sessions."""
    return memory.remember_fact(fact)


def get_memory(query: str = "") -> str:
    """Recall what Nova remembers about the user."""
    if query and query.strip():
        matches = memory.search_facts(query.strip())
        if matches:
            return "I remember: " + "; ".join(matches) + "."
    facts = memory.get_facts()
    if not facts:
        return "I don't have any saved facts about you yet. Tell me something and I'll remember it."
    return "Here's what I remember about you: " + "; ".join(facts) + "."
