"""
EXTRACTOR — Convenios colectivos
"""

import re
from typing import Optional


PROTOCOLOS = [
    (r"protocolo\s+(?:de\s+)?acoso\s+sexual",      "Protocolo acoso sexual"),
    (r"protocolo\s+(?:de\s+)?acoso\s+laboral",      "Protocolo acoso laboral"),
    (r"plan\s+de\s+igualdad",                       "Plan de igualdad"),
    (r"teletrabajo|trabajo\s+remoto",               "Teletrabajo"),
    (r"formaci[oó]n\s+continua",                    "Formación continua"),
    (r"prevenci[oó]n\s+de\s+riesgos",               "Prevención de riesgos laborales"),
    (r"conciliaci[oó]n\s+familiar",                 "Conciliación familiar"),
]


def extraer(texto: str) -> tuple[dict, list[str]]:
    advertencias: list[str] = []

    nombre_m = re.search(r"convenio\s+colectivo\s+(?:de\s+(?:la\s+|el\s+)?)?([^\n\r,]{5,80})", texto, re.IGNORECASE)
    nombre = nombre_m.group(1).strip() if nombre_m else None

    sector_m = re.search(r"sector\s+(?:de\s+)?([^\n\r,]{5,60})", texto, re.IGNORECASE)
    ambito_m = re.search(r"[aá]mbito\s+(?:de\s+aplicaci[oó]n|funcional)[:\s]+([^\n\r]{5,80})", texto, re.IGNORECASE)

    codigo_m = re.search(r"c[oó]digo\s+(?:de\s+)?convenio[:\s]+(\d{12,15})", texto, re.IGNORECASE)

    boletin_m = re.search(r"\b(boe|dogc|bopv|bocm|borm|boja|doga)\b", texto, re.IGNORECASE)
    boletin = boletin_m.group(1).upper() if boletin_m else None

    # Vigencia
    vigencia_m = re.search(r"\b(20\d{2})\s*[-/]\s*(20\d{2})\b", texto)
    fecha_vig_inicio = f"{vigencia_m.group(1)}-01-01" if vigencia_m else None
    fecha_vig_fin = f"{vigencia_m.group(2)}-12-31" if vigencia_m else None

    # Periodicidad revisión
    periodo_m = re.search(r"(?:revisi[oó]n\s+salarial|periodicidad)[:\s]+([^\n\r,]{5,50})", texto, re.IGNORECASE)

    # Protocolos
    protocolos = [nombre for patron, nombre in PROTOCOLOS if re.search(patron, texto, re.IGNORECASE)]

    # Advertencias
    if not fecha_vig_inicio:
        advertencias.append("No se detectó la vigencia del convenio")
    if not boletin:
        advertencias.append("No se detectó referencia a boletín oficial")
    if not nombre:
        advertencias.append("No se identificó el nombre del convenio")

    datos = {
        "codigo": codigo_m.group(1) if codigo_m else None,
        "nombre": nombre,
        "sector": sector_m.group(1).strip() if sector_m else None,
        "ambito": ambito_m.group(1).strip() if ambito_m else None,
        "boletin_oficial": boletin,
        "fecha_vigencia_inicio": fecha_vig_inicio,
        "fecha_vigencia_fin": fecha_vig_fin,
        "periodicidad_vigilancia": periodo_m.group(1).strip() if periodo_m else None,
        "protocolos_detectados": protocolos,
    }

    return datos, advertencias
