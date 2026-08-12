import os
import tempfile
import time
from collections import deque

import numpy as np
import sounddevice as sd
import soundfile as sf

from config import (
    SAMPLE_RATE, CHANNELS, SILENCE_THRESHOLD, SILENCE_DURATION,
    MAX_RECORD_SECONDS, MAX_SPEECH_WAIT,
)

# Small number of samples to keep right before the user starts speaking, so the
# first syllable isn't cut off.
PRE_ROLL_SECONDS = 0.5


def record_until_silence(max_seconds: int = None):
    """Record from the default microphone until the user stops talking.

    Speech detection (a VAD-like RMS gate) waits for the user to actually start
    speaking, keeps a small pre-roll of silence, then stops after a sustained
    period of silence. Returns the path to a temporary WAV file, or None if no
    speech was detected.
    """
    max_seconds = max_seconds or MAX_RECORD_SECONDS
    block = int(SAMPLE_RATE * 0.032)  # ~32ms per callback block

    print("Listening...")
    main_audio = []                    # chunks kept once speech starts
    pre_roll = deque(maxlen=int(PRE_ROLL_SECONDS * SAMPLE_RATE / block) + 1)

    started = False
    silence_start = None
    recording_start = time.time()

    def callback(indata, frames, time_info, status):
        nonlocal started, silence_start
        if status:
            print(status)
        chunk = indata.copy()
        # RMS as float32
        rms = float(np.sqrt(np.mean(np.square(chunk))))
        print(f"RMS: {rms:.4f}")

        if not started:
            if rms >= SILENCE_THRESHOLD:
                started = True
                main_audio.extend(pre_roll)  # carry over the pre-roll silence
                silence_start = None
            else:
                pre_roll.append(chunk)
            return

        # We are recording; classify this chunk.
        main_audio.append(chunk)
        if rms < SILENCE_THRESHOLD:
            if silence_start is None:
                silence_start = time.time()
        else:
            silence_start = None

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        blocksize=block,
        callback=callback,
    )

    with stream:
        while True:
            sd.sleep(100)
            now = time.time()
            if started and silence_start is not None and (now - silence_start) > SILENCE_DURATION:
                break
            if (now - recording_start) > max_seconds:
                print(f"Max recording time ({max_seconds}s) reached.")
                break
            if not started and (now - recording_start) > MAX_SPEECH_WAIT:
                print("No speech detected.")
                break

    if not started or not main_audio:
        print("Finished listening (no speech).")
        return None

    print("Finished listening.")

    audio = np.concatenate(main_audio, axis=0).astype(np.float32)
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak * 0.95

    temp_fd, temp_path = tempfile.mkstemp(suffix=".wav")
    os.close(temp_fd)
    sf.write(temp_path, audio, SAMPLE_RATE)
    return temp_path