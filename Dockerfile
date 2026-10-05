# Engine image for the Google VM: vm/ worker + engines/{reels,motion}, one Python env.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg fonts-noto fonts-noto-color-emoji fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY engines/reels/requirements.txt engines/reels/requirements.txt
COPY engines/motion/requirements.txt engines/motion/requirements.txt
COPY vm/requirements.txt vm/requirements.txt
RUN pip install -r engines/reels/requirements.txt -r engines/motion/requirements.txt -r vm/requirements.txt \
    && playwright install --with-deps chromium

COPY engines engines
COPY vm vm

WORKDIR /app/vm
CMD ["python", "main.py"]
