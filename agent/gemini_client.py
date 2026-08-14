"""Google Gemini (direct) backend using the google-genai SDK (v2+).

Migrated off the deprecated google.generativeai package. Function calling now
runs through `client.models.generate_content(...)` and preserves the model's
exact response parts — including `thought` and `thought_signature` — by reusing
them verbatim on the next model turn, which newer Gemini models (3.x) require for
reliable multi-turn tool-calling. The fallback chain and DEBUG_LLM logging live
outside this module in agent/llm.py and are unchanged.
"""
from config import GEMINI_API_KEY, GEMINI_MODEL, MAX_TOOL_HOPS, DEBUG_LLM
from tools import TOOL_FUNCTIONS
from .ollama_client import CancellationError


def check_connection():
    try:
        from google import genai
        genai.Client(api_key=GEMINI_API_KEY or "")
        print(f"[Gemini] Connected. Using model: {GEMINI_MODEL} (google-genai)")
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


def _to_contents(types, messages):
    """OpenAI-style messages -> genai Contents (system handled separately)."""
    contents = []
    for m in messages or []:
        role = m.get("role")
        content = (m.get("content") or "").strip()
        if role == "system":
            continue
        if role == "user":
            contents.append(types.Content(role="user", parts=[types.Part(text=content)]))
        elif role == "assistant":
            contents.append(types.Content(role="model", parts=[types.Part(text=content)]))
    return contents


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
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_API_KEY or "")
    model_name = GEMINI_MODEL or "gemini-2.5-flash"
    declarations = _to_declarations(tools)
    contents = _to_contents(types, messages)
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
            config = types.GenerateContentConfig(
                tools=[{"function_declarations": declarations}] if declarations else None,
                system_instruction=system or None,
            )
            resp = client.models.generate_content(
                model=model_name, contents=contents, config=config,
            )
        except CancellationError:
            raise
        except Exception as exc:
            print(f"[Gemini] API error: {exc!r}")
            raise RuntimeError(f"Gemini API error: {exc}") from exc

        try:
            cand = resp.candidates[0]
            resp_content = cand.content
            resp_parts = list(resp_content.parts)
        except Exception as exc:
            print(f"[Gemini] Could not parse response: {exc!r}")
            if blank_retries >= 3:
                return {"role": "assistant",
                        "content": "Sorry, the model returned an empty response. Could you rephrase that?",
                        "tool_calls": []}
            blank_retries += 1
            continue

        fn_parts = [p for p in resp_parts if getattr(p, "function_call", None)]
        text = "".join(getattr(p, "text", "") or "" for p in resp_parts)

        if fn_parts:
            # Reuse the model's exact parts (incl. thought + thought_signature) on
            # the next model turn so multi-turn chaining works on Gemini 3.x.
            contents.append(types.Content(
                role=resp_content.role or "model", parts=resp_parts))
            resps = []
            for p in fn_parts:
                fc = p.function_call
                name = (fc.name or "").strip()
                args = dict(fc.args) if getattr(fc, "args", None) else {}
                if cancel_event is not None and cancel_event.is_set():
                    raise CancellationError("Stopped during tool calls.")
                res = _dispatch(name, args)
                resps.append(types.Part(function_response=types.FunctionResponse(
                    name=name, response={"result": res[:2000]})))
                print(f"[Gemini] Called tool: {name} -> {res[:120]}")
            contents.append(types.Content(role="user", parts=resps))
            continue  # more hops (multi-step chaining)

        if text.strip():
            return {"role": "assistant", "content": text.strip(), "tool_calls": []}

        # Blank-response guard
        blank_retries += 1
        print(f"[Gemini] Empty response (retry {blank_retries}).")
        if blank_retries >= 3:
            return {"role": "assistant",
                    "content": "Sorry, the model returned an empty response. Could you rephrase that?",
                    "tool_calls": []}

    return {"role": "assistant",
            "content": "I ran out of steps while handling that. Please try again.",
            "tool_calls": []}
