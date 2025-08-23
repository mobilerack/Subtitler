import os
import uuid
from flask import Flask, request, jsonify, send_from_directory
import yt_dlp
import google.generativeai as genai
import ffmpeg
from speechmatics.models import ConnectionSettings
from speechmatics.batch_client import BatchClient

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

@app.route('/process-video', methods=['POST'])
def process_video():
    data = request.get_json()
    video_url = data.get('url')
    speechmatics_api_key = data.get('speechmaticsApiKey')
    gemini_api_key = data.get('geminiApiKey')

    if not all([video_url, speechmatics_api_key, gemini_api_key]):
        return jsonify({"error": "Hiányzó adatok"}), 400
    
    unique_id = str(uuid.uuid4())
    translated_srt_path = os.path.join(TMP_DIR, f"{unique_id}_translated.srt")
    video_path = os.path.join(TMP_DIR, f"{unique_id}_video.mp4")
    output_video_path = os.path.join(TMP_DIR, f"{unique_id}_output.mp4")
    
    try:
        # 1. Lépés: Link és nyelv kinyerése
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(video_url, download=False)
            direct_url = info['url']
            language = info.get('language', 'auto')
            video_title = info.get('title', 'video')
            safe_filename = "".join([c for c in video_title if c.isalpha() or c.isdigit() or c==' ']).rstrip() + ".mp4"

        # 2. Lépés: Átirat kérése a Speechmatics API-tól
        settings = ConnectionSettings(
            url="https://asr.api.speechmatics.com/v2",
            auth_token=speechmatics_api_key,
        )
        
        with BatchClient(settings) as client:
            # JAVÍTVA: A helyes argumentumnév használata
            transcription_config = {
                "language": language,
                "output_format": "srt"
            }
            fetch_data = {
                "url": direct_url
            }

            job_id = client.submit_job(
                fetch_data=fetch_data,
                transcription_config=transcription_config
            )

            print(f"Speechmatics job elküldve, ID: {job_id}")
            original_srt_content = client.get_job_result(job_id, timeout=900)

        # 3. Lépés: Fordítás a Geminivel
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        final_prompt = TRANSLATE_PROMPT_TEMPLATE.format(srt_content=original_srt_content)
        
        gemini_response = model.generate_content(final_prompt)
        translated_srt_content = gemini_response.text
        
        with open(translated_srt_path, "w", encoding="utf-8") as f:
            f.write(translated_srt_content)

        # 4. Lépés: Felirat ráégetése
        ydl_opts_video = {'format': 'best[ext=mp4]/best', 'outtmpl': video_path, 'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts_video) as ydl:
            ydl.download([video_url])

        (
            ffmpeg
            .input(video_path)
            .filter('subtitles', translated_srt_path, force_style="PrimaryColour=&H00FF00,Bold=1,FontSize=24")
            .output(output_video_path, acodec='copy')
            .run(cmd=['ffmpeg', '-loglevel', 'quiet'], overwrite_output=True)
        )

        return send_from_directory(
            TMP_DIR,
            os.path.basename(output_video_path),
            as_attachment=True,
            download_name=safe_filename
        )

    except Exception as e:
        print(f"Hiba történt: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        # Takarítás
        for f in [translated_srt_path, video_path, output_video_path]:
            if f and os.path.exists(f):
                os.remove(f)
