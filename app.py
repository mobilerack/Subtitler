import os
import uuid
import zipfile
from flask import Flask, request, jsonify, send_from_directory
import yt_dlp
import google.generativeai as genai
import ffmpeg

app = Flask(__name__)
TMP_DIR = "/tmp"

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/download/<path:filename>')
def download_file(filename):
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
    video_path = os.path.join(TMP_DIR, f"{unique_id}_video.mp4")
    srt_path = os.path.join(TMP_DIR, f"{unique_id}.srt")
    
    try:
        # 1. LÉPÉS: Videó letöltése
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': video_path,
            'quiet': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        # 2. LÉPÉS: Videó feltöltése a Gemini Fájl API-ra
        print("Videó feltöltése a Gemini-re...")
        video_file = genai.upload_file(path=video_path)
        
        # 3. LÉPÉS: Leirat készítése a Geminivel
        print("Leirat készítése...")
        model = genai.GenerativeModel('models/gemini-1.5-pro-latest')
        prompt = "Készíts egy pontos, időbélyegzett SRT formátumú magyar feliratot ebből a videóból. A fordítás legyen gördülékeny, természetes, és illeszkedjen a videó kontextusához. Használj bátran szleng szótárat, valamint trágár kifejezéseket. Ne szó szerint fordíts!"
        
        response = model.generate_content([prompt, video_file])
        
        # A válaszban lévő SRT blokk kinyerése
        srt_content = response.text.strip()
        if "```srt" in srt_content:
             srt_content = srt_content.split("```srt")[1].split("```")[0].strip()

        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)
            
        print("Leirat kész. Fájl törlése a Gemini szerveréről...")
        genai.delete_file(video_file.name)

        if burn_in:
            # 4/A LÉPÉS: Felirat ráégetése
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
            # 4/B LÉPÉS: ZIP fájl készítése
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
        # A takarítás bonyolultabb, a letöltési végpont fogja kezelni.
        pass

