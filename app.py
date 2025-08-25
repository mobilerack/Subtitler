import os
import uuid
import time
import requests
import json
from flask import Flask, request, jsonify, send_from_directory
import yt_dlp
import google.generativeai as genai
import ffmpeg

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

app = Flask(__name__)
TMP_DIR = "/tmp"

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

def get_speechmatics_srt(api_key, audio_file_path, language_code, logger):
    """
    Hangfájl közvetlen feltöltése a Speechmatics-hez és a leirat lekérése.
    """
    url = "https://asr.api.speechmatics.com/v2/jobs/"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    config = {
        "type": "transcription",
        "transcription_config": {
            "language": language_code,
            "output_format": "srt"
        }
    }
    
    # JAVÍTÁS ITT TÖRTÉNT: 'audio/mpeg' -> 'audio/mp4'
    files = {
        'config': (None, json.dumps(config), 'application/json'),
        'data_file': (os.path.basename(audio_file_path), open(audio_file_path, 'rb'), 'audio/mp4')
    }
    
    logger.info("Speechmatics job indítása fájlfeltöltéssel...")
    response = requests.post(url, headers=headers, files=files)
    response.raise_for_status()
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
    
    logger = logging.getLogger(unique_id)
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(log_path)
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    handler.setFormatter(formatter)
    if logger.hasHandlers():
        logger.handlers.clear()
    logger.addHandler(handler)
    
    audio_base_path = os.path.join(TMP_DIR, f"{unique_id}_audio")
    audio_path_final = audio_base_path + ".m4a"
    translated_srt_path = os.path.join(TMP_DIR, f"{unique_id}_translated.srt")
    video_path = os.path.join(TMP_DIR, f"{unique_id}_video.mp4")
    output_video_path = os.path.join(TMP_DIR, f"{unique_id}_output.mp4")
    
    try:
        logger.info(f"Feldolgozás indult a következő URL-lel: {video_url}")
        
        logger.info("Hang letöltése indul...")
        ydl_opts_audio = {
            'format': 'bestaudio/best', 'outtmpl': audio_base_path, 'quiet': True,
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'm4a'}]
        }
        with yt_dlp.YoutubeDL(ydl_opts_audio) as ydl:
            info = ydl.extract_info(video_url, download=True)
            video_title = info.get('title', 'video')
            safe_filename = "".join([c for c in video_title if c.isalpha() or c.isdigit() or c==' ']).rstrip() + ".mp4"
        logger.info("Hang letöltése kész.")

        original_srt_content = get_speechmatics_srt(speechmatics_api_key, audio_path_final, language, logger)

        logger.info("Fordítás indítása a Geminivel...")
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        final_prompt = TRANSLATE_PROMPT_TEMPLATE.format(srt_content=original_srt_content)
        gemini_response = model.generate_content(final_prompt)
        translated_srt_content = gemini_response.text
        with open(translated_srt_path, "w", encoding="utf-8") as f:
            f.write(translated_srt_content)
        logger.info("Fordítás kész.")

        logger.info("Videó letöltése a felirat ráégetéséhez...")
        ydl_opts_video = {'format': 'bestvideo+bestaudio/best', 'outtmpl': video_path, 'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts_video) as ydl:
            ydl.download([video_url])
        logger.info("Videó letöltése kész.")

        logger.info("Felirat ráégetése...")
        (ffmpeg.input(video_path).filter('subtitles', translated_srt_path, force_style="PrimaryColour=&H00FF00,Bold=1,FontSize=24")
         .output(output_video_path, acodec='copy').run(cmd=['ffmpeg', '-loglevel', 'quiet'], overwrite_output=True))
        logger.info("Felirat ráégetése kész. Minden sikeres.")

        with open(log_path, 'r') as f:
            logs = f.read()
        
        return jsonify({
            "success": True,
            "download_url": f"/download/{os.path.basename(output_video_path)}",
            "logs": logs
        })

    except Exception as e:
        error_message = f"Hiba történt: {e}"
        logger.error(error_message, exc_info=True)
        logs = ""
        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                logs = f.read()
        return jsonify({"error": str(e), "logs": logs}), 500
    
    finally:
        handler.close()
        logger.removeHandler(handler)
        files_to_clean = [log_path, audio_path_final, translated_srt_path, video_path]
        # A kész videót egyelőre ne töröljük, mert le kell tölteni
        if 'output_video_path' in locals() and os.path.exists(output_video_path):
             pass # Don't clean the output file yet
        
        for f in files_to_clean:
            if f and os.path.exists(f):
                os.remove(f)

# A letöltés utáni takarítást itt oldjuk meg
@app.route('/download/<filename>')
def download_file_and_cleanup(filename):
    path = os.path.join(TMP_DIR, filename)
    try:
        # Fájl elküldése
        response = send_from_directory(TMP_DIR, filename, as_attachment=True)
        
        # Ez a rész trükkös lehet a WSGI szerverek miatt,
        # a legjobb, ha egy háttérfeladat takarítja a régi fájlokat,
        # de egy egyszerűbb megoldás a @after_this_request
        @response.call_on_close
        def cleanup():
            if os.path.exists(path):
                os.remove(path)
        
        return response
    except FileNotFoundError:
        return "Fájl nem található", 404
