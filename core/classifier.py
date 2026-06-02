"""
CLASIFICADOR — Tipo de documento laboral

Replica la lógica del clasificador TypeScript:
  1. Por ruta/nombre de archivo (heurística rápida)
  2. Por señales ponderadas en el contenido

Puerto directo de clasificador-documentos.ts.
"""

import re
from dataclasses import dataclass


@dataclass
class ResultadoClasificacion:
    tipo: str          # nomina | horario | sancion | vida_laboral | convenio | contrato | unknown
    confianza: float   # 0.0–1.0
    razon: str
    es_ambiguo: bool


# ─── SEÑALES POR TIPO ─────────────────────────────────────────────────────────

SEÑALES: dict[str, list[tuple[str, float]]] = {
    "nomina": [
        (r"recibo\s+de\s+(?:haberes|salarios|n[oó]mina)",  0.35),
        (r"l[ií]quido\s+(?:total\s+)?a\s+percibir",        0.30),
        (r"devengos",                                       0.15),
        (r"deducciones",                                    0.10),
        (r"base\s+cotizaci[oó]n",                           0.12),
        (r"irpf|i\.r\.p\.f",                                0.10),
        (r"salario\s+base",                                 0.12),
        (r"cotizaci[oó]n\s+r[eé]gimen\s+general",           0.15),
        (r"n[uú]mero\s+de\s+afiliaci[oó]n",                 0.10),
        (r"mei|mecanismo\s+equidad",                        0.08),
    ],
    "vida_laboral": [
        (r"informe\s+de\s+vida\s+laboral",                  0.60),
        (r"tesorer[ií]a\s+general\s+de\s+la\s+seguridad",   0.30),
        (r"situaci[oó]n.*alta.*baja",                        0.20),
        (r"fecha\s+de\s+(?:efecto\s+de\s+)?alta",           0.15),
        (r"r[eé]gimen.*general.*empresa",                   0.12),
        (r"d[ií]as\s+efectivamente\s+computables",          0.20),
        (r"prestaci[oó]n\s+desempleo",                       0.10),
    ],
    "horario": [
        (r"cuadrante\s+de\s+turnos",                        0.40),
        (r"horarios\s+planificados",                        0.35),
        (r"mes\/a[ñn]o",                                    0.15),
        (r"turno\s+(?:ma[ñn]ana|tarde|noche)",              0.15),
        (r"\b(?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)\b", 0.10),
        (r"jefe\s+de\s+turno",                              0.18),
        (r"abastecedor",                                    0.15),
        (r"agentes\s+(?:fijos|turnos)",                     0.18),
    ],
    "sancion": [
        (r"carta\s+de\s+sanci[oó]n",                        0.55),
        (r"apertura\s+de\s+expediente",                     0.45),
        (r"despido\s+disciplinario",                        0.50),
        (r"suspensi[oó]n\s+de\s+empleo\s+y\s+sueldo",       0.50),
        (r"falta\s+(?:leve|grave|muy\s+grave)",             0.35),
        (r"amonestaci[oó]n\s+(?:verbal|escrita)",           0.40),
        (r"r[eé]gimen\s+disciplinario",                     0.30),
        (r"incumplimiento\s+(?:grave|reiterado)",           0.18),
    ],
    "notificacion": [
        (r"mutua\s+colaboradora",                           0.45),
        (r"le\s+informamos",                                0.35),
        (r"determinaci[oó]n\s+de\s+la\s+contingencia",      0.50),
        (r"contingencia\s+com[uú]n|accidente\s+de\s+trabajo", 0.30),
        (r"parte\s+de\s+baja|proceso\s+m[eé]dico",          0.28),
        (r"reclamaci[oó]n\s+que\s+nos\s+ha\s+presentado",   0.35),
        (r"instituto\s+nacional\s+de\s+la\s+seguridad\s+social", 0.25),
    ],
    "convenio": [
        (r"convenio\s+colectivo",                           0.55),
        (r"bolet[ií]n\s+oficial",                           0.25),
        (r"comisi[oó]n\s+negociadora",                      0.35),
        (r"jornada\s+laboral.*horas\s+anuales",             0.25),
        (r"tabla\s+salarial",                               0.30),
        (r"representantes\s+(?:sindicales|trabajadores)",   0.15),
    ],
    "contrato": [
        (r"contrato\s+de\s+trabajo",                        0.55),
        (r"cl[aá]usulas?\s+(?:adicionales|espec[ií]ficas)?", 0.20),
        (r"c[oó]digo\s+de\s+contrato",                      0.25),
        (r"per[ií]odo\s+de\s+prueba",                       0.18),
        (r"duraci[oó]n\s+(?:del\s+)?contrato",              0.18),
        (r"jornada\s+(?:completa|parcial)",                 0.20),
        (r"servicio\s+p[uú]blico\s+de\s+empleo",            0.25),
        (r"datos\s+de\s+(?:la\s+)?empresa.*datos\s+de\s+(?:la\s+)?persona\s+trabajadora", 0.30),
    ],
}

CARPETA_A_TIPO: dict[str, str] = {
    "nominas": "nomina",
    "horarios": "horario",
    "vida_laboral": "vida_laboral",
    "sanciones": "sancion",
    "notificaciones": "notificacion",
    "escritos": "notificacion",
    "convenios": "convenio",
    "contratos": "contrato",
}

NOMBRE_A_TIPO: list[tuple[str, str]] = [
    (r"nomina|n[oó]mina|payroll|haberes",       "nomina"),
    (r"vida_laboral|vida\s+laboral|vl_",        "vida_laboral"),
    (r"cuadrante|turno|horario|schedule",       "horario"),
    (r"sancion|sanci[oó]n|expediente",          "sancion"),
    (r"notificacion|escrito|mutua|contingencia", "notificacion"),
    (r"convenio|ccol",                          "convenio"),
    (r"contrato|contract",                       "contrato"),
]


def clasificar_por_contenido(texto: str) -> ResultadoClasificacion:
    scores: dict[str, float] = {}
    for tipo, señales in SEÑALES.items():
        score = sum(
            peso for patron, peso in señales
            if re.search(patron, texto, re.IGNORECASE)
        )
        if score > 0:
            scores[tipo] = score

    if not scores:
        return ResultadoClasificacion("unknown", 0.0, "sin señales suficientes", False)

    ordenado = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    mejor_tipo, mejor_score = ordenado[0]
    confianza = min(mejor_score, 1.0)
    es_ambiguo = len(ordenado) > 1 and ordenado[1][1] / mejor_score > 0.75

    if confianza < 0.10:
        return ResultadoClasificacion("unknown", 0.0, "score insuficiente", False)

    return ResultadoClasificacion(
        tipo=mejor_tipo,
        confianza=round(confianza * 0.7 if es_ambiguo else confianza, 3),
        razon=f"señales para '{mejor_tipo}' (score={mejor_score:.2f})",
        es_ambiguo=es_ambiguo,
    )


def clasificar_por_ruta(nombre_archivo: str) -> ResultadoClasificacion:
    partes = nombre_archivo.lower().replace("\\", "/").split("/")
    carpeta = partes[-2] if len(partes) >= 2 else ""
    base = partes[-1]

    if carpeta in CARPETA_A_TIPO:
        return ResultadoClasificacion(CARPETA_A_TIPO[carpeta], 0.85, f"carpeta '{carpeta}'", False)

    for patron, tipo in NOMBRE_A_TIPO:
        if re.search(patron, base, re.IGNORECASE):
            return ResultadoClasificacion(tipo, 0.75, "nombre de archivo", False)

    return ResultadoClasificacion("unknown", 0.0, "sin pista en ruta", False)


def clasificar(texto: str, nombre_archivo: str, tipo_hint: str | None = None) -> ResultadoClasificacion:
    if tipo_hint and tipo_hint != "unknown":
        return ResultadoClasificacion(tipo_hint, 1.0, "tipo forzado por caller", False)

    por_ruta = clasificar_por_ruta(nombre_archivo)
    if por_ruta.confianza >= 0.70:
        return por_ruta

    por_contenido = clasificar_por_contenido(texto)

    if por_ruta.tipo != "unknown" and por_contenido.confianza > por_ruta.confianza:
        return por_contenido

    return por_ruta if por_ruta.tipo != "unknown" else por_contenido
