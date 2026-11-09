import re
import unicodedata

from pypdf import PdfReader

from services.defaults import empty_activity, empty_guide, normalize_guide
from services.suggestions import suggest_activity, suggest_presentation


def _norm(text):
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text).strip().lower()


def _search(text, pattern, flags=re.IGNORECASE):
    match = re.search(pattern, text, flags)
    return match.group(1).strip() if match else ""


def import_pdf(path):
    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    text = "\n".join(pages).replace("\x00", "")
    if not _norm(text):
        raise ValueError("El PDF no contiene texto seleccionable. Se requiere OCR para documentos escaneados.")

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    guide = empty_guide()
    warnings = [
        "La lectura de PDF es aproximada: revise y complete todos los campos antes de generar la guía."
    ]

    identification = guide["identificacion"]
    identification["programa"] = _search(
        text, r"Denominaci[oó]n del Programa de Formaci[oó]n:\s*(.+)"
    )
    identification["codigo_programa"] = _search(
        text, r"C[oó]digo del Programa de Formaci[oó]n:\s*(.+)"
    )
    identification["proyecto_formativo"] = _search(
        text, r"Nombre del Proyecto Formativo[^:]*:\s*(.+)"
    )
    identification["fase"] = _search(text, r"Fase del Proyecto[^:]*:\s*(.+)")
    identification["actividad_proyecto"] = _search(
        text, r"Actividad de Proyecto Formativo[^:]*:\s*(.+)"
    )
    identification["competencia"] = _search(text, r"Competencia:\s*(.+)")
    identification["resultados_aprendizaje"] = _search(
        text, r"Resultados de Aprendizaje:\s*(.+)"
    )
    duration = _search(text, r"Duraci[oó]n de la Gu[ií]a de Aprendizaje \(horas\):\s*(\d+(?:[.,]\d+)?)")
    if duration:
        identification["duracion_horas"] = float(duration.replace(",", "."))

    for field in ("programa", "codigo_programa", "competencia", "resultados_aprendizaje"):
        if identification.get(field):
            identification[field] = re.sub(r"\s{2,}", " ", identification[field]).strip()

    presentation = suggest_presentation(guide)
    guide["presentacion"] = presentation
    warnings.append("La presentación se generó con contenido sugerido; ajústela al contexto del programa.")

    guide["momentos"]["reflexion_inicial"]["actividades"] = [suggest_activity(guide, "reflexion_inicial", 0)]
    guide["momentos"]["contextualizacion"]["actividades"] = [suggest_activity(guide, "contextualizacion", 0)]
    guide["momentos"]["apropiacion"]["actividades"] = [suggest_activity(guide, "apropiacion", 0)]
    guide["momentos"]["transferencia"]["actividades"] = [suggest_activity(guide, "transferencia", 0)]

    evidence_lines = []
    for line in lines:
        if re.match(r"^Ev\s*\d+", line, re.IGNORECASE):
            cleaned = re.sub(r"^Ev\s*\d+[\.\):-]?\s*", "", line, flags=re.IGNORECASE).strip()
            if cleaned:
                evidence_lines.append(cleaned)
    if evidence_lines:
        guide["momentos"]["apropiacion"]["actividades"][0]["evidencias"] = evidence_lines[:2]
        guide["momentos"]["transferencia"]["actividades"][0]["evidencias"] = evidence_lines[2:] or evidence_lines[:1]

    keywords = []
    for needle in ("Sistema embebido", "Grafcet", "IoT", "MQTT", "Interfaz de potencia"):
        if needle.lower() in text.lower():
            keywords.append(needle)
    if keywords:
        guide["glosario"] = [{"termino": keyword, "definicion": "Término identificado en el documento de origen."} for keyword in keywords]

    warnings.append("Las actividades de aprendizaje se generaron con plantillas; valide horas, evidencias y criterios.")

    if not identification["programa"]:
        warnings.append("No se detectó la denominación del programa en el PDF.")
    if not identification["resultados_aprendizaje"]:
        warnings.append("No se detectaron resultados de aprendizaje en el PDF.")

    return {"guide": normalize_guide(guide), "warnings": warnings}
