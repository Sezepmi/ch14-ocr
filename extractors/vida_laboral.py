"""
EXTRACTOR — Vida laboral (TGSS)
"""

import re
from typing import Optional


def _normalizar_fecha(raw: str) -> Optional[str]:
    m = re.search(r"(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})", raw)
    if m:
        d, mo, y = m.group(1).zfill(2), m.group(2).zfill(2), m.group(3)
        if int(mo) <= 12:
            return f"{y}-{mo}-{d}"
    return None


def _limpiar_nombre(raw: str | None) -> Optional[str]:
    if not raw:
        return None
    nombre = re.sub(r"\s+", " ", raw)
    nombre = re.split(r"\s*,?\s*nacido/?a?\b", nombre, maxsplit=1, flags=re.IGNORECASE)[0]
    nombre = nombre.strip(" ,.-")
    if re.search(r"N[ºO]\s*SEGURIDAD|DOCUMENTO IDENTIFICATIVO|REFERENCIAS|INFORME", nombre, re.IGNORECASE):
        return None
    return nombre or None


def _extraer_titular(texto: str) -> Optional[str]:
    patrones = [
        r"resulta\s+que\s+D/Dª\s*\n\s*([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ ,.'-]{5,80})",
        r"DATOS\s+IDENTIFICATIVOS\s+NOMBRE\s+Y\s+APELLIDOS.*?\n\s*([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ ,.'-]{5,80})\s+\d{9,14}\s+D\.?N\.?I\.?",
        r"\n\s*([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ ,.'-]{5,80})\s+\d{9,14}\s+D\.?N\.?I\.?\s+[0-9A-Z]{7,12}",
    ]
    for patron in patrones:
        m = re.search(patron, texto, re.IGNORECASE | re.DOTALL)
        nombre = _limpiar_nombre(m.group(1) if m else None)
        if nombre:
            return nombre
    return None


def _extraer_total_dias(texto: str) -> Optional[int]:
    patrones = [
        r"total\s+de\s*\n?\s*([\d.]+)\s*d[ií]as",
        r"ha\s+figurado.*?durante\s+un\s+total\s+de.*?([\d.]+)\s*d[ií]as",
        r"\b([\d.]+)\s*d[ií]as\s+\d+\s+meses",
        r"d[ií]as\s+(?:efectivamente\s+)?computables?[:\s]+([\d.]+)",
    ]
    for patron in patrones:
        m = re.search(patron, texto, re.IGNORECASE | re.DOTALL)
        if m:
            return int(m.group(1).replace(".", ""))
    return None


def _unir_lineas_registro(lineas: list[str]) -> list[str]:
    registros: list[str] = []
    actual = ""
    for linea in lineas:
        limpia = re.sub(r"\s+", " ", linea).strip()
        if not limpia:
            continue
        if re.match(r"^(GENERAL|AUT[ÓO]NOMO|RETA|AGRARIO|MAR)\b", limpia, re.IGNORECASE):
            if actual:
                registros.append(actual)
            actual = limpia
            continue
        if actual:
            actual = f"{actual} {limpia}"
    if actual:
        registros.append(actual)
    return registros


def _es_empresa_ruido(empresa: str) -> bool:
    empresa_norm = re.sub(r"\s+", " ", empresa).strip().upper()
    return bool(
        not empresa_norm
        or empresa_norm == "EMPRESA DESCONOCIDA"
        or empresa_norm == "ESTE"
        or empresa_norm.startswith("ESTE DOCUMENTO")
        or "REFERENCIA ELECTR" in empresa_norm
        or re.fullmatch(r"[A-Z0-9]{10,}", empresa_norm)
        or len(empresa_norm) > 120
        or re.search(r"\b\d{11}\b|-----------", empresa_norm)
    )


def _parsear_registro_tgss(linea: str) -> Optional[dict]:
    if not re.match(r"^(GENERAL|AUT[ÓO]NOMO|RETA|AGRARIO|MAR)\b", linea, re.IGNORECASE):
        return None

    fechas = re.findall(r"\b\d{2}[./-]\d{2}[./-]\d{4}\b", linea)
    if not fechas:
        return None

    primera_fecha = re.search(r"\b\d{2}[./-]\d{2}[./-]\d{4}\b", linea)
    if not primera_fecha:
        return None

    prefijo = linea[:primera_fecha.start()].strip()
    sufijo = linea[primera_fecha.end():].strip()
    prefijo_m = re.match(r"^(?P<regimen>GENERAL|AUT[ÓO]NOMO|RETA|AGRARIO|MAR)\s+(?P<ccc>\d{11}|-----------)?\s*(?P<empresa>.+?)\s*$", prefijo, re.IGNORECASE)
    if not prefijo_m:
        return None

    regimen_raw = prefijo_m.group("regimen").upper()
    regimen = "AUTONOMO" if "AUT" in regimen_raw or regimen_raw == "RETA" else "GENERAL"
    ccc = prefijo_m.group("ccc") or ""
    empresa = re.sub(r"\s+", " ", prefijo_m.group("empresa")).strip(" ,-") or "Empresa desconocida"
    if _es_empresa_ruido(empresa):
        return None

    fecha_alta = _normalizar_fecha(fechas[0])
    fecha_baja = None
    # En la vida laboral TGSS suele venir fecha alta, fecha efecto alta, fecha baja.
    if len(fechas) >= 3:
        fecha_baja = _normalizar_fecha(fechas[2])
    elif len(fechas) == 2 and "---" not in sufijo[:12]:
        fecha_baja = _normalizar_fecha(fechas[1])

    tokens = sufijo.split()
    ct = next((t for t in tokens if re.fullmatch(r"\d{3}", t)), None)
    ctp = next((t.replace(",", ".") for t in tokens if re.fullmatch(r"\d{1,3},\d", t)), None)
    gc = None
    dias = None
    numeros = [t for t in tokens if re.fullmatch(r"\d{1,4}", t)]
    if numeros:
        dias = int(numeros[-1])
        gc_candidatos = [n for n in numeros[:-1] if len(n) <= 2]
        gc = gc_candidatos[-1] if gc_candidatos else None
    if dias is not None and dias < 0:
        return None

    return {
        "regimen": regimen,
        "ccc_empresa": "" if ccc == "-----------" else ccc,
        "empresa": empresa,
        "fecha_alta": fecha_alta,
        "fecha_baja": fecha_baja,
        "ct": ct,
        "ctp": float(ctp) if ctp else None,
        "gc": gc,
        "dias": dias,
        "tipo_situacion": "desempleo" if "DESEMPLEO" in empresa.upper() else ("vacaciones_retribuidas_no_disfrutadas" if "VACACIONES" in empresa.upper() else "alta_empresa"),
        "linea_origen": linea,
    }


def extraer(texto: str) -> tuple[dict, list[str]]:
    advertencias: list[str] = []

    es_vida_laboral = bool(
        re.search(r"informe\s+de\s+vida\s+laboral", texto, re.IGNORECASE) or
        re.search(r"tesorer[ií]a\s+general\s+de\s+la\s+seguridad\s+social", texto, re.IGNORECASE)
    )
    if not es_vida_laboral:
        advertencias.append("No se detectaron señales claras de informe de vida laboral TGSS")

    nombre = _extraer_titular(texto)

    dni_m = re.search(r"(?:d\.?n\.?i\.?|documento\s+identificativo)[:\s\-]*([0-9A-Z]{7,12})", texto, re.IGNORECASE)
    nss_m = re.search(r"(?:n[uú]mero\s+de\s+(?:la\s+)?seguridad\s+social|n[ºo]\s+seguridad\s+social|afiliaci[oó]n|nss)[:\s\-]*(\d[\d\s\-]{9,14})", texto, re.IGNORECASE)

    fe_m = re.search(r"fecha\s+de\s+(?:emisi[oó]n|expedici[oó]n)[:\s]+([^\n\r]{5,20})", texto, re.IGNORECASE)
    fecha_emision = _normalizar_fecha(fe_m.group(1)) if fe_m else None

    registros = [
        r for r in (_parsear_registro_tgss(l) for l in _unir_lineas_registro(texto.splitlines()))
        if r is not None
    ]

    total_doc = _extraer_total_dias(texto)
    total_calc = sum(r["dias"] or 0 for r in registros)

    if total_doc and abs(total_doc - total_calc) > 30:
        advertencias.append(f"Discrepancia en días: documento indica {total_doc}, calculado {total_calc}")

    empresas = list(dict.fromkeys(r["empresa"] for r in registros if r["empresa"] != "Empresa desconocida"))
    periodos = [f"{r['fecha_alta']} – {r['fecha_baja'] or 'actualidad'}" for r in registros]

    datos = {
        "nombre_completo_detectado": nombre,
        "dni_detectado": re.sub(r"[\s.\-]", "", dni_m.group(1)).upper() if dni_m else None,
        "nss_detectado": re.sub(r"[\s.\-/]", "", nss_m.group(1)) if nss_m else None,
        "fecha_emision": fecha_emision,
        "total_dias_computables": total_doc or (total_calc if total_calc > 0 else None),
        "num_registros": len(registros),
        "registros_detectados": registros,
        "empresas_detectadas": empresas,
        "periodos_detectados": periodos,
        "control": {
            "registros_detectados": len(registros),
            "requiere_revision": len(registros) == 0 or nombre is None,
            "motivos_revision": [
                *([] if registros else ["sin_registros_tgss"]),
                *([] if nombre else ["titular_no_detectado"]),
            ],
        },
    }

    return datos, advertencias
