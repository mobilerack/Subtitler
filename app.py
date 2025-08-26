import os
import uuid
import zipfile
import logging
from flask import Flask, request, jsonify, send_from_directory
import yt_dlp
import google.generativeai as genai
import ffmpeg

app = Flask(__name__)
TMP_DIR = "/tmp"

# Gemini prompt
TRANSLATE_PROMPT_TEMPLATE = """
Feladat: Fordítsd le a megadott SRT feliratot magyarra.
A formátumot és az időbélyegeket pontosan tartsd meg, csak a szöveget fordítsd.

Stílus: A fordítás legyen gördülékeny, természetes, és illeszkedjen a videó kontextusához.
Használj bátran szleng szótárat, valamint trágár kifejezéseket. Ne szó szerint fordíts!

Eredeti SRT felirat:
---
{srt_content}
---
"""

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/download/<path:filename>')
def download_file(filename):
    return send_from_directory(TMP_DIR, filename, as_attachment=True)

@app.route('/process-video', methods=['POST'])
def process_video():
    gemini_api_key = os.environ.get('GEMINI_API_KEY')
    data = request.get_json()
    video_url = data.get('url')
    burn_in = data.get('burnIn', False)

    if not all([video_url, gemini_api_key]):
        return jsonify({"error": "Hiányzó videó URL, vagy a GEMINI_API_KEY nincs beállítva a szerveren."}), 400
    
    unique_id = str(uuid.uuid4())
    log_path = os.path.join(TMP_DIR, f"{unique_id}.log")
    
    # Logolás beállítása egyedi fájlba
    logger = logging.getLogger(unique_id)
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(log_path, encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    if logger.hasHandlers():
        logger.handlers.clear()
    logger.addHandler(handler)
    
    # Fájlnevek
    audio_base_path = os.path.join(TMP_DIR, f"{unique_id}_audio")
    audio_path_final = audio_base_path + ".m4a"
    video_path = os.path.join(TMP_DIR, f"{unique_id}_video.mp4")
    srt_path = os.path.join(TMP_DIR, f"{unique_id}.srt")
    
    try:
        logger.info(f"Feldolgozás indult: {video_url}")
        
        # 1. Hang letöltése
        logger.info("Hang letöltése és kinyerése...")
        # ... (yt_dlp audio letöltési logika, mint korábban) ...
        logger.info("Hang letöltése kész.")

        # 2. Leirat készítése Geminivel
        genai.configure(api_key=gemini_api_key)
        logger.info("Hangfájl feltöltése a Gemini-re...")
        # ... (genai.upload_file logika, mint korábban) ...
        logger.info("Leirat készítése...")
        # ... (model.generate_content logika, mint korábban) ...
        logger.info("Leirat kész.")
        
        # 3. Videó letöltése
        logger.info("Videó letöltése...")
        # ... (yt_dlp video letöltési logika, mint korábban) ...
        logger.info("Videó letöltése kész.")

        # 4. Kimenet előállítása
        if burn_in:
            logger.info("Felirat ráégetése...")
            # ... (ffmpeg logika, mint korábban) ...
            logger.info("Felirat ráégetése kész.")
            output_path = os.path.join(TMP_DIR, f"{unique_id}_output.mp4")
            # ...
            response_data = { "video_url": f"/download/{os.path.basename(output_path)}", "download_url": f"/download/{os.path.basename(output_path)}", "burn_in": True }
        else:
            logger.info("ZIP fájl készítése...")
            zip_path = os.path.join(TMP_DIR, f"{unique_id}.zip")
            # ... (zipfile logika, mint korábban) ...
            response_data = {
                "video_url": f"/download/{os.path.basename(video_path)}", "srt_url": f"/download/{os.path.basename(srt_path)}",
                "download_url": f"/download/{os.path.basename(zip_path)}", "burn_in": False
            }
        
        with open(log_path, 'r', encoding='utf-8') as f:
            logs = f.read()
        
        response_data["logs"] = logs
        return jsonify(response_data)

    except Exception as e:
        error_message = f"Hiba történt: {e}"
        logger.error(error_message, exc_info=True)
        logs = ""
        if os.path.exists(log_path):
            with open(log_path, 'r', encoding='utf-8') as f:
                logs = f.read()
        return jsonify({"error": str(e), "logs": logs}), 500
    
    finally:
        handler.close()
        logger.removeHandler(handler)
        # ... Takarítás ...
