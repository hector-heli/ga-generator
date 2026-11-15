import zipfile

from openpyxl import load_workbook

from services import planeacion_xlsx


PROGRAMA = {
    "denominacion": "AUTOMATIZACION INDUSTRIAL",
    "codigo": "224312",
    "version": "1",
    "tipo": "Titulada",
    "ambientes": [{"nombre": "Laboratorio de automatización"}],
    "materiales": [{"nombre": "PLC", "cantidad": "5"}],
}
COMPETENCIA = {
    "codigo_norma": "N1",
    "nombre": "Programar",
    "conocimientos_saber": [
        {"texto": "Lógica de programación", "resultado_id": "r1"},
        {"texto": "Saber de otro RAE", "resultado_id": "r2"},
        {"texto": "Saber general", "resultado_id": None},
    ],
    "conocimientos_proceso": [{"texto": "Diseñar soluciones", "resultado_id": "r1"}],
    "criterios": [{"texto": "Cumple especificaciones", "resultado_id": "r1"}],
}
RESULTADO = {"id": "r1", "codigo": "RAE23", "denominacion": "Sistemas embebidos", "duracion": 48}
CONTEXTO = {
    "proyecto_nombre": "Proyecto formativo X",
    "proyecto_codigo": "SOFIA-1",
    "proyecto_regional": "Antioquia",
    "proyecto_centro": "Centro Metalmecánico",
    "fase_nombre": "Planeación",
    "actividad_nombre": "Diseñar el sistema",
}
META = {"equipo_curricular": "Equipo curricular", "fecha_elaboracion": "2026-11-15"}


def test_build_planeacion_prellena_hoja_fase(tmp_path):
    output = tmp_path / "planeacion.xlsx"
    planeacion_xlsx.build_planeacion_xlsx(
        PROGRAMA, COMPETENCIA, RESULTADO, CONTEXTO, META, output
    )

    workbook = load_workbook(output, data_only=False)
    assert workbook.sheetnames == ["Instrucciones", "FASE"]
    sheet = workbook["FASE"]
    assert sheet["E9"].value == "15/11/2026"
    assert sheet["E10"].value == "AUTOMATIZACION INDUSTRIAL"
    assert sheet["E11"].value == "Titulada"
    assert sheet["E12"].value == "224312 - V1"
    assert sheet["E13"].value == "Proyecto formativo X"
    assert sheet["E14"].value == "SOFIA-1"
    assert sheet["E15"].value == "Equipo curricular"
    assert sheet["K15"].value == "Regional: Antioquia - Centro: Centro Metalmecánico"

    assert sheet["A18"].value == "Planeación"
    assert sheet["B18"].value == "Diseñar el sistema"
    assert sheet["C18"].value == "N1 - Programar"
    assert sheet["D18"].value == "RAE23 - Sistemas embebidos"
    assert sheet["E18"].value == "Lógica de programación\nSaber general"
    assert sheet["F18"].value == "Diseñar soluciones"
    assert sheet["G18"].value == "Cumple especificaciones"
    assert sheet["I18"].value == 48
    assert sheet["M18"].value == "Laboratorio de automatización"
    assert sheet["N18"].value == "PLC - 5"


def test_build_planeacion_conserva_imagenes_y_estilos(tmp_path):
    output = tmp_path / "planeacion.xlsx"
    planeacion_xlsx.build_planeacion_xlsx(
        PROGRAMA, COMPETENCIA, RESULTADO, CONTEXTO, META, output
    )
    with zipfile.ZipFile(output) as zf:
        media = [name for name in zf.namelist() if name.startswith("xl/media/")]
        assert media == ["xl/media/image1.png", "xl/media/image2.png", "xl/media/image3.jpeg"]
        sheet = zf.read(planeacion_xlsx.SHEET_XML).decode("utf-8")
        assert 'r="E10" s="38"' in sheet
        assert 'r="I18" s="6"' in sheet


def test_build_planeacion_sin_duracion_deja_horas_vacias(tmp_path):
    output = tmp_path / "planeacion.xlsx"
    planeacion_xlsx.build_planeacion_xlsx(
        PROGRAMA, COMPETENCIA, {**RESULTADO, "duracion": 0}, CONTEXTO, {}, output
    )
    sheet = load_workbook(output)["FASE"]
    assert sheet["I18"].value is None
    assert sheet["E9"].value  # la fecha por defecto siempre se escribe
