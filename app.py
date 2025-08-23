import os
import uuid
from flask import Flask, request, jsonify, send_from_directory

# AI és videófeldolgozó könyvtárak
import yt_dlp
import whisper
import google.generativeai as genai
import ffmpeg

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

WHISPER_CACHE_PATH = os.environ.get("WHISPER_HOME", "/app/.cache/whisper")
print("Whisper modell betöltése...")
whisper_model = whisper.load_model("base", download_root=WHISPER_CACHE_PATH)
print("Whisper modell betöltve.")

def format_time(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

@app.route('/process-video', methods=['POST'])
def process_video():
    data = request.get_json()
    video_url = data.get('url')
    api_key = data.get('apiKey') 

    if not video_url or not api_key:
        return jsonify({"error": "Hiányzó videó URL vagy API kulcs"}), 400

    unique_id = str(uuid.uuid4())
    audio_path = os.path.join(TMP_DIR, f"{unique_id}.m4a")
    original_srt_path = os.path.join(TMP_DIR, f"{unique_id}_orig.srt")
    translated_srt_path = os.path.join(TMP_DIR, f"{unique_id}_translated.srt")
    video_path = os.path.join(TMP_DIR, f"{unique_id}_video.mp4")
    output_video_path = os.path.join(TMP_DIR, f"{unique_id}_output.mp4")

    try:
        # 1. Hang letöltése
        ydl_opts = {'format': 'bestaudio[ext=m4a]/bestaudio', 'outtmpl': audio_path, 'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        # 2. Transzkripció
        transcribe_result = whisper_model.transcribe(audio_path, language="en", fp16=False)
        with open(original_srt_path, "w", encoding="utf-8") as f:
            for i, segment in enumerate(transcribe_result["segments"]):
                start_time = format_time(segment['start'])
                end_time = format_time(segment['end'])
                text = segment['text'].strip()
                f.write(f"{i + 1}\n{start_time} --> {end_time}\n{text}\n\n")
        
        with open(original_srt_path, "r", encoding="utf-8") as f:
            original_srt_content = f.read()

        # 3. Fordítás (Google Gemini)
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        final_prompt = TRANSLATE_PROMPT_TEMPLATE.format(srt_content=original_srt_content)
        
        response = model.generate_content(final_prompt)
        translated_srt_content = response.text
        
        with open(translated_srt_path, "w", encoding="utf-8") as f:
            f.write(translated_srt_content)

        # 4. Felirat ráégetése
        ydl_opts_video = {'format': 'best[ext=mp4]/best', 'outtmpl': video_path, 'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts_video) as ydl:
            info = ydl.extract_info(video_url, download=True)
            video_title = info.get('title', 'video')
            safe_filename = "".join([c for c in video_title if c.isalpha() or c.isdigit() or c==' ']).rstrip() + ".mp4"

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
        for f in [audio_path, original_srt_path, translated_srt_path, video_path, output_video_path]:
            if f and os.path.exists(f):
                os.remove(f)

