import zipfile

from services import catalog_tree


def _programa(**overrides):
    programa = {
        "codigo": "224312",
        "denominacion": "AUTOMATIZACION INDUSTRIAL",
        "version": "1",
        "competencias": [
            {
                "codigo_norma": "N1",
                "nombre": "Programar",
                "resultados": [
                    {"codigo": "RAE23", "denominacion": "Sistemas embebidos", "duracion": 48},
                ],
            }
        ],
        "ambientes": [],
        "materiales": [],
    }
    programa.update(overrides)
    return programa


def test_sanitize_name_removes_invalid_characters():
    name = catalog_tree.sanitize_name('N1: Programar / "control" | prueba?*')
    assert ':' not in name
    assert "/" not in name
    assert '"' not in name
    assert "|" not in name
    assert "?" not in name
    assert "*" not in name
    assert name == "N1 Programar control prueba"


def test_sanitize_name_protege_nombres_reservados():
    assert catalog_tree.sanitize_name("CON") == "_CON"
    assert catalog_tree.sanitize_name("nul") == "_nul"


def test_programa_root_incluye_version_solo_si_existe():
    assert catalog_tree.programa_root(_programa()) == "224312-AUTOMATIZACION INDUSTRIAL-v1"
    sin_version = _programa(version="")
    assert catalog_tree.programa_root(sin_version) == "224312-AUTOMATIZACION INDUSTRIAL"
    sin_codigo = _programa(codigo="", version="")
    assert catalog_tree.programa_root(sin_codigo).startswith("SinCodigo-")


def test_build_tree_deduplica_nombres_hermanos():
    programa = _programa(
        competencias=[
            {"codigo_norma": "N1", "nombre": "Programar", "resultados": []},
            {"codigo_norma": "N1", "nombre": "Programar", "resultados": []},
        ]
    )
    tree = catalog_tree.build_tree(programa)
    names = [competencia["name"] for competencia in tree["competencias"]]
    assert names == ["N1 - Programar", "N1 - Programar (2)"]

    programa["competencias"][0]["resultados"] = [
        {"codigo": "RAE1", "denominacion": "Repetido"},
        {"codigo": "RAE1", "denominacion": "Repetido"},
    ]
    tree = catalog_tree.build_tree(programa)
    raes = [rae["name"] for rae in tree["competencias"][0]["resultados"]]
    assert raes == ["RAE1 - Repetido", "RAE1 - Repetido (2)"]


def test_build_zip_incluye_pdfs_en_raiz_y_archivos_por_rae(monkeypatch):
    monkeypatch.setattr(catalog_tree.catalog_store, "get_resultado_contexto", lambda _: {})
    programa = _programa()
    archive = catalog_tree.build_zip(
        programa,
        ("diseno.pdf", b"%PDF-1.4 diseno"),
        ("proyecto.pdf", b"%PDF-1.4 proyecto"),
    )
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()

    root = "224312-AUTOMATIZACION INDUSTRIAL-v1"
    assert f"{root}/" in names
    assert f"{root}/Diseño curricular - diseno.pdf" in names
    assert f"{root}/Proyecto formativo - proyecto.pdf" in names

    rae_path = f"{root}/N1 - Programar/RAE23 - Sistemas embebidos"
    assert f"{rae_path}/" in names
    assert f"{rae_path}/GA - RAE23 - Sistemas embebidos.docx" in names
    assert f"{rae_path}/Planeacion pedagogica - RAE23 - Sistemas embebidos.xlsx" in names
    assert f"{rae_path}/PTC RAE - RAE23 - Sistemas embebidos.xlsm" in names
    assert not any("_GFPI-F-135" in name for name in names)


def test_build_zip_sin_competencias_conserva_la_raiz():
    archive = catalog_tree.build_zip(_programa(competencias=[]))
    with zipfile.ZipFile(archive) as zf:
        assert zf.namelist() == ["224312-AUTOMATIZACION INDUSTRIAL-v1/"]
