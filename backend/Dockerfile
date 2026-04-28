FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PYTHONIOENCODING=utf-8 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ffmpeg \
    fonts-noto-cjk \
    fonts-wqy-zenhei \
    git \
    libmagic1 \
    libpq-dev \
    libreoffice \
    poppler-utils \
    procps \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-raganything.txt ./

RUN python -m pip install --upgrade pip && \
    python -m pip install -r requirements-raganything.txt

COPY . .

RUN mkdir -p \
    /app/uploads \
    /app/rag_storage \
    /app/rag_output \
    /app/runtime_tmp/multimodal_preprocess

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
