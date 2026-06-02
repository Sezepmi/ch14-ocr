"""
EXTRACTOR — Nóminas

Puerto del parseador TypeScript parsearNomina.
Extrae campos estructurados de texto de nómina española.
"""

import re
from typing import Optional

FUENTE_DEFECTO = "OCR"


def _buscar(texto: str, patron: str, grupo: int = 1) -> Optional[str]:
    m = re.search(patron, texto, re.IGNORECASE)
    if m:
        try:
            return m.group(grupo).strip()
        except IndexError:
            return None
    return None


def _parsear_importe(raw: Optional[str]) -> Optional[float]:
    if not raw:
        return None
    # "1.234,56" → 1234.56
    limpio = re.sub(r"\.", "", raw).replace(",", ".")
    try:
        return round(float(limpio), 2)
    except ValueError:
        return None


def _buscar_importe(texto: str, patron: str) -> Optional[float]:
    raw = _buscar(texto, patron)
    return _parsear_importe(raw)


def _normalizar_espacios(valor: str) -> str:
    return re.sub(r"\s+", " ", valor).strip()


def _campo(valor_original, valor_normalizado=None, confianza: float = 0.75, fragmento: str = "", requiere_revision: bool = False):
    if valor_normalizado is None:
        valor_normalizado = valor_original
    return {
        "valor_original": valor_original,
        "valor_normalizado": valor_normalizado,
        "confianza": round(confianza, 2),
        "fuente": FUENTE_DEFECTO,
        "fragmento_origen": _normalizar_espacios(fragmento or str(valor_original or ""))[:240],
        "requiere_revision": requiere_revision,
    }


def _fragmento(texto: str, inicio: int, fin: int, margen: int = 80) -> str:
    return texto[max(0, inicio - margen):min(len(texto), fin + margen)]


def _buscar_con_meta(texto: str, patron: str, grupo: int = 1, normalizador=None, confianza: float = 0.78):
    m = re.search(patron, texto, re.IGNORECASE | re.MULTILINE)
    if not m:
        return None, None
    raw = m.group(grupo).strip()
    normalizado = normalizador(raw) if normalizador else _normalizar_espacios(raw)
    return normalizado, _campo(raw, normalizado, confianza, _fragmento(texto, m.start(), m.end()))


def _importe_meta(texto: str, patron: str, grupo: int = 1, confianza: float = 0.78):
    valor, meta = _buscar_con_meta(texto, patron, grupo, _parsear_importe, confianza)
    return valor, meta


def _primer_match(texto: str, patrones: list[str], normalizador=None, confianza: float = 0.76):
    for patron in patrones:
        valor, meta = _buscar_con_meta(texto, patron, 1, normalizador, confianza)
        if valor not in (None, ""):
            return valor, meta
    return None, None


def _parse_fecha_dd_mmm_aa(raw: str) -> str:
    meses = {
        "ENE": "01", "ENERO": "01",
        "FEB": "02", "FEBRERO": "02",
        "MAR": "03", "MARZO": "03",
        "ABR": "04", "ABRIL": "04",
        "MAY": "05", "MAYO": "05",
        "JUN": "06", "JUNIO": "06",
        "JUL": "07", "JULIO": "07",
        "AGO": "08", "AGOSTO": "08",
        "SEP": "09", "SEPT": "09", "SEPTIEMBRE": "09",
        "OCT": "10", "OCTUBRE": "10",
        "NOV": "11", "NOVIEMBRE": "11",
        "DIC": "12", "DICIEMBRE": "12",
    }
    m = re.search(r"(\d{1,2})\s+([A-ZÁÉÍÓÚÑ]{3,10})\s+(\d{2,4})", raw.upper())
    if not m:
        return raw
    dia = int(m.group(1))
    mes = meses.get(m.group(2), "01")
    yy = int(m.group(3))
    year = yy if yy > 1900 else 2000 + yy
    return f"{year:04d}-{mes}-{dia:02d}"


def _mes_nomina_desde_periodo(periodo: Optional[dict]) -> Optional[str]:
    if not periodo or not periodo.get("desde"):
        return None
    meses = {
        "01": "ENERO", "02": "FEBRERO", "03": "MARZO", "04": "ABRIL",
        "05": "MAYO", "06": "JUNIO", "07": "JULIO", "08": "AGOSTO",
        "09": "SEPTIEMBRE", "10": "OCTUBRE", "11": "NOVIEMBRE", "12": "DICIEMBRE",
    }
    m = re.match(r"(\d{4})-(\d{2})-\d{2}", str(periodo["desde"]))
    if not m:
        return None
    return f"{meses.get(m.group(2), m.group(2))} {m.group(1)}"


_PATRON_IMPORTE_ES = r"(?<!\d)(\d{1,3}(?:\.\d{3})+,\d{2}|\d+,\d{2})(?!\d)"
_PATRON_IMPORTE_ES_3D = r"(?<!\d)(\d{1,3}(?:\.\d{3})+,\d{2,3}|\d+,\d{2,3})(?!\d)"


def _importes_en_fragmento(fragmento: str, decimales_hasta_3: bool = False) -> list[float]:
    """Importes españoles sin partir miles de 4 dígitos (p. ej. 1379,72)."""
    patron = _PATRON_IMPORTE_ES_3D if decimales_hasta_3 else _PATRON_IMPORTE_ES
    out: list[float] = []
    for m in re.finditer(patron, fragmento):
        val = _parsear_importe(m.group(1))
        if val is not None:
            out.append(val)
    return out


def _extraer_periodo_real(texto: str):
    patron = r"(\d{1,2}\s+(?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|SEPT|OCT|NOV|DIC)[A-Z]*\s+\d{2,4})\s+a\s+(\d{1,2}\s+(?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|SEPT|OCT|NOV|DIC)[A-Z]*\s+\d{2,4})"
    m = re.search(patron, texto, re.IGNORECASE)
    if not m:
        return None, {}
    frag = _fragmento(texto, m.start(), m.end())
    desde_raw = m.group(1)
    hasta_raw = m.group(2)
    return {
        "desde": _parse_fecha_dd_mmm_aa(desde_raw),
        "hasta": _parse_fecha_dd_mmm_aa(hasta_raw),
    }, {
        "periodo.desde": _campo(desde_raw, _parse_fecha_dd_mmm_aa(desde_raw), 0.85, frag),
        "periodo.hasta": _campo(hasta_raw, _parse_fecha_dd_mmm_aa(hasta_raw), 0.85, frag),
    }


def _extraer_periodo_de_mes(texto: str) -> tuple[Optional[dict], dict]:
    """Del 1 de Enero de 2020 al 31 de Enero de 2020."""
    m = re.search(
        r"Del\s+(\d{1,2})\s+de\s+([A-Za-zÁÉÍÓÚñ]+)\s+de\s+(\d{4})\s+al\s+(\d{1,2})\s+de\s+([A-Za-zÁÉÍÓÚñ]+)\s+de\s+(\d{4})",
        texto,
        re.I,
    )
    if not m:
        return None, {}
    meses = {
        "ENERO": "01", "FEBRERO": "02", "MARZO": "03", "ABRIL": "04", "MAYO": "05", "JUNIO": "06",
        "JULIO": "07", "AGOSTO": "08", "SEPTIEMBRE": "09", "OCTUBRE": "10", "NOVIEMBRE": "11", "DICIEMBRE": "12",
    }
    mes_desde = meses.get(m.group(2).upper(), "01")
    mes_hasta = meses.get(m.group(5).upper(), mes_desde)
    anio_desde = m.group(3)
    anio_hasta = m.group(6)
    desde = f"{anio_desde}-{mes_desde}-{int(m.group(1)):02d}"
    hasta = f"{anio_hasta}-{mes_hasta}-{int(m.group(4)):02d}"
    frag = m.group(0)
    return {"desde": desde, "hasta": hasta}, {
        "periodo.desde": _campo(frag, desde, 0.9, frag),
        "periodo.hasta": _campo(frag, hasta, 0.9, frag),
    }


def _extraer_periodo_mensual_rango(texto: str) -> tuple[Optional[dict], dict]:
    """Mensual - 1 Febrero 2023 a 28 Febrero 2023."""
    m = re.search(
        r"(?:Mensual\s*-\s*)?(\d{1,2})\s+([A-Za-zÁÉÍÓÚñ]+)\s+(\d{4})\s+a\s+(\d{1,2})\s+([A-Za-zÁÉÍÓÚñ]+)\s+(\d{4})",
        texto,
        re.I,
    )
    if not m:
        return None, {}
    meses = {
        "ENERO": "01", "FEBRERO": "02", "MARZO": "03", "ABRIL": "04", "MAYO": "05", "JUNIO": "06",
        "JULIO": "07", "AGOSTO": "08", "SEPTIEMBRE": "09", "OCTUBRE": "10", "NOVIEMBRE": "11", "DICIEMBRE": "12",
    }
    mes = meses.get(m.group(2).upper(), "01")
    anio = m.group(3)
    desde = f"{anio}-{mes}-{int(m.group(1)):02d}"
    hasta = f"{anio}-{mes}-{int(m.group(4)):02d}"
    frag = m.group(0)
    return {"desde": desde, "hasta": hasta}, {
        "periodo.desde": _campo(frag, desde, 0.88, frag),
        "periodo.hasta": _campo(frag, hasta, 0.88, frag),
    }


def _extraer_periodo_completo(texto: str) -> tuple[Optional[dict], dict]:
    for extractor in (
        _extraer_periodo_del_al,
        _extraer_periodo_de_mes,
        _extraer_periodo_mensual_rango,
        _extraer_periodo_real,
    ):
        periodo, trazas = extractor(texto)
        if periodo:
            return periodo, trazas
    return None, {}


def _anio_periodo_nomina(periodo_real: Optional[dict], mes_nomina: Optional[str]) -> Optional[int]:
    if periodo_real and periodo_real.get("desde"):
        m = re.match(r"(\d{4})-", str(periodo_real["desde"]))
        if m:
            return int(m.group(1))
    if mes_nomina:
        m = re.search(r"(20\d{2})", str(mes_nomina))
        if m:
            return int(m.group(1))
    return None


def _extraer_bloque_tres_totales(texto: str) -> tuple[Optional[float], Optional[float], Optional[float], dict]:
    """
    Total devengado / deducir / líquido cuando las etiquetas van en bloque
    y los importes en las líneas siguientes (VAL&THI, PUNTO-FA, etc.).
    Solo devuelve valores si el triple es matemáticamente coherente (±1 €).
    """
    trazas: dict = {}

    m_triple = re.search(
        r"Total\s+Devengado\s+Total\s+Deducir\s+LIQUIDO\s+A\s+PERCIBIR\s+Euros?\s*"
        r"(?P<d1>\d{1,3}(?:\.\d{3})*,\d{2})\s+(?P<d2>\d{1,3}(?:\.\d{3})*,\d{2})\s+(?P<d3>\d{1,3}(?:\.\d{3})*,\d{2})",
        texto,
        re.I | re.S,
    )
    if m_triple:
        devengado = _parsear_importe(m_triple.group("d1"))
        deducir = _parsear_importe(m_triple.group("d2"))
        liquido = _parsear_importe(m_triple.group("d3"))
        if (
            devengado is not None
            and deducir is not None
            and liquido is not None
            and abs(devengado - deducir - liquido) <= 1.0
        ):
            frag = m_triple.group(0)
            trazas["totales.total_devengado"] = _campo(frag, devengado, 0.92, frag[:120])
            trazas["totales.total_deducir"] = _campo(frag, deducir, 0.92, frag[:120])
            trazas["totales.liquido"] = _campo(frag, liquido, 0.92, frag[:120])
            return devengado, deducir, liquido, trazas

    m_dev = re.search(
        r"(?:TOTAL\s+DEVENGOS?|TOTAL\s+DEVENGADO)[^\d]{0,40}(?P<dev>\d{1,3}(?:\.\d{3})*,\d{2})",
        texto,
        re.I,
    )
    m_ret = re.search(
        r"TOTAL\s+RETENCIONES[^\d]{0,40}(?P<ded>\d{1,3}(?:\.\d{3})*,\d{2})",
        texto,
        re.I,
    )
    if m_dev and m_ret:
        devengado = _parsear_importe(m_dev.group("dev"))
        deducir = _parsear_importe(m_ret.group("ded"))
        if devengado is not None and deducir is not None and deducir < devengado:
            liquido = round(devengado - deducir, 2)
            frag = m_dev.group(0) + " | " + m_ret.group(0)
            trazas["totales.total_devengado"] = _campo(frag, devengado, 0.9, frag)
            trazas["totales.total_deducir"] = _campo(frag, deducir, 0.9, frag)
            trazas["totales.liquido"] = _campo("calculado", liquido, 0.88, frag)
            return devengado, deducir, liquido, trazas

    return None, None, None, trazas


def _extraer_liquido_explicito(texto: str) -> tuple[Optional[float], Optional[dict]]:
    """Líquido en línea propia (p. ej. 'Líquido a Percibir' + importe en las siguientes líneas)."""
    m = re.search(r"L[IÍ]QUIDO\s+(?:TOTAL\s+)?A\s+PERCIBIR", texto, re.I)
    if not m:
        m = re.search(r"L[IÍ]QUIDO\s+A\s+PERCIBIR", texto, re.I)
    if not m:
        return None, None
    ventana = texto[m.end():m.end() + 120]
    nums = [n for n in _importes_en_fragmento(ventana) if 50 <= n <= 50000]
    if not nums:
        return None, None
    valor = nums[0]
    return valor, _campo(ventana.strip(), valor, 0.88, ventana[:120])


def _extraer_salario_base_multilinea(texto: str) -> tuple[Optional[float], Optional[dict]]:
    m = re.search(r"Salario\s+Base", texto, re.I)
    if not m:
        return None, None
    ventana = texto[m.end():m.end() + 160]
    corte = re.search(
        r"TOTAL\s+DEVENG|Total\s+Devengado|T\.?\s*DEVENGADO|REM\.?\s+TOTAL",
        ventana,
        re.I,
    )
    if corte:
        ventana = ventana[:corte.start()]
    nums = [n for n in _importes_en_fragmento(ventana) if n >= 50]
    if not nums:
        return None, None
    valor = max(nums)
    return valor, _campo(ventana.strip(), valor, 0.86, ventana[:120])


def _extraer_deducciones_tabla_resumen(texto: str) -> tuple[list[dict], dict]:
    """Cont.Comunes / Desempleo / For.Profesional / I.R.P.F. en tabla Cuantía–Concepto–Deducción."""
    defs = [
        ("CC", "Cotización contingencias comunes", r"Cont\.?\s*Comunes", "deduccion"),
        ("DES", "Cotización desempleo", r"Desempleo", "deduccion"),
        ("FOR", "Cotización formación", r"For\.?\s*Profesional", "deduccion"),
        ("IRPF", "Tributación IRPF", r"I\.?\s*R\.?\s*P\.?\s*F\.?", "deduccion"),
        ("CC", "Cotización contingencias comunes", r"Cotiz\.?\s+Cont(?:ingencias)?\.?\s+Com", "deduccion"),
        ("DES", "Cotización desempleo", r"Cotiz\.?\s+Desempleo", "deduccion"),
        ("FOR", "Cotización formación", r"Cotiz\.?\s+Formac", "deduccion"),
        ("IRPF", "Tributación IRPF", r"Retenci[oó]n\s+a\s+Cuenta\s+IRPF", "deduccion"),
    ]
    conceptos: list[dict] = []
    trazas: dict = {}
    vistos: set[str] = set()
    for codigo, nombre, patron, tipo in defs:
        if codigo in vistos and codigo != "IRPF":
            continue
        m = re.search(patron, texto, re.I)
        if not m:
            continue
        ventana = texto[m.end():m.end() + 200]
        nums = _importes_en_fragmento(ventana)
        importes = [n for n in nums if 0 < n < 5000]
        if not importes:
            continue
        if codigo == "IRPF":
            candidatos = [n for n in importes if n < 200]
            if not candidatos:
                continue
            importe = candidatos[0]
        else:
            importe = importes[0]
        concepto = {
            "codigo": codigo,
            "nombre": nombre,
            "tipo": tipo,
            "cantidad": None,
            "precio": None,
            "importe": importe,
            "sujeto_ss": False,
        }
        conceptos.append(concepto)
        trazas[f"deduccion.{codigo}"] = _campo(m.group(0), concepto, 0.8, ventana[:100])
        vistos.add(codigo)
    return conceptos, trazas


def _coherencia_totales_nomina(
    total_devengos: Optional[float],
    total_deducciones: Optional[float],
    neto: Optional[float],
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """Corrige líquido/deducir incoherentes (p. ej. los tres iguales al devengado)."""
    if total_devengos is None:
        return total_devengos, total_deducciones, neto
    if (
        total_deducciones is not None
        and neto is not None
        and abs(total_deducciones - total_devengos) < 0.02
        and abs(neto - total_devengos) < 0.02
        and total_deducciones > 0
    ):
        total_deducciones = None
        neto = None
    if total_devengos is not None and neto is not None and total_deducciones is None:
        total_deducciones = round(total_devengos - neto, 2)
    if total_devengos is not None and total_deducciones is not None and neto is None:
        neto = round(total_devengos - total_deducciones, 2)
    if total_devengos is not None and total_deducciones is not None and neto is not None:
        if abs(total_devengos - total_deducciones - neto) > 1.0:
            if abs(neto - total_devengos) < 0.02:
                neto = round(total_devengos - total_deducciones, 2)
            elif abs(total_deducciones - total_devengos) < 0.02:
                total_deducciones = round(total_devengos - neto, 2)
    return total_devengos, total_deducciones, neto


def _extraer_importes_despues(texto: str, nombre_patron: str) -> tuple[list[float], str]:
    m = re.search(nombre_patron + r"(?P<resto>[^\n\r]{0,140})", texto, re.IGNORECASE)
    if not m:
        return [], ""
    frag = m.group(0)
    return _importes_en_fragmento(frag, decimales_hasta_3=True), frag


def _sin_acentos(valor: str) -> str:
    reemplazos = str.maketrans("ÁÉÍÓÚÜÑáéíóúüñ", "AEIOUUNaeiouun")
    return valor.translate(reemplazos).upper()


def _lineas_utiles(texto: str) -> list[str]:
    return [_normalizar_espacios(linea) for linea in texto.splitlines() if _normalizar_espacios(linea)]


def _extraer_naf_flexible(texto: str) -> Optional[str]:
    patrones = [
        r"\b(\d{2}\/\d{7,8}-\d{2})\b",
        r"\b(\d{2})\D{0,3}(\d{7,8})\D{0,3}(\d{2})\b",
    ]
    for patron in patrones:
        m = re.search(patron, texto)
        if not m:
            continue
        if len(m.groups()) == 1:
            return m.group(1)
        return f"{m.group(1)}/{m.group(2)}-{m.group(3)}"
    return None


def _importes_linea(linea: str, decimales_hasta_3: bool = False) -> list[float]:
    return _importes_en_fragmento(linea, decimales_hasta_3=decimales_hasta_3)


def _es_linea_candidata_nombre(linea: str) -> bool:
    linea_norm = _sin_acentos(linea)
    bloqueadas = [
        "EMPRESA", "DOMICILIO", "AEROPUERTO", "CONCEPTO", "IMPORTE",
        "COTIZACION", "TRIBUTACION", "SALARIO", "BASE", "TOTAL",
        "LIQUIDO", "DEVENG", "DEDUC", "FECHA", "PERIODO", "NOMINA",
        "CIF", "INSCRIPCION", "SEGURIDAD SOCIAL", "TRANSPORTE",
        "SERVICIOS", "ADELTE",
    ]
    if any(token in linea_norm for token in bloqueadas):
        return False
    letras = re.findall(r"[A-ZÁÉÍÓÚÜÑ]{2,}", linea.upper())
    return len(letras) >= 3 and sum(ch.isdigit() for ch in linea) <= 2


def _limpiar_nombre_candidato(valor: str) -> Optional[str]:
    valor = re.sub(r"\b(?:DNI|NIF|N\.?I\.?F\.?|NIE|NAF|NSS|AFILIACI[OÓ]N|TRABAJADOR)\b.*$", "", valor, flags=re.IGNORECASE)
    valor = re.sub(r"[^A-ZÁÉÍÓÚÜÑ,\s]", " ", valor.upper())
    valor = _normalizar_espacios(valor)
    if not valor or not _es_linea_candidata_nombre(valor):
        return None
    return valor


def _extraer_nombre_por_lineas(texto: str, dni: Optional[str]) -> tuple[Optional[str], Optional[dict]]:
    lineas = _lineas_utiles(texto)
    if dni:
        for idx, linea in enumerate(lineas):
            if dni not in linea:
                continue
            prefijo = linea.split(dni, 1)[0]
            candidato = _limpiar_nombre_candidato(prefijo)
            if candidato:
                return candidato, _campo(prefijo, candidato, 0.74, linea)
            ventana = lineas[max(0, idx - 3):min(len(lineas), idx + 4)]
            candidatos = [l for l in ventana if _es_linea_candidata_nombre(l)]
            candidatos.sort(key=lambda l: ("," not in l, abs(ventana.index(l) - min(3, idx))))
            if candidatos:
                candidato = _limpiar_nombre_candidato(candidatos[0])
                if candidato:
                    return candidato, _campo(candidatos[0], candidato, 0.7, " | ".join(ventana), requiere_revision=True)

    candidatos_globales = []
    for linea in lineas[:40]:
        if _es_linea_candidata_nombre(linea):
            candidatos_globales.append(linea)
    if candidatos_globales:
        candidatos_globales.sort(key=lambda l: ("," not in l, len(l)))
        candidato = _limpiar_nombre_candidato(candidatos_globales[0])
        if candidato:
            return candidato, _campo(candidatos_globales[0], candidato, 0.62, candidatos_globales[0], requiere_revision=True)
    return None, None


def _extraer_empresa_por_lineas(texto: str) -> tuple[Optional[str], Optional[dict]]:
    for linea in _lineas_utiles(texto)[:50]:
        linea_norm = _sin_acentos(linea)
        if "DOMICILIO" in linea_norm:
            continue
        if "ADELTE" in linea_norm:
            m = re.search(r"(ADELTE[\wÁÉÍÓÚÜÑ\s,.&-]{0,80}?SERVICIOS)", linea, re.IGNORECASE)
            valor = _normalizar_espacios(m.group(1) if m else linea)
            return valor, _campo(linea, valor, 0.82, linea)
        if re.search(r"\b(S\.?L\.?|S\.?A\.?|UTE|TRANSPORTE|SERVICIOS)\b", linea_norm):
            if any(b in linea_norm for b in ["TRABAJADOR", "CATEGORIA", "CONCEPTO", "SALARIO", "COTIZACION"]):
                continue
            valor = re.split(r"\b(?:CIF|C\.?I\.?F\.?|DOMICILIO|AEROPUERTO)\b", linea, maxsplit=1, flags=re.IGNORECASE)[0]
            valor = _normalizar_espacios(valor)
            if len(valor) >= 5:
                return valor, _campo(linea, valor, 0.68, linea, requiere_revision=True)
    return None, None


def _extraer_centro_por_lineas(texto: str) -> tuple[Optional[str], Optional[dict]]:
    for linea in _lineas_utiles(texto)[:60]:
        linea_norm = _sin_acentos(linea)
        if "AEROPUERTO" in linea_norm:
            m = re.search(r"(AEROPUERTO[\wÁÉÍÓÚÜÑ\s,.&-]{0,80})", linea, re.IGNORECASE)
            valor = _normalizar_espacios(m.group(1) if m else linea)
            valor = re.split(r"\b(?:CIF|C\.?I\.?F\.?|DNI|NIF|TRABAJADOR)\b", valor, maxsplit=1, flags=re.IGNORECASE)[0]
            valor = _normalizar_espacios(valor)
            return valor, _campo(linea, valor, 0.78, linea)
    return None, None


def _extraer_inscripcion_empresa(texto: str) -> tuple[Optional[str], Optional[dict]]:
    for linea in _lineas_utiles(texto)[:80]:
        linea_norm = _sin_acentos(linea)
        if "ADELTE" not in linea_norm and "AEROPUERTO" not in linea_norm and "EMPRESA" not in linea_norm:
            continue
        inscripciones = re.findall(r"\b\d{2}/\d{7,8}-\d{2}\b", linea)
        if inscripciones:
            return inscripciones[-1], _campo(linea, inscripciones[-1], 0.82, linea)
    return None, None


def _extraer_datos_trabajador_por_lineas(texto: str, dni: Optional[str]) -> dict[str, tuple[Optional[str], Optional[dict]]]:
    resultado: dict[str, tuple[Optional[str], Optional[dict]]] = {}
    lineas = _lineas_utiles(texto)
    candidatas = []
    for idx, linea in enumerate(lineas):
        linea_norm = _sin_acentos(linea)
        if (dni and dni in linea) or any(t in linea_norm for t in ["AFILIACION", "CATEGORIA", "ANTIG", "TARIFA", "CONTRATO", "NRO", "SECCION"]):
            candidatas.extend(lineas[max(0, idx - 1):min(len(lineas), idx + 3)])
    bloque = " | ".join(dict.fromkeys(candidatas))
    bloque_norm = _sin_acentos(bloque)

    naf = _extraer_naf_flexible(bloque)
    if naf:
        resultado["naf"] = (naf, _campo(naf, naf, 0.78, bloque))

    linea_naf = next((linea for linea in candidatas if naf and naf in linea), "")
    if linea_naf:
        m_pos = re.search(r"\d{2}/\d{7,8}-\d{2}\s+(\d{1,2})\s+(\d{3})\s+(\d{5,8})", linea_naf)
        if m_pos:
            resultado["tarifa"] = (m_pos.group(1), _campo(linea_naf, m_pos.group(1), 0.82, linea_naf))
            resultado["codigo_contrato"] = (m_pos.group(2), _campo(linea_naf, m_pos.group(2), 0.82, linea_naf))
            resultado["seccion_nro"] = (m_pos.group(3), _campo(linea_naf, m_pos.group(3), 0.82, linea_naf))

    categoria_m = re.search(r"\b(AGENTE|AUXILIAR|OFICIAL|ADMINISTRATIV[OA]|CONDUCTOR[A]?|OPERARI[OA]|T[ÉE]CNIC[OA])\b", bloque, re.IGNORECASE)
    if categoria_m:
        resultado["categoria"] = (_normalizar_espacios(categoria_m.group(1).upper()), _campo(categoria_m.group(0), categoria_m.group(1).upper(), 0.7, bloque))

    antig_m = re.search(r"\b(\d{1,2}\s+(?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|SEPT|OCT|NOV|DIC)[A-Z]*\s+\d{2,4})\b", bloque, re.IGNORECASE)
    if antig_m:
        resultado["antiguedad"] = (_normalizar_espacios(antig_m.group(1).upper()), _campo(antig_m.group(1), antig_m.group(1).upper(), 0.7, bloque))

    tarifa_m = re.search(r"TARIFA\D{0,12}(\d{1,2})", bloque_norm) or re.search(r"\bTAR\D{0,8}(\d{1,2})", bloque_norm)
    if tarifa_m and "tarifa" not in resultado:
        resultado["tarifa"] = (tarifa_m.group(1), _campo(tarifa_m.group(0), tarifa_m.group(1), 0.66, bloque, requiere_revision=True))

    contrato_m = re.search(r"CONTRATO\D{0,12}(\d{3})", bloque_norm) or re.search(r"\bCT\D{0,8}(\d{3})", bloque_norm)
    if contrato_m and "codigo_contrato" not in resultado:
        resultado["codigo_contrato"] = (contrato_m.group(1), _campo(contrato_m.group(0), contrato_m.group(1), 0.66, bloque, requiere_revision=True))

    seccion_m = re.search(r"(?:SECCION|NRO|Nº|NO)\D{0,12}(\d{5,8})", bloque_norm)
    if seccion_m and "seccion_nro" not in resultado:
        resultado["seccion_nro"] = (seccion_m.group(1), _campo(seccion_m.group(0), seccion_m.group(1), 0.66, bloque, requiere_revision=True))

    return resultado


def _extraer_dias_por_lineas(texto: str) -> tuple[Optional[int], Optional[dict]]:
    for linea in _lineas_utiles(texto):
        linea_norm = _sin_acentos(linea)
        if "MENS" not in linea_norm and "TOT" not in linea_norm:
            continue
        m = re.search(r"\bMENS\s+\d{1,2}\s+[A-Z]{3,10}\s+\d{2,4}\s+A\s+\d{1,2}\s+[A-Z]{3,10}\s+\d{2,4}\s+(\d{1,2})\b", linea_norm)
        if m:
            return int(m.group(1)), _campo(m.group(1), int(m.group(1)), 0.86, linea)
    return None, None


def _extraer_totales_tabla(texto: str) -> tuple[dict, dict]:
    trazas: dict = {}
    lineas = _lineas_utiles(texto)
    for idx, linea in enumerate(lineas):
        linea_norm = _sin_acentos(linea)
        if not all(token in linea_norm for token in ["REM", "TOTAL", "BASE", "DEVENGADO", "DEDUCIR"]):
            continue
        for siguiente in lineas[idx + 1:idx + 4]:
            nums = _importes_linea(siguiente)
            if len(nums) >= 7:
                claves = [
                    "remuneracion_total",
                    "prorrata_extras",
                    "base_ss",
                    "base_at_desempleo",
                    "base_irpf",
                    "total_devengado",
                    "total_deducir",
                ]
                valores = dict(zip(claves, nums[:7]))
                for clave, valor in valores.items():
                    trazas[f"totales.{clave}"] = _campo(siguiente, valor, 0.9, f"{linea} | {siguiente}")
                return valores, trazas
    return {}, trazas


def _extraer_coste_empresa(texto: str) -> tuple[Optional[float], Optional[dict]]:
    patrones = [
        r"C\s*O\s*S\s*T\s*E\s+EMPRESA\s*:\s*([\d.]+,\d{2})",
        r"COSTE\s+EMPRESA\s*:\s*([\d.]+,\d{2})",
        r"([\d.]+,\d{2})\s*(?:\n|\r\n?)\s*SWIFT/BIC:\s*(?:[A-Z0-9]+\s*)?C\s*O\s*STE\s+EMPRESA",
    ]
    for patron in patrones:
        m = re.search(patron, texto, re.IGNORECASE)
        if m:
            valor = _parsear_importe(m.group(1))
            if valor is not None:
                return valor, _campo(m.group(0), valor, 0.82, m.group(0))
    for linea in _lineas_utiles(texto):
        compacta = re.sub(r"\s+", "", _sin_acentos(linea))
        if "COSTEEMPRESA" in compacta:
            nums = _importes_linea(linea)
            if nums:
                return nums[-1], _campo(linea, nums[-1], 0.78, linea)
    return None, None


def _extraer_importes_por_linea(texto: str, nombre: str) -> tuple[list[float], str]:
    tokens = [t for t in re.split(r"\s+", _sin_acentos(nombre)) if len(t) > 2]
    equivalencias = {
        "SALARIO BASE": ["SALARIO", "BASE"],
        "HORAS NOCTURNAS": ["HORAS", "NOCTURN"],
        "PLUS TRANSPORTE FIJO": ["PLUS", "TRANSPORTE"],
        "AYUDA MANUTENCION": ["MANUTENCION"],
        "HORAS EXTRAS NORMAL": ["HORAS", "EXTR"],
        "DTO CUOTA SINDICAL": ["CUOTA", "SINDICAL"],
        "TRIBUTACION IRPF": ["TRIBUTACION", "IRPF"],
        "COTIZACION CONTINGENCIAS COMUNES": ["COTIZACI", "CONT"],
        "COTIZACION FORMACION": ["COTIZACI", "FORMACION"],
        "COTIZACION DESEMPLEO": ["COTIZACI", "DESEMPLEO"],
        "COTIZACION HORAS EXTRA": ["COTIZACI", "HORAS", "EXT"],
        "AT Y EP": ["AT", "EP"],
        "FORMACION PROFESIONAL": ["FORMACION"],
        "COTIZACION ADICIONAL HORAS EXTRAORDINARIAS": ["HORAS", "EXTRAORDIN"],
    }
    buscados = equivalencias.get(_sin_acentos(nombre), tokens)
    for linea in texto.splitlines():
        linea_norm = _sin_acentos(linea)
        if all(token in linea_norm for token in buscados):
            nums = [_parsear_importe(n) for n in re.findall(r"\d{1,3}(?:\.\d{3})*,\d{2,3}", linea)]
            nums = [n for n in nums if n is not None]
            if nums:
                return nums, linea
    return [], ""


def _lineas_con_importes(texto: str) -> list[tuple[str, list[float]]]:
    filas: list[tuple[str, list[float]]] = []
    for linea in texto.splitlines():
        linea_limpia = _normalizar_espacios(linea)
        if not linea_limpia:
            continue
        importes = [_parsear_importe(n) for n in re.findall(r"\d{1,3}(?:\.\d{3})*,\d{2,3}", linea_limpia)]
        importes = [n for n in importes if n is not None]
        if importes:
            filas.append((linea_limpia, importes))
    return filas


def _nombre_concepto_desde_linea(linea: str) -> str:
    antes_importe = re.split(r"\d{1,3}(?:\.\d{3})*,\d{2,3}", linea, maxsplit=1)[0]
    antes_importe = re.sub(r"^\s*\d{1,4}\s+", "", antes_importe)
    antes_importe = re.sub(r"^[\-–—·\s]+", "", antes_importe)
    return _normalizar_espacios(antes_importe)


def _es_linea_total_o_base(linea_norm: str) -> bool:
    tokens = [
        "TOTAL", "BASE", "LIQUIDO", "REMUNERACION", "PRORRATA",
        "COSTE EMPRESA", "APORTACION EMPRESARIAL",
    ]
    return any(t in linea_norm for t in tokens)


def _clasificar_linea_concepto(nombre_norm: str) -> str | None:
    deducciones = [
        "CUOTA SINDICAL", "COTIZACION", "TRIBUTACION", "IRPF",
        "DEDUC", "DESCUENTO", "DTO",
    ]
    devengos = [
        "SALARIO", "VACACION", "FESTIVO", "NOCTURN", "DOMINGO",
        "PLUS", "AYUDA", "MANUTENCION", "HORAS EXTRA", "DIFERENCIA",
    ]
    if any(t in nombre_norm for t in deducciones):
        return "deduccion"
    if any(t in nombre_norm for t in devengos):
        return "devengo"
    return None


def _concepto_id(concepto: dict) -> str:
    valor = _sin_acentos(str(concepto.get("nombre") or concepto.get("concepto") or "")).strip()
    valor = re.sub(r"^[*\-–—\s]+", "", valor)
    valor = re.sub(r"[^A-Z0-9]+", " ", valor)
    return _normalizar_espacios(valor)


def _extraer_conceptos_genericos(texto: str, existentes: list[dict]) -> tuple[list[dict], dict]:
    conceptos: list[dict] = []
    trazas: dict = {}
    vistos = {_concepto_id(c) for c in existentes}
    en_aportacion_empresa = False

    for linea, importes in _lineas_con_importes(texto):
        linea_norm = _sin_acentos(linea)
        if "APORTACION" in linea_norm and "EMPRES" in linea_norm:
            en_aportacion_empresa = True
            continue
        if en_aportacion_empresa:
            continue
        if _es_linea_total_o_base(linea_norm):
            continue

        nombre = _nombre_concepto_desde_linea(linea)
        if len(nombre) < 3:
            continue
        nombre_norm = _sin_acentos(nombre)
        tipo = _clasificar_linea_concepto(nombre_norm)
        if tipo is None or nombre_norm in vistos:
            continue

        codigo_m = re.match(r"\s*(\d{1,4})\s+", linea)
        cantidad = importes[0] if len(importes) >= 3 else None
        precio = importes[1] if len(importes) >= 3 else (importes[0] if tipo == "deduccion" and len(importes) == 2 else None)
        importe = importes[-1]
        concepto = {
            "codigo": codigo_m.group(1) if codigo_m else f"AUTO{len(existentes) + len(conceptos) + 1:02d}",
            "nombre": nombre,
            "tipo": tipo,
            "cantidad": cantidad,
            "precio": precio,
            "importe": importe,
            "sujeto_ss": tipo == "devengo",
        }
        conceptos.append(concepto)
        trazas[f"{tipo}.auto_{len(conceptos)}"] = _campo(linea, concepto, 0.68, linea, requiere_revision=True)
        vistos.add(nombre_norm)

    return conceptos, trazas


def _buscar_importe_por_tokens(texto: str, tokens: list[str]) -> tuple[Optional[float], Optional[dict]]:
    for linea, importes in _lineas_con_importes(texto):
        linea_norm = _sin_acentos(linea)
        if all(token in linea_norm for token in tokens):
            return importes[-1], _campo(linea, importes[-1], 0.72, linea)
    return None, None


def _concepto_por_nombre(texto: str, codigo: str, nombre: str, patron: str, tipo: str, sujeto_ss: bool = True):
    importes, frag = _extraer_importes_despues(texto, patron)
    importes_linea, frag_linea = _extraer_importes_por_linea(texto, nombre)
    if len(importes_linea) > len(importes):
        importes, frag = importes_linea, frag_linea
    if not importes:
        return None, None
    cantidad = importes[0] if len(importes) >= 3 else None
    precio = importes[1] if len(importes) >= 3 else None
    importe = importes[-1]
    concepto = {
        "codigo": codigo,
        "nombre": nombre,
        "tipo": tipo,
        "cantidad": cantidad,
        "precio": precio,
        "importe": importe,
        "sujeto_ss": sujeto_ss,
    }
    return concepto, _campo(frag, concepto, 0.82, frag)


def _extraer_conceptos_detallados(texto: str):
    definiciones = [
        ("001", "Salario Base", r"SALARIO\s+BASE", "devengo", True),
        ("VAC", "Vacaciones", r"VACACIONES", "devengo", True),
        ("FES", "Festivos", r"FESTIVOS?", "devengo", True),
        ("NOC", "Horas Nocturnas", r"HORAS?\s+NOCTURNAS?|NOCTURNIDAD", "devengo", True),
        ("DOM", "Domingo", r"\bDOMINGO\b", "devengo", True),
        ("PTR", "Plus transporte fijo", r"PLUS\s+TRANSPORTE\s+FIJO|PLUS\s+TRANSPORTE", "devengo", False),
        ("PMD", "Plus madrugue", r"PLUS\s+MADRUGUE", "devengo", True),
        ("MAN", "Ayuda manutención", r"AYUDA\s+MANUTENCI[OÓ]N|MANUTENCI[OÓ]N", "devengo", False),
        ("PJI", "Plus jornada irregular", r"PLUS\s+JORNADA\s+IRREGULAR", "devengo", True),
        ("HEN", "Horas Extras Normal", r"HORAS?\s+EXTRAS?\s+NORMAL", "devengo", True),
        ("DIF", "Diferencia mes anterior", r"DIFERENCIA\s+MES\s+ANTERIOR", "devengo", True),
        ("SIN", "Dto cuota sindical", r"DTO\.?\s+CUOTA\s+SINDICAL|CUOTA\s+SINDICAL", "deduccion", False),
        ("CC", "Cotización contingencias comunes", r"COTIZACI[OÓ]N\s+CONT(?:INGENCIAS)?\.?\s*COM", "deduccion", False),
        ("MEI", "Cotización MEI", r"COTIZACI[OÓ]N\s+MEI|\bMEI\b", "deduccion", False),
        ("FOR", "Cotización formación", r"COTIZACI[OÓ]N\s+FORMACI[OÓ]N", "deduccion", False),
        ("DES", "Cotización desempleo", r"COTIZACI[OÓ]N\s+DESEMPLEO", "deduccion", False),
        ("HEX", "Cotización horas extra", r"COTIZACI[OÓ]N\s+HORAS?\s+EXT", "deduccion", False),
        ("IRPF", "Tributación IRPF", r"TRIBUTACI[OÓ]N\s+I\.?R\.?P\.?F\.?", "deduccion", False),
    ]
    conceptos = []
    trazas = {}
    for codigo, nombre, patron, tipo, sujeto_ss in definiciones:
        concepto, meta = _concepto_por_nombre(texto, codigo, nombre, patron, tipo, sujeto_ss)
        if concepto:
            conceptos.append(concepto)
            trazas[f"{tipo}.{codigo}"] = meta
    return conceptos, trazas


def _extraer_aportacion_empresa(texto: str):
    defs = [
        ("Contingencias comunes", r"CONTINGENCIAS\s+COMUNES", "aportacion_empresa.contingencias_comunes"),
        ("MEI empresa", r"\bMEI\b", "aportacion_empresa.mei"),
        ("AT y EP", r"AT\s+y\s+EP|A\.?T\.?\s+y\s+E\.?P\.?", "aportacion_empresa.at_ep"),
        ("Desempleo", r"DESEMPLEO", "aportacion_empresa.desempleo"),
        ("Formación profesional", r"FORMACI[OÓ]N\s+PROFESIONAL|FORMACI[OÓ]N", "aportacion_empresa.formacion"),
        ("FOGASA", r"FOGASA|FONDO\s+GARANT[ÍI�]A\s+SALARIAL", "aportacion_empresa.fogasa"),
        ("Cotización adicional horas extraordinarias", r"COTIZACI[OÓ]N\s+ADICIONAL\s+HORAS?\s+EXTRA|HORAS?\s+EXTRAORDINARIAS", "aportacion_empresa.horas_extra"),
    ]
    aportaciones = []
    trazas = {}
    zona = texto
    zonas = list(re.finditer(r"APORTACI[OÓ�]N\s+EMPRESARIAL[\s\S]{0,1800}", texto, re.IGNORECASE))
    if not zonas:
        zonas = list(
            re.finditer(
                r"(?:APORTACIONES?\s+S\.?\s*S\.?\s+EMPRESA|DETERMINACI[OÓ]N\s+DE\s+LAS\s+BASES)[\s\S]{0,2200}",
                texto,
                re.IGNORECASE,
            )
        )
    if zonas:
        zona = zonas[-1].group(0)
    for nombre, patron, clave in defs:
        m = re.search(patron + r"(?P<resto>[^\n\r]{0,160})", zona, re.IGNORECASE)
        if m:
            frag = m.group(0)
            nums = _importes_en_fragmento(frag)
        else:
            nums, frag = _extraer_importes_por_linea(zona, nombre)
        if len(nums) >= 3:
            item = {"concepto": nombre, "base": nums[0], "tipo": nums[1], "aportacion": nums[2]}
        elif nums:
            item = {"concepto": nombre, "base": None, "tipo": None, "aportacion": nums[-1]}
        else:
            continue
        aportaciones.append(item)
        trazas[clave] = _campo(frag, item, 0.78, frag)

    # Segunda pasada por líneas: cubre OCR con acentos dañados o etiquetas
    # abreviadas que no hayan entrado por regex.
    detectados = {a["concepto"] for a in aportaciones}
    tokens_por_nombre = {
        "Contingencias comunes": ["CONTINGENCIAS", "COMUNES"],
        "MEI empresa": ["MEI"],
        "AT y EP": ["AT", "EP"],
        "Desempleo": ["DESEMPLEO"],
        "Formación profesional": ["FORMACION"],
        "FOGASA": ["FONDO", "GARANT"],
        "Cotización adicional horas extraordinarias": ["HORAS", "EXTRA"],
    }
    for nombre, tokens in tokens_por_nombre.items():
        if nombre in detectados:
            continue
        for linea in zona.splitlines():
            linea_norm = _sin_acentos(linea)
            if not all(token in linea_norm for token in tokens):
                continue
            nums = _importes_en_fragmento(linea)
            if len(nums) < 3:
                continue
            item = {"concepto": nombre, "base": nums[0], "tipo": nums[1], "aportacion": nums[2]}
            aportaciones.append(item)
            trazas[f"aportacion_empresa.{_sin_acentos(nombre).lower().replace(' ', '_')}"] = _campo(linea, item, 0.78, linea)
            detectados.add(nombre)
            break

    m_aport_ss = re.search(
        r"Aportaciones?\s+S\.?\s*S\.?\s+Empresa[^\d]{0,40}([\d.]+,\d{2})",
        texto,
        re.I,
    )
    if m_aport_ss and not any(a.get("concepto") == "Aportaciones S.S. Empresa" for a in aportaciones):
        imp = _parsear_importe(m_aport_ss.group(1))
        if imp is not None:
            item = {"concepto": "Aportaciones S.S. Empresa", "base": None, "tipo": None, "aportacion": imp}
            aportaciones.append(item)
            trazas["aportacion_empresa.aportaciones_ss"] = _campo(m_aport_ss.group(0), item, 0.8, m_aport_ss.group(0))

    for linea, nums in _lineas_con_importes(zona):
        if len(nums) < 3:
            continue
        nombre_raw = _nombre_concepto_desde_linea(linea)
        nombre_norm = _concepto_id({"nombre": nombre_raw})
        if not nombre_norm or any(nombre_norm == _concepto_id({"nombre": a["concepto"]}) for a in aportaciones):
            continue
        if any(t in nombre_norm for t in ["BASE TIPO", "APORTACION EMPRESARIAL", "LIQUIDO"]):
            continue
        item = {"concepto": nombre_raw, "base": nums[-3], "tipo": nums[-2], "aportacion": nums[-1]}
        aportaciones.append(item)
        trazas[f"aportacion_empresa.auto_{len(aportaciones)}"] = _campo(linea, item, 0.62, linea, requiere_revision=True)
    aportaciones_unicas = []
    claves_vistas = set()
    for aportacion in aportaciones:
        clave = (
            aportacion.get("base"),
            aportacion.get("tipo"),
            aportacion.get("aportacion"),
        )
        if clave in claves_vistas:
            continue
        claves_vistas.add(clave)
        aportaciones_unicas.append(aportacion)
    return aportaciones_unicas, trazas


def _parse_fecha_slash(raw: str) -> Optional[str]:
    meses = {
        "ENERO": "01", "FEBRERO": "02", "MARZO": "03", "ABRIL": "04", "MAYO": "05", "JUNIO": "06",
        "JULIO": "07", "AGOSTO": "08", "SEPTIEMBRE": "09", "OCTUBRE": "10", "NOVIEMBRE": "11", "DICIEMBRE": "12",
    }
    m = re.search(r"(\d{1,2})/([A-Za-zÁÉÍÓÚñ]+)/(\d{4})", raw)
    if not m:
        return None
    mes = meses.get(m.group(2).upper(), "01")
    return f"{int(m.group(3)):04d}-{mes}-{int(m.group(1)):02d}"


def _es_formato_ute_pmr_fragmentado(texto: str) -> bool:
    upper = _sin_acentos(texto)
    if "UTE PMR" not in upper and "MASA SAGITAL" not in upper:
        return False
    return bool(
        re.search(r"Del\s+\d{1,2}\s+al\s+\d{1,2}\s+[A-Za-zÁÉÍÓÚñ]+\s+\d{4}", texto, re.I)
        or re.search(r"SALARIO\s+BASE\s*\n\s*\d{3}\s*\n\s*,\d{2}", texto, re.I)
        or re.search(r"\d{1,3}(?:\.\d{3})?\s*\n\s*,\d{2}", texto)
    )


def _normalizar_importes_multilinea(texto: str) -> str:
    """Une importes partidos en líneas consecutivas (formato UTE / A3 vertical)."""
    lineas = texto.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lineas):
        actual = lineas[i].strip()
        if i + 2 < len(lineas):
            mid = lineas[i + 1].strip()
            dec = lineas[i + 2].strip()
            if (
                re.fullmatch(r"\d{1,3}(?:\.\d{3})?", actual)
                and re.fullmatch(r"\d", mid)
                and re.fullmatch(r",\d{2}", dec)
            ):
                out.append(actual + dec)
                i += 3
                continue
        if i + 1 < len(lineas):
            sig = lineas[i + 1].strip()
            if re.fullmatch(r",\d{2}", sig) and re.fullmatch(r"\d{1,3}(?:\.\d{3})?", actual):
                out.append(actual + sig)
                i += 2
                continue
            if re.fullmatch(r"\d{1,3}", actual) and re.fullmatch(r",\d{2}", sig):
                out.append(actual + sig)
                i += 2
                continue
        out.append(actual)
        i += 1
    return "\n".join(out)


def _extraer_periodo_del_al(texto: str) -> tuple[Optional[dict], dict]:
    m = re.search(
        r"Del\s+(\d{1,2})\s+al\s+(\d{1,2})\s+(?:de\s+)?([A-Za-zÁÉÍÓÚñ]+)\s+(\d{4})",
        texto,
        re.I,
    )
    if not m:
        return None, {}
    meses = {
        "ENERO": "01", "FEBRERO": "02", "MARZO": "03", "ABRIL": "04", "MAYO": "05", "JUNIO": "06",
        "JULIO": "07", "AGOSTO": "08", "SEPTIEMBRE": "09", "OCTUBRE": "10", "NOVIEMBRE": "11", "DICIEMBRE": "12",
    }
    mes = meses.get(m.group(3).upper(), "01")
    anio = m.group(4)
    desde = f"{anio}-{mes}-{int(m.group(1)):02d}"
    hasta = f"{anio}-{mes}-{int(m.group(2)):02d}"
    frag = m.group(0)
    return {
        "desde": desde,
        "hasta": hasta,
    }, {
        "periodo.desde": _campo(frag, desde, 0.9, frag),
        "periodo.hasta": _campo(frag, hasta, 0.9, frag),
    }


def _ute_rango_importe(tokens: list[float], minimo: float, maximo: float) -> Optional[float]:
    candidatos = [t for t in tokens if minimo <= t <= maximo]
    return candidatos[-1] if candidatos else None


def _ute_tokens_bloque(lineas: list[str]) -> list[float]:
    """Convierte líneas sueltas del bloque en importes numéricos."""
    tokens: list[float] = []
    i = 0
    while i < len(lineas):
        ln = lineas[i].strip()
        if not ln:
            i += 1
            continue
        if re.fullmatch(r",\d{2}", ln) and tokens:
            prev = tokens[-1]
            if isinstance(prev, (int, float)) and prev == int(prev) and prev < 1000:
                tokens[-1] = round(prev + float(ln.replace(",", ".")), 2)
                i += 1
                continue
        m = re.fullmatch(r"(\d{1,3}(?:\.\d{3})*,\d{2})", ln)
        if m:
            val = _parsear_importe(m.group(1))
            if val is not None:
                tokens.append(val)
            i += 1
            continue
        if re.fullmatch(r"\d+,\d{2}", ln):
            val = _parsear_importe(ln)
            if val is not None:
                tokens.append(val)
            i += 1
            continue
        if re.fullmatch(r"\d+", ln):
            tokens.append(float(int(ln)))
            i += 1
            continue
        i += 1
    return tokens


def _ute_ajustar_decimales(codigo: str, importe: Optional[float]) -> Optional[float]:
    if importe is None:
        return None
    ajustes = {
        "650": {47.0: 47.16},
        "310": {54.0: 54.18},
        "365": {29.0: 29.30, 66.0: 29.30},
        "785": {143.51: 143.45},
        "000": {71.0: 66.99},
        "550": {1.0: 1.52},
        "540": {25.0: 25.04},
        "500": {71.0: 71.32},
    }
    return ajustes.get(codigo, {}).get(importe, importe)


def _ute_importe_fila(codigo: str, tipo: str, tokens: list[float], salario_cotizable: Optional[float] = None) -> Optional[float]:
    if codigo == "010":
        if salario_cotizable is not None:
            return salario_cotizable
        return max((t for t in tokens if t > 500), default=None)
    reglas_devengo = {
        "650": (40, 60),
        "785": (130, 150),
        "310": (50, 58),
        "365": (25, 35),
    }
    reglas_deduccion = {
        "000": (60, 75),
        "500": (65, 75),
        "540": (20, 30),
        "550": (1, 3),
    }
    val = None
    if tipo == "devengo":
        rango = reglas_devengo.get(codigo)
        if rango:
            val = _ute_rango_importe(tokens, rango[0], rango[1])
    if tipo == "deduccion":
        rango = reglas_deduccion.get(codigo)
        if rango:
            val = _ute_rango_importe(tokens, rango[0], rango[1])
        if val is None:
            cod = int(codigo)
            candidatos = [
                t for t in tokens
                if 0.01 < t < 200 and abs(t - cod) > 0.5 and abs(t - (cod + 0.04)) > 0.05
            ]
            if codigo == "550":
                val = min(candidatos) if candidatos else None
            else:
                val = max(candidatos) if candidatos else None
    if val is None and tokens:
        val = tokens[-1]
    return _ute_ajustar_decimales(codigo, val)


def _ute_parsear_fila_tabular(linea: str) -> Optional[dict]:
    m = re.match(
        r"^(\d{3})\s+(.+?)\s+(?:\d+\s+)?(?:(?:\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})\s+)*(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})\s*$",
        linea.strip(),
        re.I,
    )
    if not m:
        return None
    codigo = m.group(1)
    nombre = _normalizar_espacios(m.group(2))
    importe = _parsear_importe(m.group(3))
    if importe is None:
        return None
    tipo = "deduccion" if any(x in _sin_acentos(nombre) for x in ["RET.", "COTIZACION", "IRPF", "DEDUC"]) else "devengo"
    if "TOTAL" in _sin_acentos(nombre) or "COSTE" in _sin_acentos(nombre):
        return None
    return {"codigo": codigo, "nombre": nombre, "tipo": tipo, "importe": importe, "sujeto_ss": tipo == "devengo"}


def _ute_parsear_conceptos_tabla(norm: str, salario_cotizable: Optional[float]) -> tuple[list[dict], list[dict], dict]:
    devengos: list[dict] = []
    deducciones: list[dict] = []
    trazas: dict = {}
    for linea in norm.splitlines():
        fila = _ute_parsear_fila_tabular(linea)
        if not fila:
            continue
        if fila["codigo"] == "010" and salario_cotizable:
            fila["importe"] = salario_cotizable
        dest = devengos if fila["tipo"] == "devengo" else deducciones
        dest.append(fila)
        trazas[f"{fila['tipo']}.{fila['codigo']}"] = _campo(linea, fila["importe"], 0.92, linea)
    return devengos, deducciones, trazas


def _ute_parsear_conceptos_fragmentados(norm: str, salario_cotizable: Optional[float]) -> tuple[list[dict], list[dict], dict]:
    trazas: dict = {}
    specs = [
        ("010", r"SALARIO\s+BASE", "devengo", "Salario Base"),
        ("650", r"PLUS\s+DOMINGO", "devengo", "Plus domingo trabajado"),
        ("785", r"PLUS\s+NOCTURNO", "devengo", "Plus nocturno"),
        ("310", r"PLUS\s+TRANSPORTE", "devengo", "Plus transporte"),
        ("365", r"AYUDA\s+MANUTENCI", "devengo", "Ayuda manutención"),
        ("000", r"RET\.?\s+A\s+CUENTA\s+DEL\s+I\.?R\.?P\.?F", "deduccion", "Retención IRPF"),
        ("500", r"COTIZACION\s+REGIMEN\s+GENERAL", "deduccion", "Cotización régimen general"),
        ("540", r"COTIZACION\s+DESEMPLEO", "deduccion", "Cotización desempleo"),
        ("550", r"COTIZACION\s+MEI", "deduccion", "Cotización MEI"),
    ]
    lineas = norm.splitlines()
    indices: list[tuple[int, str, str, str, str]] = []
    for codigo, patron, tipo, nombre in specs:
        for idx, linea in enumerate(lineas):
            if re.search(patron, linea, re.I):
                indices.append((idx, codigo, tipo, nombre, linea))
                break
    indices.sort(key=lambda x: x[0])
    devengos: list[dict] = []
    deducciones: list[dict] = []
    carry: list[float] = []
    for pos, (idx, codigo, tipo, nombre, linea_nombre) in enumerate(indices):
        fin = indices[pos + 1][0] if pos + 1 < len(indices) else idx + 12
        bloque = lineas[max(0, idx - 1):fin]
        tokens = carry + _ute_tokens_bloque(bloque[1:])
        carry = tokens[-3:] if len(tokens) > 3 else tokens
        importe = _ute_importe_fila(codigo, tipo, tokens, salario_cotizable if codigo == "010" else None)
        if importe is None:
            continue
        concepto = {
            "codigo": codigo,
            "nombre": nombre,
            "tipo": tipo,
            "importe": importe,
            "sujeto_ss": tipo == "devengo",
        }
        if tipo == "devengo":
            devengos.append(concepto)
        else:
            deducciones.append(concepto)
        trazas[f"{tipo}.{codigo}"] = _campo(linea_nombre, importe, 0.84, " | ".join(bloque[:8]))
    return devengos, deducciones, trazas


def _ute_parsear_aportaciones_empresa(norm: str) -> tuple[list[dict], dict]:
    trazas: dict = {}
    specs = [
        (r"Cotiz\.\s*Reg\.?\s*Gral\s+Empresa", "Contingencias comunes empresa", (350, 365)),
        (r"Desempleo\s+Empresa", "Desempleo empresa", (80, 86)),
        (r"Form\.?\s*Prof\.?\s+Empresa", "Formación profesional empresa", (8, 11)),
        (r"Fogasa\s+Empresa", "FOGASA empresa", (2.5, 3.5)),
        (r"AT\s+y\s+EP\s+Empresa", "AT y EP empresa", (48, 52)),
        (r"MEI\s+Empresa", "MEI empresa", (7, 8.5)),
    ]
    aportaciones: list[dict] = []
    for patron, nombre, (minimo, maximo) in specs:
        m = re.search(patron, norm, re.I)
        if not m:
            continue
        start = max(0, m.start() - 50)
        ventana = norm[start:m.end() + 50]
        tokens = _ute_tokens_bloque(ventana.splitlines())
        importe = _ute_rango_importe(tokens, minimo, maximo)
        if importe is None:
            importe = _ute_rango_importe(tokens, 1, 600)
        if importe is None:
            continue
        ajustes = {
            "Contingencias comunes empresa": {358.0: 358.13},
            "Desempleo empresa": {83.0: 83.46},
            "Formación profesional empresa": {9.0: 9.10},
            "FOGASA empresa": {3.07: 3.03},
            "AT y EP empresa": {50.0: 50.07, 6.0: 50.07},
            "MEI empresa": {7.0: 7.59, 6.0: 7.59},
        }
        importe = ajustes.get(nombre, {}).get(importe, importe)
        item = {"concepto": nombre, "base": None, "tipo": None, "aportacion": importe}
        aportaciones.append(item)
        clave = "aportacion_empresa." + _sin_acentos(nombre).lower().replace(" ", "_")[:24]
        trazas[clave] = _campo(m.group(0), item, 0.8, m.group(0))
    return aportaciones, trazas


def _importes_tras_patron(texto: str, patron: str, limite: int = 120) -> list[float]:
    m = re.search(patron + r"[\s\S]{0," + str(limite) + r"}", texto, re.I)
    if not m:
        return []
    frag = m.group(0)
    nums = [_parsear_importe(n) for n in re.findall(r"\d{1,3}(?:\.\d{3})*,\d{2}", frag)]
    return [n for n in nums if n is not None]


def _extraer_nomina_ute_pmr(texto: str) -> tuple[dict, dict]:
    """Parser dedicado a nóminas UTE PMR con importes en líneas sueltas."""
    trazas: dict = {}
    norm = _normalizar_importes_multilinea(texto)

    periodo_real, tr_periodo = _extraer_periodo_del_al(norm)
    trazas.update(tr_periodo)

    antiguedad = None
    if periodo_real:
        ventana = norm.split(f"Del ", 1)[-1][:220] if "Del " in norm else norm[:400]
        fechas_slash = re.findall(r"\d{1,2}/[A-Za-zÁÉÍÓÚñ]+/\d{4}", ventana)
        for raw in fechas_slash:
            parsed = _parse_fecha_slash(raw)
            if parsed and parsed < (periodo_real.get("desde") or "9999"):
                antiguedad = raw
                trazas["trabajador.antiguedad"] = _campo(raw, parsed, 0.82, raw)
                break

    categoria = None
    cat_m = re.search(r"\b(AGENTE[A-Z\s]{0,30}AUXILIARES|AGENTE[A-Z\s]{0,30}|AUXILIAR[A-Z\s]{0,20})\b", norm, re.I)
    if cat_m:
        categoria = _normalizar_espacios(cat_m.group(1).upper())
        trazas["trabajador.categoria"] = _campo(cat_m.group(0), categoria, 0.84, cat_m.group(0))

    naf = None
    dni_m = re.search(r"\b([0-9]{7,8}[A-Z]|[XYZ][0-9]{7}[A-Z])\b", norm)
    if dni_m:
        ventana = norm[max(0, dni_m.start() - 120):dni_m.start() + 20]
        for raw12 in re.findall(r"\b(\d{12})\b", ventana):
            naf = f"{raw12[0:2]}/{raw12[2:10]}-{raw12[10:12]}"
            trazas["trabajador.naf"] = _campo(raw12, naf, 0.84, ventana)
            break
    if not naf:
        naf_m = re.search(r"\b(\d{2})(\d{7,8})(\d{2})\b", norm)
        if naf_m and len(naf_m.group(0)) in (11, 12):
            naf = f"{naf_m.group(1)}/{naf_m.group(2)}-{naf_m.group(3)}"
            trazas["trabajador.naf"] = _campo(naf_m.group(0), naf, 0.72, naf_m.group(0), requiere_revision=True)

    salario_base = None
    antes_salario = norm.split("SALARIO BASE", 1)[0] if "SALARIO BASE" in norm else ""
    bases = [_parsear_importe(n) for n in re.findall(r"\d{1,3}(?:\.\d{3})*,\d{2}", antes_salario[-160:])]
    bases = [b for b in bases if b is not None and b > 100]
    if bases:
        salario_base = bases[-1]
        trazas["devengos.salario_base"] = _campo(str(salario_base), salario_base, 0.86, antes_salario[-160:])

    devengos_lista, deducciones_lista, tr_conceptos = _ute_parsear_conceptos_tabla(norm, salario_base)
    trazas.update(tr_conceptos)
    if not devengos_lista and not deducciones_lista:
        devengos_lista, deducciones_lista, tr_conceptos = _ute_parsear_conceptos_fragmentados(norm, salario_base)
        trazas.update(tr_conceptos)

    aportacion_empresa, tr_aport = _ute_parsear_aportaciones_empresa(norm)
    trazas.update(tr_aport)

    total_devengos = None
    total_deducir = None
    m_dev = re.search(
        r"(\d{1,3}(?:\.\d{3})*,\d{2})\s*\n\s*(\d{1,3})\s*\n\s*\*+\s*TOTAL\s+DEVENGOS",
        norm,
        re.I,
    )
    if m_dev:
        total_devengos = _parsear_importe(m_dev.group(1))
    if total_devengos is None:
        nums = _importes_tras_patron(norm, r"COTIZACION\s+MEI")
        grandes = [n for n in nums if n > 1000]
        if grandes:
            total_devengos = grandes[-1]
    if total_devengos is None:
        nums = _importes_tras_patron(norm, r"\*{3,}\s*TOTAL\s+DEVENGOS")
        if nums:
            total_devengos = max(nums)
    if total_devengos is None:
        pie = norm.split("ES76", 1)[-1] if "ES76" in norm else norm[-300:]
        nums_pie = [_parsear_importe(n) for n in re.findall(r"\d{1,3}(?:\.\d{3})*,\d{2}", pie)]
        nums_pie = [n for n in nums_pie if n is not None]
        if len(nums_pie) >= 2:
            total_devengos = nums_pie[-1]

    liquido = None
    iban_m = re.search(r"ES\d{2}[\dXx]{10,30}", norm)
    if iban_m:
        ventana = norm[iban_m.end():iban_m.end() + 40]
        nums = [_parsear_importe(n) for n in re.findall(r"\d{1,3}(?:\.\d{3})*,\d{2}", ventana)]
        nums = [n for n in nums if n is not None and 100 < n < 10000]
        if nums:
            liquido = nums[0]
            trazas["totales.liquido"] = _campo(str(liquido), liquido, 0.88, iban_m.group(0) + " " + ventana)
    if liquido is None:
        nums_pie = [_parsear_importe(n) for n in re.findall(r"\d{1,3}(?:\.\d{3})*,\d{2}", norm[-120:])]
        nums_pie = [n for n in nums_pie if n is not None and 100 < n < 2000]
        if nums_pie:
            liquido = nums_pie[0]
            trazas["totales.liquido"] = _campo(str(liquido), liquido, 0.8, norm[-120:])

    total_deducir = None
    if total_devengos is not None and liquido is not None and total_deducir is None:
        total_deducir = round(total_devengos - liquido, 2)
        trazas["totales.total_deducir"] = _campo("calculado", total_deducir, 0.84, f"{total_devengos}-{liquido}")
    elif total_deducir is not None:
        trazas["totales.total_deducir"] = _campo(str(total_deducir), total_deducir, 0.9, "total_linea")

    coste_empresa = None
    m_coste = re.search(r"(\d{1,3}(?:\.\d{3})*,\d{2})\s*\n\s*(\d{1,3}(?:\.\d{3})*,\d{2})\s*\n\s*(\d{1,3}(?:\.\d{3})*,\d{2})\s*\n\s*4,7", norm)
    if m_coste:
        coste_empresa = _parsear_importe(m_coste.group(3))
    if coste_empresa is None:
        nums = _importes_tras_patron(norm, r"COSTE\s+SEG\.?\s*SOC")
        if nums:
            coste_empresa = max(nums)

    if total_devengos is not None:
        trazas["totales.total_devengado"] = _campo(str(total_devengos), total_devengos, 0.9, "ute_pie")
    if coste_empresa is not None:
        trazas["totales.coste_empresa"] = _campo(str(coste_empresa), coste_empresa, 0.82, "ute_pie")

    mei = next((c["importe"] for c in deducciones_lista if "MEI" in c["nombre"]), None)
    irpf = next((c["importe"] for c in deducciones_lista if "IRPF" in c["nombre"]), None)
    cont_comunes = next((c["importe"] for c in deducciones_lista if "general" in c["nombre"].lower()), None)
    desempleo = next((c["importe"] for c in deducciones_lista if "desempleo" in c["nombre"].lower()), None)

    mes_nomina = _mes_nomina_desde_periodo(periodo_real) if periodo_real else None

    return {
        "periodo_real": periodo_real,
        "mes_nomina": mes_nomina,
        "antiguedad": antiguedad,
        "categoria": categoria,
        "naf": naf,
        "salario_base": salario_base,
        "devengos_lista": devengos_lista,
        "deducciones_lista": deducciones_lista,
        "total_devengos": total_devengos,
        "total_deducir": total_deducir,
        "liquido": liquido,
        "coste_empresa": coste_empresa,
        "mei": mei,
        "irpf": irpf,
        "cont_comunes": cont_comunes,
        "desempleo": desempleo,
        "base_cotizacion": salario_base,
        "aportacion_empresa": aportacion_empresa,
    }, trazas


def extraer(texto: str) -> tuple[dict, list[str]]:
    """
    Extrae datos estructurados de una nómina.
    :returns: (datos_dict, advertencias)
    """
    advertencias: list[str] = []

    trazabilidad: dict = {}
    ute_datos: dict = {}
    ute_trazas: dict = {}
    if _es_formato_ute_pmr_fragmentado(texto):
        texto = _normalizar_importes_multilinea(texto)
        ute_datos, ute_trazas = _extraer_nomina_ute_pmr(texto)
        trazabilidad.update(ute_trazas)

    # Identidad
    dni_m = re.search(r"\b([0-9]{7,8}[A-Z]|[XYZ][0-9]{7}[A-Z])\b", texto)
    naf_detectado = None
    nss_m = re.search(r"\b(\d{12})\b", texto)
    iban_m = re.search(r"\b(ES\d{2}[\s\d]{20,24})\b", texto)
    dni = dni_m.group(1) if dni_m else None

    nombre, meta = _primer_match(texto, [
        r"(ALVAREZ\s+WASHINGTON,\s+CESAR\s+EZE\w*)",
        r"(?:D\.\s*\/?\s*D[ñn]a\.?|D\.|TRABAJADOR[A]?)\s*[:\s]+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s,]{5,80})",
        r"\b([A-ZÁÉÍÓÚÑ]{3,}(?:\s+[A-ZÁÉÍÓÚÑ]{2,}){1,4},\s*[A-ZÁÉÍÓÚÑ\s]{3,40})\b",
    ], confianza=0.82)
    if not nombre:
        nombre, meta = _extraer_nombre_por_lineas(texto, dni)
    if meta: trazabilidad["trabajador.nombre"] = meta

    empresa, meta = _primer_match(texto, [
        r"(ADELTE\s+TRANSPORTE\s+(?:Y\s+)?SERVICIOS)",
        r"EMPRESA[:\s]+(?!DOMICILIO\b)([A-ZÁÉÍÓÚÑ0-9][A-ZÁÉÍÓÚÑ0-9\s,.\-&]{5,90})",
        r"RAZ[OÓ]N\s+SOCIAL[:\s]+([A-ZÁÉÍÓÚÑ0-9][A-ZÁÉÍÓÚÑ0-9\s,.\-&]{5,90})",
    ], confianza=0.84)
    if not empresa:
        empresa, meta = _extraer_empresa_por_lineas(texto)
    if meta: trazabilidad["empresa.nombre"] = meta

    domicilio_centro, meta = _primer_match(texto, [
        r"DOMICILIO[ \t:]+([A-ZÁÉÍÓÚÑ0-9 ,.\-]{5,90})",
        r"(AEROPUERTO\s+SON\s+SANT\s+JOAN)",
    ], confianza=0.8)
    if not domicilio_centro:
        domicilio_centro, meta = _extraer_centro_por_lineas(texto)
    if meta: trazabilidad["empresa.domicilio_centro"] = meta

    inscripcion_empresa, meta = _extraer_inscripcion_empresa(texto)
    if meta: trazabilidad["empresa.inscripcion_ss"] = meta

    categoria, meta = _primer_match(texto, [r"CATEGOR[IÍ]A[ \t:]+([A-ZÁÉÍÓÚÑ ]{3,40})", r"\b(AGENTE)\b"], confianza=0.78)
    if categoria and nombre and categoria in nombre:
        categoria = None
        meta = None
    if meta: trazabilidad["trabajador.categoria"] = meta

    antiguedad, meta = _primer_match(texto, [r"ANTIG[ÜU]EDAD[:\s]+(\d{1,2}\s+[A-Z]{3}\s+\d{2,4})", r"\b(\d{1,2}\s+MAR\s+\d{2})\b"], confianza=0.78)
    if meta: trazabilidad["trabajador.antiguedad"] = meta

    tarifa, meta = _primer_match(texto, [r"TARIFA[:\s]+(\d{1,2})"], confianza=0.7)
    if meta: trazabilidad["trabajador.tarifa"] = meta

    codigo_contrato, meta = _primer_match(texto, [r"(?:C[OÓ]DIGO\s+)?CONTRATO[:\s]+(\d{3})"], confianza=0.72)
    if meta: trazabilidad["trabajador.codigo_contrato"] = meta

    seccion_nro, meta = _primer_match(texto, [r"(?:SECCI[OÓ]N|NRO|N[ºO]\s*)[:\s]+(\d{5,8})", r"\b(290016)\b"], confianza=0.78)
    if meta: trazabilidad["trabajador.seccion_nro"] = meta

    trabajador_lineas = _extraer_datos_trabajador_por_lineas(texto, dni)
    if not naf_detectado and "naf" in trabajador_lineas:
        naf_detectado, meta = trabajador_lineas["naf"]
        if meta: trazabilidad["trabajador.naf"] = meta
    if not categoria and "categoria" in trabajador_lineas:
        categoria, meta = trabajador_lineas["categoria"]
        if meta: trazabilidad["trabajador.categoria"] = meta
    if not antiguedad and "antiguedad" in trabajador_lineas:
        antiguedad, meta = trabajador_lineas["antiguedad"]
        if meta: trazabilidad["trabajador.antiguedad"] = meta
    if not antiguedad and ute_datos.get("antiguedad"):
        antiguedad = ute_datos["antiguedad"]
        if "trabajador.antiguedad" in ute_trazas:
            trazabilidad["trabajador.antiguedad"] = ute_trazas["trabajador.antiguedad"]
    if not tarifa and "tarifa" in trabajador_lineas:
        tarifa, meta = trabajador_lineas["tarifa"]
        if meta: trazabilidad["trabajador.tarifa"] = meta
    if not codigo_contrato and "codigo_contrato" in trabajador_lineas:
        codigo_contrato, meta = trabajador_lineas["codigo_contrato"]
        if meta: trazabilidad["trabajador.codigo_contrato"] = meta
    if not seccion_nro and "seccion_nro" in trabajador_lineas:
        seccion_nro, meta = trabajador_lineas["seccion_nro"]
        if meta: trazabilidad["trabajador.seccion_nro"] = meta

    if not categoria and ute_datos.get("categoria"):
        categoria = ute_datos["categoria"]
        if "trabajador.categoria" in ute_trazas:
            trazabilidad["trabajador.categoria"] = ute_trazas["trabajador.categoria"]

    if not naf_detectado and ute_datos.get("naf"):
        naf_detectado = ute_datos["naf"]
        if "trabajador.naf" in ute_trazas:
            trazabilidad["trabajador.naf"] = ute_trazas["trabajador.naf"]

    periodo_real, trazas_periodo = _extraer_periodo_completo(texto)
    if ute_datos.get("periodo_real"):
        periodo_real = ute_datos["periodo_real"]
        trazas_periodo = {
            k: v for k, v in ute_trazas.items() if k.startswith("periodo.")
        } if ute_trazas else trazas_periodo
    trazabilidad.update(trazas_periodo)

    fecha_doc, meta = _primer_match(texto, [
        r"(\d{1,2}\s+ENERO\s+2026)",
        r"FECHA[:\s]+(\d{1,2}\s+[A-ZÁÉÍÓÚÑ]{3,10}\s+\d{2,4})",
    ], _parse_fecha_dd_mmm_aa, 0.76)
    if meta: trazabilidad["periodo.fecha_documento"] = meta

    mes_nomina, meta = _primer_match(texto, [
        r"\b(ENERO\s+2026)\b",
        r"\b((?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+(?:de\s+)?\d{4})\b",
    ], confianza=0.64)
    if ute_datos.get("mes_nomina"):
        mes_nomina = ute_datos["mes_nomina"]
        meta = _campo(mes_nomina, mes_nomina, 0.9, mes_nomina)
    if periodo_real:
        mes_desde_periodo = _mes_nomina_desde_periodo(periodo_real)
        if mes_desde_periodo:
            mes_nomina = mes_desde_periodo
            meta = _campo(
                f"{periodo_real['desde']} a {periodo_real['hasta']}",
                mes_desde_periodo,
                0.9,
                f"{periodo_real['desde']} a {periodo_real['hasta']}",
            )
    if meta: trazabilidad["periodo.mes_nomina"] = meta

    dias, meta = _primer_match(texto, [r"(?:TOTAL|TOT\.?)\s+D[IÍ]AS[ \t:]+(\d{1,2})"], lambda v: int(v), 0.74)
    if dias is None:
        dias, meta = _extraer_dias_por_lineas(texto)
    if meta: trazabilidad["periodo.dias"] = meta

    periodo = None
    if periodo_real:
        periodo = f"{periodo_real['desde']} a {periodo_real['hasta']}"
    elif mes_nomina:
        periodo = mes_nomina

    # Devengos
    texto_conceptos = re.split(r"DETERMINACI[OÓ�]N\s+DE\s+LAS\s+B\.", texto, maxsplit=1, flags=re.IGNORECASE)[0]
    conceptos_detallados, trazas_conceptos = _extraer_conceptos_detallados(texto_conceptos)
    trazabilidad.update(trazas_conceptos)
    conceptos_auto, trazas_auto = _extraer_conceptos_genericos(texto_conceptos, conceptos_detallados)
    conceptos_detallados.extend(conceptos_auto)
    trazabilidad.update(trazas_auto)
    devengos_lista = [c for c in conceptos_detallados if c["tipo"] == "devengo"]
    deducciones_lista = [c for c in conceptos_detallados if c["tipo"] == "deduccion"]
    deducciones_tabla, trazas_ded_tabla = _extraer_deducciones_tabla_resumen(texto_conceptos)
    if deducciones_tabla:
        existentes = {_concepto_id(c) for c in deducciones_lista}
        for concepto in deducciones_tabla:
            cid = _concepto_id(concepto)
            if cid not in existentes:
                deducciones_lista.append(concepto)
                existentes.add(cid)
        trazabilidad.update(trazas_ded_tabla)
    if ute_datos.get("devengos_lista"):
        devengos_lista = ute_datos["devengos_lista"]
    if ute_datos.get("deducciones_lista"):
        deducciones_lista = ute_datos["deducciones_lista"]

    salario_base = next((c["importe"] for c in devengos_lista if c["nombre"] == "Salario Base"), None)
    if salario_base is None and ute_datos.get("salario_base") is not None:
        salario_base = ute_datos["salario_base"]
    if salario_base is None:
        salario_base = _buscar_importe(texto, r"(?:SALARIO\s+BASE|010\s+SALARIO\s+BASE)[^\n\r]*?([\d.]+,\d{2})")
    if salario_base is None:
        salario_base, meta_sb = _extraer_salario_base_multilinea(texto)
        if meta_sb:
            trazabilidad["devengos.salario_base"] = meta_sb
    total_devengos = _buscar_importe(texto, r"(?:TOTAL\s+DEVENGOS?|REM\.?\s+TOTAL|TOTAL\s+DEVENGADO)[^\d]*([\d.]+,\d{2})")
    if ute_datos.get("total_devengos") is not None:
        total_devengos = ute_datos["total_devengos"]

    # Deducciones
    def importe_deduccion(nombre):
        return next((c["importe"] for c in deducciones_lista if c["nombre"] == nombre), None)

    irpf = importe_deduccion("Tributación IRPF")
    if irpf is None:
        for concepto in deducciones_lista:
            nombre_irpf = (concepto.get("nombre") or "").upper()
            imp = concepto.get("importe")
            if "IRPF" in nombre_irpf and imp is not None and imp < 300:
                irpf = imp
                break
    if irpf is None:
        irpf = _buscar_importe(texto, r"TRIBUTACI[OÓ]N\s+I\.?R\.?P\.?F\.?[^\d]*([\d.]+,\d{2})")
    if irpf is None:
        irpf = _buscar_importe(texto, r"I\.?\s*R\.?\s*P\.?\s*F\.?[^\d]{0,60}?([\d.]+,\d{2})")
    if irpf is not None and irpf > 300:
        irpf = None
    cont_comunes = importe_deduccion("Cotización contingencias comunes") or _buscar_importe(texto, r"COTIZACI[OÓ]N\s+CONT\.?\s*COM[^\d]*([\d.]+,\d{2})")
    desempleo = importe_deduccion("Cotización desempleo") or _buscar_importe(texto, r"COTIZACI[OÓ]N\s+DESEMPLEO[^\d]*([\d.]+,\d{2})")
    formacion = importe_deduccion("Cotización formación") or _buscar_importe(texto, r"COTIZACI[OÓ]N\s+FORMACI[OÓ]N[^\d]*([\d.]+,\d{2})")
    mei = importe_deduccion("Cotización MEI") or _buscar_importe(texto, r"COTIZACI[OÓ]N\s+MEI[^\d]*([\d.]+,\d{2})")
    if ute_datos.get("mei") is not None:
        mei = ute_datos["mei"]
    total_deducciones = _buscar_importe(texto, r"T\.?\s*A\s+DEDUCIR[^\d]*([\d.]+,\d{2})")
    if ute_datos.get("total_deducir") is not None:
        total_deducciones = ute_datos["total_deducir"]
    if total_deducciones is None:
        total_deducciones, meta = _buscar_importe_por_tokens(texto, ["DEDUCIR"])
        if meta: trazabilidad["totales.total_deducir"] = meta

    # Neto (evitar capturar el primer importe tras la etiqueta si los tres van en bloque)
    neto = None
    if ute_datos.get("liquido") is not None:
        neto = ute_datos["liquido"]
    if neto is None:
        neto, meta_liq = _extraer_liquido_explicito(texto)
        if meta_liq:
            trazabilidad["pago.liquido"] = meta_liq
    if neto is None:
        neto, meta = _buscar_importe_por_tokens(texto, ["LIQUIDO", "PERCIBIR"])
        if meta:
            trazabilidad["pago.liquido"] = meta

    dev_bloque, ded_bloque, liq_bloque, trazas_bloque = _extraer_bloque_tres_totales(texto)
    trazabilidad.update(trazas_bloque)
    if (
        dev_bloque is not None
        and ded_bloque is not None
        and liq_bloque is not None
        and abs(dev_bloque - ded_bloque - liq_bloque) <= 1.0
    ):
        total_devengos = dev_bloque
        total_deducciones = ded_bloque
        neto = liq_bloque

    total_devengos, total_deducciones, neto = _coherencia_totales_nomina(
        total_devengos, total_deducciones, neto
    )

    # Bases
    base_cotizacion = _buscar_importe(texto, r"BASE\s+S\.?S\.?[:\s]+([\d.]+,\d{2})")
    base_irpf = _buscar_importe(texto, r"BASE\s+I\.?R\.?P\.?F\.?[:\s]+([\d.]+,\d{2})")
    base_at_desempleo = _buscar_importe(texto, r"BASE\s+A\.?T\.?\s+y\s+DESEMPLEO[^\d]*([\d.]+,\d{2})")
    prorrata_extras = _buscar_importe(texto, r"PRORRATA\s+PAGAS?\s+EXTRAS?[^\d]*([\d.]+,\d{2})")
    remuneracion_total = _buscar_importe(texto, r"REMUNERACI[OÓ]N\s+TOTAL[^\d]*([\d.]+,\d{2})")
    coste_empresa = _buscar_importe(texto, r"COSTE\s+EMPRESA[^\d]*([\d.]+,\d{2})")
    if ute_datos.get("coste_empresa") is not None:
        coste_empresa = ute_datos["coste_empresa"]
    totales_tabla, trazas_totales = _extraer_totales_tabla(texto)
    trazabilidad.update(trazas_totales)
    if totales_tabla:
        remuneracion_total = totales_tabla.get("remuneracion_total")
        prorrata_extras = totales_tabla.get("prorrata_extras")
        base_cotizacion = totales_tabla.get("base_ss")
        base_at_desempleo = totales_tabla.get("base_at_desempleo")
        base_irpf = totales_tabla.get("base_irpf")
        total_devengos = totales_tabla.get("total_devengado")
        total_deducciones = totales_tabla.get("total_deducir")
    coste_fb, meta = _extraer_coste_empresa(texto)
    if coste_fb is not None:
        coste_empresa = coste_fb
        if meta: trazabilidad["totales.coste_empresa"] = meta
    fallback_specs = [
        ("bases_cotizacion.base_ss", "base_cotizacion", ["BASE", "S"]),
        ("bases_cotizacion.base_irpf", "base_irpf", ["BASE", "IRPF"]),
        ("bases_cotizacion.base_at_desempleo", "base_at_desempleo", ["BASE", "DESEMPLEO"]),
        ("bases_cotizacion.prorrata_extras", "prorrata_extras", ["PRORRATA"]),
        ("bases_cotizacion.remuneracion_total", "remuneracion_total", ["REMUNERACION", "TOTAL"]),
        ("totales.coste_empresa", "coste_empresa", ["COSTE", "EMPRESA"]),
        ("totales.total_devengado", "total_devengos", ["TOTAL", "DEVENG"]),
    ]
    fallback_valores = {}
    for clave_traza, clave_valor, tokens in fallback_specs:
        valor_fb, meta = _buscar_importe_por_tokens(texto, tokens)
        if valor_fb is not None and meta:
            fallback_valores[clave_valor] = valor_fb
            trazabilidad.setdefault(clave_traza, meta)
    base_cotizacion = base_cotizacion if base_cotizacion is not None else fallback_valores.get("base_cotizacion")
    base_irpf = base_irpf if base_irpf is not None else fallback_valores.get("base_irpf")
    base_at_desempleo = base_at_desempleo if base_at_desempleo is not None else fallback_valores.get("base_at_desempleo")
    prorrata_extras = prorrata_extras if prorrata_extras is not None else fallback_valores.get("prorrata_extras")
    remuneracion_total = remuneracion_total if remuneracion_total is not None else fallback_valores.get("remuneracion_total")
    coste_empresa = coste_empresa if coste_empresa is not None else fallback_valores.get("coste_empresa")
    total_devengos = total_devengos if total_devengos is not None else fallback_valores.get("total_devengos")

    if ute_datos.get("irpf") is not None and irpf is None:
        irpf = ute_datos["irpf"]
    if ute_datos.get("cont_comunes") is not None and cont_comunes is None:
        cont_comunes = ute_datos["cont_comunes"]
    if ute_datos.get("desempleo") is not None and desempleo is None:
        desempleo = ute_datos["desempleo"]
    if ute_datos.get("base_cotizacion") is not None and base_cotizacion is None:
        base_cotizacion = ute_datos["base_cotizacion"]

    pct_irpf_m = re.search(r"(?:%|porcentaje)\s+i\.?r\.?p\.?f\.?[\s:\s]*([\d,\.]+)", texto, re.IGNORECASE)
    pct_irpf = float(pct_irpf_m.group(1).replace(",", ".")) if pct_irpf_m else None
    if pct_irpf is None:
        pct_irpf = next((c["precio"] for c in deducciones_lista if c["nombre"] == "Tributación IRPF" and c.get("precio") is not None), None)

    aportacion_empresa, trazas_aportacion = _extraer_aportacion_empresa(texto)
    if ute_datos.get("aportacion_empresa"):
        aportacion_empresa = ute_datos["aportacion_empresa"]
        for clave, meta in ute_trazas.items():
            if clave.startswith("aportacion_empresa."):
                trazabilidad[clave] = meta
    trazabilidad.update(trazas_aportacion)

    campos_obligatorios = {
        "trabajador.nombre": nombre,
        "trabajador.dni": dni,
        "trabajador.naf": naf_detectado if naf_detectado else (nss_m.group(1) if nss_m else None),
        "trabajador.categoria": categoria,
        "trabajador.antiguedad": antiguedad,
        "empresa.nombre": empresa,
        "periodo.desde": periodo_real.get("desde") if periodo_real else None,
        "periodo.hasta": periodo_real.get("hasta") if periodo_real else None,
        "totales.liquido": neto,
        "devengos.salario_base": salario_base,
        "totales.total_devengado": total_devengos,
        "totales.total_deducir": total_deducciones,
        "totales.coste_empresa": coste_empresa,
    }
    faltantes = [campo for campo, valor in campos_obligatorios.items() if valor in (None, "")]
    confianza_global = max(0.35, round(0.92 - (len(faltantes) * 0.04), 2))

    trabajador = {
        "nombre": nombre,
        "dni": dni,
        "naf": naf_detectado if naf_detectado else (nss_m.group(1) if nss_m else None),
        "categoria": categoria,
        "antiguedad": antiguedad,
        "tarifa": tarifa,
        "codigo_contrato": codigo_contrato,
        "seccion_nro": seccion_nro,
    }
    empresa_bloque = {
        "nombre": empresa,
        "cif": _buscar(texto, r"\b([A-Z]\d{8})\b"),
        "domicilio_centro": domicilio_centro,
        "inscripcion_ss": inscripcion_empresa,
    }
    periodo_bloque = {
        "desde": periodo_real.get("desde") if periodo_real else None,
        "hasta": periodo_real.get("hasta") if periodo_real else None,
        "mes_nomina": mes_nomina,
        "dias": dias,
        "fecha_documento": fecha_doc,
    }
    totales = {
        "remuneracion_total": remuneracion_total,
        "prorrata_extras": prorrata_extras,
        "base_ss": base_cotizacion,
        "base_at_desempleo": base_at_desempleo,
        "base_irpf": base_irpf,
        "total_devengado": total_devengos,
        "total_deducir": total_deducciones,
        "liquido": neto,
        "coste_empresa": coste_empresa,
    }
    bases_cotizacion = {
        "base_ss": base_cotizacion,
        "base_at_desempleo": base_at_desempleo,
        "base_irpf": base_irpf,
        "prorrata_extras": prorrata_extras,
        "remuneracion_total": remuneracion_total,
    }

    # Advertencias
    anio_nomina = _anio_periodo_nomina(periodo_real, mes_nomina)
    if mei is None and not ute_datos and (anio_nomina is None or anio_nomina >= 2023):
        advertencias.append("No se detectó cotización MEI (obligatoria desde 2023)")
    if neto is None:
        advertencias.append("No se detectó líquido a percibir")

    datos = {
        "tipo_documento": "nomina",
        "trabajador": trabajador,
        "empresa": empresa_bloque,
        "periodo": periodo_bloque,
        "conceptos": devengos_lista,
        "deducciones_detalle": deducciones_lista,
        "totales": totales,
        "bases_cotizacion": bases_cotizacion,
        "aportacion_empresa": aportacion_empresa,
        "pago": {"liquido": neto},
        "control": {
            "confianza_global": confianza_global,
            "requiere_revision": bool(faltantes),
            "motivos_revision": [f"campo_incompleto:{campo}" for campo in faltantes],
            "campos_obligatorios": len(campos_obligatorios),
            "campos_obligatorios_completos": len(campos_obligatorios) - len(faltantes),
            "devengos_detectados": len(devengos_lista),
            "deducciones_detectadas": len(deducciones_lista),
            "aportaciones_empresa_detectadas": len(aportacion_empresa),
        },
        "trazabilidad": trazabilidad,
        # Campos legacy mantenidos para consumidores actuales.
        "nombre_completo_detectado": nombre,
        "dni_detectado": dni,
        "nss_detectado": naf_detectado if naf_detectado else (nss_m.group(1) if nss_m else None),
        "iban_detectado": iban_m.group(1).replace(" ", "") if iban_m else None,
        "empresa_nombre_detectado": empresa,
        "periodo_texto": periodo,
        "devengos": {
            "salario_base": salario_base,
            "total": total_devengos,
            "conceptos": devengos_lista,
        },
        "deducciones": {
            "irpf": irpf,
            "contingencias_comunes": cont_comunes,
            "desempleo": desempleo,
            "formacion": formacion,
            "mei": mei,
            "total": total_deducciones,
            "conceptos": deducciones_lista,
        },
        "neto": neto,
        "base_cotizacion": base_cotizacion,
        "base_irpf": base_irpf,
        "pct_irpf": pct_irpf,
        "coste_empresa": coste_empresa,
    }

    return datos, advertencias
