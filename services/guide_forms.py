"""Lectura de formularios HTML (sin SPA) hacia el modelo de guía.

El patrón es: un formulario por sección, todos los campos se envían juntos y
los botones de acción indican qué hacer además de guardar los cambios:

    action=save
    action=add
    action=delete:<uid>
    action=up:<uid> / down:<uid>
    action=suggest:<uid>

Así no se pierden ediciones al agregar, borrar o reordenar una actividad.
"""

import re

from services.defaults import MOMENT_ORDER, as_uid, empty_activity
from services.suggestions import suggest_section

TEXT_FIELDS = ("titulo", "introduccion", "ambiente", "estrategias", "modalidad")
LIST_FIELDS = ("instrucciones", "debate", "instrumentos", "evidencias", "criterios")
MATERIAL_FIELDS = ("consumible", "devolutivo", "apoyo")
MAX_ITEMS = 50

_UID_KEY = re.compile(r"^(?:act|block)\.([A-Za-z0-9_-]+)\.")


def _text(value):
    return str(value or "").strip()


def _lines(value):
    return [line.strip() for line in str(value or "").splitlines() if line.strip()]


def _hours(value):
    match = re.search(r"\d+(?:[.,]\d+)?", _text(value))
    if not match:
        return 0
    return float(match.group(0).replace(",", "."))


def _uids_in_form(form, prefix):
    found = []
    pattern = re.compile(rf"^{re.escape(prefix)}\.([A-Za-z0-9_-]+)\.")
    for key in form.keys():
        match = pattern.match(key)
        if match and match.group(1) not in found:
            found.append(match.group(1))
    return found


def _order(form, key, fallback):
    raw = _text(form.get(key))
    if not raw:
        return list(fallback)
    ordered = []
    for uid in raw.split(","):
        uid = _text(uid)
        if uid and uid not in ordered:
            ordered.append(uid)
    for uid in fallback:
        if uid not in ordered:
            ordered.append(uid)
    return ordered


def _indexes(form, prefix):
    pattern = re.compile(rf"^{re.escape(prefix)}\.(\d+)(?:\.|$)")
    indexes = set()
    for key in form.keys():
        match = pattern.match(key)
        if match:
            indexes.add(int(match.group(1)))
    return sorted(indexes)


def _move(items, index, offset):
    target = index + offset
    if 0 <= index < len(items) and 0 <= target < len(items):
        items[index], items[target] = items[target], items[index]


def _action(form):
    return _text(form.get("action")) or "save"


def _delete_index(action):
    try:
        return int(action.split(":", 1)[1])
    except (IndexError, ValueError):
        return -1


def _suggest(form):
    return _text(form.get("usar_ia")).lower() in ("on", "1", "true", "si", "sí")


# ---------------------------------------------------------------------------
# Identificación
# ---------------------------------------------------------------------------

IDENTIFICATION_FIELDS = (
    "programa",
    "codigo_programa",
    "proyecto_formativo",
    "fase",
    "actividad_proyecto",
    "competencia",
    "resultados_aprendizaje",
    "duracion_horas",
)


def parse_identification(form, guide):
    identification = guide["identificacion"]
    for field in IDENTIFICATION_FIELDS:
        if field in form:
            if field == "duracion_horas":
                identification[field] = _hours(form.get(field))
            else:
                identification[field] = _text(form.get(field))
    return guide


# ---------------------------------------------------------------------------
# Presentación
# ---------------------------------------------------------------------------

BLOCK_TYPES = ("parrafo", "subtitulo", "lista")


def _block_from_form(form, uid):
    tipo = _text(form.get(f"block.{uid}.tipo", "parrafo")).lower()
    if tipo not in BLOCK_TYPES:
        tipo = "parrafo"
    return {"uid": as_uid(uid), "tipo": tipo, "texto": form.get(f"block.{uid}.texto", "")}


def parse_presentation(form, guide):
    existing = list(guide["presentacion"].get("bloques") or [])
    order = _order(form, "block_order", [block["uid"] for block in existing])
    current = {block["uid"]: block for block in existing}
    edited = {
        uid: _block_from_form(form, uid) for uid in _uids_in_form(form, "block")
    }
    blocks = [edited.get(uid) or current.get(uid) for uid in order]
    blocks = [block for block in blocks if block]
    for uid, block in edited.items():
        if uid not in order:
            blocks.append(block)

    action = _action(form)
    if action == "add":
        blocks.append({"uid": as_uid(None), "tipo": "parrafo", "texto": ""})
    elif action.startswith("delete:"):
        uid = action.split(":", 1)[1]
        blocks = [block for block in blocks if block["uid"] != uid]
    elif action.startswith(("up:", "down:")):
        uid = action.split(":", 1)[1]
        index = next(
            (position for position, block in enumerate(blocks) if block["uid"] == uid),
            None,
        )
        if index is not None:
            _move(blocks, index, -1 if action.startswith("up:") else 1)
    elif action == "suggest":
        result = suggest_section(guide, "presentacion", use_llm=_suggest(form))
        suggested = result.get("presentacion", {}).get("bloques") or []
        blocks = [
            {
                "uid": as_uid(None),
                "tipo": block.get("tipo") if block.get("tipo") in BLOCK_TYPES else "parrafo",
                "texto": block.get("texto", ""),
            }
            for block in suggested
        ]

    guide["presentacion"]["bloques"] = blocks[:MAX_ITEMS]
    return guide


# ---------------------------------------------------------------------------
# Momentos y actividades
# ---------------------------------------------------------------------------


def _activity_from_form(form, uid, moment_id, index):
    activity = empty_activity(moment_id, index)
    activity["uid"] = as_uid(uid)
    prefix = f"act.{uid}."
    for field in TEXT_FIELDS:
        if prefix + field in form:
            activity[field] = _text(form.get(prefix + field))
    for field in LIST_FIELDS:
        if prefix + field in form:
            activity[field] = _lines(form.get(prefix + field))
    for field in MATERIAL_FIELDS:
        key = prefix + "materiales." + field
        if key in form:
            activity["materiales"][field] = _text(form.get(key))
    key = prefix + "duracion_horas"
    if key in form:
        activity["duracion_horas"] = _hours(form.get(key))
    return activity


def parse_moment(form, guide, moment_id):
    if moment_id not in MOMENT_ORDER:
        raise ValueError("Momento de formación inválido.")
    moment = guide["momentos"][moment_id]
    existing = list(moment.get("actividades") or [])
    current = {activity["uid"]: activity for activity in existing}
    order = _order(form, "activity_order", [activity["uid"] for activity in existing])
    edited = {
        uid: _activity_from_form(form, uid, moment_id, index)
        for index, uid in enumerate(_uids_in_form(form, "act"))
    }
    activities = [edited.get(uid) or current.get(uid) for uid in order]
    activities = [activity for activity in activities if activity]
    for uid, activity in edited.items():
        if uid not in order:
            activities.append(activity)

    action = _action(form)
    if action == "add":
        activities.append(empty_activity(moment_id, len(activities)))
    elif action.startswith("delete:"):
        uid = action.split(":", 1)[1]
        activities = [activity for activity in activities if activity["uid"] != uid]
    elif action.startswith(("up:", "down:")):
        uid = action.split(":", 1)[1]
        index = next(
            (
                position
                for position, activity in enumerate(activities)
                if activity["uid"] == uid
            ),
            None,
        )
        if index is not None:
            _move(activities, index, -1 if action.startswith("up:") else 1)
    elif action.startswith("suggest:"):
        uid = action.split(":", 1)[1]
        index = next(
            (
                position
                for position, activity in enumerate(activities)
                if activity["uid"] == uid
            ),
            0,
        )
        result = suggest_section(
            guide, "actividad", moment_id, index, use_llm=_suggest(form)
        )
        suggested = result.get("actividad")
        if suggested:
            suggested["uid"] = as_uid(uid)
            activities[index] = suggested

    moment["actividades"] = activities[:MAX_ITEMS]
    return guide


# ---------------------------------------------------------------------------
# Glosario y referentes
# ---------------------------------------------------------------------------


def parse_glossary(form, guide):
    rows = []
    for index in _indexes(form, "glosario"):
        rows.append(
            {
                "termino": _text(form.get(f"glosario.{index}.termino")),
                "definicion": _text(form.get(f"glosario.{index}.definicion")),
            }
        )
    action = _action(form)
    if action == "add":
        rows.append({"termino": "", "definicion": ""})
    elif action.startswith("delete:"):
        index = _delete_index(action)
        if 0 <= index < len(rows):
            rows.pop(index)
    elif action == "suggest":
        rows = suggest_section(guide, "glosario", use_llm=_suggest(form)).get(
            "glosario", []
        )
        rows = [
            {
                "termino": _text(item.get("termino") if isinstance(item, dict) else item),
                "definicion": _text(item.get("definicion") if isinstance(item, dict) else ""),
            }
            for item in rows
        ]
    guide["glosario"] = rows[:MAX_ITEMS]
    return guide


def parse_references(form, guide):
    rows = []
    for index in _indexes(form, "referencia"):
        rows.append(_text(form.get(f"referencia.{index}")))
    action = _action(form)
    if action == "add":
        rows.append("")
    elif action.startswith("delete:"):
        index = _delete_index(action)
        if 0 <= index < len(rows):
            rows.pop(index)
    elif action == "suggest":
        rows = suggest_section(guide, "referencias", use_llm=_suggest(form)).get(
            "referencias", []
        )
        rows = [_text(item.get("texto") if isinstance(item, dict) else item) for item in rows]
    guide["referencias"] = rows[:MAX_ITEMS]
    return guide


# ---------------------------------------------------------------------------
# Control del documento
# ---------------------------------------------------------------------------

AUTHOR_FIELDS = ("nombre", "cargo", "dependencia", "fecha")
CHANGE_FIELDS = ("nombre", "cargo", "dependencia", "fecha", "razon")


def _rows_from_form(form, prefix, fields):
    rows = []
    for index in _indexes(form, prefix):
        rows.append(
            {field: _text(form.get(f"{prefix}.{index}.{field}")) for field in fields}
        )
    return rows


def parse_control(form, guide):
    authors = _rows_from_form(form, "autor", AUTHOR_FIELDS)
    changes = _rows_from_form(form, "cambio", CHANGE_FIELDS)
    action = _action(form)

    if action == "add_autor":
        authors.append({"nombre": "", "cargo": "Instructor", "dependencia": "Centro Metalmecánico", "fecha": ""})
    elif action.startswith("delete_autor:"):
        index = _delete_index(action)
        if 0 <= index < len(authors):
            authors.pop(index)
    elif action == "add_cambio":
        changes.append({field: "" for field in CHANGE_FIELDS})
    elif action.startswith("delete_cambio:"):
        index = _delete_index(action)
        if 0 <= index < len(changes):
            changes.pop(index)

    if not authors:
        authors = [{"nombre": "", "cargo": "Instructor", "dependencia": "Centro Metalmecánico", "fecha": ""}]
    guide["control_documento"]["autores"] = authors[:MAX_ITEMS]
    guide["control_cambios"] = changes[:MAX_ITEMS]
    return guide


def parse_section(form, guide, section, moment_id=None):
    if section == "identificacion":
        return parse_identification(form, guide)
    if section == "presentacion":
        return parse_presentation(form, guide)
    if section == "momentos":
        return parse_moment(form, guide, moment_id)
    if section == "glosario":
        return parse_glossary(form, guide)
    if section == "referentes":
        return parse_references(form, guide)
    if section == "control":
        return parse_control(form, guide)
    raise ValueError(f"Sección no soportada: {section}")
