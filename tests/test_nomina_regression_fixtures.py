"""Regresión: plantillas PUNTO-FA, VAL&THI y Claire (bloque devengo/deducir/líquido)."""

import io
from pathlib import Path

import pytest

from core.ingesta import ingestar
from extractors import nomina

_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "nominas"

_SNIPPET_PUNTO_FA = """
PUNTO-FA, S.L.
Del 1 de Enero de 2020 al 31 de Enero de 2020
VERONICA BENNASSAR ORDINOLA
Salario Base
30,00
27,380
821,48
TOTAL DEVENGOS
1.277,33
Retención a Cuenta IRPF
5,10
1.277,330
65,14
Cotiz. Contingencias Comunes
1.415,600
66,53
Cotiz. Formac. Prof.
1,41
Cotiz. Desempleo
21,94
TOTAL RETENCIONES
154,79
Aportaciones S.S. Empresa
446,65
1.277,33
1.122,54
"""

_SNIPPET_VALTHI = """
VAL&THI S.L.(I.B.)
Periodo de Liquidación
Del 1 al 31 de MARZO 2021
Salario base
677,29
Plus transporte
73,08
Total Devengado
Total Deducir
LIQUIDO A PERCIBIR
Euros
919,69
78,18
841,51
Cont.Comunes
43,23
Desempleo
14,26
For.Profesional
0,92
I.R.P.F.
19,77
"""

_SNIPPET_CLAIRE = """
Mensual - 1 Febrero 2023 a 28 Febrero 2023
REM. TOTAL P.P. EXTRAS BASE C.C. BASE A.T. Y DES BASE I.R.P.F. T. DEVENGADO T. A DEDUCIR
1369,72 282,51 1652,23 1652,23 1369,72 1379,72 202,44
Líquido  a  Percibir
1177,28
Coste Empresa : 1909,26
Salario Base
1118,82
Tributación IRPF
118,82
"""


class TestNominaRegressionSnippets:
    def test_punto_fa_totales_y_salario(self):
        datos, _ = nomina.extraer(_SNIPPET_PUNTO_FA)
        assert datos["totales"]["total_devengado"] == 1277.33
        assert datos["totales"]["total_deducir"] == 154.79
        assert datos["totales"]["liquido"] == 1122.54
        assert datos["devengos"]["salario_base"] == 821.48
        assert datos["periodo"]["desde"] == "2020-01-01"
        assert datos["periodo"]["hasta"] == "2020-01-31"

    def test_valthi_triple_coherente(self):
        datos, advertencias = nomina.extraer(_SNIPPET_VALTHI)
        assert datos["totales"]["total_devengado"] == 919.69
        assert datos["totales"]["total_deducir"] == 78.18
        assert datos["totales"]["liquido"] == 841.51
        assert datos["devengos"]["salario_base"] == 677.29
        assert datos["deducciones"]["irpf"] == 19.77
        assert datos["periodo"]["desde"] == "2021-03-01"
        assert not any("MEI" in a for a in advertencias)

    def test_claire_tabla_y_liquido(self):
        datos, _ = nomina.extraer(_SNIPPET_CLAIRE)
        assert datos["totales"]["total_devengado"] == 1379.72
        assert datos["totales"]["total_deducir"] == 202.44
        assert datos["totales"]["liquido"] == 1177.28
        assert datos["devengos"]["salario_base"] == 1118.82
        assert datos["deducciones"]["irpf"] == 118.82
        assert datos["periodo"]["desde"] == "2023-02-01"


@pytest.mark.skipif(
    not (_FIXTURES_DIR / "01 ENERO 2020.pdf").exists(),
    reason="PDFs de regresión no copiados a tests/fixtures/nominas",
)
class TestNominaRegressionPdfs:
    @pytest.mark.parametrize(
        "archivo,esperado",
        [
            (
                "01 ENERO 2020.pdf",
                {
                    "total_devengado": 1277.33,
                    "total_deducir": 154.79,
                    "liquido": 1122.54,
                    "salario_base": 821.48,
                },
            ),
            (
                "nomina ELENA MAR 21.pdf",
                {
                    "total_devengado": 919.69,
                    "total_deducir": 78.18,
                    "liquido": 841.51,
                    "salario_base": 677.29,
                },
            ),
            (
                "2023 02 30 nomina enero_vanesa luna gomez_claire.pdf",
                {
                    "total_devengado": 1379.72,
                    "total_deducir": 202.44,
                    "liquido": 1177.28,
                    "salario_base": 1118.82,
                },
            ),
        ],
    )
    def test_pdf_reales_si_existen(self, archivo: str, esperado: dict):
        path = _FIXTURES_DIR / archivo
        contenido = path.read_bytes()
        texto = ingestar(io.BytesIO(contenido), path.name).texto
        datos, _ = nomina.extraer(texto)
        for clave, valor in esperado.items():
            if clave == "salario_base":
                assert datos["devengos"][clave] == valor
            else:
                assert datos["totales"][clave] == valor
