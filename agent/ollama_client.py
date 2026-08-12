import json

import requests

from config import OLLAMA_HOST, OLLAMA_MODEL, PREFERRED_MODELS, OLLAMA_OPTIONS, DEBUG_LLM


def get_options():
    """Return the generation options sent to Ollama, so latency knobs
    (num_ctx / num_predict / temperature) in config.py take effect."""
    return dict(OLLAMA_OPTIONS)

# The model actually selected at runtime (latched after the first successful check).
_selected_model = None


class CancellationError(RuntimeError):
    """Raised when the user asks to stop the model mid-generation."""


def _available_models():
    """Return the list of model names currently installed in Ollama."""
    try:
        resp = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        return []


def _matches(name):
    """True if a model name matches one of the preferred tool-capable families."""
    base = name.split(":")[0]
    return any(base == p or name == p for p in PREFERRED_MODELS)


def pick_model():
    """Choose the best available model, preferring the configured model, then
    the best tool-capable model that is actually installed."""
    global _selected_model
    if _selected_model:
        return _selected_model

    names = _available_models()
    if not names:
        raise RuntimeError(
            f"Cannot reach Ollama at {OLLAMA_HOST}. "
            "Please start Ollama (run `ollama serve`) and pull a model, e.g. `ollama pull qwen2.5-coder:3b`."
        )

    configured_base = OLLAMA_MODEL.split(":")[0]
    # 1) Prefer the exact configured model if installed
    if OLLAMA_MODEL in names:
        _selected_model = OLLAMA_MODEL
    # 2) Otherwise any installed variant of the same family as the configured model
    elif any(n.split(":")[0] == configured_base for n in names):
        _selected_model = next(n for n in names if n.split(":")[0] == configured_base)
    # 3) Otherwise the best preferred (tool-capable) model
    elif any(_matches(n) for n in names):
        _selected_model = next(n for n in names if _matches(n))
    # 4) Fall back to whatever is installed
    else:
        _selected_model = names[0]

    return _selected_model


def check_connection():
    """Validate that Ollama is up and a usable model is present. Never raises —
    just logs a warning so the app can still boot while Ollama is starting."""
    try:
        model = pick_model()
        print(f"[Ollama] Connected. Using model: {model}")
    except Exception as exc:
        print(f"[Ollama] WARNING: {exc}")


def chat_with_tools(messages, tools, cancel_event=None):
    """Send a chat request (with optional tool schemas) to Ollama and return the
    assistant message dict. Native Ollama tool_calls are preserved as-is.

    Uses Ollama's streaming endpoint so the request can be interrupted: if
    `cancel_event` is set mid-generation (e.g. the user clicks "Stop"), the
    HTTP stream is aborted and a `CancellationError` is raised.
    """
    model = pick_model()

    payload = {
        "model": model,
        "messages": messages,
        "tools": tools or [],
        "stream": True,
        "options": get_options(),
    }

    if DEBUG_LLM:
        names = [t.get("function", {}).get("name", "?") for t in (tools or [])]
        print(f"[Ollama] SENDING to {model} | tools in payload ({len(names)}): {names}")

    # Reassemble an assistant message from the streamed chunks.
    msg = {"role": "assistant", "content": "", "tool_calls": []}

    try:
        with requests.post(f"{OLLAMA_HOST}/api/chat", json=payload,
                           timeout=180, stream=True) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines(decode_unicode=True):
                if cancel_event is not None and cancel_event.is_set():
                    raise CancellationError("Generation stopped by user.")
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except Exception:
                    continue
                message = data.get("message") or {}
                content = message.get("content") or ""
                if content:
                    msg["content"] += content
                if data.get("done"):
                    if message.get("tool_calls"):
                        msg["tool_calls"] = message.get("tool_calls")
                    break
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(
            f"Cannot reach Ollama at {OLLAMA_HOST}. Make sure Ollama is running (`ollama serve`)."
        ) from exc
    except CancellationError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Ollama request failed: {exc}") from exc

    return msg

