import re

TOKEN_RE = re.compile(r'name="csrf_token" value="([^"]+)"')


def _csrf(client):
    response = client.get("/")
    match = TOKEN_RE.search(response.get_data(as_text=True))
    assert match
    return match.group(1)


def test_identificacion_has_catalog_prefill(client):
    r = client.post("/guias/nueva", data={"csrf_token": _csrf(client), "titulo": "T"}, follow_redirects=True)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Cargar desde catálogo" in html or "cat-programa" in html


def test_identificacion_prefill_ui_present(client):
    r = client.post("/guias/nueva", data={"csrf_token": _csrf(client), "titulo": "X"})
    assert r.status_code in (302, 303)
    loc = r.headers.get("Location", "")
    r2 = client.get(loc)
    html = r2.get_data(as_text=True)
    assert 'id="cat-programa"' in html
    assert "catalog_prefill.js" in html
