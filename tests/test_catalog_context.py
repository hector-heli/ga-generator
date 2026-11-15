import config
from services import catalog_store


def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CATALOG_DB", tmp_path / "catalog.sqlite3")
    catalog_store.init_db()


def _crear_resultado():
    pid = catalog_store.create_programa(
        {
            "programa": {"denominacion": "AUTOMATIZACION", "codigo": "224312", "version": "1"},
            "competencias": [
                {
                    "codigo_norma": "N1",
                    "nombre": "Programar",
                    "resultados": [
                        {"codigo": "RAE23", "denominacion": "Sistemas embebidos", "duracion": 48}
                    ],
                }
            ],
            "ambientes": [],
            "materiales": [],
        }
    )
    detalle = catalog_store.get_programa_detalle(pid)
    return pid, detalle["competencias"][0]["resultados"][0]["id"]


def test_contexto_devuelve_proyecto_fase_y_actividad(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    pid, resultado_id = _crear_resultado()
    proyecto_id = catalog_store.create_proyecto(
        {
            "programa_id": pid,
            "nombre": "Proyecto formativo X",
            "codigo_sofia": "SOFIA-1",
            "regional": "Antioquia",
            "centro_formacion": "Centro Metalmecánico",
        }
    )
    fase_id = catalog_store.add_fase(proyecto_id, {"nombre": "Planeación"})
    actividad_id = catalog_store.add_actividad(fase_id, {"nombre": "Diseñar el sistema"})
    catalog_store.set_actividad_resultados(actividad_id, [resultado_id])

    contexto = catalog_store.get_resultado_contexto(resultado_id)
    assert contexto["proyecto_id"] == proyecto_id
    assert contexto["proyecto_nombre"] == "Proyecto formativo X"
    assert contexto["proyecto_codigo"] == "SOFIA-1"
    assert contexto["proyecto_regional"] == "Antioquia"
    assert contexto["proyecto_centro"] == "Centro Metalmecánico"
    assert contexto["fase_id"] == fase_id
    assert contexto["fase_nombre"] == "Planeación"
    assert contexto["actividad_id"] == actividad_id
    assert contexto["actividad_nombre"] == "Diseñar el sistema"


def test_contexto_sin_actividad_devuelve_el_proyecto_del_programa(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    pid, resultado_id = _crear_resultado()
    proyecto_id = catalog_store.create_proyecto(
        {"programa_id": pid, "nombre": "Proyecto sin actividades", "codigo_sofia": "SOFIA-2"}
    )

    contexto = catalog_store.get_resultado_contexto(resultado_id)
    assert contexto["proyecto_id"] == proyecto_id
    assert contexto["proyecto_nombre"] == "Proyecto sin actividades"
    assert "fase_id" not in contexto
    assert "actividad_id" not in contexto


def test_contexto_de_resultado_inexistente(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    assert catalog_store.get_resultado_contexto("no-existe") == {}
    assert catalog_store.get_resultado_contexto("../../etc") == {}
