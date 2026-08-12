import os
import sys
import threading

from audio.recorder import record_until_silence
from audio.stt import transcribe_detect
from audio.tts import speak
from audio.wakeword import WakeWordDetector
from agent.core import Agent
from config import ASSISTANT_NAME, USE_WAKE_WORD, WAKE_PHRASES, LANGUAGE
from audio.mic import ensure_mic_unmuted

EXIT_PHRASES = ["exit", "quit", "stop listening", "goodbye", "power off"]


def _read_text():
    """Listen once, transcribe (auto-detecting English vs Urdu), clean up the
    temp audio, and return (text, language)."""
    audio_path = record_until_silence()
    if not audio_path:
        return "", "en"
    try:
        text, lang = transcribe_detect(audio_path, LANGUAGE)
    finally:
        if os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except Exception:
                pass
    return (text or ""), (lang or "en")


def _handle(agent: Agent) -> bool:
    """Capture + process one user utterance. Returns False if the user asked to exit."""
    text, lang = _read_text()
    if not text:
        print("(nothing heard)")
        return True
    print(f"You [{lang}]: {text}")

    if any(phrase in text.lower() for phrase in EXIT_PHRASES):
        print("Exiting...")
        speak("Goodbye!")
        return False

    response = agent.process_input(text, language=lang)
    speak(response)
    return True


def run_push_to_talk(agent: Agent):
    """Wait for the user to press Enter, then record; ends when they say goodbye."""
    print(f"\n=== {ASSISTANT_NAME} — push-to-talk mode ===")
    print("Press Enter to start talking, then speak. Say 'goodbye' to exit.\n")
    while True:
        input("Press Enter to talk (or Ctrl+C to exit)...")
        try:
            if not _handle(agent):
                break
        except KeyboardInterrupt:
            break
        except Exception as exc:
            print(f"An error occurred: {exc}")


def run_wake_word(agent: Agent):
    """Hands-free mode: Nova stays silent until you say the wake phrase."""
    print(f"\n=== {ASSISTANT_NAME} — hands-free mode ===")
    print(f'Say "Hey {ASSISTANT_NAME}" to wake me, then give your command.\n')
    print('Type "quit" or say "goodbye" to exit.\n')
    exit_request = threading.Event()

    def on_wake():
        if exit_request.is_set():
            return
        try:
            if not _handle(agent):
                exit_request.set()
                return
        except KeyboardInterrupt:
            exit_request.set()
            return
        except Exception as exc:
            print(f"An error occurred: {exc}")
        # re-arm for the next wake word
        if not exit_request.is_set():
            wake.start()

    state = {"wake": None}

    def start():
        wake = WakeWordDetector(phrases=WAKE_PHRASES, callback=on_wake)
        state["wake"] = wake
        wake.start()
        return wake

    wake = start()

    try:
        while not exit_request.is_set():
            line = input().strip().lower()
            if line in ("quit", "exit", "goodbye"):
                exit_request.set()
                break
            elif line == "stop":
                # Manually pause hands-free listening
                wake.stop()
                print('Hands-free paused. Press Enter to resume, or type "quit" to exit.')
                input()
                if not exit_request.is_set():
                    wake = start()
                    state["wake"] = wake
    finally:
        if state["wake"]:
            state["wake"].stop()


def main():
    print(f"Initializing {ASSISTANT_NAME}...")
    try:
        ensure_mic_unmuted()
    except Exception:
        pass
    agent = Agent()
    print("Initialization complete!")

    use_wake = USE_WAKE_WORD
    if "--no-wake" in sys.argv:
        use_wake = False
    elif "--wake" in sys.argv:
        use_wake = True

    try:
        if use_wake:
            run_wake_word(agent)
        else:
            run_push_to_talk(agent)
    except KeyboardInterrupt:
        print("\nExiting gracefully...")
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
