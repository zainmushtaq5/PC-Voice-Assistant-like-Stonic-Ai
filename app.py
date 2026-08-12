import base64
import os
import tempfile

from flask import Flask, jsonify, request

from audio.stt import transcribe_detect
from audio.tts import speak_to_file
from agent.core import Agent
from config import LANGUAGE

app = Flask(__name__, static_url_path='', static_folder='static')
agent = None


@app.before_request
def init_agent():
    global agent
    if agent is None:
        print("Initializing Agent...")
        agent = Agent()


@app.route('/')
def index():
    return app.send_static_file('index.html')


@app.route('/api/status', methods=['GET'])
def status():
    """Simple health check so the UI can show a friendly banner if something's off."""
    try:
        from agent.llm import pick_model
        model = pick_model()
        return jsonify({"ok": True, "model": model})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)})


@app.route('/api/chat', methods=['POST'])
def chat():
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files['audio']
    if audio_file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # Save the uploaded audio to a temp file (browsers usually send webm/ogg)
    temp_fd, temp_path = tempfile.mkstemp(suffix=".webm")
    os.close(temp_fd)

    try:
        audio_file.save(temp_path)

        # 1. Transcribe (auto-detects English vs Urdu) + decode wav/webm/ogg
        text, lang = transcribe_detect(temp_path, LANGUAGE)
        print(f"Transcribed [{lang}]: {text}")

        if not text:
            return jsonify({
                "text": "",
                "response": "Sorry, I couldn't hear that. Could you try again?",
                "audio": "",
            })

        # 2. Process with Agent (LLM + tools) — replies in the detected language
        response_text = agent.process_input(text, language=lang)
        print(f"Agent Response: {response_text}")

        # 3. Text to Speech -> base64 audio so the browser can play it
        audio_base64 = ""
        try:
            audio_path = speak_to_file(response_text)
            if audio_path and os.path.exists(audio_path):
                with open(audio_path, 'rb') as fh:
                    audio_base64 = base64.b64encode(fh.read()).decode('ascii')
                try:
                    os.remove(audio_path)
                except Exception:
                    pass
        except Exception as exc:
            print(f"TTS error: {exc}")

        return jsonify({
            "text": text,
            "response": response_text,
            "audio": audio_base64,
        })
    except Exception as exc:
        print(f"Error in chat endpoint: {exc}")
        return jsonify({"error": str(exc)}), 500
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


if __name__ == '__main__':
    # debug=False so the agent isn't double-initialised by the reloader.
    app.run(host='0.0.0.0', port=5000, debug=False)

