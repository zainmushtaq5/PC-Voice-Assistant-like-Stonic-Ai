import os
import tempfile

import speech_recognition as sr

from config import LANGUAGE, STT_LANGUAGE_CODES


def _ensure_wav(path):
    """Return a WAV path that speech_recognition can read. If `path` is already a
    RIFF/WAV file it is returned as-is; otherwise it is decoded to a temporary WAV
    via PyAV (handles webm/ogg/mp3 from the browser). The caller must delete the
    returned path if it differs from the input."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(12)
        if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
            return path
    except Exception:
        return path
    try:
        import av
        import numpy as np
        import soundfile as sf

        container = av.open(path)
        astr = next(s for s in container.streams if s.type == "audio")
        rate = getattr(astr.codec_context, "sample_rate", None) or 16000
        chunks = []
        for frame in container.decode(astr):
            arr = frame.to_ndarray()
            if arr.ndim == 1:
                arr = arr.reshape(1, -1)
            chunks.append(arr)
        if not chunks:
            return path
        data = np.concatenate(chunks, axis=1)  # (channels, samples)
        data = data.T                          # (samples, channels)
        if data.dtype.kind == "i":
            data = data.astype("float32") / 32768.0

        fd, out = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        sf.write(out, data, rate)
        return out
    except Exception as exc:
        print(f"[STT] PyAV decode failed, using original file: {exc}")
        return path


def _recognize(r, audio, lang_code, show_all=False):
    """Call Google Web Speech. Returns None on failure/unknown speech."""
    if not lang_code:
        return None
    try:
        return r.recognize_google(audio, language=lang_code, show_all=show_all)
    except sr.UnknownValueError:
        return None
    except Exception as exc:
        print(f"[STT] Google recognizer error: {exc}")
        return None


def _alternatives(resp):
    """Normalise recognize_google(show_all=True) output into a list of alts."""
    if isinstance(resp, dict):
        return resp.get("alternative", [])
    if isinstance(resp, list):
        return resp
    return []


def _top(alternatives):
    """Return (transcript, confidence) for the top hypothesis, else (None, None)."""
    if not alternatives:
        return None, None
    alt = alternatives[0]
    return alt.get("transcript"), alt.get("confidence")


def transcribe_detect(audio_path, language=None):
    """Transcribe audio and return (text, language) where language is 'en', 'ur'
    or ''. `language=None` uses config.LANGUAGE ('auto' detects per utterance)."""
    if not audio_path or not os.path.exists(audio_path):
        return "", ""
    lang = (language or LANGUAGE or "auto").strip().lower()

    readable = _ensure_wav(audio_path)   # converts webm/ogg/mp3 -> wav if needed
    temp_created = (readable != audio_path)

    try:
        with sr.AudioFile(readable) as source:
            r = sr.Recognizer()
            audio = r.record(source)
    except Exception as exc:
        print(f"[STT] Could not read audio file: {exc}")
        return "", ""
    finally:
        if temp_created and readable and os.path.exists(readable):
            try:
                os.remove(readable)
            except Exception:
                pass

    codes = STT_LANGUAGE_CODES

    # Forced language mode.
    if lang in codes:
        text = _recognize(r, audio, codes[lang])
        return (text or "").strip(), lang

    # Auto-detect: try English and Urdu, keep the higher-confidence hypothesis.
    en_alt = _alternatives(_recognize(r, audio, codes.get("en"), show_all=True))
    ur_alt = _alternatives(_recognize(r, audio, codes.get("ur"), show_all=True))
    en_txt, en_conf = _top(en_alt)
    ur_txt, ur_conf = _top(ur_alt)

    if en_txt and ur_txt:
        e = en_conf if en_conf is not None else 0.5
        u = ur_conf if ur_conf is not None else 0.3
        if u > e:
            return ur_txt.strip(), "ur"
        return en_txt.strip(), "en"
    if ur_txt and not en_txt:
        return ur_txt.strip(), "ur"
    if en_txt and not ur_txt:
        return en_txt.strip(), "en"
    return "", ""


def transcribe(audio_path):
    """Compatibility helper: transcribe and return only the text (auto-detects
    English vs Urdu using config.LANGUAGE)."""
    text, _lang = transcribe_detect(audio_path)
    return text
