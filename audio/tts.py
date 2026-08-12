import os
import re
import subprocess
import tempfile
import time
import pyttsx3
from config import TTS_ENGINE, PIPER_VOICE_MODEL, PLAYBACK_COMMAND, TTS_URDU_LANG, EDGE_TTS_URDU_VOICE, EDGE_TTS_RATE

_engine = None

# Matches Urdu script (Arabic-script range) so we know to use the Urdu TTS.
_URDU_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F]")


def _get_engine():
    """Lazily initialise the shared pyttsx3 engine (thread-safe enough for our use)."""
    global _engine
    if _engine is None:
        try:
            _engine = pyttsx3.init()
            # A slightly faster, natural rate for conversational output.
            try:
                rate = _engine.getProperty("rate")
                _engine.setProperty("rate", max(rate - 15, 120))
            except Exception:
                pass
        except Exception as exc:
            print(f"[TTS] Failed to init pyttsx3: {exc}")
            _engine = None
    return _engine


def _has_urdu(text):
    """True if the text contains Urdu/Arabic-script characters."""
    return bool(_URDU_RE.search(text or ""))


def _play_file(path, stop_event=None):
    """Stream an audio file through sounddevice so the first audio comes out almost
    immediately (no full-file pre-decode), and stop instantly the moment
    `stop_event` is set (the Stop button = force stop)."""
    container = None
    try:
        import av
        import numpy as np
        import sounddevice as sd

        container = av.open(path)
        astr = next(s for s in container.streams if s.type == "audio")
        rate = getattr(astr.codec_context, "sample_rate", None) or 48000

        frames = iter(container.decode(astr))
        try:
            first = next(frames)
        except StopIteration:
            return
        arr = first.to_ndarray()
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        channels = arr.shape[0]

        def _as_playable(a):
            if a.ndim == 1:
                a = a.reshape(1, -1)
            # PyAV gives planar (channels, samples); sounddevice wants (samples, channels)
            a = a.T
            if a.dtype.kind == "i":
                a = a.astype("float32") / 32768.0
            else:
                a = a.astype("float32")
            return np.ascontiguousarray(a)

        with sd.OutputStream(samplerate=rate, channels=channels, dtype="float32") as stream:
            stream.write(_as_playable(arr))
            for frame in frames:
                if stop_event is not None and stop_event.is_set():
                    try:
                        stream.abort()
                    except Exception:
                        pass
                    return
                stream.write(_as_playable(frame.to_ndarray()))
    except Exception as exc:
        print(f"[TTS] Could not play audio file: {exc}")
    finally:
        if container is not None:
            try:
                container.close()
            except Exception:
                pass


def _edge_urdu_to_file(text, stop_event=None):
    """Generate Urdu speech with the edge-tts neural voice, streaming to a temp MP3.
    Aborts early if `stop_event` is set (force-stop mid-generation). Returns the
    temp path, or '' on failure/abort."""
    try:
        import asyncio
        import edge_tts

        def _abort():
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass

        fd, path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)

        if stop_event is not None and stop_event.is_set():
            _abort()
            return ""

        async def _gen():
            comm = edge_tts.Communicate(text, EDGE_TTS_URDU_VOICE, rate=EDGE_TTS_RATE)
            async for chunk in comm.stream():
                if stop_event is not None and stop_event.is_set():
                    break
                ch_type = chunk.get("type")
                if ch_type == "audio" and chunk.get("data"):
                    with open(path, "ab") as fh:
                        fh.write(chunk["data"])

        asyncio.run(_gen())

        if stop_event is not None and stop_event.is_set():
            _abort()
            return ""
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return path
        _abort()
    except Exception as exc:
        print(f"[TTS] edge-tts unavailable ({exc}). Falling back to gTTS.")
    return ""


def _speak_urdu(text, stop_event=None):
    """Speak Urdu with the neural edge-tts voice first, falling back to gTTS so
    replies always work even if edge-tts / internet is unavailable."""
    if stop_event is not None and stop_event.is_set():
        return
    path = _edge_urdu_to_file(text, stop_event)
    if path:
        try:
            _play_file(path, stop_event)
            return
        finally:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
    _speak_gtts(text, stop_event)


def _speak_gtts(text, stop_event=None):
    """Speak Urdu text using Google TTS (gTTS) — robot-like fallback voice."""
    if stop_event is not None and stop_event.is_set():
        return
    try:
        from gtts import gTTS

        fd, path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        try:
            if stop_event is not None and stop_event.is_set():
                return
            gTTS(text=text, lang=TTS_URDU_LANG).save(path)
            _play_file(path, stop_event)
        finally:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
    except Exception as exc:
        print(f"[TTS] Urdu TTS unavailable ({exc}). Falling back to system voice.")
        speak_pyttsx3(text)


def _speak_english(text, stop_event=None):
    """Real-time English speech via the system engine (no render-then-play
    doubling, so it starts right away). `stop_speaking()` halts it immediately."""
    if stop_event is not None and stop_event.is_set():
        return
    engine = _get_engine()
    if engine is None:
        print("[TTS] No TTS engine available.")
        return
    try:
        engine.say(text)
        engine.runAndWait()
    except Exception as exc:
        print(f"[TTS] pyttsx3 speech error: {exc}")


def stop_speaking():
    """Force-stop any speech currently being produced (English engine or streaming
    playback). Called by the GUI Stop button for an immediate halt."""
    global _engine
    if _engine is not None:
        try:
            _engine.stop()
        except Exception:
            pass


def speak(text, stop_event=None):
    """Speak the given text aloud. Urdu uses the neural edge-tts voice (streamed);
    English uses the real-time system engine directly so it speaks at natural
    speed instead of rendering-a-file-then-playing (which doubled the time). Both
    are interruptible via `stop_event` / `stop_speaking()`."""
    if not text or not text.strip():
        return
    print(f"Assistant: {text}")
    if stop_event is not None and stop_event.is_set():
        return
    if _has_urdu(text):
        _speak_urdu(text, stop_event)
    else:
        _speak_english(text, stop_event)


def speak_piper(text):
    if not os.path.exists(PIPER_VOICE_MODEL):
        print(f"[TTS] Piper model not found at {PIPER_VOICE_MODEL}. Falling back to pyttsx3.")
        speak_pyttsx3(text)
        return

    temp_fd, temp_path = tempfile.mkstemp(suffix=".wav")
    os.close(temp_fd)
    try:
        cmd = f'echo "{text}" | piper -m "{PIPER_VOICE_MODEL}" -f "{temp_path}"'
        subprocess.run(cmd, shell=True, check=True, stderr=subprocess.DEVNULL)
        play_cmd = PLAYBACK_COMMAND.format(temp_path)
        subprocess.run(play_cmd, shell=True, check=True)
    except Exception as exc:
        print(f"[TTS] Piper error: {exc}. Falling back to pyttsx3.")
        speak_pyttsx3(text)
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


def speak_pyttsx3(text):
    engine = _get_engine()
    if engine is None:
        print("[TTS] No TTS engine available.")
        return
    try:
        engine.say(text)
        engine.runAndWait()
    except Exception as exc:
        print(f"[TTS] pyttsx3 speech error: {exc}")


def speak_to_file(text: str) -> str:
    """Generate TTS audio for text and return the path to a temp file (WAV for
    English, MP3 for Urdu — both playable by browsers)."""
    if not text or not text.strip():
        return ""

    # Urdu -> edge-tts neural voice first (human-sounding), then gTTS MP3
    # (browsers/`_play_file` both handle MP3).
    if _has_urdu(text):
        path = _edge_urdu_to_file(text)
        if path:
            return path
        try:
            from gtts import gTTS

            fd, path = tempfile.mkstemp(suffix=".mp3")
            os.close(fd)
            gTTS(text=text, lang=TTS_URDU_LANG).save(path)
            if os.path.exists(path) and os.path.getsize(path) > 0:
                return path
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
        except Exception as exc:
            print(f"[TTS] Urdu to-file error: {exc}")

    temp_fd, temp_path = tempfile.mkstemp(suffix=".wav")
    os.close(temp_fd)

    # Try Piper first (nicer voice) if configured and available.
    if TTS_ENGINE.lower() == "piper" and os.path.exists(PIPER_VOICE_MODEL):
        cmd = f'echo "{text}" | piper -m "{PIPER_VOICE_MODEL}" -f "{temp_path}"'
        try:
            subprocess.run(cmd, shell=True, check=True, stderr=subprocess.DEVNULL)
            if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
                return temp_path
        except Exception as exc:
            print(f"[TTS] Piper-to-file error: {exc}")

    # Fall back to pyttsx3.
    engine = _get_engine()
    if engine is not None:
        try:
            engine.save_to_file(text, temp_path)
            engine.runAndWait()
            if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
                return temp_path
        except Exception as exc:
            print(f"[TTS] pyttsx3-to-file error: {exc}")

    return ""

