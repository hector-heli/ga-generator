import re
import zipfile

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

from services.docx_builder import BULLET_STYLE, build_docx


def _build(sample_guide, tmp_path):
    output = tmp_path / "guia.docx"
    build_docx(sample_guide, output)
    return output, Document(str(output))


def _find_paragraph(document, text):
    for paragraph in document.paragraphs:
        if paragraph.text.strip() == text:
            return paragraph
    raise AssertionError(f"No se encontró el párrafo: {text}")


def test_build_docx(sample_guide, tmp_path):
    output, document = _build(sample_guide, tmp_path)
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert output.exists()
    assert output.stat().st_size > 1000
    assert "FORMATO GUÍA DE APRENDIZAJE" in text
    assert "IDENTIFICACIÓN DE LA GUIA DE APRENDIZAJE" in text
    assert document.tables


def test_titulos_respetan_los_estilos_de_la_plantilla(sample_guide, tmp_path):
    _, document = _build(sample_guide, tmp_path)

    process = _find_paragraph(document, "PROCESO DE GESTIÓN DE FORMACIÓN PROFESIONAL INTEGRAL")
    assert process.style.name == "Heading 1"
    heading = document.styles["Heading 1"]
    assert heading.font.bold is True
    assert str(heading.font.color.rgb) == "262626"

    format_title = _find_paragraph(document, "FORMATO GUÍA DE APRENDIZAJE")
    assert format_title.style.name == "Normal"
    assert format_title.alignment == WD_ALIGN_PARAGRAPH.CENTER
    assert format_title.runs
    assert all(run.font.size.pt == 12 and run.bold for run in format_title.runs)


def test_secciones_y_momentos_usan_titulos_numerados(sample_guide, tmp_path):
    _, document = _build(sample_guide, tmp_path)

    sections = [
        "IDENTIFICACIÓN DE LA GUIA DE APRENDIZAJE",
        "PRESENTACIÓN",
        "FORMULACIÓN DE LAS ACTIVIDADES DE APRENDIZAJE",
    ]
    for section in sections:
        assert _find_paragraph(document, section).style.name == "Heading 2"

    moments = [
        "Actividades de reflexión inicial:",
        "Actividades de contextualización e identificación de conocimientos necesarios para el aprendizaje:",
        "Actividades de apropiación:",
        "Actividades de transferencia del conocimiento:",
    ]
    for moment in moments:
        assert _find_paragraph(document, moment).style.name == "Heading 3"

    for style_name in ("Heading 2", "Heading 3"):
        style = document.styles[style_name]
        numbering = style.element.find(qn("w:pPr")).find(qn("w:numPr"))
        assert numbering is not None


def test_secciones_inician_en_pagina_nueva(sample_guide, tmp_path):
    _, document = _build(sample_guide, tmp_path)

    sections = [
        "PRESENTACIÓN",
        "FORMULACIÓN DE LAS ACTIVIDADES DE APRENDIZAJE",
        "PLANTEAMIENTO DE EVIDENCIAS DE APRENDIZAJE PARA LA EVALUACIÓN EN EL PROCESO FORMATIVO.",
        "GLOSARIO DE TÉRMINOS",
        "REFERENTES BIBLIOGRÁFICOS",
        "CONTROL DEL DOCUMENTO",
        "CONTROL DE CAMBIOS (diligenciar únicamente si realiza ajustes a la guía)",
    ]
    for section in sections:
        paragraph = _find_paragraph(document, section)
        assert paragraph.paragraph_format.page_break_before is True

    identification = _find_paragraph(document, "IDENTIFICACIÓN DE LA GUIA DE APRENDIZAJE")
    assert not identification.paragraph_format.page_break_before


def test_identificacion_usa_vineta_y_valor_en_la_misma_linea(sample_guide, tmp_path):
    _, document = _build(sample_guide, tmp_path)
    identification = sample_guide["identificacion"]

    expected = {
        "Denominación del Programa de Formación:": identification["programa"],
        "Código del Programa de Formación:": identification["codigo_programa"],
        "Nombre del Proyecto Formativo (si aplica):": identification["proyecto_formativo"],
        "Fase del Proyecto (si aplica):": identification["fase"],
        "Actividad de Proyecto Formativo (si aplica):": identification["actividad_proyecto"],
        "Competencia:": identification["competencia"],
        "Resultados de Aprendizaje:": identification["resultados_aprendizaje"],
    }
    for label, value in expected.items():
        matches = [p for p in document.paragraphs if p.text.startswith(label)]
        assert len(matches) == 1
        paragraph = matches[0]
        assert paragraph.style.name == BULLET_STYLE
        assert value in paragraph.text
        assert len(paragraph.runs) == 1

    duration_label = "Duración de la Guía de Aprendizaje (horas):"
    duration = [p for p in document.paragraphs if p.text.startswith(duration_label)]
    assert len(duration) == 1
    assert duration[0].style.name == BULLET_STYLE
    assert f"{float(identification['duracion_horas']):g} H" in duration[0].text


def test_listas_usan_el_estilo_de_vineta_de_la_plantilla(sample_guide, tmp_path):
    _, document = _build(sample_guide, tmp_path)

    bullet_style = document.styles[BULLET_STYLE]
    numbering = bullet_style.element.find(qn("w:pPr")).find(qn("w:numPr"))
    assert numbering is not None

    bullets = [p for p in document.paragraphs if p.style.name == BULLET_STYLE]
    assert bullets

    numbered = [p for p in document.paragraphs if p.text.startswith(("1. ", "2. ", "3. "))]
    assert numbered
    assert all(p.style.name == "List Paragraph" for p in numbered)


def test_matriz_usa_table_grid_y_cabecera_de_la_plantilla(sample_guide, tmp_path):
    _, document = _build(sample_guide, tmp_path)

    matrix = next(table for table in document.tables if table.style.name == "Table Grid")
    assert len(matrix.columns) == 6
    assert [column.width.twips for column in matrix.columns] == [1398, 1634, 1515, 1698, 1673, 1711]

    for column in range(6):
        cell = matrix.cell(0, column)
        run = cell.paragraphs[0].runs[0]
        assert run.font.size.pt == 12
        assert run.bold is True
        assert str(run.font.color.rgb) == "FFFFFF"
        shade = cell._tc.get_or_add_tcPr().find(qn("w:shd"))
        assert shade.get(qn("w:fill")) == "262626"


def test_el_cuerpo_no_fuerza_century_gothic(sample_guide, tmp_path):
    _, document = _build(sample_guide, tmp_path)

    fonts = {
        element.get(qn("w:ascii"))
        for element in document.element.body.iter(qn("w:rFonts"))
        if element.get(qn("w:ascii"))
    }
    assert "Century Gothic" not in fonts


def test_conserva_encabezado_pie_y_logo(sample_guide, tmp_path):
    output, _ = _build(sample_guide, tmp_path)

    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        headers = "".join(
            archive.read(name).decode("utf-8") for name in names if name.startswith("word/header")
        )
        footers = "".join(
            archive.read(name).decode("utf-8") for name in names if name.startswith("word/footer")
        )
        footer_text = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", footers))
        assert "<w:drawing" in headers or "<w:pict" in headers
        assert "GFPI-F-135 V04" in footer_text
        assert any(name.startswith("word/media/") for name in names)
