"""
EXTRACTOR — Contrato laboral

Soporta formatos habituales y variantes SEPE (copia básica). Si el texto no
trae un campo, se intenta inferir desde el nombre del archivo.
"""

import re
from typing import Optional


def _fecha(raw: str | None) -> Optional[str]:
    if not raw:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return raw
    m = re.search(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})", raw)
    if not m:
        return None
    dia, mes, year = m.group(1).zfill(2), m.group(2).zfill(2), m.group(3)
    if int(mes) > 12:
        return None
    return f"{year}-{mes}-{dia}"


def _buscar(texto: str, patron: str) -> Optional[str]:
    m = re.search(patron, texto, re.IGNORECASE)
    return m.group(1).strip() if m else None


def _importe(raw: str | None) -> Optional[float]:
    if not raw:
        return None
    try:
        return float(raw.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def _es_copia_basica(texto: str) -> bool:
    return bool(re.search(r"copia\s+b[aá]sica|contrato\s+de\s+trabajo\s+indefinido", texto, re.IGNORECASE))


def _normalizar_nombre_sepe(raw: str) -> str:
    limpio = re.sub(r"\s+", " ", raw).strip()
    if "," not in limpio:
        return limpio
    apellidos, nombre = [p.strip() for p in limpio.split(",", 1)]
    if apellidos and nombre:
        return f"{nombre} {apellidos}"
    return limpio


def _trabajador_copia_basica(texto: str) -> Optional[str]:
    inicio = re.search(r"DATOS\s+DEL/?DE\s+LA\s+TRABAJADOR/A", texto, re.IGNORECASE)
    if not inicio:
        return None
    bloque = texto[inicio.start(): inicio.start() + 700]
    m = re.search(
        r"D\./D.{0,4}\.?\s*\n\s*([A-ZÁÉÍÓÚÑ][^\n]{3,70})",
        bloque,
        re.IGNORECASE,
    )
    return _normalizar_nombre_sepe(m.group(1)) if m else None


def _dni_trabajador_copia_basica(texto: str) -> Optional[str]:
    inicio = re.search(r"DATOS\s+DEL/?DE\s+LA\s+TRABAJADOR/A", texto, re.IGNORECASE)
    if not inicio:
        return None
    bloque = texto[inicio.start(): inicio.start() + 900]
    m = re.search(r"\b([0-9]{8}[A-Z]|[XYZ][0-9]{7}[A-Z])\b", bloque, re.IGNORECASE)
    return m.group(1).upper() if m else None


def _nombre_invalido(nombre: Optional[str]) -> bool:
    if not nombre:
        return True
    limpio = nombre.strip()
    if len(limpio) < 5:
        return True
    if re.match(r"^D\./D", limpio, re.IGNORECASE) or limpio.upper() == "CIF":
        return True
    return bool(re.search(r"\b(NIF|NIE|CUARTA|FECHA|DOMICILIO|NACIONALIDAD)\b", limpio, re.IGNORECASE))


def _empresa_copia_basica(texto: str) -> Optional[str]:
    return _buscar(
        texto,
        r"NOMBRE\s+O\s+RAZ[ÓO]N\s+SOCIAL\s+DE\s+LA\s+EMPRESA\s*\n\s*([A-ZÁÉÍÓÚÑ0-9][^\n]{3,90})",
    )


def _categoria_copia_basica(texto: str) -> Optional[str]:
    return _buscar(texto, r"prestar[aá]\s+sus\s+servicios\s+como\s*(?:\(\d+\)\s*)?([^,\n]{3,80})")


def _centro_copia_basica(texto: str) -> Optional[str]:
    return _buscar(
        texto,
        r"centro\s+de\s+trabajo\s+ubicado\s+en[^.\n]{0,40}\n?\s*([^.\n]{3,90})",
    )


def _hints_desde_nombre(nombre_archivo: str | None) -> dict:
    if not nombre_archivo:
        return {}
    hints: dict = {}
    codigo = re.search(r"cto[\s\-]?(\d{3})", nombre_archivo, re.IGNORECASE)
    if codigo:
        hints["codigo_contrato"] = codigo.group(1)
    fecha = re.search(r"(\d{4}-\d{2}-\d{2})(?=\.pdf|$)", nombre_archivo, re.IGNORECASE)
    if fecha:
        hints["fecha_inicio"] = fecha.group(1)
    nombre = re.search(r"[-\s]([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]{4,50})\s*-\s*CB\b", nombre_archivo, re.IGNORECASE)
    if nombre:
        hints["nombre_completo_detectado"] = " ".join(
            p.capitalize() for p in nombre.group(1).strip().split()
        )
    return hints


def _clausulas(texto: str) -> list[str]:
    patrones = [
        r"per[ií]odo\s+de\s+prueba",
        r"pacto\s+de\s+no\s+competencia",
        r"confidencialidad",
        r"teletrabajo|trabajo\s+a\s+distancia",
        r"exclusividad",
        r"horas?\s+complementarias",
    ]
    detectadas = []
    for patron in patrones:
        m = re.search(patron, texto, re.IGNORECASE)
        if m:
            detectadas.append(m.group(0))
    return detectadas


def extraer(texto: str, nombre_archivo: str | None = None) -> tuple[dict, list[str]]:
    advertencias: list[str] = []
    hints = _hints_desde_nombre(nombre_archivo)
    copia_basica = _es_copia_basica(texto)

    if not re.search(
        r"contrato\s+de\s+trabajo|servicio\s+p[uú]blico\s+de\s+empleo|c[oó]digo\s+de\s+contrato|copia\s+b[aá]sica",
        texto,
        re.IGNORECASE,
    ):
        advertencias.append("No se detectaron señales claras de contrato laboral")

    nombre = (
        (_trabajador_copia_basica(texto) if copia_basica else None)
        or _buscar(texto, r"(?:trabajador(?:/a)?|persona\s+trabajadora|empleado(?:/a)?)[:\s]+([A-ZÁÉÍÓÚÑ][^\n\r\d]{3,70})")
    )
    if _nombre_invalido(nombre):
        nombre = hints.get("nombre_completo_detectado")

    dni = _dni_trabajador_copia_basica(texto) if copia_basica else _buscar(
        texto,
        r"(?:d\.?n\.?i\.?|n\.?i\.?f\.?|nie)[:\s\-]+([0-9]{8}[A-Z]|[XYZ][0-9]{7}[A-Z])",
    )

    nss = _buscar(texto, r"(?:n[uú]mero\s+de\s+)?(?:afiliaci[oó]n|nss)[:\s\-]+(\d[\d\s\-\/]{9,16})")
    empresa = (
        (_empresa_copia_basica(texto) if copia_basica else None)
        or _buscar(texto, r"(?:empresa|empleador(?:a)?)[:\s]+([A-ZÁÉÍÓÚÑ0-9 .,&\-]{3,90})")
    )
    cif = _buscar(texto, r"(?:c\.?i\.?f\.?\/nif\/nie|c\.?i\.?f\.?)[:\s\-]*\n?\s*([A-Z0-9]{8,10})")
    centro = (
        (_centro_copia_basica(texto) if copia_basica else None)
        or _buscar(texto, r"centro\s+de\s+trabajo[:\s]+([^\n\r]{3,90})")
    )

    fecha_inicio = (
        _fecha(_buscar(texto, r"inici[aá]ndose\s+la\s+relaci[oó]n\s+laboral\s+en\s+fecha\s+([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{4})"))
        or _fecha(_buscar(texto, r"(?:fecha\s+de\s+inicio|inicio\s+de\s+la\s+relaci[oó]n|desde)[:\s]+([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{4})"))
        or hints.get("fecha_inicio")
    )
    fecha_fin = _fecha(_buscar(texto, r"(?:fecha\s+de\s+fin|hasta|duraci[oó]n\s+hasta)[:\s]+([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{4})"))

    tipo = (
        _buscar(texto, r"modalidad\s+contractual\s+([^\n.]{3,60})")
        or _buscar(texto, r"(?:tipo\s+de\s+contrato|modalidad)[:\s]+([^\n\r]{3,80})")
        or ("Fijo discontinuo" if copia_basica and re.search(r"fijos?\s+discontinuos?", texto, re.IGNORECASE) else None)
    )
    codigo = (
        _buscar(texto, r"c[oó]digo\s+de\s+contrato[:\s]+(\d{3})")
        or _buscar(texto, r"\bCT[:\s]+(\d{3})\b")
        or hints.get("codigo_contrato")
    )
    jornada = _buscar(texto, r"jornada[:\s]+([^\n\r]{3,80})")
    horas_raw = _buscar(texto, r"(\d{1,2}(?:[,.]\d{1,2})?)\s*horas?\s+semanales")
    horas = float(horas_raw.replace(",", ".")) if horas_raw else None
    categoria = (
        (_categoria_copia_basica(texto) if copia_basica else None)
        or _buscar(texto, r"(?:categor[ií]a|grupo\s+profesional|puesto\s+de\s+trabajo)[:\s]+([^\n\r]{3,80})")
    )
    salario = _importe(_buscar(texto, r"(?:salario|retribuci[oó]n)[:\s]+(\d{1,3}(?:\.\d{3})*,\d{2})"))
    periodo_prueba = _buscar(texto, r"per[ií]odo\s+de\s+prueba\s+de[^.\n]{0,20}([0-9]+\s*meses?)") or _buscar(
        texto, r"per[ií]odo\s+de\s+prueba[:\s]+([^\n\r]{3,80})"
    )

    if not fecha_inicio:
        advertencias.append("No se detectó fecha de inicio del contrato")
    if not tipo and not codigo:
        advertencias.append("No se detectó modalidad/código de contrato")
    if not jornada and horas is None:
        advertencias.append("No se detectó jornada u horas semanales")
    if copia_basica and not dni:
        advertencias.append("DNI del trabajador no legible en copia básica")

    datos = {
        "nombre_completo_detectado": nombre,
        "dni_detectado": re.sub(r"[\s.\-]", "", dni).upper() if dni else None,
        "nss_detectado": re.sub(r"\D", "", nss) if nss else None,
        "empresa": empresa,
        "cif_empresa": cif.upper() if cif else None,
        "centro_trabajo": centro,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "tipo_contrato": tipo,
        "codigo_contrato": codigo,
        "jornada": jornada,
        "horas_semanales": horas,
        "categoria": categoria,
        "salario": salario,
        "periodo_prueba": periodo_prueba,
        "clausulas_detectadas": _clausulas(texto),
    }
    return datos, advertencias
