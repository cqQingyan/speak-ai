from flask import Flask, render_template, request, jsonify
from services.asr_service import transcribe_audio
from services.llm_service import chat_with_llm
from services.tts_service import text_to_speech
import base64
import os
import json

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/process_audio', methods=['POST'])
def process_audio():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided'}), 400

    audio_file = request.files['audio']
    audio_data = audio_file.read()

    # 1. ASR
    user_text = transcribe_audio(audio_data)

    # If ASR returns None or empty string, handle gracefully
    if not user_text:
        # Instead of 500, we can return a prompt asking the user to speak again
        # OR we can assume it was just silence/noise and ignore.
        # But for the UI flow, let's return a "I didn't hear you" message.
        user_text = ""
        ai_text = "抱歉，我没有听清，请再说一遍。"
    else:
        print(f"User said: {user_text}")

        # 2. LLM
        history_str = request.form.get('history', '[]')
        try:
            history = json.loads(history_str)
        except:
            history = []

        ai_text = chat_with_llm(user_text, history)
        print(f"AI replied: {ai_text}")

    # 3. TTS
    # Even if ASR failed, we want to speak the error message "I didn't hear you"
    audio_bytes = text_to_speech(ai_text)

    response_data = {
        'user_text': user_text,
        'ai_text': ai_text
    }

    if audio_bytes:
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        response_data['audio_base64'] = audio_base64
    else:
        # If TTS fails, we still return the text, just no audio
        print("TTS failed or returned no audio")

    return jsonify(response_data)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
