from services.defaults import MOMENTS, iter_activities


def _clean(text):
    return str(text or "").strip()


def derive_evidence(guide):
    rows = []
    activity_map = {}
    counter = 0
    identification = guide["identificacion"]
    for moment_id, moment, activity, index in iter_activities(guide):
        evidence_items = []
        for description in activity.get("evidencias", []):
            description = _clean(description)
            if not description:
                continue
            counter += 1
            code = f"Ev{counter}"
            evidence_items.append({"codigo": code, "descripcion": description})
            rows.append(
                {
                    "fase": identification.get("fase", ""),
                    "actividad_proyecto": identification.get("actividad_proyecto", ""),
                    "actividad_aprendizaje": activity.get("titulo", ""),
                    "evidencia": f"{code}. {description}",
                    "criterios": "\n".join(_clean(item) for item in activity.get("criterios", []) if _clean(item)),
                    "tecnicas": "Observación directa y revisión documental",
                    "instrumentos": ", ".join(_clean(item) for item in activity.get("instrumentos", []) if _clean(item)),
                    "moment_id": moment_id,
                    "activity_index": index,
                }
            )
        if MOMENTS[moment_id]["requires_evidence"] and not evidence_items:
            evidence_items.append({"codigo": "Pendiente", "descripcion": "Pendiente por definir"})
            rows.append(
                {
                    "fase": identification.get("fase", ""),
                    "actividad_proyecto": identification.get("actividad_proyecto", ""),
                    "actividad_aprendizaje": activity.get("titulo", ""),
                    "evidencia": "Pendiente por definir",
                    "criterios": "\n".join(_clean(item) for item in activity.get("criterios", []) if _clean(item)),
                    "tecnicas": "Observación directa y revisión documental",
                    "instrumentos": ", ".join(_clean(item) for item in activity.get("instrumentos", []) if _clean(item)),
                    "moment_id": moment_id,
                    "activity_index": index,
                }
            )
        activity_map[(moment_id, index)] = evidence_items
    return rows, activity_map
