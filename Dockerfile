FROM python:3.11-slim

# ─── Sistema ────────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    ghostscript \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-spa \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ─── Dependencias Python ─────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ─── Precargar modelo EasyOCR (evita cold start) ─────────────────────────────
RUN python -c "import easyocr; easyocr.Reader(['es'], gpu=False, verbose=False)" || true

# ─── Código ──────────────────────────────────────────────────────────────────
COPY . .

# ─── Arranque ────────────────────────────────────────────────────────────────
ENV HOST=0.0.0.0
ENV PORT=5050
ENV DEBUG=false

EXPOSE 5050

# Render/Railway inyectan PORT en runtime; 1 worker reduce RAM (EasyOCR).
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-5050} --workers 1 --timeout 120 --graceful-timeout 30 app:app"]
