import copy
import json
import re

from config import CONTENT_BANK_DIR
from services.defaults import empty_activity, rae_code
from services.evidence import derive_evidence

_BANK = None


def _load_bank():
    global _BANK
    if _BANK is None:
        path = CONTENT_BANK_DIR / "bank.json"
        _BANK = json.loads(path.read_text(encoding="utf-8"))
    return _BANK


def context_from_guide(guide):
    identification = guide.get("identificacion", {})
    programa = identification.get("programa") or "el programa de formación"
    proyecto = identification.get("proyecto_formativo") or "el proceso productivo"
    competencia = identification.get("competencia") or "la competencia del programa"
    rae = identification.get("resultados_aprendizaje") or "el resultado de aprendizaje"
    return {
        "programa": programa,
        "programa_lower": programa.lower(),
        "proyecto": proyecto,
        "proyecto_lower": proyecto.lower(),
        "competencia": competencia,
        "competencia_lower": competencia.lower(),
        "rae": rae,
        "rae_code": rae_code(guide),
        "fase": identification.get("fase") or "",
        "tema": _resolve_tema(rae),
        "tema_lower": _resolve_tema(rae).lower(),
    }


def _resolve_tema(text):
    config = _load_bank().get("tema_rules") or {}
    lowered = str(text or "").lower()
    for rule in config.get("rules", []):
        if any(str(needle).lower() in lowered for needle in rule.get("contains", [])):
            if rule.get("tema"):
                return rule["tema"]
    return config.get("default") or "los sistemas embebidos y la automatización"


def _fill(value, context):
    if isinstance(value, str):
        result = value
        for key, replacement in context.items():
            result = result.replace("{" + key + "}", str(replacement))
        return result
    if isinstance(value, list):
        return [_fill(item, context) for item in value]
    if isinstance(value, dict):
        return {key: _fill(item, context) for key, item in value.items()}
    return value


def suggest_presentation(guide):
    template = _load_bank()["presentacion"]
    return _fill(copy.deepcopy(template), context_from_guide(guide))


def _focused_appropriation(template, index, context):
    activity = copy.deepcopy(template)
    if index <= 0:
        return activity
    extra = _load_bank().get("apropiacion_extra")
    if not extra:
        return activity
    override = _fill(copy.deepcopy(extra), {**context, "numero": str(index + 1)})
    activity.update(override)
    return activity


def suggest_activity(guide, moment_id, index=0):
    if moment_id not in ("reflexion_inicial", "contextualizacion", "apropiacion", "transferencia"):
        return empty_activity(moment_id, index)
    context = context_from_guide(guide)
    template = _load_bank()[moment_id]
    activity = _fill(copy.deepcopy(template), context)
    if moment_id == "apropiacion":
        activity = _focused_appropriation(activity, index, context)
    activity.setdefault("evidencias", [])
    activity.setdefault("criterios", [])
    return activity


def suggest_glossary(guide=None):
    return _fill(copy.deepcopy(_load_bank()["glosario"]), context_from_guide(guide or {}))


def suggest_references(guide=None):
    return _fill(copy.deepcopy(_load_bank()["referencias"]), context_from_guide(guide or {}))


LLM_SECTIONS = ("presentacion", "glosario", "referencias", "actividad")


def _template_section(guide, section, moment_id=None, index=0):
    if section == "presentacion":
        return {"presentacion": suggest_presentation(guide)}
    if section == "glosario":
        return {"glosario": suggest_glossary(guide)}
    if section == "referencias":
        return {"referencias": suggest_references(guide)}
    if section == "actividad":
        return {"actividad": suggest_activity(guide, moment_id or "apropiacion", int(index or 0))}
    if section == "evidencias":
        rows, _ = derive_evidence(guide)
        return {"evidencias": rows}
    raise ValueError(f"Sección no soportada: {section}")


def suggest_section(guide, section, moment_id=None, index=0, use_llm=False):
    if use_llm and section in LLM_SECTIONS:
        try:
            from services import llm

            if llm.available():
                payload = llm.suggest(section, guide, moment_id, int(index or 0))
                payload["source"] = "llm"
                return payload
            warning = "La IA está deshabilitada o sin API key; se usaron plantillas."
        except Exception as exc:
            warning = f"No se pudo usar la IA ({exc}); se usaron plantillas."
        result = _template_section(guide, section, moment_id, index)
        result["source"] = "plantilla"
        result["warning"] = warning
        return result
    result = _template_section(guide, section, moment_id, index)
    result["source"] = "plantilla"
    return result


def keywords(text, limit=8):
    words = re.findall(r"[A-Za-zÁÉÍÓÚáéíóúÑñ]{5,}", str(text or "").lower())
    stop = {"para", "como", "desde", "entre", "sobre", "según", "mediante", "sistema", "proceso", "equipo"}
    unique = []
    for word in words:
        if word not in stop and word not in unique:
            unique.append(word)
    return unique[:limit]
