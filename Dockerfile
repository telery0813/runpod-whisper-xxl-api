FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3 python3-pip ffmpeg git \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安裝 Python 套件
RUN pip3 install --no-cache-dir \
    runpod==1.7.7 \
    faster-whisper \
    pyannote.audio

COPY handler.py /app/handler.py

CMD ["python3", "-u", "/app/handler.py"]
