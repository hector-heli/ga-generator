import re
import unicodedata

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from services.defaults import empty_activity, empty_guide, normalize_guide
from services.suggestions import suggest_activity


def _norm(text):
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text).strip().lower()


def _hours(text):
    match = re.search(r"\d+(?:[.,]\d+)?", str(text or ""))
    return float(match.group(0).replace(",", ".")) if match else 0


def _after_colon(text):
    text = str(text or "")
    if ":" in text:
        return text.split(":", 1)[1].strip()
    return ""


def _identification_field(label):
    key = _norm(label)
    mapping = [
        ("denominacion del programa", "programa"),
        ("codigo del programa", "codigo_programa"),
        ("nombre del proyecto formativo", "proyecto_formativo"),
        ("fase del proyecto", "fase"),
        ("actividad de proyecto formativo", "actividad_proyecto"),
        ("competencia", "competencia"),
        ("resultados de aprendizaje", "resultados_aprendizaje"),
    ]
    for needle, field in mapping:
        if needle in key:
            return field
    if "duracion de la guia de aprendizaje" in key:
        return "duracion_horas"
    return None


def _is_identification_label(text):
    field = _identification_field(text)
    if not field:
        return False
    prefix = _norm(text.split(":", 1)[0])
    return prefix in (
        "denominacion del programa de formacion",
        "codigo del programa de formacion",
        "nombre del proyecto formativo (si aplica)",
        "fase del proyecto (si aplica)",
        "actividad de proyecto formativo (si aplica)",
        "competencia",
        "resultados de aprendizaje",
        "duracion de la guia de aprendizaje (horas)",
    )


def _set_identification(identification, label, value):
    field = _identification_field(label)
    if not field:
        return False
    if field == "duracion_horas":
        identification["duracion_horas"] = _hours(value or label)
    else:
        identification[field] = str(value or "").strip()
    return True


def _parse_evidence_table(table, activity):
    if not activity:
        return
    if len(table.rows) < 2 or len(table.columns) < 1:
        return
    first = _norm(table.cell(0, 0).text)
    if "resultado de la actividad" not in first:
        return
    text = table.cell(1, 0).text
    for line in text.splitlines():
        line = line.strip()
        if re.match(r"^Ev\s*\d+", line, re.IGNORECASE):
            description = re.sub(r"^Ev\s*\d+[\.\):-]?\s*", "", line, flags=re.IGNORECASE).strip()
            if description:
                activity["evidencias"].append(description)


def _parse_matrix(table, guide):
    if len(table.columns) != 6:
        return
    header = " ".join(_norm(cell.text) for cell in table.rows[0].cells)
    if "evidencias de aprendizaje" not in header:
        return
    for row in table.rows[1:]:
        cells = [cell.text.strip() for cell in row.cells]
        if len(cells) < 6:
            continue
        if not cells[2].strip() and not cells[3].strip():
            continue
        guide["evidencias"].append(
            {
                "fase": cells[0],
                "actividad_proyecto": cells[1],
                "actividad_aprendizaje": cells[2],
                "evidencia": cells[3],
                "criterios": cells[4],
                "tecnicas": cells[5],
            }
        )


def _parse_control(table, guide):
    if len(table.columns) not in (5, 6):
        return
    header = " ".join(_norm(cell.text) for cell in table.rows[0].cells)
    if "nombre" not in header or "cargo" not in header:
        return
    is_changes = "razon del cambio" in header
    for row in table.rows[1:]:
        cells = [cell.text.strip() for cell in row.cells]
        if not any(cells):
            continue
        if is_changes:
            guide["control_cambios"].append(
                {
                    "nombre": cells[1] if len(cells) > 1 else "",
                    "cargo": cells[2] if len(cells) > 2 else "",
                    "dependencia": cells[3] if len(cells) > 3 else "",
                    "fecha": cells[4] if len(cells) > 4 else "",
                    "razon": cells[5] if len(cells) > 5 else "",
                }
            )
        else:
            guide["control_documento"]["autores"] = [
                {
                    "nombre": cells[1] if len(cells) > 1 else "",
                    "cargo": cells[2] if len(cells) > 2 else "",
                    "dependencia": cells[3] if len(cells) > 3 else "",
                    "fecha": cells[4] if len(cells) > 4 else "",
                }
            ]


def _reset_activity(activity, moment_id, title):
    template = empty_activity(moment_id, 0)
    for key, value in template.items():
        activity[key] = value
    activity["titulo"] = title


def _has_content(activity):
    return bool(
        str(activity.get("introduccion") or "").strip()
        or activity.get("instrucciones")
        or activity.get("debate")
        or str(activity.get("ambiente") or "").strip()
        or str(activity.get("estrategias") or "").strip()
        or activity.get("instrumentos")
        or activity.get("evidencias")
        or activity.get("criterios")
        or float(activity.get("duracion_horas") or 0)
        or any(str(value or "").strip() for value in (activity.get("materiales") or {}).values())
    )


def _clean_activity(activity, moment_id, index):
    title = str(activity.get("titulo") or "").strip()
    hours_match = re.search(r"\((\d+(?:[.,]\d+)?)\s*H\)\s*$", title, re.IGNORECASE)
    if hours_match:
        activity["duracion_horas"] = float(hours_match.group(1).replace(",", "."))
        activity["titulo"] = re.sub(
            r"\(\s*\d+(?:[.,]\d+)?\s*H\s*\)\s*$", "", title, flags=re.IGNORECASE
        ).strip()
    ambiente = str(activity.get("ambiente") or "")
    if "duracion" in _norm(ambiente):
        if not float(activity.get("duracion_horas") or 0):
            match = re.search(r"duraci[oó]n[^:]*:\s*(\d+(?:[.,]\d+)?)", ambiente, re.IGNORECASE)
            if match:
                activity["duracion_horas"] = float(match.group(1).replace(",", "."))
        ambiente = re.sub(r"\n?\s*Duraci[oó]n[^\n]*", "", ambiente, flags=re.IGNORECASE).strip()
        activity["ambiente"] = ambiente
    if not _has_content(activity):
        suggested = suggest_activity({"identificacion": {}, "momentos": {}}, moment_id, index)
        title = str(activity.get("titulo") or "").strip() or suggested.get("titulo", "")
        original = dict(activity)
        activity.update(suggested)
        _defaults = {"Análisis de situación problema", "Contraste de soluciones tecnológicas", "Implementar y comisionar el sistema", "Integrar el sistema a una red IoT"}
        if title and title not in _defaults:
            activity["titulo"] = title
        elif original.get("titulo") and str(original["titulo"]).strip() and original["titulo"] not in _defaults:
            activity["titulo"] = str(original["titulo"]).strip()
        else:
            activity["titulo"] = suggested.get("titulo", title)


def import_docx(path):
    document = Document(str(path))
    guide = empty_guide()
    for moment_id in ("reflexion_inicial", "contextualizacion", "apropiacion", "transferencia"):
        guide["momentos"][moment_id]["actividades"] = []
    guide["presentacion"]["bloques"] = []
    guide["glosario"] = []
    guide["referencias"] = []
    guide["evidencias"] = []
    guide["control_cambios"] = []
    warnings = []

    section = None
    moment_id = None
    activity = None
    placeholder = False
    current_field = None
    pending_label = None

    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            paragraph = Paragraph(child, document)
            text = paragraph.text.strip()
            if not text:
                continue
            style = paragraph.style.name if paragraph.style is not None else ""
            normalized = _norm(text)

            if style in ("Heading 1", "Heading 2"):
                if "identificacion de la guia" in normalized:
                    section = "identificacion"
                elif normalized == "presentacion":
                    section = "presentacion"
                elif "formulacion de las actividades" in normalized:
                    section = "formulacion"
                elif "planteamiento de evidencias" in normalized:
                    section = "evidencias"
                elif "glosario" in normalized:
                    section = "glosario"
                elif "referentes" in normalized:
                    section = "referencias"
                elif "control del documento" in normalized:
                    section = "control_documento"
                elif "control de cambios" in normalized:
                    section = "control_cambios"
                else:
                    section = None
                moment_id = None
                activity = None
                placeholder = False
                current_field = None
                pending_label = None
                continue

            if style == "Heading 3" and section == "formulacion":
                if "reflexion" in normalized:
                    moment_id = "reflexion_inicial"
                elif "contextualizacion" in normalized:
                    moment_id = "contextualizacion"
                elif "apropiacion" in normalized:
                    moment_id = "apropiacion"
                elif "transferencia" in normalized:
                    moment_id = "transferencia"
                else:
                    continue
                if not guide["momentos"][moment_id]["actividades"]:
                    activity = empty_activity(moment_id, 0)
                    _reset_activity(activity, moment_id, activity["titulo"])
                    guide["momentos"][moment_id]["actividades"].append(activity)
                    placeholder = True
                else:
                    activity = guide["momentos"][moment_id]["actividades"][-1]
                    placeholder = False
                current_field = None
                continue

            if style == "Heading 4" and section == "formulacion":
                if "preguntas para el debate" in normalized:
                    current_field = "debate"
                    placeholder = False
                    continue
                if not moment_id:
                    continue
                if placeholder and not _has_content(activity):
                    _reset_activity(activity, moment_id, text)
                else:
                    activity = empty_activity(
                        moment_id, len(guide["momentos"][moment_id]["actividades"])
                    )
                    activity["titulo"] = text
                    guide["momentos"][moment_id]["actividades"].append(activity)
                placeholder = False
                current_field = None
                continue

            if section == "identificacion":
                if _is_identification_label(text):
                    label, value = (text.split(":", 1) + [""])[:2] if ":" in text else (text, "")
                    if value.strip():
                        _set_identification(guide["identificacion"], label, value)
                        pending_label = None
                    else:
                        pending_label = label
                    continue
                if pending_label:
                    _set_identification(guide["identificacion"], pending_label, text)
                    pending_label = None
                continue

            if section == "presentacion":
                if normalized.startswith("2.3 proyeccion del egresado"):
                    continue
                if text.startswith("###"):
                    guide["presentacion"]["bloques"].append({"tipo": "subtitulo", "texto": text})
                elif text.startswith("*") or text.startswith("-") or re.match(r"^\d+\.\s+", text):
                    guide["presentacion"]["bloques"].append({"tipo": "lista", "texto": text})
                else:
                    runs = [run for run in paragraph.runs if run.text.strip()]
                    is_bold = bool(runs) and all(run.bold for run in runs)
                    is_heading = bool(re.match(r"^\d+(?:\.\d+)+\s+\S", text))
                    tipo = "subtitulo" if is_bold or is_heading else "parrafo"
                    guide["presentacion"]["bloques"].append({"tipo": tipo, "texto": text})
                continue

            if section == "formulacion" and activity:
                if normalized.startswith("ambiente requerido"):
                    current_field = "ambiente"
                    activity["ambiente"] = _after_colon(text)
                    if "duracion" in normalized:
                        match = re.search(
                            r"duraci[oó]n[^:]*:\s*(\d+(?:[.,]\d+)?)", text, re.IGNORECASE
                        )
                        if match:
                            activity["duracion_horas"] = float(match.group(1).replace(",", "."))
                        activity["ambiente"] = re.split(
                            r"\n?\s*Duraci[oó]n", activity["ambiente"], flags=re.IGNORECASE
                        )[0].strip()
                    continue
                if normalized.startswith("estrategia didactica") or normalized.startswith(
                    "estrategias o tecnicas"
                ):
                    current_field = "estrategias"
                    activity["estrategias"] = _after_colon(text)
                    continue
                if normalized.startswith("instrumentos de evaluacion"):
                    current_field = "instrumentos"
                    value = _after_colon(text)
                    if value:
                        activity["instrumentos"].append(value)
                    continue
                if normalized.startswith("materiales de formacion"):
                    current_field = "materiales"
                    value = _after_colon(text)
                    if value:
                        activity["materiales"]["apoyo"] = value
                    continue
                if normalized.startswith("material de apoyo"):
                    current_field = "material_apoyo"
                    value = _after_colon(text)
                    if value:
                        activity["materiales"]["apoyo"] = (
                            activity["materiales"]["apoyo"] + "\n" + value
                        ).strip()
                    continue
                if normalized.startswith("duracion"):
                    activity["duracion_horas"] = _hours(text)
                    continue
                if normalized.startswith("consumible"):
                    activity["materiales"]["consumible"] = _after_colon(text)
                    current_field = "materiales"
                    continue
                if normalized.startswith("devolutivo"):
                    activity["materiales"]["devolutivo"] = _after_colon(text)
                    current_field = "materiales"
                    continue

                if style == "List Paragraph":
                    if current_field == "instrumentos":
                        activity["instrumentos"].append(text)
                    elif current_field == "debate":
                        activity["debate"].append(text)
                    elif current_field == "material_apoyo":
                        activity["materiales"]["apoyo"] = (
                            activity["materiales"]["apoyo"] + "\n" + text
                        ).strip()
                    else:
                        activity["instrucciones"].append(text)
                else:
                    if current_field == "ambiente" and activity["ambiente"]:
                        activity["ambiente"] += "\n" + text
                    elif current_field == "estrategias" and activity["estrategias"]:
                        activity["estrategias"] += "\n" + text
                    elif current_field == "material_apoyo":
                        activity["materiales"]["apoyo"] = (
                            activity["materiales"]["apoyo"] + "\n" + text
                        ).strip()
                    elif not activity["introduccion"]:
                        activity["introduccion"] = text
                    else:
                        activity["introduccion"] += "\n\n" + text
                continue

            if section == "glosario":
                if ":" in text:
                    term, definition = text.split(":", 1)
                    guide["glosario"].append(
                        {"termino": term.strip(), "definicion": definition.strip()}
                    )
                else:
                    guide["glosario"].append({"termino": text, "definicion": ""})
                continue

            if section == "referencias":
                guide["referencias"].append(text)
                continue

        elif child.tag == qn("w:tbl"):
            table = Table(child, document)
            if section == "formulacion":
                _parse_evidence_table(table, activity)
            elif section == "evidencias":
                _parse_matrix(table, guide)
            elif section in ("control_documento", "control_cambios"):
                _parse_control(table, guide)

    for moment_id in ("reflexion_inicial", "contextualizacion", "apropiacion", "transferencia"):
        activities = guide["momentos"][moment_id]["actividades"]
        if not activities:
            activity = suggest_activity(guide, moment_id, 0)
            guide["momentos"][moment_id]["actividades"] = [activity]
            warnings.append(
                f"No se detectaron actividades en {guide['momentos'][moment_id]['titulo']}."
            )
            continue
        for index, item in enumerate(activities):
            _clean_activity(item, moment_id, index)

    if not guide["presentacion"]["bloques"]:
        warnings.append("No se detectó contenido en la presentación.")
    if not guide["identificacion"]["programa"]:
        warnings.append("No se detectó la denominación del programa.")
    if not guide["glosario"]:
        warnings.append("La guía de origen no contiene glosario.")
    if not guide["referencias"]:
        warnings.append("La guía de origen no contiene referentes bibliográficos.")

    return {"guide": normalize_guide(guide), "warnings": warnings}
