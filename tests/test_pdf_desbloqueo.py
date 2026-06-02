from core.pdf_desbloqueo import construir_candidatos_pdf, variantes_clave_documento


def test_variantes_nif():
    v = variantes_clave_documento("12345678A", "")
    assert "12345678A" in v
    assert "12345678a" in v
    assert "12345678" in v


def test_variantes_nss():
    v = variantes_clave_documento("", "28/10000000-01")
    assert "281000000001" in v


def test_prioridad_manual_y_perfil():
    c = construir_candidatos_pdf(
        trabajadores=[{"id": "t1", "nif": "11111111H", "nss": "111"}],
        trabajador_id="t1",
        pdf_password="clave-manual",
        claves_perfil={"nif": "99999999R"},
    )
    assert c[0] == "clave-manual"
    assert "99999999R" in c
    assert "11111111H" in c


def test_trabajador_priorizado_sobre_catalogo():
    c = construir_candidatos_pdf(
        trabajadores=[
            {"id": "t1", "nif": "11111111H"},
            {"id": "t2", "nif": "22222222J"},
        ],
        trabajador_id="t1",
    )
    idx_t1 = c.index("11111111H")
    idx_t2 = c.index("22222222J")
    assert idx_t1 < idx_t2
