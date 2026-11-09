from services.defaults import (
    MOMENT_ORDER,
    empty_guide,
    normalize_guide,
    rae_code,
    safe_slug,
    total_hours,
)


def test_empty_guide_structure():
    guide = empty_guide()
    assert set(guide["momentos"]) == set(MOMENT_ORDER)
    for moment_id in MOMENT_ORDER:
        assert guide["momentos"][moment_id]["actividades"]
    assert guide["identificacion"]["duracion_horas"] == 0


def test_normalize_guide_handles_garbage():
    guide = normalize_guide(None)
    assert guide["identificacion"]["programa"] == ""
    guide = normalize_guide("texto")
    assert set(guide["momentos"]) == set(MOMENT_ORDER)


def test_normalize_guide_coerces_types():
    raw = {
        "identificacion": {"programa": 123, "duracion_horas": "8 horas"},
        "momentos": {
            "apropiacion": {
                "actividades": [
                    {
                        "titulo": "Actividad",
                        "instrucciones": "linea 1\nlinea 2",
                        "duracion_horas": "4,5 h",
                        "materiales": "Kit",
                    }
                ]
            }
        },
        "glosario": ["Término"],
    }
    guide = normalize_guide(raw)
    assert guide["identificacion"]["programa"] == "123"
    assert guide["identificacion"]["duracion_horas"] == 8
    activity = guide["momentos"]["apropiacion"]["actividades"][0]
    assert activity["instrucciones"] == ["linea 1", "linea 2"]
    assert activity["duracion_horas"] == 4.5
    assert activity["materiales"]["consumible"] == "Kit"
    assert guide["glosario"] == [{"termino": "Término", "definicion": ""}]


def test_normalize_guide_rejects_bad_presentation_type():
    guide = normalize_guide({"presentacion": {"bloques": [{"tipo": "desconocido", "texto": "x"}]}})
    assert guide["presentacion"]["bloques"][0]["tipo"] == "parrafo"


def test_total_hours(sample_guide):
    assert total_hours(sample_guide) == 100


def test_rae_code(sample_guide):
    assert rae_code(sample_guide) == "RAE23"
    assert rae_code(empty_guide()) == "RAE"


def test_safe_slug():
    assert safe_slug("RAE23: Sistemas / Embebidos") == "RAE23_Sistemas_Embebidos"
    assert safe_slug("", fallback="guia") == "guia"
    assert len(safe_slug("x" * 200)) == 80
