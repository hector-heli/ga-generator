from docx import Document

from services import catalog_guides


PROGRAMA = {"id": "p1", "denominacion": "AUTOMATIZACION", "codigo": "224312"}
COMPETENCIA = {"codigo_norma": "N1", "nombre": "Programar"}
RESULTADO = {"id": "r1", "codigo": "RAE23", "denominacion": "Sistemas embebidos", "duracion": 48}
CONTEXTO = {
    "proyecto_id": "pr1",
    "proyecto_nombre": "Proyecto formativo X",
    "fase_id": "f1",
    "fase_nombre": "Planeación",
    "actividad_id": "a1",
    "actividad_nombre": "Diseñar el sistema",
    "proyecto_centro": "Centro Metalmecánico",
}


def test_build_guide_prellena_identificacion():
    guide = catalog_guides.build_guide(PROGRAMA, COMPETENCIA, RESULTADO, CONTEXTO)
    identificacion = guide["identificacion"]
    assert identificacion["programa"] == "AUTOMATIZACION"
    assert identificacion["codigo_programa"] == "224312"
    assert identificacion["competencia"] == "N1 - Programar"
    assert identificacion["resultados_aprendizaje"] == "RAE23 - Sistemas embebidos"
    assert identificacion["duracion_horas"] == 48
    assert identificacion["proyecto_formativo"] == "Proyecto formativo X"
    assert identificacion["fase"] == "Planeación"
    assert identificacion["actividad_proyecto"] == "Diseñar el sistema"
    assert identificacion["proyecto_id"] == "pr1"
    assert identificacion["fase_id"] == "f1"
    assert identificacion["actividad_id"] == "a1"
    assert identificacion["resultados_ids"] == ["r1"]
    assert guide["control_documento"]["autores"][0]["dependencia"] == "Centro Metalmecánico"


def test_build_guide_sin_contexto_deja_campos_vacios():
    guide = catalog_guides.build_guide(PROGRAMA, COMPETENCIA, RESULTADO, None)
    identificacion = guide["identificacion"]
    assert identificacion["proyecto_formativo"] == ""
    assert identificacion["fase"] == ""
    assert identificacion["actividad_proyecto"] == ""


def test_build_guide_docx(tmp_path):
    output = tmp_path / "guia.docx"
    catalog_guides.build_guide_docx(PROGRAMA, COMPETENCIA, RESULTADO, CONTEXTO, output)
    assert output.exists()
    document = Document(str(output))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "AUTOMATIZACION" in text
    assert "N1 - Programar" in text
    assert "RAE23 - Sistemas embebidos" in text
