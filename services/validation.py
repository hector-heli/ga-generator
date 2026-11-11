from services.defaults import MOMENT_ORDER, MOMENTS, total_hours
from services.evidence import derive_evidence

__all__ = ["validate_guide", "derive_evidence", "section_report"]

SECTION_IDENTIFICACION = "identificacion"
SECTION_PRESENTACION = "presentacion"
SECTION_GLOSARIO = "glosario"
SECTION_REFERENTES = "referentes"
SECTION_CONTROL = "control"
SECTION_GENERAL = "general"


def _clean(text):
    return str(text or "").strip()


def _item(section, level, message):
    return {"section": section, "level": level, "message": message}


def _collect(guide, computed, declared, evidence_rows):
    items = []
    identification = guide["identificacion"]

    required = [
        ("programa", "Denominación del programa"),
        ("codigo_programa", "Código del programa"),
        ("competencia", "Competencia"),
        ("resultados_aprendizaje", "Resultados de aprendizaje"),
    ]
    for key, label in required:
        if not _clean(identification.get(key)):
            items.append(_item(SECTION_IDENTIFICACION, "error", f"Falta diligenciar: {label}."))

    for moment_id in MOMENT_ORDER:
        section = f"momentos/{moment_id}"
        activities = guide["momentos"][moment_id]["actividades"]
        if not activities:
            items.append(
                _item(
                    section,
                    "error",
                    f"El momento '{MOMENTS[moment_id]['label']}' debe tener al menos una actividad.",
                )
            )

    appropriation = guide["momentos"]["apropiacion"]["actividades"]
    if len(appropriation) < 1:
        items.append(
            _item(
                "momentos/apropiacion",
                "error",
                "Debe registrar al menos una actividad de apropiación.",
            )
        )

    for moment_id in ("apropiacion", "transferencia"):
        section = f"momentos/{moment_id}"
        for index, activity in enumerate(guide["momentos"][moment_id]["actividades"], start=1):
            label = MOMENTS[moment_id]["label"]
            if not _clean(activity.get("titulo")):
                items.append(
                    _item(section, "error", f"{label} {index}: falta el título de la actividad.")
                )
            if not [item for item in activity.get("evidencias", []) if _clean(item)]:
                items.append(
                    _item(
                        section,
                        "error",
                        f"{label} {index}: la actividad debe registrar al menos una evidencia para la matriz azul.",
                    )
                )
            if not _clean(activity.get("ambiente")):
                items.append(
                    _item(section, "warning", f"{label} {index}: no se definió el ambiente requerido.")
                )
            if not _clean(activity.get("estrategias")):
                items.append(
                    _item(
                        section,
                        "warning",
                        f"{label} {index}: no se definieron las estrategias didácticas.",
                    )
                )
            if not float(activity.get("duracion_horas") or 0):
                items.append(
                    _item(section, "warning", f"{label} {index}: la duración es cero.")
                )

    for moment_id in MOMENT_ORDER:
        section = f"momentos/{moment_id}"
        for index, activity in enumerate(guide["momentos"][moment_id]["actividades"], start=1):
            if not _clean(activity.get("introduccion")):
                items.append(
                    _item(
                        section,
                        "warning",
                        f"{MOMENTS[moment_id]['label']} {index}: falta la introducción de la actividad.",
                    )
                )
            if not activity.get("instrucciones"):
                items.append(
                    _item(
                        section,
                        "warning",
                        f"{MOMENTS[moment_id]['label']} {index}: no se registraron instrucciones.",
                    )
                )

    if declared and abs(computed - declared) > 0.001:
        items.append(
            _item(
                SECTION_GENERAL,
                "warning",
                f"La duración declarada ({declared:g} h) no coincide con la suma de actividades ({computed:g} h).",
            )
        )
    if not declared:
        items.append(
            _item(SECTION_GENERAL, "warning", "No se ha definido la duración total de la guía.")
        )
    if not computed:
        items.append(
            _item(
                SECTION_GENERAL,
                "error",
                "La guía no tiene horas acumuladas en sus actividades.",
            )
        )

    glossary = [
        item
        for item in guide.get("glosario", [])
        if _clean(item.get("termino")) or _clean(item.get("definicion"))
    ]
    if not glossary:
        items.append(_item(SECTION_GLOSARIO, "warning", "La sección de glosario está vacía."))
    references = [
        item.get("texto") if isinstance(item, dict) else item
        for item in guide.get("referencias", [])
    ]
    if not any(_clean(item) for item in references):
        items.append(
            _item(
                SECTION_REFERENTES,
                "warning",
                "La sección de referentes bibliográficos está vacía.",
            )
        )
    authors = guide.get("control_documento", {}).get("autores", [])
    if not any(_clean(author.get("nombre")) for author in authors):
        items.append(
            _item(
                SECTION_CONTROL,
                "warning",
                "No se registró el autor en el control del documento.",
            )
        )
    if not guide.get("control_cambios"):
        items.append(
            _item(
                SECTION_CONTROL,
                "warning",
                "El control de cambios está vacío.",
            )
        )

    if not evidence_rows:
        items.append(
            _item(
                SECTION_GENERAL,
                "error",
                "No fue posible construir la matriz de evidencias.",
            )
        )
    for row in evidence_rows:
        if row["actividad_aprendizaje"] and not _clean(row["criterios"]):
            section = (
                f"momentos/{row['moment_id']}"
                if row.get("moment_id")
                else SECTION_GENERAL
            )
            items.append(
                _item(
                    section,
                    "warning",
                    f"La actividad '{row['actividad_aprendizaje']}' no tiene criterios de evaluación asociados.",
                )
            )

    return items


def _group(items):
    sections = {}
    for item in items:
        entry = sections.setdefault(item["section"], {"errors": [], "warnings": []})
        bucket = "errors" if item["level"] == "error" else "warnings"
        entry[bucket].append(item["message"])
    return sections


def validate_guide(guide):
    computed = total_hours(guide)
    declared = float(guide["identificacion"].get("duracion_horas") or 0)
    evidence_rows, activity_map = derive_evidence(guide)
    items = _collect(guide, computed, declared, evidence_rows)
    sections = _group(items)

    return {
        "ok": not any(item["level"] == "error" for item in items),
        "errors": [item["message"] for item in items if item["level"] == "error"],
        "warnings": [item["message"] for item in items if item["level"] == "warning"],
        "computed_hours": computed,
        "declared_hours": declared,
        "evidence_rows": evidence_rows,
        "activity_evidence": {f"{k[0]}:{k[1]}": v for k, v in activity_map.items()},
        "sections": sections,
        "items": items,
    }


def section_report(validation, section):
    """Errores y advertencias de una sección, listos para la plantilla."""
    entry = validation.get("sections", {}).get(section, {})
    return {
        "errors": entry.get("errors", []),
        "warnings": entry.get("warnings", []),
    }
