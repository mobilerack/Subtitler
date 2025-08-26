import os
import uuid
import zipfile
import logging
import re
from flask import Flask, request, jsonify, send_from_directory
import yt_dlp
import google.generativeai as genai
import ffmpeg

app = Flask(__name__)
TMP_DIR = "/tmp"

# Gemini prompt (változatlan)
TRANSLATE_PROMPT_TEMPLATE = """..."""

def clean_and_format_srt(srt_text):
    """
    Ez a funkció fogadja a Gemini által adott nyers SRT szöveget,
    és garantáltan szabványos SRT formátumúvá alakítja.
    Kijavítja a pontokat vesszőkre az időbélyegekben és biztosítja a helyes sorközöket.
    """
    blocks = srt_text.strip().split('\n\n')
    cleaned_blocks = []
    for i, block in enumerate(blocks):
        lines = block.strip().split('\n')
        if len(lines) < 2:
            continue

        # Időbélyeg sor javítása (pontok cseréje vesszőkre)
        timestamp_line = lines[1].replace('.', ',')
        
        # Ellenőrizzük, hogy a formátum helyes-e, mielőtt hozzáadnánk
        if '-->' in timestamp_line:
            new_block = f"{i + 1}\n{timestamp_line}\n" + "\n".join(lines[2:])
            cleaned_blocks.append(new_block)

    return "\n\n".join(cleaned_blocks)

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

    # ... (A bemeneti adatok ellenőrzése változatlan) ...
    
    genai.configure(api_key=gemini_api_key)
    
    unique_id = str(uuid.uuid4())
    # ... (Logolás és fájlnevek beállítása változatlan) ...
    
    try:
        # ... (Hang letöltése változatlan) ...

        # ... (Hang feltöltése a Gemini-re változatlan) ...
        
        # 2. LÉPÉS: Leirat készítése
        logger.info("Leirat készítése...")
        model = genai.GenerativeModel('models/gemini-1.5-flash-latest')
        prompt = "Készíts egy pontos, időbélyegzett SRT formátumú feliratot ebből a hangfájlból..."
        
        response = model.generate_content([prompt, audio_file])
        
        # A nyers SRT tartalom kinyerése
        raw_srt_content = response.text.strip()
        if "```srt" in raw_srt_content:
             raw_srt_content = raw_srt_content.split("```srt")[1].split("```")[0].strip()

        # ITT HÍVJUK MEG A TISZTÍTÓ FUNKCIÓT
        srt_content = clean_and_format_srt(raw_srt_content)

        with open(srt_path, "w", encoding="utf-8-sig") as f:
            f.write(srt_content)
            
        logger.info("Leirat kész és formázva. Hangfájl törlése a Gemini szerveréről...")
        genai.delete_file(audio_file.name)

        # ... (3. és 4. lépés - Videó letöltés, kimenet előállítása változatlan) ...

    except Exception as e:
        # ... (Hibakezelés változatlan) ...
    
    finally:
        # ... (Takarítás változatlan) ...
        pass
