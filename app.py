"""
MICROSERVICIO OCR — Punto de entrada Flask

Endpoints:
  POST /procesar          → un documento
  POST /procesar/batch    → hasta 10 documentos
  GET  /health            → liveness probe
  GET  /health/ocr        → verifica que EasyOCR esté disponible
"""

import io
import json
import time
from dataclasses import asdict
from typing import Optional

from flask import Flask, request, jsonify
from flask_cors import CORS

import config
from core.pipeline import procesar_documento

app = Flask(__name__)
CORS(app, origins="*")  # En prod: restringir a dominio appPlus

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _parse_json_field(field_name: str, default=None):
    """Lee un campo JSON de multipart/form-data."""
    raw = request.form.get(field_name)
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return default


def _documento_a_dict(doc) -> dict:
    """Convierte DocumentoImportado a dict serializable."""
    return {
        "archivo": doc.archivo,
        "tipo_documento": doc.tipo_documento,
        "confianza": doc.confianza,
        "needs_review": doc.needs_review,
        "review_motivos": doc.review_motivos,
        "ocr_usado": doc.ocr_usado,
        "calidad_imagen": doc.calidad_imagen,
        "duplicado": doc.duplicado,
        "persona": doc.persona,
        "datos": doc.datos,
        "errores": doc.errores,
        "advertencias": doc.advertencias,
        "duracion_ms": doc.duracion_ms,
    }


# ─── ENDPOINTS ────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "servicio": "ocr-service",
        "version": "1.0.0",
        "ocr_engine": config.OCR_ENGINE,
    })


@app.get("/health/ocr")
def health_ocr():
    """Verifica proveedores OCR disponibles sin cargar modelos pesados."""
    try:
        import easyocr
        easyocr_ok = True
    except ImportError:
        easyocr_ok = False

    try:
        import pytesseract
        tesseract_ok = True
    except ImportError:
        tesseract_ok = False

    try:
        import paddleocr
        paddleocr_ok = True
    except ImportError:
        paddleocr_ok = False

    ok = (
        (config.OCR_ENGINE == "easyocr" and easyocr_ok) or
        (config.OCR_ENGINE == "tesseract" and tesseract_ok) or
        (config.OCR_ENGINE == "paddleocr" and paddleocr_ok) or
        (config.OCR_ENGINE == "auto" and (easyocr_ok or tesseract_ok or paddleocr_ok))
    )

    return jsonify({
        "ok": ok,
        "engine": config.OCR_ENGINE,
        "easyocr": easyocr_ok,
        "tesseract": tesseract_ok,
        "paddleocr": paddleocr_ok,
        "gpu": config.OCR_GPU,
    }), 200 if ok else 503


@app.post("/procesar")
def procesar():
    """
    Procesa un único documento.

    Multipart form-data:
      file           : archivo (PDF/Excel/imagen)
      trabajadores   : JSON array de {id, nombre_completo, nif, nss, iban?, variantes?}
      leyenda_turnos : JSON dict (opcional, para horarios)
      horas_contrato : float (opcional, para horarios)
      tipo_hint      : string (opcional)
      trabajador_id  : UUID trabajador prioritario para claves PDF (opcional)
      pdf_password   : contraseña manual PDF (opcional)
      claves_perfil  : JSON {nif, nss} del perfil de sesión (opcional)
      modo           : 'strict' | 'warn' (opcional, default 'strict')
    """
    if "file" not in request.files:
        return jsonify({"ok": False, "error": {"codigo": "SIN_ARCHIVO", "mensaje": "Se requiere el campo 'file'"}}), 400

    archivo = request.files["file"]
    nombre_archivo = archivo.filename or "documento"

    # Validar tamaño
    fileobj = io.BytesIO(archivo.read())
    fileobj.seek(0, 2)
    size_mb = fileobj.tell() / (1024 * 1024)
    fileobj.seek(0)
    if size_mb > config.MAX_FILE_SIZE_MB:
        return jsonify({
            "ok": False,
            "error": {
                "codigo": "ARCHIVO_DEMASIADO_GRANDE",
                "mensaje": f"El archivo supera el límite de {config.MAX_FILE_SIZE_MB}MB",
            },
        }), 413

    trabajadores = _parse_json_field("trabajadores", [])
    leyenda_turnos = _parse_json_field("leyenda_turnos")
    horas_contrato_raw = request.form.get("horas_contrato")
    horas_contrato = float(horas_contrato_raw) if horas_contrato_raw else None
    tipo_hint = request.form.get("tipo_hint")
    trabajador_id = request.form.get("trabajador_id") or None
    pdf_password = request.form.get("pdf_password") or None
    claves_perfil = _parse_json_field("claves_perfil")
    modo = request.form.get("modo", config.MODO_DEFECTO)

    try:
        doc = procesar_documento(
            fileobj=fileobj,
            nombre_archivo=nombre_archivo,
            trabajadores=trabajadores,
            leyenda_turnos=leyenda_turnos,
            horas_contrato=horas_contrato,
            tipo_hint=tipo_hint,
            modo=modo,
            trabajador_id=trabajador_id,
            pdf_password=pdf_password,
            claves_perfil=claves_perfil,
        )
        return jsonify({
            "ok": True,
            "resultado": _documento_a_dict(doc),
            "duracion_ms": doc.duracion_ms,
        })
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": {"codigo": "ERROR_PROCESAMIENTO", "mensaje": str(e)},
        }), 500


@app.post("/procesar/batch")
def procesar_batch():
    """
    Procesa hasta MAX_BATCH_SIZE documentos en lote.

    Multipart form-data:
      files[]        : archivos (múltiples)
      trabajadores   : JSON array
      leyenda_turnos : JSON dict (opcional)
      modo           : 'strict' | 'warn'
    """
    archivos = request.files.getlist("files[]")
    if not archivos:
        return jsonify({"ok": False, "error": {"codigo": "SIN_ARCHIVOS", "mensaje": "Se requieren archivos en 'files[]'"}}), 400
    if len(archivos) > config.MAX_BATCH_SIZE:
        return jsonify({
            "ok": False,
            "error": {
                "codigo": "DEMASIADOS_ARCHIVOS",
                "mensaje": f"Máximo {config.MAX_BATCH_SIZE} archivos por lote",
            },
        }), 400

    trabajadores = _parse_json_field("trabajadores", [])
    leyenda_turnos = _parse_json_field("leyenda_turnos")
    trabajador_id = request.form.get("trabajador_id") or None
    pdf_password = request.form.get("pdf_password") or None
    claves_perfil = _parse_json_field("claves_perfil")
    modo = request.form.get("modo", config.MODO_DEFECTO)

    inicio = time.time()
    resultados = []
    errores_count = 0
    needs_review_count = 0
    duplicados_count = 0

    for archivo in archivos:
        nombre_archivo = archivo.filename or "documento"
        fileobj = io.BytesIO(archivo.read())
        try:
            doc = procesar_documento(
                fileobj=fileobj,
                nombre_archivo=nombre_archivo,
                trabajadores=trabajadores,
                leyenda_turnos=leyenda_turnos,
                modo=modo,
                trabajador_id=trabajador_id,
                pdf_password=pdf_password,
                claves_perfil=claves_perfil,
            )
            resultados.append(_documento_a_dict(doc))
            if doc.needs_review:
                needs_review_count += 1
            if doc.duplicado:
                duplicados_count += 1
            if doc.errores:
                errores_count += 1
        except Exception as e:
            resultados.append({
                "archivo": nombre_archivo,
                "tipo_documento": "unknown",
                "confianza": 0.0,
                "needs_review": True,
                "review_motivos": ["error_procesamiento"],
                "ocr_usado": False,
                "calidad_imagen": 0.0,
                "duplicado": False,
                "persona": None,
                "datos": {},
                "errores": [str(e)],
                "advertencias": [],
                "duracion_ms": 0,
            })
            errores_count += 1

    duracion_total = int((time.time() - inicio) * 1000)

    return jsonify({
        "ok": True,
        "resultados": resultados,
        "resumen": {
            "total": len(archivos),
            "procesados": len(resultados),
            "needs_review": needs_review_count,
            "duplicados": duplicados_count,
            "errores": errores_count,
            "duracion_total_ms": duracion_total,
        },
    })


# ─── ENTRY POINT ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
