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
TRANSLATE_PROMPT_TEMPLATE = """...""" # A prompt szövegét a rövidség kedvéért nem illesztem be újra

app = Flask(__name__)
TMP_DIR = "/tmp"

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/download/<filename>')
def download_file(filename):
    # Ez a végpont a kész, feliratozott videó letöltéséhez kell
    return send_from_directory(TMP_DIR, filename, as_attachment=True)

def get_speechmatics_srt(api_key, file_path, language_code, logger):
    """Videó- vagy hangfájl feltöltése a Speechmatics-hez."""
    url = "https://asr.api.speechmatics.com/v2/jobs/"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    config = {
        "type": "transcription",
        "transcription_config": {
            "language": language_code,
            "output_format": "srt"
        }
    }
    
    # A fájltípus alapján automatikusan beállítjuk a MIME típust
    mime_type = 'video/mp4' if file_path.endswith('.mp4') else 'audio/mp4'
    
    files = {
        'config': (None, json.dumps(config), 'application/json'),
        'data_file': (os.path.basename(file_path), open(file_path, 'rb'), mime_type)
    }
    
    logger.info(f"Speechmatics job indítása fájlfeltöltéssel... Fájl: {os.path.basename(file_path)}, Típus: {mime_type}")
    
    try:
        response = requests.post(url, headers=headers, files=files)
        response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        logger.error(f"Speechmatics API hiba! Részletek: {err.response.text}")
        raise err

    job_id = response.json()['id']
    logger.info(f"Speechmatics job elküldve, ID: {job_id}")

    while True:
        status_response = requests.get(f"{url}{job_id}", headers=headers)
        status_response.raise_for_status()
        job_status = status_response.json()['job']['status']
        logger.info(f"Job státusz: {job_status}")
        if job_status == "done":
            break
        if job_status in ["rejected", "failed"]:
            raise Exception(f"Speechmatics job sikertelen: {status_response.json()}")
        time.sleep(10)

    logger.info("SRT felirat lekérése...")
    srt_response = requests.get(f"{url}{job_id}/transcript?format=srt", headers=headers)
    srt_response.raise_for_status()
    logger.info("SRT felirat sikeresen lekérve.")
    return srt_response.text

@app.route('/process-video', methods=['POST'])
def process_video():
    data = request.get_json()
    video_url = data.get('url')
    speechmatics_api_key = data.get('speechmaticsApiKey')
    gemini_api_key = data.get('geminiApiKey')
    language = data.get('language', 'en')

    if not all([video_url, speechmatics_api_key, gemini_api_key, language]):
        return jsonify({"error": "Hiányzó adatok"}), 400
    
    unique_id = str(uuid.uuid4())
    log_path = os.path.join(TMP_DIR, f"{unique_id}.log")
    
    # Logolás beállítása... (változatlan)
    logger = logging.getLogger(unique_id)
    # ...
    
    video_path = os.path.join(TMP_DIR, f"{unique_id}_video.mp4")
    translated_srt_path = os.path.join(TMP_DIR, f"{unique_id}_translated.srt")
    output_video_path = os.path.join(TMP_DIR, f"{unique_id}_output.mp4")
    
    try:
        logger.info(f"Feldolgozás indult a következő URL-lel: {video_url}")
        
        # 1. LÉPÉS: A videó letöltése (már nem kell külön a hang)
        logger.info("Videó letöltése indul...")
        ydl_opts_video = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': video_path,
            'quiet': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts_video) as ydl:
            info = ydl.extract_info(video_url, download=True)
            video_title = info.get('title', 'video')
            safe_filename = "".join([c for c in video_title if c.isalpha() or c.isdigit() or c==' ']).rstrip() + ".mp4"
        logger.info("Videó letöltése kész.")

        # 2. LÉPÉS: Átirat kérése a LETÖLTÖTT videófájllal
        original_srt_content = get_speechmatics_srt(speechmatics_api_key, video_path, language, logger)

        # 3. LÉPÉS: Fordítás a Geminivel (változatlan)
        logger.info("Fordítás indítása a Geminivel...")
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        final_prompt = TRANSLATE_PROMPT_TEMPLATE.format(srt_content=original_srt_content)
        gemini_response = model.generate_content(final_prompt)
        translated_srt_content = gemini_response.text
        with open(translated_srt_path, "w", encoding="utf-8") as f:
            f.write(translated_srt_content)
        logger.info("Fordítás kész.")

        # 4. LÉPÉS: Felirat ráégetése (a videó már le van töltve)
        logger.info("Felirat ráégetése...")
        (ffmpeg.input(video_path).filter('subtitles', translated_srt_path, force_style="PrimaryColour=&H00FF00,Bold=1,FontSize=24")
         .output(output_video_path, acodec='copy').run(cmd=['ffmpeg', '-loglevel', 'quiet'], overwrite_output=True))
        logger.info("Felirat ráégetése kész. Minden sikeres.")

        with open(log_path, 'r', encoding='utf-8') as f:
            logs = f.read()
        
        return jsonify({
            "success": True,
            "download_url": f"/download/{os.path.basename(output_video_path)}",
            "logs": logs
        })

    except Exception as e:
        # Hibakezelés (változatlan)
        # ...
    
    finally:
        # Takarítás (változatlan)
        # ...
        pass
