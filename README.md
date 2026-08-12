# Nova — Local Voice Assistant

A fully local, privacy-respecting, **free** voice assistant for your PC.
It uses **Ollama** for the AI brain, **Vosk** for speech-to-text, and **pyttsx3**
(or Piper) for text-to-speech. Nothing is sent to the cloud.

## How it works

```
Your voice → Vosk (STT) → Nova Agent (Ollama + tools) → pyttsx3/Piper (TTS) → Your voice
```

The agent can **open apps and websites, search the web, read/write files, run
commands, simulate typing/clicks**, and report the time or system info. Common
commands are handled by a fast deterministic router; everything else goes to
the LLM with full tool-calling.

## Setup (Windows / Python 3.11 venv)

This project already ships a virtualenv with all dependencies installed.

```bash
# 1. (If not already done) install dependencies
.\.venv311\Scripts\python.exe -m pip install -r requirements.txt

# 2. Make sure Ollama is installed and running, with a model pulled
ollama serve          # (usually already running as a service)
ollama pull qwen2.5-coder:3b   # or any tool-capable model

# 3. STT: Vosk model already downloaded into models/vosk-model-small-en-us-0.15
#    If missing, run:
#      pip install vosk
#      Download vosk-model-small-en-us-0.15 and extract into models/
```

## Running the Assistant (Desktop GUI) — best for hands-free

A desktop window with **push-to-talk** and **hands-free "Hey Nova"** mode,
live transcript, and spoken replies:

```bash
.\.venv311\Scripts\python.exe gui.py
```

In the window:
- Press the **Push to Talk** button (or **Space**) and speak.
- Tick **Hands-free "Hey Nova"** and just say `Hey Nova` to wake it, then say
  your command — no clicking needed.

## Running the Assistant (Web UI) — recommended for browser

```bash
.\.venv311\Scripts\python.exe app.py
```

Then open **http://localhost:5000** in your browser, click **Start Listening**,
speak, and click **Stop Listening**. Nova transcribes, thinks, and speaks back —
all locally.

## Running the Assistant (Terminal only)

```bash
.\.venv311\Scripts\python.exe main.py
```

Hands-free mode keeps the mic only for the wake phrase, so Nova no longer records and
"listens" to everything around you. Press Ctrl+C, type `quit`, or say "goodbye" to exit.

## What's new / feature highlights

- **Hands-free + push-to-talk (CLI).** No more always-on continuous recording. Run
  `main.py` for hands-free (say "Hey Nova") or `main.py --no-wake` for push-to-talk.
- **Persistent long-term memory.** Conversations and facts you tell Nova are stored in a
  local SQLite file (`memory/nova_memory.db`) and survive restarts. Say *"remember that I
  live in London"* or *"call me Sam"*, then ask *"what do you remember about me?"*.
- **Wider toolset.** Nova can now browse folders, list and search files, list drives, open
  File Explorer, create/delete files, open Spotify, draft emails, open your calendar, and
  guide smart-home control — on top of the original app/website/web/weather/time/typing tools.
- **PC access with a safe boundary.** Nova may access the whole computer *except* the D:
  volume (`D:\`). File tools and `run_command` refuse anything on that drive. To change the
  excluded drive, edit `BLOCKED_DRIVES` in `config.py`.
- **Human, conversational tone.** The system prompt is written to speak like a real person
  (contractions, warmth, varied rhythm), and replies are post-processed to strip markdown,
  bullets, and emojis before they're read aloud.

## Bilingual (English / Urdu) chat

Nova can now listen, think and reply in **both English and Urdu**:

- **Speech recognition** uses Google Web Speech. With `LANGUAGE = "auto"` (the
  default) it tries English and Urdu per utterance and keeps whichever the API
  is most confident about. Set `LANGUAGE = "en"` or `"ur"` to force one.
- **Replies** follow the user's language. If you speak Urdu, Nova's LLM is told
  to answer in Urdu script (اردو) and the reply is spoken using Google TTS (gTTS).
  English stays on the local pyttsx3/Piper voices.
- Works on the CLI (`main.py`), the desktop GUI (`gui.py`) and the web UI
  (`app.py`) — the web UI's `webm`/`ogg` audio is decoded automatically.

> Both Urdu recognition and Urdu speech need internet (Google STT + gTTS), just
> like the existing Google-based English STT already does.

## Known limitations

- **LLM quality in Urdu.** The default model `qwen2.5-coder:3b` is an
  English/code model, so its Urdu is usable but not perfect (occasional mixed
  English or slightly stiff phrasing). A general multilingual model such as
  `qwen2.5:7b` or `qwen2.5:14b` (pull via `ollama pull`) produces much better
  Urdu.
- **Wake word.** "Hey Nova" wake detection is English-only (Vosk small English
  model). You wake it in English, then give the command in either language.
- **Urdu TTS / STT need internet** (gTTS and Google Web Speech). Local/offline
  Urdu voices/models are not bundled.
- **Auto-detection** calls Google twice (en + ur), so it's slightly slower than
  a single forced-language call. If you only use one language, set `LANGUAGE`
  accordingly for a faster response.
- **Destructive actions** (delete/shutdown/restart) still require an
  unambiguous request before Nova acts.

## Configuration

Everything is in `config.py`:

| Setting | What it does | Default |
|---|---|---|
| `OLLAMA_MODEL` | LLM used for thinking/tools | `qwen2.5-coder:3b` |
| `STT_MODEL_DIR` | Vosk offline speech model | `models/vosk-model-small-en-us-0.15` |
| `TTS_ENGINE` | `pyttsx3` (offline) or `piper` | `pyttsx3` |
| `SILENCE_THRESHOLD` | Microphone sensitivity | `0.012` |
| `ASSISTANT_NAME` | Name the assistant responds to | `Nova` |

> **Tip:** For noticeably smarter answers and more reliable tool calling, pull a
> larger model: `ollama pull qwen2.5:7b` (or `qwen2.5:14b` if you have RAM).
> Nova auto-detects and prefers the best tool-capable model installed.

## Notes

- **Why Vosk and not faster-whisper?** faster-whisper (ctranslate2) hard-crashes
  (access violation) on this specific CPU, so we use Vosk which is fully offline
  and CPU-friendly. Audio (webm/ogg/wav) is decoded with PyAV — no ffmpeg needed.
- The `run_command` tool can execute code on your machine. It has a basic
  denylist but is not fully sandboxed — only enable it if you trust your voice
  input and keep your mic disabled otherwise.

