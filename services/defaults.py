import copy
import re
import uuid

MOMENT_ORDER = ["reflexion_inicial", "contextualizacion", "apropiacion", "transferencia"]

_UID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def new_uid():
    """Return a short, URL- and form-safe identifier."""
    return uuid.uuid4().hex[:12]


def as_uid(value):
    """Keep a valid identifier or create a new one for legacy/imported data."""
    text = str(value or "").strip()
    return text if _UID_RE.fullmatch(text) else new_uid()


def _presentation_block(tipo, texto):
    return {"uid": new_uid(), "tipo": tipo, "texto": texto}

MOMENTS = {
    "reflexion_inicial": {
        "titulo": "Actividades de reflexión inicial",
        "label": "Reflexión inicial",
        "requires_evidence": False,
    },
    "contextualizacion": {
        "titulo": "Actividades de contextualización e identificación de conocimientos necesarios para el aprendizaje",
        "label": "Contextualización",
        "requires_evidence": False,
    },
    "apropiacion": {
        "titulo": "Actividades de apropiación",
        "label": "Apropiación",
        "requires_evidence": True,
    },
    "transferencia": {
        "titulo": "Actividades de transferencia del conocimiento",
        "label": "Transferencia",
        "requires_evidence": True,
    },
}


def empty_activity(moment_id="apropiacion", index=0):
    titles = {
        "reflexion_inicial": "Análisis de situación problema",
        "contextualizacion": "Contraste de soluciones tecnológicas",
        "apropiacion": "Implementar y comisionar el sistema",
        "transferencia": "Integrar el sistema a una red IoT",
    }
    return {
        "uid": new_uid(),
        "titulo": titles.get(moment_id, "Actividad de aprendizaje"),
        "introduccion": "",
        "instrucciones": [],
        "debate": [],
        "ambiente": "",
        "estrategias": "",
        "materiales": {
            "consumible": "",
            "devolutivo": "",
            "apoyo": "",
        },
        "instrumentos": [],
        "duracion_horas": 0,
        "modalidad": "Grupal",
        "evidencias": [],
        "criterios": [],
    }


def empty_guide():
    return {
        "meta": {
            "titulo_proceso": "PROCESO DE GESTIÓN DE FORMACIÓN PROFESIONAL INTEGRAL",
            "titulo_formato": "FORMATO GUÍA DE APRENDIZAJE",
        },
        "identificacion": {
            "programa": "",
            "codigo_programa": "",
            "proyecto_formativo": "",
            "fase": "",
            "actividad_proyecto": "",
            "competencia": "",
            "resultados_aprendizaje": "",
            "duracion_horas": 0,
            "programa_id": "",
            "proyecto_id": "",
            "fase_id": "",
            "actividad_id": "",
            "resultados_ids": [],
        },
        "presentacion": {
            "bloques": [
                _presentation_block("parrafo", "Estimado Aprendiz:"),
                _presentation_block("parrafo", ""),
                _presentation_block("subtitulo", "Alineación con su perfil y proyección profesional"),
                _presentation_block("parrafo", ""),
            ]
        },
        "momentos": {
            "reflexion_inicial": {
                "titulo": MOMENTS["reflexion_inicial"]["titulo"],
                "actividades": [empty_activity("reflexion_inicial")],
            },
            "contextualizacion": {
                "titulo": MOMENTS["contextualizacion"]["titulo"],
                "actividades": [empty_activity("contextualizacion")],
            },
            "apropiacion": {
                "titulo": MOMENTS["apropiacion"]["titulo"],
                "actividades": [empty_activity("apropiacion")],
            },
            "transferencia": {
                "titulo": MOMENTS["transferencia"]["titulo"],
                "actividades": [empty_activity("transferencia")],
            },
        },
        "evidencias": [],
        "glosario": [],
        "referencias": [],
        "control_documento": {
            "autores": [
                {"nombre": "", "cargo": "Instructor", "dependencia": "Centro Metalmecánico", "fecha": ""}
            ]
        },
        "control_cambios": [],
    }


def _as_text(value):
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return str(value)
    return str(value)


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    return [value]


def _as_hours(value):
    if isinstance(value, (int, float)):
        return float(value) if value else 0
    match = re.search(r"\d+(?:[.,]\d+)?", _as_text(value))
    if not match:
        return 0
    return float(match.group(0).replace(",", "."))


def _normalize_activity(raw, moment_id, index):
    base = empty_activity(moment_id, index)
    raw = raw if isinstance(raw, dict) else {}
    base["uid"] = as_uid(raw.get("uid"))
    for key in ("titulo", "introduccion", "ambiente", "estrategias", "modalidad"):
        if key in raw:
            base[key] = _as_text(raw[key])
    for key in ("instrucciones", "debate", "instrumentos", "evidencias", "criterios"):
        if key in raw:
            base[key] = [_as_text(item) for item in _as_list(raw[key])]
    if isinstance(raw.get("materiales"), dict):
        for key in ("consumible", "devolutivo", "apoyo"):
            base["materiales"][key] = _as_text(raw["materiales"].get(key, ""))
    elif raw.get("materiales"):
        base["materiales"]["consumible"] = _as_text(raw["materiales"])
    base["duracion_horas"] = _as_hours(raw.get("duracion_horas", base["duracion_horas"]))
    return base


def normalize_guide(raw):
    base = empty_guide()
    raw = raw if isinstance(raw, dict) else {}

    meta = raw.get("meta")
    if isinstance(meta, dict):
        base["meta"].update({k: _as_text(v) for k, v in meta.items() if k in base["meta"]})

    identification = raw.get("identificacion")
    if isinstance(identification, dict):
        base["identificacion"].update(
            {
                "programa": _as_text(identification.get("programa")),
                "codigo_programa": _as_text(identification.get("codigo_programa")),
                "proyecto_formativo": _as_text(identification.get("proyecto_formativo")),
                "fase": _as_text(identification.get("fase")),
                "actividad_proyecto": _as_text(identification.get("actividad_proyecto")),
                "competencia": _as_text(identification.get("competencia")),
                "resultados_aprendizaje": _as_text(identification.get("resultados_aprendizaje")),
                "duracion_horas": _as_hours(identification.get("duracion_horas")),
                "programa_id": _as_text(identification.get("programa_id")),
                "proyecto_id": _as_text(identification.get("proyecto_id")),
                "fase_id": _as_text(identification.get("fase_id")),
                "actividad_id": _as_text(identification.get("actividad_id")),
                "resultados_ids": [_as_text(item) for item in _as_list(identification.get("resultados_ids")) if _as_text(item)],
            }
        )

    presentation = raw.get("presentacion")
    if isinstance(presentation, dict) and isinstance(presentation.get("bloques"), list):
        blocks = []
        for block in presentation["bloques"]:
            if isinstance(block, str):
                blocks.append(_presentation_block("parrafo", block))
            elif isinstance(block, dict):
                tipo = _as_text(block.get("tipo", "parrafo")).lower()
                if tipo not in ("parrafo", "subtitulo", "lista"):
                    tipo = "parrafo"
                blocks.append(
                    {
                        "uid": as_uid(block.get("uid")),
                        "tipo": tipo,
                        "texto": _as_text(block.get("texto")),
                    }
                )
        base["presentacion"]["bloques"] = blocks

    moments = raw.get("momentos")
    if isinstance(moments, dict):
        for moment_id in MOMENT_ORDER:
            source = moments.get(moment_id)
            if not isinstance(source, dict):
                continue
            activities = source.get("actividades")
            if activities is None and source.get("titulo") and not isinstance(source.get("titulo"), dict):
                activities = source
            if activities is not None:
                base["momentos"][moment_id]["actividades"] = [
                    _normalize_activity(activity, moment_id, index)
                    for index, activity in enumerate(_as_list(activities))
                ]
            if source.get("titulo"):
                base["momentos"][moment_id]["titulo"] = _as_text(source["titulo"])

    for key in ("evidencias", "referencias", "control_cambios"):
        if isinstance(raw.get(key), list):
            base[key] = copy.deepcopy(raw[key])

    glossary = raw.get("glosario")
    if isinstance(glossary, list):
        base["glosario"] = []
        for item in glossary:
            if isinstance(item, dict):
                base["glosario"].append(
                    {
                        "termino": _as_text(item.get("termino")),
                        "definicion": _as_text(item.get("definicion")),
                    }
                )
            else:
                base["glosario"].append({"termino": _as_text(item), "definicion": ""})

    control = raw.get("control_documento")
    if isinstance(control, dict) and isinstance(control.get("autores"), list):
        authors = []
        for author in control["autores"]:
            if isinstance(author, dict):
                authors.append(
                    {
                        "nombre": _as_text(author.get("nombre")),
                        "cargo": _as_text(author.get("cargo")),
                        "dependencia": _as_text(author.get("dependencia")),
                        "fecha": _as_text(author.get("fecha")),
                    }
                )
        if authors:
            base["control_documento"]["autores"] = authors

    return base


def iter_activities(guide):
    for moment_id in MOMENT_ORDER:
        moment = guide["momentos"][moment_id]
        for index, activity in enumerate(moment["actividades"]):
            yield moment_id, moment, activity, index


def total_hours(guide):
    return sum(float(activity.get("duracion_horas") or 0) for _, _, activity, _ in iter_activities(guide))


def rae_code(guide):
    text = guide["identificacion"].get("resultados_aprendizaje", "")
    match = re.search(r"RAE\s*\d+", text, re.IGNORECASE)
    if match:
        return match.group(0).replace(" ", "").upper()
    return "RAE"


def safe_slug(text, fallback="guia"):
    text = _as_text(text).strip()
    text = re.sub(r"[^\w\sÁÉÍÓÚáéíóúÑñÜü-]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "_", text)
    text = text.strip("_.")
    return text[:80] or fallback
