"""Provider-agnostic LLM entry point.

A short layer over the backends (OpenRouter cloud or local Ollama), exposing the
same three names the rest of the app imports: `chat_with_tools`,
`check_connection` and `pick_model`.

`LLM_PROVIDER` picks the primary backend; if it fails (for example OpenRouter is
out of credits), we automatically fall back to the other backend so Nova keeps
working instead of breaking. The provider is read from `config.LLM_PROVIDER` on
every call, so Nova can switch between Online (OpenRouter) and local (Ollama) at
run time from the UI without restarting.
"""
import config
from .ollama_client import CancellationError

_BACKENDS = None

# Ordered fallback chain per selected primary provider. If the selected one fails
# (rate limit, 402, 429, etc.) we try the next provider in its chain.
_FALLBACK_ORDER = {
    "gemini": ["gemini", "openrouter", "ollama"],
    "openrouter": ["openrouter", "ollama"],
    "ollama": ["ollama", "openrouter"],
}


def _backends():
    global _BACKENDS
    if _BACKENDS is None:
        _BACKENDS = {
            "openrouter": _load_openrouter(),
            "ollama": _load_ollama(),
            "gemini": _load_gemini(),
        }
    return _BACKENDS


def _load_openrouter():
    from . import openrouter_client
    return openrouter_client


def _load_ollama():
    from . import ollama_client
    return ollama_client


def _load_gemini():
    from . import gemini_client
    return gemini_client


def _primary():
    return _backends()[config.LLM_PROVIDER]


def _chain():
    order = _FALLBACK_ORDER.get(config.LLM_PROVIDER, [config.LLM_PROVIDER])
    return [(p, _backends().get(p)) for p in order]


def check_connection():
    _primary().check_connection()


def pick_model():
    return _primary().pick_model()


def chat_with_tools(messages, tools, cancel_event=None):
    """Try backends in the configured fallback order (e.g. Gemini -> OpenRouter ->
    Ollama) and return the first one that answers. If all fail, raise with the
    collected errors. Cancellation is always forwarded unchanged."""
    errors = []
    for prov, backend in _chain():
        if backend is None:
            continue
        try:
            return backend.chat_with_tools(messages, tools, cancel_event)
        except CancellationError:
            raise
        except Exception as exc:
            print(f"[LLM] Backend '{prov}' failed: {exc}")
            errors.append(f"{prov}: {exc}")
    if errors:
        raise RuntimeError("LLM unavailable. " + "; ".join(errors))
    raise RuntimeError("No LLM backend available.")

