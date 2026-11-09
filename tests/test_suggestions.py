import pytest

from services.suggestions import context_from_guide, suggest_section


def test_context_tema(sample_guide):
    assert "embebidos" in context_from_guide(sample_guide)["tema"]


def test_suggest_presentation(sample_guide):
    out = suggest_section(sample_guide, "presentacion")
    assert out["source"] == "plantilla"
    text = " ".join(block["texto"] for block in out["presentacion"]["bloques"])
    assert "{" not in text


def test_suggest_activity_extra(sample_guide):
    out = suggest_section(sample_guide, "actividad", "apropiacion", 1)
    assert "apropiación 2" in out["actividad"]["titulo"]
    assert out["actividad"]["duracion_horas"] == 16


def test_suggest_glossary_and_references(sample_guide):
    assert suggest_section(sample_guide, "glosario")["glosario"]
    assert suggest_section(sample_guide, "referencias")["referencias"]


def test_suggest_evidencias_uses_shared_logic(sample_guide):
    out = suggest_section(sample_guide, "evidencias")
    assert out["evidencias"][0]["evidencia"].startswith("Ev1.")


def test_unsupported_section(sample_guide):
    with pytest.raises(ValueError):
        suggest_section(sample_guide, "desconocida")


def test_llm_disabled_falls_back(sample_guide, monkeypatch):
    from services import llm

    monkeypatch.setattr(llm, "available", lambda: False)
    out = suggest_section(sample_guide, "glosario", use_llm=True)
    assert out["source"] == "plantilla"
    assert "warning" in out


def test_llm_error_falls_back(sample_guide, monkeypatch):
    from services import llm

    monkeypatch.setattr(llm, "available", lambda: True)

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(llm, "suggest", boom)
    out = suggest_section(sample_guide, "glosario", use_llm=True)
    assert out["source"] == "plantilla"
    assert "boom" in out["warning"]
