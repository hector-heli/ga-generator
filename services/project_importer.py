import re

from pypdf import PdfReader


def _clean(value):
    return re.sub(r"\s+", " ", (value or "")).strip()


def _num(value):
    try:
        return float(str(value).replace(",", "."))
    except Exception:
        return 0.0


def _strip_running(text):
    lines = []
    for line in (text or "").splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("Modelo de Mejora"):
            continue
        if s.startswith("SERVICIO NACIONAL DE APRENDIZAJE"):
            continue
        if s.startswith("Sistema Integrado de Gestión"):
            continue
        if s.startswith("PROYECTO FORMATIVO"):
            continue
        if s.startswith("Procedimiento Ejecución"):
            continue
        if re.match(r"^Página \d+ de \d+", s):
            continue
        if re.match(r"^GFPI-?\s*F-?\s*016", s, re.I):
            continue
        lines.append(s)
    return "\n".join(lines)


def _extract_basic(page1):
    t = page1
    data = {
        "codigo_sofia": "", "programa_codigo": "", "programa_version": "",
        "nombre": "", "centro_formacion": "", "regional": "", "tiempo_meses": 0.0,
        "empresas": "", "palabras_clave": "", "total_resultados": 0,
        "planteamiento": "", "justificacion": "", "objetivo_general": "",
        "objetivos_especificos": "", "alcance": "", "innovacion": "", "valoracion": "",
    }
    m = re.search(r"Código Proyecto SOFIA:\s*.*?Información básica del proyecto\s*(\d{5,})", t, re.S | re.I)
    if not m:
        m = re.search(r"Código Proyecto SOFIA:\s*(\d{5,})", t, re.I)
    if m:
        data["codigo_sofia"] = m.group(1)
    m = re.search(r"(\d{5,})\s*Código del Programa SOFIA", t, re.I)
    if m:
        data["programa_codigo"] = m.group(1)
    m = re.search(r"Versión del Programa:\s*(\d+)", t, re.I)
    if m:
        data["programa_version"] = m.group(1)
    m = re.search(r"1\.3\s*\.?\s*Nombre del proyecto:\s*(.+?)\s*1\.4", t, re.S | re.I)
    if m:
        data["nombre"] = _clean(m.group(1))
    m = re.search(r"1\.1 Centro de Formación:\s*(.+?)\s*1\.2", t, re.S | re.I)
    if m:
        data["centro_formacion"] = _clean(m.group(1))
    m = re.search(r"1\.2 Regional:\s*(.+?)\s*1\.3", t, re.S | re.I)
    if m:
        data["regional"] = _clean(m.group(1))
    m = re.search(r"1\.5 Tiempo estimado de\s*ejecución del proyecto \(meses\):\s*([\d.,]+)", t, re.S | re.I)
    if m:
        data["tiempo_meses"] = _num(m.group(1))
    m = re.search(r"1\.6 Empresas o instituciones.*?financiación:.*?\)\s*(.+?)\s*1\.7", t, re.S | re.I)
    if m:
        data["empresas"] = _clean(m.group(1))
    m = re.search(r"1\.7 Palabras claves de\s*búsqueda:\s*(.+?)\s*1\.8", t, re.S | re.I)
    if m:
        value = _clean(m.group(1))
        value = re.sub(r"(?:\s+\d+){1,4}\s*$", "", value).strip()
        data["palabras_clave"] = value
    m = re.search(r"1\.8 Número total de resultados.*?:\s*(\d+)", t, re.S | re.I)
    if m:
        data["total_resultados"] = int(_num(m.group(1)))
    m = re.search(r"2\.1 Planteamiento del problema o necesidad que se pretende solucionar\s*(.+?)\s*2\.2", t, re.S | re.I)
    if m:
        data["planteamiento"] = _clean(m.group(1))
    m = re.search(r"2\.2 Justificación del proyecto\s*(.+?)\s*2\.3", t, re.S | re.I)
    if m:
        data["justificacion"] = _clean(m.group(1))
    m = re.search(r"2\.3 Objetivo general\s*(.+?)\s*2\.4", t, re.S | re.I)
    if m:
        data["objetivo_general"] = _clean(m.group(1))
    m = re.search(r"2\.4 Objetivos específicos\s*(.+?)\s*2\.5", t, re.S | re.I)
    if m:
        data["objetivos_especificos"] = _clean(m.group(1))
    m = re.search(r"2\.5 Alcance\s*(.+?)\s*2\.6", t, re.S | re.I)
    if m:
        data["alcance"] = _clean(m.group(1))
    m = re.search(r"2\.6 Innovación/Gestión Tecnológica\s*(.+?)\s*2\.7", t, re.S | re.I)
    if m:
        data["innovacion"] = _clean(m.group(1))
    m = re.search(r"2\.7 Valoración Productiva\s*(.+?)\s*3\.\s*Planeación", t, re.S | re.I)
    if m:
        data["valoracion"] = _clean(m.group(1))
    return data


def _phase_chunks(pages):
    chunks = []
    current = None
    for page in pages:
        text = _strip_running(page)
        for line in text.splitlines():
            m = re.match(r"^FASE\s+(\d+)\b\s*(.*)$", line.strip(), re.I)
            if m:
                if current:
                    chunks.append(current)
                current = {"numero": m.group(1), "nombre": _clean(m.group(2)), "texto": ""}
                continue
            if current:
                current["texto"] += " " + line
    if current:
        chunks.append(current)
    # merge repeated phase headings: same number -> concatenate
    merged = {}
    order = []
    for ch in chunks:
        key = ch["numero"]
        if key not in merged:
            merged[key] = {"numero": key, "nombre": ch["nombre"], "texto": ""}
            order.append(key)
        if not merged[key]["nombre"] and ch["nombre"]:
            merged[key]["nombre"] = ch["nombre"]
        merged[key]["texto"] += " " + ch["texto"]
    return [merged[k] for k in order]


def _parse_phase_activities(chunk):
    text = _clean(chunk.get("texto", ""))
    # code segments: RAE code followed by competency code
    matches = list(re.finditer(r"\b(\d{6})\s*-\s*", text))
    activities = []
    for i, m in enumerate(matches):
        rae_code = m.group(1)
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        segment = text[m.end():end].strip(" .-")
        # split RAE part from competency name at the next code if present
        nxt = matches[i + 1] if i + 1 < len(matches) else None
        comp_name = ""
        if nxt:
            after = text[nxt.end():]
            stop = (matches[i + 2].start() - nxt.end()) if i + 2 < len(matches) else len(after)
            comp_name = _clean(after[:max(stop, 0)])[:300]
        hm = re.search(r"(\d+(?:[\.,]\d+)?)\s*H\b", segment, re.I)
        hours = _num(hm.group(1)) if hm else 0.0
        denom = re.sub(r"\s*\d+(?:[\.,]\d+)?\s*H\b.*$", "", segment, flags=re.I).strip(" .-")
        rae_label = ""
        rm = re.match(r"(RAE\s*\d+)\s*:\s*(.*)", denom, re.I)
        if rm:
            rae_label = re.sub(r"\s+", "", rm.group(1)).upper()
            denom = rm.group(2).strip()
        if len(denom) < 8:
            continue
        activities.append({
            "codigo": rae_code,
            "rae_codigo": rae_label,
            "nombre": denom[:300],
            "descripcion": comp_name,
            "duracion": hours,
        })
    return activities


def parse_project_pdf(path):
    reader = PdfReader(str(path))
    pages = [p.extract_text() or "" for p in reader.pages]
    basic = _extract_basic(_strip_running("\n".join(pages[:3])))
    # phases live between page 3 and the resources section
    phase_pages = []
    for page in pages[2:]:
        if "3.7. Recursos estimados" in page or "Recursos estimados" in page:
            break
        phase_pages.append(page)
    chunks = _phase_chunks(phase_pages)
    fases = []
    warnings = []
    for ch in chunks:
        acts = _parse_phase_activities(ch)
        if not acts:
            warnings.append(f"Fase {ch['numero']}: no se detectaron actividades/RAE.")
        fases.append({"nombre": f"FASE {ch['numero']} {ch['nombre']}".strip(), "productos": "", "actividades": acts})
    if not fases:
        warnings.append("No se detectaron fases del proyecto en el PDF.")
    total_raes = sum(len(f["actividades"]) for f in fases)
    if basic.get("total_resultados") and total_raes and abs(basic["total_resultados"] - total_raes) > 2:
        warnings.append(f"El PDF declara {basic['total_resultados']} resultados y se detectaron {total_raes} actividades/RAE.")
    return {
        "proyecto": basic,
        "fases": fases,
        "meta": {"source": str(path), "fases_count": len(fases), "actividades_count": total_raes},
        "warnings": warnings[:60],
    }
