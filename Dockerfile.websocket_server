FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system packages needed for audio, video and building some wheels
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        git \
        ffmpeg \
        libsndfile1 \
        libsndfile1-dev \
        libportaudio2 \
        portaudio19-dev \
        libpulse-dev \
        libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install. Filter out Windows-only packages like pywin32/pyreadline3
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip setuptools wheel \
    && (grep -vE '^(pywin32|pyreadline3)' requirements.txt > requirements-linux.txt || true) \
    && pip install --no-cache-dir -r requirements-linux.txt

# Copy app sources
COPY . /app

# Default command: run the project entrypoint
CMD ["python", "app.py"]
