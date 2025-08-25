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
    # Ezt a végpontot a kész fájlok letöltéséhez használjuk
    return send_from_directory(TMP_DIR, filename, as_attachment=True)

@app.route('/process-video', methods=['POST'])
def process_video():
    data = request.get_json()
    video_url = data.get('url')
    gemini_api_key = data.get('geminiApiKey')
    burn_in = data.get('burnIn', False)

    if not all([video_url, gemini_api_key]):
        return jsonify({"error": "Hiányzó adatok"}), 400
    
    genai.configure(api_key=gemini_api_key)
    
    unique_id = str(uuid.uuid4())
    audio_base_path = os.path.join(TMP_DIR, f"{unique_id}_audio")
    audio_path_final = audio_base_path + ".m4a"
    video_path = os.path.join(TMP_DIR, f"{unique_id}_video.mp4")
    srt_path = os.path.join(TMP_DIR, f"{unique_id}.srt")
    
    try:
        # 1. LÉPÉS: Csak a hang letöltése és konvertálása
        print("Hang letöltése és kinyerése...")
        ydl_opts_audio = {
            'format': 'bestaudio/best',
            'outtmpl': audio_base_path,
            'quiet': True,
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'm4a'}],
        }
        with yt_dlp.YoutubeDL(ydl_opts_audio) as ydl:
            info = ydl.extract_info(video_url, download=True)
            video_title = info.get('title', 'video')

        # 2. LÉPÉS: A hangfájl feltöltése a Gemini Fájl API-ra (JAVÍTVA)
        print("Hangfájl feltöltése a Gemini-re...")
        audio_file = genai.upload_file(
            path=audio_path_final,
            mime_type="audio/mp4" # Ezzel a sorral egészítettük ki
        )
        
        # 3. LÉPÉS: Leirat készítése a Geminivel a hangfájl alapján
        print("Leirat készítése...")
        model = genai.GenerativeModel('models/gemini-1.5-pro-latest')
        prompt = "Készíts egy pontos, időbélyegzett SRT formátumú magyar feliratot ebből a hangfájlból. A fordítás legyen gördülékeny, természetes, és illeszkedjen a videó kontextusához. Használj bátran szleng szótárat, valamint trágár kifejezéseket. Ne szó szerint fordíts!"
        
        response = model.generate_content([prompt, audio_file])
        
        srt_content = response.text.strip()
        if "```srt" in srt_content:
             srt_content = srt_content.split("```srt")[1].split("```")[0].strip()

        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)
            
        print("Leirat kész. Hangfájl törlése a Gemini szerveréről...")
        genai.delete_file(audio_file.name)

        # 4. LÉPÉS: A teljes videó letöltése
        print("Videó letöltése a végső feldolgozáshoz...")
        ydl_opts_video = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': video_path,
            'quiet': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts_video) as ydl:
            ydl.download([video_url])

        # 5. LÉPÉS: Kimenet előállítása a felhasználó választása alapján
        if burn_in:
            print("Felirat ráégetése...")
            output_video_path = os.path.join(TMP_DIR, f"{unique_id}_output.mp4")
            (ffmpeg.input(video_path)
             .filter('subtitles', srt_path, force_style="PrimaryColour=&H00FF00,Bold=1,FontSize=24")
             .output(output_video_path, acodec='copy')
             .run(cmd=['ffmpeg', '-loglevel', 'quiet'], overwrite_output=True))
            
            return jsonify({
                "video_url": f"/download/{os.path.basename(output_video_path)}",
                "download_url": f"/download/{os.path.basename(output_video_path)}",
            })
        else:
            print("ZIP fájl készítése...")
            zip_path = os.path.join(TMP_DIR, f"{unique_id}.zip")
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                zipf.write(video_path, os.path.basename(video_path))
                zipf.write(srt_path, os.path.basename(srt_path))

            return jsonify({
                "video_url": f"/download/{os.path.basename(video_path)}",
                "srt_url": f"/download/{os.path.basename(srt_path)}",
                "download_url": f"/download/{os.path.basename(zip_path)}",
            })

    except Exception as e:
        print(f"Hiba történt: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        # Takarítás
        files_to_clean = [audio_path_final, video_path, srt_path]
        for f in files_to_clean:
             if os.path.exists(f):
                  os.remove(f)

