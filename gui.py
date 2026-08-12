"""Nova — desktop voice assistant GUI.

A Tkinter window with:
  * Push-to-talk (click a button or press Space)
  * Hands-free "Hey Nova" wake word (toggle)
  * Live transcript, status, and spoken replies.

Run:  .\\.venv311\\Scripts\\python.exe gui.py
"""
import os
import queue
import threading
import eel

from agent.core import Agent
from audio.recorder import record_until_silence
from audio.stt import transcribe_detect
from audio.tts import speak, stop_speaking
from audio.wakeword import WakeWordDetector
import config


def beep():
    """Short audible cue for 'start listening' (Windows)."""
    try:
        import winsound
        winsound.Beep(1200, 90)
    except Exception:
        pass


class Controller(threading.Thread):
    """Runs on a background thread; never touches Tkinter directly."""

    def __init__(self, cmd_q, gui_q):
        super().__init__(daemon=True)
        self.cmd_q = cmd_q          # msg -> controller
        self.gui_q = gui_q          # (kind, text) -> GUI
        self.stop_evt = threading.Event()
        self.wake_enabled = False
        self.wake = None
        self.busy = False
        self.agent = None
        # Set when the user clicks Stop while Nova is speaking, so `speak()` can
        # cut the audio off immediately.
        self.speak_stop = threading.Event()
        # Runtime-switchable settings (mirrors config so the UI can change them live).
        # The segmented buttons default to "English" / "Online", so start in a
        # consistent state (unless the config already picked a specific language).
        self.lang = (config.LANGUAGE or "auto").lower()
        if self.lang not in ("en", "ur"):
            self.lang = "en"
        config.LANGUAGE = self.lang
        self.provider = (config.LLM_PROVIDER or "openrouter").lower()

    def _set_provider(self, provider):
        """Switch between 'gemini' (Google), 'openrouter' (Online) and 'ollama' (local)."""
        p = (provider or "").strip().lower()
        if p in ("gemini", "google"):
            self.provider = "gemini"
        elif p in ("openrouter", "online"):
            self.provider = "openrouter"
        elif p in ("ollama", "local"):
            self.provider = "ollama"
        else:
            return
        config.LLM_PROVIDER = self.provider
        label = {"gemini": "Google Gemini", "openrouter": "Online (OpenRouter)",
                 "ollama": "Ollama (local)"}[self.provider]
        self.notify('status', f'LLM mode: {label}')
        self.notify('info', f'[Settings] LLM switched to {label}')

    def _set_language(self, lang):
        """Set reply/recognition language: 'en', 'ur' or 'auto'."""
        l = (lang or "").strip().lower()
        if l not in ("en", "ur", "auto"):
            return
        self.lang = l
        config.LANGUAGE = l
        label = {"en": "English", "ur": "Urdu", "auto": "Auto"}.get(l, l)
        self.notify('status', f'Language: {label}')
        self.notify('info', f'[Settings] Language set to {label}')

    def run(self):
        self.notify('status', 'Loading Nova...')
        try:
            from audio.mic import ensure_mic_unmuted
            ensure_mic_unmuted()
        except Exception:
            pass
        try:
            self.agent = Agent()
        except Exception as exc:
            self.notify('agent', f"Startup error: {exc}")
            return
        self.notify('status', 'Ready. Click Push to Talk, or press Space.')

        while not self.stop_evt.is_set():
            try:
                msg = self.cmd_q.get(timeout=0.2)
            except queue.Empty:
                continue
            if msg == 'quit':
                break
            if msg == 'enable_wake':
                self.wake_enabled = True
                self._start_wake()
            elif msg == 'disable_wake':
                self.wake_enabled = False
                if self.wake:
                    self.wake.stop()
                self.notify('status', 'Hands-free off. Click Listen, or press Space.')
            elif msg == 'talk':
                if not self.busy:
                    self.handle_capture()
            elif isinstance(msg, tuple) and msg[0] == 'text':
                if not self.busy:
                    self.handle_text(msg[1])
            elif isinstance(msg, tuple) and msg[0] == 'set_provider':
                self._set_provider(msg[1])
            elif isinstance(msg, tuple) and msg[0] == 'set_language':
                self._set_language(msg[1])

        if self.wake:
            self.wake.stop()

    def notify(self, kind, text=''):
        self.gui_q.put((kind, text))

    def _start_wake(self):
        if self.wake:
            self.wake.stop()
        self.notify('status', f'Say "Hey {config.ASSISTANT_NAME}"...')
        self.wake = WakeWordDetector(callback=self._on_wake)
        self.wake.start()

    def _on_wake(self):
        self.notify('status', f'Hey {config.ASSISTANT_NAME}! Listening...')
        beep()
        self.handle_capture(manual=False)

    def handle_capture(self, manual=True):
        if self.busy or self.agent is None:
            return
        self.busy = True
        try:
            self.notify('status', 'Listening...')
            beep()

            path = record_until_silence()
            if not path:
                self.notify('status', 'Nothing heard. Try again.')
                return

            text, lang = transcribe_detect(path, self.lang)
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass

            if not text:
                self.notify('agent', "Sorry, I couldn't hear that. Could you try again?")
                return

            self.notify('user', text)
            self.notify('status', 'Thinking...')
            try:
                # Cancellable: clicking "Stop" interrupts the model generation.
                reply = self.agent.process_input(text, language=lang)
            except Exception as exc:
                reply = f"Sorry, something went wrong: {exc}"
            self.notify('agent', reply)

            self.notify('status', 'Speaking...')
            self.speak_stop.clear()
            try:
                # Cancellable: clicking "Stop" while speaking cuts the audio off
                # immediately via the speak_stop event.
                speak(reply, self.speak_stop)
            except Exception:
                pass
        finally:
            self.busy = False
            self.speak_stop.clear()
            if self.wake_enabled and not self.stop_evt.is_set():
                self._start_wake()  # stay hands-free, ready for the next "Hey Nova"
            else:
                self.notify('status', 'Ready.')

    def stop_processing(self):
        """Force-stop the current activity immediately. Interrupts model thinking,
        cuts off any speech (English engine or streaming playback) right away."""
        if self.agent is not None:
            self.agent.cancel()
        # Cut off any audio currently being spoken immediately (force stop).
        self.speak_stop.set()
        try:
            stop_speaking()
        except Exception:
            pass
        self.notify('status', 'Stopping...')

    def handle_text(self, text):
        """Text-input path (for testing alongside voice). Sends the typed text
        straight to the agent, shows the reply in the chat, and speaks it — the
        same pipeline voice uses, so nothing about voice mode is removed."""
        if self.busy or self.agent is None:
            return
        text = (text or "").strip()
        if not text:
            self.notify('status', 'Please type something first.')
            return
        self.busy = True
        try:
            self.notify('user', text)
            self.notify('status', 'Thinking...')
            try:
                # Cancellable: clicking "Stop" interrupts the model generation.
                reply = self.agent.process_input(text, language=self.lang)
            except Exception as exc:
                reply = f"Sorry, something went wrong: {exc}"
            self.notify('agent', reply)

            self.notify('status', 'Speaking...')
            self.speak_stop.clear()
            try:
                speak(reply, self.speak_stop)
            except Exception:
                pass
        finally:
            self.busy = False
            self.speak_stop.clear()
            self.notify('status', 'Ready.')


# Global queues for Eel
cmd_q = queue.Queue()
gui_q = queue.Queue()
controller_ref = None  # set after the controller thread starts, so JS can stop it

@eel.expose
def on_talk():
    cmd_q.put('talk')

@eel.expose
def on_text_input(text):
    """Text-input (testing) path — send typed text straight to the agent."""
    cmd_q.put(('text', text))

@eel.expose
def on_wake_toggle(enabled):
    cmd_q.put('enable_wake' if enabled else 'disable_wake')

@eel.expose
def on_set_provider(provider):
    """Switch LLM backend ('openrouter' = Online, 'ollama' = local)."""
    cmd_q.put(('set_provider', provider))

@eel.expose
def on_set_language(lang):
    """Switch reply/recognition language ('en' / 'ur')."""
    cmd_q.put(('set_language', lang))

@eel.expose
def on_stop():
    """Called from the web UI's Stop button. Interrupts thinking/execution even
    while the controller thread is blocked inside the LLM call."""
    if controller_ref is not None:
        controller_ref.stop_processing()

def start_gui():
    global controller_ref
    # Initialize eel with the web folder
    eel.init('web')
    
    # Start the controller thread
    controller = Controller(cmd_q, gui_q)
    controller_ref = controller
    controller.start()
    
    # Start background polling loop
    def poll_gui():
        while True:
            try:
                kind, text = gui_q.get_nowait()
                if kind == 'status':
                    eel.updateStatus(text)()
                elif kind == 'user':
                    eel.addChat(text, 'user')()
                elif kind == 'agent':
                    eel.addChat(text, 'agent')()
                elif kind == 'info':
                    eel.addChat(text, 'info')()
            except queue.Empty:
                pass
            eel.sleep(0.1)

    eel.spawn(poll_gui)
    
    try:
        eel.start('index.html', size=(540, 640), port=0)
    except (SystemExit, KeyboardInterrupt):
        pass
    finally:
        cmd_q.put('quit')
        controller.join(timeout=1)

if __name__ == "__main__":
    start_gui()

