"""Resumen, estados por sección y navegación lateral."""

from services.defaults import MOMENT_ORDER, MOMENTS, iter_activities, rae_code, total_hours

STATUS_LABELS = {
    "done": "Completo",
    "partial": "Con pendientes",
    "empty": "Sin diligenciar",
}


def _clean(value):
    return str(value or "").strip()


def _activity_has_content(activity):
    if _clean(activity.get("titulo")):
        return True
    if _clean(activity.get("introduccion")) or _clean(activity.get("ambiente")):
        return True
    if _clean(activity.get("estrategias")) or float(activity.get("duracion_horas") or 0):
        return True
    for field in ("instrucciones", "debate", "instrumentos", "evidencias", "criterios"):
        if any(_clean(item) for item in activity.get(field, [])):
            return True
    return any(_clean(value) for value in (activity.get("materiales") or {}).values())


def guide_summary(guide):
    identification = guide["identificacion"]
    programa = _clean(identification.get("programa"))
    resultado = _clean(identification.get("resultados_aprendizaje"))
    proyecto = _clean(identification.get("proyecto_formativo"))
    code = rae_code(guide)
    if programa:
        title = f"{code} · {programa}"
    elif resultado:
        title = f"{code} · {resultado}"
    else:
        title = "Guía sin identificar"
    subtitle = proyecto or resultado or "Complete la identificación para reconocerla."
    return {
        "programa": programa,
        "codigo": _clean(identification.get("codigo_programa")),
        "proyecto": proyecto,
        "resultado": resultado,
        "rae": code,
        "title": title,
        "subtitle": subtitle,
        "computed_hours": total_hours(guide),
        "declared_hours": float(identification.get("duracion_horas") or 0),
        "activity_count": sum(1 for _ in iter_activities(guide)),
        "evidence_count": sum(
            1
            for _, _, activity, _ in iter_activities(guide)
            for item in activity.get("evidencias", [])
            if _clean(item)
        ),
    }


def _identity_status(guide, validation):
    identification = guide["identificacion"]
    filled = sum(
        1
        for field in ("programa", "codigo_programa", "competencia", "resultados_aprendizaje")
        if _clean(identification.get(field))
    )
    if not filled:
        return "empty"
    if validation["sections"].get("identificacion", {}).get("errors"):
        return "partial"
    return "done"


def _presentation_status(guide):
    blocks = guide["presentacion"].get("bloques", [])
    filled = sum(1 for block in blocks if _clean(block.get("texto")))
    if filled >= 2:
        return "done"
    return "partial" if filled else "empty"


def _moment_status(guide, validation, moment_id):
    section = validation["sections"].get(f"momentos/{moment_id}", {})
    activities = guide["momentos"][moment_id].get("actividades", [])
    if not activities:
        return "empty"
    if section.get("errors") or section.get("warnings"):
        return "partial"
    if not any(_activity_has_content(activity) for activity in activities):
        return "empty"
    return "done"


def _glossary_status(guide):
    return (
        "done"
        if any(
            _clean(item.get("termino")) or _clean(item.get("definicion"))
            for item in guide.get("glosario", [])
        )
        else "empty"
    )


def _references_status(guide):
    return "done" if any(_clean(item) for item in guide.get("referencias", [])) else "empty"


def _control_status(guide):
    authors = guide.get("control_documento", {}).get("autores", [])
    has_author = any(_clean(author.get("nombre")) for author in authors)
    has_changes = bool(guide.get("control_cambios"))
    if has_author and has_changes:
        return "done"
    if has_author or has_changes:
        return "partial"
    return "empty"


def section_status(guide, validation):
    statuses = {
        "identificacion": _identity_status(guide, validation),
        "presentacion": _presentation_status(guide),
        "glosario": _glossary_status(guide),
        "referentes": _references_status(guide),
        "control": _control_status(guide),
        "resumen": "done" if validation.get("ok") else "partial",
    }
    for moment_id in MOMENT_ORDER:
        statuses[f"momentos/{moment_id}"] = _moment_status(
            guide, validation, moment_id
        )
    return statuses


def build_navigation(guide_id, guide, validation, active):
    statuses = section_status(guide, validation)
    base = f"/guias/{guide_id}"

    def link(label, href, key, hint=""):
        return {
            "label": label,
            "href": href,
            "key": key,
            "status": statuses.get(key, "empty"),
            "hint": hint,
            "active": key == active,
        }

    items = [
        {"heading": "Guía"},
        link("Identificación", f"{base}/identificacion", "identificacion"),
        link("Presentación", f"{base}/presentacion", "presentacion"),
        {"heading": "Momentos de formación"},
    ]
    for moment_id in MOMENT_ORDER:
        count = len(guide["momentos"][moment_id].get("actividades", []))
        hint = f"{count} actividad" if count == 1 else f"{count} actividades"
        items.append(
            link(
                MOMENTS[moment_id]["label"],
                f"{base}/momentos/{moment_id}",
                f"momentos/{moment_id}",
                hint,
            )
        )
    items.extend(
        [
            {"heading": "Cierre"},
            link("Glosario", f"{base}/glosario", "glosario"),
            link("Referentes", f"{base}/referentes", "referentes"),
            link("Control del documento", f"{base}/control", "control"),
            link("Resumen y generación", f"{base}/resumen", "resumen"),
        ]
    )

    links = [item for item in items if "href" in item]
    done = sum(1 for item in links if item["status"] == "done")
    progress = round((done / len(links)) * 100) if links else 0
    return {
        "entries": items,
        "statuses": statuses,
        "progress": progress,
        "done": done,
        "total": len(links),
    }
