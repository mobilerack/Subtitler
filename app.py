import os
import uuid
import zipfile
from flask import Flask, request, jsonify, send_from_directory
import yt_dlp
import google.generativeai as genai
import ffmpeg

app = Flask(__name__)
TMP_DIR = "/tmp"

# ... (A TRANSLATE_PROMPT_TEMPLATE változatlan) ...

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/download/<path:filename>')
def download_file(filename):
    return send_from_directory(TMP_DIR, filename, as_attachment=True)

@app.route('/process-video', methods=['POST'])
def process_video():
    # A KULCSOT MÁR NEM A FELHASZNÁLÓTÓL, HANEM A BIZTONSÁGOS KÖRNYEZETBŐL OLVASSUK
    gemini_api_key = os.environ.get('GEMINI_API_KEY')
    
    data = request.get_json()
    video_url = data.get('url')
    burn_in = data.get('burnIn', False)

    if not all([video_url, gemini_api_key]):
        # A hibaüzenetet is frissítjük
        return jsonify({"error": "Hiányzó videó URL, vagy a GEMINI_API_KEY nincs beállítva a szerveren."}), 400
    
    genai.configure(api_key=gemini_api_key)
    
    # ... A kód többi része (letöltés, Gemini hívás, stb.) változatlan ...
    # ...
