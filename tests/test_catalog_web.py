import io
import re
import zipfile

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


def _crear_programa():
    data = {
        "programa": {"denominacion": "AUTOMATIZACION", "codigo": "224312", "version": "1", "tipo": "Titulada"},
        "competencias": [{
            "codigo_norma": "N1", "nombre": "Programar", "duracion": 48, "orden": 0,
            "resultados": [{"codigo": "RAE23", "denominacion": "Sistemas embebidos", "duracion": 48, "orden": 0}],
            "conocimientos_proceso": [{"texto": "Diseñar soluciones", "rae_codigo": "RAE23"}],
            "conocimientos_saber": [{"texto": "Lógica de programación", "rae_codigo": "RAE23"}],
            "criterios": [{"texto": "Cumple especificaciones", "rae_codigo": "RAE23"}],
        }],
        "ambientes": [{"nombre": "Laboratorio"}],
        "materiales": [{"nombre": "PLC", "cantidad": "5"}],
    }
    return catalog_store.create_programa(data)



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
    assert "Andamiaje ZIP" in r.get_data(as_text=True)

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


def test_andamiaje_formulario_y_descarga_zip(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    pid = _crear_programa()

    r = client.get("/programas")
    assert "Andamiaje ZIP" in r.get_data(as_text=True)

    r = client.get(f"/programas/{pid}/andamiaje")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'name="pdf_diseno"' in html
    assert 'name="pdf_proyecto"' in html
    assert "N1 - Programar" in html
    assert "RAE23 - Sistemas embebidos" in html

    r = client.post(
        f"/programas/{pid}/andamiaje.zip",
        data={
            "pdf_diseno": (io.BytesIO(b"%PDF-1.4 diseno"), "diseno.pdf"),
            "pdf_proyecto": (io.BytesIO(b"%PDF-1.4 proyecto"), "proyecto.pdf"),
            "equipo_curricular": "Equipo curricular",
            "regional_centro": "Regional Antioquia - Centro Metalmecánico",
            "fecha_elaboracion": "2026-11-15",
        },
        content_type="multipart/form-data",
    )
    assert r.status_code == 200
    assert r.mimetype == "application/zip"

    with zipfile.ZipFile(io.BytesIO(r.data)) as zf:
        names = zf.namelist()
    root = "224312-AUTOMATIZACION-v1"
    assert f"{root}/Diseño curricular - diseno.pdf" in names
    assert f"{root}/Proyecto formativo - proyecto.pdf" in names
    rae_path = f"{root}/N1 - Programar/RAE23 - Sistemas embebidos"
    assert f"{rae_path}/GA - RAE23 - Sistemas embebidos.docx" in names
    assert f"{rae_path}/Planeacion pedagogica - RAE23 - Sistemas embebidos.xlsx" in names
    assert f"{rae_path}/PTC RAE - RAE23 - Sistemas embebidos.xlsm" in names


def test_andamiaje_exige_los_dos_pdf(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    pid = _crear_programa()

    r = client.post(
        f"/programas/{pid}/andamiaje.zip",
        data={"pdf_diseno": (io.BytesIO(b"%PDF-1.4 diseno"), "diseno.pdf")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert "Adjunte el PDF de proyecto formativo" in r.get_data(as_text=True)


def test_andamiaje_rechaza_archivos_que_no_son_pdf(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    pid = _crear_programa()

    r = client.post(
        f"/programas/{pid}/andamiaje.zip",
        data={
            "pdf_diseno": (io.BytesIO(b"no es pdf"), "diseno.docx"),
            "pdf_proyecto": (io.BytesIO(b"%PDF-1.4 proyecto"), "proyecto.pdf"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert "debe tener extensión .pdf" in r.get_data(as_text=True)


def test_andamiaje_rechaza_pdf_con_contenido_invalido(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    pid = _crear_programa()

    r = client.post(
        f"/programas/{pid}/andamiaje.zip",
        data={
            "pdf_diseno": (io.BytesIO(b"no es pdf"), "diseno.pdf"),
            "pdf_proyecto": (io.BytesIO(b"%PDF-1.4 proyecto"), "proyecto.pdf"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert "no parece ser un PDF válido" in r.get_data(as_text=True)


def test_andamiaje_requiere_csrf(tmp_path, monkeypatch):
    client = _setup(tmp_path, monkeypatch)
    pid = _crear_programa()
    monkeypatch.setitem(app_module.app.config, "CSRF_ENABLED", True)

    r = client.post(
        f"/programas/{pid}/andamiaje.zip",
        data={
            "pdf_diseno": (io.BytesIO(b"%PDF-1.4 diseno"), "diseno.pdf"),
            "pdf_proyecto": (io.BytesIO(b"%PDF-1.4 proyecto"), "proyecto.pdf"),
        },
        content_type="multipart/form-data",
    )
    assert r.status_code == 400
