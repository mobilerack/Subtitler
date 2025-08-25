import os
import uuid
import time
import requests
import json
from flask import Flask, request, jsonify, send_from_directory
import yt_dlp
import google.generativeai as genai
import ffmpeg

# Gemini prompt (változatlan)
TRANSLATE_PROMPT_TEMPLATE = """..."""

app = Flask(__name__)
TMP_DIR = "/tmp"

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

def get_speechmatics_srt(api_key, audio_file_path, language_code, logger):
    """Hangfájl közvetlen feltöltése a Speechmatics-hez."""
    url = "https://asr.api.speechmatics.com/v2/jobs/"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    config = {
        "type": "transcription",
        "transcription_config": { "language": language_code, "output_format": "srt" }
    }
    
    files = {
        'config': (None, json.dumps(config), 'application/json'),
        'data_file': (os.path.basename(audio_file_path), open(audio_file_path, 'rb'), 'audio/mp4')
    }
    
    logger.info("Speechmatics job indítása fájlfeltöltéssel...")
    response = requests.post(url, headers=headers, files=files)
    response.raise_for_status()
    job_id = response.json()['id']
    logger.info(f"Speechmatics job elküldve, ID: {job_id}")

    # Polling logika (változatlan)
    while True:
        # ...
        time.sleep(10)

    logger.info("SRT felirat lekérése...")
    srt_response = requests.get(f"{url}{job_id}/transcript?format=srt", headers=headers)
    srt_response.raise_for_status()
    logger.info("SRT felirat sikeresen lekérve.")
    return srt_response.text

@app.route('/process-video', methods=['POST'])
def process_video():
    data = request.get_json()
    # Eredeti URL-t figyelmen kívül hagyjuk a teszt idejére
    # video_url = data.get('url')
    speechmatics_api_key = data.get('speechmaticsApiKey')
    gemini_api_key = data.get('geminiApiKey')
    # A nyelvet is fixen angolra állítjuk a teszthez
    # language = data.get('language', 'en')

    # === TESZT ===
    # Használjunk egy garantáltan működő, egyszerű MP3 fájlt
    video_url = "https://upload.wikimedia.org/wikipedia/commons/d/dd/En-us-house.ogg"
    language = "en"
    # =============

    if not all([video_url, speechmatics_api_key, gemini_api_key, language]):
        return jsonify({"error": "Hiányzó adatok"}), 400
    
    unique_id = str(uuid.uuid4())
    log_path = os.path.join(TMP_DIR, f"{unique_id}.log")
    
    # ... Logolás beállítása (változatlan) ...
    
    audio_base_path = os.path.join(TMP_DIR, f"{unique_id}_audio")
    audio_path_final = audio_base_path + ".m4a"
    # ... többi fájlnév (változatlan) ...
    
    try:
        # ... Logolás indítása ...
        
        # 1. Lépés: Hangfájl letöltése a TESZT URL-ről
        logger.info("Hang letöltése indul...")
        ydl_opts_audio = {
            'format': 'bestaudio/best', 'outtmpl': audio_base_path, 'quiet': True,
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'm4a'}]
        }
        with yt_dlp.YoutubeDL(ydl_opts_audio) as ydl:
            # A videó címet most fixen adjuk meg
            video_title = "teszt_video"
            safe_filename = video_title + ".mp4"
            ydl.download([video_url])
        logger.info("Hang letöltése kész.")

        # A folyamat többi része (Speechmatics, Gemini, FFmpeg) változatlan
        original_srt_content = get_speechmatics_srt(speechmatics_api_key, audio_path_final, language, logger)
        
        # ... Gemini fordítás ...
        
        # A tesztben a videó ráégetést kihagyhatjuk, hogy gyorsabb legyen
        # Így a végén nem videót, hanem csak egy sikeres üzenetet kellene kapnunk a logban.
        logger.info("Teszt sikeres, a Speechmatics feldolgozta a fájlt.")
        with open(log_path, 'r') as f:
            logs = f.read()
        return jsonify({"success": True, "logs": logs, "download_url": "#"})

    except Exception as e:
        # ... Hibakezelés (változatlan) ...
    
    finally:
        # ... Takarítás (változatlan) ...
        pass
