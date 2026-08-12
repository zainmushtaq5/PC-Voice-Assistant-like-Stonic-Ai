"""OpenRouter (cloud LLM) backend — OpenAI-compatible chat + tool calling.

This lets Nova use a large model (e.g. Qwen3 Coder 480B A35B) over the internet
instead of the small local Ollama model, so it can reliably handle requests that
aren't hardcoded. The request/response format is OpenAI-compatible.
"""
import json

import requests

from config import (
    OPENROUTER_API_KEY, OPENROUTER_MODEL, OPENROUTER_FALLBACK_MODEL,
    OPENROUTER_BASE_URL, OPENROUTER_HTTP_REFERER, OPENROUTER_X_TITLE,
    OLLAMA_OPTIONS, DEBUG_LLM,
)
from .ollama_client import CancellationError

_selected_model = None


def _headers():
    h = {
        "Authorization": "Bearer " + (OPENROUTER_API_KEY or ""),
        "Content-Type": "application/json",
    }
    if OPENROUTER_HTTP_REFERER:
        h["HTTP-Referer"] = OPENROUTER_HTTP_REFERER
    if OPENROUTER_X_TITLE:
        h["X-Title"] = OPENROUTER_X_TITLE
    return h


def _list_models():
    try:
        r = requests.get(f"{OPENROUTER_BASE_URL}/models", headers=_headers(), timeout=20)
        r.raise_for_status()
        return [m.get("id") for m in r.json().get("data", [])]
    except Exception:
        return []


def _is_qwen3_coder(model_id):
    i = (model_id or "").lower()
    return "qwen3" in i and "coder" in i


def pick_model():
    """Choose the model id. Prefers OPENROUTER_MODEL if it's actually available,
    otherwise falls back to a genuinely FREE (:free) model — NEVER a paid one, so
    Nova can't silently hit an insufficient-credits 402."""
    global _selected_model
    if _selected_model:
        return _selected_model

    ids = _list_models()
    free_ids = [i for i in ids if i.lower().endswith(":free")]

    # 1) Use the configured model when it actually exists.
    if OPENROUTER_MODEL and OPENROUTER_MODEL in ids:
        _selected_model = OPENROUTER_MODEL
        return _selected_model

    # 2) Otherwise fall back only to free models, preferring familiar tool-capable
    #    families (qwen3 / nemotron / gpt-oss / gemma) over the rest.
    if free_ids:
        def _rank(mid):
            m = mid.lower()
            return (
                0 if any(k in m for k in ("qwen3", "nemotron", "gpt-oss", "gemma")) else 1,
                m,
            )
        _selected_model = sorted(free_ids, key=_rank)[0]
        return _selected_model

    # 3) Last resort: the configured id (OpenRouter will then report a clear error).
    _selected_model = OPENROUTER_MODEL or ""
    return _selected_model


def check_connection():
    """Validate key/model availability. Never raises — just logs a warning."""
    try:
        model = pick_model()
        print(f"[OpenRouter] Connected. Using model: {model}")
    except Exception as exc:
        print(f"[OpenRouter] WARNING: {exc}")


def _chat_once(model, messages, tools, cancel_event=None):
    """Run one chat request against a specific model. Returns the assistant message
    dict, or raises on any error."""
    temp = OLLAMA_OPTIONS.get("temperature", 0.6)
    max_tokens = OLLAMA_OPTIONS.get("num_predict", 384)

    payload = {
        "model": model,
        "messages": messages,
        "tools": tools or [],
        "tool_choice": "auto",          # explicitly allow the model to use tools
        "stream": True,
        "temperature": temp,
        "max_tokens": max_tokens,
    }

    if DEBUG_LLM:
        names = [t.get("function", {}).get("name", "?") for t in (tools or [])]
        print(f"[OpenRouter] SENDING to {model} | tools in payload ({len(names)}): {names}")
        print(f"[OpenRouter] tool_choice=auto | max_tokens={max_tokens}")

    url = f"{OPENROUTER_BASE_URL}/chat/completions"
    content = ""
    tool_calls = []

    try:
        with requests.post(url, json=payload, headers=_headers(),
                           stream=True, timeout=180) as resp:
            if resp.status_code != 200:
                body = resp.text or f"HTTP {resp.status_code}"
                print(f"[OpenRouter] ERROR response ({resp.status_code}): {body[:600]}")
                raise RuntimeError(f"OpenRouter error {resp.status_code}: {body[:500]}")
            for raw in resp.iter_lines():
                if cancel_event is not None and cancel_event.is_set():
                    raise CancellationError("Generation stopped by user.")
                if not raw:
                    continue
                line = raw.strip()
                if line.startswith(b"data:"):
                    line = line[5:].strip()
                if line == b"[DONE]":
                    break
                try:
                    chunk = json.loads(line)
                except Exception:
                    continue
                if chunk.get("error"):
                    print(f"[OpenRouter] STREAM error from API: {str(chunk.get('error'))[:500]}")
                    raise RuntimeError(str(chunk.get("error"))[:500])
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                if delta.get("content"):
                    content += delta["content"]
                for t in delta.get("tool_calls") or []:
                    idx = t.get("index", 0)
                    while len(tool_calls) <= idx:
                        tool_calls.append({
                            "id": "", "type": "function",
                            "function": {"name": "", "arguments": ""},
                        })
                    slot = tool_calls[idx]
                    if t.get("id"):
                        slot["id"] = t["id"]
                    fn = t.get("function") or {}
                    if fn.get("name"):
                        slot["function"]["name"] += fn["name"]
                    if fn.get("arguments"):
                        slot["function"]["arguments"] += fn.get("arguments", "")
    except requests.exceptions.ConnectionError as exc:
        print(f"[OpenRouter] Connection error: {exc}")
        raise RuntimeError(
            "Cannot reach OpenRouter. Check your internet connection and API key."
        ) from exc

    effective = [tc for tc in tool_calls if tc["function"].get("name")]
    if DEBUG_LLM:
        print(f"[OpenRouter] RESULT: content_len={len(content)} tool_calls={[t['function'].get('name') for t in effective]}")
    return {"role": "assistant", "content": content, "tool_calls": effective}


def chat_with_tools(messages, tools, cancel_event=None):
    """Try the primary free model; if it fails (402 insufficient credits, 429 rate
    limit, 502 capacity, etc.), fall back to the tier-2 low-cost paid model
    (OPENROUTER_FALLBACK_MODEL) before the caller falls back to local Ollama."""
    model = pick_model()
    if not model:
        raise RuntimeError("No OpenRouter model configured (set OPENROUTER_MODEL).")
    try:
        return _chat_once(model, messages, tools, cancel_event)
    except CancellationError:
        raise
    except Exception as exc_primary:
        fb = OPENROUTER_FALLBACK_MODEL
        if fb and fb.lower() != model.lower():
            print(f"[OpenRouter] Primary model {model} failed: {exc_primary}")
            print(f"[OpenRouter] Falling back to model: {fb}")
            return _chat_once(fb, messages, tools, cancel_event)
        raise
