import re
from pathlib import Path

from services.pdf_layout import (
    parse_project_pdf,
    clean,
    _num,
    strip_running_headers,
)


# ---------------------------------------------------------------------------
# Utilidades auxiliares (replicando lo esencial de la versión original para
# mantener compatibilidad mientras se refactoriza la lógica principal)
# ---------------------------------------------------------------------------

def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()


def _num(value: str) -> float:
    try:
        return float(str(value).replace(",", "."))
    except Exception:
        return 0.0


def _strip_running(text: str) -> str:
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


def _extract_basic(page1: str) -> dict:
    """Versión ligera de la extracción básica original, usa pdf_layout donde
    sea posible pero mantiene la firma esperada por el código que llama."""
    from services.pdf_layout import extract_pdf_text_tables

    # Usar el nuevo parser estructurado si disponemos de pdfplumber
    try:
        raw = extract_pdf_text_tables(str(page1)) if isinstance(page1, Path) else extract_pdf_text_tables(Path(page1))
        if raw.get("pages"):
            basic = raw["pages"][0]
            # El nuevo parser ya devuelve la estructura completa; aquí solo
            # devolvemos los campos que el código antiguo esperaba.
            txt = basic.get("text", "")
            tables = basic.get("tables", [])
            combined = txt
            for tbl in tables:
                for row in tbl:
                    for c in row:
                        combined += " " + (c or "")

            data = {
                "codigo_sofia": "",
                "programa_codigo": "",
                "programa_version": "",
                "nombre": "",
                "centro_formacion": "",
                "regional": "",
                "tiempo_meses": 0.0,
                "empresas": "",
                "palabras_clave": "",
                "total_resultados": 0,
            }

            # Código SOFIA
            m = re.search(r"Código Proyecto SOFIA[:\s]*(\d{5,})", combined, re.I)
            if m:
                data["codigo_sofia"] = m.group(1)

            # Código programa
            m = re.search(r"(\d{5,})\s*Código del Programa SOFIA", combined, re.I)
            if m:
                data["programa_codigo"] = m.group(1)

            # Versión programa
            m = re.search(r"Versión del Programa[:\s]*(\d+)", combined, re.I)
            if m:
                data["programa_version"] = m.group(1)

            # Nombre del proyecto (1.3)
            m = re.search(r"1\.3\s*\.?\s*Nombre del proyecto:\s*(.+?)\s*1\.4", combined, re.S | re.I)
            if m:
                data["nombre"] = _clean(m.group(1))

            # Centro de formación (1.1)
            m = re.search(r"1\.1\s*Centro de Formación:\s*(.+?)\s*1\.2", combined, re.S | re.I)
            if m:
                data["centro_formacion"] = _clean(m.group(1))

            # Regional (1.2)
            m = re.search(r"1\.2\s*Regional:\s*(.+?)\s*1\.3", combined, re.S | re.I)
            if m:
                data["regional"] = _clean(m.group(1))

            # Tiempo estimado ejecución (meses) (1.5)
            m = re.search(r"1\.5\s*Tiempo estimado de\s*ejecución del proyecto \(meses\):\s*([\d.,]+)", combined, re.S | re.I)
            if m:
                data["tiempo_meses"] = _num(m.group(1))

            # Empresas (1.6)
            m = re.search(r"1\.6\s*Empresas o instituciones.*?financiación:.*?\)\s*(.+?)\s*1\.7", combined, re.S | re.I)
            if m:
                data["empresas"] = _clean(m.group(1))

            # Palabras clave (1.7)
            m = re.search(r"1\.7\s*Palabras claves de\s*búsqueda:\s*(.+?)\s*1\.8", combined, re.S | re.I)
            if m:
                value = _clean(m.group(1))
                value = re.sub(r"(?:\s+\d+){1,4}\s*$", "", value).strip()
                data["palabras_clave"] = value

            # Total resultados (1.8)
            m = re.search(r"1\.8\s*Número total de resultados.*?:\s*(\d+)", combined, re.S | re.I)
            if m:
                data["total_resultados"] = int(_num(m.group(1)))

            return data
    except Exception:
        pass

    # Fallback: extracción basada en expresiones regulares sobre texto limpio
    t = _strip_running(page1)
    data = {
        "codigo_sofia": "",
        "programa_codigo": "",
        "programa_version": "",
        "nombre": "",
        "centro_formacion": "",
        "regional": "",
        "tiempo_meses": 0.0,
        "empresas": "",
        "palabras_clave": "",
        "total_resultados": 0,
    }

    m = re.search(r"Código Proyecto SOFIA[:\s]*(\d{5,})", t, re.I)
    if m:
        data["codigo_sofia"] = m.group(1)

    m = re.search(r"(\d{5,})\s*Código del Programa SOFIA", t, re.I)
    if m:
        data["programa_codigo"] = m.group(1)

    m = re.search(r"Versión del Programa[:\s]*(\d+)", t, re.I)
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

    m = re.search(r"1\.7\s*Palabras claves de\s*búsqueda:\s*(.+?)\s*1\.8", t, re.S | re.I)
    if m:
        value = _clean(m.group(1))
        value = re.sub(r"(?:\s+\d+){1,4}\s*$", "", value).strip()
        data["palabras_clave"] = value

    m = re.search(r"1\.8\s*Número total de resultados.*?:\s*(\d+)", t, re.S | re.I)
    if m:
        data["total_resultados"] = int(_num(m.group(1)))

    return data


# ---------------------------------------------------------------------------
# Función principal: parse_project_pdf (compatibilidad con app.py)
# ---------------------------------------------------------------------------

def parse_project_pdf(path: str) -> dict:
    """Parsea un PDF de proyecto formativo GFPI-F-016.

    Esta función es el punto de entrada que usa ``app.py`` y ``project_import``.
    Devuelve un dict con las claves esperadas:
      - "proyecto": datos básicos (misma estructura que la versión antigua).
      - "fases": lista de fases con actividades/resultados/competencia.
      - "meta": conteo de fases y actividades/RAE.
      - "warnings": advertencias de consistencia.

    La implementación prioriza la extracción estructurada con pdfplumber
    (a través de ``services.pdf_layout.parse_project_pdf``) y cae_back a
    la lógica heredada cuando el PDF no tiene tablas compatibles.
    """
    # Intentar usar el nuevo parser estructurado
    try:
        result = parse_project_pdf(str(path))
        # Asegurar compatibilidad hacia atrás: el nuevo parser devuelve
        # "actividad_denominacion" o similar; normalizamos los nombres de campo.
        # El schema esperado por app.py/Project_import incluye:
        #   - fase.nombre, fase.actividades[].nombre, .duracion, .rae_codigo, etc.
        # Re-mapeo sutil para que coincida con lo que espera el flujo actual:
        if result.get("fases"):
            # Asegurar que cada actividad tenga 'nombre' y 'descripcion' (o 'actividad')
            for fase in result["fases"]:
                if fase.get("actividad") and not fase.get("nombre"):
                    fase["nombre"] = fase.pop("actividad", "")
                # Normalizar 'resultado_codigo' a 'rae_codigo' para compatibilidad
                for act in fase.get("actividades", []) if "actividades" in fase else []:
                    pass  # El nuevo schema no usa "actividades" anidadas en la misma forma
        return result
    except Exception:
        pass

    # Fallback: ruta antigua (texto plano + regex)
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = [p.extract_text() or "" for p in reader.pages]
    basic = _extract_basic(_strip_running("\n".join(pages[:3])))

    # phases live between page 3 and the resources section
    phase_pages = []
    for page in pages[2:]:
        if "3.7. Recursos estimados" in page or "Recursos estimados" in page:
            break
        phase_pages.append(page)

    # _phase_chunks y _parse_phase_activities heredados adaptados
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
        matches = list(re.finditer(r"\b(\d{6})\s*-\s", text))
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

    chunks = _phase_chunks(phase_pages)
    fases = []
    warnings = []
    for ch in chunks:
        acts = _parse_phase_activities(ch)
        if not acts:
            warnings.append(f"Fase {ch['numero']}: no se detectaron actividades/RAE.")
        fase_nombre = f"FASE {ch['numero']} {ch['nombre']}".strip()
        fases.append({
            "nombre": fase_nombre,
            "productos": "",
            "actividades": acts,
        })
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