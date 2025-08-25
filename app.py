import os
import uuid
import time
import requests
import json
import logging
from flask import Flask, request, jsonify, Response, send_from_directory
from threading import Thread
import yt_dlp
import google.generativeai as genai
import ffmpeg

app = Flask(__name__)
TMP_DIR = "/tmp"

# Egy egyszerű, globális "adatbázis" a jobok állapotának követésére
JOBS = {}

def process_task(job_id, video_url, gemini_api_key, burn_in):
    """Ez a függvény fut a háttérben, és végzi a nehéz munkát."""
    log_path = os.path.join(TMP_DIR, f"{job_id}.log")
    
    # Logolás beállítása a jobhoz tartozó fájlba
    logger = logging.getLogger(job_id)
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(log_path, encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    handler.setFormatter(formatter)
    if logger.hasHandlers():
        logger.handlers.clear()
    logger.addHandler(handler)

    try:
        # Fájlnevek definiálása
        audio_base_path = os.path.join(TMP_DIR, f"{job_id}_audio")
        audio_path_final = audio_base_path + ".m4a"
        video_path = os.path.join(TMP_DIR, f"{job_id}_video.mp4")
        srt_path = os.path.join(TMP_DIR, f"{job_id}.srt")
        output_video_path = os.path.join(TMP_DIR, f"{job_id}_output.mp4")
        zip_path = os.path.join(TMP_DIR, f"{job_id}.zip")

        # === Itt kezdődik a tényleges munka, minden lépést logolunk ===
        logger.info(f"Feldolgozás indult: {video_url}")
        
        # 1. Hang letöltése
        logger.info("Hang letöltése és kinyerése...")
        # ... (yt_dlp audio letöltési logika) ...
        logger.info("Hang letöltése kész.")

        # 2. Leirat készítése Geminivel
        logger.info("Hangfájl feltöltése a Gemini-re...")
        # ... (genai.upload_file logika) ...
        logger.info("Leirat készítése...")
        # ... (model.generate_content logika) ...
        logger.info("Leirat kész.")
        
        # 3. Videó letöltése
        logger.info("Videó letöltése...")
        # ... (yt_dlp video letöltési logika) ...
        logger.info("Videó letöltése kész.")

        if burn_in:
            logger.info("Felirat ráégetése...")
            # ... (ffmpeg logika) ...
            logger.info("Felirat ráégetése kész.")
            JOBS[job_id] = {"status": "success", "download_url": f"/download/{os.path.basename(output_video_path)}"}
        else:
            logger.info("ZIP fájl készítése...")
            # ... (zipfile logika) ...
            JOBS[job_id] = {
                "status": "success",
                "video_url": f"/download/{os.path.basename(video_path)}",
                "srt_url": f"/download/{os.path.basename(srt_path)}",
                "download_url": f"/download/{os.path.basename(zip_path)}",
            }
        
    except Exception as e:
        error_message = f"Hiba történt: {e}"
        logger.error(error_message, exc_info=True)
        JOBS[job_id] = {"status": "error", "message": str(e)}
    finally:
        handler.close()
        logger.removeHandler(handler)
        logger.info("END_OF_LOG")


@app.route('/process-video', methods=['POST'])
def start_process_video():
    data = request.get_json()
    job_id = str(uuid.uuid4())
    
    # Elmentjük a jobot 'pending' státusszal
    JOBS[job_id] = {"status": "pending"}

    # Elindítjuk a feldolgozást egy külön háttérszálon
    thread = Thread(target=process_task, args=(
        job_id,
        data.get('url'),
        data.get('geminiApiKey'),
        data.get('burnIn')
    ))
    thread.daemon = True
    thread.start()

    # Azonnal visszaadjuk a job_id-t a kliensnek
    return jsonify({"job_id": job_id})

@app.route('/stream-logs/<job_id>')
def stream_logs(job_id):
    def generate():
        log_file = os.path.join(TMP_DIR, f"{job_id}.log")
        # Várunk, amíg a logfájl létrejön
        while not os.path.exists(log_file):
            time.sleep(1)
        
        with open(log_file, 'r', encoding='utf-8') as f:
            while True:
                line = f.readline()
                if line:
                    if "END_OF_LOG" in line:
                        job_details = JOBS.get(job_id, {})
                        yield f"event: result\ndata: {json.dumps(job_details)}\n\n"
                        break
                    yield f"data: {line.strip()}\n\n"
                else:
                    time.sleep(0.5)

    return Response(generate(), mimetype='text/event-stream')

# A többi végpont (index, download) változatlan...
