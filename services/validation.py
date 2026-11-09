from services.defaults import MOMENT_ORDER, MOMENTS, total_hours
from services.evidence import derive_evidence

__all__ = ["validate_guide", "derive_evidence"]


def _clean(text):
    return str(text or "").strip()


def validate_guide(guide):
    errors = []
    warnings = []
    identification = guide["identificacion"]

    required = [
        ("programa", "Denominación del programa"),
        ("codigo_programa", "Código del programa"),
        ("competencia", "Competencia"),
        ("resultados_aprendizaje", "Resultados de aprendizaje"),
    ]
    for key, label in required:
        if not _clean(identification.get(key)):
            errors.append(f"Falta diligenciar: {label}.")

    for moment_id in MOMENT_ORDER:
        activities = guide["momentos"][moment_id]["actividades"]
        if not activities:
            errors.append(f"El momento '{MOMENTS[moment_id]['label']}' debe tener al menos una actividad.")

    appropriation = guide["momentos"]["apropiacion"]["actividades"]
    if len(appropriation) < 1:
        errors.append("Debe registrar al menos una actividad de apropiación.")

    for moment_id in ("apropiacion", "transferencia"):
        for index, activity in enumerate(guide["momentos"][moment_id]["actividades"], start=1):
            label = MOMENTS[moment_id]["label"]
            if not _clean(activity.get("titulo")):
                errors.append(f"{label} {index}: falta el título de la actividad.")
            if not [item for item in activity.get("evidencias", []) if _clean(item)]:
                errors.append(
                    f"{label} {index}: la actividad debe registrar al menos una evidencia para la matriz azul."
                )
            if not _clean(activity.get("ambiente")):
                warnings.append(f"{label} {index}: no se definió el ambiente requerido.")
            if not _clean(activity.get("estrategias")):
                warnings.append(f"{label} {index}: no se definieron las estrategias didácticas.")
            if not float(activity.get("duracion_horas") or 0):
                warnings.append(f"{label} {index}: la duración es cero.")

    for moment_id in MOMENT_ORDER:
        for index, activity in enumerate(guide["momentos"][moment_id]["actividades"], start=1):
            if not _clean(activity.get("introduccion")):
                warnings.append(
                    f"{MOMENTS[moment_id]['label']} {index}: falta la introducción de la actividad."
                )
            if not activity.get("instrucciones"):
                warnings.append(
                    f"{MOMENTS[moment_id]['label']} {index}: no se registraron instrucciones."
                )

    computed = total_hours(guide)
    declared = float(identification.get("duracion_horas") or 0)
    if declared and abs(computed - declared) > 0.001:
        warnings.append(
            f"La duración declarada ({declared:g} h) no coincide con la suma de actividades ({computed:g} h)."
        )
    if not declared:
        warnings.append("No se ha definido la duración total de la guía.")
    if not computed:
        errors.append("La guía no tiene horas acumuladas en sus actividades.")

    if not guide.get("glosario"):
        warnings.append("La sección de glosario está vacía.")
    if not guide.get("referencias"):
        warnings.append("La sección de referentes bibliográficos está vacía.")
    authors = guide.get("control_documento", {}).get("autores", [])
    if not any(_clean(author.get("nombre")) for author in authors):
        warnings.append("No se registró el autor en el control del documento.")
    if not guide.get("control_cambios"):
        warnings.append("El control de cambios está vacío.")

    evidence_rows, activity_map = derive_evidence(guide)
    if not evidence_rows:
        errors.append("No fue posible construir la matriz de evidencias.")
    for row in evidence_rows:
        if row["actividad_aprendizaje"] and not _clean(row["criterios"]):
            warnings.append(
                f"La actividad '{row['actividad_aprendizaje']}' no tiene criterios de evaluación asociados."
            )

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "computed_hours": computed,
        "declared_hours": declared,
        "evidence_rows": evidence_rows,
        "activity_evidence": {f"{k[0]}:{k[1]}": v for k, v in activity_map.items()},
    }
