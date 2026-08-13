"""Google Gemini (direct) backend — a third primary LLM option, independent of
OpenRouter and Ollama.

It converts Nova's OpenAI-style tool schemas into Gemini function_declarations,
runs its own multi-step tool loop (capped by MAX_TOOL_HOPS), reuses TOOL_FUNCTIONS
to execute any function call, and returns the final reply in the same shape the
agent loop expects ({role, content, tool_calls}), so the rest of Nova is unchanged.
Includes a blank-response guard, try/except error logging and DEBUG_LLM printing.
"""
from config import GEMINI_API_KEY, GEMINI_MODEL, MAX_TOOL_HOPS, DEBUG_LLM
from tools import TOOL_FUNCTIONS
from .ollama_client import CancellationError


def _import_genai():
    try:
        # pyrefly: ignore [missing-import]
        import google.generativeai as genai
    except Exception as exc:
        raise RuntimeError(f"google-generativeai is not installed: {exc}")
    return genai


_genai = None
_model = None


def _get_model():
    global _genai, _model
    if _model is None:
        _genai = _import_genai()
        _genai.configure(api_key=GEMINI_API_KEY or "")
        _model = _genai.GenerativeModel(GEMINI_MODEL)
    return _model


def check_connection():
    try:
        _get_model()
        print(f"[Gemini] Connected. Using model: {GEMINI_MODEL}")
    except Exception as exc:
        print(f"[Gemini] WARNING: {exc}")


def pick_model():
    return GEMINI_MODEL


def _to_declarations(tools):
    """OpenAI-style tool schemas -> Gemini function_declarations."""
    decls = []
    for t in tools or []:
        fn = (t or {}).get("function", {}) or {}
        decls.append({
            "name": fn.get("name", ""),
            "description": fn.get("description", "") or "",
            "parameters": fn.get("parameters") or {"type": "object", "properties": {}},
        })
    return decls


def _system_text(messages):
    return "\n".join((m.get("content") or "") for m in messages if m.get("role") == "system")


def _to_contents(messages):
    """OpenAI-style messages -> Gemini contents (system handled separately)."""
    contents = []
    for m in messages or []:
        role = m.get("role")
        content = (m.get("content") or "").strip()
        if role == "system":
            continue
        if role == "user":
            contents.append({"role": "user", "parts": [{"text": content}]})
        elif role == "assistant":
            contents.append({"role": "model", "parts": [{"text": content}]})
        # Gemini keeps its own function_call/function_response history internally,
        # so any OpenRouter-style 'tool' messages here are deliberately skipped.
    return contents


def _parse_response(resp):
    text = ""
    fn_calls = []
    try:
        cands = resp.candidates
        if not cands:
            fb = getattr(resp, "prompt_feedback", None)
            print(f"[Gemini] No candidates returned. prompt_feedback={fb!r}")
            return "", []
        cand = cands[0]
        finish_reason = getattr(cand, "finish_reason", None)
        if finish_reason and str(finish_reason) not in ("1", "STOP"):
            print(f"[Gemini] Candidate finish_reason={finish_reason!r} "
                  f"safety_ratings={getattr(cand, 'safety_ratings', None)!r}")
        parts = cand.content.parts
        if not parts:
            print(f"[Gemini] Candidate has no parts. finish_reason={finish_reason!r}")
    except Exception as exc:
        print(f"[Gemini] Could not parse response: {exc!r}")
        return "", []
    for p in parts:
        if hasattr(p, "function_call") and p.function_call:
            fn_calls.append(p.function_call)
        if hasattr(p, "text") and p.text:
            text += p.text
    return text.strip(), fn_calls


def _extract_args(fc):
    args = getattr(fc, "args", None)
    if args is None:
        return {}
    if hasattr(args, "items"):
        return dict(args.items())
    return dict(args or {})


def _dispatch(name, args):
    if name in TOOL_FUNCTIONS:
        try:
            result = TOOL_FUNCTIONS[name](**args)
        except TypeError as te:
            result = (
                f"Tool '{name}' was called with missing/invalid arguments ({te}). "
                f"Call {name} again with the correct arguments."
            )
        except Exception as exc:
            result = f"Error executing {name}: {exc}"
    else:
        result = f"Error: unknown tool '{name}'."
    return str(result)


def chat_with_tools(messages, tools, cancel_event=None):
    model_name = GEMINI_MODEL or "gemini-2.5-flash"
    genai = _import_genai()
    genai.configure(api_key=GEMINI_API_KEY or "")
    declarations = _to_declarations(tools)
    contents = _to_contents(messages)
    system = _system_text(messages)

    blank_retries = 0
    hops = 0
    while hops < MAX_TOOL_HOPS:
        hops += 1
        if cancel_event is not None and cancel_event.is_set():
            raise CancellationError("Stopped before next step.")

        if DEBUG_LLM:
            print(f"[Gemini] SENDING to {model_name} | tools ({len(declarations)}): "
                  + ", ".join(d["name"] for d in declarations))
            print(f"[Gemini] messages={len(contents)} system_len={len(system)}")

        try:
            model = genai.GenerativeModel(
                model_name,
                tools=[{"function_declarations": declarations}] if declarations else None,
                system_instruction=system or None,
            )
            resp = model.generate_content(contents)
        except CancellationError:
            raise
        except Exception as exc:
            print(f"[Gemini] API error: {exc!r}")
            raise RuntimeError(f"Gemini API error: {exc}") from exc

        text, fn_calls = _parse_response(resp)

        if fn_calls:
            contents.append({
                "role": "model",
                "parts": [
                    {"function_call": {"name": fc.name, "args": _extract_args(fc)}}
                    for fc in fn_calls
                ],
            })
            resps = []
            for fc in fn_calls:
                if cancel_event is not None and cancel_event.is_set():
                    raise CancellationError("Stopped during tool calls.")
                res = _dispatch(fc.name, _extract_args(fc))
                resps.append({"name": fc.name, "response": res[:2000]})
                print(f"[Gemini] Called tool: {fc.name} -> {res[:120]}")
            contents.append({
                "role": "user",
                "parts": [
                    {"function_response": {"name": rp["name"], "response": {"result": rp["response"]}}}
                    for rp in resps
                ],
            })
            continue  # more hops (multi-step chaining)

        if text.strip():
            return {"role": "assistant", "content": text, "tool_calls": []}

        # Blank-response guard
        blank_retries += 1
        print(f"[Gemini] Empty response (retry {blank_retries}).")
        if blank_retries >= 3:
            return {
                "role": "assistant",
                "content": "Sorry, the model returned an empty response. Could you rephrase that?",
                "tool_calls": [],
            }

    return {
        "role": "assistant",
        "content": "I ran out of steps while handling that. Please try again.",
        "tool_calls": [],
    }
