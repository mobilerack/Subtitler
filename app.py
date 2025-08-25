import os
import uuid
import time
import requests
import json
import logging
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
    """Hangfájl feltöltése a Speechmatics-hez, RÉSZLETES hibakezeléssel."""
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
    
    try:
        response = requests.post(url, headers=headers, files=files)
        # Ez a sor dob hibát, ha a státuszkód 4xx vagy 5xx
        response.raise_for_status() 
    except requests.exceptions.HTTPError as err:
        # Itt elkapjuk a hibát, és kiírjuk a részletes választ a szerverről
        logger.error(f"Speechmatics API hiba! Részletek: {err.response.text}")
        # Majd újra dobjuk a hibát, hogy a fő folyamat is leálljon
        raise err

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
    # A kód többi része ugyanaz marad, mint a legutóbbi teszt verziónál
    data = request.get_json()
    speechmatics_api_key = data.get('speechmaticsApiKey')
    gemini_api_key = data.get('geminiApiKey')
    
    # === TESZT ===
    video_url = "https://upload.wikimedia.org/wikipedia/commons/d/dd/En-us-house.ogg"
    language = "en"
    # =============

    unique_id = str(uuid.uuid4())
    log_path = os.path.join(TMP_DIR, f"{unique_id}.log")
    
    # Logolás beállítása...
    logger = logging.getLogger(unique_id)
    # ... (a többi logolási kód változatlan)
    
    audio_base_path = os.path.join(TMP_DIR, f"{unique_id}_audio")
    audio_path_final = audio_base_path + ".m4a"
    
    try:
        logger.info("Teszt feldolgozás indul...")
        
        # Hang letöltése...
        logger.info("Hang letöltése indul...")
        # ... (ydl_opts_audio és with yt_dlp.YoutubeDL... változatlan)
        
        # Átirat kérése...
        original_srt_content = get_speechmatics_srt(speechmatics_api_key, audio_path_final, language, logger)

        # A tesztben a többi lépés most nem fontos...
        logger.info("Teszt sikeres, a Speechmatics feldolgozta a fájlt.")
        with open(log_path, 'r') as f:
            logs = f.read()
        return jsonify({"success": True, "logs": logs, "download_url": "#"})

    except Exception as e:
        error_message = f"Hiba történt: {e}"
        logger.error(error_message, exc_info=True)
        logs = ""
        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                logs = f.read()
        # Itt most a részletesebb hibát fogja visszaadni
        return jsonify({"error": str(e), "logs": logs}), 500
    
    finally:
        # Takarítás...
        pass
