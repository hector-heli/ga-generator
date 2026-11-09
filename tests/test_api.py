def test_index(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Generador" in response.data


def test_health(client):
    assert client.get("/api/health").get_json() == {"ok": True}


def test_normalize(client, sample_guide):
    response = client.post("/api/normalize", json={"guide": sample_guide})
    assert response.status_code == 200
    assert response.get_json()["identificacion"]["programa"] == sample_guide["identificacion"]["programa"]


def test_validate(client, sample_guide):
    response = client.post("/api/validate", json={"guide": sample_guide})
    data = response.get_json()
    assert response.status_code == 200
    assert "ok" in data and "errors" in data


def test_suggest(client, sample_guide):
    response = client.post("/api/suggest", json={"guide": sample_guide, "section": "presentacion"})
    assert response.status_code == 200
    assert response.get_json()["presentacion"]["bloques"]


def test_suggest_invalid(client, sample_guide):
    response = client.post("/api/suggest", json={"guide": sample_guide, "section": "nope"})
    assert response.status_code == 400


def test_draft_roundtrip(client, sample_guide):
    created = client.post("/api/draft", json={"guide": sample_guide}).get_json()
    loaded = client.get(f"/api/draft/{created['id']}")
    assert loaded.status_code == 200
    assert loaded.get_json()["identificacion"]["programa"] == sample_guide["identificacion"]["programa"]


def test_draft_invalid_id(client):
    assert client.get("/api/draft/..").status_code == 400


def test_download_traversal(client):
    assert client.get("/download/..").status_code == 400
    assert client.get("/download/inexistente.docx").status_code == 404


def test_generate_docx(client, sample_guide):
    response = client.post("/api/generate", json={"guide": sample_guide, "format": "docx"})
    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert client.get(data["download"]).status_code == 200


def test_config_save_masks_key(client):
    response = client.post(
        "/api/config",
        json={"llm": {"enabled": True, "base_url": "https://x/v1", "model": "m", "api_key": "secret"}},
    )
    data = response.get_json()
    assert response.status_code == 200
    assert data["llm"]["api_key"] == "***"
    assert data["llm"]["has_api_key"] is True


def test_config_test_disabled(client):
    assert client.post("/api/config/test").status_code == 400
