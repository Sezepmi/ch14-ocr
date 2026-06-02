"""
EXTRACTOR — Notificaciones / escritos laborales
(mutua, INSS, empresa, resoluciones administrativas, etc.)
"""

import re
from typing import Optional

MESES = {
    "enero": "01", "febrero": "02", "marzo": "03", "abril": "04", "mayo": "05", "junio": "06",
    "julio": "07", "agosto": "08", "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12",
}

TEMAS = [
    (r"determinaci[oó]n\s+de\s+la\s+contingencia|contingencia\s+com[uú]n|accidente\s+de\s+trabajo", "contingencia"),
    (r"parte\s+de\s+baja|baja\s+m[eé]dica|proceso\s+m[eé]dico", "baja-medica"),
    (r"reclamaci[oó]n", "reclamacion"),
    (r"resoluci[oó]n|le\s+informamos|notificaci[oó]n", "comunicacion"),
    (r"mutua\s+colaboradora|mutua\s+intercomarcal", "mutua"),
    (r"instituto\s+nacional\s+de\s+la\s+seguridad\s+social|inss|tgss", "inss"),
]


def _fecha(texto: str) -> Optional[str]:
    m = re.search(r"\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})\b", texto)
    if m:
        d, mo, y = m.group(1).zfill(2), m.group(2).zfill(2), m.group(3)
        if int(mo) <= 12:
            return f"{y}-{mo}-{d}"

    m2 = re.search(
        r"(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+de\s+(\d{4})",
        texto, re.IGNORECASE
    )
    if m2:
        mes = MESES.get(m2.group(2).lower())
        if mes:
            return f"{m2.group(3)}-{mes}-{m2.group(1).zfill(2)}"

    m3 = re.search(r"Fecha:\s*(\d{4})[./-](\d{2})[./-](\d{2})", texto, re.IGNORECASE)
    if m3:
        return f"{m3.group(1)}-{m3.group(2)}-{m3.group(3)}"

    return None


def _fecha_referencia(texto: str) -> Optional[str]:
    m = re.search(
        r"(?:iniciado|con\s+fecha|desde)\s+el\s+(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+de\s+(\d{4})",
        texto, re.IGNORECASE
    )
    if m:
        mes = MESES.get(m.group(2).lower())
        if mes:
            return f"{m.group(3)}-{mes}-{m.group(1).zfill(2)}"
    return None


def _remitente(texto: str) -> Optional[str]:
    lineas = [l.strip() for l in texto.splitlines() if l.strip()]
    for linea in lineas[:12]:
        if re.search(r"mutua|seguridad\s+social|empresa|instituto\s+nacional", linea, re.IGNORECASE):
            return re.sub(r"\s+", " ", linea)[:120]
    return None


def _destinatario(texto: str) -> Optional[str]:
    m = re.search(
        r"\n\s*([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s.'-]{8,60})\n(?:CL|C/|CALLE|AVDA|AV\.|PLAZA)",
        texto
    )
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()
    m2 = re.search(r"Apreciad[oa]\s+Sr[a.]?\s+([^,\n]{3,40})", texto, re.IGNORECASE)
    if m2:
        return m2.group(1).strip()
    return None


def _tema(texto: str) -> str:
    for patron, slug in TEMAS:
        if re.search(patron, texto, re.IGNORECASE):
            return slug
    return "general"


def extraer(texto: str) -> tuple[dict, list[str]]:
    advertencias: list[str] = []

    dni_m = re.search(r"\b([0-9]{8}[A-Z]|[XYZ][0-9]{7}[A-Z])\b", texto, re.IGNORECASE)
    fecha = _fecha(texto)
    if not fecha:
        advertencias.append("No se detectó fecha clara del escrito")

    datos = {
        "tipo_documento": "notificacion",
        "nombre_completo_detectado": _destinatario(texto),
        "dni_detectado": dni_m.group(1).upper() if dni_m else None,
        "fecha": fecha,
        "fecha_documento": fecha,
        "fecha_referencia": _fecha_referencia(texto),
        "remitente": _remitente(texto),
        "tema": _tema(texto),
        "asunto": _tema(texto),
    }

    return datos, advertencias
