"""
Configuración del microservicio OCR.
Lee variables de entorno con valores por defecto seguros.
"""

import os

# ─── SERVIDOR ─────────────────────────────────────────────────────────────────

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "5050"))
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# ─── LÍMITES ──────────────────────────────────────────────────────────────────

MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "20"))
MAX_BATCH_SIZE = int(os.getenv("MAX_BATCH_SIZE", "10"))
OCR_TIMEOUT_SECS = int(os.getenv("OCR_TIMEOUT_SECS", "60"))

# ─── OCR ──────────────────────────────────────────────────────────────────────

OCR_LANGUAGES = os.getenv("OCR_LANGUAGES", "es").split(",")
OCR_GPU = os.getenv("OCR_GPU", "false").lower() == "true"
OCR_MIN_QUALITY = float(os.getenv("OCR_MIN_QUALITY", "0.4"))
OCR_ENGINE = os.getenv("OCR_ENGINE", "easyocr").lower()  # easyocr | tesseract | paddleocr | auto
TESSERACT_LANG = os.getenv("TESSERACT_LANG", "spa")
MIN_TEXTO_PDF_COMPLETO = int(os.getenv("MIN_TEXTO_PDF_COMPLETO", "350"))
OCR_MAX_PAGINAS = int(os.getenv("OCR_MAX_PAGINAS", "12"))

# ─── VALIDACIÓN ───────────────────────────────────────────────────────────────

MODO_DEFECTO = os.getenv("MODO_DEFECTO", "strict")  # strict | warn
