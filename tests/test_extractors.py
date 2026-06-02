"""Tests básicos de los extractores."""

import pytest
from extractors import nomina, horario, sancion, vida_laboral, convenio, contrato


class TestExtractorNomina:
    TEXTO = """
    D. Juan García López
    EMPRESA: EMPRESA EJEMPLO S.A.   CIF: B12345678
    Período: Enero 2025
    SALARIO BASE         010   1.134,00
    TOTAL DEVENGOS               1.650,00
    COTIZACIÓN CONT. COM  720     77,43
    COTIZACIÓN DESEMPLEO          25,58
    COTIZACIÓN FORMACIÓN           1,65
    COTIZACIÓN MEI                 2,14
    TRIBUTACIÓN I.R.P.F.   15%  247,50
    T. A DEDUCIR                 354,30
    Líquido total a percibir:   1.295,70
    BASE S.S.: 1.650,00
    12345678A   280000000001
    """

    def test_extrae_nombre(self):
        datos, _ = nomina.extraer(self.TEXTO)
        assert datos["nombre_completo_detectado"] is not None
        assert "García" in datos["nombre_completo_detectado"] or "GARCIA" in datos["nombre_completo_detectado"].upper()

    def test_extrae_salario_base(self):
        datos, _ = nomina.extraer(self.TEXTO)
        assert datos["devengos"]["salario_base"] == 1134.0

    def test_extrae_neto(self):
        datos, _ = nomina.extraer(self.TEXTO)
        assert datos["neto"] == 1295.70

    def test_extrae_base_cotizacion(self):
        datos, _ = nomina.extraer(self.TEXTO)
        assert datos["base_cotizacion"] == 1650.0

    def test_extrae_mei(self):
        datos, _ = nomina.extraer(self.TEXTO)
        assert datos["deducciones"]["mei"] == 2.14

    def test_sin_mei_genera_advertencia(self):
        texto_sin_mei = "SALARIO BASE 1.000,00\nTOTAL DEVENGOS 1.000,00\nLíquido total a percibir: 850,00"
        _, advertencias = nomina.extraer(texto_sin_mei)
        assert any("MEI" in a for a in advertencias)

    def test_extrae_nomina_estructurada_adelte(self):
        texto = """
        ADELTE TRANSPORTE Y SERVICIOS
        DOMICILIO AEROPUERTO SON SANT JOAN
        ALVAREZ WASHINGTON, CESAR EZE
        DNI 71675766S   Nº AFILIACION S.S. 33/10296416-17
        CATEGORIA AGENTE   ANTIGÜEDAD 22 MAR 19   TARIFA 10   CONTRATO 100   NRO 290016
        MENS 01 DIC 25 a 31 DIC 25   TOTAL DIAS 30
        FECHA 12 ENERO 2026
        Salario Base 30,00 53,590 1.607,70
        Vacaciones 46,86
        Festivos 6,00 3,200 19,20
        Horas Nocturnas 48,00 1,660 79,68
        Domingo 25,00 2,880 72,00
        Plus transporte fijo 30,00 1,753 52,58
        Plus madrugue 5,00 6,430 32,15
        Ayuda manutención 7,00 6,430 45,01
        Plus jornada irregular 30,00 4,737 142,12
        Horas Extras Normal 8,00 19,720 157,76
        Diferencia mes anterior 121,11
        Dto cuota sindical 10,00
        Cotización contingencias comunes 4,70 111,17
        Cotización MEI 0,13 3,07
        Cotización formación 0,10 2,52
        Cotización desempleo 1,55 39,11
        Cotización horas extra 4,70 7,41
        Tributación I.R.P.F. 18,56 418,54
        Remuneración total 2.097,30
        Prorrata pagas extras 267,94
        BASE S.S.: 2.365,24
        BASE A.T. y desempleo 2.523,00
        BASE I.R.P.F.: 2.255,06
        TOTAL DEVENGADO 2.255,06
        T. A DEDUCIR 712,93
        Líquido total a percibir: 1.542,13
        Coste empresa 3.108,54
        APORTACIÓN EMPRESARIAL
        Contingencias comunes 2.365,24 23,60 558,20
        MEI 2.365,24 0,67 15,85
        AT y EP 2.523,00 3,30 83,26
        Desempleo 2.523,00 5,50 138,77
        Formación profesional 2.523,00 0,60 15,14
        FOGASA 2.523,00 0,20 5,05
        Cotización adicional horas extraordinarias 157,76 23,60 37,23
        """
        datos, _ = nomina.extraer(texto)

        assert datos["trabajador"]["nombre"] == "ALVAREZ WASHINGTON, CESAR EZE"
        assert datos["empresa"]["nombre"] == "ADELTE TRANSPORTE Y SERVICIOS"
        assert datos["empresa"]["domicilio_centro"] == "AEROPUERTO SON SANT JOAN"
        assert datos["periodo"]["desde"] == "2025-12-01"
        assert datos["periodo"]["hasta"] == "2025-12-31"
        assert datos["devengos"]["salario_base"] == 1607.70
        assert datos["totales"]["liquido"] == 1542.13
        assert datos["totales"]["coste_empresa"] == 3108.54
        assert len(datos["conceptos"]) >= 10
        assert len(datos["deducciones_detalle"]) >= 7
        assert len(datos["aportacion_empresa"]) >= 7
        assert "trabajador.nombre" in datos["trazabilidad"]


class TestExtractorContrato:
    def test_extrae_datos_basicos_contrato(self):
        texto = """
        CONTRATO DE TRABAJO
        Trabajador: Juan Garcia Lopez
        DNI: 12345678A
        Empresa: Test S.A.
        Fecha de inicio: 01/02/2025
        Código de contrato: 100
        Jornada: completa
        40 horas semanales
        Categoría: Agente
        Salario: 1.500,00
        Período de prueba: 2 meses
        """
        datos, advertencias = contrato.extraer(texto)
        assert datos["dni_detectado"] == "12345678A"
        assert datos["fecha_inicio"] == "2025-02-01"
        assert datos["codigo_contrato"] == "100"
        assert datos["horas_semanales"] == 40
        assert not advertencias

    def test_extrae_copia_basica_sepe(self):
        texto = """
        CONTRATO DE TRABAJO INDEFINIDO **COPIA BASICA**
        NOMBRE O RAZÓN SOCIAL DE LA EMPRESA
        ADELTE TRANSPORTE Y SERVICIOS EFS SLU
        DATOS DEL/DE LA TRABAJADOR/A
        D./Dª.
        RUBIO MORENO, DAVID
        NIF/NIE
        CUARTA: la duración del presente contrato será INDEFINIDA, iniciándose la relación laboral en fecha 01/09/2024
        modalidad contractual Fijo Discontinuo.
        """
        nombre = "ATS PMR PMI- DAVID RUBIO MORENO - CB cto300-2024-09-01.pdf"
        datos, advertencias = contrato.extraer(texto, nombre)
        assert datos["nombre_completo_detectado"] == "DAVID RUBIO MORENO"
        assert datos["fecha_inicio"] == "2024-09-01"
        assert datos["codigo_contrato"] == "300"
        assert datos["empresa"] == "ADELTE TRANSPORTE Y SERVICIOS EFS SLU"
        assert "DNI del trabajador no legible" in " ".join(advertencias)


class TestExtractorVidaLaboral:
    def test_extrae_registros_tgss_reales(self):
        texto = """
        INFORME DE VIDA LABORAL
        De los antecedentes obrantes en la Tesorería General de la Seguridad Social al día 5 de agosto de 2024 , resulta que D/Dª
        MARGARITA GARCIA COLL , nacido/a el 29 de enero de 1974 , con
        Número de la Seguridad Social 070082769844 , D.N.I. 018232764C , domicilio en
        ha figurado en situación de alta en el Sistema de la Seguridad Social durante un total de
        3.621 días 11 meses
        GENERAL 07124967975 ADELTE TRANSPORTE Y SERVICIOS,S.L. 11.03.2024 11.03.2024 --- 300 --- 10 118
        GENERAL 07129429066 VACACIONES RETRIBUIDAS Y NO
        DISFRUTADAS
        16.11.2023 16.11.2023 16.11.2023 --- --- -- 1
        GENERAL 07129429066 UTE PMR MASA-SAGITAL L3 01.04.2023 01.04.2023 15.11.2023 300 75,0 10 165
        GENERAL ----------- PRESTACION DESEMPLEO. EXTINCION 09.11.2022 09.11.2022 08.03.2023 --- --- 10 120
        """
        datos, _ = vida_laboral.extraer(texto)

        assert datos["nombre_completo_detectado"] == "MARGARITA GARCIA COLL"
        assert datos["dni_detectado"] == "018232764C"
        assert datos["nss_detectado"] == "070082769844"
        assert datos["total_dias_computables"] == 3621
        assert datos["num_registros"] == 4
        assert datos["registros_detectados"][0]["empresa"] == "ADELTE TRANSPORTE Y SERVICIOS,S.L."
        assert datos["registros_detectados"][0]["fecha_alta"] == "2024-03-11"
        assert datos["registros_detectados"][0]["ct"] == "300"
        assert datos["registros_detectados"][0]["gc"] == "10"
        assert datos["registros_detectados"][0]["dias"] == 118
        assert "ADELTE TRANSPORTE Y SERVICIOS,S.L." in datos["empresas_detectadas"]


class TestExtractorSancion:
    TEXTO = """
    Estimado trabajador D. Carlos López Martínez, DNI: 11111111C
    Por la presente le comunicamos CARTA DE SANCIÓN
    DESPIDO DISCIPLINARIO por FALTA MUY GRAVE
    Artículo 54 del Estatuto de los Trabajadores
    """

    def test_detecta_tipo_despido(self):
        datos, _ = sancion.extraer(self.TEXTO)
        assert datos["tipo_sancion"] == "despido_disciplinario"

    def test_detecta_grado_muy_grave(self):
        datos, _ = sancion.extraer(self.TEXTO)
        assert datos["grado_falta"] == "muy_grave"

    def test_extrae_articulo(self):
        datos, _ = sancion.extraer(self.TEXTO)
        assert datos["articulo"] is not None
        assert "54" in datos["articulo"]

    def test_advertencia_sin_firma(self):
        _, advertencias = sancion.extraer(self.TEXTO)
        assert any("acuse de recibo" in a for a in advertencias)

    def test_hints_nombre_canonico_sin_texto(self):
        nombre = "2025-01-17_notificacion-suspension-empleo-sueldo_heredia-vicente.pdf"
        datos, advertencias = sancion.extraer("", nombre)
        assert datos["tipo_sancion"] == "suspension_empleo_sueldo"
        assert datos["fecha"] == "2025-01-17"
        assert datos["nombre_completo_detectado"] == "Vicente Heredia"
        assert any("insuficiente" in a for a in advertencias)


class TestExtractorConvenio:
    TEXTO = """
    CONVENIO COLECTIVO DE HOSTELERÍA Y RESTAURACIÓN
    Código de convenio: 990001765011982
    BOE núm. 123
    Vigencia: 2024-2026
    Plan de igualdad
    Teletrabajo
    """

    def test_detecta_nombre(self):
        datos, _ = convenio.extraer(self.TEXTO)
        assert datos["nombre"] is not None
        assert "HOSTELERÍA" in datos["nombre"].upper() or "hostelería" in datos["nombre"].lower()

    def test_detecta_vigencia(self):
        datos, _ = convenio.extraer(self.TEXTO)
        assert datos["fecha_vigencia_inicio"] == "2024-01-01"
        assert datos["fecha_vigencia_fin"] == "2026-12-31"

    def test_detecta_protocolos(self):
        datos, _ = convenio.extraer(self.TEXTO)
        assert "Plan de igualdad" in datos["protocolos_detectados"]
        assert "Teletrabajo" in datos["protocolos_detectados"]

    def test_codigo(self):
        datos, _ = convenio.extraer(self.TEXTO)
        assert datos["codigo"] == "990001765011982"


class TestExtractorNominaUtePmr:
    TEXTO = """
UTE PMR MASA SAGITAL L3
54378735L
SARA MORA MUÑOZ
AGENTE SERVICIOS AUXILIARES
Del 01 al 31 Julio 2023
25/Agosto/2018
031100371786
001
,76
1.065
1
,76
1.065
SALARIO BASE
010
,62
PLUS DOMINGO TRABAJADO
650
,45
143
,51
COTIZACION MEI
550
,85
1.339
,87
164
******* TOTAL DEVENGOS Y DEDUCCIONES
ES7614650100971XXXX
1.174
,98
1.517
,48
1.517
,48
4,7
1,65
"""

    def test_extrae_totales_ute_pmr(self):
        datos, _adv = nomina.extraer(self.TEXTO)
        assert datos["periodo"]["desde"] == "2023-07-01"
        assert datos["periodo"]["hasta"] == "2023-07-31"
        assert datos["trabajador"]["antiguedad"] == "25/Agosto/2018"
        assert datos["totales"]["total_devengado"] == 1339.87
        assert datos["totales"]["liquido"] == 1174.98
        assert datos["totales"]["total_deducir"] == 164.89
        assert datos["devengos"]["salario_base"] == 1065.76
        assert datos["control"]["confianza_global"] >= 0.88
        assert datos["control"]["motivos_revision"] == []
