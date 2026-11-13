import config
import services.catalog_store as cs


def test_catalog_store_crud(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CATALOG_DB", tmp_path / "catalog.sqlite3")
    cs.init_db()
    data = {
        "programa": {"denominacion": "PROG", "codigo": "123", "version": "1", "horas_total": 100},
        "competencias": [{
            "codigo_norma": "N1", "nombre": "COMP", "duracion": 40, "orden": 0,
            "resultados": [{"codigo": "RAE1", "denominacion": "R1", "duracion": 40, "orden": 0}],
            "conocimientos_proceso": [{"rae_codigo": "RAE1", "texto": "proc", "orden": 0}],
            "conocimientos_saber": [{"rae_codigo": "RAE1", "texto": "saber", "orden": 0}],
            "criterios": [{"rae_codigo": "RAE1", "texto": "crit", "orden": 0}],
        }],
        "ambientes": [{"categoria": "A", "nombre": "Lab"}],
        "materiales": [{"categoria": "M", "nombre": "PLC", "cantidad": "1"}],
    }
    pid = cs.create_programa(data)
    assert pid
    progs = cs.list_programas()
    assert progs and progs[0]["codigo"] == "123"
    detail = cs.get_programa_detalle(pid)
    assert detail["competencias"][0]["resultados"][0]["codigo"] == "RAE1"
    assert detail["ambientes"][0]["nombre"] == "Lab"
    api = cs.get_programa_api(pid)
    assert api["competencias"][0]["nombre"] == "COMP"
    # replace
    data["programa"]["denominacion"] = "PROG2"
    cs.replace_programa(pid, data)
    assert cs.get_programa(pid)["denominacion"] == "PROG2"
    cs.delete_programa(pid)
    assert cs.get_programa(pid) is None
