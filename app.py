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
    
    genai.configure(api_key=gemini_api_key)
    
    unique_id = str(uuid.uuid4())
    log_path = os.path.join(TMP_DIR, f"{unique_id}.log")
    
    logger = logging.getLogger(unique_id)
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(log_path, encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    if logger.hasHandlers():
        logger.handlers.clear()
    logger.addHandler(handler)
    
    audio_path_final = os.path.join(TMP_DIR, f"{unique_id}_audio.m4a")
    video_path = os.path.join(TMP_DIR, f"{unique_id}_video.mp4")
    srt_path = os.path.join(TMP_DIR, f"{unique_id}.srt")
    
    try:
        logger.info(f"Feldolgozás indult: {video_url}")

        logger.info("Hang letöltése és kinyerése...")
        ydl_opts_audio = {
            'format': 'bestaudio/best', 'outtmpl': audio_path_final.replace('.m4a', ''),
            'quiet': True, 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'm4a'}]
        }
        with yt_dlp.YoutubeDL(ydl_opts_audio) as ydl:
            info = ydl.extract_info(video_url, download=True)
            video_title = info.get('title', 'video')

        if not os.path.exists(audio_path_final) or os.path.getsize(audio_path_final) == 0:
            logger.error("A yt-dlp nem tudott hangfájlt kinyerni.")
            raise ValueError("A megadott URL-ből nem sikerült hangfájlt kinyerni.")
        logger.info("Hang letöltése kész.")

        logger.info("Hangfájl feltöltése a Gemini-re...")
        audio_file = genai.upload_file(path=audio_path_final, mime_type="audio/mp4")
        
        logger.info("Leirat készítése...")
        model = genai.GenerativeModel('models/gemini-1.5-flash-latest')
        prompt = "Készíts egy pontos, időbélyegzett SRT formátumú feliratot ebből a hangfájlból..." # A teljes prompt itt van
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
        safe_filename = "".join([c for c in video_title if c.isalpha() or c.isdigit() or c==' ']).rstrip() + ".mp4"

        if burn_in:
            logger.info("Felirat ráégetése...")
            output_video_path = os.path.join(TMP_DIR, f"{unique_id}_output.mp4")
            (ffmpeg.input(video_path).filter('subtitles', srt_path, force_style="PrimaryColour=&H00FF00,Bold=1,FontSize=24")
             .output(output_video_path, acodec='copy').run(cmd=['ffmpeg', '-loglevel', 'quiet'], overwrite_output=True))
            logger.info("Felirat ráégetése kész.")
            response_data = {"video_url": f"/download/{os.path.basename(output_video_path)}", "download_url": f"/download/{os.path.basename(output_video_path)}", "burn_in": True}
        else:
            logger.info("ZIP fájl készítése...")
            zip_path = os.path.join(TMP_DIR, f"{unique_id}.zip")
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                zipf.write(video_path, os.path.basename(video_path))
                zipf.write(srt_path, os.path.basename(srt_path))
            response_data = {
                "video_url": f"/download/{os.path.basename(video_path)}", "srt_url": f"/download/{os.path.basename(srt_path)}",
                "download_url": f"/download/{os.path.basename(zip_path)}", "burn_in": False
            }
        
        with open(log_path, 'r', encoding='utf-8') as f:
            logs = f.read()
        response_data["logs"] = logs
        return jsonify(response_data)

    except Exception as e:
        # EZ A RÉSZ HIÁNYZOTT - MOST MÁR HELYESEN BE VAN HÚZVA
        error_message = f"Hiba történt: {e}"
        logger.error(error_message, exc_info=True)
        logs = ""
        if os.path.exists(log_path):
            with open(log_path, 'r', encoding='utf-8') as f:
                logs = f.read()
        return jsonify({"error": str(e), "logs": logs}), 500
    
    finally:
        # EZ A RÉSZ IS HIÁNYZOTT - MOST MÁR HELYESEN BE VAN HÚZVA
        handler.close()
        logger.removeHandler(handler)
        # Itt az összes ideiglenes fájlt töröljük, a letölthetőket kivéve
        # A letöltés utáni takarítás bonyolultabb, egyelőre a Render Disk-re támaszkodunk
        files_to_clean = [audio_path_final, srt_path, log_path]
        if burn_in:
            files_to_clean.append(video_path) # Az eredeti videót törölhetjük
        
        for f in files_to_clean:
            if os.path.exists(f):
                os.remove(f)

