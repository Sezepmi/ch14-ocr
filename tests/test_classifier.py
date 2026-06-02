"""Tests del clasificador de documentos."""

import pytest
from core.classifier import clasificar, clasificar_por_contenido, clasificar_por_ruta


class TestClasificarPorContenido:
    def test_nomina_con_señales_fuertes(self):
        texto = "RECIBO DE NÓMINA\nLíquido total a percibir: 1.500,00€\nDevengos\nDeducciones"
        r = clasificar_por_contenido(texto)
        assert r.tipo == "nomina"
        assert r.confianza >= 0.50

    def test_vida_laboral_con_señal_principal(self):
        texto = "INFORME DE VIDA LABORAL\nTesorería General de la Seguridad Social"
        r = clasificar_por_contenido(texto)
        assert r.tipo == "vida_laboral"
        assert r.confianza >= 0.60

    def test_sancion_despido(self):
        texto = "Carta de sanción\nDespido disciplinario por falta muy grave\nFalta muy grave"
        r = clasificar_por_contenido(texto)
        assert r.tipo == "sancion"

    def test_convenio_tabla_salarial(self):
        texto = "Convenio colectivo de hostelería\nTabla salarial 2025\nComisión negociadora"
        r = clasificar_por_contenido(texto)
        assert r.tipo == "convenio"

    def test_contrato_laboral(self):
        texto = "Contrato de trabajo\nCódigo de contrato 100\nJornada completa\nPeríodo de prueba"
        r = clasificar_por_contenido(texto)
        assert r.tipo == "contrato"

    def test_texto_vacio_devuelve_unknown(self):
        r = clasificar_por_contenido("")
        assert r.tipo == "unknown"
        assert r.confianza == 0.0


class TestClasificarPorRuta:
    def test_carpeta_nominas(self):
        r = clasificar_por_ruta("nominas/enero_2025.pdf")
        assert r.tipo == "nomina"
        assert r.confianza == 0.85

    def test_carpeta_sanciones(self):
        r = clasificar_por_ruta("sanciones/carta_juan.pdf")
        assert r.tipo == "sancion"

    def test_carpeta_vida_laboral(self):
        r = clasificar_por_ruta("vida_laboral/informe.pdf")
        assert r.tipo == "vida_laboral"

    def test_carpeta_contratos(self):
        r = clasificar_por_ruta("contratos/contrato_juan.pdf")
        assert r.tipo == "contrato"

    def test_nombre_archivo_nomina(self):
        r = clasificar_por_ruta("nomina_marzo_2025.pdf")
        assert r.tipo == "nomina"
        assert r.confianza == 0.75

    def test_ruta_desconocida(self):
        r = clasificar_por_ruta("documentos/archivo.pdf")
        assert r.tipo == "unknown"
        assert r.confianza == 0.0


class TestClasificar:
    def test_tipo_hint_gana_siempre(self):
        r = clasificar("texto cualquiera", "archivo.pdf", tipo_hint="horario")
        assert r.tipo == "horario"
        assert r.confianza == 1.0

    def test_ruta_con_alta_confianza_gana(self):
        r = clasificar("texto sin señales", "nominas/enero.pdf")
        assert r.tipo == "nomina"  # por carpeta, confianza 0.85 ≥ 0.70

    def test_contenido_gana_si_ruta_sin_confianza(self):
        texto = "INFORME DE VIDA LABORAL\nTesorería General de la Seguridad Social"
        r = clasificar(texto, "documentos/desconocido.pdf")
        assert r.tipo == "vida_laboral"
