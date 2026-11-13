import io
import re

import app as app_module
import config
from services import catalog_store


def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "GUIDES_DB", tmp_path / "guides.sqlite3")
    monkeypatch.setattr(config, "CATALOG_DB", tmp_path / "catalog.sqlite3")
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    monkeypatch.setitem(app_module.app.config, "CSRF_ENABLED", False)
    catalog_store.init_db()
    return app_module.app.test_client()


def test_catalog_pages_and_api(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    r = client.get("/programas")
    assert r.status_code == 200
    assert "Programas de formación" in r.get_data(as_text=True)

    data = {
        "programa": {"denominacion": "AUTOMATIZACION", "codigo": "224312", "version": "1"},
        "competencias": [{
            "codigo_norma": "N1", "nombre": "Programar", "duracion": 48, "orden": 0,
            "resultados": [{"codigo": "RAE23", "denominacion": "Sistemas embebidos", "duracion": 48, "orden": 0}],
            "conocimientos_proceso": [], "conocimientos_saber": [], "criterios": [],
        }],
        "ambientes": [], "materiales": [],
    }
    pid = catalog_store.create_programa(data)

    r = client.get(f"/programas/{pid}")
    assert r.status_code == 200
    assert "RAE23" in r.get_data(as_text=True)

    r = client.get("/api/catalog/programas")
    assert r.status_code == 200
    js = r.get_json()
    assert js["programas"] and js["programas"][0]["codigo"] == "224312"
    comp_id = js["programas"][0]["competencias"][0]["id"]

    r = client.get(f"/api/catalog/competencias/{comp_id}/resultados")
    assert r.status_code == 200
    assert r.get_json()["resultados"][0]["codigo"] == "RAE23"


def test_catalog_import_preview_save(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    parsed = {
        "programa": {"denominacion": "X", "codigo": "999", "version": "1", "horas_total": 10},
        "competencias": [], "ambientes": [], "materiales": [],
        "meta": {"competencias_count": 0, "resultados_count": 0, "horas_competencias": 0},
        "warnings": [],
    }
    monkeypatch.setattr(app_module.catalog_importer, "parse_design_pdf", lambda p: parsed)
    pdf_bytes = io.BytesIO(b"%PDF-1.4 test")
    r = client.post("/programas/importar", data={"step": "preview", "file": (pdf_bytes, "diseno.pdf")}, content_type="multipart/form-data")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Vista previa" in html
    match = re.search(r'name="preview_token" value="([^"]+)"', html)
    assert match

    r = client.post("/programas/importar", data={"step": "save", "preview_token": match.group(1)}, follow_redirects=True)
    assert r.status_code == 200
    assert catalog_store.find_programa("999", "1") is not None
