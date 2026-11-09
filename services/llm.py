import json
import os
import re
import urllib.error
import urllib.request

from config import load_config
from services.defaults import MOMENTS, empty_activity, normalize_guide

SYSTEM_PROMPT = (
    "Eres un experto en diseño curricular del SENA (Formación Profesional Integral). "
    "Redactas contenido técnico en español, claro y pertinente al programa de formación. "
    "Respondes únicamente con JSON válido, sin explicaciones ni bloques de código."
)


def _settings():
    config = load_config()
    settings = dict(config.get("llm") or {})
    env_key = os.environ.get("GA_LLM_API_KEY")
    if env_key:
        settings["api_key"] = env_key
    return settings


def available():
    settings = _settings()
    return bool(settings.get("enabled")) and bool(settings.get("api_key")) and bool(settings.get("base_url"))


def chat(messages, temperature=0.4, timeout=60):
    settings = _settings()
    if not settings.get("api_key"):
        raise RuntimeError("No hay API key configurada para el proveedor LLM.")
    base_url = str(settings.get("base_url") or "").rstrip("/")
    if not base_url:
        raise RuntimeError("No hay base_url configurada para el proveedor LLM.")
    url = f"{base_url}/chat/completions"
    body = json.dumps(
        {
            "model": settings.get("model") or "gpt-4o-mini",
            "messages": messages,
            "temperature": temperature,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings['api_key']}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"El proveedor LLM respondió {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"No fue posible contactar al proveedor LLM: {exc.reason}") from exc
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Respuesta del proveedor LLM con formato inesperado.") from exc


def _parse_json(text):
    text = str(text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise RuntimeError("El proveedor LLM no devolvió JSON válido.")
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise RuntimeError("El proveedor LLM no devolvió JSON válido.") from exc


def _context(guide):
    identification = guide.get("identificacion", {}) if isinstance(guide, dict) else {}
    return {
        "programa": identification.get("programa") or "el programa de formación",
        "proyecto": identification.get("proyecto_formativo") or "el proceso productivo",
        "competencia": identification.get("competencia") or "la competencia del programa",
        "resultados_aprendizaje": identification.get("resultados_aprendizaje") or "el resultado de aprendizaje",
        "fase": identification.get("fase") or "",
        "actividad_proyecto": identification.get("actividad_proyecto") or "",
    }


def _ask(context, instruction, timeout=60):
    user = (
        "Contexto de la guía de aprendizaje:\n"
        f"- Programa: {context['programa']}\n"
        f"- Proyecto formativo: {context['proyecto']}\n"
        f"- Competencia: {context['competencia']}\n"
        f"- Resultado de aprendizaje: {context['resultados_aprendizaje']}\n"
        f"- Fase: {context['fase']}\n"
        f"- Actividad del proyecto: {context['actividad_proyecto']}\n\n"
        f"{instruction}"
    )
    raw = chat(
        [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}],
        timeout=timeout,
    )
    return _parse_json(raw)


def _activity_payload(raw, moment_id):
    guide = normalize_guide({"momentos": {moment_id: {"actividades": [raw]}}})
    activity = guide["momentos"][moment_id]["actividades"][0]
    fallback = empty_activity(moment_id, 0)
    for key, value in fallback.items():
        activity.setdefault(key, value)
    return {"actividad": activity}


def suggest_activity(context, moment_id, index=0):
    moment = MOMENTS.get(moment_id, MOMENTS["apropiacion"])
    instruction = (
        f"Redacta la actividad de aprendizaje número {index + 1} del momento '{moment['label']}' "
        f"({moment['titulo']}). Devuelve un objeto JSON con las claves: "
        "titulo (texto), introduccion (texto), instrucciones (lista de textos), debate (lista de textos), "
        "ambiente (texto), estrategias (texto), materiales (objeto con consumible, devolutivo y apoyo), "
        "instrumentos (lista de textos), duracion_horas (número), modalidad (texto), "
        "evidencias (lista de textos) y criterios (lista de textos)."
    )
    return _activity_payload(_ask(context, instruction), moment_id)


def suggest_presentation(context):
    instruction = (
        "Redacta la presentación de la guía de aprendizaje dirigida al aprendiz. "
        "Devuelve un objeto JSON con la clave bloques, una lista de objetos con las claves "
        "tipo (parrafo, subtitulo o lista) y texto."
    )
    raw = _ask(context, instruction)
    guide = normalize_guide({"presentacion": raw})
    blocks = guide["presentacion"]["bloques"]
    if not blocks:
        raise RuntimeError("El proveedor LLM no devolvió bloques de presentación.")
    return {"presentacion": {"bloques": blocks}}


def suggest_glossary(context):
    instruction = (
        "Propón un glosario de entre 8 y 12 términos técnicos pertinentes. "
        "Devuelve un objeto JSON con la clave glosario, una lista de objetos con las claves termino y definicion."
    )
    raw = _ask(context, instruction)
    guide = normalize_guide({"glosario": raw.get("glosario") if isinstance(raw, dict) else raw})
    if not guide["glosario"]:
        raise RuntimeError("El proveedor LLM no devolvió un glosario válido.")
    return {"glosario": guide["glosario"]}


def suggest_references(context):
    instruction = (
        "Propón entre 5 y 8 referentes bibliográficos confiables en formato APA. "
        "Devuelve un objeto JSON con la clave referencias, una lista de textos."
    )
    raw = _ask(context, instruction)
    references = raw.get("referencias") if isinstance(raw, dict) else raw
    if not isinstance(references, list):
        raise RuntimeError("El proveedor LLM no devolvió referencias válidas.")
    cleaned = [str(item).strip() for item in references if str(item).strip()]
    if not cleaned:
        raise RuntimeError("El proveedor LLM no devolvió referencias válidas.")
    return {"referencias": cleaned}


def suggest(section, guide, moment_id=None, index=0, timeout=60):
    context = _context(guide)
    if section == "actividad":
        return suggest_activity(context, moment_id or "apropiacion", int(index or 0))
    if section == "presentacion":
        return suggest_presentation(context)
    if section == "glosario":
        return suggest_glossary(context)
    if section == "referencias":
        return suggest_references(context)
    raise ValueError(f"Sección no soportada por el proveedor LLM: {section}")
