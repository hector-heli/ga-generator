import copy
import re
from pathlib import Path

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor, Twips

from config import TEMPLATE_PATH
from services.defaults import MOMENT_ORDER, MOMENTS, iter_activities
from services.evidence import derive_evidence

FONT = "Century Gothic"
BLUE_FILL = "C8F0FA"
DARK_FILL = "262626"
WHITE = "FFFFFF"

MARKUP = re.compile(r"(\*\*.+?\*\*|\*[^*]+?\*)")


def _set_cell_width(cell, twips):
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_w = tc_pr.find(qn("w:tcW"))
    if tc_w is None:
        tc_w = OxmlElement("w:tcW")
        tc_pr.append(tc_w)
    tc_w.set(qn("w:w"), str(twips))
    tc_w.set(qn("w:type"), "dxa")


def _set_grid_width(table, widths):
    grid = table._tbl.tblGrid
    columns = grid.findall(qn("w:gridCol"))
    for index, width in enumerate(widths):
        if index < len(columns):
            columns[index].set(qn("w:w"), str(width))
        else:
            column = OxmlElement("w:gridCol")
            column.set(qn("w:w"), str(width))
            grid.append(column)


def _set_table_properties(table, widths):
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    table.autofit = False
    tbl_pr = table._tbl.tblPr
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:w"), str(sum(widths)))
    tbl_w.set(qn("w:type"), "dxa")
    tbl_ind = tbl_pr.find(qn("w:tblInd"))
    if tbl_ind is None:
        tbl_ind = OxmlElement("w:tblInd")
        tbl_pr.append(tbl_ind)
    tbl_ind.set(qn("w:w"), "0")
    tbl_ind.set(qn("w:type"), "dxa")
    layout = tbl_pr.find(qn("w:tblLayout"))
    if layout is None:
        layout = OxmlElement("w:tblLayout")
        tbl_pr.append(layout)
    layout.set(qn("w:type"), "fixed")
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), "4")
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), "000000")
        borders.append(element)
    existing = tbl_pr.find(qn("w:tblBorders"))
    if existing is not None:
        tbl_pr.remove(existing)
    tbl_pr.append(borders)
    _set_grid_width(table, widths)
    for row in table.rows:
        for index, cell in enumerate(row.cells):
            if index < len(widths):
                _set_cell_width(cell, widths[index])


def _shade(cell, fill, theme_tint=None):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    if theme_tint:
        shd.set(qn("w:themeFill"), "text1")
        shd.set(qn("w:themeFillTint"), theme_tint)


def _set_run(run, font=FONT, size=None, bold=None, italic=None, color=None):
    if font:
        run.font.name = font
        r_pr = run._element.get_or_add_rPr()
        r_fonts = r_pr.find(qn("w:rFonts"))
        if r_fonts is None:
            r_fonts = OxmlElement("w:rFonts")
            r_pr.insert(0, r_fonts)
        for attribute in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
            r_fonts.set(qn(attribute), font)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    if color:
        run.font.color.rgb = RGBColor.from_string(color)


def _add_runs(paragraph, text, size=None, bold=False, italic=False, color=None):
    text = str(text or "")
    for part in MARKUP.split(text):
        if not part:
            continue
        is_bold = bold
        is_italic = italic
        if part.startswith("**") and part.endswith("**") and len(part) >= 4:
            part = part[2:-2]
            is_bold = True
        elif part.startswith("*") and part.endswith("*") and len(part) >= 2:
            part = part[1:-1]
            is_italic = True
        run = paragraph.add_run(part)
        _set_run(run, size=size, bold=is_bold, italic=is_italic, color=color)


def _clean_markdown(text):
    text = str(text or "").strip()
    text = re.sub(r"^#{1,6}\s*", "", text)
    text = re.sub(r"^[\*\-•]\s+", "", text)
    return text.strip()


def _add_spacer(doc):
    paragraph = doc.add_paragraph(style="Normal")
    paragraph.paragraph_format.space_after = Pt(0)
    return paragraph


def _add_heading(doc, text, level):
    paragraph = doc.add_paragraph(style=f"Heading {level}")
    _add_runs(paragraph, text)
    return paragraph


def _add_body(doc, text, bold=False):
    lines = str(text or "").splitlines()
    for line in lines:
        line = _clean_markdown(line)
        if not line:
            continue
        paragraph = doc.add_paragraph(style="Normal")
        _add_runs(paragraph, line, bold=bold)


def _add_bullet(doc, text):
    paragraph = doc.add_paragraph(style="List Paragraph")
    _add_runs(paragraph, _clean_markdown(text))


def _add_label_value(doc, label, value):
    paragraph = doc.add_paragraph(style="Normal")
    run = paragraph.add_run(label)
    _set_run(run, bold=True, color="000000")
    if str(value or "").strip():
        value_paragraph = doc.add_paragraph(style="Normal")
        _add_runs(value_paragraph, value)
    else:
        _add_spacer(doc)


def _add_prefixed(doc, prefix, value):
    paragraph = doc.add_paragraph(style="Normal")
    run = paragraph.add_run(prefix)
    _set_run(run, bold=True, color="000000")
    if str(value or "").strip():
        _add_runs(paragraph, " " + str(value))
    return paragraph


def _set_cell_text(cell, text, size=8, bold=False, color=None, align=None, line_spacing=1.0):
    cell.text = ""
    paragraphs = []
    lines = str(text or "").splitlines() or [""]
    for index, line in enumerate(lines):
        paragraph = cell.paragraphs[0] if index == 0 else cell.add_paragraph()
        paragraph.paragraph_format.space_after = Pt(0)
        paragraph.paragraph_format.line_spacing = line_spacing
        if align is not None:
            paragraph.alignment = align
        _add_runs(paragraph, line, size=size, bold=bold, color=color)
        paragraphs.append(paragraph)
    return paragraphs


def _add_evidence_box(doc, activity, evidence_items):
    table = doc.add_table(rows=2, cols=1)
    _set_table_properties(table, [9629])
    for row in table.rows:
        _shade(row.cells[0], BLUE_FILL)

    title_cell = table.cell(0, 0)
    title_cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    title_paragraph = title_cell.paragraphs[0]
    title_paragraph.paragraph_format.space_after = Pt(0)
    title_paragraph.paragraph_format.line_spacing = 1.5
    run = title_paragraph.add_run("Resultado de la actividad")
    _set_run(run, size=12, bold=True, color="000000")

    body_cell = table.cell(1, 0)
    body_cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP
    modality = body_cell.paragraphs[0]
    modality.paragraph_format.space_after = Pt(0)
    modality.paragraph_format.line_spacing = 1.5
    run = modality.add_run("Modalidad de trabajo: ")
    _set_run(run, size=12, bold=True, color="000000")
    run = modality.add_run(str(activity.get("modalidad") or "Grupal"))
    _set_run(run, size=12, bold=True, color="000000")

    instruction = body_cell.add_paragraph()
    instruction.paragraph_format.space_after = Pt(0)
    instruction.paragraph_format.line_spacing = 1.5
    run = instruction.add_run("Presente al instructor las siguientes evidencias")
    _set_run(run, size=12, bold=True, color="000000")

    for item in evidence_items:
        paragraph = body_cell.add_paragraph(style="List Paragraph")
        paragraph.paragraph_format.space_after = Pt(0)
        paragraph.paragraph_format.line_spacing = 1.5
        text = f"{item['codigo']}. {item['descripcion']}" if item["codigo"] != "Pendiente" else "Pendiente por definir"
        _add_runs(paragraph, text, size=12, bold=True, color="000000")
    _add_spacer(doc)
    return table


def _add_evidence_matrix(doc, guide, activity_map):
    headers = [
        "Fase del proyecto formativo",
        "Actividad del proyecto formativo",
        "Actividad de Aprendizaje",
        "Evidencias de Aprendizaje",
        "Criterios de Evaluación",
        "Técnicas e Instrumentos de Evaluación",
    ]
    widths = [1398, 1634, 1515, 1698, 1673, 1711]
    groups = []
    for moment_id in ("apropiacion", "transferencia"):
        for index, activity in enumerate(guide["momentos"][moment_id]["actividades"]):
            items = activity_map.get((moment_id, index)) or [
                {"codigo": "Pendiente", "descripcion": "Pendiente por definir"}
            ]
            groups.append((activity, items))
    if not groups:
        for moment_id, _, activity, index in iter_activities(guide):
            items = activity_map.get((moment_id, index)) or []
            if items:
                groups.append((activity, items))

    table = doc.add_table(rows=1 + len(groups), cols=6)
    _set_table_properties(table, widths)
    for index, header in enumerate(headers):
        cell = table.cell(0, index)
        _shade(cell, DARK_FILL)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        _set_cell_text(
            cell,
            header,
            size=8,
            bold=True,
            color=WHITE,
            align=WD_ALIGN_PARAGRAPH.CENTER,
            line_spacing=1.0,
        )
    for row_index, (activity, items) in enumerate(groups, start=1):
        evidence_text = "\n".join(
            f"{item['codigo']}. {item['descripcion']}"
            if item["codigo"] != "Pendiente"
            else "Pendiente por definir"
            for item in items
        )
        criteria_text = "\n".join(str(item) for item in activity.get("criterios", []) if str(item).strip())
        instruments = ", ".join(str(item) for item in activity.get("instrumentos", []) if str(item).strip())
        values = [
            guide["identificacion"].get("fase", ""),
            guide["identificacion"].get("actividad_proyecto", ""),
            activity.get("titulo", ""),
            evidence_text,
            criteria_text,
            f"Técnicas: Observación directa y revisión documental\nInstrumentos: {instruments}".strip(),
        ]
        for column, value in enumerate(values):
            cell = table.cell(row_index, column)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP
            _set_cell_text(cell, value, size=8, bold=False, line_spacing=1.0)
    return table


def _add_control_table(doc, headers, label, rows, widths, keys):
    table = doc.add_table(rows=1 + max(1, len(rows)), cols=len(headers))
    _set_table_properties(table, widths)
    for index, header in enumerate(headers):
        cell = table.cell(0, index)
        _shade(cell, DARK_FILL)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        _set_cell_text(
            cell,
            header,
            size=12,
            bold=True,
            color=WHITE,
            align=WD_ALIGN_PARAGRAPH.CENTER,
            line_spacing=1.5,
        )
    data = rows or [{}]
    for row_index, item in enumerate(data, start=1):
        first = table.cell(row_index, 0)
        first.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        _set_cell_text(first, label, size=12, bold=True, line_spacing=1.5)
        for column, key in enumerate(keys, start=1):
            cell = table.cell(row_index, column)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            _set_cell_text(
                cell,
                item.get(key, "") if isinstance(item, dict) else "",
                size=12,
                bold=True,
                align=WD_ALIGN_PARAGRAPH.CENTER,
                line_spacing=1.5,
            )
    return table


def _add_materials(doc, activity):
    materials = activity.get("materiales") or {}
    consumible = str(materials.get("consumible") or "").strip()
    devolutivo = str(materials.get("devolutivo") or "").strip()
    apoyo = str(materials.get("apoyo") or "").strip()
    if not (consumible or devolutivo or apoyo):
        return
    _add_prefixed(doc, "Materiales de formación:", "")
    if consumible:
        paragraph = doc.add_paragraph(style="List Paragraph")
        run = paragraph.add_run("Consumible: ")
        _set_run(run, bold=True)
        _add_runs(paragraph, consumible)
    if devolutivo:
        paragraph = doc.add_paragraph(style="List Paragraph")
        run = paragraph.add_run("Devolutivo: ")
        _set_run(run, bold=True)
        _add_runs(paragraph, devolutivo)
    if apoyo:
        _add_prefixed(doc, "Material de apoyo:", "")
        for line in apoyo.splitlines():
            if line.strip():
                _add_bullet(doc, line)


def _add_activity(doc, moment_id, activity, index, evidence_items):
    _add_heading(doc, activity.get("titulo") or f"Actividad {index + 1}", 4)
    if str(activity.get("introduccion") or "").strip():
        _add_body(doc, activity.get("introduccion"))
    for instruction in activity.get("instrucciones", []):
        if str(instruction).strip():
            _add_bullet(doc, instruction)
    debate = activity.get("debate") or []
    if debate:
        _add_prefixed(doc, "Preguntas para el debate:", "")
        for question in debate:
            if str(question).strip():
                _add_bullet(doc, question)
    if str(activity.get("ambiente") or "").strip():
        _add_prefixed(doc, "Ambiente requerido:", activity.get("ambiente"))
    if str(activity.get("estrategias") or "").strip():
        label = "Estrategia didáctica:" if moment_id == "reflexion_inicial" else "Estrategias o técnicas didácticas activas:"
        _add_prefixed(doc, label, activity.get("estrategias"))
    instruments = [str(item) for item in activity.get("instrumentos", []) if str(item).strip()]
    if instruments:
        _add_prefixed(doc, "Instrumentos de evaluación:", "")
        for instrument in instruments:
            _add_bullet(doc, instrument)
    _add_materials(doc, activity)
    hours = float(activity.get("duracion_horas") or 0)
    _add_prefixed(doc, "Duración de la actividad:", f"{hours:g} horas.")
    if moment_id in ("apropiacion", "transferencia") or evidence_items:
        _add_evidence_box(doc, activity, evidence_items or [{"codigo": "Pendiente", "descripcion": ""}])
    _add_spacer(doc)


def _add_identification(doc, guide):
    identification = guide["identificacion"]
    _add_heading(doc, "IDENTIFICACIÓN DE LA GUIA DE APRENDIZAJE", 2)
    _add_label_value(doc, "Denominación del Programa de Formación:", identification.get("programa"))
    _add_label_value(doc, "Código del Programa de Formación:", identification.get("codigo_programa"))
    _add_label_value(doc, "Nombre del Proyecto Formativo (si aplica):", identification.get("proyecto_formativo"))
    _add_label_value(doc, "Fase del Proyecto (si aplica):", identification.get("fase"))
    _add_label_value(doc, "Actividad de Proyecto Formativo (si aplica):", identification.get("actividad_proyecto"))
    _add_label_value(doc, "Competencia:", identification.get("competencia"))
    _add_label_value(doc, "Resultados de Aprendizaje:", identification.get("resultados_aprendizaje"))
    paragraph = doc.add_paragraph(style="Normal")
    run = paragraph.add_run("Duración de la Guía de Aprendizaje (horas): ")
    _set_run(run, bold=True, color="000000")
    run = paragraph.add_run(f"{float(identification.get('duracion_horas') or 0):g} H")
    _set_run(run, bold=True, color="000000")
    _add_spacer(doc)


def _add_presentation(doc, guide):
    _add_heading(doc, "PRESENTACIÓN", 2)
    _add_spacer(doc)
    for block in guide["presentacion"].get("bloques", []):
        text = str(block.get("texto") or "")
        if not text.strip():
            continue
        tipo = block.get("tipo", "parrafo")
        if tipo == "subtitulo":
            paragraph = doc.add_paragraph(style="Normal")
            _add_runs(paragraph, _clean_markdown(text), bold=True)
        elif tipo == "lista":
            _add_bullet(doc, text)
        else:
            _add_body(doc, text)


def _add_activities(doc, guide, activity_map):
    _add_heading(doc, "FORMULACIÓN DE LAS ACTIVIDADES DE APRENDIZAJE", 2)
    for moment_id in MOMENT_ORDER:
        moment = guide["momentos"][moment_id]
        title = moment.get("titulo") or MOMENTS[moment_id]["titulo"]
        _add_heading(doc, title if title.endswith(":") else f"{title}:", 3)
        for index, activity in enumerate(moment["actividades"]):
            items = activity_map.get((moment_id, index), [])
            _add_activity(doc, moment_id, activity, index, items)


def build_docx(guide, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"No se encontró la plantilla: {TEMPLATE_PATH}")

    document = Document(str(TEMPLATE_PATH))
    body = document.element.body
    section_properties = body.find(qn("w:sectPr"))
    for child in list(body):
        if child is section_properties:
            continue
        body.remove(child)

    _add_heading(document, guide["meta"].get("titulo_proceso", "PROCESO DE GESTIÓN DE FORMACIÓN PROFESIONAL INTEGRAL"), 1)
    _add_heading(document, guide["meta"].get("titulo_formato", "FORMATO GUÍA DE APRENDIZAJE"), 1)
    _add_spacer(document)
    _add_identification(document, guide)
    _add_presentation(document, guide)
    _, activity_map = derive_evidence(guide)
    _add_activities(document, guide, activity_map)
    _add_heading(
        document,
        "PLANTEAMIENTO DE EVIDENCIAS DE APRENDIZAJE PARA LA EVALUACIÓN EN EL PROCESO FORMATIVO.",
        2,
    )
    _add_evidence_matrix(document, guide, activity_map)
    _add_spacer(document)

    _add_heading(document, "GLOSARIO DE TÉRMINOS", 2)
    if guide.get("glosario"):
        for entry in guide["glosario"]:
            term = str(entry.get("termino") or "").strip()
            definition = str(entry.get("definicion") or "").strip()
            if not term and not definition:
                continue
            paragraph = document.add_paragraph(style="Normal")
            if term:
                run = paragraph.add_run(f"{term}: ")
                _set_run(run, bold=True)
            _add_runs(paragraph, definition)
    _add_spacer(document)

    _add_heading(document, "REFERENTES BIBLIOGRÁFICOS", 2)
    for reference in guide.get("referencias", []):
        text = reference.get("texto") if isinstance(reference, dict) else reference
        if str(text or "").strip():
            _add_bullet(document, text)
    _add_spacer(document)

    _add_heading(document, "CONTROL DEL DOCUMENTO", 2)
    authors = guide.get("control_documento", {}).get("autores", [])
    _add_control_table(
        document,
        ["", "Nombre", "Cargo", "Dependencia", "Fecha"],
        "Autor (es)",
        authors,
        [1230, 2706, 1559, 1701, 2551],
        ["nombre", "cargo", "dependencia", "fecha"],
    )
    _add_spacer(document)

    _add_heading(document, "CONTROL DE CAMBIOS (diligenciar únicamente si realiza ajustes a la guía)", 2)
    _add_control_table(
        document,
        ["", "Nombre", "Cargo", "Dependencia", "Fecha", "Razón del Cambio"],
        "Autor (es)",
        guide.get("control_cambios", []),
        [1305, 2604, 1550, 1559, 795, 1934],
        ["nombre", "cargo", "dependencia", "fecha", "razon"],
    )

    document.save(str(output_path))
    return output_path
