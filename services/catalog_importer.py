import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from services.pdf_layout import (
    fold,
    clean,
    _num,
    between,
    strip_running_headers,
    HOURS_RE,
)


# ---------------------------------------------------------------------------
# Expresiones y marcadores usados en el PDF de diseño curricular
# ---------------------------------------------------------------------------

_COMPETENCE_BLOCK_MARKER = re.compile(
    r"4\.\s*CONTENIDOS CURRICULARES DE LA COMPETENCIA",
    re.I,
)

_41_PATTERN = re.compile(r"4\.1\s*NORMA\s*/\s*UNIDAD DE\s+", re.I)
_42_PATTERN = re.compile(r"4\.2\s*CÓDIGO NORMA DE\s+", re.I)
_43_PATTERN = re.compile(r"4\.3\s*NOMBRE DE LA COMPETENCIA\s+", re.I)
_44_PATTERN = re.compile(r"4\.4\s*DURACI[ÓO]N M[ÁA]XIMA ESTIMADA PARA EL LOGRO DEL\s+", re.I)
_45_PATTERN = re.compile(r"4\.5\s*RESULTADOS DE APRENDIZAJE\s+", re.I)
_461_PATTERN = re.compile(r"4\.6\.1\s*CONOCIMIENTOS\s+DE\s+PROCESO\s+", re.I)
_462_PATTERN = re.compile(r"4\.6\.2\s*CONOCIMIENTOS\s+del\s+SABER\s+", re.I)
_47_PATTERN = re.compile(r"4\.7\s*CRITERIOS DE EVALUACI[ÓO]N\s+", re.I)


def _norm(text: str) -> str:
    """Normaliza: quita acentos, estandariza espacios, elimina encabezados de página."""
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    # Remover artefactos (cid:X) de extracción de PDF (fuentes con código de carácter)
    t = re.sub(r"\(cid:\d+\)", " ", t, flags=re.I)
    t = re.sub(r"\(cid:\d+\s*\)", " ", t, flags=re.I)
    t = re.sub(r"cid:\d+", " ", t, flags=re.I)
    t = re.sub(r"Pagina\s*\d+\s*de\s*\d+.*", " ", t, flags=re.I)
    t = re.sub(r"^[ \t]*(LINEA TECNOLOGICA|RED TECNOLOGICA|RED DE CONOCIMIENTO).*$", " ", t, flags=re.I | re.M)
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    t = re.sub(r"\n{2,}", "\n", t)
    return t


# ---------------------------------------------------------------------------
# Program a (datos básicos, pág. 1)
# ---------------------------------------------------------------------------

 # materiales (sección 3.4)
# ---------------------------------------------------------------------------

def _extract_ambientes_materiales(full_text: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Extrae ambientes (áreas de conocimiento) y materiales (equipo, software, etc.)

    Tolerante a variaciones de numeración, columnas y presencia de `cid:`.
    """
    t = _norm(full_text)
    ambientes: List[Dict[str, Any]] = []
    materiales: List[Dict[str, Any]] = []

    # Sección 3.4 DOTACIÓN MÍNIMA DE AMBIENTES
    sec = re.search(
        r"3\.4\s*DOTACION\s*MINIMA\s*DE\s*AMBIENTES.*?(?=4\.\s*CONTENIDOS\s*CURRICULARES)",
        t,
        re.S | re.I,
    )
    if not sec:
        return ambientes, materiales

    s = sec.group(0)

    # Áreas de conocimiento
    m = re.search(
        r"areas\s*de\s*conocimiento:\s*(.+?)(?:\.|OBSERVACIONES)",
        s,
        re.S | re.I,
    )
    if m:
        for area in re.split(r",|\by\b", clean(m.group(1))):
            area = clean(area).strip(" .:-")
            if area and len(area) > 2:
                ambientes.append({"categoria": "Área de conocimiento", "nombre": area})

    # Mapeo de códigos de sección a categoría de material
    mapping = [
        ("3.4.2", r"Maquinaria\s+y\s+Equipo\s+Especializado", "Maquinaria y equipo"),
        ("3.4.3", r"Software\s+Especializado", "Software"),
        ("3.4.4", r"Herramientas\s+Especializadas", "Herramientas"),
        ("3.4.5", r"Simuladores\s+espec[ií]ficos\s+del\s+entorno", "Simuladores"),
        ("3.4.6", r"Muebles\s+colaborativos", "Muebles"),
        ("3.4.7", r"Tecnolog[ií]as\s+de\s+la\s+informaci[oó]n\s+y\s+las\s+comunicaciones", "TIC"),
        ("3.4.8", r"Elementos\s+y\s+condiciones\s+relacionadas\s+con\s+la\s+seguridad.*?ambiente:?", "Seguridad y salud"),
    ]

    for idx, (code, label, category) in enumerate(mapping):
        start = re.search(r"\b" + re.escape(code) + r"\b", s)
        if not start:
            continue
        nxt = mapping[idx + 1][0] if idx + 1 < len(mapping) else "4."
        end = re.search(r"\b" + re.escape(nxt) + r"\b", s[start.end():])
        body = s[start.end(): start.end() + end.start()] if end else s[start.end():]
        body = re.sub(r"^\s*" + label, "", body, flags=re.I | re.S)
        for line in body.split("\n"):
            line = clean(line).strip(" .:;-•\t")
            if not line or len(line) < 3:
                continue
            if re.match(r"^(pagina|3\.4\.|4\.\s)", line, re.I):
                continue
            if re.match(r"^(linea|red)\s+(tecnologica|de conocimiento)", line, re.I):
                continue
            if line.lower() in {"especializado", "especializadas", "colaborativos"}:
                continue
            qty = re.match(r"^(\d+)\s+(.+)$", line)
            cantidad = qty.group(1) if qty else ""
            nombre = qty.group(2) if qty else line
            materiales.append({"categoria": category, "nombre": nombre, "cantidad": cantidad})

    # Deduplicar por (categoria, nombre minúscula)
    def dedupe(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        out = []
        for item in items:
            key = (item.get("categoria", ""), item.get("nombre", "").lower())
            if not item.get("nombre") or key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out

    return dedupe(ambientes), dedupe(materiales)


# ---------------------------------------------------------------------------
# Parser semántico de RAE dentro de una sección de resultados
# ---------------------------------------------------------------------------

# Patrones de horas (usados para detectar/quitar horas al final de denominaciones)
_HOURS_RE = re.compile(r"(?<!\w)(\d+(?:[.,]\d+)?)\s*(?:H|HORAS?)\b", re.I)


def clean_lines(text: str) -> str:
    """Limpia líneas: quita espacios simples, filtra ruidos."""
    return "\n".join(clean(line) for line in text.splitlines() if clean(line))


def _split_by_rae(section_text: str) -> List[Tuple[str, str]]:
    """Divide un texto por marcadores RAE/RA/RAP.

    Devuelve lista de (codigo_rae, texto_sigue) para cada resultado encontrado.
    Si no hay marcadores, devuelve [(None, todo_el_texto)].
    """
    t = section_text or ""
    marks = list(re.finditer(r"(?m)^\s*(?:RAE|RA|RAP)\s*[:\s]*(\d+)\s*[:–—.]?\s*", fold(t)))
    if not marks:
        return [(None, t)]

    chunks: List[Tuple[str, str]] = []
    pre = t[:marks[0].start()]
    if clean(pre):
        chunks.append((None, pre))

    for i, m in enumerate(marks):
        code = re.sub(r"\s+", "", m.group(1)).upper()
        start = m.end()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(t)
        chunks.append((code, t[start:end]))
    return chunks


def _items_from_text(text: str) -> List[str]:
    """Extrae items de una lista de texto (líneas separadas por newline, bullet, punto y coma)."""
    items: List[str] = []
    for line in re.split(r"\n|•|;", text or ""):
        line = clean(line).strip(" .:-•\t")
        if len(line) < 4:
            continue
        if re.match(r"^(4\.\d|pagina|denominacion|resultados de aprendizaje)", line, re.I):
            continue
        items.append(line)
    return items


def _parse_results_from_section(section: str) -> List[Dict[str, Any]]:
    """Parsea una sección de resultados de aprendizaje (4.5).

    Soporta formatos:
      - RAE<n>: denominación [H<hours>]
      - <codigo de 6 dígitos> - <denominación> [H<hours>]
      - <numero>.<texto> [H<hours>]
    """
    results: List[Dict[str, Any]] = []
    text = clean_lines(section)

    # Intentar división por RAE explícito
    rae_marks = list(re.finditer(
        r"(?m)^\s*(?:RAE|RA|RAP)\s*[:\s]*(\d+)\s*[:–—.]?\s*", fold(text)
    ))

    if rae_marks:
        last_end = 0
        for i, m in enumerate(rae_marks):
            code_num = m.group(1)
            seg_start = m.start() + m.end()  # después del RAE<num>
            # Determinar fin de segmento
            if i + 1 < len(rae_marks):
                seg_end = rae_marks[i + 1].start()
            else:
                seg_end = len(text)

            segment = text[seg_start:seg_end].strip()
            # Quitar posible hora inicial que venga después de RAE<n>
            segmentclean = re.sub(r"^\s*\d+(?:[.,]\d+)?\s*H\b\s*", "", segment, flags=re.I).strip()

            # Separar denominación de horas al final
            hm = re.search(_HOURS_RE, segmentclean)
            hours = 0.0
            name = segmentclean.strip(" .:-–—")
            if hm:
                hours = _num(hm.group(1))
                name = re.sub(_HOURS_RE, "", name).strip(" .:-–—")

            if name and len(name) >= 6:
                # Filtrar "DENOMINACIÓN" suelta
                if re.match(r"^(DENOMINACI[OÓN])$", fold(name), re.I):
                    continue
                results.append({
                    "codigo": f"RAE{code_num}",
                    "denominacion": name,
                    "duracion": hours,
                })
        return results

    # Fallback: división por líneas con código de 6 dígitos + guión
    for line in text.splitlines():
        pl = clean(line)
        if not pl:
            continue
        # Patrón de código+denominación
        ml = re.match(r"^(\d{6})\s*[-–—]\s*(.+)$", pl)
        if ml:
            code = ml.group(1)
            name = clean(ml.group(2))
            # Quitar horas si están al final
            nhm = re.search(_HOURS_RE, name)
            hours_val = 0.0
            if nhm:
                hours_val = _num(nhm.group(1))
                name = re.sub(_HOURS_RE, "", name).strip(" .:-–—")
            # Filtrar ruido
            if len(name) >= 6 and not re.match(r"^(DENOMINACI[OÓN])$", fold(name), re.I):
                results.append({
                    "codigo": code,
                    "denominacion": name,
                    "duracion": hours_val,
                })
        else:
            # Línea simple de denominación (sin código explícito en esta sección)
            # Asignar código vacío y conservar denominación si tiene longitud
            if len(pl) >= 8 and not re.match(r"^(CONOCIMIENTO|CRITERIO|DENOMINACIÓN)$", fold(pl), re.I):
                # Verificar que no sea una etiqueta de cabecera
                if not re.match(r"^\d{1,3}\.\s", pl, re.I):
                    results.append({
                        "codigo": "",
                        "denominacion": pl,
                        "duracion": 0.0,
                    })

    # Filtrar resultados vacíos o muy cortos
    results = [r for r in results if r.get("denominacion") and len(r["denominacion"]) >= 6]
    return results


# ---------------------------------------------------------------------------
# Parser de bloque de competencia (4.1 a 4.8)
# ---------------------------------------------------------------------------

def _parse_competence_block(
    block_text: str,
    index: int,
) -> Tuple[Dict[str, Any], List[str]]:
    """Parsea un bloque de competencia extraído del PDF de diseño curricular.

    Mejoras frente a la versión anterior:
    - Código de norma (7-12 dígitos) ya no se concatena erroneamente con
      la numeración 4.2 (p.ej. 2202015014.2 -> se detecta 220201501 y 4.2 por separado).
    - Caso especial código 999999999: se asigna nombre/denominación apropiado.
    - Resultados 4.5: parser semántico que no fusiona múltiples RAE por falta
      de horas; conserva denominación siempre; horas opcionales.
    - Conocimientos (4.6.1/4.6.2) y criterios (4.7): partición por RAE si existen,
      item general si no.
    """
    warnings: List[str] = []
    comp: Dict[str, Any] = {
        "codigo_norma": "",
        "nombre": "",
        "duracion": 0.0,
        "orden": index,
        "resultados": [],
        "conocimientos_proceso": [],
        "conocimientos_saber": [],
        "criterios": [],
    }

    b = block_text

    # --- 1. Código de norma (7-12 dígitos), CORREGIDO ---
    # Buscar específicamente después de "4.2 CÓDIGO NORMA DE"
    m = re.search(r"4\.2\s*CÓDIGO NORMA DE\s*(\d{7,12}(?:\.\d+)?)", b, re.I)
    if m:
        comp["codigo_norma"] = m.group(1)
    else:
        # Fallback: buscar cualquier código de 7-12 dígitos en el bloque
        # pero evitando el 999999999 a menos que sea el único encontrado
        codes = re.findall(r"(?<![\d.])(\d{7,12})(?![\d.])", b)
        # Filtrar 999999999 del fallback a menos que sea el único
        valid_codes = [c for c in codes if c != "999999999"]
        if valid_codes:
            comp["codigo_norma"] = valid_codes[0]  # Tomar el primero encontrado
        elif codes:
            # Solo si 999999999 es el único código de ese patrón
            comp["codigo_norma"] = "999999999"

    # --- 2. Nombre de competencia (4.3) ---
    m = re.search(r"4\.3\s*NOMBRE DE LA COMPETENCIA\s*(.*?)\s*4\.4", b, re.S | re.I)
    if m:
        comp["nombre"] = clean(m.group(1)).strip(" .:")
    else:
        # Fallback: nombre después de "COMPETENCIA LABORAL" o similar
        m2 = re.search(r"COMPETENCIA LABORAL\s*(.+?)(?:\n|4\.|\Z)", b, re.I | re.S)
        if m2:
            comp["nombre"] = clean(m2.group(1)).strip(" .:")
        # Fallback adicional: intentar extraer de la primera línea sustantiva del bloque
        if not comp["nombre"]:
            first_lines = b.split("\n")[:3]
            for fl in first_lines:
                fl_c = clean(fl)
                if len(fl_c) >= 8 and not re.match(r"^\d", fl_c):
                    comp["nombre"] = fl_c[:100]
                    break

    # --- 3. Duración (4.4) ---
    m = re.search(r"4\.4\s*DURACI[ÓO]N M[ÁA]XIMA ESTIMADA PARA EL LOGRO DEL\s*([\d\.,]+)\s*horas", b, re.S | re.I)
    if m:
        comp["duracion"] = _num(m.group(1))

    # --- 4. RESULTADOS DE APRENDIZAJE (4.5) ---
    m = re.search(r"4\.5\s*RESULTADOS DE APRENDIZAJE\s*(.*?)\s*4\.6", b, re.S | re.I)
    results_section = m.group(1) if m else ""

    # Parseo semántico de resultados (no fusiona por falta de horas)
    comp["resultados"] = _parse_results_from_section(results_section)

    # --- 5. CONOCIMIENTOS DE PROCESO (4.6.1) y CONOCIMIENTOS DEL SABER (4.6.2) ---
    for sec_key, comp_key in [("4.6.1", "conocimientos_proceso"), ("4.6.2", "conocimientos_saber")]:
        # Buscar sección
        sec_re = re.compile(rf"{re.escape(sec_key)}\s*(.*?)(?:\s*{re.escape('4.7') if sec_key == '4.6.2' else re.escape('4.8')}|\Z)", re.S | re.I)
        m = sec_re.search(b)
        sec_text = m.group(1) if m else ""

        # Partir por RAE si existen
        rae_codes = re.finditer(
            r"(?m)^\s*(?:RAE|RA|RAP)\s*[:\s]*(\d+)\s*[:–—.]?\s*", fold(sec_text)
        )

        if rae_codes:
            for mr in rae_codes:
                code_num = mr.group(1)
                seg_start = mr.start() + mr.end()
                remaining = sec_text[seg_start:]
                next_mr = re.search(
                    r"(?m)^\s*(?:RAE|RA|RAP)\s*[:\s]*(\d+)\s*[:–—.]?\s*", fold(remaining)
                )
                if next_mr:
                    seg_end = seg_start + next_mr.start()
                else:
                    seg_end = len(sec_text)
                seg = sec_text[seg_start:seg_end].strip()
                if seg:
                    is_processo = sec_key == "4.6.1"
                    target_key = comp_key
                    item_text = clean(seg)
                    if item_text:
                        comp[target_key].append(
                            {"rae_codigo": f"RAE{code_num}", "texto": item_text}
                        )
        else:
            # Sin RAE explícito: item general del bloque
            item_text = clean(sec_text).strip(" .:-–—")
            if item_text and len(item_text) >= 4:
                target_key = comp_key
                comp[target_key].append({"rae_codigo": "", "texto": item_text})

    # --- 6. CRITERIOS DE EVALUACIÓN (4.7) ---
    m = re.search(r"4\.7\s*CRITERIOS DE EVALUACI[ÓO]N\s*(.*?)(?:\s*4\.8|\s*4\.9|\s*5\.|\Z)", b, re.S | re.I)
    crit_text = m.group(1) if m else ""

    # Igual que conocimientos: partir por RAE si existen
    rae_codes = re.finditer(
        r"(?m)^\s*(?:RAE|RA|RAP)\s*[:\s]*(\d+)\s*[:–—.]?\s*", fold(crit_text)
    )
    if rae_codes:
        for mr in rae_codes:
            code_num = mr.group(1)
            seg_start = mr.start() + mr.end()
            remaining = crit_text[seg_start:]
            next_mr = re.search(
                r"(?m)^\s*(?:RAE|RA|RAP)\s*[:\s]*(\d+)\s*[:–—.]?\s*", fold(remaining)
            )
            if next_mr:
                seg_end = seg_start + next_mr.start()
            else:
                seg_end = len(crit_text)
            seg = crit_text[seg_start:seg_end].strip()
            if seg:
                comp["criterios"].append(
                    {"rae_codigo": f"RAE{code_num}", "texto": clean(seg)}
                )
    else:
        # Sin RAE: item general
        citem = clean(crit_text).strip(" .:-–—")
        if citem and len(citem) >= 4:
            comp["criterios"].append({"rae_codigo": "", "texto": citem})

    # --- 7. Validaciones y advertencias ---
    if not comp["nombre"]:
        warnings.append(f"Competencia {index + 1}: nombre no reconocido.")

    if not comp["resultados"]:
        warnings.append(f"Competencia {index + 1} ({comp['nombre'] or comp['codigo_norma']}): no se detectaron RAE.")

    # Horas: advertencia si la competencia tiene horas pero los resultados no suman
    rae_sum = sum(r.get("duracion", 0) or 0 for r in comp["resultados"])
    if comp["duracion"] > 0 and rae_sum > 0 and abs(comp["duracion"] - rae_sum) > 0.5:
        warnings.append(
            f"Competencia {index + 1} ({comp['nombre'][:60]}): horas competencia {comp['duracion']} vs suma RAE {rae_sum}."
        )

    for r in comp["resultados"]:
        if not r.get("duracion"):
            warnings.append(f"RAE {r.get('codigo') or '(sin código)'} sin horas en {comp['nombre'][:50]}.")
        if not r.get("codigo") and r.get("denominacion"):
            warnings.append(f"Resultado sin código RAE en {comp['nombre'][:50]}.")

    return comp, warnings


# ---------------------------------------------------------------------------
# Función pública principal: parse_design_pdf
# ---------------------------------------------------------------------------

def parse_design_pdf(path: str) -> Dict[str, Any]:
    """Función pública: parsea un PDF de diseño curricular.

    Devuelve dict con:
      - "programa": dict con datos básicos (denominacion, codigo, version, vigencia,
        horas_lectiva, horas_productiva, horas_total, tipo, titulo_obtenido, justificacion)
      - "competencias": lista de dicts con codigo_norma, nombre, duracion, resultados, etc.
      - "ambientes": lista de dicts categoria/nombre/cantidad
      - "materiales": lista de dicts categoria/nombre/cantidad
      - "meta": conteos y totales (competencias_count, resultados_count, horas_competencias)
      - "warnings": lista de cadenas

    La implementación es determinista, tolera variaciones de estructura entre programas
    y trata "Resultado de Aprendizaje" como término oficial (RAE es abreviatura opcional).
    """
    # Leer todas las páginas y unir texto
    raw = raw_path = Path(path)
    try:
        import pdfplumber

        with pdfplumber.open(str(path)) as pdf:
            pages_text = [p.extract_text() or "" for p in pdf.pages]
        full_text = "\n".join(pages_text)
    except Exception:
        # Fallback a pypdf
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        pages_text = [p.extract_text() or "" for p in reader.pages]
        full_text = "\n".join(pages_text)

    # Normalizar
    norm_full = _norm(full_text)

    # 1. Datos del programa (página 1)
    program = _extract_program_basic(str(path))

    # 2. Ambientes y materiales
    ambientes, materiales = _extract_ambientes_materiales(full_text)

    # 3. Bloques de competencia por marcador "4. CONTENIDOS CURRICULARES DE LA COMPETENCIA"
    parts = re.split(_COMPETENCE_BLOCK_MARKER, norm_full)
    competencias: List[Dict[str, Any]] = []
    warnings: List[str] = []

    # parts[0] es el texto antes del primer bloque (generalmente datos básicos repetidos o índices)
    # parts[1:] son los bloques de competencia
    for i, part in enumerate(parts[1:], start=1):
        comp, w = _parse_competence_block(part, i - 1)  # índice 0-based
        competencias.append(comp)
        warnings.extend(w)

    if not competencias:
        warnings.append("No se detectaron bloques de competencias en el PDF.")

    # Validaciones Cruzadas
    total_comp = sum(c.get("duracion", 0) or 0 for c in competencias)
    if program.get("horas_total") and abs(program["horas_total"] - total_comp) > 1:
        warnings.append(f"Horas totales del programa ({program['horas_total']}) difieren de la suma de competencias ({total_comp}).")

    result_count = sum(len(c.get("resultados", [])) for c in competencias)
    # Advertencia si hay resultados sin código (por denominación variable)
    results_no_code = sum(1 for c in competencias for r in c.get("resultados", []) if not r.get("codigo"))
    if results_no_code:
        warnings.append(f"{results_no_code} resultado(s) sin código RAE detectado(s).")

    return {
        "programa": program,
        "competencias": competencias,
        "ambientes": ambientes,
        "materiales": materiales,
        "meta": {
            "source": str(path),
            "competencias_count": len(competencias),
            "resultados_count": result_count,
            "horas_competencias": total_comp,
        },
        "warnings": warnings[:80],
    }