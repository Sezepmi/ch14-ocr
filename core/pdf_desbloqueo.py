"""
Desbloqueo de PDF protegidos con contraseña.

Estrategia: probar candidatos derivados del perfil/catálogo (NIF, NSS y variantes).
En la práctica, muchas nóminas PDF usan el DNI como clave de apertura.
"""

from __future__ import annotations

import re
from typing import Any


def _valor(obj: dict[str, Any], *keys: str) -> str:
    for key in keys:
        val = obj.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""


def _normalizar_doc_id(raw: str) -> str:
    return re.sub(r"[\s.\-]", "", raw or "").upper()


def variantes_clave_documento(nif: str = "", nss: str = "") -> list[str]:
    """Genera variantes habituales de contraseña a partir de NIF/NSS."""
    candidatos: list[str] = []
    vistos: set[str] = set()

    def add(raw: str) -> None:
        clave = (raw or "").strip()
        if not clave or clave in vistos:
            return
        vistos.add(clave)
        candidatos.append(clave)

    nif_norm = _normalizar_doc_id(nif)
    if nif_norm:
        add(nif_norm)
        add(nif_norm.lower())
        solo_digitos = re.sub(r"[^0-9]", "", nif_norm)
        if solo_digitos:
            add(solo_digitos)

    nss_norm = re.sub(r"[\s.\-/]", "", nss or "")
    if nss_norm:
        add(nss_norm)
        nss_digitos = re.sub(r"[^0-9]", "", nss or "")
        if nss_digitos:
            add(nss_digitos)
            if len(nss_digitos) >= 10:
                add(nss_digitos[-10:])

    return candidatos


def construir_candidatos_pdf(
    trabajadores: list[dict[str, Any]] | None = None,
    trabajador_id: str | None = None,
    pdf_password: str | None = None,
    claves_perfil: dict[str, Any] | None = None,
) -> list[str]:
    """
    Orden de prioridad:
      1. Contraseña manual (pdf_password)
      2. Claves del perfil de sesión (claves_perfil: nif/nss/dni)
      3. Trabajador indicado (trabajador_id) en catálogo
      4. Resto del catálogo
    """
    candidatos: list[str] = []
    vistos: set[str] = set()

    def add(raw: str) -> None:
        clave = (raw or "").strip()
        if not clave or clave in vistos:
            return
        vistos.add(clave)
        candidatos.append(clave)

    if pdf_password:
        add(pdf_password)

    if claves_perfil:
        for clave in variantes_clave_documento(
            _valor(claves_perfil, "nif", "dni", "NIF", "DNI"),
            _valor(claves_perfil, "nss", "NSS"),
        ):
            add(clave)

    catalogo = trabajadores or []

    if trabajador_id:
        titular = next((t for t in catalogo if t.get("id") == trabajador_id), None)
        if titular:
            for clave in variantes_clave_documento(
                _valor(titular, "nif", "dni"),
                _valor(titular, "nss"),
            ):
                add(clave)

    for trabajador in catalogo:
        if trabajador_id and trabajador.get("id") == trabajador_id:
            continue
        for clave in variantes_clave_documento(
            _valor(trabajador, "nif", "dni"),
            _valor(trabajador, "nss"),
        ):
            add(clave)

    return candidatos


def pdf_esta_cifrado(pdf_bytes: bytes) -> bool:
    try:
        import fitz

        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            return bool(doc.is_encrypted)
    except Exception:
        return False


def desbloquear_pdf_bytes(
    pdf_bytes: bytes,
    candidatos: list[str],
) -> tuple[bytes | None, list[str], list[str]]:
    """
    Devuelve (pdf_bytes_desbloqueado, advertencias, errores).
    Si no está cifrado, devuelve los bytes originales.
    """
    advertencias: list[str] = []
    errores: list[str] = []

    try:
        import fitz
    except ImportError:
        if pdf_esta_cifrado(pdf_bytes):
            return None, advertencias, [
                "PDF protegido con contraseña pero PyMuPDF (fitz) no está disponible."
            ]
        return pdf_bytes, advertencias, errores

    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            if not doc.is_encrypted:
                return pdf_bytes, advertencias, errores
    except Exception as e:
        return None, advertencias, [f"No se pudo abrir el PDF: {e}"]

    if not candidatos:
        return None, advertencias, [
            "PDF protegido con contraseña. No hay NIF/NSS en perfil o catálogo para intentar desbloqueo."
        ]

    for clave in candidatos:
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            if doc.authenticate(clave):
                desbloqueado = doc.tobytes()
                doc.close()
                advertencias.append(
                    "PDF protegido desbloqueado automáticamente con datos del perfil/catálogo."
                )
                return desbloqueado, advertencias, errores
            doc.close()
        except Exception:
            continue

    return None, advertencias, [
        "PDF protegido con contraseña: no se pudo desbloquear con NIF/NSS del perfil o catálogo. "
        "Pruebe JPG/PNG o indique la contraseña manualmente."
    ]


def preparar_pdf_para_ingesta(
    pdf_bytes: bytes,
    trabajadores: list[dict[str, Any]] | None = None,
    trabajador_id: str | None = None,
    pdf_password: str | None = None,
    claves_perfil: dict[str, Any] | None = None,
) -> tuple[bytes, list[str], list[str]]:
    """Normaliza bytes PDF (desbloqueo si aplica)."""
    candidatos = construir_candidatos_pdf(
        trabajadores=trabajadores,
        trabajador_id=trabajador_id,
        pdf_password=pdf_password,
        claves_perfil=claves_perfil,
    )
    desbloqueado, advertencias, errores = desbloquear_pdf_bytes(pdf_bytes, candidatos)
    if errores:
        return pdf_bytes, advertencias, errores
    return desbloqueado or pdf_bytes, advertencias, errores
