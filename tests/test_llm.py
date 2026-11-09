import json

import pytest

from services import llm


def test_parse_json_plain():
    assert llm._parse_json('{"a": 1}') == {"a": 1}


def test_parse_json_fenced():
    assert llm._parse_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_parse_json_invalid():
    with pytest.raises(RuntimeError):
        llm._parse_json("no es json")


def test_available_env_override(monkeypatch, tmp_path):
    import config

    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"llm": {"enabled": True, "base_url": "https://x/v1", "api_key": ""}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)
    monkeypatch.setenv("GA_LLM_API_KEY", "test-key")
    assert llm.available() is True


def test_suggest_activity(sample_guide, monkeypatch):
    payload = {
        "titulo": "Nueva",
        "introduccion": "Intro",
        "instrucciones": ["a"],
        "duracion_horas": 3,
        "evidencias": ["Ev"],
    }
    monkeypatch.setattr(llm, "chat", lambda *args, **kwargs: json.dumps(payload))
    out = llm.suggest("actividad", sample_guide, "apropiacion", 0)
    assert out["actividad"]["titulo"] == "Nueva"
    assert out["actividad"]["duracion_horas"] == 3


def test_suggest_presentation(sample_guide, monkeypatch):
    payload = {"bloques": [{"tipo": "parrafo", "texto": "Hola"}]}
    monkeypatch.setattr(llm, "chat", lambda *args, **kwargs: json.dumps(payload))
    out = llm.suggest("presentacion", sample_guide)
    assert out["presentacion"]["bloques"][0]["texto"] == "Hola"


def test_suggest_glossary_and_references(sample_guide, monkeypatch):
    monkeypatch.setattr(
        llm, "chat", lambda *args, **kwargs: json.dumps({"glosario": [{"termino": "T", "definicion": "D"}]})
    )
    assert llm.suggest("glosario", sample_guide)["glosario"][0]["termino"] == "T"

    monkeypatch.setattr(llm, "chat", lambda *args, **kwargs: json.dumps({"referencias": ["Ref"]}))
    assert llm.suggest("referencias", sample_guide)["referencias"] == ["Ref"]
