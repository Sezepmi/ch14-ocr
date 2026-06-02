"""Tests del resolutor de identidad."""

import pytest
from core.identity import resolver_identidad


TRABAJADORES = [
    {"id": "t1", "nombre_completo": "Juan García López", "nif": "12345678A", "nss": "280000000001", "iban": "ES9121000418450200051332"},
    {"id": "t2", "nombre_completo": "María Fernández Ruiz", "nif": "87654321B", "nss": "280000000002"},
    {"id": "t3", "nombre_completo": "Carlos López Martínez", "nif": "11111111C", "nss": "280000000003"},
]

TRABAJADORES_CAMEL = [
    {"id": "t1", "nombreCompleto": "Juan García López", "nif": "12345678A", "nss": "280000000001"},
]


class TestMatchExacto:
    def test_dni_exacto(self):
        r = resolver_identidad("", TRABAJADORES, dni_detectado="12345678A")
        assert r.persona_id == "t1"
        assert r.confidence == 0.99
        assert "DNI exacto" in r.razon

    def test_nss_exacto(self):
        r = resolver_identidad("", TRABAJADORES, nss_detectado="280000000002")
        assert r.persona_id == "t2"
        assert r.confidence == 0.99

    def test_iban_exacto(self):
        r = resolver_identidad("", TRABAJADORES, iban_detectado="ES9121000418450200051332")
        assert r.persona_id == "t1"
        assert r.confidence == 0.97

    def test_dni_normaliza_espacios(self):
        r = resolver_identidad("", TRABAJADORES, dni_detectado="12 345 678 A")
        assert r.persona_id == "t1"

    def test_acepta_nombre_completo_camelcase(self):
        r = resolver_identidad("", TRABAJADORES_CAMEL, dni_detectado="12345678A")
        assert r.persona_id == "t1"
        assert r.nombre_completo == "Juan García López"


class TestFuzzyNombre:
    def test_nombre_exacto_alta_confianza(self):
        r = resolver_identidad("Juan García López", TRABAJADORES)
        assert r.persona_id == "t1"
        assert r.confidence >= 0.88

    def test_nombre_invertido_resuelve(self):
        r = resolver_identidad("García López Juan", TRABAJADORES)
        assert r.persona_id == "t1"

    def test_nombre_con_tildes(self):
        r = resolver_identidad("Maria Fernandez Ruiz", TRABAJADORES)
        assert r.persona_id == "t2"

    def test_nombre_desconocido_no_vincula(self):
        r = resolver_identidad("Pedro Desconocido Nadie", TRABAJADORES)
        assert r.persona_id is None

    def test_catalogo_vacio(self):
        r = resolver_identidad("Juan García", [])
        assert r.persona_id is None
        assert "catálogo vacío" in r.razon

    def test_sin_datos_identidad(self):
        r = resolver_identidad("", [])
        assert r.persona_id is None
        assert r.confidence == 0.0


class TestPrioridad:
    def test_dni_tiene_prioridad_sobre_fuzzy(self):
        """Aunque el nombre no coincida, el DNI debe ganar."""
        r = resolver_identidad("Nombre Completamente Erroneo", TRABAJADORES, dni_detectado="12345678A")
        assert r.persona_id == "t1"
        assert "DNI exacto" in r.razon
