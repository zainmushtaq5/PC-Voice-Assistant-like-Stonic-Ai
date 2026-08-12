"""Hands-free "Hey Nova" wake-word detection.

Uses Vosk with a small grammar restricted to wake phrases, fed continuously from
the microphone. When a wake phrase is heard, the callback is invoked and the
detector stops itself (the caller decides when to restart listening).
"""
import json
import threading

import numpy as np
import sounddevice as sd

from config import SAMPLE_RATE, STT_MODEL_DIR


class WakeWordDetector:
    def __init__(self, phrases=("hey nova", "hi nova", "nova"), rate=SAMPLE_RATE,
                 callback=None):
        self.phrases = [p.lower() for p in phrases]
        self.rate = rate
        self.callback = callback or (lambda: None)
        self._model = None
        self._rec = None
        self._stop = threading.Event()
        self._thread = None
        self._running = False

    def _load(self):
        if self._model is None:
            from vosk import KaldiRecognizer, Model
            self._model = Model(STT_MODEL_DIR)
            grammar = '["' + '", "'.join(self.phrases) + '"]'
            self._rec = KaldiRecognizer(self._model, self.rate, grammar)
            self._rec.SetWords(False)

    def start(self):
        if self._running:
            return
        self._running = True
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        self._stop.set()

    @property
    def running(self):
        return self._running

    def _run(self):
        try:
            self._load()
        except Exception as exc:
            print(f"[WakeWord] Failed to load model from {STT_MODEL_DIR}: {exc}")
            print("[WakeWord] Check that a Vosk model folder exists under models/.")
            self._running = False
            return

        print(f"[WakeWord] Listening for: {', '.join(self.phrases)}")

        detected = threading.Event()
        block = int(self.rate * 0.032)

        # Peak detection twice: on the running partial text, and every ~0.5s on
        # the finalized result too (more reliable on the small model).
        final_every = max(1, int(0.5 / (block / self.rate)))
        last_final = ""
        blocks_since_final = 0

        def _partial_text():
            try:
                return json.loads(self._rec.PartialResult()).get("partial", "").lower()
            except Exception:
                return ""

        def _found(text):
            return bool(text) and any(p in text for p in self.phrases)

        def audio_callback(indata, frames, time_info, status):
            nonlocal last_final, blocks_since_final
            if status or detected.is_set():
                return
            pcm = (np.clip(indata, -1.0, 1.0) * 32767).astype("int16").tobytes()
            self._rec.AcceptWaveform(pcm)
            partial = _partial_text()
            if _found(partial):
                print(f"[WakeWord] Detected: {partial}")
                detected.set()
                return
            blocks_since_final += 1
            if blocks_since_final >= final_every:
                blocks_since_final = 0
                try:
                    last_final = json.loads(
                        self._rec.FinalResult()).get("text", "").lower()
                except Exception:
                    pass
                if _found(last_final):
                    print(f"[WakeWord] Detected (final): {last_final}")
                    detected.set()

        try:
            with sd.InputStream(
                samplerate=self.rate,
                channels=1,
                blocksize=block,
                callback=audio_callback,
            ):
                while not self._stop.is_set() and not detected.is_set():
                    sd.sleep(100)
        except Exception as exc:
            print(f"[WakeWord] Microphone error: {exc}")
            self._running = False
            return

        if detected.is_set():
            self.stop()
            try:
                self.callback()
            except Exception as exc:
                print(f"[WakeWord] callback error: {exc}")


