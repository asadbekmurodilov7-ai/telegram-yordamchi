FROM python:3.12-slim

WORKDIR /app

# ffmpeg — musiqali video story yasash uchun; DejaVu shrift — matnli story yozuvi uchun
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py story.py musiqa.py asadbek-bot-yoriqnoma.md ./
# YouTube cookies (bo'lsa) — yt-dlp uchun bot-tekshiruvni chetlab o'tishga yordam beradi
COPY www.youtube.com_cookies.tx[t] ./

CMD ["python", "bot.py"]
