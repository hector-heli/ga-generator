import copy
import re
from urllib.parse import parse_qs, urlparse

from docx import Document

from services import store
from services.defaults import new_uid, normalize_guide
from services.validation import validate_guide

TOKEN_RE = re.compile(r'name="csrf_token" value="([^"]+)"')
GUIDE_LOCATION_RE = re.compile(r"/guias/([A-Za-z0-9_-]+)/")


def csrf(client, path="/"):
    response = client.get(path)
    assert response.status_code == 200
    match = TOKEN_RE.search(response.get_data(as_text=True))
    assert match, f"No se encontró el token CSRF en {path}"
    return match.group(1)


def create_guide(client, **fields):
    token = csrf(client)
    response = client.post(
        "/guias/nueva",
        data={"csrf_token": token, **fields},
        follow_redirects=False,
    )
    assert response.status_code == 303
    match = GUIDE_LOCATION_RE.search(response.headers["Location"])
    assert match
    return match.group(1)


def test_dashboard_has_generator_title_and_forms(client):
    response = client.get("/")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Generador de Guías de Aprendizaje" in html
    assert "Nueva guía" in html
    assert "Importar documento" in html


def test_create_guide_and_persist_identification(client):
    guide_id = create_guide(
        client,
        programa="Automatización de sistemas mecatrónicos",
        codigo_programa="224312",
        resultados_aprendizaje="RAE23 · Implementar sistemas",
        duracion_horas="8",
    )

    stored = store.get_guide(guide_id)
    assert stored["identificacion"]["programa"] == "Automatización de sistemas mecatrónicos"
    assert stored["identificacion"]["duracion_horas"] == 8

    page = client.get(f"/guias/{guide_id}/identificacion")
    html = page.get_data(as_text=True)
    assert page.status_code == 200
    assert "224312" in html

    token = csrf(client, f"/guias/{guide_id}/identificacion")
    response = client.post(
        f"/guias/{guide_id}/identificacion",
        data={
            "csrf_token": token,
            "action": "save",
            "programa": "Programa actualizado",
            "codigo_programa": "999999",
            "competencia": "Competencia de prueba",
            "resultados_aprendizaje": "RAE01",
            "duracion_horas": "12",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    stored = store.get_guide(guide_id)
    assert stored["identificacion"]["programa"] == "Programa actualizado"
    assert stored["identificacion"]["competencia"] == "Competencia de prueba"


def test_all_guide_sections_and_settings_render(client):
    guide_id = create_guide(client, programa="Programa", codigo_programa="1")
    assert client.get(f"/guias/{guide_id}").status_code == 303
    paths = [
        f"/guias/{guide_id}/identificacion",
        f"/guias/{guide_id}/presentacion",
        f"/guias/{guide_id}/momentos",
        f"/guias/{guide_id}/momentos/reflexion_inicial",
        f"/guias/{guide_id}/momentos/contextualizacion",
        f"/guias/{guide_id}/momentos/apropiacion",
        f"/guias/{guide_id}/momentos/transferencia",
        f"/guias/{guide_id}/glosario",
        f"/guias/{guide_id}/referentes",
        f"/guias/{guide_id}/control",
        f"/guias/{guide_id}/resumen",
    ]
    for path in paths:
        assert client.get(path).status_code == 200, path
    assert client.get("/configuracion").status_code == 200


def test_web_post_requires_csrf(client):
    assert client.post("/guias/nueva", data={}).status_code == 400
    assert (
        client.post(
            "/guias/nueva", data={"csrf_token": "incorrecto"}
        ).status_code
        == 400
    )


def test_add_delete_and_reorder_apropiacion_activities(client):
    guide_id = create_guide(client, programa="Programa", codigo_programa="1")
    path = f"/guias/{guide_id}/momentos/apropiacion"
    token = csrf(client, path)
    stored = normalize_guide(store.get_guide(guide_id))
    first_uid = stored["momentos"]["apropiacion"]["actividades"][0]["uid"]

    response = client.post(
        path,
        data={
            "csrf_token": token,
            "action": "add",
            "activity_order": first_uid,
            f"act.{first_uid}.titulo": "Actividad uno",
            f"act.{first_uid}.duracion_horas": "4",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    stored = normalize_guide(store.get_guide(guide_id))
    activities = stored["momentos"]["apropiacion"]["actividades"]
    assert len(activities) == 2
    assert activities[0]["titulo"] == "Actividad uno"

    # Add a second one with a known title, then reorder it above the first.
    token = csrf(client, path)
    second_uid = activities[1]["uid"]
    client.post(
        path,
        data={
            "csrf_token": token,
            "action": "save",
            "activity_order": f"{activities[0]['uid']},{second_uid}",
            f"act.{activities[0]['uid']}.titulo": "Actividad uno",
            f"act.{activities[0]['uid']}.duracion_horas": "4",
            f"act.{second_uid}.titulo": "Actividad dos",
            f"act.{second_uid}.duracion_horas": "2",
        },
    )

    token = csrf(client, path)
    response = client.post(
        path,
        data={
            "csrf_token": token,
            "action": f"up:{second_uid}",
            "activity_order": f"{activities[0]['uid']},{second_uid}",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    stored = normalize_guide(store.get_guide(guide_id))
    activities = stored["momentos"]["apropiacion"]["actividades"]
    assert [activity["titulo"] for activity in activities] == [
        "Actividad dos",
        "Actividad uno",
    ]

    token = csrf(client, path)
    client.post(
        path,
        data={
            "csrf_token": token,
            "action": f"delete:{second_uid}",
            "activity_order": f"{second_uid},{activities[1]['uid']}",
        },
    )
    stored = normalize_guide(store.get_guide(guide_id))
    activities = stored["momentos"]["apropiacion"]["actividades"]
    assert [activity["titulo"] for activity in activities] == ["Actividad uno"]

    # Deleting the last activity must leave the moment empty (not restore a default).
    token = csrf(client, path)
    client.post(
        path,
        data={
            "csrf_token": token,
            "action": f"delete:{activities[0]['uid']}",
            "activity_order": activities[0]["uid"],
        },
    )
    stored = normalize_guide(store.get_guide(guide_id))
    assert stored["momentos"]["apropiacion"]["actividades"] == []


def test_glossary_add_and_delete(client):
    guide_id = create_guide(client, programa="Programa", codigo_programa="1")
    path = f"/guias/{guide_id}/glosario"
    token = csrf(client, path)
    client.post(
        path,
        data={
            "csrf_token": token,
            "action": "save",
            "glosario.0.termino": "PLC",
            "glosario.0.definicion": "Controlador lógico programable",
        },
    )
    stored = store.get_guide(guide_id)
    assert stored["glosario"] == [
        {"termino": "PLC", "definicion": "Controlador lógico programable"}
    ]

    token = csrf(client, path)
    client.post(
        path,
        data={
            "csrf_token": token,
            "action": "add",
            "glosario.0.termino": "PLC",
            "glosario.0.definicion": "Controlador lógico programable",
        },
    )
    stored = store.get_guide(guide_id)
    assert len(stored["glosario"]) == 2
    assert stored["glosario"][1] == {"termino": "", "definicion": ""}

    token = csrf(client, path)
    client.post(
        path,
        data={
            "csrf_token": token,
            "action": "delete:0",
            "glosario.0.termino": "PLC",
            "glosario.0.definicion": "Controlador lógico programable",
            "glosario.1.termino": "",
            "glosario.1.definicion": "",
        },
    )
    stored = store.get_guide(guide_id)
    assert stored["glosario"] == [{"termino": "", "definicion": ""}]


def test_presentation_add_and_reorder_blocks(client):
    guide_id = create_guide(client, programa="Programa", codigo_programa="1")
    path = f"/guias/{guide_id}/presentacion"
    token = csrf(client, path)
    stored = normalize_guide(store.get_guide(guide_id))
    blocks = stored["presentacion"]["bloques"]
    order = ",".join(block["uid"] for block in blocks)
    data = {"csrf_token": token, "action": "add", "block_order": order}
    for index, block in enumerate(blocks):
        data[f"block.{block['uid']}.tipo"] = block["tipo"]
        data[f"block.{block['uid']}.texto"] = block["texto"]
    client.post(path, data=data)

    stored = normalize_guide(store.get_guide(guide_id))
    assert len(stored["presentacion"]["bloques"]) == len(blocks) + 1
    first, second = stored["presentacion"]["bloques"][0], stored["presentacion"]["bloques"][1]

    token = csrf(client, path)
    data = {
        "csrf_token": token,
        "action": f"down:{first['uid']}",
        "block_order": ",".join(
            block["uid"] for block in stored["presentacion"]["bloques"]
        ),
    }
    for block in stored["presentacion"]["bloques"]:
        data[f"block.{block['uid']}.tipo"] = block["tipo"]
        data[f"block.{block['uid']}.texto"] = block["texto"]
    client.post(path, data=data)

    stored = normalize_guide(store.get_guide(guide_id))
    assert stored["presentacion"]["bloques"][0]["uid"] == second["uid"]
    assert stored["presentacion"]["bloques"][1]["uid"] == first["uid"]


def test_references_and_control_can_be_edited(client):
    guide_id = create_guide(client, programa="Programa", codigo_programa="1")

    path = f"/guias/{guide_id}/referentes"
    token = csrf(client, path)
    client.post(
        path,
        data={
            "csrf_token": token,
            "action": "add",
            "referencia.0": "Norma técnica de referencia",
        },
    )
    stored = store.get_guide(guide_id)
    assert stored["referencias"] == ["Norma técnica de referencia", ""]

    path = f"/guias/{guide_id}/control"
    token = csrf(client, path)
    client.post(
        path,
        data={
            "csrf_token": token,
            "action": "add_cambio",
            "autor.0.nombre": "Ana Instructora",
            "autor.0.cargo": "Instructora",
            "autor.0.dependencia": "Centro Metalmecánico",
            "autor.0.fecha": "2026-11-10",
            "cambio.0.nombre": "Ana Instructora",
            "cambio.0.cargo": "Instructora",
            "cambio.0.dependencia": "Centro Metalmecánico",
            "cambio.0.fecha": "2026-11-10",
            "cambio.0.razon": "Ajuste de evidencias",
        },
    )
    stored = store.get_guide(guide_id)
    assert stored["control_documento"]["autores"][0]["nombre"] == "Ana Instructora"
    assert len(stored["control_cambios"]) == 2
    assert stored["control_cambios"][0]["razon"] == "Ajuste de evidencias"


def test_settings_form_saves_masked_key(client):
    token = csrf(client, "/configuracion")
    response = client.post(
        "/configuracion",
        data={
            "csrf_token": token,
            "llm_enabled": "on",
            "base_url": "https://example.test/v1",
            "model": "modelo-prueba",
            "api_key": "secreto",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    page = client.get("/configuracion").get_data(as_text=True)
    assert "https://example.test/v1" in page
    assert "Clave configurada" in page
    assert "secreto" not in page


def test_suggest_without_llm_warns_and_uses_templates(client):
    guide_id = create_guide(client, programa="Programa", codigo_programa="1")
    path = f"/guias/{guide_id}/glosario"
    token = csrf(client, path)
    page = client.post(
        path,
        data={"csrf_token": token, "action": "suggest", "usar_ia": "on"},
        follow_redirects=True,
    )
    html = page.get_data(as_text=True)
    assert "se usaron las plantillas locales" in html
    assert store.get_guide(guide_id)["glosario"]


def test_cleared_activity_title_is_kept_empty(client):
    guide_id = create_guide(client, programa="Programa", codigo_programa="1")
    path = f"/guias/{guide_id}/momentos/apropiacion"
    stored = normalize_guide(store.get_guide(guide_id))
    activity = stored["momentos"]["apropiacion"]["actividades"][0]

    token = csrf(client, path)
    client.post(
        path,
        data={
            "csrf_token": token,
            "action": "save",
            "activity_order": activity["uid"],
            f"act.{activity['uid']}.titulo": "",
            f"act.{activity['uid']}.duracion_horas": "0",
        },
    )

    stored = normalize_guide(store.get_guide(guide_id))
    assert stored["momentos"]["apropiacion"]["actividades"][0]["titulo"] == ""
    validation = validate_guide(stored)
    assert any("falta el título" in error for error in validation["errors"])


def test_generate_from_web_contains_multiple_appropriation_activities(
    client, sample_guide, tmp_path
):
    guide = normalize_guide(sample_guide)
    extra = copy.deepcopy(guide["momentos"]["apropiacion"]["actividades"][0])
    extra["uid"] = new_uid()
    extra["titulo"] = "Actividad de apropiación adicional"
    extra["duracion_horas"] = 2
    guide["momentos"]["apropiacion"]["actividades"].append(extra)
    guide_id = store.create_guide(guide)

    path = f"/guias/{guide_id}/resumen"
    token = csrf(client, path)
    response = client.post(
        f"/guias/{guide_id}/generar",
        data={"csrf_token": token, "format": "docx"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    query = parse_qs(urlparse(response.headers["Location"]).query)
    filename = query["archivo"][0]
    assert filename.endswith(".docx")

    generated = tmp_path / "output" / filename
    assert generated.exists()
    text = "\n".join(paragraph.text for paragraph in Document(str(generated)).paragraphs)
    assert "Actividad de apropiación adicional" in text
    assert guide["momentos"]["apropiacion"]["actividades"][0]["titulo"] in text


def test_missing_guide_returns_404(client):
    assert client.get("/guias/no-existe/identificacion").status_code == 404
    assert client.get("/guias/../../etc/identificacion").status_code == 404
