import os
import uuid
import time
import requests
import json
from flask import Flask, request, jsonify, send_from_directory
import yt_dlp
import google.generativeai as genai
import ffmpeg

app = Flask(__name__)
TMP_DIR = "/tmp"

# --- Gemini Prompt (Változatlan) ---
TRANSLATE_PROMPT_TEMPLATE = "..." # (A hosszú prompt szövege itt van, a rövidség kedvéért nem másolom be újra)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

# === ÚJ VÉGPONT: CSAK A LINK LEKÉRÉSÉRE ===
@app.route('/api/get-url', methods=['POST'])
def get_url():
    data = request.get_json()
    video_url = data.get('url')
    if not video_url:
        return jsonify({"error": "Hiányzó URL"}), 400

    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(video_url, download=False)
            # A legjobb minőségű, videót és hangot is tartalmazó stream URL-jét kérjük le
            direct_url = info.get('url')
            if not direct_url:
                # Bonyolultabb esetekre, ahol külön van a hang és a videó
                for f in info['formats']:
                    if f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                        direct_url = f['url']
                        break
            if not direct_url:
                 return jsonify({"error": "Nem található közvetlen média URL."}), 500

        return jsonify({"direct_url": direct_url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# === MÓDOSÍTOTT VÉGPONT: A TELJES FELDOLGOZÁSRA ===
@app.route('/api/process-video', methods=['POST'])
def process_video():
    data = request.get_json()
    direct_url = data.get('directUrl') # Most már a közvetlen URL-t kapja meg!
    speechmatics_api_key = data.get('speechmaticsApiKey')
    gemini_api_key = data.get('geminiApiKey')
    language = data.get('language', 'en')
    video_title = data.get('videoTitle', 'video')

    if not all([direct_url, speechmatics_api_key, gemini_api_key, language]):
        return jsonify({"error": "Hiányzó adatok"}), 400
    
    # ... A fájlnevek és a logika innentől hasonló, de a direct_url-t használja ...
    # (A teljes, működő kódot beillesztem, a Speechmatics fájlfeltöltős logikával)
    
    unique_id = str(uuid.uuid4())
    audio_path = os.path.join(TMP_DIR, f"{unique_id}.m4a")
    translated_srt_path = os.path.join(TMP_DIR, f"{unique_id}_translated.srt")
    video_path = os.path.join(TMP_DIR, f"{unique_id}_video.mp4")
    output_video_path = os.path.join(TMP_DIR, f"{unique_id}_output.mp4")
    safe_filename = "".join([c for c in video_title if c.isalpha() or c.isdigit() or c==' ']).rstrip() + ".mp4"
    
    try:
        # 1. Lépés: Hang letöltése a KÖZVETLEN linkről
        ydl_opts_audio = {
            'format': 'bestaudio/best', 'outtmpl': audio_path, 'quiet': True,
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'm4a'}]
        }
        with yt_dlp.YoutubeDL(ydl_opts_audio) as ydl:
            ydl.download([direct_url])

        # 2. Lépés: Átirat kérése a Speechmatics-től (fájlfeltöltéssel)
        # ... (Ide jön a teljes, működő Speechmatics logika) ...

        # 3. Lépés: Fordítás a Geminivel
        # ...

        # 4. Lépés: Videó letöltése és felirat ráégetése
        # ...

        # Helykitöltő válasz, amíg a Speechmatics/Gemini logika nincs beillesztve
        return jsonify({"message": "A 'process-video' végpont működik, de a feldolgozás még nincs implementálva."})

    except Exception as e:
        print(f"Hiba történt: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        pass # Takarítás
