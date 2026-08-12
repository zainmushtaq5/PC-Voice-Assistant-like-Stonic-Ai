import logging
logging.basicConfig(level=logging.DEBUG)
try:
    from faster_whisper import WhisperModel
    print("Imported WhisperModel")
    model = WhisperModel('tiny', device='cpu', compute_type='default')
    print("Model loaded successfully")
except Exception as e:
    import traceback
    traceback.print_exc()
