"""
EXTRACTOR — Horarios / Cuadrantes de turnos
"""

import re
from datetime import date
from typing import Optional

MESES = {
    "enero": "01", "febrero": "02", "marzo": "03", "abril": "04", "mayo": "05", "junio": "06",
    "julio": "07", "agosto": "08", "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12",
}
MESES_INV = {v: k for k, v in MESES.items()}

CATEGORIAS_ARCHIVO = [
    "AGENTES", "PMR", "AUXILIARES", "RAMP", "HANDLING", "FACTURACION", "SUPERVISORES", "COORDINADORES",
]

CODIGOS_LIBRES = {"L", "D", "X", "-", "V", "F"}
LINEAS_IGNORAR = re.compile(r"^(VARIABLES|L|M|X|J|V|S|D|LF|BM|VC|EN|FE|MA|AB|JU|JL|AG|SE|OC|NO|DI)$", re.I)
MESES_LINEA = re.compile(r"^(ENERO|FEBRERO|MARZO|ABRIL|MAYO|JUNIO|JULIO|AGOSTO|SEPTIEMBRE|OCTUBRE|NOVIEMBRE|DICIEMBRE)$", re.I)


def _hints_desde_nombre(nombre_archivo: str | None) -> dict:
    hints: dict = {}
    if not nombre_archivo:
        return hints
    upper = nombre_archivo.upper()
    if re.search(r"MENSUAL(?:ES)?", upper):
        hints["periodo_tipo"] = "mensual"
    elif re.search(r"QUINCENAL(?:ES)?|QUINCENA", upper):
        hints["periodo_tipo"] = "quincenal"
    elif re.search(r"SEMANAL(?:ES)?|SEMANA", upper):
        hints["periodo_tipo"] = "semanal"
    for cat in CATEGORIAS_ARCHIVO:
        if cat in upper:
            hints["categoria"] = cat.lower()
            break
    m = re.search(r"\b(0?[1-9]|1[0-2])[-_/](20\d{2})\b", nombre_archivo)
    if m:
        mes = m.group(1).zfill(2)
        hints["mes"] = mes
        hints["anio"] = m.group(2)
        hints["mes_iso"] = f"{m.group(2)}-{mes}"
    m2 = re.search(r"\b(20\d{2})[-_/](0?[1-9]|1[0-2])\b", nombre_archivo)
    if m2:
        mes = m2.group(2).zfill(2)
        hints["mes"] = mes
        hints["anio"] = m2.group(1)
        hints["mes_iso"] = f"{m2.group(1)}-{mes}"
    return hints


def _inferir_anio(mes_num: int, ref: date | None = None) -> str:
    ref = ref or date.today()
    if mes_num < ref.month - 2:
        return str(ref.year + 1)
    if mes_num > ref.month + 2:
        return str(ref.year - 1)
    return str(ref.year)


def _extraer_periodo_cuadrante(texto: str, nombre_archivo: str | None = None) -> tuple[dict, list[str]]:
    advertencias: list[str] = []
    hints = _hints_desde_nombre(nombre_archivo)
    tipo = hints.get("periodo_tipo", "desconocido")
    mes = hints.get("mes")
    anio = hints.get("anio")
    mes_nombre = None
    quincena = None
    semana = None

    if re.search(r"quincena\s*1|1[ªa]\s*quincena|del\s+1\s+al\s+15", texto, re.I):
        tipo, quincena = "quincenal", 1
    elif re.search(r"quincena\s*2|2[ªa]\s*quincena|del\s+16\s+al", texto, re.I):
        tipo, quincena = "quincenal", 2
    elif re.search(r"semana\s*(\d{1,2})", texto, re.I):
        tipo = "semanal"
        semana = int(re.search(r"semana\s*(\d{1,2})", texto, re.I).group(1))
    elif re.search(r"mensual|turnos?\s+mensual|cuadrante\s+mensual", texto, re.I) or hints.get("periodo_tipo") == "mensual":
        tipo = "mensual"

    m = re.search(
        r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+(?:de\s+)?(20\d{2})",
        texto, re.I,
    )
    if m:
        mes_nombre = m.group(1).lower()
        mes = MESES[mes_nombre]
        anio = m.group(2)

    if not mes:
        m_suelto = re.search(
            r"(?:^|\n)\s*(ENERO|FEBRERO|MARZO|ABRIL|MAYO|JUNIO|JULIO|AGOSTO|SEPTIEMBRE|OCTUBRE|NOVIEMBRE|DICIEMBRE)\s*(?:\n|$)",
            texto, re.I | re.M,
        )
        if m_suelto:
            mes_nombre = m_suelto.group(1).lower()
            mes = MESES.get(mes_nombre)

    m_num = re.search(r"\b(0?[1-9]|1[0-2])[/\-](20\d{2})\b", texto)
    if m_num:
        mes = m_num.group(1).zfill(2)
        anio = m_num.group(2)
        mes_nombre = MESES_INV.get(mes)

    if mes and not anio:
        anio = _inferir_anio(int(mes))
        advertencias.append("anio_cuadrante_inferido")

    if not mes:
        advertencias.append("mes_cuadrante_no_detectado")
    if tipo == "desconocido" and mes:
        tipo = "mensual"

    mes_iso = f"{anio}-{mes}" if mes and anio else None
    meta = {"tipo": tipo}
    if mes:
        meta["mes"] = mes
    if anio:
        meta["anio"] = anio
    if mes_iso:
        meta["mes_iso"] = mes_iso
    if mes_nombre:
        meta["mes_nombre"] = mes_nombre
    if quincena:
        meta["quincena"] = quincena
    if semana:
        meta["semana"] = semana
    etiqueta_partes = []
    if mes_nombre:
        etiqueta_partes.append(mes_nombre.upper())
    elif mes_iso:
        etiqueta_partes.append(mes_iso)
    if tipo != "desconocido":
        etiqueta_partes.append(f"({tipo})")
    if etiqueta_partes:
        meta["etiqueta"] = " ".join(etiqueta_partes)

    return meta, advertencias


def _extraer_categoria(texto: str, nombre_archivo: str | None = None) -> str | None:
    hints = _hints_desde_nombre(nombre_archivo)
    if hints.get("categoria"):
        return hints["categoria"]
    m = re.search(r"(?:cuadrante|turnos?)\s+(?:de\s+|mensual(?:es)?\s+)?([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]{2,30})", texto, re.I)
    if m:
        cat = " ".join(m.group(1).strip().split()[:3]).lower()
        if not re.search(r"mensual|quincenal|semanal|turno", cat):
            return cat
    return None


def _limpiar_nombre_cuadrante(nombre: str) -> str:
    return re.sub(r"\s+(BM|VC|LF|PM|IT|LC)\s*$", "", nombre.strip(), flags=re.I)


def _es_nombre_trabajador(linea: str) -> bool:
    primera = linea.split("\t")[0].strip()
    t = primera if len(primera) >= 6 else linea.strip()
    if len(t) < 6 or len(t) > 60:
        return False
    if re.match(r"^VARIABLES\b", t, re.I):
        return False
    if LINEAS_IGNORAR.match(t) or MESES_LINEA.match(t):
        return False
    if t.isdigit():
        return False
    if re.search(r"\d{1,2}:\d{2}", t):
        return False
    if re.match(r"^[A-Z]{1,3}(\s+[A-Z]{1,3}){4,}$", t):
        return False
    if "\t" in linea and len(t.split()) <= 2 and len(t) <= 12:
        return False
    return bool(re.match(r"^[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ0-9\s,.'-]{4,}$", t))


def _parsear_fila_tabulada(linea: str) -> dict | None:
    if "\t" not in linea:
        return None
    celdas = [c.strip() for c in linea.split("\t") if c.strip()]
    if len(celdas) < 8:
        return None
    if not _es_nombre_trabajador(celdas[0]):
        return None
    codigos = []
    for celda in celdas[1:]:
        codigos.extend(_tokenizar_turnos(celda))
    if len(codigos) < 7:
        return None
    return {"nombre_raw": _limpiar_nombre_cuadrante(celdas[0]), "codigos": codigos}


def _tokenizar_turnos(linea: str) -> list[str]:
    return [t.upper() for t in re.findall(r"\b(?:\d{1,2}:\d{2}|[A-Z]{1,3})\b", linea, re.I)]


def _extraer_filas(texto: str) -> list[dict]:
    filas: list[dict] = []
    lineas = texto.splitlines()

    for linea in lineas:
        tab = _parsear_fila_tabulada(linea)
        if tab:
            filas.append(tab)
    if filas:
        return filas

    for i, linea in enumerate(lineas):
        linea = linea.strip()
        if not _es_nombre_trabajador(linea):
            continue
        codigos: list[str] = []
        for j in range(i + 1, min(i + 20, len(lineas))):
            shift = lineas[j].strip()
            if not shift:
                continue
            if _es_nombre_trabajador(shift) or MESES_LINEA.match(shift):
                break
            if re.match(r"^\d{1,2}$", shift):
                continue
            tokens = _tokenizar_turnos(shift)
            if tokens:
                codigos.extend(tokens)
        if len(codigos) >= 7:
            filas.append({"nombre_raw": _limpiar_nombre_cuadrante(linea), "codigos": codigos})

    if filas:
        return filas

    for linea in lineas:
        partes = re.split(r"\s{2,}", linea.strip())
        if len(partes) < 3:
            continue
        nombre_raw = partes[0].strip()
        if not _es_nombre_trabajador(nombre_raw):
            continue
        tokens = [p.strip() for p in partes[1:] if p.strip()]
        codigos = [
            t.upper() for t in tokens
            if re.match(r"^\d{1,2}:\d{2}$", t) or (len(t) <= 3 and re.match(r"^[A-Z0-9LDVFMTNx\-]+$", t, re.I))
        ]
        if len(codigos) >= 7:
            filas.append({"nombre_raw": _limpiar_nombre_cuadrante(nombre_raw), "codigos": codigos})
    return filas


def extraer(
    texto: str,
    leyenda_turnos: Optional[dict] = None,
    horas_contrato: Optional[float] = None,
    nombre_archivo: str | None = None,
) -> tuple[dict, list[str]]:
    advertencias: list[str] = []
    leyenda = leyenda_turnos or {}

    empresa_m = re.search(r"(?:empresa|centro de trabajo|establecimiento)[:\s]+([^\n\r]{3,60})", texto, re.IGNORECASE)
    empresa = empresa_m.group(1).strip() if empresa_m else ("ADELTE TRANSPORTE Y SERVICIOS" if re.search(r"\bADELTE\b", texto, re.I) else None)

    periodo_meta, adv_periodo = _extraer_periodo_cuadrante(texto, nombre_archivo)
    advertencias.extend(adv_periodo)
    categoria = _extraer_categoria(texto, nombre_archivo)
    periodo = periodo_meta.get("mes_iso") or periodo_meta.get("etiqueta")

    filas = _extraer_filas(texto)

    turnos_detectados: dict[str, int] = {}
    for fila in filas:
        for cod in fila["codigos"]:
            turnos_detectados[cod] = turnos_detectados.get(cod, 0) + 1

    personas_detectadas = [f["nombre_raw"] for f in filas]
    es_cuadrante_grupal = len(filas) > 1

    for fila in filas:
        if fila["nombre_raw"].upper() == "VARIABLES":
            continue
        consec = max_consec = 0
        for cod in fila["codigos"]:
            if cod not in CODIGOS_LIBRES and not re.match(r"^\d{1,2}:\d{2}$", cod):
                consec += 1
                max_consec = max(max_consec, consec)
            elif re.match(r"^\d{1,2}:\d{2}$", cod):
                consec += 1
                max_consec = max(max_consec, consec)
            else:
                consec = 0
        if max_consec > 6:
            advertencias.append(f"{fila['nombre_raw']}: {max_consec} días consecutivos sin descanso")

    datos = {
        "nombre_completo_detectado": personas_detectadas[0] if len(personas_detectadas) == 1 else None,
        "empresa": empresa,
        "periodo": periodo,
        "periodo_mes": periodo_meta.get("mes_iso"),
        "periodo_tipo": periodo_meta.get("tipo"),
        "periodo_cuadrante": periodo_meta,
        "categoria": categoria,
        "es_cuadrante_grupal": es_cuadrante_grupal,
        "personas_detectadas": personas_detectadas,
        "filas": filas,
        "turnos_detectados": turnos_detectados,
    }

    return datos, advertencias
