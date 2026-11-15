"""Capa de extracción y normalización determinista para PDFs GFPI-F-016.

Proporciona:
  - Limpieza de texto (eliminación de encabezados/pies, normalización de acentos).
  - Extracción de texto + tablas por página (pdfplumber como primaria, pypdf respaldo).
  - Parsers de estructura para PDFs de proyecto formativo y diseño curricular.
  - Helpers reutilizables: clean, fold/between, numéricos, detección de códigos.
"""

import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Utilidades de normalización y limpieza
# ---------------------------------------------------------------------------

_ACCENTS: dict = {
    "á": "a",
    "à": "a",
    "ä": "a",
    "â": "a",
    "ã": "a",
    "å": "a",
    "é": "e",
    "è": "e",
    "ë": "e",
    "ê": "e",
    "í": "i",
    "ì": "i",
    "ï": "i",
    "î": "i",
    "ó": "o",
    "ò": "o",
    "ö": "o",
    "ô": "o",
    "õ": "o",
    "ú": "u",
    "ù": "u",
    "ü": "u",
    "û": "u",
    "ñ": "n",
    "ç": "c",
}
_ACCENTS.update({k.upper(): v.upper() for k, v in list(_ACCENTS.items())})
_TABLE = str.maketrans(_ACCENTS)


def fold(text: str) -> str:
    """Quita tildes y normaliza para comparaciones insensibles a acentos/mayúsculas."""
    return (text or "").translate(_TABLE)


def clean(value: str) -> str:
    """Comprime espacios en blanco y recorta."""
    return re.sub(r"\s+", " ", (value or "")).strip()


def _num(value: str) -> float:
    try:
        return float(str(value).replace(",", "."))
    except Exception:
        return 0.0


def between(
    text: str,
    start_re: str,
    end_re: Optional[str] = None,
) -> str:
    """Extrae texto entre dos marcadores regex sobre *text* sin procesar."""
    folded = fold(text)
    m1 = re.search(start_re, folded, re.I | re.S)
    if not m1:
        return ""
    start_idx = m1.start()
    if end_re is None:
        return text[start_idx:]
    folded_after = folded[m1.end():]
    m2 = re.search(end_re, folded_after, re.I | re.S)
    if not m2:
        return text[start_idx:]
    end_idx = start_idx + m1.end() + m2.start()
    return text[start_idx:end_idx]


def strip_running_headers(text: str) -> str:
    """Elimina líneas recurrentes de cubierta/estructura de PDFs GFPI-F-016."""
    lines: List[str] = []
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
        if re.match(r"^SENA[-\s]*logo", s, re.I):
            continue
        lines.append(s)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Extracción de PDF: texto + tablas
# ---------------------------------------------------------------------------

def extract_pdf_text_tables(path: str) -> Dict[str, Any]:
    """Intenta extraer texto y tablas de todas las páginas de un PDF.

    Retorna un dict con:
      "pages": lista de dicts { "text": str, "tables": list[list[list[str]]] }
    Si falla pdfplumber, intenta con pypdf solo texto.
    """
    result: Dict[str, Any] = {"pages": []}

    try:
        import pdfplumber

        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                txt = page.extract_text() or ""
                tables = page.extract_tables() or []
                result["pages"].append({"text": txt, "tables": tables})
            return result
    except Exception:
        pass

    # Fallback a pypdf (solo texto, no tablas estructuradas)
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        for page in reader.pages:
            txt = page.extract_text() or ""
            result["pages"].append({"text": txt, "tables": []})
        return result
    except Exception:
        return result


# ---------------------------------------------------------------------------
# Parser de PDF de proyecto formativo (moved from project_importer.py)
# ---------------------------------------------------------------------------

PHASE_RE = re.compile(r"^\s*(?:FASE|ETAPA)\s*(\d+)\b[:\s.-]*(.*)$", re.I)
RESULT_RE = re.compile(r"^\s*(\d{6})\s*[-–—]?\s*(.+)$", re.S)
COMP_RE = re.compile(r"^\s*(\d{7,12})\s*[-–—]?\s*(.+)$", re.S)
HOURS_RE = re.compile(r"(?<!\w)(\d+(?:[.,]\d+)?)\s*(?:H|HORAS?)\b", re.I)


def _is_result_code(cell: str) -> bool:
    return bool(re.match(r"^\s*\d{6}\s*[-–—]", cell))


def _is_competence_code(cell: str) -> bool:
    return bool(re.match(r"^\s*\d{7,12}\s*[-–—]", cell))


def _parse_single_rae_line(line: str) -> Optional[Dict[str, Any]]:
    """Parsea una línea con un resultado de aprendizaje."""
    line = clean(line)
    if not line:
        return None

    m = re.match(r"^(\d{6})\s*[-–—]\s*(.+)$", line)
    if not m:
        return None

    code = m.group(1)
    rest = m.group(2).strip()

    label = ""
    rm = re.match(r"^(RAE|RA|RAP)\s*[:\s]*(\d+)\s*[:–—.]?\s*", rest, re.I)
    if rm:
        label = f"{rm.group(1).upper()}{rm.group(2)}"
        rest = rest[rm.end():].strip()

    hours = 0.0
    hm = re.search(HOURS_RE, rest)
    if hm:
        hours = _num(hm.group(1))
        rest = re.sub(HOURS_RE, "", rest, flags=re.I).strip()

    name = clean(rest).strip(" .:-–—")
    if re.match(r"^(DENOMINACI[OÓ]N|RESULTADOS DE APRENDIZAJE)$", fold(name), re.I):
        return None
    if len(name) < 6:
        return None

    return {
        "codigo": code,
        "denominacion": name,
        "duracion": hours,
        "label": label.upper() if label else "",
    }


def _parse_project_phases(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Parsea fases, actividades, resultados y competencias del proyecto."""
    records: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None

    for page in pages:
        text = page.get("text", "") or ""
        tables = page.get("tables", []) or []

        all_cells: List[str] = []
        for line in text.splitlines():
            s = clean(line)
            if s:
                all_cells.append(s)
        for tbl in tables:
            if not tbl or len(tbl[0]) < 4:
                continue
            for row in tbl:
                for c in row:
                    s = clean(c)
                    if s:
                        all_cells.append(s)

        for cell in all_cells:
            if _is_result_code(cell):
                if current is not None:
                    records.append(current)
                m = RESULT_RE.match(cell)
                if not m:
                    continue
                code = m.group(1)
                rest = m.group(2)

                label = ""
                rm = re.match(r"^(RAE|RA|RAP)\s*[:\s]*(\d+)\s*[:–—.]?\s*", rest, re.I)
                if rm:
                    label = f"{rm.group(1).upper()}{rm.group(2)}"
                    rest = rest[rm.end():].strip()

                parsed = _parse_single_rae_line(code + " " + rest) if rest else None
                if parsed is None:
                    hours = 0.0
                    hm = re.search(HOURS_RE, rest)
                    if hm:
                        hours = _num(hm.group(1))
                        rest = re.sub(HOURS_RE, "", rest, flags=re.I).strip()
                    name = clean(rest).strip(" .:-–—")
                    parsed = {"codigo": code, "denominacion": name, "duracion": hours, "label": label.upper() if label else ""}

                fase_match = re.search(PHASE_RE, text)
                fase = ""
                fase_num = "0"
                if fase_match:
                    fase = clean(fase_match.group(2)).strip()
                    fm = re.search(r"(\d+)", fase)
                    if fm:
                        fase_num = fm.group(1)

                comp_match = re.search(COMP_RE, rest)
                comp_code = ""
                comp_name = ""
                if comp_match:
                    comp_code = comp_match.group(1)
                    comp_name = clean(comp_match.group(2)).strip()
                if not comp_code and current is not None:
                    comp_code = current.get("competencia_codigo", "")
                    comp_name = current.get("competencia_nombre", "")

                current = {
                    "fase": fase,
                    "fase_num": fase_num,
                    "actividad": "",
                    "resultado_codigo": parsed["codigo"],
                    "resultado_denominacion": parsed["denominacion"],
                    "resultado_label": parsed["label"],
                    "horas": parsed["duracion"],
                    "competencia_codigo": comp_code,
                    "competencia_nombre": comp_name,
                }
                continue

            if _is_competence_code(cell) and current is not None:
                cm = COMP_RE.match(cell)
                if cm:
                    current["competencia_codigo"] = cm.group(1)
                    current["competencia_nombre"] = clean(cm.group(2)).strip()
                continue

            if current is None:
                continue

            if len(cell) >= 8 and not _is_result_code(cell) and not _is_competence_code(cell):
                if not current.get("actividad"):
                    current["actividad"] = clean(cell)
                else:
                    old = current["actividad"]
                    new = clean(cell)
                    if old != new:
                        current["actividad"] = old + " " + new

    filtered: List[Dict[str, Any]] = []
    for r in records:
        if not r.get("resultado_codigo") and not r.get("actividad"):
            continue
        if not r.get("fase_num") and r.get("fase"):
            fm = re.search(r"(\d+)", r["fase"])
            r["fase_num"] = fm.group(1) if fm else "0"
        filtered.append(r)

    return filtered


def parse_project_pdf(path: str) -> Dict[str, Any]:
    """Parsea un PDF de proyecto formativo GFPI-F-016.

    Extrae datos básicos, fases con actividades/resultados/competencias,
    y metadatos de consistencia.
    """
    try:
        p = Path(path)
        if not p.exists():
            return {
                "proyecto": {},
                "fases": [],
                "meta": {"source": str(path), "fases_count": 0, "actividades_count": 0},
                "warnings": [f"Archivo no encontrado: {path}"],
            }
    except Exception as e:
        return {
            "proyecto": {},
            "fases": [],
            "meta": {"source": str(path), "fases_count": 0, "actividades_count": 0},
            "warnings": [f"Error accediendo al archivo: {e}"],
        }

    raw = extract_pdf_text_tables(str(path))
    if not raw.get("pages"):
        return {
            "proyecto": {},
            "fases": [],
            "meta": {"source": str(path), "fases_count": 0, "actividades_count": 0},
            "warnings": ["No se pudieron extraer páginas del PDF."],
        }

    # 1. Datos básicos (página 1) - usando tablas si están disponibles
    basic: Dict[str, Any] = {
        "codigo_sofia": "",
        "programa_codigo": "",
        "programa_version": "",
        "nombre": "",
        "centro_formacion": "",
        "regional": "",
        "tiempo_meses": "0",
        "empresas": "",
        "palabras_clave": "",
        "total_resultados": "0",
    }

    # Intentar extraer de tablas de la página 1
    tables_1 = raw["pages"][0].get("tables", []) if raw.get("pages") else []
    combined_text_1 = raw["pages"][0].get("text", "") if raw.get("pages") else ""

    # Parsear tablas para extraer campos básicos
    for row in tables_1:
        if not row or len(row) < 2:
            continue
        label = clean(row[0])
        value = clean(row[1]) if len(row) > 1 and row[1] else ""
        label_f = fold(label)

        # Código SOFIA (buscar en cualquier etiqueta que lo contenga)
        if not basic["codigo_sofia"] and re.search(r"Código Proyecto SOFIA", label_f, re.I):
            m = re.search(r"\d{5,}", value)
            if m:
                basic["codigo_sofia"] = m.group(0)

        # Código programa
        if not basic["programa_codigo"] and re.search(r"Código del Programa", label_f, re.I):
            m = re.search(r"\d{5,}", value)
            if m:
                basic["programa_codigo"] = m.group(0)

        # Versión programa
        if not basic["programa_version"] and re.search(r"Versión del Programa", label_f, re.I):
            m = re.search(r"\d+", value)
            if m:
                basic["programa_version"] = m.group(0)

        # Nombre del proyecto
        if not basic["nombre"] and re.search(r"Nombre del proyecto", label_f, re.I):
            basic["nombre"] = value

        # Centro de formación
        if not basic["centro_formacion"] and re.search(r"Centro de Formación", label_f, re.I):
            basic["centro_formacion"] = value

        # Regional
        if not basic["regional"] and re.search(r"Regional", label_f, re.I):
            basic["regional"] = value

        # Tiempo meses
        if not basic["tiempo_meses"] or basic["tiempo_meses"] == "0":
            if re.search(r"Tiempo estimado", label_f, re.I):
                m = re.search(r"[\d.,]+", value)
                if m:
                    basic["tiempo_meses"] = m.group(0)

        # Empresas
        if not basic["empresas"] and re.search(r"Empresas", label_f, re.I):
            basic["empresas"] = value

        # Palabras clave
        if not basic["palabras_clave"] and re.search(r"Palabras clave", label_f, re.I):
            basic["palabras_clave"] = value

        # Total resultados
        if not basic["total_resultados"] or basic["total_resultados"] == "0":
            if re.search(r"Número total de resultados", label_f, re.I):
                m = re.search(r"\d+", value)
                if m:
                    basic["total_resultados"] = m.group(0)

    # Fallback a extracción por texto si faltan campos esenciales
    if not basic["nombre"] or not basic["codigo_sofia"]:
        txt = combined_text_1
        # Código SOFIA
        if not basic["codigo_sofia"]:
            m = re.search(r"Código Proyecto SOFIA[:\s]*(\d{5,})", txt, re.I)
            if m:
                basic["codigo_sofia"] = m.group(1)
        # Nombre
        if not basic["nombre"]:
            m = re.search(r"1\.3\s*Nombre del proyecto[:\s]*(.+?)(?:\s*1\.4|\s*Código)", txt, re.S | re.I)
            if m:
                basic["nombre"] = clean(m.group(1))
        # Programa código
        if not basic["programa_codigo"]:
            m = re.search(r"Código del Programa SOFIA[:\s]*(\d{5,})", txt, re.I)
            if m:
                basic["programa_codigo"] = m.group(1)
        # Versión
        if not basic["programa_version"]:
            m = re.search(r"Versión del Programa[:\s]*(\d+)", txt, re.I)
            if m:
                basic["programa_version"] = m.group(1)

    # 2. Fases de planeación (páginas 3 en adelante hasta recursos)
    phase_pages: List[Dict[str, Any]] = []
    for pg in raw["pages"][2:]:
        txt = pg.get("text", "") or ""
        if re.search(r"3\.\s*7\b.*[Rr]ecursos", txt) or "Recursos estimados" in txt or "3.7." in txt:
            break
        phase_pages.append(pg)

    # 3. Parsear fases
    fases_parsed = _parse_project_phases(phase_pages)

    # 4. Warnings y totales
    warnings: List[str] = []
    rae_count = sum(1 for f in fases_parsed if f.get("resultado_codigo"))
    total_hours = sum(f.get("horas", 0) or 0 for f in fases_parsed)

    declared = basic.get("total_resultados")
    if declared and rae_count and abs(int(declared) - rae_count) > 2:
        warnings.append(f"El PDF declara {declared} resultados y se detectaron {rae_count} RAE con código.")

    phases_no_act = sum(1 for f in fases_parsed if not f.get("actividad"))
    if phases_no_act:
        warnings.append(f"{phases_no_act} fase(s) sin actividad/descripción detectada(s).")

    phases_no_rae = sum(1 for f in fases_parsed if not f.get("resultado_codigo"))
    if phases_no_rae:
        warnings.append(f"{phases_no_rae} fase(s) sin RAE/código de resultado detectado(s).")

    if total_hours < 2000 or total_hours > 4000:
        warnings.append(f"Suma total de horas detectadas ({total_hours:.0f}) difiere del rango esperado (~2000-4000 h).")

    output_fases: List[Dict[str, Any]] = []
    for f in fases_parsed:
        output_fases.append({
            "nombre": f.get("fase", f"FASE {f.get('fase_num', '')}").strip(),
            "actividad": f.get("actividad", "").strip() or None,
            "resultado_codigo": f.get("resultado_codigo", "").strip() or None,
            "resultado_denominacion": f.get("resultado_denominacion", "").strip() or None,
            "resultado_label": f.get("resultado_label", "").strip() or None,
            "duracion": f.get("horas", 0.0),
            "competencia_codigo": f.get("competencia_codigo", "").strip() or None,
            "competencia_nombre": f.get("competencia_nombre", "").strip() or None,
        })

    return {
        "proyecto": basic,
        "fases": output_fases,
        "meta": {
            "source": str(path),
            "fases_count": len(output_fases),
            "actividades_count": rae_count,
        },
        "warnings": warnings[:60],
    }


# ---------------------------------------------------------------------------
# Parser de PDF de diseño curricular
# ---------------------------------------------------------------------------

_COMPETENCE_BLOCK_MARKER = re.compile(
    r"4\.\s*CONTENIDOS CURRICULARES DE LA COMPETENCIA",
    re.I,
)


def _norm(text: str) -> str:
    """Normaliza: quita acentos, estandariza espacios, elimina encabezados de página."""
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    # Remover artefactos (cid:X) de extracción de PDF
    t = re.sub(r"\(cid:\d+\)", " ", t, flags=re.I)
    t = re.sub(r"\(cid:\d+\s*\)", " ", t, flags=re.I)
    t = re.sub(r"cid:\d+", " ", t, flags=re.I)
    t = re.sub(r"Pagina\s*\d+\s*de\s*\d+.*", " ", t, flags=re.I)
    t = re.sub(r"^[ \t]*(LINEA TECNOLOGICA|RED TECNOLOGICA|RED DE CONOCIMIENTO).*$", " ", t, flags=re.I | re.M)
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    t = re.sub(r"\n{2,}", "\n", t)
    return t


# ... (resto del código de catalog_importer continuaría aquí)