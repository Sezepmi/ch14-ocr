"""
PIPELINE — Orquestador del procesamiento de un documento

Flujo completo:
  1. Ingestar (extraer texto)
  2. Clasificar tipo de documento
  3. Extraer datos con el parser específico
  4. Resolver identidad
  5. Detectar duplicados (hash de contenido)
  6. Devolver DocumentoImportado

No interactúa con BD — es stateless.
"""

import hashlib
import time
from dataclasses import dataclass, field
from typing import Optional

from core.ingesta import ingestar
from core.classifier import clasificar
from core.identity import resolver_identidad, ResultadoIdentidad
from extractors import nomina, horario, sancion, vida_laboral, convenio, contrato, notificacion


# ─── TIPOS ────────────────────────────────────────────────────────────────────

@dataclass
class DocumentoImportado:
    archivo: str
    tipo_documento: str
    confianza: float
    needs_review: bool
    review_motivos: list[str]
    ocr_usado: bool
    calidad_imagen: float
    duplicado: bool
    persona: Optional[dict]
    datos: dict
    errores: list[str]
    advertencias: list[str]
    duracion_ms: int = 0


# ─── HELPERS ──────────────────────────────────────────────────────────────────

# Cache simple de hashes para detección de duplicados (in-memory, se reinicia con el servidor)
_hashes_vistos: set[str] = set()


def _es_duplicado(contenido: bytes) -> bool:
    h = hashlib.sha256(contenido).hexdigest()[:16]
    if h in _hashes_vistos:
        return True
    _hashes_vistos.add(h)
    return False


def _serializar_persona(persona: Optional[ResultadoIdentidad]) -> Optional[dict]:
    if persona is None:
        return None
    return {
        "persona_id": persona.persona_id,
        "nombre_completo": persona.nombre_completo,
        "nombre_detectado": persona.nombre_detectado,
        "confidence": persona.confidence,
        "candidatos": [
            {"id": c.id, "nombre_completo": c.nombre_completo, "score": c.score}
            for c in persona.candidatos
        ],
        "razon": persona.razon,
    }


EXTRACTORES = {
    "nomina":       nomina.extraer,
    "horario":      horario.extraer,
    "sancion":      sancion.extraer,
    "vida_laboral": vida_laboral.extraer,
    "convenio":     convenio.extraer,
    "contrato":     contrato.extraer,
    "notificacion": notificacion.extraer,
}


# ─── FUNCIÓN PRINCIPAL ────────────────────────────────────────────────────────

def procesar_documento(
    fileobj,
    nombre_archivo: str,
    trabajadores: list[dict],
    leyenda_turnos: Optional[dict] = None,
    horas_contrato: Optional[float] = None,
    tipo_hint: Optional[str] = None,
    modo: str = "strict",
    trabajador_id: Optional[str] = None,
    pdf_password: Optional[str] = None,
    claves_perfil: Optional[dict] = None,
) -> DocumentoImportado:
    """
    Procesa un documento laboral de principio a fin.

    :param fileobj:         File-like con el contenido del documento
    :param nombre_archivo:  Nombre original del archivo
    :param trabajadores:    Catálogo [{id, nombre_completo, nif, nss, iban?, variantes?}]
    :param leyenda_turnos:  Leyenda de turnos (solo para horarios)
    :param horas_contrato:  Horas mensuales del contrato (solo para horarios)
    :param tipo_hint:       Tipo forzado por el caller (opcional)
    :param modo:            'strict' | 'warn'
    :returns:               DocumentoImportado
    """
    inicio = time.time()
    errores: list[str] = []
    advertencias: list[str] = []

    fileobj.seek(0)
    contenido_bytes = fileobj.read()
    fileobj.seek(0)

    # ── 1. Ingestar ──
    ingesta = ingestar(
        fileobj,
        nombre_archivo,
        trabajadores=trabajadores,
        trabajador_id=trabajador_id,
        pdf_password=pdf_password,
        claves_perfil=claves_perfil,
    )
    errores.extend(ingesta.errores)
    advertencias.extend(ingesta.advertencias)

    if not ingesta.texto and not errores:
        errores.append("No se pudo extraer texto del documento")

    # ── 2. Clasificar ──
    clasificacion = clasificar(ingesta.texto, nombre_archivo, tipo_hint)
    tipo = clasificacion.tipo

    if tipo == "unknown":
        return DocumentoImportado(
            archivo=nombre_archivo,
            tipo_documento="unknown",
            confianza=0.0,
            needs_review=True,
            review_motivos=["tipo_desconocido"],
            ocr_usado=ingesta.ocr_usado,
            calidad_imagen=ingesta.calidad_imagen,
            duplicado=False,
            persona=None,
            datos={},
            errores=errores + [f"Tipo desconocido: {clasificacion.razon}"],
            advertencias=advertencias,
            duracion_ms=int((time.time() - inicio) * 1000),
        )

    # ── 3. Extraer datos ──
    extractor = EXTRACTORES.get(tipo)
    if extractor is None:
        errores.append(f"No hay extractor para tipo '{tipo}'")
        datos: dict = {}
        adv_extractor: list[str] = []
    else:
        try:
            kwargs = {}
            if tipo == "horario":
                if leyenda_turnos:
                    kwargs["leyenda_turnos"] = leyenda_turnos
                if horas_contrato:
                    kwargs["horas_contrato"] = horas_contrato
                kwargs["nombre_archivo"] = nombre_archivo
            if tipo == "contrato":
                kwargs["nombre_archivo"] = nombre_archivo
            if tipo == "sancion":
                kwargs["nombre_archivo"] = nombre_archivo
            datos, adv_extractor = extractor(ingesta.texto, **kwargs)
            advertencias.extend(adv_extractor)
        except Exception as e:
            datos = {}
            adv_extractor = []
            errores.append(f"Error en extractor '{tipo}': {e}")

    # ── 4. Resolver identidad ──
    persona_res = resolver_identidad(
        nombre_detectado=datos.get("nombre_completo_detectado", ""),
        trabajadores=trabajadores,
        dni_detectado=datos.get("dni_detectado", ""),
        nss_detectado=datos.get("nss_detectado", ""),
        iban_detectado=datos.get("iban_detectado", ""),
    )
    persona = _serializar_persona(persona_res)

    # ── 5. Detectar duplicado ──
    duplicado = _es_duplicado(contenido_bytes) if contenido_bytes else False

    # ── 6. Determinar needs_review ──
    needs_review = (
        clasificacion.confianza < 0.90
        or (persona_res.persona_id is None and bool(trabajadores))
        or duplicado
        or bool(errores)
        or clasificacion.es_ambiguo
    )
    review_motivos: list[str] = []
    if clasificacion.confianza < 0.90:
        review_motivos.append("confianza_baja" if clasificacion.confianza < 0.70 else "confianza_media")
    if persona_res.persona_id is None and trabajadores:
        review_motivos.append("trabajador_no_resuelto")
    if duplicado:
        review_motivos.append("duplicado")
    if clasificacion.es_ambiguo:
        review_motivos.append("clasificacion_ambigua")
    control = datos.get("control") if isinstance(datos, dict) else None
    if isinstance(control, dict):
        motivos_control = control.get("motivos_revision") or []
        if isinstance(motivos_control, list):
            for motivo in motivos_control:
                if isinstance(motivo, str) and motivo not in review_motivos:
                    review_motivos.append(motivo)
        if control.get("requiere_revision") is True:
            needs_review = True

    duracion = int((time.time() - inicio) * 1000)

    return DocumentoImportado(
        archivo=nombre_archivo,
        tipo_documento=tipo,
        confianza=clasificacion.confianza,
        needs_review=needs_review,
        review_motivos=review_motivos,
        ocr_usado=ingesta.ocr_usado,
        calidad_imagen=ingesta.calidad_imagen,
        duplicado=duplicado,
        persona=persona,
        datos=datos,
        errores=errores,
        advertencias=advertencias,
        duracion_ms=duracion,
    )
