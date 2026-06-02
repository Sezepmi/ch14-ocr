"""
EXTRACTOR — Sanciones disciplinarias
Extrae hechos imputados y clasifica motivos para diagnóstico/revisión.
"""

import re
from typing import Optional

TIPOS_SANCION = [
    (r"despido\s+disciplinario", "despido_disciplinario"),
    (r"suspensi[oó]n\s+de\s+empleo\s+y\s+sueldo", "suspension_empleo_sueldo"),
    (r"sancion\s+empleo\s+y\s+sueldo", "suspension_empleo_sueldo"),
    (r"amonestaci[oó]n\s+escrita", "amonestacion_escrita"),
    (r"amonestaci[oó]n\s+verbal", "amonestacion_verbal"),
    (r"carta\s+de\s+sanci[oó]n", "amonestacion_escrita"),
    (r"apertura\s+de\s+expediente", "otra"),
]

GRADOS = [
    (r"falta\s+muy\s+grave|faltas\s+muy\s+graves", "muy_grave"),
    (r"falta\s+grave|faltas\s+graves", "grave"),
    (r"falta\s+leve|faltas\s+leves", "leve"),
    (r"muy\s+grave", "muy_grave"),
    (r"\bgrave\b", "grave"),
    (r"\bleve\b", "leve"),
]

MESES = {
    "enero": "01", "febrero": "02", "marzo": "03", "abril": "04", "mayo": "05", "junio": "06",
    "julio": "07", "agosto": "08", "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12",
}

CATALOGO_MOTIVOS = [
    (r"falsificaci[oó]n|t[ií]pex|documento\s+no\s+cierto|justificante\s+anterior\s+reutilizado|modificado\s+para\s+hacer\s+uso", "falsificacion_justificante", "Falsificación o manipulación de justificante", 0.92),
    (r"no\s+asisti[oó]|falta\s+de\s+asistencia|ausencia\s+injustificada|falta\s+al\s+trabajo|no\s+acudi[oó]\s+al\s+trabajo", "ausencia_injustificada", "Ausencia o falta de asistencia injustificada", 0.88),
    (r"abandon[oó]\s+(?:el\s+)?puesto|abandono\s+del\s+puesto|marcharse\s+debido|dej[oó]\s+su\s+puesto", "abandono_puesto", "Abandono del puesto de trabajo", 0.9),
    (r"no\s+justific[oó]|sin\s+justificar|no\s+ha\s+justificado|no\s+ha\s+aportado", "falta_justificacion", "Falta de justificación de ausencia o abandono", 0.85),
    (r"disciplina\s+laboral|incumplimiento\s+contractual|incumplimiento\s+de\s+deberes|deberes\s+b[aá]sicos", "incumplimiento_deberes", "Incumplimiento de deberes laborales", 0.8),
    (r"puntualidad|retraso|horario|jornada\s+laboral|permanecer\s+en\s+el\s+puesto", "incumplimiento_horario", "Incumplimiento de horario o permanencia", 0.75),
    (r"desobediencia|desacato|reiterad", "desobediencia_reiteracion", "Desobediencia o reiteración de faltas", 0.78),
    (r"baja\s+m[eé]dica|servicio\s+m[eé]dico|justificante", "justificacion_medica", "Cuestionamiento de baja o justificante médico", 0.7),
]


def _fecha_extensa(dia: str, mes_raw: str, anio: str) -> Optional[str]:
    mes = MESES.get(mes_raw.lower())
    if not mes:
        return None
    return f"{anio}-{mes}-{dia.zfill(2)}"


def _fecha(texto: str) -> Optional[str]:
    m = re.search(r"\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\b", texto)
    if m:
        d, mo, y = m.group(1).zfill(2), m.group(2).zfill(2), m.group(3)
        if int(mo) <= 12:
            return f"{y}-{mo}-{d}"
    m2 = re.search(
        r"\ba\s+(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+de\s+(\d{4})",
        texto, re.IGNORECASE
    ) or re.search(
        r"(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+de\s+(\d{4})",
        texto, re.IGNORECASE
    )
    if m2:
        return _fecha_extensa(m2.group(1), m2.group(2), m2.group(3))
    return None


def _capitalizar_palabras(valor: str) -> str:
    return " ".join(p.capitalize() for p in valor.split())


def _nombre_desde_slug_trabajador(slug: str) -> Optional[str]:
    partes = [p for p in slug.split("-") if p]
    if len(partes) < 2:
        return None
    nombre = partes[-1]
    apellidos = " ".join(partes[:-1])
    completo = f"{_capitalizar_palabras(nombre)} {_capitalizar_palabras(apellidos)}".strip()
    return completo if len(completo) >= 5 else None


def _hints_desde_nombre_canonico(nombre_archivo: str) -> dict:
    hints: dict = {}
    m = re.match(
        r"^(\d{4}-\d{2}-\d{2})_([^_]+)_([a-z0-9-]+)\.[a-z0-9]+$",
        nombre_archivo,
        re.IGNORECASE,
    )
    if not m:
        return hints
    hints["fecha"] = m.group(1)
    segmento = m.group(2).lower()
    slug_trab = m.group(3)

    if re.search(r"suspension-empleo-sueldo|notificacion-suspension", segmento):
        hints["tipo_sancion"] = "suspension_empleo_sueldo"
    elif re.search(r"despido-disciplinario|notificacion-despido", segmento):
        hints["tipo_sancion"] = "despido_disciplinario"
    elif "amonestacion-escrita" in segmento:
        hints["tipo_sancion"] = "amonestacion_escrita"
    elif "amonestacion-verbal" in segmento:
        hints["tipo_sancion"] = "amonestacion_verbal"

    if re.search(r"-muy-grave(?:-|$)", segmento):
        hints["grado_falta"] = "muy_grave"
    elif re.search(r"-grave(?:-|$)", segmento):
        hints["grado_falta"] = "grave"
    elif re.search(r"-leve(?:-|$)", segmento):
        hints["grado_falta"] = "leve"

    nombre = _nombre_desde_slug_trabajador(slug_trab)
    if nombre:
        hints["nombre_completo_detectado"] = nombre
    return hints


def _hints_desde_nombre(nombre_archivo: str | None) -> dict:
    if not nombre_archivo:
        return {}
    hints = dict(_hints_desde_nombre_canonico(nombre_archivo))
    upper = nombre_archivo.upper()
    if re.search(r"SANCION\s+EMPLEO\s+Y\s+SUELDO|SUSPENSION", upper) and "tipo_sancion" not in hints:
        hints["tipo_sancion"] = "suspension_empleo_sueldo"
    if "grado_falta" not in hints:
        if re.search(r"(?:^|_)MUY[_\s-]?GRAVE(?:_|$)", upper):
            hints["grado_falta"] = "muy_grave"
        elif re.search(r"(?:^|_)GRAVE(?:_|$)", upper):
            hints["grado_falta"] = "grave"
        elif re.search(r"(?:^|_)LEVE(?:_|$)", upper):
            hints["grado_falta"] = "leve"
    if "fecha" not in hints:
        m_fecha = re.search(r"_(\d{6})(?=\.pdf|$)", nombre_archivo, re.IGNORECASE)
        if m_fecha:
            dd, mm, yy = m_fecha.group(1)[:2], m_fecha.group(1)[2:4], m_fecha.group(1)[4:6]
            anio = f"19{yy}" if int(yy) >= 70 else f"20{yy}"
            hints["fecha"] = f"{anio}-{mm}-{dd}"
    if "nombre_completo_detectado" not in hints:
        m_nombre = re.search(r"_(?:MUY[_\s-]?GRAVE|GRAVE|LEVE)_([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]{4,50})_", nombre_archivo, re.IGNORECASE)
        if m_nombre:
            partes = m_nombre.group(1).strip().split()
            if len(partes) >= 3:
                hints["nombre_completo_detectado"] = f"{partes[-1]} {' '.join(partes[:-1])}"
            else:
                hints["nombre_completo_detectado"] = m_nombre.group(1).strip()
    return hints


def _clasificar_motivos(texto: str) -> list[dict]:
    detectados = []
    for patron, codigo, etiqueta, confianza in CATALOGO_MOTIVOS:
        m = re.search(patron, texto, re.IGNORECASE)
        if m:
            detectados.append({
                "codigo": codigo,
                "etiqueta": etiqueta,
                "confianza": confianza,
                "fragmento": m.group(0)[:180],
            })
    return sorted(detectados, key=lambda x: x["confianza"], reverse=True)


def _extraer_hechos(texto: str) -> list[dict]:
    hechos = []
    patron = re.compile(
        r"(?:^|\n)\s*(?:As[ií]\s+pues,?\s+|Por\s+otro\s+lado,?\s+|En\s+cuanto\s+a[l]?\s+|Pues\s+bien,?\s+)?"
        r"(?:el|El)\s+(\d{1,2})\s+de\s+([A-Za-zÁÉÍÓÚÑáéíóúñ]+)\s+de\s+(\d{4})[^.\n]{0,20}[,.]?\s*"
        r"([\s\S]{20,900}?)"
        r"(?=\n(?:As[ií]\s+pues|Pues\s+bien|Por\s+otro\s+lado|En\s+cuanto|Faltas\s+|Por\s+todo|$))",
        re.IGNORECASE,
    )
    for m in patron.finditer(texto):
        fecha = _fecha_extensa(m.group(1), m.group(2), m.group(3))
        resumen = re.sub(r"\s+", " ", m.group(4)).strip()
        if len(resumen) < 20:
            continue
        hechos.append({
            "fecha": fecha,
            "resumen": resumen,
            "motivos": _clasificar_motivos(resumen),
        })
    if not hechos:
        bloque = re.search(
            r"(?:detallar|imputan|expuestos)[:\s]*([\s\S]{40,2500}?)(?:Por\s+todo\s+lo\s+anteriormente|Faltas\s+(?:Leves|Graves)|Reciba\s+un\s+cordial)",
            texto, re.IGNORECASE
        )
        if bloque:
            resumen = re.sub(r"\s+", " ", bloque.group(1)).strip()[:1200]
            if len(resumen) >= 40:
                hechos.append({"resumen": resumen, "motivos": _clasificar_motivos(resumen)})
    return hechos


def _motivos_unicos(hechos: list[dict]) -> list[dict]:
    mapa: dict[str, dict] = {}
    for hecho in hechos:
        for motivo in hecho.get("motivos", []):
            prev = mapa.get(motivo["codigo"])
            if not prev or prev["confianza"] < motivo["confianza"]:
                mapa[motivo["codigo"]] = motivo
    return sorted(mapa.values(), key=lambda x: x["confianza"], reverse=True)


def _extraer_faltas_convenio(texto: str) -> list[dict]:
    faltas = []
    for bloque in re.finditer(r"Faltas\s+(Leves|Graves|Muy\s+Graves):\s*([^\n]+(?:\n(?!\s*Faltas)[^\n]+)*)", texto, re.IGNORECASE):
        grado_raw = bloque.group(1).lower()
        grado = "muy_grave" if "muy" in grado_raw else "grave" if "grave" in grado_raw else "leve"
        for item in re.finditer(r"(\d+)\.\s*([^\n:]{5,200})", bloque.group(2)):
            faltas.append({
                "grado": grado,
                "numero": item.group(1),
                "texto": re.sub(r"\s+", " ", item.group(2).replace("_", " ")).strip(),
            })
    return faltas


def _extraer_articulos(texto: str) -> list[str]:
    articulos = set()
    for m in re.finditer(r"art[ií]?culo\.?\s*(\d+[\w.\-]*)", texto, re.IGNORECASE):
        articulos.add(f"Art. {m.group(1)}")
    for m in re.finditer(r"\bart\.\s*(\d+[\w.\-]*)", texto, re.IGNORECASE):
        articulos.add(f"Art. {m.group(1)}")
    return list(articulos)


def _extraer_nombre(texto: str, hint: str | None) -> Optional[str]:
    candidatos = []
    m1 = re.search(r"DON\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]{4,50})\s*\n\s*DNI", texto, re.IGNORECASE)
    if m1:
        candidatos.append(m1.group(1).strip())
    m2 = re.search(r"([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]{4,50})\s+El trabajador", texto, re.IGNORECASE)
    if m2:
        candidatos.append(m2.group(1).strip())
    if hint:
        candidatos.append(hint)
    for raw in candidatos:
        if len(raw) >= 5 and not re.search(r"se encuentre en su puesto|comisi[oó]n por su parte", raw, re.IGNORECASE):
            return raw
    return None


def _periodo_suspension(texto: str) -> tuple[Optional[str], Optional[str]]:
    m = re.search(
        r"desde\s+la\s+fecha\s+(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})\s+hasta\s+el\s+(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})",
        texto, re.IGNORECASE
    )
    if not m:
        return None, None
    mes_desde = MESES.get(m.group(2).lower())
    mes_hasta = MESES.get(m.group(5).lower())
    if not mes_desde or not mes_hasta:
        return None, None
    return (
        f"{m.group(3)}-{mes_desde}-{m.group(1).zfill(2)}",
        f"{m.group(6)}-{mes_hasta}-{m.group(4).zfill(2)}",
    )


def extraer(texto: str, nombre_archivo: str | None = None) -> tuple[dict, list[str]]:
    advertencias: list[str] = []
    hints = _hints_desde_nombre(nombre_archivo)
    texto_limpio = (texto or "").strip()

    if len(texto_limpio) < 150:
        advertencias.append(
            "Texto del documento insuficiente; parte de los datos proviene del nombre de archivo"
        )

    tipo_sancion = hints.get("tipo_sancion")
    if not tipo_sancion:
        tipo_sancion = next((t for pat, t in TIPOS_SANCION if re.search(pat, texto, re.IGNORECASE)), None)

    grado_falta = hints.get("grado_falta")
    if not grado_falta:
        grado_falta = next((g for pat, g in GRADOS if re.search(pat, texto, re.IGNORECASE)), None)

    hechos = _extraer_hechos(texto)
    faltas_convenio = _extraer_faltas_convenio(texto)
    motivos = _motivos_unicos(hechos)
    for motivo in _clasificar_motivos(texto):
        if not any(m["codigo"] == motivo["codigo"] for m in motivos):
            motivos.append(motivo)
    motivos = sorted(motivos, key=lambda x: x["confianza"], reverse=True)

    nombre = _extraer_nombre(texto, hints.get("nombre_completo_detectado"))
    dni_m = re.search(r"DNI\s*N?[ºo]?\s*([0-9]{8}[A-Z]|[XYZ][0-9]{7}[A-Z])", texto, re.IGNORECASE)
    dni = dni_m.group(1).upper() if dni_m else None
    empresa = re.search(r"ADELTE\s+TRANSPORTE[^\n]{0,40}", texto, re.IGNORECASE)
    empresa_txt = empresa.group(0).strip() if empresa else None
    fecha = _fecha(texto) or hints.get("fecha")

    dias_m = re.search(r"suspensi[oó]n\s+de\s+empleo\s+y\s+sueldo\s+de\s+(\d+)\s+d[ií]as", texto, re.IGNORECASE)
    if not dias_m:
        dias_m = re.search(r"suspensi[oó]n[^\d]{0,40}(\d+)\s+d[ií]as", texto, re.IGNORECASE)
    dias_suspension = int(dias_m.group(1)) if dias_m else None

    articulos = _extraer_articulos(texto)
    articulo = articulos[0] if articulos else None
    inicio_susp, fin_susp = _periodo_suspension(texto)

    texto_hechos = None
    if hechos:
        texto_hechos = "\n\n".join(
            f"[{h['fecha']}] {h['resumen']}" if h.get("fecha") else h["resumen"]
            for h in hechos
        )[:4000]

    lc = texto.lower()
    firma_empresa = bool(re.search(r"head of labour|representante legal|reciba un cordial saludo|direcci[oó]n de (?:la )?empresa", texto, re.IGNORECASE))
    firma_trabajador = bool(re.search(r"el trabajador|recib[ií]|enterado|firmar el duplicado", lc))

    if grado_falta in ("grave", "muy_grave") and not articulos:
        advertencias.append("Falta grave/muy grave sin artículo del convenio/ET citado")
    if tipo_sancion == "despido_disciplinario" and not texto_hechos:
        advertencias.append("Carta de despido sin descripción de hechos imputados")
    if tipo_sancion == "suspension_empleo_sueldo" and not dias_suspension:
        advertencias.append("Suspensión sin días especificados")
    if tipo_sancion == "despido_disciplinario" and not firma_trabajador:
        advertencias.append("Despido sin acuse de recibo del trabajador detectado")
    if not motivos:
        advertencias.append("No se pudieron clasificar motivos concretos de la sanción")

    datos = {
        "nombre_completo_detectado": nombre,
        "dni_detectado": dni,
        "empresa": empresa_txt,
        "fecha": fecha,
        "tipo_sancion": tipo_sancion,
        "grado_falta": grado_falta,
        "dias_suspension": dias_suspension,
        "texto_hechos": texto_hechos,
        "descripcion_falta": texto_hechos[:500] if texto_hechos else None,
        "articulo": articulo,
        "articulos_citados": articulos,
        "motivos_clasificados": motivos,
        "hechos_detectados": hechos,
        "faltas_convenio_detectadas": faltas_convenio,
        "fecha_inicio_suspension": inicio_susp,
        "fecha_fin_suspension": fin_susp,
        "firma_empresa": firma_empresa,
        "firma_trabajador": firma_trabajador,
    }
    return datos, advertencias
