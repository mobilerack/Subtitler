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
    # ... (változatlan)
    pass

@app.route('/process-video', methods=['POST'])
def process_video():
    gemini_api_key = os.environ.get('GEMINI_API_KEY')
    data = request.get_json()
    video_url = data.get('url')
    burn_in = data.get('burnIn', False)

    if not all([video_url, gemini_api_key]):
        # ... (változatlan)
        pass
    
    genai.configure(api_key=gemini_api_key)
    
    unique_id = str(uuid.uuid4())
    log_path = os.path.join(TMP_DIR, f"{unique_id}.log")
    
    # Logolás beállítása...
    logger = logging.getLogger(unique_id)
    # ...

    audio_base_path = os.path.join(TMP_DIR, f"{unique_id}_audio")
    audio_path_final = audio_base_path + ".m4a"
    video_path = os.path.join(TMP_DIR, f"{unique_id}_video.mp4")
    srt_path = os.path.join(TMP_DIR, f"{unique_id}.srt")
    
    try:
        logger.info(f"Feldolgozás indult: {video_url}")

        # 1. LÉPÉS: Hang kinyerése a videóból
        logger.info("Hang letöltése és kinyerése...")
        ydl_opts_audio = {
            'format': 'bestaudio/best',
            'outtmpl': audio_base_path,
            'quiet': True,
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'm4a'}],
        }
        with yt_dlp.YoutubeDL(ydl_opts_audio) as ydl:
            info = ydl.extract_info(video_url, download=True)
            video_title = info.get('title', 'video')

        # === JAVÍTOTT, ROBUSZTUS ELLENŐRZÉS ===
        # A `yt-dlp` `info` szótárában ellenőrizzük, hogy van-e benne audiokodek.
        # Ha nincs, akkor az nem hangfájl (hanem valószínűleg egy HTML oldal).
        if not info.get('acodec') or info.get('acodec') == 'none':
            logger.error("A yt-dlp nem tudott hangot kinyerni. Az oldal valószínűleg blokkolja a letöltést.")
            raise ValueError("A megadott URL-ből nem sikerült érvényes hangfájlt kinyerni. Az oldal blokkolhatja a letöltést.")
        
        logger.info("Hang letöltése kész.")

        # 2. LÉPÉS: Leirat készítése Geminivel
        # ... (Ez a rész változatlan) ...

        # 3. LÉPÉS: A teljes videó letöltése
        # ... (Ez a rész változatlan) ...

        # 4. LÉPÉS: Kimenet előállítása
        # ... (Ez a rész változatlan) ...

    except Exception as e:
        # ... (Hibakezelés változatlan)
    
    finally:
        # ... (Takarítás változatlan)
        pass
