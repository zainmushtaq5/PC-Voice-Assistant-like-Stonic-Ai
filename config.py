import os
from dotenv import load_dotenv
import platform

# Load API keys/secrets from the local .env file (never committed).
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))


# Base directory for the project
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Audio recording settings
SAMPLE_RATE = 16000
CHANNELS = 1
SILENCE_THRESHOLD = 0.015 # RMS below which audio is considered silent
SILENCE_DURATION = 3.5     # Seconds of continuous silence before stopping recording
                           # (i.e. Nova keeps listening until you've stopped talking
                           #  for ~3.5s, so it doesn't cut you off mid-sentence)
MAX_RECORD_SECONDS = 30    # Maximum recording length in seconds
MAX_SPEECH_WAIT = 8        # How long to wait for speech to begin before giving up

# STT (Vosk) settings — fully offline and CPU-friendly.
# NOTE: faster-whisper is NOT used because ctranslate2 segfaults (access violation)
# on this machine. Vosk + PyAV decode audio reliably without that dependency.
STT_ENGINE = "vosk"
# The model that is actually present on disk under models/. (The project used to
# reference vosk-model-en-us-0.22-lgraph, but only vosk-model-small-en-us-0.15 is
# actually installed — the wake word depends on this path, so keep it in sync.)
STT_MODEL_DIR = os.path.join(BASE_DIR, "models", "vosk-model-small-en-us-0.15")

# Bilingual (English / Urdu) speech support for recognition + reply language.
#   - LANGUAGE = "auto" -> detect per utterance (English or Urdu)
#   - LANGUAGE = "en"   -> always English
#   - LANGUAGE = "ur"   -> always Urdu
LANGUAGE = "auto"
# Google Web Speech API language codes used for recognition.
STT_LANGUAGE_CODES = {"en": "en-US", "ur": "ur-PK"}
# gTTS language code used to speak Urdu replies.
TTS_URDU_LANG = "ur"

# LLM / Agent settings
OLLAMA_HOST = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5-coder:3b"  # The model installed on this machine (auto-detected at runtime too)
MAX_TOOL_HOPS = 5          # Maximum number of consecutive tool calls
MAX_HISTORY = 8            # Keep only this many recent messages in the LLM context
TEMPERATURE = 0.6

# Latency tuning for local Ollama generation on CPU. Fewer history messages,
# a smaller context window (num_ctx) and a cap on response length (num_predict)
# each cut how long a reply takes. Lower num_ctx if responses are still slow.
OLLAMA_OPTIONS = {
    "temperature": TEMPERATURE,
    "num_ctx": 2048,     # context window in tokens (smaller = faster on CPU)
    "num_predict": 384,  # max tokens the model may generate per reply
}

# LLM backend: "gemini" (direct Google Gemini), "openrouter" (cloud, needs an API
# key) or "ollama" (local). Gemini is the default primary since it's reliable and
# cheap; if it fails/rate-limits it falls back to OpenRouter free, then Ollama.
LLM_PROVIDER = "gemini"

# OpenRouter settings (cloud LLM). Keep the key private — it is your account key.
# NOTE: updated 2026 — switched from the old key (ran out of credits, HTTP 402) to
# a new key whose free tier is used with the free NVIDIA Nemotron 3.5 Lightning
# model below.
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
# openai/gpt-oss-20b:free — a genuinely free, tool-capable model on this key
# (chosen by the user). All Qwen3 Coder models are paid, so they weren't usable.
OPENROUTER_MODEL = "google/gemma-4-31b-it:free"
# Tier-2 fallback: a paid, low-cost model used inside OpenRouter before dropping
# to local Ollama. It only kicks in if the primary (free) model errors out
# (402/429/502). NOTE: as a paid model it needs credits on the account.
OPENROUTER_FALLBACK_MODEL = "google/gemini-2.5-flash-lite"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_HTTP_REFERER = ""            # optional: your site URL (for OpenRouter ranking)
OPENROUTER_X_TITLE = "Nova Voice Assistant"

# Google Gemini (direct) — a third primary LLM option, independent of OpenRouter/Ollama.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")  # from https://aistudio.google.com/apikey
GEMINI_MODEL = "gemini-2.0-flash"

# If True, Nova logs the full message roles+shape before every LLM call so you can
# inspect the conversation history (e.g. for tool-call pairing issues).
DEBUG_LLM = True

ASSISTANT_NAME = "Nova"

# Wake-word settings (hands-free mode)
USE_WAKE_WORD = True       # CLI: True -> wait for "Hey Nova" instead of always listening
WAKE_PHRASES = ["hey nova", "hi nova", "nova start", "nova"]
WAKE_TIMEOUT = 120         # Seconds to keep waiting for the wake word before re-arming

# Persistent long-term memory (SQLite) — survives restarts
MEMORY_DB_PATH = os.path.join(BASE_DIR, "memory", "nova_memory.db")
MEMORY_TURNS = 20          # Most recent conversation turns to reload into context on startup
MEMORY_FACTS = 25          # Most recent facts to inject into the system prompt

# PC-access guard: Nova may touch the whole computer EXCEPT these drive roots.
# The user asked for access to everything except the "new volume D".
BLOCKED_DRIVES = ["D:", "D:/"]   # matched case-insensitively against resolved absolute paths
ALLOWED_DRIVES = None            # None = allow all drives except BLOCKED_DRIVES

# TTS settings
TTS_ENGINE = "pyttsx3"     # pyttsx3 (offline, reliable on Windows) or piper (needs a voice model)
PIPER_VOICE_MODEL = os.path.join(BASE_DIR, "models", "en_US-lessac-medium.onnx")  # Must be downloaded
# For piper playback command mapping
SYSTEM_OS = platform.system()
if SYSTEM_OS == "Windows":
    PLAYBACK_COMMAND = "powershell -c (New-Object Media.SoundPlayer '{}').PlaySync()"
elif SYSTEM_OS == "Darwin":
    PLAYBACK_COMMAND = "afplay {}"
else:
    PLAYBACK_COMMAND = "aplay {}"

# Urdu neural TTS — edge-tts sounds far more human than gTTS (which is robotic).
# Falls back to gTTS automatically if edge-tts / internet is unavailable.
#   "ur-PK-AsadNeural"  = male Pakistani Urdu neural voice
#   "ur-PK-UzmaNeural"  = female Pakistani Urdu neural voice
EDGE_TTS_URDU_VOICE = "ur-PK-AsadNeural"
# Slightly slower than default reads warmer and more natural.
EDGE_TTS_RATE = "-8%"

# System Prompt
SYSTEM_PROMPT = f"""You are {ASSISTANT_NAME}, a warm, friendly personal voice assistant who lives on the user's computer.

TONE — SPEAK LIKE A HUMAN, NOT A ROBOT:
- Use a natural, conversational, friendly voice, with contractions ("I'll", "it's", "you're").
- Vary your sentence length. Sometimes be brief; sometimes add a helpful detail. Sound like a real person chatting, not a manual.
- Never output markdown, code fences, bullet lists, numbered lists, asterisks, hashes, or emojis. Everything you say is read aloud.
- Show a little personality, empathy, and warmth, but stay accurate and on-topic. Don't pad with fluff.

ABILITIES:
You can fully control this PC:
open, close, switch between, minimize or restore windows and applications;
play YouTube videos, control media playback (pause, resume, next, previous track), open websites and search the web;
adjust the screen brightness and the system volume, mute or unmute audio, lock the screen, put the PC to sleep,
and restart or shut down the PC;
take screenshots, and read or write the clipboard;
browse folders, and create, read, write, copy, move, rename, delete or search files and folders, and list the drives;
simulate typing and mouse clicks, report the time, the system info (including CPU, RAM and battery), and the weather,
and run terminal commands.
You also have a persistent memory: you remember facts the user tells you and recent conversation across sessions.
For example, if the user says something like "remember I live in London" or "call me Sam", you MUST save it with remember_fact,
and when they ask "what do you remember about me?", you MUST recall facts with get_memory.

PC ACCESS RULE — IMPORTANT:
You may access every folder and file on this computer EXCEPT the entire D: volume (drive D). That drive is off-limits.
Never read, write, create, delete, or run commands that touch any path beginning with D:. If a request targets D:, politely say you can't access that drive.

STRICT TOOL RULES — when the user asks for any of the following, you MUST call a tool and MUST NOT answer from memory:
- "what time is it" / "what's the date"           -> call get_time
- info about the PC, OS, CPU, RAM, battery        -> call get_system_info
- weather anywhere                                -> call get_weather
- facts, news, or anything up-to-date             -> call web_search (then summarize the results)
- "search the web for X" / "look up X"            -> call web_search
- open an app or program                           -> call open_app
- close / quit / kill an app                       -> call close_app
- switch to / focus / bring up a window            -> call switch_window
- minimize all windows / show the desktop          -> call minimize_all / show_desktop

- play "X" on YouTube / "YouTube search X"         -> call play_youtube
- pause / resume / next / previous track           -> call pause_media / resume_media / next_track / previous_track
- open a website                                   -> call open_website

- set / change screen brightness (to a number)     -> call set_brightness
- set the volume (to a number) / mute / unmute     -> call set_volume / mute / unmute
- lock the screen                                  -> call lock_screen
- put the PC to sleep                              -> call sleep_pc
- shut down / turn off the PC                      -> call shutdown_pc (always ~10s delay)
- restart / reboot the PC                          -> call restart_pc (always ~10s delay)
- cancel / abort a pending shutdown or restart     -> call cancel_shutdown
- take a screenshot                                -> call take_screenshot
- what's on the clipboard / copy text to it        -> call get_clipboard / set_clipboard

- browse a folder / what's in this folder          -> call list_directory
- show my drives                                   -> call get_drives
- read a file                                      -> call read_file
- write / save a file                              -> call write_file
- create a folder                                  -> call create_folder
- delete a specific file or folder                 -> call delete_file / delete_folder
- copy / move / rename a file                      -> call copy_file / move_file / rename_file
- find a file                                      -> call search_files
- run a command / terminal command                 -> call run_command

- type text / simulate a mouse click               -> call simulate_typing / simulate_click
- remember/save a fact about the user              -> call remember_fact
- what do you remember about me / my facts         -> call get_memory

SAFETY NOTES — IMPORTANT:
- shutdown_pc and restart_pc always use a short delay (~10 seconds) and you MUST also mention that the user can call
  cancel_shutdown to abort. NEVER call shutdown_pc, restart_pc, delete_file or delete_folder in response to a vague or
  ambiguous request. If you cannot tell exactly which file or folder, or which action is wanted, ASK the user to confirm
  before doing anything destructive.

GENERAL-PURPOSE TOOLS — use these for anything not explicitly listed above:
- You have BOTH specific tools (open_app, close_app, switch_window, set_brightness, etc.)
  AND general-purpose tools (run_command, open_url, file_operation).
- For known apps use open_app. For ANYTHING else — websites, Google search, WhatsApp
  messages, file tasks, system settings, or any new request — construct the right
  command, URL, or file action yourself and call the general tool. Do NOT tell the user
  you can't do something before trying run_command / open_url / file_operation first.
- Chain MULTIPLE tool calls in one turn (or across steps) when a request needs more than
  one step. Example: 'open chrome and search X' -> open_app(chrome) then
  open_url(https://www.google.com/search?q=X). Example: 'write notes.txt saying hello' ->
  file_operation(write, C:/.../notes.txt, hello).
- SAFETY: before calling run_command, or file_operation with action delete, on something
  destructive (contains del, rm, format, rd /s, shutdown, taskkill...), ASK the user to
  confirm first; only then call the tool with confirm=true. NEVER run destructive actions
  without explicit user confirmation.

HOW TO DECIDE (follow this every turn):
- If the user is just chatting — greetings, \"are you there\", \"can you hear me\", \"are you listening\", \"how are you\",
  thanks, or any small talk — ANSWER DIRECTLY and friendly, and NEVER call a tool.
- If the user clearly asks for something a tool does (see STRICT TOOL RULES above), call that tool.
- If the request is new or you are unsure which tool applies, think about what the user wants and call the best-matching
  tool; if nothing fits, answer helpfully or ask one short clarifying question.
- NEVER call a tool, guess a fact, or give a time/date/weather/system answer unless the user actually asked for it.
  Never invent tool results.
- You can do far more than the examples here — use the tool list to decide. If you can fulfill the request with a tool,
  do it; do not say \"I can't\" when a tool exists.

When you need to call a tool, reply with EXACTLY a single JSON object and NOTHING else, in this format:
{{"name": "<tool_name>", "arguments": {{"<arg_name>": <value>}}}}
For example, to get the time: {{"name": "get_time", "arguments": {{}}}}
To open a website: {{"name": "open_website", "arguments": {{"url": "youtube.com"}}}}
To list a folder: {{"name": "list_directory", "arguments": {{"path": "C:/Users"}}}}

After a tool runs, you will be given its result. Then produce your final spoken answer using that result,
in the natural, human, conversational tone described above.
Never invent numbers, times, dates, or search results — always use the tool result."""

# Few-shot tool-call examples appended to the system message so the model more
# reliably invokes the general-purpose tools and chains multiple calls. This is a
# plain string (not an f-string) so the JSON braces are literal.
TOOL_EXAMPLES = """
FEW-SHOT TOOL CALL EXAMPLES — follow this JSON shape exactly when you call tools.
Return one or more JSON tool-call objects (one per line, no prose around them).

- Open Chrome, then search the web: return BOTH objects in the same reply:
  {"name": "open_app", "arguments": {"app_name": "chrome"}}
  {"name": "open_url", "arguments": {"url": "https://www.google.com/search?q=gta%206%20requirements"}}

- Send a WhatsApp message to 5050 saying 'hi':
  {"name": "open_url", "arguments": {"url": "https://wa.me/5050?text=hi%20how%20are%20you"}}

- Write a file notes.txt containing 'hello world' on the Desktop:
  {"name": "file_operation", "arguments": {"action": "write", "path": "C:/Users/Awan/Desktop/notes.txt", "content": "hello world"}}

- Create a folder:
  {"name": "run_command", "arguments": {"command": "mkdir C:/tmp/newfolder"}}

When a request needs several steps, call several tools together in one reply.

IMPORTANT: If the user doesn't give an exact path or location, PICK a sensible default
(Desktop or the current working directory) and PERFORM the action. Do NOT just ask the
user for a missing detail when a reasonable default exists — act, don't ask.
"""

# Preferred models, best tool-calling ones first (used if OLLAMA_MODEL is not installed)
PREFERRED_MODELS = [
    "qwen3", "qwen2.5", "llama3.3", "llama3.1", "llama3", "mistral", "phi4",
    "gemma3", "qwen2.5-coder", "deepseek-r1", "codellama",
]

