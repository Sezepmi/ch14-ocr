"""
IDENTIDAD — Resolución de trabajador a partir de datos del documento

Puerto del resolutor-identidad.ts usando rapidfuzz.
Prioridad: DNI > NSS > IBAN > fuzzy nombre
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from rapidfuzz import fuzz


# ─── TIPOS ────────────────────────────────────────────────────────────────────

@dataclass
class Candidato:
    id: str
    nombre_completo: str
    score: float


@dataclass
class ResultadoIdentidad:
    persona_id: Optional[str]
    nombre_completo: Optional[str]
    nombre_detectado: Optional[str]
    confidence: float
    candidatos: list[Candidato] = field(default_factory=list)
    razon: str = ""


# ─── CONSTANTES ───────────────────────────────────────────────────────────────

UMBRAL_ALTO = 88
UMBRAL_BAJO = 65


# ─── NORMALIZACIÓN ────────────────────────────────────────────────────────────

def _normalizar_dni(raw: str) -> str:
    if not raw:
        return ""
    return re.sub(r"[\s.\-]", "", raw).upper()


def _normalizar_nss(raw: str) -> str:
    if not raw:
        return ""
    return re.sub(r"[\s.\-/]", "", raw)


def _normalizar_iban(raw: str) -> str:
    if not raw:
        return ""
    return re.sub(r"\s", "", raw).upper()


def _normalizar_nombre(texto: str) -> str:
    import unicodedata
    sin_tildes = unicodedata.normalize("NFD", texto)
    sin_tildes = "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", sin_tildes.lower())).strip()


def _valor(trabajador: dict, *claves: str) -> str:
    for clave in claves:
        valor = trabajador.get(clave)
        if valor is not None:
            return str(valor)
    return ""


def _id_trabajador(trabajador: dict) -> str:
    return _valor(trabajador, "id", "trabajador_id", "trabajadorId")


def _nombre_trabajador(trabajador: dict) -> str:
    return _valor(trabajador, "nombre_completo", "nombreCompleto", "nombre")


def _variantes_nombre_detectado(nombre: str) -> list[str]:
    """Variantes para nombres legales en mayúsculas (APELLIDOS NOMBRE / NOMBRE APELLIDOS)."""
    partes = [p for p in nombre.split() if p]
    variantes: list[str] = []
    if len(partes) >= 3:
        variantes.append(_normalizar_nombre(f"{partes[-1]} {' '.join(partes[:-1])}"))
        variantes.append(_normalizar_nombre(f"{' '.join(partes[1:])} {partes[0]}"))
    return variantes


def _variantes(trabajador: dict) -> list[str]:
    nombre = _nombre_trabajador(trabajador)
    variantes = [_normalizar_nombre(nombre)]
    partes = nombre.split()
    if len(partes) >= 2:
        mitad = len(partes) // 2
        apellidos = " ".join(partes[:mitad])
        nombre_propio = " ".join(partes[mitad:])
        variantes.append(_normalizar_nombre(f"{apellidos} {nombre_propio}"))
        variantes.append(_normalizar_nombre(f"{nombre_propio} {apellidos}"))
    for v in trabajador.get("variantes", []):
        variantes.append(_normalizar_nombre(v))
    return list(dict.fromkeys(variantes))  # dedup preservando orden


# ─── FUNCIÓN PRINCIPAL ────────────────────────────────────────────────────────

def resolver_identidad(
    nombre_detectado: str,
    trabajadores: list[dict],
    dni_detectado: str = "",
    nss_detectado: str = "",
    iban_detectado: str = "",
) -> ResultadoIdentidad:
    """
    Resuelve a qué trabajador pertenece un documento.

    :param nombre_detectado:  Nombre extraído del documento
    :param trabajadores:      Lista de dicts {id, nombre_completo, nif, nss, iban?, variantes?}
    :param dni_detectado:     DNI/NIF extraído (opcional)
    :param nss_detectado:     NSS extraído (opcional)
    :param iban_detectado:    IBAN extraído (opcional)
    """
    if not any([nombre_detectado, dni_detectado, nss_detectado, iban_detectado]):
        return ResultadoIdentidad(None, None, None, 0.0, razon="sin datos de identidad")

    # ── DNI exacto ──
    if dni_detectado:
        dni_norm = _normalizar_dni(dni_detectado)
        for t in trabajadores:
            if _normalizar_dni(_valor(t, "nif", "dni", "dniDetectado", "dni_detectado")) == dni_norm:
                return ResultadoIdentidad(
                    _id_trabajador(t), _nombre_trabajador(t), nombre_detectado or None,
                    0.99, razon=f"DNI exacto: {dni_detectado}"
                )

    # ── NSS exacto ──
    if nss_detectado:
        nss_norm = _normalizar_nss(nss_detectado)
        for t in trabajadores:
            if _normalizar_nss(_valor(t, "nss", "naf", "nssDetectado", "nss_detectado")) == nss_norm:
                return ResultadoIdentidad(
                    _id_trabajador(t), _nombre_trabajador(t), nombre_detectado or None,
                    0.99, razon=f"NSS exacto: {nss_detectado}"
                )

    # ── IBAN exacto ──
    if iban_detectado:
        iban_norm = _normalizar_iban(iban_detectado)
        for t in trabajadores:
            iban_trabajador = _valor(t, "iban", "ibanDetectado", "iban_detectado")
            if iban_trabajador and _normalizar_iban(iban_trabajador) == iban_norm:
                return ResultadoIdentidad(
                    _id_trabajador(t), _nombre_trabajador(t), nombre_detectado or None,
                    0.97, razon=f"IBAN exacto: {iban_detectado}"
                )

    # ── Fuzzy nombre ──
    if not nombre_detectado:
        return ResultadoIdentidad(None, None, None, 0.0, razon="nombre vacío, sin match por documento")

    if not trabajadores:
        return ResultadoIdentidad(None, None, nombre_detectado, 0.0, razon="catálogo vacío")

    nombre_norm = _normalizar_nombre(nombre_detectado)
    if not nombre_norm:
        return ResultadoIdentidad(None, None, nombre_detectado, 0.0, razon="nombre vacío tras normalización")

    variantes_detectado = [_normalizar_nombre(v) for v in _variantes_nombre_detectado(nombre_detectado)]
    variantes_detectado.append(nombre_norm)
    variantes_detectado = list(dict.fromkeys(v for v in variantes_detectado if v))

    candidatos: list[Candidato] = []
    for t in trabajadores:
        variantes = _variantes(t)
        mejor_score = max(
            max(fuzz.token_set_ratio(detectado, v) for v in variantes)
            for detectado in variantes_detectado
        )
        candidatos.append(Candidato(_id_trabajador(t), _nombre_trabajador(t), mejor_score))

    candidatos.sort(key=lambda c: c.score, reverse=True)
    top = candidatos[0]
    es_ambiguo = (
        len(candidatos) > 1
        and candidatos[1].score > 0
        and top.score - candidatos[1].score < 8
    )
    confidence = round(top.score / 100, 3)

    if top.score >= UMBRAL_ALTO and not es_ambiguo:
        return ResultadoIdentidad(
            top.id, top.nombre_completo, nombre_detectado,
            confidence, candidatos[:2],
            razon=f"fuzzy score={top.score:.1f}",
        )

    if top.score >= UMBRAL_BAJO:
        return ResultadoIdentidad(
            None, None, nombre_detectado,
            confidence, candidatos[:3],
            razon=f"candidato propuesto (score={top.score:.1f}, {'ambiguo' if es_ambiguo else 'score insuficiente'})",
        )

    return ResultadoIdentidad(
        None, None, nombre_detectado,
        confidence, candidatos[:2],
        razon=f"score bajo ({top.score:.1f}), no se vincula",
    )
