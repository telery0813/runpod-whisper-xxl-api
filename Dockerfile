FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

# 系統套件
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Python 套件（對齊 Faster-Whisper-XXL_r245.4）
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# RunPod handler
COPY handler.py .

CMD ["python3", "-u", "handler.py"]
