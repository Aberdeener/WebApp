FROM python:3-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg

RUN pip install yt-dlp flask bs4 requests Pillow

RUN mkdir /app

COPY app.py raphson.png script.js style.css /app/
COPY ./templates /app/templates

WORKDIR /app

ENTRYPOINT ["flask", "run", "--host", "0.0.0.0"]
