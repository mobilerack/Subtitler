import os
import uuid
import time
import requests
import json
import logging
import zipfile
from flask import Flask, request, jsonify, Response, send_from_directory
from threading import Thread
import yt_dlp
import google.generativeai as genai
import ffmpeg

app = Flask(__name__)
TMP_DIR = "/tmp"

# Egy egyszerű, globális "adatbázis" a jobok állapotának követésére
JOBS = {}

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

def process_task(job_id, video_url, gemini_api_key, burn_in):
    """Ez a függvény fut a háttérben, és végzi a nehéz munkát."""
    log_path = os.path.join(TMP_DIR, f"{job_id}.log")
    
    logger = logging.getLogger(job_id)
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(log_path, encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    if logger.hasHandlers():
        logger.handlers.clear()
    logger.addHandler(handler)

    try:
        audio_base_path = os.path.join(TMP_DIR, f"{job_id}_audio")
        audio_path_final = audio_base_path + ".m4a"
        video_path = os.path.join(TMP_DIR, f"{job_id}_video.mp4")
        srt_path = os.path.join(TMP_DIR, f"{job_id}.srt")
        output_video_path = os.path.join(TMP_DIR, f"{job_id}_output.mp4")
        zip_path = os.path.join(TMP_DIR, f"{job_id}.zip")

        logger.info(f"Feldolgozás indult: {video_url}")
        
        logger.info("Hang letöltése és kinyerése...")
        ydl_opts_audio = {
            'format': 'bestaudio/best', 'outtmpl': audio_base_path, 'quiet': True,
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'm4a'}]
        }
        with yt_dlp.YoutubeDL(ydl_opts_audio) as ydl:
            ydl.extract_info(video_url, download=True)
        logger.info("Hang letöltése kész.")

        genai.configure(api_key=gemini_api_key)
        logger.info("Hangfájl feltöltése a Gemini-re...")
        audio_file = genai.upload_file(path=audio_path_final, mime_type="audio/mp4")
        
        logger.info("Leirat készítése...")
        model = genai.GenerativeModel('models/gemini-1.5-pro-latest')
        prompt = "Készíts egy pontos, időbélyegzett SRT formátumú magyar feliratot ebből a hangfájlból. A fordítás legyen gördülékeny, természetes, és illeszkedjen a videó kontextusához. Használj bátran szleng szótárat, valamint trágár kifejezéseket. Ne szó szerint fordíts!"
        response = model.generate_content([prompt, audio_file])
        srt_content = response.text.strip()
        if "```srt" in srt_content:
             srt_content = srt_content.split("```srt")[1].split("```")[0].strip()
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)
        logger.info("Leirat kész.")
        genai.delete_file(audio_file.name)
        
        logger.info("Videó letöltése...")
        ydl_opts_video = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': video_path, 'quiet': True
        }
        with yt_dlp.YoutubeDL(ydl_opts_video) as ydl:
            ydl.download([video_url])
        logger.info("Videó letöltése kész.")

        if burn_in:
            logger.info("Felirat ráégetése...")
            (ffmpeg.input(video_path).filter('subtitles', srt_path, force_style="PrimaryColour=&H00FF00,Bold=1,FontSize=24")
             .output(output_video_path, acodec='copy').run(cmd=['ffmpeg', '-loglevel', 'quiet'], overwrite_output=True))
            logger.info("Felirat ráégetése kész.")
            JOBS[job_id] = {"status": "success", "download_url": f"/download/{os.path.basename(output_video_path)}", "burn_in": True, "video_url": f"/download/{os.path.basename(output_video_path)}"}
        else:
            logger.info("ZIP fájl készítése...")
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                zipf.write(video_path, os.path.basename(video_path))
                zipf.write(srt_path, os.path.basename(srt_path))
            JOBS[job_id] = {
                "status": "success", "burn_in": False,
                "video_url": f"/download/{os.path.basename(video_path)}",
                "srt_url": f"/download/{os.path.basename(srt_path)}",
                "download_url": f"/download/{os.path.basename(zip_path)}",
            }
        
    except Exception as e:
        error_message = f"Hiba történt: {e}"
        logger.error(error_message, exc_info=True)
        JOBS[job_id] = {"status": "error", "message": str(e)}
    finally:
        logger.info("END_OF_LOG")
        handler.close()
        logger.removeHandler(handler)

# === HIÁNYZÓ RÉSZEK PÓTOLVA ===
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/download/<path:filename>')
def download_file(filename):
    return send_from_directory(TMP_DIR, filename, as_attachment=True)
# ================================

@app.route('/process-video', methods=['POST'])
def start_process_video():
    data = request.get_json()
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {"status": "pending"}

    thread = Thread(target=process_task, args=(
        job_id,
        data.get('url'),
        data.get('geminiApiKey'),
        data.get('burnIn')
    ))
    thread.daemon = True
    thread.start()

    return jsonify({"job_id": job_id})

@app.route('/stream-logs/<job_id>')
def stream_logs(job_id):
    def generate():
        log_file = os.path.join(TMP_DIR, f"{job_id}.log")
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
                    if JOBS.get(job_id, {}).get("status") in ["success", "error"]:
                        job_details = JOBS.get(job_id, {})
                        yield f"event: result\ndata: {json.dumps(job_details)}\n\n"
                        break
                    time.sleep(0.5)

    return Response(generate(), mimetype='text/event-stream')

