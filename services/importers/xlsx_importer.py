import re
import unicodedata

from openpyxl import load_workbook

from services.defaults import empty_guide, normalize_guide
from services.suggestions import suggest_activity, suggest_presentation


def _norm(text):
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text).strip().lower()


def _clean(value):
    return str(value or "").replace("\r", "").strip()


def _find_value(sheet, needles):
    for row in sheet.iter_rows():
        for cell in row:
            key = _norm(cell.value)
            if key and any(needle in key for needle in needles):
                for offset in range(1, 14):
                    candidate = sheet.cell(row=cell.row, column=cell.column + offset).value
                    if candidate not in (None, ""):
                        return _clean(candidate)
    return ""


def _find_cell(sheet, needle):
    for row in sheet.iter_rows():
        for cell in row:
            if needle in _norm(cell.value):
                return cell
    return None


def _split_items(text):
    text = _clean(text)
    if not text:
        return []
    parts = re.split(r"\n(?=\s*\d+\.\d+\.\d+\.)", text)
    if len(parts) == 1:
        parts = re.split(r"(?=\s*\d+\.\d+\.\d+\.\s)", text)
    items = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        match = re.search(r"(\d+\.\d+\.\d+\.)\s*(.*)", part, re.DOTALL)
        title = match.group(2) if match else part
        hours_match = re.search(r"\((\d+(?:[.,]\d+)?)\s*H\)", title, re.IGNORECASE)
        hours = float(hours_match.group(1).replace(",", ".")) if hours_match else 0
        title = re.sub(r"\(\s*\d+(?:[.,]\d+)?\s*H\s*\)", "", title, flags=re.IGNORECASE).strip()
        title = re.sub(r"\s+", " ", title).strip(" .")
        items.append({"titulo": title, "horas": hours, "codigo": match.group(1) if match else ""})
    return items


def _split_evidences(text):
    evidences = []
    for line in _clean(text).splitlines():
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"^Ev\s*\d+[\.\):-]?\s*", "", line, flags=re.IGNORECASE)
        if line:
            evidences.append(line)
    return evidences


def _split_lines(text):
    return [line.strip() for line in _clean(text).splitlines() if line.strip()]


def import_xlsx(path):
    workbook = load_workbook(str(path), data_only=True)
    sheet = workbook["FASE"] if "FASE" in workbook.sheetnames else workbook[workbook.sheetnames[0]]
    guide = empty_guide()
    guide["momentos"]["reflexion_inicial"]["actividades"] = []
    guide["momentos"]["contextualizacion"]["actividades"] = []
    guide["momentos"]["apropiacion"]["actividades"] = []
    guide["momentos"]["transferencia"]["actividades"] = []
    guide["glosario"] = []
    guide["referencias"] = []
    guide["evidencias"] = []
    warnings = []

    identification = guide["identificacion"]
    identification["programa"] = _find_value(sheet, ["denominacion del programa"])
    identification["codigo_programa"] = _find_value(sheet, ["codigo y version del programa"])
    identification["proyecto_formativo"] = _find_value(sheet, ["nombre del proyecto formativo"])

    phase_cell = _find_cell(sheet, "fase de proyecto formativo")
    if phase_cell is not None:
        for offset in range(1, 8):
            value = sheet.cell(row=phase_cell.row, column=phase_cell.column + offset).value
            if value not in (None, ""):
                identification["fase"] = _clean(value)
                break

    competence_cell = _find_cell(sheet, "competencia")
    rae_cell = _find_cell(sheet, "resultados de aprendizaje")
    criteria_cell = _find_cell(sheet, "criterios de evaluacion")
    activities_cell = _find_cell(sheet, "actividades de aprendizaje a desarrollar")
    evidence_cell = _find_cell(sheet, "descripcion de la evidencia de aprendizaje")
    strategies_cell = _find_cell(sheet, "estrategias didacticas activas")
    environment_cell = _find_cell(sheet, "ambientes")
    materials_cell = _find_cell(sheet, "materiales de formacion")
    hours_direct_cell = _find_cell(sheet, "horas trabajo directo")
    hours_independent_cell = _find_cell(sheet, "horas trabajo independiente")

    data_row = None
    for candidate in (competence_cell, rae_cell, activities_cell):
        if candidate is not None and candidate.row < sheet.max_row:
            data_row = candidate.row + 1
            break
    if data_row is None:
        data_row = 18

    def value_below(cell):
        if cell is None:
            return ""
        for row in range(cell.row + 1, min(sheet.max_row, cell.row + 6) + 1):
            value = sheet.cell(row=row, column=cell.column).value
            if value not in (None, ""):
                return _clean(value)
        return ""

    identification["competencia"] = value_below(competence_cell)
    identification["resultados_aprendizaje"] = value_below(rae_cell)
    criteria_text = value_below(criteria_cell)
    activities_text = value_below(activities_cell)
    evidence_text = value_below(evidence_cell)
    strategies_text = value_below(strategies_cell)
    environment_text = value_below(environment_cell)
    materials_text = value_below(materials_cell)
    hours_direct = value_below(hours_direct_cell)
    hours_independent = value_below(hours_independent_cell)

    if not identification["actividad_proyecto"]:
        activity_cell = _find_cell(sheet, "actividad de proyecto formativo")
        if activity_cell is not None:
            identification["actividad_proyecto"] = value_below(activity_cell)

    criteria = _split_lines(criteria_text)
    evidences = _split_evidences(evidence_text)
    items = _split_items(activities_text)

    if not items:
        items = [{"titulo": identification["resultados_aprendizaje"] or "Actividad de apropiación", "horas": 0}]
        warnings.append("No se detectaron actividades de aprendizaje numeradas en el PPPF.")

    transfer_item = None
    for item in items:
        if re.search(r"\bIoT\b|internet de las cosas|red", item["titulo"], re.IGNORECASE):
            transfer_item = item
            break

    appropriation_items = [item for item in items if item is not transfer_item]
    if not appropriation_items:
        appropriation_items = items

    total_hours = 0
    for index, item in enumerate(appropriation_items):
        activity = suggest_activity(guide, "apropiacion", index)
        activity["titulo"] = item["titulo"]
        activity["duracion_horas"] = item["horas"] or activity.get("duracion_horas", 0)
        if criteria:
            activity["criterios"] = criteria
        if strategies_text:
            activity["estrategias"] = strategies_text
        if environment_text:
            activity["ambiente"] = environment_text
        if materials_text:
            activity["materiales"]["consumible"] = materials_text
        total_hours += float(activity["duracion_horas"] or 0)
        guide["momentos"]["apropiacion"]["actividades"].append(activity)

    transfer = suggest_activity(guide, "transferencia", 0)
    if transfer_item:
        transfer["titulo"] = transfer_item["titulo"]
        transfer["duracion_horas"] = transfer_item["horas"] or transfer.get("duracion_horas", 0)
    if criteria:
        transfer["criterios"] = criteria
    if strategies_text:
        transfer["estrategias"] = strategies_text
    if environment_text:
        transfer["ambiente"] = environment_text
    if materials_text:
        transfer["materiales"]["consumible"] = materials_text
    total_hours += float(transfer["duracion_horas"] or 0)
    guide["momentos"]["transferencia"]["actividades"].append(transfer)

    remaining_evidences = list(evidences)
    if remaining_evidences:
        guide["momentos"]["apropiacion"]["actividades"][0]["evidencias"] = remaining_evidences
    for index, item in enumerate(items):
        if index < len(evidences) and item is not transfer_item:
            guide["momentos"]["apropiacion"]["actividades"][min(index, len(guide["momentos"]["apropiacion"]["actividades"]) - 1)][
                "evidencias"
            ] = [evidences[index]]
    if evidences and transfer_item:
        transfer["evidencias"] = evidences[-3:] if len(evidences) >= 3 else evidences

    guide["momentos"]["reflexion_inicial"]["actividades"] = [suggest_activity(guide, "reflexion_inicial", 0)]
    guide["momentos"]["contextualizacion"]["actividades"] = [suggest_activity(guide, "contextualizacion", 0)]
    guide["presentacion"] = suggest_presentation(guide)

    identification["duracion_horas"] = total_hours or float(_clean(hours_direct).strip() or 0) + float(
        _clean(hours_independent).strip() or 0
    )

    authors_name = _find_value(sheet, ["nombre completo de los integrantes"])
    regional = _find_value(sheet, ["regional y centro de formacion"])
    date = _find_value(sheet, ["fecha de elaboracion"])
    if authors_name or regional:
        names = [line.strip() for line in authors_name.splitlines() if line.strip()]
        guide["control_documento"]["autores"] = [
            {
                "nombre": name,
                "cargo": "Instructor",
                "dependencia": (regional.splitlines()[-1] if regional else "Centro de Formación"),
                "fecha": date,
            }
            for name in (names or [""])
        ]

    if not identification["programa"]:
        warnings.append("No se detectó la denominación del programa en el archivo XLSX.")
    if not identification["resultados_aprendizaje"]:
        warnings.append("No se detectaron resultados de aprendizaje en el archivo XLSX.")
    if not evidences:
        warnings.append("No se detectaron evidencias en el archivo XLSX.")

    return {"guide": normalize_guide(guide), "warnings": warnings}
