# 1. Alapkép kiválasztása
FROM python:3.11-slim

# 2. Környezeti változók beállítása
ENV PYTHONUNBUFFERED=1 \
    PORT=8080 \
    WHISPER_HOME=/app/.cache/whisper

# 3. Munkakönyvtár beállítása a konténeren belül
WORKDIR /app

# 4. Rendszerfüggőségek telepítése (FFmpeg)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# 5. Python függőségek telepítése
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Whisper modell letöltése a build során ("besütés")
RUN python -c "import whisper; whisper.load_model('base', download_root='${WHISPER_HOME}')"

# 7. Biztonsági beállítás: Felhasználóra váltás, hogy ne rootként fusson az app
RUN useradd --create-home --shell /bin/bash appuser
USER appuser

# 8. Alkalmazás kódjának másolása
COPY . .

# 9. Konténer futtatási parancsa
CMD ["gunicorn", "--bind", "0.0.0.0:${PORT}", "--workers", "1", "--threads", "8", "--timeout", "0", "app:app"]

